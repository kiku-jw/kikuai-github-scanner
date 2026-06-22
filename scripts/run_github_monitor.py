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
import uuid


REPO_ROOT = Path(__file__).resolve().parent.parent
SCANNER_SCRIPT = REPO_ROOT / "scripts" / "opportunity_scanner.py"
DEFAULT_CONFIG_PATH = REPO_ROOT / "config" / "github-monitor.json"
SECRET_ENV_NAMES = (
    "GITHUB_TOKEN",
    "GH_TOKEN",
    "TELEGRAM_BOT_TOKEN",
    "TG_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "TG_CHAT_ID",
)
STDIO_TAIL_LIMIT = 1600


class MonitorConfigError(ValueError):
    pass


class MonitorRunError(RuntimeError):
    pass


@dataclasses.dataclass(frozen=True)
class GitHubQueryLane:
    lane_id: str
    query: str
    enabled: bool
    max_candidates: int
    per_page: int
    issues_per_repo: int
    sort: str
    order: str
    notes: str
    expected_signal: str


@dataclasses.dataclass(frozen=True)
class MonitorConfig:
    enabled: bool
    data_dir: Path
    default_max_candidates: int
    per_page: int
    issues_per_repo: int
    deep_review_max_candidates: int
    ecosystems_enrich: bool
    ecosystems_max_candidates: int
    repo_digest_batch: bool
    repo_digest_max_candidates: int
    repo_digest_max_files: int
    repo_digest_max_bytes: int
    repo_digest_clone_timeout_seconds: int
    total_candidate_cap: int
    send_telegram: bool
    write_calibration: bool
    write_dashboard: bool
    github_queries: list[GitHubQueryLane]


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


def repo_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def repo_path(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


def read_json_file(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise MonitorConfigError("Monitor config must be a JSON object.")
    return payload


def positive_int(value: object, field_name: str, *, allow_zero: bool = False) -> int:
    if not isinstance(value, int):
        raise MonitorConfigError(f"{field_name} must be an integer.")
    if allow_zero:
        if value < 0:
            raise MonitorConfigError(f"{field_name} must be >= 0.")
    elif value <= 0:
        raise MonitorConfigError(f"{field_name} must be > 0.")
    return value


def text_value(value: object, field_name: str, *, required: bool = False) -> str:
    if value is None:
        if required:
            raise MonitorConfigError(f"{field_name} is required.")
        return ""
    if not isinstance(value, str):
        raise MonitorConfigError(f"{field_name} must be a string.")
    cleaned = value.strip()
    if required and not cleaned:
        raise MonitorConfigError(f"{field_name} is required.")
    return cleaned


def bool_value(value: object, field_name: str, default: bool) -> bool:
    if value is None:
        return default
    if not isinstance(value, bool):
        raise MonitorConfigError(f"{field_name} must be a boolean.")
    return value


def load_monitor_config(path: Path) -> MonitorConfig:
    raw = read_json_file(path)
    default_max_candidates = positive_int(raw.get("default_max_candidates", 6), "default_max_candidates")
    per_page = positive_int(raw.get("per_page", 10), "per_page")
    issues_per_repo = positive_int(raw.get("issues_per_repo", 3), "issues_per_repo", allow_zero=True)
    raw_queries = raw.get("github_queries")
    if not isinstance(raw_queries, list):
        raise MonitorConfigError("github_queries must be a list.")

    lanes: list[GitHubQueryLane] = []
    lane_ids: set[str] = set()
    for index, item in enumerate(raw_queries, 1):
        if not isinstance(item, dict):
            raise MonitorConfigError(f"github_queries[{index}] must be an object.")
        lane_id = text_value(item.get("id"), f"github_queries[{index}].id", required=True)
        if lane_id in lane_ids:
            raise MonitorConfigError(f"Duplicate github query id: {lane_id}")
        lane_ids.add(lane_id)
        lanes.append(
            GitHubQueryLane(
                lane_id=lane_id,
                query=text_value(item.get("query"), f"github_queries[{index}].query", required=True),
                enabled=bool_value(item.get("enabled"), f"github_queries[{index}].enabled", True),
                max_candidates=positive_int(item.get("max_candidates", default_max_candidates), f"github_queries[{index}].max_candidates"),
                per_page=positive_int(item.get("per_page", per_page), f"github_queries[{index}].per_page"),
                issues_per_repo=positive_int(item.get("issues_per_repo", issues_per_repo), f"github_queries[{index}].issues_per_repo", allow_zero=True),
                sort=text_value(item.get("sort", "updated"), f"github_queries[{index}].sort") or "updated",
                order=text_value(item.get("order", "desc"), f"github_queries[{index}].order") or "desc",
                notes=text_value(item.get("notes"), f"github_queries[{index}].notes"),
                expected_signal=text_value(item.get("expected_signal"), f"github_queries[{index}].expected_signal"),
            )
        )

    config = MonitorConfig(
        enabled=bool_value(raw.get("enabled"), "enabled", True),
        data_dir=Path(text_value(raw.get("data_dir", "data"), "data_dir") or "data"),
        default_max_candidates=default_max_candidates,
        per_page=per_page,
        issues_per_repo=issues_per_repo,
        deep_review_max_candidates=positive_int(raw.get("deep_review_max_candidates", 5), "deep_review_max_candidates", allow_zero=True),
        ecosystems_enrich=bool_value(raw.get("ecosystems_enrich"), "ecosystems_enrich", False),
        ecosystems_max_candidates=positive_int(raw.get("ecosystems_max_candidates", 5), "ecosystems_max_candidates", allow_zero=True),
        repo_digest_batch=bool_value(raw.get("repo_digest_batch"), "repo_digest_batch", False),
        repo_digest_max_candidates=positive_int(raw.get("repo_digest_max_candidates", 1), "repo_digest_max_candidates", allow_zero=True),
        repo_digest_max_files=positive_int(raw.get("repo_digest_max_files", 80), "repo_digest_max_files", allow_zero=True),
        repo_digest_max_bytes=positive_int(raw.get("repo_digest_max_bytes", 500000), "repo_digest_max_bytes", allow_zero=True),
        repo_digest_clone_timeout_seconds=positive_int(
            raw.get("repo_digest_clone_timeout_seconds", 90),
            "repo_digest_clone_timeout_seconds",
            allow_zero=True,
        ),
        total_candidate_cap=positive_int(raw.get("total_candidate_cap", 50), "total_candidate_cap"),
        send_telegram=bool_value(raw.get("send_telegram"), "send_telegram", False),
        write_calibration=bool_value(raw.get("write_calibration"), "write_calibration", True),
        write_dashboard=bool_value(raw.get("write_dashboard"), "write_dashboard", True),
        github_queries=lanes,
    )
    validate_monitor_config(config)
    return config


def enabled_lanes(config: MonitorConfig) -> list[GitHubQueryLane]:
    return [lane for lane in config.github_queries if lane.enabled]


def validate_monitor_config(config: MonitorConfig) -> None:
    if config.deep_review_max_candidates > config.total_candidate_cap:
        raise MonitorConfigError("deep_review_max_candidates cannot exceed total_candidate_cap.")
    total_planned = sum(lane.max_candidates for lane in enabled_lanes(config))
    if total_planned > config.total_candidate_cap:
        raise MonitorConfigError(
            f"Enabled GitHub lanes request {total_planned} candidates, above total_candidate_cap={config.total_candidate_cap}."
        )
    for lane in config.github_queries:
        if lane.order not in {"asc", "desc"}:
            raise MonitorConfigError(f"github query {lane.lane_id} has invalid order: {lane.order}")
        if "is:private" in lane.query.lower():
            raise MonitorConfigError(f"github query {lane.lane_id} requests private repositories.")


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
    completed = subprocess.run(command, cwd=cwd, env=env, text=True, capture_output=True, check=False)
    return CommandOutcome(returncode=completed.returncode, stdout=completed.stdout, stderr=completed.stderr)


def scanner_command(data_dir: Path, week: str, *args: str) -> list[str]:
    return [sys.executable, str(SCANNER_SCRIPT), "--data-dir", str(data_dir), "--week", week, *args]


def command_record(
    name: str,
    command: list[str],
    outcome: CommandOutcome,
    started_at: str,
    finished_at: str,
    secrets: list[str],
    lane_id: str = "",
) -> dict[str, object]:
    return {
        "name": name,
        "lane_id": lane_id,
        "command": command_to_log(command),
        "started_at": started_at,
        "finished_at": finished_at,
        "returncode": outcome.returncode,
        "stdout_json": parse_json_stdout(outcome.stdout),
        "stdout_tail": sanitize_text(outcome.stdout, secrets),
        "stderr_tail": sanitize_text(outcome.stderr, secrets),
    }


def run_step(
    log: dict[str, object],
    name: str,
    command: list[str],
    cwd: Path,
    env: dict[str, str],
    secrets: list[str],
    command_runner: object,
    lane_id: str = "",
) -> dict[str, object]:
    started_at = utc_now()
    outcome = command_runner(command, cwd, env)
    finished_at = utc_now()
    record = command_record(name, command, outcome, started_at, finished_at, secrets, lane_id)
    steps = log.get("steps")
    if isinstance(steps, list):
        steps.append(record)
    if outcome.returncode != 0:
        raise MonitorRunError(f"Step failed: {name}")
    payload = record.get("stdout_json")
    return payload if isinstance(payload, dict) else {}


def run_log_path(data_dir: Path, week: str, run_id: str) -> Path:
    return data_dir / "runs" / f"{week}-github-monitor-{run_id}.json"


def write_run_log(path: Path, log: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(log, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def candidate_count_from_payload(payload: dict[str, object]) -> int:
    collection = payload.get("collection")
    if isinstance(collection, dict) and isinstance(collection.get("candidate_count"), int):
        return int(collection.get("candidate_count"))
    return 0


def run_monitor(
    config_path: Path,
    week: str,
    send: bool,
    command_runner: object = subprocess_runner,
    env: dict[str, str] | None = None,
) -> dict[str, object]:
    config = load_monitor_config(config_path)
    if not config.enabled:
        raise MonitorConfigError("Monitor config is disabled.")
    if send and not config.send_telegram:
        raise MonitorConfigError("Refusing Telegram send: config send_telegram is false.")

    run_env = dict(os.environ if env is None else env)
    data_dir = config.data_dir if config.data_dir.is_absolute() else REPO_ROOT / config.data_dir
    run_id = f"{compact_utc_stamp()}-{uuid.uuid4().hex[:8]}"
    log_path = run_log_path(data_dir, week, run_id)
    secrets = secret_values(run_env)
    lanes = enabled_lanes(config)
    log: dict[str, object] = {
        "run_id": run_id,
        "status": "running",
        "started_at": utc_now(),
        "finished_at": "",
        "week": week,
        "config_path": repo_relative(config_path),
        "config_sha256": config_hash(config_path),
        "data_dir": repo_relative(data_dir),
        "send_requested": send,
        "send_enabled_by_config": config.send_telegram,
        "enabled_lane_count": len(lanes),
        "enabled_lanes": [lane.lane_id for lane in lanes],
        "total_candidate_cap": config.total_candidate_cap,
        "steps": [],
        "candidate_counts": {"by_lane": {}, "total_collected": 0},
        "telegram": {},
        "error": {},
    }

    try:
        for lane in lanes:
            payload = run_step(
                log,
                "github-search",
                scanner_command(
                    data_dir,
                    week,
                    "github-search",
                    "--query",
                    lane.query,
                    "--max-candidates",
                    str(lane.max_candidates),
                    "--per-page",
                    str(lane.per_page),
                    "--issues-per-repo",
                    str(lane.issues_per_repo),
                    "--sort",
                    lane.sort,
                    "--order",
                    lane.order,
                    "--ingest",
                ),
                REPO_ROOT,
                run_env,
                secrets,
                command_runner,
                lane.lane_id,
            )
            count = candidate_count_from_payload(payload)
            counts = log["candidate_counts"]
            if isinstance(counts, dict):
                by_lane = counts.get("by_lane")
                if isinstance(by_lane, dict):
                    by_lane[lane.lane_id] = count
                total = counts.get("total_collected")
                counts["total_collected"] = (int(total) if isinstance(total, int) else 0) + count

        run_step(log, "label", scanner_command(data_dir, week, "label"), REPO_ROOT, run_env, secrets, command_runner)
        if config.ecosystems_enrich:
            run_step(
                log,
                "ecosystems-enrich",
                scanner_command(
                    data_dir,
                    week,
                    "ecosystems-enrich",
                    "--max-candidates",
                    str(config.ecosystems_max_candidates),
                ),
                REPO_ROOT,
                run_env,
                secrets,
                command_runner,
            )
        if config.repo_digest_batch:
            run_step(
                log,
                "repo-digest-batch",
                scanner_command(
                    data_dir,
                    week,
                    "repo-digest-batch",
                    "--max-candidates",
                    str(config.repo_digest_max_candidates),
                    "--max-files",
                    str(config.repo_digest_max_files),
                    "--max-bytes",
                    str(config.repo_digest_max_bytes),
                    "--clone-timeout-seconds",
                    str(config.repo_digest_clone_timeout_seconds),
                ),
                REPO_ROOT,
                run_env,
                secrets,
                command_runner,
            )
        run_step(
            log,
            "deep-review",
            scanner_command(data_dir, week, "deep-review", "--max-candidates", str(config.deep_review_max_candidates)),
            REPO_ROOT,
            run_env,
            secrets,
            command_runner,
        )
        run_step(log, "digest", scanner_command(data_dir, week, "digest"), REPO_ROOT, run_env, secrets, command_runner)
        if config.write_calibration:
            run_step(log, "calibration", scanner_command(data_dir, week, "calibration"), REPO_ROOT, run_env, secrets, command_runner)
        if config.write_dashboard:
            run_step(log, "dashboard", scanner_command(data_dir, week, "dashboard"), REPO_ROOT, run_env, secrets, command_runner)
        telegram_dry_run = run_step(
            log,
            "send-telegram-digest-dry-run",
            scanner_command(data_dir, week, "send-telegram-digest", "--dry-run"),
            REPO_ROOT,
            run_env,
            secrets,
            command_runner,
        )
        log["telegram"] = {"dry_run": telegram_dry_run}
        if send:
            telegram_send = run_step(
                log,
                "send-telegram-digest",
                scanner_command(data_dir, week, "send-telegram-digest", "--skip-empty"),
                REPO_ROOT,
                run_env,
                secrets,
                command_runner,
            )
            log["telegram"] = {"dry_run": telegram_dry_run, "send": telegram_send}
        log["status"] = "success"
        return log
    except Exception:
        exception_type, exception_value, _ = sys.exc_info()
        log["status"] = "failed"
        log["error"] = {
            "type": exception_type.__name__ if exception_type is not None else "unknown",
            "message": sanitize_text(str(exception_value), secrets),
        }
        raise
    finally:
        log["finished_at"] = utc_now()
        write_run_log(log_path, log)
        log["run_log_path"] = str(log_path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Opportunity Scanner GitHub monitor pipeline.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Monitor config JSON path")
    parser.add_argument("--week", default=default_week(), help="ISO week label, e.g. 2026-W23")
    parser.add_argument("--send", action="store_true", help="Send Telegram digest after a successful dry-run check")
    return parser


def main(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = run_monitor(repo_path(Path(args.config)), args.week, bool(args.send))
    except (OSError, json.JSONDecodeError, MonitorConfigError, MonitorRunError) as error:
        print(json.dumps({"status": "failed", "error": str(error)}, sort_keys=True), file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "status": result.get("status"),
                "week": result.get("week"),
                "run_log_path": result.get("run_log_path"),
                "candidate_counts": result.get("candidate_counts"),
                "telegram": result.get("telegram"),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
