#!/usr/bin/env python3
from __future__ import annotations

import argparse
import dataclasses
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid


REPO_ROOT = Path(__file__).resolve().parent.parent
SCANNER_SCRIPT = REPO_ROOT / "scripts" / "opportunity_scanner.py"
GITHUB_MONITOR_SCRIPT = REPO_ROOT / "scripts" / "run_github_monitor.py"
DEFAULT_CONFIG_PATH = REPO_ROOT / "config" / "autonomous-loop.json"
SECRET_ENV_NAMES = (
    "GITHUB_TOKEN",
    "GH_TOKEN",
    "TELEGRAM_BOT_TOKEN",
    "TG_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "TG_CHAT_ID",
    "REDDIT_ACCESS_TOKEN",
    "REDDIT_CLIENT_SECRET",
)
STDIO_TAIL_LIMIT = 1600
GITHUB_API_BASE = "https://api.github.com"
GITHUB_API_VERSION = "2026-03-10"
REDDIT_ALLOWED_SORTS = {"hot", "new", "top"}
FAILURE_ISSUE_MARKER_PREFIX = "<!-- opportunity-scanner:autonomous-loop-failure="
FAILURE_ISSUE_LABEL_SPECS = {
    "opportunity-scanner": ("0366d6", "Managed by the Opportunity Scanner."),
    "autonomous-loop": ("5319e7", "Autonomous scanner control loop."),
    "type:failure": ("b60205", "Autonomous loop failure or recovery."),
}


class LoopConfigError(ValueError):
    pass


class LoopRunError(RuntimeError):
    pass


class LoopStepError(LoopRunError):
    def __init__(self, message: str, record: dict[str, object]) -> None:
        super().__init__(message)
        self.record = record


class LoopJobError(LoopRunError):
    def __init__(self, message: str, records: list[dict[str, object]]) -> None:
        super().__init__(message)
        self.records = records


@dataclasses.dataclass(frozen=True)
class LoopJob:
    job_id: str
    job_type: str
    enabled: bool
    interval_hours: int
    send_telegram: bool
    config: Path
    feeds: list[str]
    max_stories: int
    comments_per_story: int
    max_total_items: int
    max_clusters: int
    max_candidates: int
    ingest: bool
    post_pipeline: bool
    deep_review_max_candidates: int
    ecosystems_enrich: bool
    ecosystems_max_candidates: int
    repo_digest_batch: bool
    repo_digest_max_candidates: int
    repo_digest_max_files: int
    repo_digest_max_bytes: int
    repo_digest_clone_timeout_seconds: int
    mirror_github_issues: bool
    mirror_repo: str
    mirror_verdicts: list[str]
    sync_github_project: bool
    project_owner: str
    project_number: int
    project_id: str
    subreddits: list[str]
    reddit_sort: str
    max_posts_per_subreddit: int
    chat_id: str
    source_input: Path
    source_verdicts: list[str]
    min_score: int
    external_command: list[str]


@dataclasses.dataclass(frozen=True)
class FailureIssueConfig:
    enabled: bool
    repo: str
    api_base: str
    labels: list[str]


@dataclasses.dataclass(frozen=True)
class LoopConfig:
    enabled: bool
    data_dir: Path
    state_path: Path
    lock_path: Path
    lock_stale_minutes: int
    health_stale_grace_hours: int
    command_timeout_seconds: int
    max_jobs_per_tick: int
    send_telegram: bool
    failure_issues: FailureIssueConfig
    jobs: list[LoopJob]


@dataclasses.dataclass(frozen=True)
class CommandOutcome:
    returncode: int
    stdout: str
    stderr: str


def utc_now() -> str:
    return (
        datetime.datetime.now(datetime.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def compact_utc_stamp() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def default_week() -> str:
    today = datetime.date.today()
    year, week, _ = today.isocalendar()
    return f"{year}-W{week:02d}"


def parse_utc_timestamp(value: object) -> datetime.datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed.astimezone(datetime.timezone.utc)


def repo_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def safe_issue_path_ref(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return path.name


def repo_path(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


def read_json_file(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise LoopConfigError("Autonomous loop config must be a JSON object.")
    return payload


def read_json_object(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise LoopRunError(f"Expected JSON object at {path}")
    return payload


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def positive_int(value: object, field_name: str, *, allow_zero: bool = False) -> int:
    if not isinstance(value, int):
        raise LoopConfigError(f"{field_name} must be an integer.")
    if allow_zero:
        if value < 0:
            raise LoopConfigError(f"{field_name} must be >= 0.")
    elif value <= 0:
        raise LoopConfigError(f"{field_name} must be > 0.")
    return value


def text_value(value: object, field_name: str, *, required: bool = False) -> str:
    if value is None:
        if required:
            raise LoopConfigError(f"{field_name} is required.")
        return ""
    if not isinstance(value, str):
        raise LoopConfigError(f"{field_name} must be a string.")
    cleaned = value.strip()
    if required and not cleaned:
        raise LoopConfigError(f"{field_name} is required.")
    return cleaned


def bool_value(value: object, field_name: str, default: bool) -> bool:
    if value is None:
        return default
    if not isinstance(value, bool):
        raise LoopConfigError(f"{field_name} must be a boolean.")
    return value


def text_list(value: object, field_name: str, default: list[str]) -> list[str]:
    if value is None:
        return list(default)
    if not isinstance(value, list):
        raise LoopConfigError(f"{field_name} must be a list.")
    result: list[str] = []
    for index, item in enumerate(value, 1):
        text = text_value(item, f"{field_name}[{index}]", required=True)
        if text not in result:
            result.append(text)
    return result


def clean_env_value(raw: str) -> str:
    value = raw.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def load_env_file_into(env: dict[str, str], path: Path) -> list[str]:
    if not path.exists():
        return []
    loaded: list[str] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            raise LoopConfigError(f"Invalid env line at {path}:{line_number}")
        key, raw_value = stripped.split("=", 1)
        key = key.strip()
        if not key or not (key[0].isalpha() or key[0] == "_") or not all(character.isalnum() or character == "_" for character in key):
            raise LoopConfigError(f"Invalid env key at {path}:{line_number}")
        if key not in env:
            env[key] = clean_env_value(raw_value)
            loaded.append(key)
    return loaded


def load_loop_config(path: Path) -> LoopConfig:
    raw = read_json_file(path)
    raw_jobs = raw.get("jobs")
    if not isinstance(raw_jobs, list):
        raise LoopConfigError("jobs must be a list.")
    raw_failure = raw.get("failure_issue_reporting", {})
    if raw_failure is None:
        raw_failure = {}
    if not isinstance(raw_failure, dict):
        raise LoopConfigError("failure_issue_reporting must be an object.")
    failure_issues = FailureIssueConfig(
        enabled=bool_value(raw_failure.get("enabled"), "failure_issue_reporting.enabled", False),
        repo=text_value(raw_failure.get("repo"), "failure_issue_reporting.repo"),
        api_base=text_value(raw_failure.get("api_base", GITHUB_API_BASE), "failure_issue_reporting.api_base") or GITHUB_API_BASE,
        labels=text_list(
            raw_failure.get("labels"),
            "failure_issue_reporting.labels",
            ["opportunity-scanner", "autonomous-loop", "type:failure"],
        ),
    )

    data_dir = Path(text_value(raw.get("data_dir", "data"), "data_dir") or "data")
    jobs: list[LoopJob] = []
    job_ids: set[str] = set()
    for index, item in enumerate(raw_jobs, 1):
        if not isinstance(item, dict):
            raise LoopConfigError(f"jobs[{index}] must be an object.")
        job_id = text_value(item.get("id"), f"jobs[{index}].id", required=True)
        if job_id in job_ids:
            raise LoopConfigError(f"Duplicate job id: {job_id}")
        job_ids.add(job_id)
        job_type = text_value(item.get("type"), f"jobs[{index}].type", required=True)
        if job_type not in {"github-monitor", "hn-demand", "reddit-demand", "telegram-feedback", "oss-bounty-radar"}:
            raise LoopConfigError(f"Unsupported job type for {job_id}: {job_type}")
        reddit_sort = text_value(item.get("sort", "hot"), f"jobs[{index}].sort") or "hot"
        if reddit_sort not in REDDIT_ALLOWED_SORTS:
            raise LoopConfigError(f"jobs[{index}].sort must be one of: {', '.join(sorted(REDDIT_ALLOWED_SORTS))}")
        jobs.append(
            LoopJob(
                job_id=job_id,
                job_type=job_type,
                enabled=bool_value(item.get("enabled"), f"jobs[{index}].enabled", True),
                interval_hours=positive_int(item.get("interval_hours", 24), f"jobs[{index}].interval_hours"),
                send_telegram=bool_value(item.get("send_telegram"), f"jobs[{index}].send_telegram", False),
                config=Path(text_value(item.get("config", "config/github-monitor.json"), f"jobs[{index}].config") or "config/github-monitor.json"),
                feeds=text_list(item.get("feeds"), f"jobs[{index}].feeds", ["askstories", "showstories"]),
                max_stories=positive_int(item.get("max_stories", 40), f"jobs[{index}].max_stories", allow_zero=True),
                comments_per_story=positive_int(
                    item.get("comments_per_post", item.get("comments_per_story", 10)),
                    f"jobs[{index}].comments_per_story",
                    allow_zero=True,
                ),
                max_total_items=positive_int(item.get("max_total_items", 300), f"jobs[{index}].max_total_items", allow_zero=True),
                max_clusters=positive_int(item.get("max_clusters", 6), f"jobs[{index}].max_clusters", allow_zero=True),
                max_candidates=positive_int(item.get("max_candidates", 3), f"jobs[{index}].max_candidates", allow_zero=True),
                ingest=bool_value(item.get("ingest"), f"jobs[{index}].ingest", True),
                post_pipeline=bool_value(item.get("post_pipeline"), f"jobs[{index}].post_pipeline", True),
                deep_review_max_candidates=positive_int(
                    item.get("deep_review_max_candidates", 3),
                    f"jobs[{index}].deep_review_max_candidates",
                    allow_zero=True,
                ),
                ecosystems_enrich=bool_value(item.get("ecosystems_enrich"), f"jobs[{index}].ecosystems_enrich", False),
                ecosystems_max_candidates=positive_int(
                    item.get("ecosystems_max_candidates", 5),
                    f"jobs[{index}].ecosystems_max_candidates",
                    allow_zero=True,
                ),
                repo_digest_batch=bool_value(item.get("repo_digest_batch"), f"jobs[{index}].repo_digest_batch", False),
                repo_digest_max_candidates=positive_int(
                    item.get("repo_digest_max_candidates", 1),
                    f"jobs[{index}].repo_digest_max_candidates",
                    allow_zero=True,
                ),
                repo_digest_max_files=positive_int(
                    item.get("repo_digest_max_files", 80),
                    f"jobs[{index}].repo_digest_max_files",
                    allow_zero=True,
                ),
                repo_digest_max_bytes=positive_int(
                    item.get("repo_digest_max_bytes", 500000),
                    f"jobs[{index}].repo_digest_max_bytes",
                    allow_zero=True,
                ),
                repo_digest_clone_timeout_seconds=positive_int(
                    item.get("repo_digest_clone_timeout_seconds", 90),
                    f"jobs[{index}].repo_digest_clone_timeout_seconds",
                    allow_zero=True,
                ),
                mirror_github_issues=bool_value(item.get("mirror_github_issues"), f"jobs[{index}].mirror_github_issues", False),
                mirror_repo=text_value(item.get("mirror_repo"), f"jobs[{index}].mirror_repo"),
                mirror_verdicts=text_list(
                    item.get("mirror_verdicts"),
                    f"jobs[{index}].mirror_verdicts",
                    ["watchlist", "proof-card", "PRD-lite", "operator-proof-approved"],
                ),
                sync_github_project=bool_value(item.get("sync_github_project"), f"jobs[{index}].sync_github_project", False),
                project_owner=text_value(item.get("project_owner"), f"jobs[{index}].project_owner"),
                project_number=positive_int(item.get("project_number", 0), f"jobs[{index}].project_number", allow_zero=True),
                project_id=text_value(item.get("project_id"), f"jobs[{index}].project_id"),
                subreddits=text_list(item.get("subreddits"), f"jobs[{index}].subreddits", []),
                reddit_sort=reddit_sort,
                max_posts_per_subreddit=positive_int(
                    item.get("max_posts_per_subreddit", 10),
                    f"jobs[{index}].max_posts_per_subreddit",
                    allow_zero=True,
                ),
                chat_id=text_value(item.get("chat_id"), f"jobs[{index}].chat_id"),
                source_input=Path(text_value(item.get("input", item.get("source_input", "")), f"jobs[{index}].input")),
                source_verdicts=text_list(
                    item.get("source_verdicts", item.get("verdicts")),
                    f"jobs[{index}].source_verdicts",
                    ["candidate", "watchlist"],
                ),
                min_score=positive_int(item.get("min_score", 14), f"jobs[{index}].min_score", allow_zero=True),
                external_command=text_list(item.get("external_command"), f"jobs[{index}].external_command", []),
            )
        )

    config = LoopConfig(
        enabled=bool_value(raw.get("enabled"), "enabled", True),
        data_dir=data_dir,
        state_path=Path(text_value(raw.get("state_path", "data/runs/autonomous-loop-state.json"), "state_path") or "data/runs/autonomous-loop-state.json"),
        lock_path=Path(text_value(raw.get("lock_path", "data/runs/autonomous-loop.lock"), "lock_path") or "data/runs/autonomous-loop.lock"),
        lock_stale_minutes=positive_int(raw.get("lock_stale_minutes", 180), "lock_stale_minutes"),
        health_stale_grace_hours=positive_int(raw.get("health_stale_grace_hours", 6), "health_stale_grace_hours", allow_zero=True),
        command_timeout_seconds=positive_int(raw.get("command_timeout_seconds", 240), "command_timeout_seconds"),
        max_jobs_per_tick=positive_int(raw.get("max_jobs_per_tick", 2), "max_jobs_per_tick"),
        send_telegram=bool_value(raw.get("send_telegram"), "send_telegram", False),
        failure_issues=failure_issues,
        jobs=jobs,
    )
    validate_loop_config(config)
    return config


def validate_loop_config(config: LoopConfig) -> None:
    enabled_jobs = [job for job in config.jobs if job.enabled]
    if not enabled_jobs:
        raise LoopConfigError("At least one autonomous loop job must be enabled.")
    if config.failure_issues.enabled and not config.failure_issues.repo:
        raise LoopConfigError("failure_issue_reporting.repo is required when failure issue reporting is enabled.")
    if config.max_jobs_per_tick > len(enabled_jobs):
        return
    if config.max_jobs_per_tick <= 0:
        raise LoopConfigError("max_jobs_per_tick must be > 0.")


def config_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def secret_values(env: dict[str, str]) -> list[str]:
    values: list[str] = []
    for name in SECRET_ENV_NAMES:
        value = env.get(name, "")
        if value:
            values.append(value)
    return values


def sanitize_text(text: str, secrets: list[str]) -> str:
    sanitized = text
    for secret in secrets:
        if secret:
            sanitized = sanitized.replace(secret, "[REDACTED]")
    if len(sanitized) > STDIO_TAIL_LIMIT:
        return sanitized[-STDIO_TAIL_LIMIT:]
    return sanitized


class LoopGitHubClient:
    def __init__(self, token: str, api_base: str, timeout: int) -> None:
        self.token = token
        self.api_base = api_base.rstrip("/")
        self.timeout = timeout

    def request_json(self, method: str, path: str, params: dict[str, object], body: dict[str, object] | None = None) -> object:
        query = urllib.parse.urlencode({key: value for key, value in params.items() if value not in ("", None)})
        url = f"{self.api_base}{path}"
        if query:
            url = f"{url}?{query}"
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
            "User-Agent": "opportunity-scanner-autonomous-loop",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        payload = None
        if body is not None:
            payload = json.dumps(body, ensure_ascii=True).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=payload, headers=headers, method=method)
        response = None
        try:
            response = urllib.request.urlopen(request, timeout=self.timeout)
            raw_body = response.read().decode("utf-8")
            if not raw_body:
                return {}
            return json.loads(raw_body)
        finally:
            if response is not None:
                response.close()

    def get_json(self, path: str, params: dict[str, object]) -> object:
        return self.request_json("GET", path, params)

    def post_json(self, path: str, body: dict[str, object]) -> object:
        return self.request_json("POST", path, {}, body)

    def patch_json(self, path: str, body: dict[str, object]) -> object:
        return self.request_json("PATCH", path, {}, body)


def first_env_value(env: dict[str, str], names: tuple[str, ...]) -> str:
    for name in names:
        value = str(env.get(name, "")).strip()
        if value:
            return value
    return ""


def github_owner_repo(repo: str) -> tuple[str, str]:
    cleaned = repo.removeprefix("https://github.com/").strip("/")
    parts = [part for part in cleaned.split("/") if part]
    if len(parts) != 2:
        raise LoopConfigError("GitHub repo must be in owner/name form")
    return parts[0], parts[1]


def failure_issue_marker(job_id: str) -> str:
    return f"{FAILURE_ISSUE_MARKER_PREFIX}{job_id} -->"


def failure_issue_number(issue: dict[str, object]) -> int | None:
    raw_number = issue.get("number")
    if raw_number in ("", None):
        raw_number = issue.get("issue_number")
    if raw_number in ("", None):
        raw_number = issue.get("open_failure_issue_number")
    if isinstance(raw_number, int):
        return raw_number
    text_number = str(raw_number or "").strip()
    if text_number.isdigit():
        return int(text_number)
    for key in ("html_url", "issue_url", "url"):
        text = str(issue.get(key) or "").rstrip("/")
        tail = text.rsplit("/", 1)[-1]
        if tail.isdigit():
            return int(tail)
    return None


def failure_label_spec(label: str) -> tuple[str, str]:
    if label in FAILURE_ISSUE_LABEL_SPECS:
        return FAILURE_ISSUE_LABEL_SPECS[label]
    return "ededed", "Opportunity Scanner autonomous loop label."


def ensure_failure_label(client: object, repo: str, label: str) -> None:
    owner, name = github_owner_repo(repo)
    color, description = failure_label_spec(label)
    try:
        client.post_json(
            f"/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(name)}/labels",
            {"name": label, "color": color, "description": description},
        )
    except urllib.error.HTTPError as exc:
        if exc.code != 422:
            raise


def ensure_failure_labels(client: object, repo: str, labels: list[str]) -> int:
    count = 0
    for label in labels:
        ensure_failure_label(client, repo, label)
        count += 1
    return count


def search_failure_issue(client: object, repo: str, job_id: str) -> dict[str, object]:
    query = f"repo:{repo} type:issue in:body autonomous-loop-failure {job_id}"
    result = client.get_json("/search/issues", {"q": query, "per_page": 5})
    items = result.get("items") if isinstance(result, dict) else []
    marker = failure_issue_marker(job_id)
    if not isinstance(items, list):
        return {}
    for item in items:
        if not isinstance(item, dict):
            continue
        haystack = "\n".join([str(item.get("title") or ""), str(item.get("body") or "")])
        if marker in haystack or job_id in haystack:
            return item
    for item in items:
        if isinstance(item, dict):
            return item
    return {}


def failure_issue_body(job_record: dict[str, object], run_log_path: Path) -> str:
    job_id = str(job_record.get("job_id") or "unknown")
    error = job_record.get("error") if isinstance(job_record.get("error"), dict) else {}
    commands = job_record.get("commands") if isinstance(job_record.get("commands"), list) else []
    failed_command = {}
    for command in commands:
        if isinstance(command, dict) and command.get("returncode") not in (0, "0", None):
            failed_command = command
            break
    if not failed_command and commands and isinstance(commands[-1], dict):
        failed_command = commands[-1]
    return "\n".join(
        [
            failure_issue_marker(job_id),
            "",
            "## Autonomous Loop Failure",
            "",
            f"- Job: `{job_id}`",
            f"- Type: `{job_record.get('type') or 'unknown'}`",
            f"- Started: `{job_record.get('started_at') or 'unknown'}`",
            f"- Finished: `{job_record.get('finished_at') or 'unknown'}`",
            f"- Error type: `{error.get('type') or 'unknown'}`",
            f"- Error message: {error.get('message') or 'unknown'}",
            f"- Run log: `{safe_issue_path_ref(run_log_path)}`",
            "",
            "## Failed Step",
            "",
            f"- Step: `{failed_command.get('name') or 'unknown'}`",
            f"- Return code: `{failed_command.get('returncode') if failed_command else 'unknown'}`",
            f"- Stderr tail: {failed_command.get('stderr_tail') or 'none'}",
            "",
            "## Operator Notes",
            "",
            "- This issue is updated by the local autonomous loop.",
            "- Repeated failures update this issue instead of creating duplicates.",
            "- Recovery is recorded as a comment; the issue is not auto-closed.",
            "",
        ]
    )


def create_failure_issue(client: object, repo: str, title: str, body: str, labels: list[str]) -> dict[str, object]:
    owner, name = github_owner_repo(repo)
    result = client.post_json(
        f"/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(name)}/issues",
        {"title": title, "body": body, "labels": labels},
    )
    return result if isinstance(result, dict) else {}


def update_failure_issue(client: object, repo: str, issue_number: int, title: str, body: str, labels: list[str]) -> dict[str, object]:
    owner, name = github_owner_repo(repo)
    result = client.patch_json(
        f"/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(name)}/issues/{issue_number}",
        {"title": title, "body": body, "labels": labels},
    )
    return result if isinstance(result, dict) else {}


def comment_failure_issue(client: object, repo: str, issue_number: int, body: str) -> dict[str, object]:
    owner, name = github_owner_repo(repo)
    result = client.post_json(
        f"/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(name)}/issues/{issue_number}/comments",
        {"body": body},
    )
    return result if isinstance(result, dict) else {}


def command_to_log(command: list[str]) -> list[str]:
    return [repo_relative(Path(part)) if part.startswith(str(REPO_ROOT)) else part for part in command]


def parse_json_stdout(stdout: str) -> object:
    stripped = stdout.strip()
    if not stripped:
        return {}
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return {}


def subprocess_runner(command: list[str], cwd: Path, env: dict[str, str]) -> CommandOutcome:
    timeout_text = str(env.get("AUTONOMOUS_LOOP_COMMAND_TIMEOUT_SECONDS", "")).strip()
    timeout = int(timeout_text) if timeout_text.isdigit() else None
    try:
        completed = subprocess.run(command, cwd=cwd, env=env, text=True, capture_output=True, check=False, timeout=timeout)
        return CommandOutcome(returncode=completed.returncode, stdout=completed.stdout, stderr=completed.stderr)
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        stderr = "\n".join(chunk for chunk in [stderr, f"Timed out after {timeout} seconds."] if chunk)
        return CommandOutcome(returncode=124, stdout=stdout, stderr=stderr)


def command_record(
    name: str,
    command: list[str],
    outcome: CommandOutcome,
    started_at: str,
    finished_at: str,
    secrets: list[str],
) -> dict[str, object]:
    return {
        "name": name,
        "command": command_to_log(command),
        "started_at": started_at,
        "finished_at": finished_at,
        "returncode": outcome.returncode,
        "stdout_json": parse_json_stdout(outcome.stdout),
        "stdout_tail": sanitize_text(outcome.stdout, secrets),
        "stderr_tail": sanitize_text(outcome.stderr, secrets),
    }


def run_command(
    name: str,
    command: list[str],
    runner: object,
    env: dict[str, str],
    secrets: list[str],
) -> dict[str, object]:
    started_at = utc_now()
    outcome = runner(command, REPO_ROOT, env)
    finished_at = utc_now()
    record = command_record(name, command, outcome, started_at, finished_at, secrets)
    if outcome.returncode != 0:
        raise LoopStepError(f"Step failed: {name}", record)
    return record


def synthetic_success_record(name: str, stdout_json: dict[str, object]) -> dict[str, object]:
    now = utc_now()
    stdout_tail = json.dumps(stdout_json, ensure_ascii=True, sort_keys=True)
    return {
        "name": name,
        "command": [],
        "started_at": now,
        "finished_at": now,
        "returncode": 0,
        "stdout_json": stdout_json,
        "stdout_tail": stdout_tail,
        "stderr_tail": "",
    }


def scanner_command(data_dir: Path, week: str, *args: str) -> list[str]:
    return [sys.executable, str(SCANNER_SCRIPT), "--data-dir", str(data_dir), "--week", week, *args]


def mirror_command(data_dir: Path, week: str, job: LoopJob) -> list[str]:
    if not job.mirror_repo:
        raise LoopConfigError(f"Job {job.job_id} enables mirror_github_issues without mirror_repo.")
    return scanner_command(
        data_dir,
        week,
        "mirror-github-issues",
        "--repo",
        job.mirror_repo,
        "--verdicts",
        *job.mirror_verdicts,
    )


def project_sync_command(data_dir: Path, week: str, job: LoopJob) -> list[str] | None:
    if not job.sync_github_project:
        return None
    if not job.mirror_repo:
        return None
    project_owner = job.project_owner
    if not project_owner and not job.project_id:
        try:
            project_owner, _ = github_owner_repo(job.mirror_repo)
        except LoopConfigError:
            return None
    if not job.project_id and job.project_number <= 0:
        return None
    command = scanner_command(
        data_dir,
        week,
        "sync-github-project",
        "--repo",
        job.mirror_repo,
    )
    if project_owner:
        command.extend(["--project-owner", project_owner])
    if job.project_number > 0:
        command.extend(["--project-number", str(job.project_number)])
    if job.project_id:
        command.extend(["--project-id", job.project_id])
    return command


def append_project_sync_command(commands: list[tuple[str, list[str]]], data_dir: Path, week: str, job: LoopJob) -> None:
    command = project_sync_command(data_dir, week, job)
    if command is not None:
        commands.append(("sync-github-project", command))


def append_analysis_post_pipeline_commands(
    commands: list[tuple[str, list[str]]],
    data_dir: Path,
    week: str,
    job: LoopJob,
    loop_config: LoopConfig,
    send_requested: bool,
) -> None:
    commands.append(("label", scanner_command(data_dir, week, "label")))
    if job.ecosystems_enrich:
        commands.append(
            (
                "ecosystems-enrich",
                scanner_command(data_dir, week, "ecosystems-enrich", "--max-candidates", str(job.ecosystems_max_candidates)),
            )
        )
    if job.repo_digest_batch:
        commands.append(
            (
                "repo-digest-batch",
                scanner_command(
                    data_dir,
                    week,
                    "repo-digest-batch",
                    "--max-candidates",
                    str(job.repo_digest_max_candidates),
                    "--max-files",
                    str(job.repo_digest_max_files),
                    "--max-bytes",
                    str(job.repo_digest_max_bytes),
                    "--clone-timeout-seconds",
                    str(job.repo_digest_clone_timeout_seconds),
                ),
            )
        )
    deep_review_command = scanner_command(data_dir, week, "deep-review")
    if job.deep_review_max_candidates >= 0:
        deep_review_command.extend(["--max-candidates", str(job.deep_review_max_candidates)])
    commands.append(("deep-review", deep_review_command))
    commands.append(("digest", scanner_command(data_dir, week, "digest")))
    commands.append(("calibration", scanner_command(data_dir, week, "calibration")))
    commands.append(("dashboard", scanner_command(data_dir, week, "dashboard")))
    if job.mirror_github_issues:
        commands.append(("mirror-github-issues", mirror_command(data_dir, week, job)))
    append_project_sync_command(commands, data_dir, week, job)
    commands.append(("send-telegram-digest-dry-run", scanner_command(data_dir, week, "send-telegram-digest", "--dry-run")))
    if send_requested and loop_config.send_telegram and job.send_telegram:
        commands.append(("send-telegram-digest", scanner_command(data_dir, week, "send-telegram-digest", "--skip-empty")))


def job_state(state: dict[str, object], job_id: str) -> dict[str, object]:
    jobs = state.get("jobs")
    if not isinstance(jobs, dict):
        return {}
    row = jobs.get(job_id)
    return row if isinstance(row, dict) else {}


def is_job_due(job: LoopJob, state: dict[str, object], now: datetime.datetime, force: bool) -> tuple[bool, str]:
    if not job.enabled:
        return False, "disabled"
    if force:
        return True, "forced"
    row = job_state(state, job.job_id)
    last_success = parse_utc_timestamp(row.get("last_success_at"))
    if last_success is None:
        return True, "never-succeeded"
    due_at = last_success + datetime.timedelta(hours=job.interval_hours)
    if now >= due_at:
        return True, f"due-since-{due_at.isoformat().replace('+00:00', 'Z')}"
    return False, f"not-due-until-{due_at.isoformat().replace('+00:00', 'Z')}"


def update_job_state(
    state: dict[str, object],
    job: LoopJob,
    status: str,
    started_at: str,
    finished_at: str,
    run_log_path: Path,
) -> dict[str, object]:
    jobs = state.get("jobs")
    if not isinstance(jobs, dict):
        jobs = {}
        state["jobs"] = jobs
    row = {
        "job_id": job.job_id,
        "type": job.job_type,
        "last_started_at": started_at,
        "last_finished_at": finished_at,
        "last_status": status,
        "last_run_log_path": str(run_log_path),
    }
    if status == "success":
        row["last_success_at"] = finished_at
    previous = jobs.get(job.job_id)
    if isinstance(previous, dict) and "last_success_at" in previous and status != "success":
        row["last_success_at"] = previous["last_success_at"]
    if isinstance(previous, dict) and status != "success":
        for key in ("open_failure_issue_number", "open_failure_issue_url"):
            if key in previous:
                row[key] = previous[key]
    jobs[job.job_id] = row
    return state


def run_github_monitor_job(
    job: LoopJob,
    week: str,
    loop_config: LoopConfig,
    send_requested: bool,
    runner: object,
    env: dict[str, str],
    secrets: list[str],
) -> list[dict[str, object]]:
    data_dir = repo_path(loop_config.data_dir)
    command = [
        sys.executable,
        str(GITHUB_MONITOR_SCRIPT),
        "--config",
        str(repo_path(job.config)),
        "--week",
        week,
    ]
    records: list[dict[str, object]] = []
    try:
        records.append(run_command("github-monitor", command, runner, env, secrets))
        if job.mirror_github_issues:
            records.append(run_command("mirror-github-issues", mirror_command(data_dir, week, job), runner, env, secrets))
        project_command = project_sync_command(data_dir, week, job)
        if project_command is not None:
            records.append(run_command("sync-github-project", project_command, runner, env, secrets))
        records.append(run_command("send-telegram-digest-dry-run", scanner_command(data_dir, week, "send-telegram-digest", "--dry-run"), runner, env, secrets))
        if send_requested and loop_config.send_telegram and job.send_telegram:
            records.append(run_command("send-telegram-digest", scanner_command(data_dir, week, "send-telegram-digest", "--skip-empty"), runner, env, secrets))
    except LoopStepError as exc:
        records.append(exc.record)
        raise LoopJobError(str(exc), records) from exc
    return records


def run_hn_demand_job(
    job: LoopJob,
    week: str,
    loop_config: LoopConfig,
    send_requested: bool,
    runner: object,
    env: dict[str, str],
    secrets: list[str],
) -> list[dict[str, object]]:
    data_dir = repo_path(loop_config.data_dir)
    commands: list[tuple[str, list[str]]] = []
    hn_args = [
        "hn-demand",
        "--feeds",
        *job.feeds,
        "--max-stories",
        str(job.max_stories),
        "--comments-per-story",
        str(job.comments_per_story),
        "--max-total-items",
        str(job.max_total_items),
        "--max-clusters",
        str(job.max_clusters),
        "--max-candidates",
        str(job.max_candidates),
    ]
    if job.ingest:
        hn_args.append("--ingest")
    commands.append(("hn-demand", scanner_command(data_dir, week, *hn_args)))
    if job.ingest and job.post_pipeline:
        append_analysis_post_pipeline_commands(commands, data_dir, week, job, loop_config, send_requested)
    records: list[dict[str, object]] = []
    for name, command in commands:
        try:
            records.append(run_command(name, command, runner, env, secrets))
        except LoopStepError as exc:
            records.append(exc.record)
            raise LoopJobError(str(exc), records) from exc
    return records


def run_reddit_demand_job(
    job: LoopJob,
    week: str,
    loop_config: LoopConfig,
    send_requested: bool,
    runner: object,
    env: dict[str, str],
    secrets: list[str],
) -> list[dict[str, object]]:
    data_dir = repo_path(loop_config.data_dir)
    has_token = bool(first_env_value(env, ("REDDIT_ACCESS_TOKEN",)))
    has_client_credentials = bool(first_env_value(env, ("REDDIT_CLIENT_ID",)) and first_env_value(env, ("REDDIT_CLIENT_SECRET",)))
    has_user_agent = bool(first_env_value(env, ("REDDIT_USER_AGENT",)))
    if not job.subreddits:
        return [synthetic_success_record("reddit-demand", {"skipped": True, "reason": "missing-subreddits"})]
    if not has_user_agent:
        return [synthetic_success_record("reddit-demand", {"skipped": True, "reason": "missing-reddit-user-agent"})]
    if not has_token and not has_client_credentials:
        return [synthetic_success_record("reddit-demand", {"skipped": True, "reason": "missing-reddit-oauth"})]
    commands: list[tuple[str, list[str]]] = []
    reddit_args = [
        "reddit-demand",
        "--subreddits",
        *job.subreddits,
        "--sort",
        job.reddit_sort,
        "--max-posts-per-subreddit",
        str(job.max_posts_per_subreddit),
        "--comments-per-post",
        str(job.comments_per_story),
        "--max-total-items",
        str(job.max_total_items),
        "--max-clusters",
        str(job.max_clusters),
        "--max-candidates",
        str(job.max_candidates),
    ]
    if job.ingest:
        reddit_args.append("--ingest")
    commands.append(("reddit-demand", scanner_command(data_dir, week, *reddit_args)))
    if job.ingest and job.post_pipeline:
        append_analysis_post_pipeline_commands(commands, data_dir, week, job, loop_config, send_requested)
    records: list[dict[str, object]] = []
    for name, command in commands:
        try:
            records.append(run_command(name, command, runner, env, secrets))
        except LoopStepError as exc:
            records.append(exc.record)
            raise LoopJobError(str(exc), records) from exc
    return records


def run_telegram_feedback_job(
    job: LoopJob,
    week: str,
    loop_config: LoopConfig,
    runner: object,
    env: dict[str, str],
    secrets: list[str],
) -> list[dict[str, object]]:
    data_dir = repo_path(loop_config.data_dir)
    if not first_env_value(env, ("TELEGRAM_BOT_TOKEN", "TG_BOT_TOKEN")):
        return [synthetic_success_record("telegram-feedback", {"skipped": True, "reason": "missing-telegram-token"})]
    if not job.chat_id and not first_env_value(env, ("TELEGRAM_CHAT_ID", "TG_CHAT_ID")):
        return [synthetic_success_record("telegram-feedback", {"skipped": True, "reason": "missing-telegram-chat-id"})]
    command = scanner_command(data_dir, week, "telegram-feedback")
    if job.chat_id:
        command.extend(["--chat-id", job.chat_id])
    records: list[dict[str, object]] = []
    try:
        records.append(run_command("telegram-feedback", command, runner, env, secrets))
    except LoopStepError as exc:
        records.append(exc.record)
        raise LoopJobError(str(exc), records) from exc
    return records


def run_oss_bounty_radar_job(
    job: LoopJob,
    week: str,
    loop_config: LoopConfig,
    send_requested: bool,
    runner: object,
    env: dict[str, str],
    secrets: list[str],
) -> list[dict[str, object]]:
    data_dir = repo_path(loop_config.data_dir)
    if not str(job.source_input):
        return [synthetic_success_record("oss-bounty-radar", {"skipped": True, "reason": "missing-input"})]
    commands: list[tuple[str, list[str]]] = []
    if job.external_command:
        commands.append(("oss-bounty-radar-scan", job.external_command))
    import_command = scanner_command(
        data_dir,
        week,
        "oss-bounty-radar",
        "--input",
        str(repo_path(job.source_input)),
        "--max-candidates",
        str(job.max_candidates),
        "--min-score",
        str(job.min_score),
        "--verdicts",
        *job.source_verdicts,
    )
    if job.ingest:
        import_command.append("--ingest")
    commands.append(("oss-bounty-radar", import_command))
    if job.ingest and job.post_pipeline:
        append_analysis_post_pipeline_commands(commands, data_dir, week, job, loop_config, send_requested)
    records: list[dict[str, object]] = []
    for name, command in commands:
        try:
            records.append(run_command(name, command, runner, env, secrets))
        except LoopStepError as exc:
            records.append(exc.record)
            raise LoopJobError(str(exc), records) from exc
    return records


def run_job(
    job: LoopJob,
    week: str,
    loop_config: LoopConfig,
    send_requested: bool,
    runner: object,
    env: dict[str, str],
    secrets: list[str],
) -> list[dict[str, object]]:
    if job.job_type == "github-monitor":
        return run_github_monitor_job(job, week, loop_config, send_requested, runner, env, secrets)
    if job.job_type == "hn-demand":
        return run_hn_demand_job(job, week, loop_config, send_requested, runner, env, secrets)
    if job.job_type == "reddit-demand":
        return run_reddit_demand_job(job, week, loop_config, send_requested, runner, env, secrets)
    if job.job_type == "telegram-feedback":
        return run_telegram_feedback_job(job, week, loop_config, runner, env, secrets)
    if job.job_type == "oss-bounty-radar":
        return run_oss_bounty_radar_job(job, week, loop_config, send_requested, runner, env, secrets)
    raise LoopRunError(f"Unsupported job type: {job.job_type}")


def job_state_row(state: dict[str, object], job_id: str) -> dict[str, object]:
    jobs = state.get("jobs")
    if not isinstance(jobs, dict):
        jobs = {}
        state["jobs"] = jobs
    row = jobs.get(job_id)
    if not isinstance(row, dict):
        row = {}
        jobs[job_id] = row
    return row


def update_failure_state(state: dict[str, object], job_id: str, notification: dict[str, object]) -> None:
    row = job_state_row(state, job_id)
    row["open_failure_issue_number"] = notification.get("issue_number")
    row["open_failure_issue_url"] = notification.get("issue_url")
    row["last_failure_issue_action"] = notification.get("action")
    row["last_failure_issue_at"] = utc_now()


def clear_failure_state(state: dict[str, object], job_id: str, notification: dict[str, object]) -> None:
    row = job_state_row(state, job_id)
    row["last_recovery_issue_action"] = notification.get("action")
    row["last_recovery_issue_at"] = utc_now()
    row.pop("open_failure_issue_number", None)
    row.pop("open_failure_issue_url", None)


def failure_issue_client(loop_config: LoopConfig, env: dict[str, str], client: object | None) -> object | None:
    if client is not None:
        return client
    token = first_env_value(env, ("GITHUB_TOKEN", "GH_TOKEN"))
    if not token:
        return None
    return LoopGitHubClient(token, loop_config.failure_issues.api_base, loop_config.command_timeout_seconds)


def sync_failed_job_issue(
    loop_config: LoopConfig,
    job_record: dict[str, object],
    run_log_path: Path,
    state: dict[str, object],
    client: object,
) -> dict[str, object]:
    job_id = str(job_record.get("job_id") or "unknown")
    repo = loop_config.failure_issues.repo
    labels = list(loop_config.failure_issues.labels)
    title = f"Autonomous loop failure: {job_id}"
    body = failure_issue_body(job_record, run_log_path)
    ensure_failure_labels(client, repo, labels)
    state_row = job_state(state, job_id)
    issue: dict[str, object] = {}
    state_issue_number = failure_issue_number(state_row)
    if state_issue_number is not None:
        issue = {"number": state_issue_number, "html_url": state_row.get("open_failure_issue_url")}
    if not issue:
        issue = search_failure_issue(client, repo, job_id)
    issue_number = failure_issue_number(issue)
    if issue_number is None:
        created = create_failure_issue(client, repo, title, body, labels)
        notification = {
            "job_id": job_id,
            "action": "created-failure-issue",
            "issue_number": failure_issue_number(created),
            "issue_url": created.get("html_url") or created.get("url"),
        }
    else:
        updated = update_failure_issue(client, repo, issue_number, title, body, labels)
        notification = {
            "job_id": job_id,
            "action": "updated-failure-issue",
            "issue_number": issue_number,
            "issue_url": updated.get("html_url") or issue.get("html_url") or issue.get("issue_url") or issue.get("url"),
        }
    update_failure_state(state, job_id, notification)
    return notification


def sync_recovered_job_issue(
    loop_config: LoopConfig,
    job_record: dict[str, object],
    run_log_path: Path,
    state: dict[str, object],
    client: object,
) -> dict[str, object] | None:
    job_id = str(job_record.get("job_id") or "unknown")
    previous_issue_number = failure_issue_number({"number": job_record.get("previous_failure_issue_number")})
    if previous_issue_number is None:
        return None
    body = "\n".join(
        [
            f"Autonomous loop job `{job_id}` recovered.",
            "",
            f"- Recovered at: `{job_record.get('finished_at') or utc_now()}`",
            f"- Run log: `{safe_issue_path_ref(run_log_path)}`",
            "- The issue is left open for operator review.",
        ]
    )
    comment_failure_issue(client, loop_config.failure_issues.repo, previous_issue_number, body)
    notification = {
        "job_id": job_id,
        "action": "commented-recovery",
        "issue_number": previous_issue_number,
        "issue_url": job_record.get("previous_failure_issue_url"),
    }
    clear_failure_state(state, job_id, notification)
    return notification


def sync_failure_issue_notifications(
    loop_config: LoopConfig,
    job_results: list[dict[str, object]],
    run_log_path: Path,
    state: dict[str, object],
    env: dict[str, str],
    client: object | None,
    secrets: list[str],
) -> list[dict[str, object]]:
    if not loop_config.failure_issues.enabled:
        return []
    gh_client = failure_issue_client(loop_config, env, client)
    if gh_client is None:
        return [{"action": "skipped-missing-github-token", "repo": loop_config.failure_issues.repo}]
    notifications: list[dict[str, object]] = []
    for job_record in job_results:
        try:
            if job_record.get("status") == "failed":
                notifications.append(sync_failed_job_issue(loop_config, job_record, run_log_path, state, gh_client))
            elif job_record.get("status") == "success":
                notification = sync_recovered_job_issue(loop_config, job_record, run_log_path, state, gh_client)
                if notification:
                    notifications.append(notification)
        except Exception as exc:
            notifications.append(
                {
                    "job_id": job_record.get("job_id"),
                    "action": "failure-issue-sync-error",
                    "error": sanitize_text(str(exc), secrets),
                }
            )
    return notifications


def command_stdout_dict(command: dict[str, object]) -> dict[str, object]:
    stdout_json = command.get("stdout_json")
    return stdout_json if isinstance(stdout_json, dict) else {}


def int_value(value: object) -> int:
    return value if isinstance(value, int) else 0


def run_health_summary(payload: dict[str, object]) -> dict[str, object]:
    jobs = payload.get("jobs") if isinstance(payload.get("jobs"), list) else []
    selected = [job for job in jobs if isinstance(job, dict) and job.get("status") not in {"skipped"}]
    commands = []
    for job in jobs:
        if not isinstance(job, dict):
            continue
        raw_commands = job.get("commands")
        if isinstance(raw_commands, list):
            commands.extend(command for command in raw_commands if isinstance(command, dict))
    mirror_counts = {"created": 0, "linked": 0, "updated": 0, "commented": 0, "skipped": 0}
    project_counts = {"added": 0, "skipped": 0, "dry_runs": 0, "candidate_issues": 0}
    reddit_counts = {"posts": 0, "comments": 0, "candidates": 0}
    enrichment_counts = {"candidate_count": 0, "enrichment_count": 0, "written_count": 0}
    repo_digest_counts = {"candidate_count": 0, "digested_count": 0, "failed_count": 0, "dry_runs": 0}
    oss_bounty_counts = {"candidate_count": 0, "skipped_count": 0}
    telegram_counts = {"dry_runs": 0, "sent_messages": 0, "skipped_empty": 0}
    feedback_counts = {"decisions_written": 0, "ignored": 0, "callbacks_answered": 0, "filter_updates": 0}
    for command in commands:
        stdout = command_stdout_dict(command)
        if command.get("name") == "mirror-github-issues":
            mirror_counts["created"] += int_value(stdout.get("created_count"))
            mirror_counts["linked"] += int_value(stdout.get("linked_count"))
            mirror_counts["updated"] += int_value(stdout.get("updated_count"))
            mirror_counts["commented"] += int_value(stdout.get("commented_count"))
            mirror_counts["skipped"] += int_value(stdout.get("skipped_count"))
        if command.get("name") == "sync-github-project":
            project_counts["added"] += int_value(stdout.get("added_count"))
            project_counts["skipped"] += int_value(stdout.get("skipped_count"))
            project_counts["dry_runs"] += int_value(stdout.get("dry_run_count"))
            project_counts["candidate_issues"] += int_value(stdout.get("candidate_issue_count"))
        if command.get("name") == "reddit-demand":
            collection = stdout.get("collection") if isinstance(stdout.get("collection"), dict) else {}
            reddit_counts["posts"] += int_value(collection.get("post_count"))
            reddit_counts["comments"] += int_value(collection.get("comment_count"))
            reddit_counts["candidates"] += int_value(collection.get("candidate_count"))
        if command.get("name") == "ecosystems-enrich":
            enrichment_counts["candidate_count"] += int_value(stdout.get("candidate_count"))
            enrichment_counts["enrichment_count"] += int_value(stdout.get("enrichment_count"))
            enrichment_counts["written_count"] += int_value(stdout.get("written_count"))
        if command.get("name") == "repo-digest-batch":
            repo_digest_counts["candidate_count"] += int_value(stdout.get("candidate_count"))
            repo_digest_counts["digested_count"] += int_value(stdout.get("digested_count"))
            repo_digest_counts["failed_count"] += int_value(stdout.get("failed_count"))
            if stdout.get("dry_run"):
                repo_digest_counts["dry_runs"] += 1
        if command.get("name") == "oss-bounty-radar":
            oss_bounty_counts["candidate_count"] += int_value(stdout.get("candidate_count"))
            oss_bounty_counts["skipped_count"] += int_value(stdout.get("skipped_count"))
        if str(command.get("name")).startswith("send-telegram-digest"):
            if stdout.get("dry_run"):
                telegram_counts["dry_runs"] += 1
            if stdout.get("skipped"):
                telegram_counts["skipped_empty"] += 1
            telegram_counts["sent_messages"] += len(stdout.get("sent_message_ids")) if isinstance(stdout.get("sent_message_ids"), list) else 0
        if command.get("name") == "telegram-feedback":
            feedback_counts["decisions_written"] += int_value(stdout.get("decisions_written"))
            feedback_counts["ignored"] += int_value(stdout.get("ignored_count"))
            feedback_counts["callbacks_answered"] += int_value(stdout.get("callbacks_answered"))
            feedback_counts["filter_updates"] += int_value(stdout.get("filter_updates_written"))
    notifications = payload.get("failure_issue_notifications")
    notification_rows = notifications if isinstance(notifications, list) else []
    return {
        "selected_jobs": len(selected),
        "succeeded_jobs": sum(1 for job in selected if isinstance(job, dict) and job.get("status") == "success"),
        "failed_jobs": sum(1 for job in selected if isinstance(job, dict) and job.get("status") == "failed"),
        "skipped_jobs": sum(1 for job in jobs if isinstance(job, dict) and job.get("status") == "skipped"),
        "dry_run_jobs": sum(1 for job in selected if isinstance(job, dict) and job.get("status") == "dry-run"),
        "command_count": len(commands),
        "mirror_counts": mirror_counts,
        "project_counts": project_counts,
        "reddit_counts": reddit_counts,
        "enrichment_counts": enrichment_counts,
        "repo_digest_counts": repo_digest_counts,
        "oss_bounty_counts": oss_bounty_counts,
        "telegram_counts": telegram_counts,
        "feedback_counts": feedback_counts,
        "failure_issue_notifications": len(notification_rows),
    }


def job_health_row(
    job: LoopJob,
    state: dict[str, object],
    now: datetime.datetime,
    stale_grace_hours: int,
) -> dict[str, object]:
    row = job_state(state, job.job_id)
    last_success = parse_utc_timestamp(row.get("last_success_at"))
    last_finished = parse_utc_timestamp(row.get("last_finished_at"))
    reference_time = last_success or last_finished
    due, due_reason = is_job_due(job, state, now, False)
    stale_after_hours = job.interval_hours + stale_grace_hours
    age_hours: float | None = None
    if reference_time is not None:
        age_hours = max(0.0, (now - reference_time).total_seconds() / 3600)
    stale = bool(job.enabled and (reference_time is None or age_hours is not None and age_hours > stale_after_hours))
    return {
        "job_id": job.job_id,
        "type": job.job_type,
        "enabled": job.enabled,
        "last_status": row.get("last_status", "never-run"),
        "last_success_at": row.get("last_success_at", ""),
        "last_finished_at": row.get("last_finished_at", ""),
        "last_run_log_path": row.get("last_run_log_path", ""),
        "interval_hours": job.interval_hours,
        "stale_after_hours": stale_after_hours,
        "age_hours": round(age_hours, 2) if age_hours is not None else None,
        "due": due,
        "due_reason": due_reason,
        "stale": stale,
        "open_failure_issue_url": row.get("open_failure_issue_url", ""),
    }


def autonomous_loop_health(config_path: Path, env: dict[str, str], now: datetime.datetime | None = None) -> dict[str, object]:
    loop_config = load_loop_config(config_path)
    state_path = repo_path(loop_config.state_path)
    state = read_json_object(state_path)
    current_time = now or datetime.datetime.now(datetime.timezone.utc)
    jobs = [job_health_row(job, state, current_time, loop_config.health_stale_grace_hours) for job in loop_config.jobs]
    stale_jobs = [job for job in jobs if job.get("stale")]
    enabled_jobs = [job for job in jobs if job.get("enabled")]
    telegram_configured = bool(first_env_value(env, ("TELEGRAM_BOT_TOKEN", "TG_BOT_TOKEN"))) and bool(
        first_env_value(env, ("TELEGRAM_CHAT_ID", "TG_CHAT_ID"))
    )
    github_configured = bool(first_env_value(env, ("GITHUB_TOKEN", "GH_TOKEN")))
    return {
        "status": "stale" if stale_jobs else "ok",
        "checked_at": current_time.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "config_path": repo_relative(config_path),
        "state_path": repo_relative(state_path),
        "enabled_job_count": len(enabled_jobs),
        "stale_job_count": len(stale_jobs),
        "send_enabled_by_config": loop_config.send_telegram,
        "telegram_configured": telegram_configured,
        "github_configured": github_configured,
        "jobs": jobs,
    }


class FileLock:
    def __init__(self, path: Path, stale_minutes: int) -> None:
        self.path = path
        self.stale_minutes = stale_minutes
        self.acquired = False

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            if self.is_stale():
                self.path.unlink(missing_ok=True)
                fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            else:
                raise LoopRunError(f"Autonomous loop lock already exists: {self.path}")
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps({"pid": os.getpid(), "created_at": utc_now()}, sort_keys=True) + "\n")
        self.acquired = True

    def is_stale(self) -> bool:
        try:
            stat = self.path.stat()
        except FileNotFoundError:
            return False
        age = datetime.datetime.now(datetime.timezone.utc).timestamp() - stat.st_mtime
        return age > self.stale_minutes * 60

    def release(self) -> None:
        if self.acquired:
            self.path.unlink(missing_ok=True)
            self.acquired = False

    def __enter__(self) -> FileLock:
        self.acquire()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.release()


def write_run_log(data_dir: Path, payload: dict[str, object]) -> Path:
    run_id = str(payload["run_id"])
    week = str(payload["week"])
    path = data_dir / "runs" / f"{week}-autonomous-loop-{run_id}.json"
    write_json(path, payload)
    return path


def run_autonomous_loop(
    config_path: Path,
    week: str,
    send_requested: bool,
    dry_run: bool,
    force: bool,
    runner: object,
    env: dict[str, str],
    now: datetime.datetime | None = None,
    failure_client: object | None = None,
) -> dict[str, object]:
    started_at = utc_now()
    run_id = f"{compact_utc_stamp()}-{uuid.uuid4().hex[:8]}"
    loop_config = load_loop_config(config_path)
    data_dir = repo_path(loop_config.data_dir)
    state_path = repo_path(loop_config.state_path)
    lock_path = repo_path(loop_config.lock_path)
    secrets = secret_values(env)
    env = dict(env)
    env["AUTONOMOUS_LOOP_COMMAND_TIMEOUT_SECONDS"] = str(loop_config.command_timeout_seconds)
    state = read_json_object(state_path)
    current_time = now or datetime.datetime.now(datetime.timezone.utc)
    selected_jobs = 0
    job_results: list[dict[str, object]] = []
    status = "success"

    payload: dict[str, object] = {
        "run_id": run_id,
        "status": "running",
        "week": week,
        "started_at": started_at,
        "finished_at": "",
        "config_path": repo_relative(config_path),
        "config_sha256": config_hash(config_path),
        "data_dir": repo_relative(data_dir),
        "send_requested": send_requested,
        "send_enabled_by_config": loop_config.send_telegram,
        "command_timeout_seconds": loop_config.command_timeout_seconds,
        "dry_run": dry_run,
        "force": force,
        "jobs": job_results,
    }

    if not loop_config.enabled:
        payload["status"] = "disabled"
        payload["finished_at"] = utc_now()
        run_log_path = write_run_log(data_dir, payload)
        payload["run_log_path"] = str(run_log_path)
        return payload

    with FileLock(lock_path, loop_config.lock_stale_minutes):
        for job in loop_config.jobs:
            due, reason = is_job_due(job, state, current_time, force)
            if not due:
                job_results.append({"job_id": job.job_id, "type": job.job_type, "status": "skipped", "reason": reason})
                continue
            if selected_jobs >= loop_config.max_jobs_per_tick:
                job_results.append({"job_id": job.job_id, "type": job.job_type, "status": "skipped", "reason": "max-jobs-per-tick"})
                continue
            selected_jobs += 1
            job_started_at = utc_now()
            previous_job_state = job_state(state, job.job_id)
            job_record: dict[str, object] = {
                "job_id": job.job_id,
                "type": job.job_type,
                "status": "running",
                "reason": reason,
                "started_at": job_started_at,
                "finished_at": "",
                "commands": [],
            }
            if previous_job_state.get("open_failure_issue_number"):
                job_record["previous_failure_issue_number"] = previous_job_state.get("open_failure_issue_number")
                job_record["previous_failure_issue_url"] = previous_job_state.get("open_failure_issue_url")
            try:
                if dry_run:
                    job_record["status"] = "dry-run"
                else:
                    job_record["commands"] = run_job(job, week, loop_config, send_requested, runner, env, secrets)
                    job_record["status"] = "success"
            except LoopJobError as exc:
                job_record["status"] = "failed"
                job_record["commands"] = exc.records
                job_record["error"] = {"type": type(exc).__name__, "message": sanitize_text(str(exc), secrets)}
                status = "partial-failure"
            except Exception as exc:
                job_record["status"] = "failed"
                job_record["error"] = {"type": type(exc).__name__, "message": sanitize_text(str(exc), secrets)}
                status = "partial-failure"
            job_finished_at = utc_now()
            job_record["finished_at"] = job_finished_at
            job_results.append(job_record)
            if not dry_run:
                state = update_job_state(state, job, str(job_record["status"]), job_started_at, job_finished_at, data_dir / "runs" / f"{week}-autonomous-loop-{run_id}.json")

        if selected_jobs == 0 and status == "success":
            status = "noop"
        payload["status"] = status
        payload["finished_at"] = utc_now()
        run_log_path = write_run_log(data_dir, payload)
        payload["failure_issue_notifications"] = [] if dry_run else sync_failure_issue_notifications(
            loop_config,
            job_results,
            run_log_path,
            state,
            env,
            failure_client,
            secrets,
        )
        payload["health_summary"] = run_health_summary(payload)
        payload["run_log_path"] = str(run_log_path)
        run_log_path = write_run_log(data_dir, payload)
        payload["run_log_path"] = str(run_log_path)
        if not dry_run:
            state["updated_at"] = payload["finished_at"]
            state["last_run_log_path"] = str(run_log_path)
            write_json(state_path, state)
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Opportunity Scanner autonomous control loop.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Autonomous loop config JSON path")
    parser.add_argument("--week", default=default_week(), help="ISO week label, e.g. 2026-W24")
    parser.add_argument("--send", action="store_true", help="Allow real Telegram send for jobs that also allow it")
    parser.add_argument("--dry-run", action="store_true", help="Evaluate due jobs without running commands or updating state")
    parser.add_argument("--force", action="store_true", help="Run enabled jobs even when not due")
    parser.add_argument("--health-check", action="store_true", help="Print read-only loop health from config and state")
    return parser


def main(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    run_env = dict(os.environ)
    try:
        load_env_file_into(run_env, REPO_ROOT / ".env")
        if args.health_check:
            result = autonomous_loop_health(
                config_path=Path(args.config),
                env=run_env,
            )
            print(json.dumps(result, sort_keys=True))
            return 0
        result = run_autonomous_loop(
            config_path=Path(args.config),
            week=str(args.week),
            send_requested=bool(args.send),
            dry_run=bool(args.dry_run),
            force=bool(args.force),
            runner=subprocess_runner,
            env=run_env,
        )
    except Exception as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
