#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime
import hashlib
import html
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Callable


HARD_GATE_HINTS = {
    "banned_category": "banned-category",
    "clear_scam": "clear-scam",
    "no_usable_data": "no-usable-data",
    "known_incompatible_license": "known-incompatible-license",
    "non_public_source": "non-public-source",
    "unauthorized_security_testing": "unauthorized-security-testing",
    "copied_brand_or_assets": "copied-brand-or-assets",
    "first_payment_requires_calls": "first-payment-requires-calls",
}

SEARCH_LANES = {
    "active_abandoned_forks": "active-abandoned-forks",
    "cli_to_ui_gap": "cli-to-ui-gap",
    "commercial_intent_density": "commercial-intent-density",
    "academic_hobbyist_bias": "academic-hobbyist-bias",
    "demand_pain_cluster": "demand-pain-cluster",
}

MONEY_TERMS = (
    "hosted",
    "managed",
    "cloud",
    "pricing",
    "paid",
    "support",
    "enterprise",
    "pro plan",
    "subscription",
)

GITHUB_API_BASE = "https://api.github.com"
GITHUB_API_VERSION = "2026-03-10"
GITHUB_TOKEN_ENV_NAMES = ("GITHUB_TOKEN", "GH_TOKEN")
GITLAB_API_BASE = "https://gitlab.com/api/v4"
GITLAB_TOKEN_ENV_NAMES = ("GITLAB_TOKEN", "GL_TOKEN")
HN_API_BASE = "https://hacker-news.firebaseio.com/v0"
REDDIT_AUTH_API_BASE = "https://www.reddit.com"
REDDIT_OAUTH_API_BASE = "https://oauth.reddit.com"
REDDIT_CLIENT_ID_ENV_NAMES = ("REDDIT_CLIENT_ID",)
REDDIT_CLIENT_SECRET_ENV_NAMES = ("REDDIT_CLIENT_SECRET",)
REDDIT_ACCESS_TOKEN_ENV_NAMES = ("REDDIT_ACCESS_TOKEN",)
REDDIT_USER_AGENT_ENV_NAMES = ("REDDIT_USER_AGENT",)
TELEGRAM_API_BASE = "https://api.telegram.org"
TELEGRAM_TOKEN_ENV_NAMES = ("TELEGRAM_BOT_TOKEN", "TG_BOT_TOKEN")
TELEGRAM_CHAT_ID_ENV_NAMES = ("TELEGRAM_CHAT_ID", "TG_CHAT_ID")
TELEGRAM_MESSAGE_LIMIT = 4096
TELEGRAM_CHUNK_LIMIT = 3900
HTTP_TIMEOUT_SECONDS = 20
ECOSYSTEMS_API_BASE = "https://repos.ecosyste.ms/api/v1"
ECOSYSTEMS_DATA_LICENSE = "CC-BY-SA-4.0"
ECOSYSTEMS_ATTRIBUTION_URL = "https://repos.ecosyste.ms/"
GH_ARCHIVE_ATTRIBUTION_URL = "https://www.gharchive.org/"
GITHUB_ISSUE_MIRROR_DEFAULT_VERDICTS = ("watchlist", "proof-card", "PRD-lite", "operator-proof-approved")
GITHUB_ISSUE_MARKER_PREFIX = "<!-- opportunity-scanner:candidate_id="
GITHUB_ISSUE_MANAGED_MARKER = "<!-- opportunity-scanner:managed-body -->"
GITHUB_ISSUE_LABEL_SPECS = {
    "opportunity-scanner": ("0366d6", "Managed by the Opportunity Scanner."),
    "needs:evidence": ("fbca04", "Needs more public evidence before proof work."),
    "needs:operator-review": ("5319e7", "Needs Operator's personal-fit review."),
    "needs:proof": ("0e8a16", "Ready for a bounded proof-card decision."),
    "needs:prd": ("1d76db", "Ready for a PRD-lite shaping pass."),
    "risk:distribution": ("d93f0b", "Distribution or first-100 reachability risk."),
    "risk:legal": ("b60205", "Legal, license, rights, or ToS risk."),
    "risk:payment": ("d4c5f9", "Payment trigger or monetization risk."),
    "risk:platform": ("d93f0b", "Single-platform or API dependency risk."),
    "risk:support": ("d93f0b", "Support, onboarding, or integration load risk."),
}
WEAK_LABEL_MODEL_NAME = "heuristic-weak-labeler-v0"
WEAK_LABEL_ALLOWED_STATUSES = {"needs-evidence", "codex-review", "watchlist-candidate"}
WEAK_LABEL_STRONG_STATUSES = {"codex-review", "watchlist-candidate", "watchlist", "proof-card", "PRD-lite"}
REPO_DIGEST_ALLOWED_STATUSES = WEAK_LABEL_STRONG_STATUSES | {"proof-card-candidate", "operator-proof-approved"}
REPO_DIGEST_SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "__pycache__",
    "coverage",
    "dist",
    "node_modules",
    "vendor",
}
REPO_DIGEST_TEXT_EXTENSIONS = {
    ".cfg",
    ".css",
    ".go",
    ".html",
    ".java",
    ".js",
    ".json",
    ".jsx",
    ".md",
    ".mjs",
    ".py",
    ".rb",
    ".rs",
    ".sh",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}
PAIN_TERMS = (
    "install",
    "setup",
    "deploy",
    "docker",
    "kubernetes",
    "helm",
    "dashboard",
    "ui",
    "hosted",
    "managed",
    "cloud",
    "pricing",
    "support",
    "integration",
    "template",
    "one-click",
    "one click",
)
HN_FEEDS = ("askstories", "showstories", "newstories")
HN_DEFAULT_FEEDS = ("askstories", "showstories")
HN_PAIN_PATTERNS = (
    "how do i",
    "how can i",
    "how to",
    "what do you use",
    "what are you using",
    "is there a tool",
    "looking for",
    "alternative to",
    "alternatives to",
    "i hate",
    "hate using",
    "frustrating",
    "painful",
    "annoying",
    "manual",
    "spreadsheet",
    "workaround",
    "can't find",
    "cannot find",
    "hard to",
    "too expensive",
    "missing",
    "broken",
    "sucks",
)
HN_BUYER_TERMS = (
    "developer",
    "developers",
    "founder",
    "founders",
    "startup",
    "saas",
    "team",
    "teams",
    "agency",
    "client",
    "customer",
    "users",
    "freelancer",
    "devops",
    "designer",
    "marketer",
)
HN_WORKAROUND_TERMS = (
    "currently",
    "manual",
    "spreadsheet",
    "using",
    "workaround",
    "script",
    "copy paste",
    "copy-paste",
    "excel",
    "zapier",
    "cron",
)
HN_PRODUCT_TERMS = (
    "tool",
    "script",
    "dashboard",
    "export",
    "report",
    "api",
    "extension",
    "template",
    "bot",
    "monitor",
    "alert",
    "hosted",
    "managed",
    "cloud",
    "one-click",
    "one click",
)
HN_ASYNC_DISTRIBUTION_TERMS = (
    "alternative to",
    "alternatives to",
    "what do you use",
    "show hn",
    "ask hn",
    "tool",
    "extension",
    "template",
    "api",
)
HN_REJECT_TERMS = (
    "crypto",
    "trading",
    "investment",
    "investing",
    "medical",
    "diagnosis",
    "lawyer",
    "legal advice",
    "compliance advice",
    "copyright",
    "downloader",
    "download youtube",
    "bypass",
    "scrape private",
    "terms of service",
    "requires sales call",
    "talk to sales",
    "schedule a demo",
    "book a call",
)
HN_HYPE_TERMS = (
    "crypto",
    "trading",
    "ai agent",
    "agi",
    "web3",
    "nft",
    "metaverse",
)
HN_CLUSTER_STOPWORDS = {
    "about",
    "after",
    "again",
    "against",
    "also",
    "because",
    "before",
    "being",
    "could",
    "does",
    "doing",
    "from",
    "have",
    "into",
    "just",
    "like",
    "need",
    "needs",
    "only",
    "really",
    "some",
    "that",
    "their",
    "there",
    "these",
    "thing",
    "this",
    "those",
    "want",
    "what",
    "when",
    "where",
    "which",
    "with",
    "without",
    "would",
    "your",
}
HN_CANDIDATE_MIN_SCORE = 10
HN_REPORT_ONLY_MIN_SCORE = 7
HN_HTML_TAG_RE = re.compile(r"<[^>]+>")
HN_WORD_RE = re.compile(r"[a-z0-9][a-z0-9+._-]*")
REDDIT_ALLOWED_SORTS = ("hot", "new", "top")
PUBLIC_AUTH_REQUIRED_API_SURFACES = {"reddit-oauth-api"}
TELEGRAM_FEEDBACK_COMMANDS = {
    "/reject": "operator-reject",
    "/park": "operator-park",
    "/watchlist": "operator-watchlist",
    "/proof": "operator-proof-approved",
    "/filter": "filter-update-needed",
}
TELEGRAM_FEEDBACK_CALLBACKS = {
    "reject": "operator-reject",
    "park": "operator-park",
    "watchlist": "operator-watchlist",
    "proof": "operator-proof-approved",
    "filter": "filter-update-needed",
    "rj": "operator-reject",
    "pk": "operator-park",
    "wl": "operator-watchlist",
    "pf": "operator-proof-approved",
    "fl": "filter-update-needed",
}
CLI_TERMS = ("cli", "command line", "terminal", "shell")
ACADEMIC_TERMS = ("academic", "research", "paper", "student", "toy", "demo", "tutorial", "learning")
BUYER_HINTS = (
    ("devops", "devops teams"),
    ("kubernetes", "devops teams"),
    ("helm", "devops teams"),
    ("developer", "developers"),
    ("developers", "developers"),
    ("api", "developers"),
    ("github", "developers"),
    ("cli", "developers"),
    ("discord", "community operators"),
    ("telegram", "community operators"),
    ("mobile", "mobile app users"),
    ("browser extension", "browser extension users"),
    ("shopify", "shopify merchants"),
)
CORE_EVIDENCE_FIELDS = (
    "target_buyer",
    "painful_job",
    "monetization",
    "distribution_channel",
    "support_load",
    "legal_license",
    "demo_or_proof",
)
COUNCIL_LANES = (
    "market-payment",
    "pain-signal",
    "distribution-first-100",
    "buildability-support",
    "legal-platform-risk",
    "skeptic-kill",
)
COUNCIL_VERDICTS = {"pass", "caution", "veto", "unknown"}
DEEP_REVIEW_INPUT_STATUSES = {"codex-review", "watchlist-candidate", "watchlist", "proof-card-candidate"}
DEEP_REVIEW_FINAL_STATUSES = {"reject", "park", "watchlist", "proof-card", "PRD-lite"}
DEEP_REVIEW_STRONG_STATUSES = {"proof-card", "PRD-lite"}
OPERATOR_DECISIONS = {"operator-reject", "operator-park", "operator-watchlist", "operator-proof-approved", "filter-update-needed"}
OPERATOR_DIGEST_VERDICT_OVERRIDES = {
    "operator-reject": "reject",
    "operator-park": "park",
    "operator-watchlist": "watchlist",
    "operator-proof-approved": "operator-proof-approved",
}
STRICT_SCORECARD_ITEMS = (
    ("pain_urgency", "Urgent recurring pain"),
    ("result_clarity", "Clear buyer-visible result"),
    ("one_function", "One small function"),
    ("demand_proof", "Demand proof"),
    ("no_call_revenue", "No-call revenue path"),
    ("online_reachability", "Online reachability"),
    ("speed_to_first_money", "Speed to first money"),
    ("cheap_7_day_proof", "Cheap seven-day proof"),
    ("automated_fulfillment", "Automated fulfillment"),
    ("repeatability", "Repeatability"),
    ("manual_work_scaling", "Scales without proportional manual work"),
    ("downside_cap", "Limited downside"),
    ("rights_tos_clean", "Clean rights and ToS"),
    ("platform_resilience", "Platform resilience"),
    ("unit_economics", "Unit economics"),
    ("support_simplicity", "Simple support"),
    ("proof_quality", "Proof quality"),
)
STRICT_PROOF_CARD_MIN = 27
STRICT_CHALLENGER_MIN = 22
STRICT_WATCHLIST_MIN = 16
TELEGRAM_HUMAN_CANDIDATE_LIMIT = 5
TELEGRAM_READY_VERDICTS = {"proof-card", "PRD-lite", "operator-proof-approved"}


def utc_now() -> str:
    return (
        datetime.datetime.now(datetime.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def default_week() -> str:
    today = datetime.date.today()
    iso = today.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def normalize_url(value: object) -> str:
    text = str(value or "").strip()
    if text.endswith("/"):
        return text[:-1]
    return text


def normalize_repo_key(value: object) -> str:
    text = normalize_text(value).lower()
    if not text:
        return ""
    if text.endswith(".git"):
        text = text[:-4]
    parsed = urllib.parse.urlparse(text if "://" in text else f"https://{text}")
    host = parsed.netloc.lower()
    path = parsed.path.strip("/")
    parts = [part for part in path.split("/") if part]
    if host and len(parts) >= 2:
        return f"{host}/{parts[0]}/{parts[1]}"
    if "/" in text:
        parts = [part for part in text.strip("/").split("/") if part]
        if len(parts) == 2:
            return f"github.com/{parts[0]}/{parts[1]}"
    return text


def repo_key_from_candidate(candidate: dict[str, object]) -> str:
    raw_metadata = candidate.get("raw_metadata")
    if isinstance(raw_metadata, dict):
        for key in ("repo_key", "github_repo_key", "full_name", "repository"):
            repo_key = normalize_repo_key(raw_metadata.get(key))
            if repo_key:
                return repo_key
    for key in ("repo_key", "repository", "project_url"):
        repo_key = normalize_repo_key(candidate.get(key))
        if repo_key:
            return repo_key
    return ""


def fork_family_key_from_candidate(candidate: dict[str, object], repo_key: str) -> str:
    raw_metadata = candidate.get("raw_metadata")
    if isinstance(raw_metadata, dict):
        for key in (
            "fork_family_key",
            "source_full_name",
            "source_repo_key",
            "ultimate_source_full_name",
            "parent_full_name",
        ):
            family_key = normalize_repo_key(raw_metadata.get(key))
            if family_key:
                return family_key
    family_key = normalize_repo_key(candidate.get("fork_family_key"))
    if family_key:
        return family_key
    return repo_key


def normalize_text(value: object) -> str:
    return str(value or "").strip()


def candidate_identity(candidate: dict[str, object]) -> str:
    fork_family_key = normalize_text(candidate.get("fork_family_key"))
    if fork_family_key:
        return fork_family_key.lower()
    repo_key = normalize_text(candidate.get("repo_key"))
    if repo_key:
        return repo_key.lower()
    project_url = normalize_url(candidate.get("project_url"))
    if project_url:
        return project_url.lower()
    fallback = "|".join(
        [
            normalize_text(candidate.get("source")),
            normalize_text(candidate.get("source_url")),
            normalize_text(candidate.get("project_name")),
            normalize_text(candidate.get("short_description")),
        ]
    )
    return fallback.lower()


def candidate_aliases(candidate: dict[str, object]) -> set[str]:
    aliases: set[str] = set()
    repo_key = normalize_text(candidate.get("repo_key"))
    fork_family_key = normalize_text(candidate.get("fork_family_key"))
    project_url = normalize_url(candidate.get("project_url")).lower()
    if repo_key:
        aliases.add(f"repo:{repo_key}")
    if fork_family_key:
        aliases.add(f"family:{fork_family_key}")
    if project_url:
        aliases.add(f"url:{project_url}")
    raw_metadata = candidate.get("raw_metadata")
    if isinstance(raw_metadata, dict):
        provider = normalize_text(raw_metadata.get("provider")) or "unknown"
        repo_id = normalize_text(raw_metadata.get("id"))
        node_id = normalize_text(raw_metadata.get("node_id"))
        full_name = normalize_repo_key(raw_metadata.get("full_name") or raw_metadata.get("path_with_namespace"))
        if repo_id and provider == "github":
            aliases.add(f"github-id:{repo_id}")
        if node_id and provider == "github":
            aliases.add(f"github-node:{node_id}")
        if repo_id and provider == "gitlab":
            aliases.add(f"gitlab-id:{repo_id}")
        if full_name:
            aliases.add(f"repo:{full_name}")
    return aliases


def stable_candidate_id(candidate: dict[str, object]) -> str:
    digest = hashlib.sha256(candidate_identity(candidate).encode("utf-8")).hexdigest()
    return f"cand_{digest[:16]}"


def read_jsonl(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    rows: list[dict[str, object]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            print(f"Invalid JSONL at {path}:{line_number}", file=sys.stderr)
            raise
        if not isinstance(parsed, dict):
            raise ValueError(f"JSONL row must be an object at {path}:{line_number}")
        rows.append(parsed)
    return rows


def append_jsonl(path: Path, row: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(row, ensure_ascii=True, sort_keys=True)
    with_newline = encoded + "\n"
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    path.write_text(existing + with_newline, encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n" for row in rows)
    path.write_text(payload, encoding="utf-8")


def clean_lanes(raw_lanes: object) -> dict[str, bool]:
    lanes: dict[str, bool] = {}
    source = raw_lanes if isinstance(raw_lanes, dict) else {}
    for lane in SEARCH_LANES:
        lanes[lane] = bool(source.get(lane))
    return lanes


def clean_raw_text(raw_text: object) -> dict[str, object]:
    source = raw_text if isinstance(raw_text, dict) else {}
    return {
        "readme_excerpt": normalize_text(source.get("readme_excerpt")),
        "issue_excerpts": source.get("issue_excerpts") if isinstance(source.get("issue_excerpts"), list) else [],
        "discussion_excerpts": source.get("discussion_excerpts")
        if isinstance(source.get("discussion_excerpts"), list)
        else [],
        "marketplace_or_store_text": normalize_text(source.get("marketplace_or_store_text")),
        "external_mentions": source.get("external_mentions")
        if isinstance(source.get("external_mentions"), list)
        else [],
    }


def clean_metadata(raw_metadata: object) -> dict[str, object]:
    return raw_metadata if isinstance(raw_metadata, dict) else {}


def normalize_candidate(raw: dict[str, object], observed_at: str) -> dict[str, object]:
    candidate = {
        "candidate_id": normalize_text(raw.get("candidate_id")),
        "observed_at": normalize_text(raw.get("observed_at")) or observed_at,
        "source": normalize_text(raw.get("source")) or "manual",
        "source_url": normalize_url(raw.get("source_url")),
        "project_url": normalize_url(raw.get("project_url")),
        "project_name": normalize_text(raw.get("project_name")) or "unknown",
        "repository": normalize_text(raw.get("repository")),
        "license": normalize_text(raw.get("license")) or "unknown",
        "short_description": normalize_text(raw.get("short_description")),
        "raw_metadata": clean_metadata(raw.get("raw_metadata")),
        "raw_text": clean_raw_text(raw.get("raw_text")),
        "search_lanes": clean_lanes(raw.get("search_lanes")),
        "collector_notes": normalize_text(raw.get("collector_notes")),
    }
    repo_key = repo_key_from_candidate(candidate)
    candidate["repo_key"] = repo_key
    candidate["fork_family_key"] = fork_family_key_from_candidate(candidate, repo_key)
    if not candidate["candidate_id"]:
        candidate["candidate_id"] = stable_candidate_id(candidate)
    return candidate


def ledger_paths(data_dir: Path, week: str) -> dict[str, Path]:
    return {
        "raw_week": data_dir / "raw" / week / "candidates.jsonl",
        "candidates": data_dir / "ledger" / "candidates.jsonl",
        "events": data_dir / "ledger" / "events.jsonl",
        "identity_aliases": data_dir / "ledger" / "identity_aliases.jsonl",
        "labels": data_dir / "ledger" / "labels.jsonl",
        "opportunity_cards": data_dir / "ledger" / "opportunity_cards.jsonl",
        "council_packets": data_dir / "ledger" / "council_packets.jsonl",
        "council_findings": data_dir / "ledger" / "council_findings.jsonl",
        "aggregations": data_dir / "ledger" / "aggregations.jsonl",
        "operator_decisions": data_dir / "ledger" / "operator_decisions.jsonl",
        "filter_updates": data_dir / "ledger" / "filter_updates.jsonl",
        "calibrations": data_dir / "ledger" / "calibrations.jsonl",
        "github_issue_mirrors": data_dir / "ledger" / "github_issue_mirrors.jsonl",
        "github_project_items": data_dir / "ledger" / "github_project_items.jsonl",
        "repo_digest_meta": data_dir / "ledger" / "repo_digest_meta.jsonl",
        "ecosystems_enrichments": data_dir / "ledger" / "ecosystems_enrichments.jsonl",
        "rescore_runs": data_dir / "ledger" / "rescore_runs.jsonl",
        "telegram_feedback_updates": data_dir / "ledger" / "telegram_feedback_updates.jsonl",
        "telegram_feedback_state": data_dir / "ledger" / "telegram_feedback_state.json",
        "evidence": data_dir / "ledger" / "evidence",
        "repo_digests": data_dir / "repo_digests",
        "reports": data_dir / "reports",
        "telegram_outbox": data_dir / "outbox" / "telegram",
    }


def ensure_layout(data_dir: Path, week: str) -> dict[str, Path]:
    paths = ledger_paths(data_dir, week)
    for path in paths.values():
        if path.suffix:
            path.parent.mkdir(parents=True, exist_ok=True)
        else:
            path.mkdir(parents=True, exist_ok=True)
    return paths


def event_row(
    candidate_id: str,
    layer: str,
    from_status: str,
    to_status: str,
    reason_codes: list[str],
    evidence_refs: list[str],
    notes: str,
    week: str = "",
) -> dict[str, object]:
    return {
        "event_id": f"evt_{uuid.uuid4().hex}",
        "candidate_id": candidate_id,
        "week": week,
        "created_at": utc_now(),
        "actor": "opportunity-scanner-cli",
        "layer": layer,
        "from_status": from_status,
        "to_status": to_status,
        "reason_codes": reason_codes,
        "evidence_refs": evidence_refs,
        "notes": notes,
    }


def evidence_markdown(candidate: dict[str, object]) -> str:
    raw_text = candidate["raw_text"] if isinstance(candidate["raw_text"], dict) else {}
    lines = [
        f"# Evidence - {candidate['project_name']}",
        "",
        f"- Candidate ID: `{candidate['candidate_id']}`",
        f"- Observed at: `{candidate['observed_at']}`",
        f"- Source: `{candidate['source']}`",
        f"- Source URL: {candidate['source_url'] or 'unknown'}",
        f"- Project URL: {candidate['project_url'] or 'unknown'}",
        f"- Repository: `{candidate['repository'] or 'unknown'}`",
        f"- Repo key: `{candidate['repo_key'] or 'unknown'}`",
        f"- Fork family key: `{candidate['fork_family_key'] or 'unknown'}`",
        f"- License: `{candidate['license'] or 'unknown'}`",
        "",
        "## Description",
        "",
        candidate["short_description"] or "unknown",
        "",
        "## README Excerpt",
        "",
        normalize_text(raw_text.get("readme_excerpt")) or "unknown",
        "",
        "## Issue Excerpts",
        "",
    ]
    issue_excerpts = raw_text.get("issue_excerpts") if isinstance(raw_text.get("issue_excerpts"), list) else []
    if issue_excerpts:
        for item in issue_excerpts:
            lines.append(f"- {normalize_text(item)}")
    else:
        lines.append("- unknown")
    lines.extend(["", "## Discussion Excerpts", ""])
    discussion_excerpts = (
        raw_text.get("discussion_excerpts") if isinstance(raw_text.get("discussion_excerpts"), list) else []
    )
    if discussion_excerpts:
        for item in discussion_excerpts:
            lines.append(f"- {normalize_text(item)}")
    else:
        lines.append("- unknown")
    lines.extend(["", "## Marketplace Or Store Text", ""])
    lines.append(normalize_text(raw_text.get("marketplace_or_store_text")) or "unknown")
    lines.extend(["", "## External Mentions", ""])
    external_mentions = raw_text.get("external_mentions") if isinstance(raw_text.get("external_mentions"), list) else []
    if external_mentions:
        for item in external_mentions:
            lines.append(f"- {normalize_text(item)}")
    else:
        lines.append("- unknown")
    lines.extend(["", "## Collector Notes", "", candidate["collector_notes"] or "unknown", ""])
    return "\n".join(lines)


def append_evidence(path: Path, candidate: dict[str, object]) -> None:
    snapshot = evidence_markdown(candidate)
    if path.exists():
        existing = path.read_text(encoding="utf-8").rstrip()
        path.write_text(existing + "\n\n---\n\n" + snapshot, encoding="utf-8")
        return
    path.write_text(snapshot, encoding="utf-8")


def status_by_candidate(events: list[dict[str, object]]) -> dict[str, str]:
    statuses: dict[str, str] = {}
    for event in events:
        candidate_id = normalize_text(event.get("candidate_id"))
        to_status = normalize_text(event.get("to_status"))
        if candidate_id and to_status:
            statuses[candidate_id] = to_status
    return statuses


def status_by_candidate_for_week(events: list[dict[str, object]], week: str) -> dict[str, str]:
    return status_by_candidate([event for event in events if normalize_text(event.get("week")) == week])


def reason_codes_by_candidate(events: list[dict[str, object]]) -> dict[str, list[str]]:
    reasons: dict[str, list[str]] = {}
    for event in events:
        candidate_id = normalize_text(event.get("candidate_id"))
        row_reasons = event.get("reason_codes")
        if not candidate_id:
            continue
        if isinstance(row_reasons, list):
            reasons[candidate_id] = [normalize_text(reason) for reason in row_reasons if normalize_text(reason)]
    return reasons


def reason_codes_by_candidate_for_week(events: list[dict[str, object]], week: str) -> dict[str, list[str]]:
    return reason_codes_by_candidate([event for event in events if normalize_text(event.get("week")) == week])


def latest_label_by_candidate(labels: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    latest: dict[str, dict[str, object]] = {}
    for label in labels:
        candidate_id = normalize_text(label.get("candidate_id"))
        if candidate_id:
            latest[candidate_id] = label
    return latest


def latest_label_by_candidate_for_week(labels: list[dict[str, object]], week: str) -> dict[str, dict[str, object]]:
    return latest_label_by_candidate([label for label in labels if normalize_text(label.get("week")) == week])


def alias_row(alias: str, candidate_id: str, source: str) -> dict[str, object]:
    return {
        "alias": alias,
        "candidate_id": candidate_id,
        "created_at": utc_now(),
        "source": source,
    }


def alias_map_from_rows(candidates: list[dict[str, object]], alias_rows: list[dict[str, object]]) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for candidate in candidates:
        candidate_id = normalize_text(candidate.get("candidate_id"))
        if not candidate_id:
            continue
        for alias in candidate_aliases(candidate):
            existing = aliases.get(alias)
            if existing and existing != candidate_id:
                raise ValueError(f"Identity alias conflict for {alias}: {existing} vs {candidate_id}")
            aliases[alias] = candidate_id
    for row in alias_rows:
        alias = normalize_text(row.get("alias"))
        candidate_id = normalize_text(row.get("candidate_id"))
        if not alias or not candidate_id:
            continue
        existing = aliases.get(alias)
        if existing and existing != candidate_id:
            raise ValueError(f"Identity alias conflict for {alias}: {existing} vs {candidate_id}")
        aliases[alias] = candidate_id
    return aliases


def resolve_candidate_id(candidate: dict[str, object], aliases: dict[str, str], existing_ids: set[str]) -> tuple[str, bool]:
    current_id = normalize_text(candidate.get("candidate_id"))
    if current_id in existing_ids:
        return current_id, False
    for alias in sorted(candidate_aliases(candidate)):
        candidate_id = aliases.get(alias)
        if candidate_id:
            return candidate_id, candidate_id != current_id
    return current_id, False


def append_new_aliases(path: Path, candidate: dict[str, object], aliases: dict[str, str]) -> list[str]:
    candidate_id = normalize_text(candidate.get("candidate_id"))
    source = normalize_text(candidate.get("source"))
    added: list[str] = []
    for alias in sorted(candidate_aliases(candidate)):
        existing = aliases.get(alias)
        if existing == candidate_id:
            continue
        if existing and existing != candidate_id:
            raise ValueError(f"Identity alias conflict for {alias}: {existing} vs {candidate_id}")
        append_jsonl(path, alias_row(alias, candidate_id, source))
        aliases[alias] = candidate_id
        added.append(alias)
    return added


def has_rescue_signal(candidate: dict[str, object]) -> bool:
    lanes = candidate.get("search_lanes")
    if isinstance(lanes, dict):
        for lane, active in lanes.items():
            if lane == "academic_hobbyist_bias":
                continue
            if bool(active):
                return True
    text = all_candidate_text(candidate).lower()
    return any(term in text for term in MONEY_TERMS)


def all_candidate_text(candidate: dict[str, object]) -> str:
    raw_text = candidate.get("raw_text")
    chunks = [
        normalize_text(candidate.get("short_description")),
        normalize_text(candidate.get("collector_notes")),
    ]
    if isinstance(raw_text, dict):
        for value in raw_text.values():
            if isinstance(value, list):
                chunks.extend(normalize_text(item) for item in value)
            else:
                chunks.append(normalize_text(value))
    return "\n".join(chunks)


def active_lane_codes(candidate: dict[str, object]) -> list[str]:
    lanes = candidate.get("search_lanes")
    if not isinstance(lanes, dict):
        return []
    return [SEARCH_LANES[lane] for lane, active in lanes.items() if bool(active) and lane in SEARCH_LANES]


def snippets_with_terms(candidate: dict[str, object], terms: tuple[str, ...], limit: int) -> list[str]:
    raw_text = candidate.get("raw_text")
    snippets: list[str] = []
    sources = [
        normalize_text(candidate.get("short_description")),
        normalize_text(candidate.get("collector_notes")),
    ]
    if isinstance(raw_text, dict):
        for value in raw_text.values():
            if isinstance(value, list):
                sources.extend(normalize_text(item) for item in value)
            else:
                sources.append(normalize_text(value))
    for source in sources:
        lowered = source.lower()
        if source and any(term in lowered for term in terms):
            snippets.append(truncate_text(source, 240))
        if len(snippets) >= limit:
            break
    return snippets


def matched_terms(text: str, terms: tuple[str, ...]) -> list[str]:
    lowered = text.lower()
    return sorted({term for term in terms if term in lowered})


def weak_product_angles(candidate: dict[str, object], text: str) -> list[str]:
    lanes = candidate.get("search_lanes") if isinstance(candidate.get("search_lanes"), dict) else {}
    angles: list[str] = []
    if bool(lanes.get("cli_to_ui_gap")):
        angles.append("web dashboard")
    if bool(lanes.get("active_abandoned_forks")):
        angles.append("maintained fork or managed version")
    if "one-click" in text.lower() or "one click" in text.lower():
        angles.append("one-click deploy")
    if "telegram" in text.lower():
        angles.append("telegram bot")
    if "discord" in text.lower():
        angles.append("discord bot")
    if "browser extension" in text.lower():
        angles.append("browser extension")
    if any(term in text.lower() for term in ("hosted", "managed", "cloud")):
        angles.append("hosted version")
    if not angles:
        angles.append("unknown")
    return sorted(set(angles))


def weak_buyer_labels(text: str) -> list[str]:
    buyers = sorted({label for needle, label in BUYER_HINTS if needle in text.lower()})
    return buyers if buyers else ["unknown"]


def weak_missing_evidence(inferred_fields: dict[str, object]) -> list[dict[str, object]]:
    missing: list[dict[str, object]] = []
    for field in CORE_EVIDENCE_FIELDS:
        field_payload = inferred_fields.get(field, {})
        value = field_payload.get("value") if isinstance(field_payload, dict) else field_payload
        if normalize_text(value) == "unknown":
            severity = "high" if field in {"target_buyer", "painful_job", "monetization"} else "medium"
            missing.append(
                {
                    "type": field,
                    "field": field,
                    "severity": severity,
                    "blocking_for": ["watchlist-candidate", "proof-card"] if severity == "high" else ["proof-card"],
                    "next_check": f"Find public evidence for {field.replace('_', ' ')}.",
                    "unknown_allowed": True,
                }
            )
    return missing


def weak_risk_hints(candidate: dict[str, object], text: str) -> list[str]:
    risks: list[str] = []
    license_name = normalize_text(candidate.get("license")).lower()
    if not license_name or license_name == "unknown":
        risks.append("unknown-license")
    raw_metadata = candidate.get("raw_metadata")
    if isinstance(raw_metadata, dict):
        if bool(raw_metadata.get("archived")):
            risks.append("archived-repository")
        if bool(raw_metadata.get("disabled")):
            risks.append("disabled-repository")
    if "do not copy brand" in text.lower() or "brand" in text.lower():
        risks.append("brand-copy-risk")
    if "api" in text.lower():
        risks.append("external-api-dependence-check-needed")
    if not risks:
        risks.append("unknown")
    return sorted(set(risks))


def weak_inferred_fields(
    candidate: dict[str, object],
    pain_phrases: list[str],
    money_signals: list[str],
    buyer_labels: list[str],
    product_angles: list[str],
    text: str,
    evidence_ref: str,
) -> dict[str, dict[str, object]]:
    license_name = normalize_text(candidate.get("license"))
    active_lanes = active_lane_codes(candidate)
    evidence_refs = [evidence_ref] if evidence_ref else []

    def field(value: str, confidence: str) -> dict[str, object]:
        normalized = normalize_text(value) or "unknown"
        refs = evidence_refs if normalized != "unknown" else []
        return {
            "value": normalized,
            "confidence": confidence if normalized != "unknown" else "none",
            "evidence_refs": refs,
            "unknown_allowed": True,
        }

    inferred: dict[str, dict[str, object]] = {
        "target_buyer": field(buyer_labels[0] if buyer_labels and buyer_labels[0] != "unknown" else "unknown", "low"),
        "painful_job": field(pain_phrases[0] if pain_phrases else "unknown", "medium"),
        "monetization": field(", ".join(money_signals) if money_signals else "unknown", "low"),
        "distribution_channel": field("github/reddit/product-hunt" if active_lanes else "unknown", "low"),
        "support_load": field("unknown", "none"),
        "legal_license": field(license_name if license_name else "unknown", "medium"),
        "demo_or_proof": field("unknown", "none"),
        "product_angle": field(
            product_angles[0] if product_angles and product_angles[0] != "unknown" else "unknown",
            "medium",
        ),
    }
    if "dashboard" in text.lower() or "hosted" in text.lower() or "one-click" in text.lower():
        inferred["demo_or_proof"] = field("public demo or deploy proof needed", "low")
    return inferred


def weak_confidence(
    candidate: dict[str, object],
    pain_phrases: list[str],
    money_signals: list[str],
    buyer_labels: list[str],
    product_angles: list[str],
) -> tuple[str, float]:
    score = 0
    if pain_phrases:
        score += 2
    if money_signals:
        score += 2
    if buyer_labels and buyer_labels[0] != "unknown":
        score += 1
    if product_angles and product_angles[0] != "unknown":
        score += 1
    score += min(len(active_lane_codes(candidate)), 2)
    if score >= 6:
        return "high", 0.82
    if score >= 3:
        return "medium", 0.58
    return "low", 0.24


def weak_label_summary(candidate: dict[str, object], product_angles: list[str], buyer_labels: list[str]) -> str:
    name = normalize_text(candidate.get("project_name")) or "unknown"
    description = normalize_text(candidate.get("short_description")) or "unknown"
    angle = product_angles[0] if product_angles else "unknown"
    buyer = buyer_labels[0] if buyer_labels else "unknown"
    return f"{name}: {description} Candidate angle: {angle}. Possible buyer: {buyer}."


def weak_status_recommendation(
    current_status: str,
    confidence: str,
    pain_phrases: list[str],
    money_signals: list[str],
    missing_evidence: list[dict[str, object]],
    candidate: dict[str, object],
) -> tuple[str, list[str]]:
    if current_status == "machine-reject":
        return "machine-reject", ["hard-gate-preserved"]
    if confidence == "low":
        return "needs-evidence", ["weak-low-confidence"]
    if has_rescue_signal(candidate) and pain_phrases and money_signals and len(missing_evidence) <= 4:
        return "watchlist-candidate", ["weak-watchlist-signal"]
    if pain_phrases or money_signals or has_rescue_signal(candidate):
        return "codex-review", ["weak-codex-review-signal"]
    return "needs-evidence", ["weak-needs-evidence"]


def weak_label_candidate(
    candidate: dict[str, object],
    current_status: str,
    current_reasons: list[str],
    evidence_ref: str,
) -> dict[str, object]:
    text = all_candidate_text(candidate)
    pain_phrases = snippets_with_terms(candidate, PAIN_TERMS, 5)
    money_signals = matched_terms(text, MONEY_TERMS)
    buyer_labels = weak_buyer_labels(text)
    product_angles = weak_product_angles(candidate, text)
    inferred_fields = weak_inferred_fields(
        candidate,
        pain_phrases,
        money_signals,
        buyer_labels,
        product_angles,
        text,
        evidence_ref,
    )
    missing_evidence = weak_missing_evidence(inferred_fields)
    risk_hints = weak_risk_hints(candidate, text)
    confidence, confidence_score = weak_confidence(candidate, pain_phrases, money_signals, buyer_labels, product_angles)
    proposed_status, reason_codes = weak_status_recommendation(
        current_status,
        confidence,
        pain_phrases,
        money_signals,
        missing_evidence,
        candidate,
    )
    uncertainty_notes: list[str] = []
    if confidence == "low":
        uncertainty_notes.append("Low-confidence label; do not reject from this layer.")
    if missing_evidence:
        uncertainty_notes.append("Missing evidence remains unresolved; unknown fields were not invented.")
    if current_reasons:
        uncertainty_notes.append(f"Current status reasons: {', '.join(current_reasons)}.")
    return {
        "label_id": f"lbl_{uuid.uuid4().hex}",
        "candidate_id": normalize_text(candidate.get("candidate_id")),
        "created_at": utc_now(),
        "actor": "opportunity-scanner-cli",
        "layer": "weak-label-baseline",
        "model": WEAK_LABEL_MODEL_NAME,
        "confidence": confidence,
        "confidence_score": confidence_score,
        "summary": weak_label_summary(candidate, product_angles, buyer_labels),
        "product_angles": product_angles,
        "buyer_labels": buyer_labels,
        "pain_phrases": pain_phrases,
        "money_signals": money_signals if money_signals else ["unknown"],
        "risk_hints": risk_hints,
        "missing_evidence": missing_evidence,
        "inferred_fields": inferred_fields,
        "uncertainty_notes": uncertainty_notes if uncertainty_notes else ["unknown"],
        "status_recommendation": proposed_status,
        "reason_codes": reason_codes,
    }


def resolved_weak_label_transition(
    from_status: str,
    proposed_status: str,
    proposed_reason_codes: list[str],
) -> tuple[str, list[str], str]:
    if from_status == "machine-reject":
        return "machine-reject", ["hard-gate-preserved"], "Deterministic hard gate remains authoritative."
    if proposed_status not in WEAK_LABEL_ALLOWED_STATUSES:
        return "needs-evidence", ["weak-final-reject-blocked"], "Weak labeler attempted a forbidden final status."
    if proposed_status == "machine-reject":
        return "needs-evidence", ["weak-final-reject-blocked"], "Weak labeler cannot create a machine reject."
    if from_status in WEAK_LABEL_STRONG_STATUSES and proposed_status == "needs-evidence":
        return from_status, ["status-preserved"], "Weak label did not lower an existing stronger status."
    if from_status in {"raw", "needs-evidence"}:
        return proposed_status, [], ""
    if from_status in WEAK_LABEL_STRONG_STATUSES and proposed_status in WEAK_LABEL_STRONG_STATUSES:
        if from_status == "watchlist-candidate" or proposed_status == "codex-review":
            return from_status, ["status-preserved"], "Weak label did not lower an existing stronger status."
        return proposed_status, [], ""
    return proposed_status, proposed_reason_codes, ""


def deterministic_prefilter(candidate: dict[str, object]) -> tuple[str, list[str], str]:
    reason_codes: list[str] = []
    if not normalize_text(candidate.get("source_url")) or not normalize_text(candidate.get("project_url")):
        reason_codes.append("missing-url")

    raw_metadata = candidate.get("raw_metadata")
    hints = {}
    collection = {}
    if isinstance(raw_metadata, dict):
        if isinstance(raw_metadata.get("prefilter_hints"), dict):
            hints = raw_metadata["prefilter_hints"]
        if isinstance(raw_metadata.get("collection"), dict):
            collection = raw_metadata["collection"]
        if bool(raw_metadata.get("private")):
            reason_codes.append("non-public-source")

    if collection:
        visibility = normalize_text(collection.get("visibility"))
        auth_required = bool(collection.get("auth_required"))
        api_surface = normalize_text(collection.get("api_surface"))
        if visibility and visibility != "public":
            reason_codes.append("non-public-source")
        if auth_required and api_surface not in PUBLIC_AUTH_REQUIRED_API_SURFACES:
            reason_codes.append("non-public-source")

    for hint_key, reason_code in HARD_GATE_HINTS.items():
        if bool(hints.get(hint_key)):
            reason_codes.append(reason_code)

    if reason_codes:
        return "machine-reject", sorted(set(reason_codes)), "Deterministic hard gate fired."

    if has_rescue_signal(candidate):
        return "codex-review", ["rescue-signal"], "Rescue signal routes candidate to Codex review."

    return "needs-evidence", ["thin-evidence"], "No hard gate, but evidence is still thin."


def resolved_prefilter_transition(
    from_status: str,
    proposed_status: str,
    proposed_reason_codes: list[str],
) -> tuple[str, list[str], str]:
    if from_status in {"none", "raw", "needs-evidence"}:
        return proposed_status, [], ""
    if proposed_status == "machine-reject":
        return proposed_status, [], ""
    if proposed_status == "codex-review" and "rescue-signal" in proposed_reason_codes:
        if from_status in {"machine-reject", "reject", "park"}:
            return "codex-review", ["rescue-reopen"], "Rescue signal reopened existing repo or fork family."
    if from_status in {"machine-reject", "codex-review", "watchlist", "proof-card", "PRD-lite", "park", "reject"}:
        return from_status, ["status-preserved"], "Duplicate observation did not lower existing status."
    return proposed_status, [], ""


class GitHubApiError(RuntimeError):
    pass


class GitHubApiClient:
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
            "User-Agent": "opportunity-scanner-local",
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
            remaining = response.headers.get("X-RateLimit-Remaining")
            if normalize_text(remaining) == "0":
                raise GitHubApiError("GitHub API rate limit reached after successful response.")
            if not raw_body:
                return {}
            return json.loads(raw_body)
        except urllib.error.HTTPError:
            raise
        except urllib.error.URLError:
            raise
        finally:
            if response is not None:
                response.close()

    def get_json(self, path: str, params: dict[str, object]) -> object:
        return self.request_json("GET", path, params)

    def post_json(self, path: str, body: dict[str, object]) -> object:
        return self.request_json("POST", path, {}, body)

    def patch_json(self, path: str, body: dict[str, object]) -> object:
        return self.request_json("PATCH", path, {}, body)

    def graphql(self, query: str, variables: dict[str, object]) -> dict[str, object]:
        result = self.post_json("/graphql", {"query": query, "variables": variables})
        if not isinstance(result, dict):
            raise GitHubApiError("GitHub GraphQL returned a non-object response")
        errors = result.get("errors")
        if isinstance(errors, list) and errors:
            first = errors[0] if isinstance(errors[0], dict) else {}
            message = normalize_text(first.get("message")) if isinstance(first, dict) else normalize_text(errors[0])
            raise GitHubApiError(f"GitHub GraphQL error: {message or 'unknown'}")
        return result


class GitLabApiError(RuntimeError):
    pass


class GitLabApiClient:
    def __init__(self, token: str, api_base: str, timeout: int) -> None:
        self.token = token
        self.api_base = api_base.rstrip("/")
        self.timeout = timeout

    def get_json(self, path: str, params: dict[str, object]) -> object:
        query = urllib.parse.urlencode({key: value for key, value in params.items() if value not in ("", None)})
        url = f"{self.api_base}{path}"
        if query:
            url = f"{url}?{query}"
        headers = {"User-Agent": "opportunity-scanner-local"}
        if self.token:
            headers["PRIVATE-TOKEN"] = self.token
        request = urllib.request.Request(url, headers=headers)
        response = None
        try:
            response = urllib.request.urlopen(request, timeout=self.timeout)
            raw_body = response.read().decode("utf-8")
            if not raw_body:
                return {}
            return json.loads(raw_body)
        except urllib.error.HTTPError as exc:
            raise GitLabApiError(str(exc)) from exc
        except urllib.error.URLError as exc:
            raise GitLabApiError(str(exc)) from exc
        finally:
            if response is not None:
                response.close()


class HackerNewsApiError(RuntimeError):
    pass


class HackerNewsApiClient:
    def __init__(self, api_base: str, timeout: int) -> None:
        self.api_base = api_base.rstrip("/")
        self.timeout = timeout

    def get_json(self, path: str, params: dict[str, object]) -> object:
        query = urllib.parse.urlencode({key: value for key, value in params.items() if value not in ("", None)})
        url = f"{self.api_base}{path}"
        if query:
            url = f"{url}?{query}"
        headers = {"User-Agent": "opportunity-scanner-local"}
        request = urllib.request.Request(url, headers=headers)
        response = None
        try:
            response = urllib.request.urlopen(request, timeout=self.timeout)
            raw_body = response.read().decode("utf-8")
            if not raw_body or raw_body == "null":
                return {}
            return json.loads(raw_body)
        except urllib.error.HTTPError as exc:
            raise HackerNewsApiError(str(exc)) from exc
        except urllib.error.URLError as exc:
            raise HackerNewsApiError(str(exc)) from exc
        finally:
            if response is not None:
                response.close()


class RedditApiError(RuntimeError):
    pass


class RedditApiClient:
    def __init__(
        self,
        access_token: str,
        user_agent: str,
        oauth_api_base: str,
        auth_api_base: str,
        timeout: int,
        client_id: str = "",
        client_secret: str = "",
    ) -> None:
        self.access_token = access_token
        self.user_agent = user_agent
        self.oauth_api_base = oauth_api_base.rstrip("/")
        self.auth_api_base = auth_api_base.rstrip("/")
        self.timeout = timeout
        self.client_id = client_id
        self.client_secret = client_secret

    def token(self) -> str:
        if self.access_token:
            return self.access_token
        if not self.client_id or not self.client_secret:
            raise RedditApiError("Missing Reddit OAuth credentials")
        credentials = f"{self.client_id}:{self.client_secret}".encode("utf-8")
        import base64

        body = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode("utf-8")
        request = urllib.request.Request(
            f"{self.auth_api_base}/api/v1/access_token",
            data=body,
            headers={
                "Authorization": f"Basic {base64.b64encode(credentials).decode('ascii')}",
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": self.user_agent,
            },
            method="POST",
        )
        response = None
        try:
            response = urllib.request.urlopen(request, timeout=self.timeout)
            payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError) as exc:
            raise RedditApiError(f"Reddit OAuth failed: {exc}") from exc
        finally:
            if response is not None:
                response.close()
        if not isinstance(payload, dict) or not normalize_text(payload.get("access_token")):
            raise RedditApiError("Reddit OAuth did not return an access token")
        self.access_token = normalize_text(payload.get("access_token"))
        return self.access_token

    def get_json(self, path: str, params: dict[str, object]) -> object:
        if not self.user_agent or self.user_agent.startswith("Python/"):
            raise RedditApiError("Reddit collection requires a unique descriptive User-Agent")
        query = urllib.parse.urlencode({key: value for key, value in params.items() if value not in ("", None)})
        url = f"{self.oauth_api_base}{path}"
        if query:
            url = f"{url}?{query}"
        request = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {self.token()}",
                "User-Agent": self.user_agent,
            },
        )
        response = None
        try:
            response = urllib.request.urlopen(request, timeout=self.timeout)
            raw_body = response.read().decode("utf-8")
            return json.loads(raw_body) if raw_body else {}
        except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError) as exc:
            raise RedditApiError(f"Reddit API request failed: {exc}") from exc
        finally:
            if response is not None:
                response.close()


def first_env_value(names: tuple[str, ...]) -> str:
    for name in names:
        value = normalize_text(os.environ.get(name))
        if value:
            return value
    return ""


def clean_env_value(raw: str) -> str:
    value = raw.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def load_env_file(path: Path) -> list[str]:
    if not path.exists():
        return []
    loaded: list[str] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            raise ValueError(f"Invalid env line at {path}:{line_number}")
        key, raw_value = stripped.split("=", 1)
        key = key.strip()
        if not key or not (key[0].isalpha() or key[0] == "_") or not all(character.isalnum() or character == "_" for character in key):
            raise ValueError(f"Invalid env key at {path}:{line_number}")
        if key not in os.environ:
            os.environ[key] = clean_env_value(raw_value)
            loaded.append(key)
    return loaded


def env_github_token() -> str:
    return first_env_value(GITHUB_TOKEN_ENV_NAMES)


def env_gitlab_token() -> str:
    return first_env_value(GITLAB_TOKEN_ENV_NAMES)


def env_reddit_client_id() -> str:
    return first_env_value(REDDIT_CLIENT_ID_ENV_NAMES)


def env_reddit_client_secret() -> str:
    return first_env_value(REDDIT_CLIENT_SECRET_ENV_NAMES)


def env_reddit_access_token() -> str:
    return first_env_value(REDDIT_ACCESS_TOKEN_ENV_NAMES)


def env_reddit_user_agent() -> str:
    return first_env_value(REDDIT_USER_AGENT_ENV_NAMES)


def env_telegram_token() -> str:
    return first_env_value(TELEGRAM_TOKEN_ENV_NAMES)


def env_telegram_chat_id() -> str:
    return first_env_value(TELEGRAM_CHAT_ID_ENV_NAMES)


def truncate_text(value: object, limit: int = 700) -> str:
    text = " ".join(normalize_text(value).split())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def github_full_name(value: object) -> str:
    text = normalize_text(value)
    parts = [part for part in text.split("/") if part]
    if len(parts) >= 2:
        return f"{parts[0]}/{parts[1]}"
    return text


def safe_dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def safe_list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def github_license_name(repo: dict[str, object]) -> str:
    license_data = safe_dict(repo.get("license"))
    spdx = normalize_text(license_data.get("spdx_id"))
    name = normalize_text(license_data.get("name"))
    if spdx and spdx != "NOASSERTION":
        return spdx
    if name:
        return name
    return "unknown"


def github_repo_metadata(repo: dict[str, object]) -> dict[str, object]:
    parent = safe_dict(repo.get("parent"))
    source = safe_dict(repo.get("source"))
    full_name = github_full_name(repo.get("full_name"))
    source_full_name = github_full_name(source.get("full_name"))
    parent_full_name = github_full_name(parent.get("full_name"))
    fork_family = source_full_name or parent_full_name or full_name
    return {
        "provider": "github",
        "id": repo.get("id"),
        "node_id": repo.get("node_id"),
        "full_name": full_name,
        "repo_key": normalize_repo_key(full_name),
        "fork_family_key": normalize_repo_key(fork_family),
        "source_full_name": source_full_name,
        "parent_full_name": parent_full_name,
        "fork": bool(repo.get("fork")),
        "private": bool(repo.get("private")),
        "archived": bool(repo.get("archived")),
        "disabled": bool(repo.get("disabled")),
        "stargazers_count": repo.get("stargazers_count"),
        "forks_count": repo.get("forks_count"),
        "open_issues_count": repo.get("open_issues_count"),
        "watchers_count": repo.get("watchers_count"),
        "language": repo.get("language"),
        "topics": repo.get("topics") if isinstance(repo.get("topics"), list) else [],
        "collection": {
            "api_surface": "github-rest",
            "api_version": GITHUB_API_VERSION,
            "visibility": "public",
            "auth_required": False,
            "endpoint_kinds": ["search/repositories", "repos", "issues"],
        },
        "created_at": repo.get("created_at"),
        "updated_at": repo.get("updated_at"),
        "pushed_at": repo.get("pushed_at"),
        "has_issues": bool(repo.get("has_issues")),
        "has_discussions": bool(repo.get("has_discussions")),
        "license_spdx": github_license_name(repo),
        "html_url": repo.get("html_url"),
    }


def issue_excerpt(issue: dict[str, object]) -> str:
    title = truncate_text(issue.get("title"), 180)
    body = truncate_text(issue.get("body"), 420)
    comments = issue.get("comments")
    updated_at = normalize_text(issue.get("updated_at"))
    url = normalize_text(issue.get("html_url"))
    chunks = [title]
    if body:
        chunks.append(body)
    if updated_at:
        chunks.append(f"updated_at={updated_at}")
    if comments not in ("", None):
        chunks.append(f"comments={comments}")
    if url:
        chunks.append(url)
    return " | ".join(chunks)


def github_issue_excerpts(client: object, full_name: str, issues_per_repo: int) -> list[str]:
    if issues_per_repo <= 0:
        return []
    owner_repo = github_full_name(full_name)
    parts = owner_repo.split("/")
    if len(parts) != 2:
        return []
    issues = client.get_json(
        f"/repos/{urllib.parse.quote(parts[0])}/{urllib.parse.quote(parts[1])}/issues",
        {"state": "all", "sort": "updated", "direction": "desc", "per_page": issues_per_repo},
    )
    excerpts: list[str] = []
    for item in safe_list(issues):
        if not isinstance(item, dict):
            continue
        if "pull_request" in item:
            continue
        excerpts.append(issue_excerpt(item))
        if len(excerpts) >= issues_per_repo:
            break
    return excerpts


def github_repo_detail(client: object, full_name: str) -> dict[str, object]:
    parts = github_full_name(full_name).split("/")
    if len(parts) != 2:
        return {}
    detail = client.get_json(f"/repos/{urllib.parse.quote(parts[0])}/{urllib.parse.quote(parts[1])}", {})
    return detail if isinstance(detail, dict) else {}


def github_search_repositories(
    client: object,
    query: str,
    max_candidates: int,
    per_page: int,
    sort: str,
    order: str,
    issues_per_repo: int,
) -> list[dict[str, object]]:
    per_page = max(1, min(per_page, 100))
    max_candidates = max(0, max_candidates)
    query = public_github_query(query)
    rows: list[dict[str, object]] = []
    page = 1
    while len(rows) < max_candidates:
        try:
            search_result = client.get_json(
                "/search/repositories",
                {"q": query, "sort": sort, "order": order, "per_page": per_page, "page": page},
            )
        except GitHubApiError:
            if rows:
                break
            raise
        if not isinstance(search_result, dict):
            break
        items = safe_list(search_result.get("items"))
        if not items:
            break
        for item in items:
            if not isinstance(item, dict):
                continue
            full_name = github_full_name(item.get("full_name"))
            if bool(item.get("private")):
                continue
            try:
                detail = github_repo_detail(client, full_name)
            except GitHubApiError:
                detail = {}
            repo = detail if detail else item
            if bool(repo.get("private")):
                continue
            try:
                issues = github_issue_excerpts(client, full_name, issues_per_repo)
            except GitHubApiError:
                issues = []
            rows.append(github_candidate_from_repo(repo, query, issues))
            if len(rows) >= max_candidates:
                break
        if len(items) < per_page:
            break
        page += 1
    return rows


def public_github_query(query: str) -> str:
    normalized = " ".join(normalize_text(query).split())
    lowered = normalized.lower()
    if "is:private" in lowered:
        raise ValueError("GitHub Source MVP only supports public repository search.")
    if "is:public" not in lowered:
        normalized = f"{normalized} is:public".strip()
    return normalized


def github_candidate_from_repo(repo: dict[str, object], query: str, issue_excerpts: list[str]) -> dict[str, object]:
    metadata = github_repo_metadata(repo)
    full_name = normalize_text(metadata.get("full_name"))
    html_url = normalize_url(metadata.get("html_url")) or f"https://github.com/{full_name}"
    topics = metadata.get("topics") if isinstance(metadata.get("topics"), list) else []
    description = truncate_text(repo.get("description"), 600)
    raw_text_blob = "\n".join([description, " ".join(normalize_text(topic) for topic in topics), "\n".join(issue_excerpts)])
    lanes = github_search_lanes(metadata, raw_text_blob)
    project_name = full_name or normalize_text(repo.get("name")) or "unknown"
    candidate = {
        "source": "github-search",
        "source_url": html_url,
        "project_url": html_url,
        "project_name": project_name,
        "repository": full_name,
        "license": github_license_name(repo),
        "short_description": description,
        "raw_metadata": metadata,
        "raw_text": {
            "readme_excerpt": f"GitHub description: {description}" if description else "",
            "issue_excerpts": issue_excerpts,
            "discussion_excerpts": [],
            "marketplace_or_store_text": "",
            "external_mentions": [f"github_search_query={query}"],
        },
        "search_lanes": lanes,
        "collector_notes": github_collector_notes(metadata),
    }
    return normalize_candidate(candidate, utc_now())


def github_search_lanes(metadata: dict[str, object], text: str) -> dict[str, bool]:
    lowered = text.lower()
    topics = " ".join(normalize_text(topic).lower() for topic in safe_list(metadata.get("topics")))
    full_text = f"{lowered}\n{topics}"
    commercial_count = sum(1 for term in MONEY_TERMS if term in full_text)
    cli_count = sum(1 for term in CLI_TERMS if term in full_text)
    pain_count = sum(1 for term in PAIN_TERMS if term in full_text)
    academic_count = sum(1 for term in ACADEMIC_TERMS if term in full_text)
    return {
        "active_abandoned_forks": bool(metadata.get("fork")) and (commercial_count > 0 or pain_count > 0),
        "cli_to_ui_gap": cli_count > 0 and ("dashboard" in full_text or "ui" in full_text or "hosted" in full_text),
        "commercial_intent_density": commercial_count >= 1,
        "academic_hobbyist_bias": academic_count >= 2 and commercial_count == 0,
    }


def github_collector_notes(metadata: dict[str, object]) -> str:
    notes = [
        "Collected from public GitHub REST API.",
        "GitHub popularity is discovery evidence, not money evidence.",
    ]
    if metadata.get("fork"):
        notes.append("Repository is a fork; fork_family_key should be used for dedupe.")
    if metadata.get("archived"):
        notes.append("Repository is archived.")
    return " ".join(notes)


def collect_github_to_file(
    output_path: Path,
    query: str,
    max_candidates: int,
    per_page: int,
    sort: str,
    order: str,
    issues_per_repo: int,
    token: str,
    api_base: str,
) -> dict[str, object]:
    client = GitHubApiClient(token=token, api_base=api_base, timeout=HTTP_TIMEOUT_SECONDS)
    candidates = github_search_repositories(client, query, max_candidates, per_page, sort, order, issues_per_repo)
    write_jsonl(output_path, candidates)
    return {"output_path": str(output_path), "candidate_count": len(candidates), "query": query}


def gitlab_full_path(value: object) -> str:
    return normalize_text(value).strip("/")


def gitlab_project_metadata(project: dict[str, object]) -> dict[str, object]:
    full_path = gitlab_full_path(project.get("path_with_namespace"))
    forked_from = safe_dict(project.get("forked_from_project"))
    forked_from_path = gitlab_full_path(forked_from.get("path_with_namespace"))
    web_url = normalize_url(project.get("web_url")) or (f"https://gitlab.com/{full_path}" if full_path else "")
    fork_family = forked_from_path or full_path
    topics = project.get("topics") if isinstance(project.get("topics"), list) else project.get("tag_list")
    return {
        "provider": "gitlab",
        "id": project.get("id"),
        "path_with_namespace": full_path,
        "repo_key": normalize_repo_key(web_url or full_path),
        "fork_family_key": normalize_repo_key(f"https://gitlab.com/{fork_family}" if fork_family else web_url),
        "forked_from_path_with_namespace": forked_from_path,
        "fork": bool(forked_from_path),
        "visibility": normalize_text(project.get("visibility")),
        "archived": bool(project.get("archived")),
        "star_count": project.get("star_count"),
        "forks_count": project.get("forks_count"),
        "open_issues_count": project.get("open_issues_count"),
        "last_activity_at": project.get("last_activity_at"),
        "created_at": project.get("created_at"),
        "default_branch": project.get("default_branch"),
        "topics": topics if isinstance(topics, list) else [],
        "collection": {
            "api_surface": "gitlab-rest",
            "api_version": "v4",
            "visibility": "public",
            "auth_required": False,
            "endpoint_kinds": ["projects", "project-issues"],
        },
        "web_url": web_url,
    }


def gitlab_issue_excerpt(issue: dict[str, object]) -> str:
    title = truncate_text(issue.get("title"), 180)
    description = truncate_text(issue.get("description"), 420)
    updated_at = normalize_text(issue.get("updated_at"))
    url = normalize_text(issue.get("web_url"))
    chunks = [title]
    if description:
        chunks.append(description)
    if updated_at:
        chunks.append(f"updated_at={updated_at}")
    if url:
        chunks.append(url)
    return " | ".join(chunk for chunk in chunks if chunk)


def gitlab_issue_excerpts(client: object, project_id: object, issues_per_project: int) -> list[str]:
    if issues_per_project <= 0 or project_id in ("", None):
        return []
    issues = client.get_json(
        f"/projects/{urllib.parse.quote(str(project_id), safe='')}/issues",
        {"state": "all", "order_by": "updated_at", "sort": "desc", "per_page": issues_per_project},
    )
    excerpts: list[str] = []
    for item in safe_list(issues):
        if not isinstance(item, dict):
            continue
        excerpts.append(gitlab_issue_excerpt(item))
        if len(excerpts) >= issues_per_project:
            break
    return excerpts


def gitlab_search_lanes(metadata: dict[str, object], text: str) -> dict[str, bool]:
    lowered = text.lower()
    topics = " ".join(normalize_text(topic).lower() for topic in safe_list(metadata.get("topics")))
    full_text = f"{lowered}\n{topics}"
    commercial_count = sum(1 for term in MONEY_TERMS if term in full_text)
    cli_count = sum(1 for term in CLI_TERMS if term in full_text)
    pain_count = sum(1 for term in PAIN_TERMS if term in full_text)
    academic_count = sum(1 for term in ACADEMIC_TERMS if term in full_text)
    return {
        "active_abandoned_forks": bool(metadata.get("fork")) and (commercial_count > 0 or pain_count > 0),
        "cli_to_ui_gap": cli_count > 0 and ("dashboard" in full_text or "ui" in full_text or "hosted" in full_text),
        "commercial_intent_density": commercial_count >= 1,
        "academic_hobbyist_bias": academic_count >= 2 and commercial_count == 0,
    }


def gitlab_candidate_from_project(project: dict[str, object], search: str, issue_excerpts: list[str]) -> dict[str, object]:
    metadata = gitlab_project_metadata(project)
    full_path = normalize_text(metadata.get("path_with_namespace"))
    web_url = normalize_url(metadata.get("web_url")) or f"https://gitlab.com/{full_path}"
    topics = metadata.get("topics") if isinstance(metadata.get("topics"), list) else []
    description = truncate_text(project.get("description"), 600)
    raw_text_blob = "\n".join([description, " ".join(normalize_text(topic) for topic in topics), "\n".join(issue_excerpts)])
    lanes = gitlab_search_lanes(metadata, raw_text_blob)
    candidate = {
        "source": "gitlab-search",
        "source_url": web_url,
        "project_url": web_url,
        "project_name": full_path or normalize_text(project.get("name")) or "unknown",
        "repository": full_path,
        "license": "unknown",
        "short_description": description,
        "raw_metadata": metadata,
        "raw_text": {
            "readme_excerpt": f"GitLab description: {description}" if description else "",
            "issue_excerpts": issue_excerpts,
            "discussion_excerpts": [],
            "marketplace_or_store_text": "",
            "external_mentions": [f"gitlab_search={search}"],
        },
        "search_lanes": lanes,
        "collector_notes": "Collected from public GitLab REST API. GitLab popularity is discovery evidence, not money evidence.",
    }
    return normalize_candidate(candidate, utc_now())


def gitlab_search_projects(
    client: object,
    search: str,
    max_candidates: int,
    per_page: int,
    order_by: str,
    sort: str,
    issues_per_project: int,
) -> list[dict[str, object]]:
    per_page = max(1, min(per_page, 100))
    max_candidates = max(0, max_candidates)
    rows: list[dict[str, object]] = []
    page = 1
    while len(rows) < max_candidates:
        try:
            projects = client.get_json(
                "/projects",
                {
                    "search": search,
                    "visibility": "public",
                    "order_by": order_by,
                    "sort": sort,
                    "per_page": per_page,
                    "page": page,
                },
            )
        except GitLabApiError:
            if rows:
                break
            raise
        items = safe_list(projects)
        if not items:
            break
        for item in items:
            if not isinstance(item, dict):
                continue
            if normalize_text(item.get("visibility")) != "public":
                continue
            try:
                issues = gitlab_issue_excerpts(client, item.get("id"), issues_per_project)
            except GitLabApiError:
                issues = []
            rows.append(gitlab_candidate_from_project(item, search, issues))
            if len(rows) >= max_candidates:
                break
        if len(items) < per_page:
            break
        page += 1
    return rows


def collect_gitlab_to_file(
    output_path: Path,
    search: str,
    max_candidates: int,
    per_page: int,
    order_by: str,
    sort: str,
    issues_per_project: int,
    token: str,
    api_base: str,
) -> dict[str, object]:
    client = GitLabApiClient(token=token, api_base=api_base, timeout=HTTP_TIMEOUT_SECONDS)
    candidates = gitlab_search_projects(client, search, max_candidates, per_page, order_by, sort, issues_per_project)
    write_jsonl(output_path, candidates)
    return {"output_path": str(output_path), "candidate_count": len(candidates), "search": search}


def hn_clean_feeds(feeds: list[str] | tuple[str, ...]) -> list[str]:
    cleaned: list[str] = []
    for feed in feeds:
        normalized = normalize_text(feed)
        if normalized not in HN_FEEDS:
            raise ValueError(f"Unsupported Hacker News feed: {normalized}")
        if normalized not in cleaned:
            cleaned.append(normalized)
    return cleaned


def hn_int_value(value: object) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return 0


def strip_html_text(value: object) -> str:
    text = html.unescape(normalize_text(value))
    text = HN_HTML_TAG_RE.sub(" ", text)
    return " ".join(text.split())


def hn_item_url(item_id: object) -> str:
    normalized_id = hn_int_value(item_id)
    if normalized_id <= 0:
        return ""
    return f"https://news.ycombinator.com/item?id={normalized_id}"


def hn_get_item(client: object, item_id: object) -> dict[str, object]:
    normalized_id = hn_int_value(item_id)
    if normalized_id <= 0:
        return {}
    item = client.get_json(f"/item/{normalized_id}.json", {})
    return item if isinstance(item, dict) else {}


def hn_document_from_item(item: dict[str, object], source_feed: str, story_id: object = 0) -> dict[str, object]:
    if not item or bool(item.get("deleted")) or bool(item.get("dead")):
        return {}
    item_id = hn_int_value(item.get("id"))
    item_type = normalize_text(item.get("type"))
    if item_id <= 0 or item_type not in {"story", "comment"}:
        return {}
    title = strip_html_text(item.get("title"))
    body = strip_html_text(item.get("text"))
    if not title and not body:
        return {}
    resolved_story_id = hn_int_value(story_id)
    if item_type == "story":
        resolved_story_id = item_id
    if resolved_story_id <= 0:
        resolved_story_id = hn_int_value(item.get("parent"))
    return {
        "id": item_id,
        "type": item_type,
        "story_id": resolved_story_id,
        "parent": hn_int_value(item.get("parent")),
        "source_feed": source_feed,
        "title": title,
        "text": body,
        "url": hn_item_url(item_id),
        "story_url": hn_item_url(resolved_story_id),
        "score": hn_int_value(item.get("score")),
        "time": item.get("time"),
        "kids": safe_list(item.get("kids")),
    }


def hn_story_ids(client: object, feeds: list[str], max_stories: int) -> list[int]:
    if max_stories <= 0:
        return []
    ids: list[int] = []
    seen: set[int] = set()
    for feed in feeds:
        raw_ids = safe_list(client.get_json(f"/{feed}.json", {}))
        for raw_id in raw_ids:
            item_id = hn_int_value(raw_id)
            if item_id <= 0 or item_id in seen:
                continue
            ids.append(item_id)
            seen.add(item_id)
            if len(ids) >= max_stories:
                return ids
    return ids


def hn_comment_documents(
    client: object,
    story: dict[str, object],
    source_feed: str,
    comments_per_story: int,
    max_items: int,
    max_depth: int = 2,
) -> tuple[list[dict[str, object]], int]:
    if comments_per_story <= 0 or max_items <= 0:
        return [], 0
    story_id = hn_int_value(story.get("id"))
    queue: list[tuple[int, int]] = []
    for raw_child_id in safe_list(story.get("kids")):
        child_id = hn_int_value(raw_child_id)
        if child_id > 0:
            queue.append((child_id, 1))
    comments: list[dict[str, object]] = []
    fetched = 0
    seen: set[int] = set()
    while queue and len(comments) < comments_per_story and fetched < max_items:
        comment_id, depth = queue.pop(0)
        if comment_id in seen:
            continue
        seen.add(comment_id)
        item = hn_get_item(client, comment_id)
        fetched += 1
        if not item:
            continue
        if depth < max_depth:
            for raw_child_id in safe_list(item.get("kids")):
                child_id = hn_int_value(raw_child_id)
                if child_id > 0 and child_id not in seen:
                    queue.append((child_id, depth + 1))
        document = hn_document_from_item(item, source_feed, story_id)
        if document and normalize_text(document.get("type")) == "comment":
            comments.append(document)
    return comments, fetched


def hn_collect_documents(
    client: object,
    feeds: list[str],
    max_stories: int,
    comments_per_story: int,
    max_total_items: int,
) -> dict[str, object]:
    story_ids = hn_story_ids(client, feeds, max_stories)
    documents: list[dict[str, object]] = []
    stories: list[dict[str, object]] = []
    comments: list[dict[str, object]] = []
    fetched_items = 0
    story_feed_by_id: dict[int, str] = {}

    for feed in feeds:
        if len(story_feed_by_id) >= len(story_ids):
            break
        for story_id in story_ids:
            if story_id not in story_feed_by_id:
                story_feed_by_id[story_id] = feed

    for story_id in story_ids:
        if fetched_items >= max_total_items:
            break
        source_feed = story_feed_by_id.get(story_id, feeds[0] if feeds else "askstories")
        story = hn_get_item(client, story_id)
        fetched_items += 1
        story_document = hn_document_from_item(story, source_feed, story_id)
        if not story_document or normalize_text(story_document.get("type")) != "story":
            continue
        thread_key, thread_label = hn_cluster_key_and_label(hn_document_text(story_document))
        story_document["thread_cluster_key"] = thread_key
        story_document["thread_cluster_label"] = thread_label
        stories.append(story_document)
        documents.append(story_document)
        remaining_items = max_total_items - fetched_items
        story_comments, comment_fetches = hn_comment_documents(
            client,
            story,
            source_feed,
            comments_per_story,
            remaining_items,
        )
        for comment in story_comments:
            comment["story_title"] = story_document.get("title")
            comment["thread_cluster_key"] = thread_key
            comment["thread_cluster_label"] = thread_label
        fetched_items += comment_fetches
        comments.extend(story_comments)
        documents.extend(story_comments)

    return {
        "story_ids": story_ids,
        "stories": stories,
        "comments": comments,
        "documents": documents,
        "fetched_items": fetched_items,
    }


def hn_document_text(document: dict[str, object]) -> str:
    return " ".join(
        chunk
        for chunk in [
            normalize_text(document.get("title")),
            normalize_text(document.get("text")),
        ]
        if chunk
    )


def hn_text_window(source: str, needle: str, limit: int = 260) -> str:
    lowered = source.lower()
    index = lowered.find(needle)
    if index < 0:
        return truncate_text(source, limit)
    start = max(0, index - 90)
    end = min(len(source), index + len(needle) + 170)
    return truncate_text(source[start:end].strip(), limit)


def hn_extract_pain_phrases(text: str, limit: int = 4) -> list[str]:
    phrases: list[str] = []
    lowered = text.lower()
    for pattern in HN_PAIN_PATTERNS:
        if pattern in lowered:
            phrase = hn_text_window(text, pattern)
            if phrase and phrase not in phrases:
                phrases.append(phrase)
        if len(phrases) >= limit:
            break
    return phrases


def hn_meaningful_words(text: str) -> list[str]:
    lowered = text.lower()
    words: list[str] = []
    for word in HN_WORD_RE.findall(lowered):
        if word in HN_CLUSTER_STOPWORDS:
            continue
        if len(word) < 3 and word not in {"ai", "api", "ui", "ux", "seo"}:
            continue
        if word not in words:
            words.append(word)
    return words


def hn_cluster_key_and_label(text: str) -> tuple[str, str]:
    lowered = text.lower()
    focused_words: list[str] = []
    for pattern in ("alternative to", "alternatives to", "how do i", "how can i", "how to", "is there a tool"):
        index = lowered.find(pattern)
        if index >= 0:
            focused_words = hn_meaningful_words(lowered[index + len(pattern) :])
            break
    words = focused_words if focused_words else hn_meaningful_words(text)
    if not words:
        return "general-pain", "general pain"
    selected = words[:6]
    return "-".join(selected), " ".join(selected)


def hn_cluster_id(key: str) -> str:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return f"hn_{digest[:12]}"


def hn_append_unique(values: list[object], value: object) -> None:
    if value not in values:
        values.append(value)


def hn_hard_reject_reasons(text: str) -> list[str]:
    lowered = text.lower()
    return [f"blocked-term:{term}" for term in HN_REJECT_TERMS if term in lowered]


def hn_dimension_score(text: str, terms: tuple[str, ...], strong_count: int = 2) -> int:
    count = len(matched_terms(text, terms))
    if count >= strong_count:
        return 2
    if count == 1:
        return 1
    return 0


def hn_score_demand_cluster(cluster: dict[str, object]) -> dict[str, object]:
    text = normalize_text(cluster.get("text_blob"))
    story_count = len(safe_list(cluster.get("story_ids")))
    excerpt_count = len(safe_list(cluster.get("excerpts")))
    hard_reasons = hn_hard_reject_reasons(text)
    buyer_clarity = hn_dimension_score(text, HN_BUYER_TERMS, 1)
    if buyer_clarity == 0:
        hard_reasons.append("no-clear-buyer")
    dimensions = {
        "pain_recurrence": 2 if story_count >= 2 or excerpt_count >= 3 else 1 if excerpt_count >= 2 else 0,
        "buyer_clarity": buyer_clarity,
        "current_workaround_clarity": hn_dimension_score(text, HN_WORKAROUND_TERMS, 2),
        "no_call_product_angle": hn_dimension_score(text, HN_PRODUCT_TERMS, 2),
        "async_distribution_hint": hn_dimension_score(text, HN_ASYNC_DISTRIBUTION_TERMS, 2),
        "legal_privacy_safety": 0 if hard_reasons else 2,
        "not_hype_novelty_only": 0 if hn_dimension_score(text, HN_HYPE_TERMS, 1) and not hn_dimension_score(text, HN_PRODUCT_TERMS, 1) else 2,
    }
    total = sum(dimensions.values())
    if hard_reasons:
        verdict = "rejected"
    elif total >= HN_CANDIDATE_MIN_SCORE:
        verdict = "candidate"
    elif total >= HN_REPORT_ONLY_MIN_SCORE:
        verdict = "report-only"
    else:
        verdict = "ignored"
    return {
        "dimensions": dimensions,
        "total": total,
        "verdict": verdict,
        "hard_reasons": sorted(set(hard_reasons)),
    }


def hn_build_demand_clusters(documents: list[dict[str, object]]) -> list[dict[str, object]]:
    clusters: dict[str, dict[str, object]] = {}
    for document in documents:
        text = hn_document_text(document)
        pain_phrases = hn_extract_pain_phrases(text)
        if not pain_phrases:
            continue
        key = normalize_text(document.get("thread_cluster_key"))
        label = normalize_text(document.get("thread_cluster_label"))
        if not key or not label:
            key, label = hn_cluster_key_and_label(text)
        if key not in clusters:
            clusters[key] = {
                "cluster_id": hn_cluster_id(key),
                "key": key,
                "label": label,
                "story_ids": [],
                "comment_ids": [],
                "source_feeds": [],
                "excerpts": [],
                "pain_phrases": [],
                "points_total": 0,
                "text_blob": "",
            }
        cluster = clusters[key]
        item_type = normalize_text(document.get("type"))
        story_id = hn_int_value(document.get("story_id"))
        item_id = hn_int_value(document.get("id"))
        if story_id > 0:
            hn_append_unique(cluster["story_ids"], story_id)
        if item_type == "comment" and item_id > 0:
            hn_append_unique(cluster["comment_ids"], item_id)
        hn_append_unique(cluster["source_feeds"], normalize_text(document.get("source_feed")))
        cluster["points_total"] = hn_int_value(cluster.get("points_total")) + hn_int_value(document.get("score"))
        cluster["text_blob"] = "\n".join([normalize_text(cluster.get("text_blob")), text]).strip()
        for phrase in pain_phrases:
            hn_append_unique(cluster["pain_phrases"], phrase)
        excerpts = safe_list(cluster.get("excerpts"))
        if len(excerpts) < 8:
            excerpts.append(
                {
                    "item_id": item_id,
                    "story_id": story_id,
                    "type": item_type,
                    "url": normalize_text(document.get("url")),
                    "story_url": normalize_text(document.get("story_url")),
                    "excerpt": pain_phrases[0],
                }
            )

    rows: list[dict[str, object]] = []
    for cluster in clusters.values():
        scoring = hn_score_demand_cluster(cluster)
        cluster["score"] = scoring
        cluster["story_count"] = len(safe_list(cluster.get("story_ids")))
        cluster["comment_count"] = len(safe_list(cluster.get("comment_ids")))
        cluster["excerpt_count"] = len(safe_list(cluster.get("excerpts")))
        rows.append(cluster)
    rows.sort(
        key=lambda cluster: (
            -hn_int_value(safe_dict(cluster.get("score")).get("total")),
            -hn_int_value(cluster.get("story_count")),
            -hn_int_value(cluster.get("comment_count")),
            normalize_text(cluster.get("label")),
        )
    )
    return rows


def hn_cluster_source_url(cluster: dict[str, object]) -> str:
    excerpts = safe_list(cluster.get("excerpts"))
    for excerpt in excerpts:
        if isinstance(excerpt, dict):
            story_url = normalize_text(excerpt.get("story_url"))
            if story_url:
                return story_url
            url = normalize_text(excerpt.get("url"))
            if url:
                return url
    story_ids = safe_list(cluster.get("story_ids"))
    return hn_item_url(story_ids[0]) if story_ids else ""


def hn_cluster_discussion_excerpts(cluster: dict[str, object], limit: int = 5) -> list[str]:
    excerpts: list[str] = []
    for item in safe_list(cluster.get("excerpts")):
        if not isinstance(item, dict):
            continue
        url = normalize_text(item.get("url")) or normalize_text(item.get("story_url"))
        text = truncate_text(item.get("excerpt"), 260)
        if url:
            excerpts.append(f"{text} [{url}]")
        else:
            excerpts.append(text)
        if len(excerpts) >= limit:
            break
    return excerpts


def hn_candidate_from_cluster(cluster: dict[str, object], week: str) -> dict[str, object]:
    score = safe_dict(cluster.get("score"))
    dimensions = safe_dict(score.get("dimensions"))
    source_url = hn_cluster_source_url(cluster)
    cluster_id = normalize_text(cluster.get("cluster_id"))
    candidate = {
        "candidate_id": f"cand_{hashlib.sha256(f'hn-demand|{cluster_id}'.encode('utf-8')).hexdigest()[:16]}",
        "source": "hn-demand",
        "source_url": source_url,
        "project_url": source_url,
        "project_name": f"HN demand: {normalize_text(cluster.get('label')) or 'unknown pain'}",
        "repository": "",
        "license": "unknown",
        "short_description": truncate_text(
            f"Public HN pain cluster: {normalize_text(cluster.get('label'))}. "
            f"Score {score.get('total', 0)}/14 across recurrence, buyer clarity, workaround clarity, "
            "no-call product angle, async distribution, and safety checks.",
            600,
        ),
        "raw_metadata": {
            "provider": "hacker-news",
            "source_type": "demand-cluster",
            "cluster_id": cluster_id,
            "story_ids": safe_list(cluster.get("story_ids")),
            "comment_ids": safe_list(cluster.get("comment_ids")),
            "story_count": cluster.get("story_count"),
            "comment_count": cluster.get("comment_count"),
            "points_total": cluster.get("points_total"),
            "score": score,
            "collection": {
                "api_surface": "hacker-news-api",
                "visibility": "public",
                "auth_required": False,
                "week": week,
            },
            "prefilter_hints": {},
        },
        "raw_text": {
            "readme_excerpt": "",
            "issue_excerpts": [truncate_text(phrase, 260) for phrase in safe_list(cluster.get("pain_phrases"))[:5]],
            "discussion_excerpts": hn_cluster_discussion_excerpts(cluster),
            "marketplace_or_store_text": "",
            "external_mentions": [f"hn:{source_url}"] if source_url else [],
        },
        "search_lanes": {
            "active_abandoned_forks": False,
            "cli_to_ui_gap": False,
            "commercial_intent_density": hn_int_value(dimensions.get("no_call_product_angle")) >= 1
            and hn_int_value(dimensions.get("buyer_clarity")) >= 1,
            "academic_hobbyist_bias": False,
            "demand_pain_cluster": True,
        },
        "collector_notes": (
            "Collected from public Hacker News API. Demand cluster is evidence of discussion pain, "
            "not proof of willingness to pay. Product angle is inferred and must pass the normal "
            "proof-card filter before any build decision."
        ),
    }
    return normalize_candidate(candidate, utc_now())


def collect_hn_demand_to_file(
    output_path: Path,
    feeds: list[str],
    max_stories: int,
    comments_per_story: int,
    max_total_items: int,
    max_clusters: int,
    max_candidates: int,
    api_base: str,
    week: str,
    client: object | None = None,
) -> dict[str, object]:
    cleaned_feeds = hn_clean_feeds(feeds)
    hn_client = client if client is not None else HackerNewsApiClient(api_base=api_base, timeout=HTTP_TIMEOUT_SECONDS)
    collection = hn_collect_documents(
        hn_client,
        cleaned_feeds,
        max_stories=max(0, max_stories),
        comments_per_story=max(0, comments_per_story),
        max_total_items=max(0, max_total_items),
    )
    clusters = hn_build_demand_clusters(collection["documents"] if isinstance(collection.get("documents"), list) else [])
    selected_clusters = clusters[: max(0, max_clusters)]
    candidates: list[dict[str, object]] = []
    for cluster in selected_clusters:
        score = safe_dict(cluster.get("score"))
        if normalize_text(score.get("verdict")) != "candidate":
            continue
        candidates.append(hn_candidate_from_cluster(cluster, week))
        if len(candidates) >= max(0, max_candidates):
            break
    write_jsonl(output_path, candidates)
    return {
        "output_path": str(output_path),
        "candidate_count": len(candidates),
        "cluster_count": len(selected_clusters),
        "total_cluster_count": len(clusters),
        "story_count": len(safe_list(collection.get("stories"))),
        "comment_count": len(safe_list(collection.get("comments"))),
        "fetched_items": collection.get("fetched_items"),
        "feeds": cleaned_feeds,
        "caps": {
            "max_stories": max_stories,
            "comments_per_story": comments_per_story,
            "max_total_items": max_total_items,
            "max_clusters": max_clusters,
            "max_candidates": max_candidates,
        },
        "clusters": selected_clusters,
        "candidates": candidates,
    }


def hn_report_cluster_lines(cluster: dict[str, object]) -> list[str]:
    score = safe_dict(cluster.get("score"))
    dimensions = safe_dict(score.get("dimensions"))
    hard_reasons = safe_list(score.get("hard_reasons"))
    source_url = hn_cluster_source_url(cluster)
    lines = [
        f"### {normalize_text(cluster.get('label')) or 'unknown pain'}",
        "",
        f"- Verdict: `{normalize_text(score.get('verdict')) or 'unknown'}`",
        f"- Score: `{score.get('total', 0)}/14`",
        f"- Stories/comments: `{cluster.get('story_count', 0)}/{cluster.get('comment_count', 0)}`",
        f"- Source: {source_url or 'unknown'}",
        f"- Hard reasons: `{', '.join(normalize_text(reason) for reason in hard_reasons) or 'none'}`",
        f"- Dimensions: {', '.join(f'{key}={value}' for key, value in sorted(dimensions.items())) or 'unknown'}",
        "",
        "Representative excerpts:",
        "",
    ]
    excerpts = hn_cluster_discussion_excerpts(cluster, 3)
    if excerpts:
        for excerpt in excerpts:
            lines.append(f"- {excerpt}")
    else:
        lines.append("- none")
    lines.append("")
    return lines


def write_hn_demand_report(data_dir: Path, week: str, collection: dict[str, object]) -> Path:
    paths = ensure_layout(data_dir, week)
    report_path = paths["reports"] / f"{week}-demand-miner.md"
    clusters = [cluster for cluster in safe_list(collection.get("clusters")) if isinstance(cluster, dict)]
    candidate_clusters = [
        cluster for cluster in clusters if normalize_text(safe_dict(cluster.get("score")).get("verdict")) == "candidate"
    ]
    report_only_clusters = [
        cluster for cluster in clusters if normalize_text(safe_dict(cluster.get("score")).get("verdict")) == "report-only"
    ]
    rejected_clusters = [
        cluster for cluster in clusters if normalize_text(safe_dict(cluster.get("score")).get("verdict")) == "rejected"
    ]
    ignored_clusters = [
        cluster for cluster in clusters if normalize_text(safe_dict(cluster.get("score")).get("verdict")) == "ignored"
    ]
    caps = safe_dict(collection.get("caps"))
    lines = [
        f"# HN Demand Miner - {week}",
        "",
        f"- Generated at: `{utc_now()}`",
        f"- Feeds: `{', '.join(normalize_text(feed) for feed in safe_list(collection.get('feeds')))}`",
        f"- Stories collected: `{collection.get('story_count', 0)}`",
        f"- Comments collected: `{collection.get('comment_count', 0)}`",
        f"- API item fetches: `{collection.get('fetched_items', 0)}`",
        f"- Clusters reported: `{collection.get('cluster_count', 0)}`",
        f"- Candidates emitted: `{collection.get('candidate_count', 0)}`",
        f"- Candidate JSONL: `{collection.get('output_path')}`",
        "",
        "## Caps",
        "",
    ]
    for key, value in sorted(caps.items()):
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Emitted Candidates", ""])
    if candidate_clusters:
        for cluster in candidate_clusters:
            lines.extend(hn_report_cluster_lines(cluster))
    else:
        lines.append("- none")
        lines.append("")
    lines.extend(["## Report-Only Clusters", ""])
    if report_only_clusters:
        for cluster in report_only_clusters:
            lines.extend(hn_report_cluster_lines(cluster))
    else:
        lines.append("- none")
        lines.append("")
    lines.extend(["## Rejected Or Noisy Patterns", ""])
    noisy_clusters = rejected_clusters + ignored_clusters
    if noisy_clusters:
        for cluster in noisy_clusters[:5]:
            lines.extend(hn_report_cluster_lines(cluster))
    else:
        lines.append("- none")
        lines.append("")
    lines.extend(
        [
            "## Recommended Filter Updates",
            "",
            "- Treat HN demand clusters as discovery evidence only.",
            "- Require normal proof-card validation before Telegram-ready recommendations.",
            "- Promote a query/filter only when repeated clusters point to the same buyer, pain, and async channel.",
            "",
        ]
    )
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def hn_collection_summary(collection: dict[str, object]) -> dict[str, object]:
    return {
        "output_path": collection.get("output_path"),
        "candidate_count": collection.get("candidate_count"),
        "cluster_count": collection.get("cluster_count"),
        "total_cluster_count": collection.get("total_cluster_count"),
        "story_count": collection.get("story_count"),
        "comment_count": collection.get("comment_count"),
        "fetched_items": collection.get("fetched_items"),
        "feeds": collection.get("feeds"),
        "caps": collection.get("caps"),
    }


def run_hn_demand(
    data_dir: Path,
    week: str,
    output_path: Path,
    feeds: list[str],
    max_stories: int,
    comments_per_story: int,
    max_total_items: int,
    max_clusters: int,
    max_candidates: int,
    api_base: str,
    ingest: bool,
    client: object | None = None,
) -> dict[str, object]:
    collection = collect_hn_demand_to_file(
        output_path=output_path,
        feeds=feeds,
        max_stories=max_stories,
        comments_per_story=comments_per_story,
        max_total_items=max_total_items,
        max_clusters=max_clusters,
        max_candidates=max_candidates,
        api_base=api_base,
        week=week,
        client=client,
    )
    report_path = write_hn_demand_report(data_dir, week, collection)
    result: dict[str, object] = {"collection": hn_collection_summary(collection), "report_path": str(report_path)}
    if ingest:
        result["ingest"] = ingest_candidates(output_path, data_dir, week)
    return result


def reddit_clean_subreddit(value: object) -> str:
    text = normalize_text(value).removeprefix("r/").strip("/")
    if not text or not re.fullmatch(r"[A-Za-z0-9_]{2,21}", text):
        raise ValueError(f"Invalid subreddit: {value}")
    return text


def reddit_clean_subreddits(values: list[str] | tuple[str, ...]) -> list[str]:
    cleaned: list[str] = []
    for value in values:
        subreddit = reddit_clean_subreddit(value)
        if subreddit not in cleaned:
            cleaned.append(subreddit)
    if not cleaned:
        raise ValueError("At least one subreddit is required")
    return cleaned


def reddit_removed_text(value: object) -> bool:
    text = normalize_text(value).lower()
    return text in {"[removed]", "[deleted]", "removed", "deleted"}


def reddit_permalink(value: object) -> str:
    text = normalize_text(value)
    if not text:
        return ""
    if text.startswith("http://") or text.startswith("https://"):
        return normalize_url(text)
    return normalize_url(f"https://www.reddit.com{text if text.startswith('/') else '/' + text}")


def reddit_listing_children(payload: object) -> list[dict[str, object]]:
    if isinstance(payload, list):
        rows: list[dict[str, object]] = []
        for item in payload:
            rows.extend(reddit_listing_children(item))
        return rows
    if not isinstance(payload, dict):
        return []
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    children = data.get("children") if isinstance(data.get("children"), list) else []
    return [child for child in children if isinstance(child, dict)]


def reddit_document_from_thing(thing: dict[str, object], subreddit: str, parent_post: dict[str, object] | None = None) -> dict[str, object]:
    data = thing.get("data") if isinstance(thing.get("data"), dict) else {}
    kind = normalize_text(thing.get("kind"))
    if not data or kind not in {"t3", "t1"}:
        return {}
    if bool(data.get("removed_by_category")):
        return {}
    title = strip_html_text(data.get("title"))
    body = strip_html_text(data.get("selftext") if kind == "t3" else data.get("body"))
    if reddit_removed_text(title) or reddit_removed_text(body):
        return {}
    if not title and not body:
        return {}
    item_id = normalize_text(data.get("id"))
    if not item_id:
        return {}
    post = parent_post if parent_post is not None else data
    post_id = normalize_text(post.get("id")) or item_id
    text = " ".join(part for part in [title, body] if part)
    key, label = hn_cluster_key_and_label(text)
    return {
        "id": int(hashlib.sha256(f"reddit:{item_id}".encode("utf-8")).hexdigest()[:8], 16),
        "reddit_id": item_id,
        "type": "story" if kind == "t3" else "comment",
        "story_id": int(hashlib.sha256(f"reddit:{post_id}".encode("utf-8")).hexdigest()[:8], 16),
        "reddit_story_id": post_id,
        "parent": normalize_text(data.get("parent_id")),
        "source_feed": f"reddit:{subreddit}",
        "title": title,
        "text": body,
        "url": reddit_permalink(data.get("permalink")),
        "story_url": reddit_permalink(post.get("permalink")),
        "score": hn_int_value(data.get("score")),
        "time": data.get("created_utc"),
        "kids": [],
        "thread_cluster_key": key,
        "thread_cluster_label": label,
    }


def reddit_collect_documents(
    client: object,
    subreddits: list[str],
    sort: str,
    max_posts_per_subreddit: int,
    comments_per_post: int,
    max_total_items: int,
) -> dict[str, object]:
    if sort not in REDDIT_ALLOWED_SORTS:
        raise ValueError(f"Unsupported Reddit sort: {sort}")
    cleaned_subreddits = reddit_clean_subreddits(subreddits)
    documents: list[dict[str, object]] = []
    posts: list[dict[str, object]] = []
    comments: list[dict[str, object]] = []
    fetched_items = 0
    for subreddit in cleaned_subreddits:
        if fetched_items >= max_total_items:
            break
        listing = client.get_json(
            f"/r/{urllib.parse.quote(subreddit)}/{sort}",
            {"limit": max(1, min(max_posts_per_subreddit, 100)), "raw_json": 1},
        )
        post_count = 0
        for child in reddit_listing_children(listing):
            if post_count >= max_posts_per_subreddit or fetched_items >= max_total_items:
                break
            data = child.get("data") if isinstance(child.get("data"), dict) else {}
            document = reddit_document_from_thing(child, subreddit)
            if not document:
                continue
            document["subreddit"] = subreddit
            posts.append(document)
            documents.append(document)
            post_count += 1
            fetched_items += 1
            if comments_per_post <= 0 or fetched_items >= max_total_items:
                continue
            post_id = normalize_text(data.get("id"))
            if not post_id:
                continue
            comment_payload = client.get_json(
                f"/r/{urllib.parse.quote(subreddit)}/comments/{urllib.parse.quote(post_id)}",
                {"limit": max(1, min(comments_per_post, 100)), "depth": 1, "raw_json": 1},
            )
            comment_count = 0
            for comment_child in reddit_listing_children(comment_payload):
                if comment_count >= comments_per_post or fetched_items >= max_total_items:
                    break
                comment = reddit_document_from_thing(comment_child, subreddit, data)
                if not comment or normalize_text(comment.get("type")) != "comment":
                    continue
                comment["subreddit"] = subreddit
                comment["thread_cluster_key"] = document.get("thread_cluster_key")
                comment["thread_cluster_label"] = document.get("thread_cluster_label")
                comments.append(comment)
                documents.append(comment)
                comment_count += 1
                fetched_items += 1
    return {
        "subreddits": cleaned_subreddits,
        "posts": posts,
        "comments": comments,
        "documents": documents,
        "fetched_items": fetched_items,
    }


def reddit_cluster_source_url(cluster: dict[str, object]) -> str:
    for item in safe_list(cluster.get("excerpts")):
        if isinstance(item, dict):
            url = normalize_text(item.get("url")) or normalize_text(item.get("story_url"))
            if url:
                return url
    return ""


def reddit_candidate_from_cluster(cluster: dict[str, object], week: str, subreddits: list[str]) -> dict[str, object]:
    score = safe_dict(cluster.get("score"))
    dimensions = safe_dict(score.get("dimensions"))
    source_url = reddit_cluster_source_url(cluster) or hn_cluster_source_url(cluster)
    cluster_id = normalize_text(cluster.get("cluster_id"))
    candidate = {
        "candidate_id": f"cand_{hashlib.sha256(f'reddit-demand|{cluster_id}'.encode('utf-8')).hexdigest()[:16]}",
        "source": "reddit-demand",
        "source_url": source_url,
        "project_url": source_url,
        "project_name": f"Reddit demand: {normalize_text(cluster.get('label')) or 'unknown pain'}",
        "repository": "",
        "license": "unknown",
        "short_description": truncate_text(
            f"Public Reddit pain cluster from {', '.join(subreddits)}. "
            f"Score {score.get('total', 0)}/14 across recurrence, buyer clarity, workaround clarity, "
            "no-call product angle, async distribution, and safety checks.",
            600,
        ),
        "raw_metadata": {
            "provider": "reddit",
            "source_type": "demand-cluster",
            "cluster_id": cluster_id,
            "subreddits": subreddits,
            "score": score,
            "collection": {
                "api_surface": "reddit-oauth-api",
                "visibility": "public",
                "auth_required": True,
                "week": week,
                "retention_note": "Keep only short public excerpts and routinely purge raw Reddit content if needed.",
            },
            "prefilter_hints": {},
        },
        "raw_text": {
            "readme_excerpt": "",
            "issue_excerpts": [truncate_text(phrase, 260) for phrase in safe_list(cluster.get("pain_phrases"))[:5]],
            "discussion_excerpts": hn_cluster_discussion_excerpts(cluster),
            "marketplace_or_store_text": "",
            "external_mentions": [f"reddit:{source_url}"] if source_url else [],
        },
        "search_lanes": {
            "active_abandoned_forks": False,
            "cli_to_ui_gap": False,
            "commercial_intent_density": hn_int_value(dimensions.get("no_call_product_angle")) >= 1
            and hn_int_value(dimensions.get("buyer_clarity")) >= 1,
            "academic_hobbyist_bias": False,
            "demand_pain_cluster": True,
        },
        "collector_notes": (
            "Collected from Reddit OAuth API with strict caps. Demand cluster is evidence of public discussion pain, "
            "not proof of willingness to pay. Deleted or removed content is skipped."
        ),
    }
    return normalize_candidate(candidate, utc_now())


def collect_reddit_demand_to_file(
    output_path: Path,
    subreddits: list[str],
    sort: str,
    max_posts_per_subreddit: int,
    comments_per_post: int,
    max_total_items: int,
    max_clusters: int,
    max_candidates: int,
    week: str,
    client: object | None = None,
    access_token: str = "",
    client_id: str = "",
    client_secret: str = "",
    user_agent: str = "",
    oauth_api_base: str = REDDIT_OAUTH_API_BASE,
    auth_api_base: str = REDDIT_AUTH_API_BASE,
) -> dict[str, object]:
    cleaned_subreddits = reddit_clean_subreddits(subreddits)
    if client is None and not access_token and not (client_id and client_secret):
        raise RedditApiError("Reddit demand requires REDDIT_ACCESS_TOKEN or REDDIT_CLIENT_ID/REDDIT_CLIENT_SECRET")
    if client is None and not user_agent:
        raise RedditApiError("Reddit demand requires REDDIT_USER_AGENT")
    reddit_client = client if client is not None else RedditApiClient(
        access_token=access_token,
        user_agent=user_agent,
        oauth_api_base=oauth_api_base,
        auth_api_base=auth_api_base,
        timeout=HTTP_TIMEOUT_SECONDS,
        client_id=client_id,
        client_secret=client_secret,
    )
    collection = reddit_collect_documents(
        reddit_client,
        cleaned_subreddits,
        sort,
        max(0, max_posts_per_subreddit),
        max(0, comments_per_post),
        max(0, max_total_items),
    )
    clusters = hn_build_demand_clusters(collection["documents"] if isinstance(collection.get("documents"), list) else [])
    selected_clusters = clusters[: max(0, max_clusters)]
    candidates: list[dict[str, object]] = []
    for cluster in selected_clusters:
        score = safe_dict(cluster.get("score"))
        if normalize_text(score.get("verdict")) != "candidate":
            continue
        candidates.append(reddit_candidate_from_cluster(cluster, week, cleaned_subreddits))
        if len(candidates) >= max(0, max_candidates):
            break
    write_jsonl(output_path, candidates)
    return {
        "output_path": str(output_path),
        "candidate_count": len(candidates),
        "cluster_count": len(selected_clusters),
        "total_cluster_count": len(clusters),
        "post_count": len(safe_list(collection.get("posts"))),
        "comment_count": len(safe_list(collection.get("comments"))),
        "fetched_items": collection.get("fetched_items"),
        "subreddits": cleaned_subreddits,
        "sort": sort,
        "caps": {
            "max_posts_per_subreddit": max_posts_per_subreddit,
            "comments_per_post": comments_per_post,
            "max_total_items": max_total_items,
            "max_clusters": max_clusters,
            "max_candidates": max_candidates,
        },
        "clusters": selected_clusters,
        "candidates": candidates,
    }


def write_reddit_demand_report(data_dir: Path, week: str, result: dict[str, object]) -> Path:
    paths = ensure_layout(data_dir, week)
    report_path = paths["reports"] / f"{week}-reddit-demand-miner.md"
    lines = [
        f"# Reddit Demand Miner - {week}",
        "",
        f"- Generated at: `{utc_now()}`",
        f"- Subreddits: `{', '.join(normalize_text(item) for item in safe_list(result.get('subreddits')))}`",
        f"- Posts/comments: `{result.get('post_count', 0)}/{result.get('comment_count', 0)}`",
        f"- Candidates emitted: `{result.get('candidate_count', 0)}`",
        "",
        "## Clusters",
        "",
    ]
    clusters = safe_list(result.get("clusters"))
    if not clusters:
        lines.append("- none")
    for cluster in clusters:
        if isinstance(cluster, dict):
            lines.extend(hn_report_cluster_lines(cluster))
    report_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return report_path


def run_reddit_demand(
    data_dir: Path,
    week: str,
    output_path: Path,
    subreddits: list[str],
    sort: str,
    max_posts_per_subreddit: int,
    comments_per_post: int,
    max_total_items: int,
    max_clusters: int,
    max_candidates: int,
    ingest: bool,
    client: object | None = None,
) -> dict[str, object]:
    result = collect_reddit_demand_to_file(
        output_path=output_path,
        subreddits=subreddits,
        sort=sort,
        max_posts_per_subreddit=max_posts_per_subreddit,
        comments_per_post=comments_per_post,
        max_total_items=max_total_items,
        max_clusters=max_clusters,
        max_candidates=max_candidates,
        week=week,
        client=client,
        access_token=env_reddit_access_token(),
        client_id=env_reddit_client_id(),
        client_secret=env_reddit_client_secret(),
        user_agent=env_reddit_user_agent(),
    )
    report_path = write_reddit_demand_report(data_dir, week, result)
    response: dict[str, object] = {"collection": {key: value for key, value in result.items() if key not in {"clusters", "candidates"}}}
    response["report_path"] = str(report_path)
    if ingest and int(result.get("candidate_count", 0)) > 0:
        response["ingest"] = ingest_candidates(output_path, data_dir, week)
    return response


def ingest_candidates(input_path: Path, data_dir: Path, week: str) -> dict[str, object]:
    observed_at = utc_now()
    paths = ensure_layout(data_dir, week)
    raw_rows = read_jsonl(input_path)
    existing_candidates = read_jsonl(paths["candidates"])
    existing_ids = {normalize_text(row.get("candidate_id")) for row in existing_candidates}
    existing_events = read_jsonl(paths["events"])
    existing_alias_rows = read_jsonl(paths["identity_aliases"])
    aliases = alias_map_from_rows(existing_candidates, existing_alias_rows)
    statuses = status_by_candidate_for_week(existing_events, week)

    normalized_rows: list[dict[str, object]] = []
    events_written: list[dict[str, object]] = []

    for raw in raw_rows:
        candidate = normalize_candidate(raw, observed_at)
        resolved_id, alias_merged = resolve_candidate_id(candidate, aliases, existing_ids)
        if alias_merged:
            candidate["candidate_id"] = resolved_id
        candidate_id = normalize_text(candidate["candidate_id"])
        normalized_rows.append(candidate)
        append_jsonl(paths["raw_week"], candidate)

        evidence_path = paths["evidence"] / f"{candidate_id}.md"
        append_evidence(evidence_path, candidate)
        evidence_refs = [str(evidence_path.relative_to(data_dir))]

        if candidate_id not in existing_ids:
            append_jsonl(paths["candidates"], candidate)
            existing_ids.add(candidate_id)
            intake_event = event_row(candidate_id, "intake", "none", "raw", [], evidence_refs, "Candidate ingested.", week)
            append_jsonl(paths["events"], intake_event)
            events_written.append(intake_event)
            from_status = "raw"
        else:
            from_status = statuses.get(candidate_id, "raw")
            duplicate_reason = "identity-alias-merged" if alias_merged else "duplicate-observed"
            duplicate_event = event_row(
                candidate_id,
                "intake",
                from_status,
                from_status,
                [duplicate_reason],
                evidence_refs,
                "Candidate already exists in ledger; raw observation appended.",
                week,
            )
            append_jsonl(paths["events"], duplicate_event)
            events_written.append(duplicate_event)

        added_aliases = append_new_aliases(paths["identity_aliases"], candidate, aliases)
        if added_aliases:
            alias_event = event_row(
                candidate_id,
                "identity-alias",
                from_status,
                from_status,
                ["identity-alias-added"],
                evidence_refs,
                f"Added aliases: {', '.join(added_aliases)}",
                week,
            )
            append_jsonl(paths["events"], alias_event)
            events_written.append(alias_event)

        proposed_status, reason_codes, notes = deterministic_prefilter(candidate)
        to_status, transition_reasons, transition_notes = resolved_prefilter_transition(
            from_status,
            proposed_status,
            reason_codes,
        )
        reason_codes = sorted(set(reason_codes + transition_reasons))
        if transition_notes:
            notes = transition_notes
        prefilter_event = event_row(candidate_id, "deterministic-prefilter", from_status, to_status, reason_codes, evidence_refs, notes, week)
        append_jsonl(paths["events"], prefilter_event)
        events_written.append(prefilter_event)
        statuses[candidate_id] = to_status

    report_path = write_batch_report(data_dir, week)
    return {
        "input_count": len(raw_rows),
        "normalized_count": len(normalized_rows),
        "events_written": len(events_written),
        "report_path": str(report_path),
    }


def weak_layer_machine_reject_violations(events: list[dict[str, object]]) -> list[dict[str, object]]:
    violations: list[dict[str, object]] = []
    for event in events:
        layer = normalize_text(event.get("layer"))
        from_status = normalize_text(event.get("from_status"))
        to_status = normalize_text(event.get("to_status"))
        if to_status == "machine-reject" and from_status != "machine-reject" and layer != "deterministic-prefilter":
            violations.append(event)
    return violations


def label_candidates(data_dir: Path, week: str) -> dict[str, object]:
    paths = ensure_layout(data_dir, week)
    candidates = latest_candidates_for_week(data_dir, week)
    events = read_jsonl(paths["events"])
    statuses = status_by_candidate_for_week(events, week)
    reasons = reason_codes_by_candidate_for_week(events, week)
    labels_written = 0
    events_written = 0
    skipped_hard_gate_count = 0

    for candidate in candidates:
        candidate_id = normalize_text(candidate.get("candidate_id"))
        current_status = statuses.get(candidate_id, "raw")
        if current_status == "machine-reject":
            skipped_hard_gate_count += 1
            continue
        evidence_ref = f"ledger/evidence/{candidate_id}.md"
        label = weak_label_candidate(candidate, current_status, reasons.get(candidate_id, []), evidence_ref)
        label["week"] = week
        append_jsonl(paths["labels"], label)
        labels_written += 1

        proposed_status = normalize_text(label.get("status_recommendation"))
        label_reason_codes = label.get("reason_codes") if isinstance(label.get("reason_codes"), list) else []
        proposed_reasons = [normalize_text(reason) for reason in label_reason_codes if normalize_text(reason)]
        to_status, transition_reasons, transition_notes = resolved_weak_label_transition(
            current_status,
            proposed_status,
            proposed_reasons,
        )
        reason_codes = sorted(set(proposed_reasons + transition_reasons))
        label_summary = normalize_text(label.get("summary"))
        notes = transition_notes or f"Weak label triage recommendation: {proposed_status}. {label_summary}"
        event = event_row(
            candidate_id,
            "weak-label-triage",
            current_status,
            to_status,
            reason_codes,
            [evidence_ref, f"ledger/labels.jsonl#{label['label_id']}"],
            notes,
            week,
        )
        append_jsonl(paths["events"], event)
        events_written += 1
        statuses[candidate_id] = to_status

    updated_events = read_jsonl(paths["events"])
    violations = weak_layer_machine_reject_violations(updated_events)
    if violations:
        raise RuntimeError("Weak layer attempted to create a machine-reject status.")
    report_path = write_batch_report(data_dir, week)
    return {
        "candidate_count": len(candidates),
        "labels_written": labels_written,
        "events_written": events_written,
        "skipped_hard_gate_count": skipped_hard_gate_count,
        "report_path": str(report_path),
    }


def latest_row_by_candidate(rows: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    latest: dict[str, dict[str, object]] = {}
    for row in rows:
        candidate_id = normalize_text(row.get("candidate_id"))
        if candidate_id:
            latest[candidate_id] = row
    return latest


def latest_row_by_candidate_for_week(rows: list[dict[str, object]], week: str) -> dict[str, dict[str, object]]:
    return latest_row_by_candidate([row for row in rows if normalize_text(row.get("week")) == week])


def relative_path_label(data_dir: Path, path: Path) -> str:
    try:
        return str(path.relative_to(data_dir))
    except ValueError:
        return str(path)


def candidate_lookup(data_dir: Path, week: str, candidate_id: str) -> tuple[dict[str, object], str]:
    paths = ensure_layout(data_dir, week)
    candidates = latest_row_by_candidate(read_jsonl(paths["candidates"]))
    normalized_id = normalize_text(candidate_id)
    candidate = candidates.get(normalized_id)
    if not candidate:
        raise ValueError(f"Unknown candidate_id: {normalized_id}")
    statuses = status_by_candidate_for_week(read_jsonl(paths["events"]), week)
    return candidate, statuses.get(normalized_id, "raw")


def repo_digest_meta_path(paths: dict[str, Path], candidate_id: str) -> Path:
    return paths["repo_digests"] / normalize_text(candidate_id) / "digest-meta.json"


def repo_digest_artifact_path(paths: dict[str, Path], candidate_id: str) -> Path:
    return paths["repo_digests"] / normalize_text(candidate_id) / "digest.md"


def repo_digest_candidate_allowed(current_status: str, force: bool) -> bool:
    return force or normalize_text(current_status) in REPO_DIGEST_ALLOWED_STATUSES


def repo_digest_should_skip(path: Path) -> bool:
    return any(part in REPO_DIGEST_SKIP_DIRS for part in path.parts)


def repo_digest_is_text_file(path: Path) -> bool:
    if path.suffix.lower() in REPO_DIGEST_TEXT_EXTENSIONS:
        return True
    if not path.suffix and path.name in {"Dockerfile", "Makefile"}:
        return True
    return False


def repo_digest_source_files(source_path: Path, max_files: int) -> list[Path]:
    if source_path.is_file():
        return [source_path]
    files: list[Path] = []
    for path in sorted(source_path.rglob("*")):
        if len(files) >= max_files:
            break
        if not path.is_file() or path.is_symlink():
            continue
        if repo_digest_should_skip(path.relative_to(source_path)):
            continue
        if not repo_digest_is_text_file(path):
            continue
        files.append(path)
    return files


def read_digest_text(path: Path, byte_limit: int) -> tuple[str, int]:
    raw = path.read_bytes()[:byte_limit]
    text = raw.decode("utf-8", errors="replace")
    return text, len(raw)


def builtin_repo_digest(source_path: Path, output_path: Path, max_files: int, max_bytes: int) -> dict[str, object]:
    if not source_path.exists():
        raise ValueError(f"Digest source path does not exist: {source_path}")
    max_files = max(1, max_files)
    max_bytes = max(1, max_bytes)
    files = repo_digest_source_files(source_path, max_files)
    remaining = max_bytes
    total_bytes = 0
    sections = [
        "# Repository Digest",
        "",
        f"- Source label: `{source_path.name}`",
        f"- Max files: `{max_files}`",
        f"- Max bytes: `{max_bytes}`",
        "",
    ]
    included_count = 0
    for path in files:
        if remaining <= 0:
            break
        text, byte_count = read_digest_text(path, remaining)
        if source_path.is_file():
            label = path.name
        else:
            label = str(path.relative_to(source_path))
        sections.extend([f"## {label}", "", "```text", text.rstrip(), "```", ""])
        included_count += 1
        total_bytes += byte_count
        remaining -= byte_count
    digest_text = "\n".join(sections).rstrip() + "\n"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(digest_text, encoding="utf-8")
    return {
        "digest_bytes": len(digest_text.encode("utf-8")),
        "source_bytes_read": total_bytes,
        "included_file_count": included_count,
        "token_estimate": max(1, len(digest_text) // 4) if digest_text.strip() else 0,
        "truncated": len(files) >= max_files or remaining <= 0,
    }


def copy_digest_file(digest_file: Path, output_path: Path, max_bytes: int) -> dict[str, object]:
    if not digest_file.exists() or not digest_file.is_file():
        raise ValueError(f"Digest file does not exist: {digest_file}")
    text, byte_count = read_digest_text(digest_file, max(1, max_bytes))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")
    return {
        "digest_bytes": len(text.encode("utf-8")),
        "source_bytes_read": byte_count,
        "included_file_count": 1,
        "token_estimate": max(1, len(text) // 4) if text.strip() else 0,
        "truncated": byte_count >= max_bytes,
    }


def latest_repo_digest_meta(paths: dict[str, Path], candidate_id: str) -> dict[str, object]:
    meta_path = repo_digest_meta_path(paths, candidate_id)
    if not meta_path.exists():
        return {}
    parsed = json.loads(meta_path.read_text(encoding="utf-8"))
    return parsed if isinstance(parsed, dict) else {}


def attach_repo_digest_to_card(card: dict[str, object], paths: dict[str, Path], data_dir: Path) -> None:
    candidate_id = normalize_text(card.get("candidate_id"))
    meta = latest_repo_digest_meta(paths, candidate_id)
    if not meta:
        return
    ledger_links = card.get("ledger_links")
    if not isinstance(ledger_links, dict):
        ledger_links = {}
        card["ledger_links"] = ledger_links
    meta_path = repo_digest_meta_path(paths, candidate_id)
    ledger_links["repo_digest_meta"] = relative_path_label(data_dir, meta_path)
    digest_path = normalize_text(meta.get("digest_path"))
    card["repo_digest"] = {
        "status": normalize_text(meta.get("status")) or "unknown",
        "tool": normalize_text(meta.get("tool")) or "unknown",
        "tool_version": normalize_text(meta.get("tool_version")) or "unknown",
        "digest_path": digest_path,
        "digest_bytes": meta.get("digest_bytes"),
        "token_estimate": meta.get("token_estimate"),
        "included_file_count": meta.get("included_file_count"),
    }


def run_repo_digest(
    data_dir: Path,
    week: str,
    candidate_id: str,
    source_path: Path | None,
    digest_file: Path | None,
    tool: str,
    tool_version: str,
    max_files: int,
    max_bytes: int,
    force: bool,
) -> dict[str, object]:
    paths = ensure_layout(data_dir, week)
    candidate, current_status = candidate_lookup(data_dir, week, candidate_id)
    normalized_id = normalize_text(candidate.get("candidate_id"))
    if not repo_digest_candidate_allowed(current_status, force):
        raise ValueError(
            f"Candidate {normalized_id} has status {current_status}; use --force to digest non-serious candidates."
        )
    if source_path is None and digest_file is None:
        raise ValueError("repo-digest requires --source-path or --digest-file")

    artifact_path = repo_digest_artifact_path(paths, normalized_id)
    if digest_file is not None:
        digest_stats = copy_digest_file(digest_file, artifact_path, max_bytes)
        source_label = digest_file.name
        source_kind = "digest-file"
    else:
        resolved_source = source_path if source_path is not None else Path(".")
        digest_stats = builtin_repo_digest(resolved_source, artifact_path, max_files, max_bytes)
        source_label = resolved_source.name
        source_kind = "source-path"

    meta_path = repo_digest_meta_path(paths, normalized_id)
    meta: dict[str, object] = {
        "digest_id": f"digest_{uuid.uuid4().hex}",
        "candidate_id": normalized_id,
        "week": week,
        "created_at": utc_now(),
        "status": "ok",
        "tool": normalize_text(tool) or "builtin",
        "tool_version": normalize_text(tool_version) or "unknown",
        "source_kind": source_kind,
        "source_label": source_label,
        "source_repo_url": normalize_text(candidate.get("project_url")),
        "repository": normalize_text(candidate.get("repository")),
        "digest_path": relative_path_label(data_dir, artifact_path),
        "meta_path": relative_path_label(data_dir, meta_path),
        "max_files": max_files,
        "max_bytes": max_bytes,
        "forced": force,
    }
    meta.update(digest_stats)
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(meta, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    append_jsonl(paths["repo_digest_meta"], meta)
    append_jsonl(
        paths["events"],
        event_row(
            normalized_id,
            "repo-digest",
            current_status,
            current_status,
            ["repo-digest-written"],
            [relative_path_label(data_dir, meta_path), relative_path_label(data_dir, artifact_path)],
            "Shortlist repository digest metadata captured.",
            week,
        ),
    )
    return {
        "candidate_id": normalized_id,
        "status": "ok",
        "meta_path": str(meta_path),
        "digest_path": str(artifact_path),
        "digest_bytes": meta.get("digest_bytes"),
        "token_estimate": meta.get("token_estimate"),
    }


def repo_digest_status_priority(status: str) -> int:
    normalized = normalize_text(status)
    priorities = {
        "operator-proof-approved": 0,
        "proof-card": 1,
        "PRD-lite": 2,
        "watchlist": 3,
        "watchlist-candidate": 4,
        "codex-review": 5,
        "proof-card-candidate": 6,
    }
    return priorities.get(normalized, 99)


def repo_digest_clone_url(candidate: dict[str, object]) -> str:
    full_name = github_full_name_from_candidate(candidate)
    if not full_name:
        return ""
    return f"https://github.com/{full_name}.git"


def repo_digest_batch_candidates(
    paths: dict[str, Path],
    week: str,
    max_candidates: int,
    force: bool,
) -> list[tuple[dict[str, object], str]]:
    if max_candidates <= 0:
        return []
    candidates = latest_row_by_candidate(read_jsonl(paths["candidates"]))
    statuses = status_by_candidate_for_week(read_jsonl(paths["events"]), week)
    selected: list[tuple[int, str, dict[str, object], str]] = []
    for candidate in candidates.values():
        candidate_id = normalize_text(candidate.get("candidate_id"))
        if not candidate_id:
            continue
        current_status = statuses.get(candidate_id, "raw")
        if not repo_digest_candidate_allowed(current_status, force):
            continue
        if not repo_digest_clone_url(candidate):
            continue
        if not force and latest_repo_digest_meta(paths, candidate_id):
            continue
        selected.append((repo_digest_status_priority(current_status), candidate_id, candidate, current_status))
    selected.sort(key=lambda item: (item[0], item[1]))
    return [(candidate, status) for _, _, candidate, status in selected[:max_candidates]]


def git_clone_shallow(url: str, target_path: Path, timeout_seconds: int) -> None:
    completed = subprocess.run(
        ["git", "clone", "--depth", "1", "--single-branch", url, str(target_path)],
        text=True,
        capture_output=True,
        check=False,
        timeout=max(1, timeout_seconds),
    )
    if completed.returncode != 0:
        stderr = truncate_text(completed.stderr or completed.stdout or "git clone failed", 600)
        raise ValueError(stderr)


def run_repo_digest_batch(
    data_dir: Path,
    week: str,
    max_candidates: int,
    max_files: int,
    max_bytes: int,
    clone_timeout_seconds: int,
    force: bool,
    dry_run: bool,
    clone_runner: Callable[[str, Path, int], None] | None = None,
) -> dict[str, object]:
    paths = ensure_layout(data_dir, week)
    selected = repo_digest_batch_candidates(paths, week, max_candidates, force)
    clone = clone_runner if clone_runner is not None else git_clone_shallow
    results: list[dict[str, object]] = []
    digested_count = 0
    failed_count = 0
    would_digest_count = 0
    for candidate, current_status in selected:
        candidate_id = normalize_text(candidate.get("candidate_id"))
        clone_url = repo_digest_clone_url(candidate)
        base_result: dict[str, object] = {
            "candidate_id": candidate_id,
            "repository": github_full_name_from_candidate(candidate),
            "source_status": current_status,
            "clone_url": clone_url,
        }
        if dry_run:
            preview = dict(base_result)
            preview["status"] = "would-digest"
            results.append(preview)
            would_digest_count += 1
            continue
        try:
            with tempfile.TemporaryDirectory(prefix=f"repo-digest-{candidate_id}-") as tmp_dir:
                checkout_path = Path(tmp_dir) / "repo"
                clone(clone_url, checkout_path, clone_timeout_seconds)
                digest_result = run_repo_digest(
                    data_dir=data_dir,
                    week=week,
                    candidate_id=candidate_id,
                    source_path=checkout_path,
                    digest_file=None,
                    tool="builtin",
                    tool_version="autonomous-batch",
                    max_files=max_files,
                    max_bytes=max_bytes,
                    force=force,
                )
            merged = dict(base_result)
            merged.update(digest_result)
            results.append(merged)
            digested_count += 1
        except Exception as error:
            failed = dict(base_result)
            failed["status"] = "failed"
            failed["error"] = truncate_text(str(error), 600)
            results.append(failed)
            failed_count += 1
    skipped_count = len(selected) - digested_count - failed_count - would_digest_count
    return {
        "candidate_count": len(selected),
        "digested_count": digested_count,
        "failed_count": failed_count,
        "skipped_count": max(0, skipped_count),
        "would_digest_count": would_digest_count,
        "dry_run": dry_run,
        "results": results,
    }


def read_json_records(path: Path) -> list[dict[str, object]]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    if text.startswith("["):
        parsed = json.loads(text)
        if not isinstance(parsed, list):
            raise ValueError(f"JSON record file must be a list or JSONL: {path}")
        return [item for item in parsed if isinstance(item, dict)]
    rows: list[dict[str, object]] = []
    for line_number, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if not stripped:
            continue
        parsed = json.loads(stripped)
        if not isinstance(parsed, dict):
            raise ValueError(f"JSONL row must be an object at {path}:{line_number}")
        rows.append(parsed)
    return rows


def gh_archive_repo_name(event: dict[str, object]) -> str:
    repo = safe_dict(event.get("repo"))
    return github_full_name(repo.get("name"))


def gh_archive_event_excerpt(event: dict[str, object]) -> str:
    payload = safe_dict(event.get("payload"))
    issue = safe_dict(payload.get("issue"))
    pull_request = safe_dict(payload.get("pull_request"))
    comment = safe_dict(payload.get("comment"))
    title = normalize_text(issue.get("title")) or normalize_text(pull_request.get("title"))
    body = normalize_text(issue.get("body")) or normalize_text(pull_request.get("body")) or normalize_text(comment.get("body"))
    url = normalize_text(issue.get("html_url")) or normalize_text(pull_request.get("html_url")) or normalize_text(comment.get("html_url"))
    event_type = normalize_text(event.get("type")) or "unknown"
    created_at = normalize_text(event.get("created_at"))
    parts = [event_type]
    if title:
        parts.append(truncate_text(title, 160))
    if body:
        parts.append(truncate_text(body, 280))
    if created_at:
        parts.append(f"created_at={created_at}")
    if url:
        parts.append(url)
    return " | ".join(parts)


def gh_archive_candidate_from_bucket(repo_name: str, bucket: dict[str, object], source_label: str) -> dict[str, object]:
    event_counts = safe_dict(bucket.get("event_counts"))
    issue_excerpts = [normalize_text(item) for item in safe_list(bucket.get("issue_excerpts")) if normalize_text(item)]
    text_blob = "\n".join(issue_excerpts)
    lanes = {
        "active_abandoned_forks": False,
        "cli_to_ui_gap": any(term in text_blob.lower() for term in ("dashboard", "ui", "hosted")),
        "commercial_intent_density": any(term in text_blob.lower() for term in MONEY_TERMS),
        "academic_hobbyist_bias": False,
        "demand_pain_cluster": any(term in text_blob.lower() for term in HN_PAIN_PATTERNS + PAIN_TERMS),
    }
    project_url = f"https://github.com/{repo_name}"
    candidate = {
        "source": "gh-archive-momentum",
        "source_url": GH_ARCHIVE_ATTRIBUTION_URL,
        "project_url": project_url,
        "project_name": repo_name,
        "repository": repo_name,
        "license": "unknown",
        "short_description": f"Public GitHub event momentum for {repo_name}.",
        "raw_metadata": {
            "provider": "gh-archive",
            "repo_name": repo_name,
            "repo_key": normalize_repo_key(repo_name),
            "fork_family_key": normalize_repo_key(repo_name),
            "event_count": bucket.get("event_count"),
            "event_counts": event_counts,
            "last_event_at": normalize_text(bucket.get("last_event_at")),
            "collection": {
                "api_surface": "gh-archive-fixture",
                "visibility": "public",
                "auth_required": False,
                "raw_events_stored": False,
                "source_label": source_label,
            },
        },
        "raw_text": {
            "readme_excerpt": "",
            "issue_excerpts": issue_excerpts,
            "discussion_excerpts": [],
            "marketplace_or_store_text": "",
            "external_mentions": [f"gh_archive_event_count={bucket.get('event_count')}"],
        },
        "search_lanes": lanes,
        "collector_notes": "Collected from public GH Archive-style events; raw event exhaust is not stored in candidate rows.",
    }
    return normalize_candidate(candidate, utc_now())


def collect_gh_archive_momentum(
    input_path: Path,
    max_events: int,
    max_repos: int,
    min_events: int,
    issue_excerpts_per_repo: int,
) -> list[dict[str, object]]:
    buckets: dict[str, dict[str, object]] = {}
    records = read_json_records(input_path)
    for event in records[: max(0, max_events)]:
        repo_name = gh_archive_repo_name(event)
        if not repo_name:
            continue
        bucket = buckets.setdefault(repo_name, {"event_count": 0, "event_counts": {}, "issue_excerpts": [], "last_event_at": ""})
        bucket["event_count"] = int(bucket.get("event_count", 0)) + 1
        event_type = normalize_text(event.get("type")) or "unknown"
        event_counts = safe_dict(bucket.get("event_counts"))
        event_counts[event_type] = int(event_counts.get(event_type, 0)) + 1
        bucket["event_counts"] = event_counts
        created_at = normalize_text(event.get("created_at"))
        if created_at > normalize_text(bucket.get("last_event_at")):
            bucket["last_event_at"] = created_at
        excerpts = bucket.get("issue_excerpts")
        if isinstance(excerpts, list) and len(excerpts) < issue_excerpts_per_repo:
            excerpt = gh_archive_event_excerpt(event)
            if excerpt:
                excerpts.append(excerpt)
    ranked = sorted(buckets.items(), key=lambda item: int(item[1].get("event_count", 0)), reverse=True)
    candidates: list[dict[str, object]] = []
    for repo_name, bucket in ranked:
        if len(candidates) >= max_repos:
            break
        if int(bucket.get("event_count", 0)) < min_events:
            continue
        candidates.append(gh_archive_candidate_from_bucket(repo_name, bucket, input_path.name))
    return candidates


def run_gh_archive_momentum(
    data_dir: Path,
    week: str,
    input_path: Path,
    output_path: Path,
    max_events: int,
    max_repos: int,
    min_events: int,
    issue_excerpts_per_repo: int,
    ingest: bool,
) -> dict[str, object]:
    ensure_layout(data_dir, week)
    candidates = collect_gh_archive_momentum(
        input_path=input_path,
        max_events=max_events,
        max_repos=max_repos,
        min_events=min_events,
        issue_excerpts_per_repo=issue_excerpts_per_repo,
    )
    write_jsonl(output_path, candidates)
    result: dict[str, object] = {
        "collection": {
            "source": "gh-archive-momentum",
            "input_path": str(input_path),
            "output_path": str(output_path),
            "candidate_count": len(candidates),
            "max_events": max_events,
            "max_repos": max_repos,
            "min_events": min_events,
        }
    }
    if ingest and candidates:
        result["ingest"] = ingest_candidates(output_path, data_dir, week)
    return result


class EcosystemsApiError(RuntimeError):
    pass


class EcosystemsApiClient:
    def __init__(self, api_base: str, timeout: int) -> None:
        self.api_base = api_base.rstrip("/")
        self.timeout = timeout

    def get_json(self, path: str, params: dict[str, object]) -> object:
        query = urllib.parse.urlencode({key: value for key, value in params.items() if value not in ("", None)})
        url = f"{self.api_base}{path}"
        if query:
            url = f"{url}?{query}"
        request = urllib.request.Request(url, headers={"User-Agent": "opportunity-scanner-local"})
        response = None
        try:
            response = urllib.request.urlopen(request, timeout=self.timeout)
            raw_body = response.read().decode("utf-8")
            if not raw_body:
                return {}
            return json.loads(raw_body)
        except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError):
            raise EcosystemsApiError("ecosyste.ms API request failed")
        finally:
            if response is not None:
                response.close()


def github_full_name_from_candidate(candidate: dict[str, object]) -> str:
    repository = github_full_name(candidate.get("repository"))
    if repository and len(repository.split("/")) == 2:
        return repository
    repo_key = normalize_repo_key(candidate.get("repo_key") or candidate.get("project_url"))
    parts = repo_key.split("/")
    if len(parts) >= 3 and parts[0] == "github.com":
        return f"{parts[1]}/{parts[2]}"
    return ""


def ecosystems_fixture_map(path: Path | None) -> dict[str, dict[str, object]]:
    if path is None:
        return {}
    records = read_json_records(path)
    mapped: dict[str, dict[str, object]] = {}
    for record in records:
        full_name = github_full_name(record.get("full_name"))
        if full_name:
            mapped[full_name.lower()] = record
    if len(records) == 1 and records[0]:
        mapped.setdefault("__single__", records[0])
    return mapped


def ecosystems_payload_for_candidate(
    client: EcosystemsApiClient,
    candidate: dict[str, object],
    fixture_rows: dict[str, dict[str, object]],
) -> tuple[dict[str, object], str]:
    full_name = github_full_name_from_candidate(candidate)
    if not full_name:
        return {}, ""
    fixture = fixture_rows.get(full_name.lower()) or fixture_rows.get("__single__")
    api_path = f"/hosts/GitHub/repositories/{urllib.parse.quote(full_name, safe='')}"
    if fixture_rows:
        return fixture, api_path
    payload = client.get_json(api_path, {})
    return payload if isinstance(payload, dict) else {}, api_path


def ecosystems_derived_fields(payload: dict[str, object]) -> dict[str, object]:
    topics = [normalize_text(topic) for topic in safe_list(payload.get("topics")) if normalize_text(topic)]
    metadata = safe_dict(payload.get("metadata"))
    files = safe_dict(metadata.get("files"))
    return {
        "full_name": github_full_name(payload.get("full_name")),
        "description": truncate_text(payload.get("description"), 500),
        "license": normalize_text(payload.get("license")),
        "language": normalize_text(payload.get("language")),
        "topics": topics[:20],
        "archived": bool(payload.get("archived")),
        "fork": bool(payload.get("fork")),
        "stargazers_count": payload.get("stargazers_count"),
        "forks_count": payload.get("forks_count"),
        "open_issues_count": payload.get("open_issues_count"),
        "pushed_at": normalize_text(payload.get("pushed_at")),
        "last_synced_at": normalize_text(payload.get("last_synced_at")),
        "homepage": normalize_url(payload.get("homepage")),
        "metadata_files": {
            "readme": normalize_text(files.get("readme")),
            "changelog": normalize_text(files.get("changelog")),
            "license": normalize_text(files.get("license")),
            "contributing": normalize_text(files.get("contributing")),
        },
    }


def latest_ecosystems_enrichment(paths: dict[str, Path], candidate_id: str, week: str) -> dict[str, object]:
    rows = [
        row
        for row in read_jsonl(paths["ecosystems_enrichments"])
        if normalize_text(row.get("candidate_id")) == candidate_id and normalize_text(row.get("week")) == week
    ]
    return rows[-1] if rows else {}


def attach_ecosystems_to_card(card: dict[str, object], paths: dict[str, Path]) -> None:
    candidate_id = normalize_text(card.get("candidate_id"))
    week = normalize_text(card.get("week"))
    enrichment = latest_ecosystems_enrichment(paths, candidate_id, week)
    if not enrichment:
        return
    card["external_enrichment"] = {
        "source": "ecosyste.ms",
        "data_license": ECOSYSTEMS_DATA_LICENSE,
        "repository": normalize_text(enrichment.get("repository")),
        "fields": enrichment.get("derived_fields") if isinstance(enrichment.get("derived_fields"), dict) else {},
    }


def attach_external_context_to_card(card: dict[str, object], paths: dict[str, Path], data_dir: Path) -> None:
    attach_repo_digest_to_card(card, paths, data_dir)
    attach_ecosystems_to_card(card, paths)


def run_ecosystems_enrich(
    data_dir: Path,
    week: str,
    candidate_id: str,
    fixture_path: Path | None,
    max_candidates: int,
    api_base: str,
    dry_run: bool,
) -> dict[str, object]:
    paths = ensure_layout(data_dir, week)
    candidates = latest_row_by_candidate(read_jsonl(paths["candidates"]))
    statuses = status_by_candidate_for_week(read_jsonl(paths["events"]), week)
    selected: list[dict[str, object]] = []
    normalized_id = normalize_text(candidate_id)
    if normalized_id:
        candidate = candidates.get(normalized_id)
        if not candidate:
            raise ValueError(f"Unknown candidate_id: {normalized_id}")
        selected = [candidate]
    else:
        for candidate in candidates.values():
            if len(selected) >= max(0, max_candidates):
                break
            if github_full_name_from_candidate(candidate):
                selected.append(candidate)

    fixture_rows = ecosystems_fixture_map(fixture_path)
    client = EcosystemsApiClient(api_base, HTTP_TIMEOUT_SECONDS)
    written = 0
    rows: list[dict[str, object]] = []
    for candidate in selected:
        current_id = normalize_text(candidate.get("candidate_id"))
        payload, api_path = ecosystems_payload_for_candidate(client, candidate, fixture_rows)
        if not payload or normalize_text(payload.get("error")):
            continue
        repository = github_full_name(payload.get("full_name")) or github_full_name_from_candidate(candidate)
        row = {
            "enrichment_id": f"eco_{uuid.uuid4().hex}",
            "candidate_id": current_id,
            "week": week,
            "created_at": utc_now(),
            "source": "ecosyste.ms",
            "source_url": f"{api_base.rstrip('/')}{api_path}",
            "attribution_url": ECOSYSTEMS_ATTRIBUTION_URL,
            "data_license": ECOSYSTEMS_DATA_LICENSE,
            "repository": repository,
            "status": "ok",
            "derived_fields": ecosystems_derived_fields(payload),
            "raw_response_stored": False,
        }
        rows.append(row)
        if dry_run:
            continue
        append_jsonl(paths["ecosystems_enrichments"], row)
        append_jsonl(
            paths["events"],
            event_row(
                current_id,
                "ecosystems-enrich",
                statuses.get(current_id, "raw"),
                statuses.get(current_id, "raw"),
                ["ecosystems-enrichment-captured"],
                ["ledger/ecosystems_enrichments.jsonl"],
                "Small attributed ecosyste.ms derived metadata captured.",
                week,
            ),
        )
        written += 1
    return {
        "candidate_count": len(selected),
        "enrichment_count": len(rows),
        "written_count": written,
        "dry_run": dry_run,
    }


def field_value(label: dict[str, object], field_name: str) -> str:
    inferred_fields = label.get("inferred_fields")
    if not isinstance(inferred_fields, dict):
        return "unknown"
    field_payload = inferred_fields.get(field_name)
    if isinstance(field_payload, dict):
        return normalize_text(field_payload.get("value")) or "unknown"
    return normalize_text(field_payload) or "unknown"


def label_list(label: dict[str, object], field_name: str) -> list[str]:
    value = label.get(field_name)
    if not isinstance(value, list):
        return []
    return [normalize_text(item) for item in value if normalize_text(item)]


def has_known_values(values: list[str]) -> bool:
    return any(value and value != "unknown" for value in values)


def missing_high_count(label: dict[str, object]) -> int:
    missing = label.get("missing_evidence")
    if not isinstance(missing, list):
        return 0
    count = 0
    for item in missing:
        if isinstance(item, dict) and normalize_text(item.get("severity")) == "high":
            count += 1
    return count


def proof_blocking_missing_count(label: dict[str, object]) -> int:
    missing = label.get("missing_evidence")
    if not isinstance(missing, list):
        return 0
    count = 0
    for item in missing:
        if not isinstance(item, dict):
            continue
        blocking_for = item.get("blocking_for") if isinstance(item.get("blocking_for"), list) else []
        if "proof-card" in [normalize_text(value) for value in blocking_for]:
            count += 1
    return count


def is_known_text(value: object) -> bool:
    text = normalize_text(value).lower()
    return bool(text) and text not in {"unknown", "none", "n/a", "null"}


def known_label_list(label: dict[str, object], field_name: str) -> list[str]:
    return [value for value in label_list(label, field_name) if is_known_text(value)]


def raw_metadata_value(candidate: dict[str, object], key: str) -> str:
    raw_metadata = candidate.get("raw_metadata")
    if not isinstance(raw_metadata, dict):
        return ""
    return normalize_text(raw_metadata.get(key))


def has_candidate_cost_cap(candidate: dict[str, object]) -> bool:
    return any(
        is_known_text(raw_metadata_value(candidate, key))
        for key in ("preview_cost_cap", "failed_job_cost_cap", "compute_cost_cap", "storage_cost_cap")
    )


def has_sensitive_or_regulated_risk(candidate: dict[str, object], label: dict[str, object]) -> bool:
    text = all_candidate_text(candidate).lower()
    risk_hints = set(known_label_list(label, "risk_hints"))
    regulated_terms = (
        "medical",
        "health",
        "legal",
        "lawyer",
        "finance",
        "financial",
        "investment",
        "trading",
        "compliance",
        "tax",
        "diagnosis",
    )
    return bool(risk_hints.intersection({"external-api-dependence-check-needed", "brand-copy-risk"})) or any(
        term in text for term in regulated_terms
    )


def clean_license_score(candidate: dict[str, object], label: dict[str, object]) -> tuple[int, str]:
    license_value = (field_value(label, "legal_license") or normalize_text(candidate.get("license"))).lower()
    risk_hints = set(known_label_list(label, "risk_hints"))
    if not is_known_text(license_value) or "unknown-license" in risk_hints:
        return 0, "license or rights are unknown"
    if "agpl" in license_value or "gpl" in license_value:
        return 0, "GPL/AGPL/server-side license risk"
    if "brand-copy-risk" in risk_hints:
        return 1, "license is known but brand/copy risk needs review"
    return 2, "license is known and no rights veto is visible"


def scorecard_band(total: int) -> str:
    if total >= STRICT_PROOF_CARD_MIN:
        return "proof-card"
    if total >= STRICT_CHALLENGER_MIN:
        return "challenger"
    if total >= STRICT_WATCHLIST_MIN:
        return "watchlist"
    return "park"


def scorecard_item(
    key: str,
    label: str,
    score: int,
    rationale: str,
    evidence: list[str] | None = None,
) -> dict[str, object]:
    return {
        "key": key,
        "label": label,
        "score": max(0, min(score, 2)),
        "rationale": rationale,
        "evidence": evidence or [],
    }


def strict_scorecard(candidate: dict[str, object], label: dict[str, object]) -> dict[str, object]:
    text = all_candidate_text(candidate).lower()
    pain_phrases = known_label_list(label, "pain_phrases")
    money_signals = known_label_list(label, "money_signals")
    active_lanes = active_lane_codes(candidate)
    buyer = field_value(label, "target_buyer")
    painful_job = field_value(label, "painful_job")
    distribution = field_value(label, "distribution_channel")
    support = field_value(label, "support_load").lower()
    product_angle = field_value(label, "product_angle")
    demo_or_proof = field_value(label, "demo_or_proof")
    clean_rights_score, clean_rights_rationale = clean_license_score(candidate, label)
    cost_cap_known = has_candidate_cost_cap(candidate)
    narrow_angles = {"web dashboard", "hosted version", "one-click deploy", "telegram bot", "discord bot", "browser extension"}
    recurring_terms = ("recurring", "monitoring", "alerts", "weekly", "monthly", "dashboard", "reports", "exports", "support")
    exact_distribution_terms = ("marketplace", "store", "directory", "search query", "first 100", "prospects", "buyers")
    api_or_platform_risk = "external-api-dependence-check-needed" in known_label_list(label, "risk_hints")

    items = [
        scorecard_item(
            "pain_urgency",
            "Urgent recurring pain",
            2 if len(pain_phrases) >= 2 else 1 if pain_phrases else 0,
            "repeated pain is visible" if len(pain_phrases) >= 2 else "some pain is visible" if pain_phrases else "no pain evidence",
            pain_phrases[:2],
        ),
        scorecard_item(
            "result_clarity",
            "Clear buyer-visible result",
            2 if is_known_text(product_angle) and is_known_text(painful_job) else 1 if is_known_text(product_angle) else 0,
            "result and job are visible" if is_known_text(product_angle) and is_known_text(painful_job) else "result is partial" if is_known_text(product_angle) else "result is unclear",
            [product_angle] if is_known_text(product_angle) else [],
        ),
        scorecard_item(
            "one_function",
            "One small function",
            2 if product_angle in narrow_angles else 1 if is_known_text(product_angle) else 0,
            "angle looks like one narrow surface" if product_angle in narrow_angles else "angle exists but may be broad" if is_known_text(product_angle) else "no narrow wedge",
            [product_angle] if is_known_text(product_angle) else [],
        ),
        scorecard_item(
            "demand_proof",
            "Demand proof",
            2 if pain_phrases and money_signals else 1 if pain_phrases or active_lanes else 0,
            "pain and money signals both exist" if pain_phrases and money_signals else "demand signal is partial" if pain_phrases or active_lanes else "no demand proof",
            (pain_phrases[:1] + money_signals[:2]),
        ),
        scorecard_item(
            "no_call_revenue",
            "No-call revenue path",
            2 if money_signals and is_known_text(distribution) and not has_sensitive_or_regulated_risk(candidate, label) else 1 if money_signals else 0,
            "money and a candidate async lane exist" if money_signals and is_known_text(distribution) else "money words exist but path is not proven" if money_signals else "no revenue path",
            money_signals[:3],
        ),
        scorecard_item(
            "online_reachability",
            "Online reachability",
            2 if is_known_text(distribution) and any(term in distribution.lower() for term in exact_distribution_terms) else 1 if active_lanes else 0,
            "first-100 channel is specific" if is_known_text(distribution) and any(term in distribution.lower() for term in exact_distribution_terms) else "only generic source lane is visible" if active_lanes else "no online reachability proof",
            active_lanes,
        ),
        scorecard_item(
            "speed_to_first_money",
            "Speed to first money",
            2 if money_signals and is_known_text(demo_or_proof) else 1 if money_signals and is_known_text(product_angle) else 0,
            "money signal and proof surface exist" if money_signals and is_known_text(demo_or_proof) else "money signal exists but proof path is weak" if money_signals else "no first-money path",
            money_signals[:2],
        ),
        scorecard_item(
            "cheap_7_day_proof",
            "Cheap seven-day proof",
            2 if cost_cap_known and is_known_text(demo_or_proof) else 1 if is_known_text(demo_or_proof) else 0,
            "cost cap and proof surface are known" if cost_cap_known and is_known_text(demo_or_proof) else "proof surface exists but cost cap is unknown" if is_known_text(demo_or_proof) else "proof path is unknown",
            [demo_or_proof] if is_known_text(demo_or_proof) else [],
        ),
        scorecard_item(
            "automated_fulfillment",
            "Automated fulfillment",
            2 if product_angle in {"template", "one-click deploy", "browser extension"} else 1 if product_angle in narrow_angles else 0,
            "fulfillment looks productized" if product_angle in {"template", "one-click deploy", "browser extension"} else "may be automatable but unproven" if product_angle in narrow_angles else "fulfillment unclear",
            [product_angle] if is_known_text(product_angle) else [],
        ),
        scorecard_item(
            "repeatability",
            "Repeatability",
            2 if any(term in text for term in recurring_terms) and (pain_phrases or money_signals) else 1 if pain_phrases or money_signals else 0,
            "recurring workflow language is visible" if any(term in text for term in recurring_terms) else "repeat use is not proven" if pain_phrases or money_signals else "no repeatability signal",
            snippets_with_terms(candidate, recurring_terms, 2),
        ),
        scorecard_item(
            "manual_work_scaling",
            "Scales without proportional manual work",
            2 if support == "low" and product_angle in narrow_angles else 1 if support in {"low", "medium"} else 0,
            "support looks bounded" if support in {"low", "medium"} else "support load is unknown",
            [support] if is_known_text(support) else [],
        ),
        scorecard_item(
            "downside_cap",
            "Limited downside",
            2 if cost_cap_known and not has_sensitive_or_regulated_risk(candidate, label) else 1 if cost_cap_known else 0,
            "cost and risk caps are visible" if cost_cap_known else "preview/failed-job cost cap is unknown",
            [],
        ),
        scorecard_item(
            "rights_tos_clean",
            "Clean rights and ToS",
            clean_rights_score,
            clean_rights_rationale,
            [field_value(label, "legal_license")],
        ),
        scorecard_item(
            "platform_resilience",
            "Platform resilience",
            0 if api_or_platform_risk else 1 if clean_rights_score > 0 and product_angle in narrow_angles else 0,
            "platform/API dependency needs review" if api_or_platform_risk else "some value may remain outside a single platform" if clean_rights_score > 0 and product_angle in narrow_angles else "platform resilience is unknown",
            [],
        ),
        scorecard_item(
            "unit_economics",
            "Unit economics",
            2 if cost_cap_known and money_signals else 1 if cost_cap_known else 0,
            "cost cap and money signal exist" if cost_cap_known and money_signals else "unit economics unknown",
            money_signals[:2],
        ),
        scorecard_item(
            "support_simplicity",
            "Simple support",
            2 if support == "low" else 1 if support == "medium" else 0,
            "support appears simple" if support == "low" else "support may be manageable" if support == "medium" else "support is unknown",
            [support] if is_known_text(support) else [],
        ),
        scorecard_item(
            "proof_quality",
            "Proof quality",
            2 if "paid" in money_signals or "pricing" in money_signals else 1 if money_signals else 0,
            "pricing/paid language exists" if "paid" in money_signals or "pricing" in money_signals else "only weak money language exists" if money_signals else "no hard proof signal",
            money_signals[:3],
        ),
    ]
    total = sum(int(item["score"]) for item in items)
    blockers = [item["key"] for item in items if int(item["score"]) == 0]
    return {
        "version": "filter-v3",
        "total": total,
        "max": len(STRICT_SCORECARD_ITEMS) * 2,
        "band": scorecard_band(total),
        "items": items,
        "zero_score_items": blockers,
    }


def score_from_signal(has_signal: bool, strong_signal: bool) -> int:
    if strong_signal:
        return 5
    if has_signal:
        return 3
    return 1


def opportunity_scores(candidate: dict[str, object], label: dict[str, object]) -> dict[str, object]:
    pain_phrases = label_list(label, "pain_phrases")
    money_signals = [value for value in label_list(label, "money_signals") if value != "unknown"]
    buyer = field_value(label, "target_buyer")
    distribution = field_value(label, "distribution_channel")
    support = field_value(label, "support_load")
    license_value = field_value(label, "legal_license")
    product_angle = field_value(label, "product_angle")
    risk_hints = label_list(label, "risk_hints")
    high_missing = missing_high_count(label)
    proof_blocking_missing = proof_blocking_missing_count(label)
    strict = strict_scorecard(candidate, label)
    scores = {
        "pain": score_from_signal(bool(pain_phrases), len(pain_phrases) >= 2),
        "monetization": score_from_signal(bool(money_signals), len(money_signals) >= 2),
        "buyer": score_from_signal(buyer != "unknown", buyer != "unknown" and len(pain_phrases) >= 1),
        "distribution": score_from_signal(distribution != "unknown", bool(active_lane_codes(candidate))),
        "buildability": score_from_signal(product_angle != "unknown", product_angle in {"web dashboard", "hosted version", "one-click deploy"}),
        "support": 2 if support == "unknown" else 4,
        "legal_risk": 2 if license_value == "unknown" or "brand-copy-risk" in risk_hints else 4,
        "missing_high": high_missing,
        "missing_proof_blocking": proof_blocking_missing,
        "strict_scorecard_total": strict["total"],
        "strict_scorecard_band": strict["band"],
    }
    numeric_total = 0
    for key, value in scores.items():
        if isinstance(value, int) and not key.startswith("missing_") and key != "strict_scorecard_total":
            numeric_total += value
    scores["total"] = numeric_total
    return scores


def opportunity_verdict(candidate: dict[str, object], label: dict[str, object], current_status: str) -> tuple[str, list[str], str]:
    scores = opportunity_scores(candidate, label)
    pain_phrases = label_list(label, "pain_phrases")
    money_signals = [value for value in label_list(label, "money_signals") if value != "unknown"]
    risk_hints = label_list(label, "risk_hints")
    high_missing = int(scores.get("missing_high", 0))
    proof_blocking_missing = int(scores.get("missing_proof_blocking", 0))
    strict_total = int(scores.get("strict_scorecard_total", 0))
    strict_band = normalize_text(scores.get("strict_scorecard_band")) or "park"
    reason_codes: list[str] = []
    if not money_signals:
        reason_codes.append("missing-money-signal")
    if not pain_phrases:
        reason_codes.append("missing-pain-signal")
    if high_missing:
        reason_codes.append("high-missing-evidence")
    if proof_blocking_missing:
        reason_codes.append("proof-card-blocked-by-missing-evidence")
    if "unknown-license" in risk_hints:
        return "park", sorted(set(reason_codes + ["license-unknown"])), "License is unknown; park until rights are clear."
    if "brand-copy-risk" in risk_hints:
        reason_codes.append("brand-copy-risk-review")
    reason_codes.append(f"strict-score-{strict_band}")
    if (
        current_status == "watchlist-candidate"
        and money_signals
        and pain_phrases
        and high_missing == 0
        and proof_blocking_missing == 0
        and strict_total >= STRICT_PROOF_CARD_MIN
    ):
        return "proof-card", sorted(set(reason_codes + ["proof-card-ready"])), f"Strict scorecard is {strict_total}/34 with no proof-card blocking missing field."
    if strict_total >= STRICT_CHALLENGER_MIN:
        return "watchlist", sorted(set(reason_codes + ["strict-challenger"])), f"Strict scorecard is {strict_total}/34; keep active but require council proof."
    if strict_total >= STRICT_WATCHLIST_MIN:
        return "watchlist", sorted(set(reason_codes + ["strict-watchlist"])), f"Strict scorecard is {strict_total}/34; one or more major blockers remain."
    if money_signals or pain_phrases or has_rescue_signal(candidate):
        return "park", sorted(set(reason_codes + ["strict-score-below-watchlist"])), f"Strict scorecard is {strict_total}/34; park until missing proof improves."
    return "reject", sorted(set(reason_codes + ["insufficient-public-evidence"])), "Deep review found no public pain or money signal."


def first_payment_checks(candidate: dict[str, object], label: dict[str, object]) -> dict[str, object]:
    money_signals = known_label_list(label, "money_signals")
    product_angle = field_value(label, "product_angle")
    demo_or_proof = field_value(label, "demo_or_proof")
    distribution = field_value(label, "distribution_channel")
    preview_cost_cap = raw_metadata_value(candidate, "preview_cost_cap") or "unknown"
    failed_job_cost_cap = raw_metadata_value(candidate, "failed_job_cost_cap") or "unknown"
    return {
        "minimum_subsystems_before_preview": product_angle if is_known_text(product_angle) else "unknown",
        "manual_or_semi_manual_payment_proof": "possible" if money_signals and is_known_text(demo_or_proof) else "unknown",
        "free_preview_cost_cap": preview_cost_cap,
        "failed_job_cost_cap": failed_job_cost_cap,
        "ordinary_quality_failure": raw_metadata_value(candidate, "ordinary_quality_failure") or "unknown",
        "built_in_substitution_residue": raw_metadata_value(candidate, "built_in_substitution_residue") or "unknown",
        "input_retry_compute_storage_limits": "known" if has_candidate_cost_cap(candidate) else "unknown",
        "result_before_payment": "possible" if is_known_text(demo_or_proof) else "unknown",
        "paid_trigger": ", ".join(money_signals) if money_signals else "unknown",
        "first_100_async_lane": distribution if is_known_text(distribution) else "unknown",
    }


def proof_blocker_summary(card: dict[str, object]) -> str:
    missing = card.get("missing_evidence")
    if isinstance(missing, list):
        for item in missing:
            if not isinstance(item, dict):
                continue
            blocking_for = item.get("blocking_for") if isinstance(item.get("blocking_for"), list) else []
            if "proof-card" in [normalize_text(value) for value in blocking_for]:
                field = normalize_text(item.get("field")) or normalize_text(item.get("type")) or "evidence"
                next_check = normalize_text(item.get("next_check")) or "find primary evidence"
                return f"{field}: {next_check}"
    strict = card.get("strict_scorecard")
    if isinstance(strict, dict):
        zero_items = strict.get("zero_score_items") if isinstance(strict.get("zero_score_items"), list) else []
        if zero_items:
            return f"zero score: {', '.join(normalize_text(item) for item in zero_items[:3])}"
    reason_codes = label_list(card, "reason_codes")
    return ", ".join(reason_codes[:3]) if reason_codes else "unknown"


def opportunity_card(
    candidate: dict[str, object],
    label: dict[str, object],
    current_status: str,
    current_reasons: list[str],
    week: str,
) -> dict[str, object]:
    candidate_id = normalize_text(candidate.get("candidate_id"))
    evidence_ref = f"ledger/evidence/{candidate_id}.md"
    label_id = normalize_text(label.get("label_id"))
    verdict, reason_codes, rationale = opportunity_verdict(candidate, label, current_status)
    product_angles = label_list(label, "product_angles")
    pain_phrases = label_list(label, "pain_phrases")
    money_signals = label_list(label, "money_signals")
    missing = label.get("missing_evidence") if isinstance(label.get("missing_evidence"), list) else []
    angle = product_angles[0] if product_angles else "unknown"
    buyer = field_value(label, "target_buyer")
    painful_job = field_value(label, "painful_job")
    scorecard = strict_scorecard(candidate, label)
    payment_checks = first_payment_checks(candidate, label)
    next_action = "Run council review lanes before a seven-day proof." if verdict in {"proof-card", "watchlist"} else "Collect missing public evidence or leave parked."
    if verdict == "reject":
        next_action = "Do not spend deep-review time unless new public evidence appears."
    return {
        "card_id": f"card_{uuid.uuid4().hex}",
        "candidate_id": candidate_id,
        "week": week,
        "created_at": utc_now(),
        "actor": "opportunity-scanner-cli",
        "layer": "codex-deep-pass-baseline",
        "source_status": current_status,
        "project_name": normalize_text(candidate.get("project_name")) or "unknown",
        "project_url": normalize_text(candidate.get("project_url")) or "unknown",
        "license": normalize_text(candidate.get("license")) or "unknown",
        "target_buyer": buyer,
        "painful_job": painful_job,
        "current_workaround": "unknown",
        "first_async_channel": payment_checks["first_100_async_lane"],
        "product_angle": angle,
        "derivative_mode": angle if angle != "unknown" else "unknown",
        "what_to_take": ["workflow idea", "public pain wording"],
        "what_not_to_copy": ["brand", "assets", "copy", "private data"],
        "strongest_signals": {
            "pain": pain_phrases[:5],
            "money": money_signals[:5],
            "lanes": active_lane_codes(candidate),
        },
        "scores": opportunity_scores(candidate, label),
        "strict_scorecard": scorecard,
        "first_payment_checks": payment_checks,
        "missing_evidence": missing,
        "risk_hints": label_list(label, "risk_hints"),
        "accepted_findings": [],
        "rejected_findings": [],
        "conflicts": [],
        "vetoes": [],
        "verdict_recommendation": verdict,
        "reason_codes": sorted(set(reason_codes + current_reasons)),
        "rationale": rationale,
        "next_validation_step": next_action,
        "kill_criteria": [
            "No public payment signal outside repo popularity.",
            "First payment requires calls or custom integration.",
            "License, brand, API, or platform risk blocks a clean derivative angle.",
        ],
        "ledger_links": {
            "evidence": evidence_ref,
            "weak_label": f"ledger/labels.jsonl#{label_id}" if label_id else "unknown",
        },
    }


def deep_review_priority(candidate: dict[str, object], label: dict[str, object], current_status: str) -> tuple[int, int, int, int, int, int, int, int]:
    status_rank = {
        "proof-card-candidate": 5,
        "watchlist-candidate": 4,
        "watchlist": 3,
        "codex-review": 2,
    }.get(current_status, 0)
    money_count = len([value for value in label_list(label, "money_signals") if value != "unknown"])
    pain_count = len(label_list(label, "pain_phrases"))
    active_lane_count = len(active_lane_codes(candidate))
    license_known = 0 if normalize_text(candidate.get("license")).lower() == "unknown" else 1
    high_missing_penalty = -missing_high_count(label)
    source_rank = 1 if normalize_text(candidate.get("source")) == "github-search" else 0
    strict_total = int(strict_scorecard(candidate, label).get("total", 0))
    return (license_known, strict_total, status_rank, high_missing_penalty, money_count, pain_count, active_lane_count, source_rank)


def council_packet(card: dict[str, object], lane: str) -> dict[str, object]:
    lane_questions = {
        "market-payment": "Is money nearby, who pays, and what paid analog or budget signal exists?",
        "pain-signal": "Is the pain repeated, urgent, and clearly tied to the candidate workflow?",
        "distribution-first-100": "Can the first 100 prospects be reached async without calls?",
        "buildability-support": "Can a first MVP stay small without custom support traps?",
        "legal-platform-risk": "Is the derivative angle clean for license, brand, ToS, API, and platform risk?",
        "skeptic-kill": "What is the strongest reason to kill or park this candidate?",
    }
    do_not = [
        "Do not judge Operator personal fit.",
        "Do not recommend building a full SaaS shell.",
        "Do not treat stars as money evidence.",
        "Do not smooth over missing evidence or conflicts.",
    ]
    return {
        "packet_id": f"pkt_{uuid.uuid4().hex}",
        "candidate_id": normalize_text(card.get("candidate_id")),
        "week": normalize_text(card.get("week")),
        "card_id": normalize_text(card.get("card_id")),
        "created_at": utc_now(),
        "lane": lane,
        "objective": lane_questions[lane],
        "evidence_packet": {
            "project_name": card.get("project_name"),
            "project_url": card.get("project_url"),
            "product_angle": card.get("product_angle"),
            "target_buyer": card.get("target_buyer"),
            "painful_job": card.get("painful_job"),
            "strongest_signals": card.get("strongest_signals"),
            "missing_evidence": card.get("missing_evidence"),
            "risk_hints": card.get("risk_hints"),
            "repo_digest": card.get("repo_digest"),
            "external_enrichment": card.get("external_enrichment"),
            "ledger_links": card.get("ledger_links"),
        },
        "do": [
            "Use only public evidence or clearly mark missing evidence.",
            "Return structured findings with reason codes.",
            "Prefer explicit vetoes over vague caution when the blocker is decisive.",
        ],
        "do_not": do_not,
        "required_output": {
            "candidate_id": normalize_text(card.get("candidate_id")),
            "week": normalize_text(card.get("week")),
            "lane": lane,
            "verdict": "pass | caution | veto | unknown",
            "confidence": "low | medium | high",
            "strongest_evidence": [],
            "missing_evidence": [],
            "reason_codes": [],
            "next_check": "unknown",
            "notes": "unknown",
        },
    }


def resolved_deep_review_transition(from_status: str, proposed_status: str) -> tuple[str, list[str], str]:
    if proposed_status not in DEEP_REVIEW_FINAL_STATUSES:
        return "watchlist", ["deep-review-invalid-status"], "Deep review proposed an invalid status."
    if from_status in DEEP_REVIEW_STRONG_STATUSES and proposed_status in {"watchlist", "park", "reject"}:
        return from_status, ["status-preserved"], "Deep review did not lower an existing strong status."
    return proposed_status, [], ""


def write_deep_review_report(data_dir: Path, week: str) -> Path:
    paths = ensure_layout(data_dir, week)
    cards = read_jsonl(paths["opportunity_cards"])
    packets = read_jsonl(paths["council_packets"])
    week_candidate_ids = {normalize_text(candidate.get("candidate_id")) for candidate in latest_candidates_for_week(data_dir, week)}
    latest_cards = latest_row_by_candidate_for_week(cards, week)
    packet_counts: dict[str, int] = {}
    for packet in packets:
        candidate_id = normalize_text(packet.get("candidate_id"))
        if candidate_id in week_candidate_ids and normalize_text(packet.get("week")) == week:
            packet_counts[candidate_id] = packet_counts.get(candidate_id, 0) + 1
    report_path = paths["reports"] / f"{week}-deep-review.md"
    lines = [
        f"# Opportunity Scanner Deep Review - {week}",
        "",
        f"- Generated at: `{utc_now()}`",
        f"- Card count: `{len(latest_cards)}`",
        "",
        "## Opportunity Cards",
        "",
    ]
    if not latest_cards:
        lines.append("- none")
    for card in sorted(latest_cards.values(), key=lambda row: normalize_text(row.get("project_name")).lower()):
        candidate_id = normalize_text(card.get("candidate_id"))
        lines.extend(
            [
                f"### {card.get('project_name')}",
                "",
                f"- Candidate ID: `{candidate_id}`",
                f"- Card ID: `{card.get('card_id')}`",
                f"- Verdict recommendation: `{card.get('verdict_recommendation')}`",
                f"- Reason codes: `{', '.join(label_list(card, 'reason_codes')) or 'none'}`",
                f"- Product angle: {card.get('product_angle') or 'unknown'}",
                f"- Target buyer: {card.get('target_buyer') or 'unknown'}",
                f"- Painful job: {card.get('painful_job') or 'unknown'}",
                f"- Next validation step: {card.get('next_validation_step') or 'unknown'}",
                f"- Council packets: `{packet_counts.get(candidate_id, 0)}`",
                "",
            ]
        )
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def deep_review_candidates(data_dir: Path, week: str, max_candidates: int | None = None) -> dict[str, object]:
    if max_candidates is not None and max_candidates < 0:
        raise ValueError("max_candidates must be a non-negative integer")
    paths = ensure_layout(data_dir, week)
    candidates = latest_candidates_for_week(data_dir, week)
    events = read_jsonl(paths["events"])
    statuses = status_by_candidate_for_week(events, week)
    reasons = reason_codes_by_candidate_for_week(events, week)
    labels = latest_label_by_candidate_for_week(read_jsonl(paths["labels"]), week)
    review_queue: list[dict[str, object]] = []
    skipped_count = 0

    for candidate in candidates:
        candidate_id = normalize_text(candidate.get("candidate_id"))
        current_status = statuses.get(candidate_id, "raw")
        label = labels.get(candidate_id, {})
        if current_status not in DEEP_REVIEW_INPUT_STATUSES or not label:
            skipped_count += 1
            continue
        review_queue.append(candidate)

    review_queue.sort(
        key=lambda candidate: deep_review_priority(
            candidate,
            labels.get(normalize_text(candidate.get("candidate_id")), {}),
            statuses.get(normalize_text(candidate.get("candidate_id")), "raw"),
        ),
        reverse=True,
    )
    if max_candidates is not None and max_candidates >= 0:
        skipped_count += max(0, len(review_queue) - max_candidates)
        review_queue = review_queue[:max_candidates]

    cards_written = 0
    packets_written = 0
    events_written = 0

    for candidate in review_queue:
        candidate_id = normalize_text(candidate.get("candidate_id"))
        current_status = statuses.get(candidate_id, "raw")
        label = labels.get(candidate_id, {})
        card = opportunity_card(candidate, label, current_status, reasons.get(candidate_id, []), week)
        attach_external_context_to_card(card, paths, data_dir)
        append_jsonl(paths["opportunity_cards"], card)
        cards_written += 1
        proposed_status = normalize_text(card.get("verdict_recommendation"))
        to_status, transition_reasons, transition_notes = resolved_deep_review_transition(current_status, proposed_status)
        card_reason_codes = label_list(card, "reason_codes")
        reason_codes = sorted(set(card_reason_codes + transition_reasons))
        notes = transition_notes or normalize_text(card.get("rationale"))
        event = event_row(
            candidate_id,
            "codex-deep-pass",
            current_status,
            to_status,
            reason_codes,
            [
                normalize_text(card.get("ledger_links", {}).get("evidence")) if isinstance(card.get("ledger_links"), dict) else "",
                f"ledger/opportunity_cards.jsonl#{card['card_id']}",
            ],
            notes,
            week,
        )
        append_jsonl(paths["events"], event)
        events_written += 1
        statuses[candidate_id] = to_status

        if to_status in {"watchlist", "proof-card"}:
            for lane in COUNCIL_LANES:
                packet = council_packet(card, lane)
                append_jsonl(paths["council_packets"], packet)
                packets_written += 1

    report_path = write_deep_review_report(data_dir, week)
    write_batch_report(data_dir, week)
    return {
        "candidate_count": len(candidates),
        "cards_written": cards_written,
        "packets_written": packets_written,
        "events_written": events_written,
        "skipped_count": skipped_count,
        "report_path": str(report_path),
    }


def normalize_council_finding(raw: dict[str, object]) -> dict[str, object]:
    candidate_id = normalize_text(raw.get("candidate_id"))
    lane = normalize_text(raw.get("lane"))
    verdict = normalize_text(raw.get("verdict"))
    confidence = normalize_text(raw.get("confidence"))
    if lane not in COUNCIL_LANES:
        raise ValueError(f"Unknown council lane: {lane}")
    if verdict not in COUNCIL_VERDICTS:
        raise ValueError(f"Unknown council verdict: {verdict}")
    if confidence not in {"low", "medium", "high"}:
        raise ValueError(f"Unknown council confidence: {confidence}")
    strongest_evidence = raw.get("strongest_evidence") if isinstance(raw.get("strongest_evidence"), list) else []
    missing_evidence = raw.get("missing_evidence") if isinstance(raw.get("missing_evidence"), list) else []
    reason_codes = raw.get("reason_codes") if isinstance(raw.get("reason_codes"), list) else []
    return {
        "finding_id": normalize_text(raw.get("finding_id")) or f"fnd_{uuid.uuid4().hex}",
        "candidate_id": candidate_id,
        "week": normalize_text(raw.get("week")),
        "packet_id": normalize_text(raw.get("packet_id")),
        "created_at": normalize_text(raw.get("created_at")) or utc_now(),
        "actor": normalize_text(raw.get("actor")) or "manual-council-finding",
        "lane": lane,
        "verdict": verdict,
        "confidence": confidence,
        "strongest_evidence": [normalize_text(item) for item in strongest_evidence if normalize_text(item)],
        "missing_evidence": [normalize_text(item) for item in missing_evidence if normalize_text(item)],
        "reason_codes": [normalize_text(item) for item in reason_codes if normalize_text(item)],
        "next_check": normalize_text(raw.get("next_check")) or "unknown",
        "notes": normalize_text(raw.get("notes")) or "unknown",
    }


def findings_by_candidate(findings: list[dict[str, object]]) -> dict[str, list[dict[str, object]]]:
    grouped: dict[str, list[dict[str, object]]] = {}
    for finding in findings:
        candidate_id = normalize_text(finding.get("candidate_id"))
        if candidate_id:
            grouped.setdefault(candidate_id, []).append(finding)
    return grouped


def aggregate_findings(candidate_id: str, findings: list[dict[str, object]], card: dict[str, object]) -> dict[str, object]:
    accepted: list[dict[str, object]] = []
    rejected: list[dict[str, object]] = []
    conflicts: list[dict[str, object]] = []
    vetoes: list[dict[str, object]] = []
    missing: list[str] = []
    reason_codes: list[str] = []
    lane_verdicts: dict[str, set[str]] = {}

    for finding in findings:
        verdict = normalize_text(finding.get("verdict"))
        lane = normalize_text(finding.get("lane"))
        lane_verdicts.setdefault(lane, set()).add(verdict)
        reason_codes.extend(label_list(finding, "reason_codes"))
        missing.extend(label_list(finding, "missing_evidence"))
        if verdict == "pass":
            accepted.append(finding)
        elif verdict == "veto":
            vetoes.append(finding)
        else:
            rejected.append(finding)

    for lane, verdicts in sorted(lane_verdicts.items()):
        if "pass" in verdicts and "veto" in verdicts:
            conflicts.append({"lane": lane, "reason": "pass-and-veto"})
    if vetoes and accepted:
        conflicts.append({"lane": "cross-lane", "reason": "accepted-findings-with-veto"})

    final_verdict = "watchlist"
    next_action = "Inspect council conflicts and missing evidence."
    high_vetoes = [finding for finding in vetoes if normalize_text(finding.get("confidence")) == "high"]
    strict_total = strict_total_from_card(card)
    legal_veto = [
        finding
        for finding in vetoes
        if normalize_text(finding.get("lane")) == "legal-platform-risk"
        or "legal-platform-veto" in label_list(finding, "reason_codes")
    ]
    first_payment_calls_veto = [
        finding for finding in vetoes if "first-payment-requires-calls" in label_list(finding, "reason_codes")
    ]

    if first_payment_calls_veto:
        final_verdict = "reject"
        reason_codes.append("first-payment-requires-calls")
        next_action = "Reject unless a self-serve first-payment path appears."
    elif legal_veto:
        final_verdict = "park"
        reason_codes.append("legal-platform-veto")
        next_action = "Park until license, brand, API, or ToS risk is cleared."
    elif high_vetoes:
        final_verdict = "reject"
        reason_codes.append("high-confidence-veto")
        next_action = "Reject unless the veto is disproven with primary evidence."
    elif conflicts:
        final_verdict = "watchlist"
        reason_codes.append("council-conflict")
        next_action = "Resolve council conflict with source inspection."
    elif len(accepted) >= 4 and not missing and strict_total >= STRICT_PROOF_CARD_MIN:
        final_verdict = "proof-card"
        reason_codes.append("council-proof-card-ready")
        next_action = "Write seven-day proof-card with success metric and kill criterion."
    elif len(accepted) >= 4 and not missing:
        final_verdict = "watchlist"
        reason_codes.append("strict-score-required-before-proof-card")
        next_action = "Improve strict scorecard evidence before proof-card."
    elif accepted:
        final_verdict = "watchlist"
        reason_codes.append("council-watchlist")
        next_action = "Collect missing evidence before proof-card."
    else:
        final_verdict = "watchlist"
        reason_codes.append("council-unknown")

    if final_verdict == "proof-card":
        market_pass = any(
            normalize_text(finding.get("lane")) == "market-payment" and normalize_text(finding.get("verdict")) == "pass"
            for finding in findings
        )
        if not market_pass:
            final_verdict = "watchlist"
            reason_codes.append("money-signal-required-before-proof-card")
            next_action = "Find payment evidence outside repo popularity."

    return {
        "aggregation_id": f"agg_{uuid.uuid4().hex}",
        "candidate_id": candidate_id,
        "week": normalize_text(card.get("week")),
        "created_at": utc_now(),
        "actor": "opportunity-scanner-cli",
        "layer": "council-aggregator",
        "card_id": normalize_text(card.get("card_id")),
        "accepted_findings": accepted,
        "rejected_findings": rejected,
        "conflicts": conflicts,
        "vetoes": vetoes,
        "missing_evidence": sorted(set(missing)),
        "final_machine_verdict": final_verdict,
        "reason_codes": sorted(set(reason_codes)),
        "recommended_next_action": next_action,
        "telegram_summary": f"{card.get('project_name', 'unknown')}: {final_verdict}. {next_action}",
        "ledger_links": {
            "opportunity_card": f"ledger/opportunity_cards.jsonl#{card.get('card_id')}",
            "council_findings": "ledger/council_findings.jsonl",
        },
    }


def write_aggregation_report(data_dir: Path, week: str) -> Path:
    paths = ensure_layout(data_dir, week)
    candidates = latest_candidates_for_week(data_dir, week)
    aggregations = latest_row_by_candidate_for_week(read_jsonl(paths["aggregations"]), week)
    report_path = paths["reports"] / f"{week}-council-aggregation.md"
    lines = [
        f"# Opportunity Scanner Council Aggregation - {week}",
        "",
        f"- Generated at: `{utc_now()}`",
        f"- Aggregation count: `{len(aggregations)}`",
        "",
        "## Verdicts",
        "",
    ]
    if not aggregations:
        lines.append("- none")
    for aggregation in sorted(aggregations.values(), key=lambda row: normalize_text(row.get("candidate_id"))):
        conflicts = aggregation.get("conflicts") if isinstance(aggregation.get("conflicts"), list) else []
        vetoes = aggregation.get("vetoes") if isinstance(aggregation.get("vetoes"), list) else []
        lines.extend(
            [
                f"### {aggregation.get('candidate_id')}",
                "",
                f"- Final machine verdict: `{aggregation.get('final_machine_verdict')}`",
                f"- Reason codes: `{', '.join(label_list(aggregation, 'reason_codes')) or 'none'}`",
                f"- Conflicts: `{len(conflicts)}`",
                f"- Vetoes: `{len(vetoes)}`",
                f"- Recommended next action: {aggregation.get('recommended_next_action') or 'unknown'}",
                "",
            ]
        )
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def council_aggregate(data_dir: Path, week: str, input_path: Path) -> dict[str, object]:
    paths = ensure_layout(data_dir, week)
    raw_findings = read_jsonl(input_path)
    normalized_findings = [normalize_council_finding(row) for row in raw_findings]
    for finding in normalized_findings:
        finding["week"] = week
        append_jsonl(paths["council_findings"], finding)

    events = read_jsonl(paths["events"])
    statuses = status_by_candidate_for_week(events, week)
    cards = latest_row_by_candidate_for_week(read_jsonl(paths["opportunity_cards"]), week)
    candidate_ids = {normalize_text(finding.get("candidate_id")) for finding in normalized_findings}
    all_findings = read_jsonl(paths["council_findings"])
    grouped = findings_by_candidate(
        [
            finding
            for finding in all_findings
            if normalize_text(finding.get("candidate_id")) in candidate_ids and normalize_text(finding.get("week")) == week
        ]
    )
    aggregations_written = 0
    events_written = 0

    for candidate_id, findings in sorted(grouped.items()):
        card = cards.get(candidate_id, {})
        if not card:
            continue
        aggregation = aggregate_findings(candidate_id, findings, card)
        append_jsonl(paths["aggregations"], aggregation)
        aggregations_written += 1
        from_status = statuses.get(candidate_id, "watchlist")
        to_status = normalize_text(aggregation.get("final_machine_verdict")) or "watchlist"
        if to_status not in DEEP_REVIEW_FINAL_STATUSES:
            to_status = "watchlist"
        event = event_row(
            candidate_id,
            "council-aggregator",
            from_status,
            to_status,
            label_list(aggregation, "reason_codes"),
            [
                f"ledger/aggregations.jsonl#{aggregation['aggregation_id']}",
                "ledger/council_findings.jsonl",
            ],
            normalize_text(aggregation.get("recommended_next_action")),
            week,
        )
        append_jsonl(paths["events"], event)
        events_written += 1
        statuses[candidate_id] = to_status

    report_path = write_aggregation_report(data_dir, week)
    write_batch_report(data_dir, week)
    return {
        "findings_written": len(normalized_findings),
        "aggregations_written": aggregations_written,
        "events_written": events_written,
        "report_path": str(report_path),
    }


def digest_verdict(candidate_id: str, statuses: dict[str, str], card: dict[str, object], aggregation: dict[str, object]) -> str:
    status = statuses.get(candidate_id, "raw")
    if status in OPERATOR_DIGEST_VERDICT_OVERRIDES:
        return OPERATOR_DIGEST_VERDICT_OVERRIDES[status]
    if aggregation:
        return normalize_text(aggregation.get("final_machine_verdict")) or "watchlist"
    if card:
        return normalize_text(card.get("verdict_recommendation")) or status
    return status


def digest_next_action(card: dict[str, object], aggregation: dict[str, object]) -> str:
    if aggregation:
        return normalize_text(aggregation.get("recommended_next_action")) or "unknown"
    if card:
        return normalize_text(card.get("next_validation_step")) or "unknown"
    return "Collect missing evidence or leave out of the digest."


def digest_candidate_line(candidate: dict[str, object], card: dict[str, object], aggregation: dict[str, object], verdict: str) -> list[str]:
    candidate_id = normalize_text(candidate.get("candidate_id"))
    card_links = card.get("ledger_links") if isinstance(card.get("ledger_links"), dict) else {}
    agg_links = aggregation.get("ledger_links") if isinstance(aggregation.get("ledger_links"), dict) else {}
    evidence = normalize_text(card_links.get("evidence")) or f"ledger/evidence/{candidate_id}.md"
    card_ref = normalize_text(agg_links.get("opportunity_card")) or (
        f"ledger/opportunity_cards.jsonl#{card.get('card_id')}" if card else "unknown"
    )
    product_angle = normalize_text(card.get("product_angle")) if card else "unknown"
    buyer = normalize_text(card.get("target_buyer")) if card else "unknown"
    painful_job = normalize_text(card.get("painful_job")) if card else "unknown"
    reason_codes = label_list(aggregation, "reason_codes") if aggregation else label_list(card, "reason_codes")
    return [
        f"### {candidate.get('project_name')}",
        "",
        f"- Candidate ID: `{candidate_id}`",
        f"- Verdict: `{verdict}`",
        f"- Product angle: {product_angle or 'unknown'}",
        f"- Buyer: {buyer or 'unknown'}",
        f"- Painful job: {painful_job or 'unknown'}",
        f"- Reason codes: `{', '.join(reason_codes) if reason_codes else 'none'}`",
        f"- Next action: {digest_next_action(card, aggregation)}",
        f"- Evidence: `{evidence}`",
        f"- Opportunity card: `{card_ref}`",
        "",
    ]


def strict_total_from_card(card: dict[str, object]) -> int:
    strict = card.get("strict_scorecard")
    if isinstance(strict, dict) and isinstance(strict.get("total"), int):
        return int(strict.get("total"))
    scores = card.get("scores")
    if isinstance(scores, dict) and isinstance(scores.get("strict_scorecard_total"), int):
        return int(scores.get("strict_scorecard_total"))
    return 0


def human_value(value: object, fallback: str = "not proven") -> str:
    text = normalize_text(value)
    return text if is_known_text(text) else fallback


def human_money_signal(card: dict[str, object]) -> str:
    strongest = card.get("strongest_signals")
    if not isinstance(strongest, dict):
        return "not proven"
    money = strongest.get("money")
    if not isinstance(money, list):
        return "not proven"
    known = [normalize_text(item) for item in money if is_known_text(item)]
    return ", ".join(known[:3]) if known else "not proven"


def human_first_100(card: dict[str, object]) -> str:
    channel = normalize_text(card.get("first_async_channel"))
    if not is_known_text(channel):
        return "not proven"
    if channel == "github/reddit/product-hunt":
        return "not proven; only generic source lane exists"
    return channel


def human_digest_candidate_block(candidate: dict[str, object], card: dict[str, object], aggregation: dict[str, object], verdict: str, index: int) -> list[str]:
    project_name = normalize_text(candidate.get("project_name")) or "Unknown project"
    project_url = normalize_text(candidate.get("project_url"))
    total = strict_total_from_card(card)
    if verdict == "PRD-lite":
        band = "PRD-lite"
    elif verdict == "operator-proof-approved":
        band = "Operator-approved"
    else:
        band = "proof-card"
    next_action = digest_next_action(card, aggregation)
    return [
        f"{index}. {project_name} - {band} ({total}/34)",
        f"URL: {project_url or 'unknown'}",
        f"Buyer: {human_value(card.get('target_buyer'))}",
        f"Pain: {human_value(card.get('painful_job'))}",
        f"Angle: {human_value(card.get('product_angle'))}",
        f"Money signal: {human_money_signal(card)}",
        f"First 100: {human_first_100(card)}",
        f"Blocker: {proof_blocker_summary(card)}",
        f"Next: {next_action}",
        "",
    ]


def telegram_human_digest(
    week: str,
    candidates: dict[str, dict[str, object]],
    statuses: dict[str, str],
    cards: dict[str, dict[str, object]],
    aggregations: dict[str, dict[str, object]],
) -> str:
    records: list[tuple[int, int, str, str, dict[str, object], dict[str, object], dict[str, object]]] = []
    counts = {"ready": 0, "watchlist": 0, "park": 0, "reject": 0, "other": 0}
    for candidate_id, candidate in candidates.items():
        card = cards.get(candidate_id, {})
        aggregation = aggregations.get(candidate_id, {})
        verdict = digest_verdict(candidate_id, statuses, card, aggregation)
        if verdict in TELEGRAM_READY_VERDICTS:
            verdict_rank = 4 if verdict in {"PRD-lite", "operator-proof-approved"} else 3
            counts["ready"] += 1
        elif verdict == "watchlist":
            counts["watchlist"] += 1
            continue
        elif verdict == "park":
            counts["park"] += 1
            continue
        elif verdict in {"reject", "machine-reject"}:
            counts["reject"] += 1
            continue
        else:
            counts["other"] += 1
            continue
        if not card:
            continue
        records.append((verdict_rank, strict_total_from_card(card), normalize_text(candidate.get("project_name")).lower(), verdict, candidate, card, aggregation))

    records.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
    selected = records[:TELEGRAM_HUMAN_CANDIDATE_LIMIT]
    lines = [
        f"Opportunity Scanner - {week}",
        "",
    ]
    if selected:
        lines.append(f"Ready shortlist: {len(selected)} candidate(s) passed final filters.")
        lines.append("")
        for index, record in enumerate(selected, start=1):
            lines.extend(human_digest_candidate_block(record[4], record[5], record[6], record[3], index))
    else:
        lines.extend(
            [
                "No ready ideas passed all filters this week.",
                "Nothing from this batch is ready for build or proof execution yet.",
                "",
            ]
        )
    lines.extend(
        [
            f"Kept out of Telegram: watchlist={counts['watchlist']}, park={counts['park']}, reject={counts['reject']}, other={counts['other']}.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def write_digest(data_dir: Path, week: str) -> Path:
    paths = ensure_layout(data_dir, week)
    candidates = latest_candidates_for_week(data_dir, week)
    candidate_by_id = {normalize_text(candidate.get("candidate_id")): candidate for candidate in candidates}
    events = read_jsonl(paths["events"])
    statuses = status_by_candidate_for_week(events, week)
    cards = latest_row_by_candidate_for_week(read_jsonl(paths["opportunity_cards"]), week)
    aggregations = latest_row_by_candidate_for_week(read_jsonl(paths["aggregations"]), week)
    sections = {
        "proof-card": [],
        "watchlist": [],
        "park": [],
        "reject": [],
        "other": [],
    }

    for candidate_id, candidate in sorted(candidate_by_id.items(), key=lambda item: normalize_text(item[1].get("project_name")).lower()):
        card = cards.get(candidate_id, {})
        aggregation = aggregations.get(candidate_id, {})
        verdict = digest_verdict(candidate_id, statuses, card, aggregation)
        if verdict in {"machine-reject", "needs-evidence", "raw"} and not card and not aggregation:
            continue
        if verdict == "PRD-lite":
            section = "proof-card"
        elif verdict in sections:
            section = verdict
        else:
            section = "other"
        sections[section].extend(digest_candidate_line(candidate, card, aggregation, verdict))

    digest_path = paths["reports"] / f"{week}-digest.md"
    outbox_path = paths["telegram_outbox"] / f"{week}-digest.md"
    lines = [
        f"# Opportunity Scanner Digest - {week}",
        "",
        f"- Generated at: `{utc_now()}`",
        f"- Telegram outbox: `{outbox_path.relative_to(data_dir)}`",
        "",
        "## Proof-Card Candidates",
        "",
    ]
    lines.extend(sections["proof-card"] or ["- none", ""])
    lines.extend(["## Watchlist", ""])
    lines.extend(sections["watchlist"] or ["- none", ""])
    lines.extend(["## Parked", ""])
    lines.extend(sections["park"] or ["- none", ""])
    lines.extend(["## Rejects", ""])
    if sections["reject"]:
        lines.extend(sections["reject"])
    else:
        reject_counts: dict[str, int] = {}
        reasons = reason_codes_by_candidate_for_week(events, week)
        for candidate_id, status in statuses.items():
            if status == "machine-reject":
                for reason in reasons.get(candidate_id, ["unknown"]):
                    reject_counts[reason] = reject_counts.get(reason, 0) + 1
        if reject_counts:
            for reason, count in sorted(reject_counts.items()):
                lines.append(f"- `{reason}`: {count}")
            lines.append("")
        else:
            lines.extend(["- none", ""])
    if sections["other"]:
        lines.extend(["## Other", ""])
        lines.extend(sections["other"])
    payload = "\n".join(lines).rstrip() + "\n"
    digest_path.write_text(payload, encoding="utf-8")
    outbox_path.parent.mkdir(parents=True, exist_ok=True)
    outbox_path.write_text(
        telegram_human_digest(week, candidate_by_id, statuses, cards, aggregations),
        encoding="utf-8",
    )
    return digest_path


def telegram_message_chunks(text: str, chunk_limit: int = TELEGRAM_CHUNK_LIMIT) -> list[str]:
    if chunk_limit <= 0 or chunk_limit > TELEGRAM_MESSAGE_LIMIT:
        raise ValueError("Telegram chunk limit must be between 1 and 4096")
    if not text:
        return []
    chunks: list[str] = []
    current = ""
    for line in text.splitlines(keepends=True):
        remaining = line
        while len(remaining) > chunk_limit:
            if current:
                chunks.append(current.rstrip())
                current = ""
            chunks.append(remaining[:chunk_limit].rstrip())
            remaining = remaining[chunk_limit:]
        if current and len(current) + len(remaining) > chunk_limit:
            chunks.append(current.rstrip())
            current = ""
        current += remaining
    if current.strip():
        chunks.append(current.rstrip())
    return [chunk for chunk in chunks if chunk]


def telegram_digest_messages(text: str) -> list[str]:
    chunks = telegram_message_chunks(text)
    if len(chunks) <= 1:
        return chunks
    total = len(chunks)
    messages: list[str] = []
    for index, chunk in enumerate(chunks, 1):
        prefix = f"Opportunity Scanner Digest ({index}/{total})\n\n"
        messages.append(f"{prefix}{chunk}")
    return messages


def send_telegram_message(token: str, chat_id: str, text: str, api_base: str, timeout: int) -> dict[str, object]:
    if len(text) > TELEGRAM_MESSAGE_LIMIT:
        raise ValueError("Telegram message text exceeds 4096 characters")
    url = f"{api_base.rstrip('/')}/bot{token}/sendMessage"
    body = json.dumps({"chat_id": chat_id, "text": text}, ensure_ascii=True).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "opportunity-scanner-local",
        },
        method="POST",
    )
    response = None
    try:
        response = urllib.request.urlopen(request, timeout=timeout)
        raw_body = response.read().decode("utf-8")
    except urllib.error.HTTPError:
        error = sys.exc_info()[1]
        raise RuntimeError(f"Telegram sendMessage failed: {error}") from error
    except urllib.error.URLError:
        error = sys.exc_info()[1]
        raise RuntimeError(f"Telegram sendMessage failed: {error}") from error
    finally:
        if response is not None:
            response.close()
    payload = json.loads(raw_body) if raw_body else {}
    if not isinstance(payload, dict):
        raise RuntimeError("Telegram sendMessage returned a non-object response")
    if not payload.get("ok"):
        description = normalize_text(payload.get("description")) or "unknown Telegram API error"
        raise RuntimeError(f"Telegram sendMessage failed: {description}")
    return payload


def send_telegram_digest(
    data_dir: Path,
    week: str,
    token: str,
    chat_id: str,
    api_base: str,
    timeout: int,
    dry_run: bool,
    skip_empty: bool = False,
    sender: Callable[[str, str, str, str, int], dict[str, object]] | None = None,
) -> dict[str, object]:
    paths = ensure_layout(data_dir, week)
    digest_path = paths["telegram_outbox"] / f"{week}-digest.md"
    if not digest_path.exists():
        write_digest(data_dir, week)
    text = digest_path.read_text(encoding="utf-8")
    messages = telegram_digest_messages(text)
    if dry_run:
        return {
            "dry_run": True,
            "digest_path": str(digest_path),
            "message_count": len(messages),
            "character_count": len(text),
        }
    if skip_empty and "Ready shortlist:" not in text:
        return {
            "dry_run": False,
            "digest_path": str(digest_path),
            "message_count": 0,
            "sent_message_ids": [],
            "skipped": True,
            "reason": "no-ready-candidates",
        }
    resolved_token = token or env_telegram_token()
    resolved_chat_id = chat_id or env_telegram_chat_id()
    if not resolved_token:
        raise ValueError("Missing TELEGRAM_BOT_TOKEN or TG_BOT_TOKEN")
    if not resolved_chat_id:
        raise ValueError("Missing TELEGRAM_CHAT_ID or TG_CHAT_ID")
    send = sender if sender is not None else send_telegram_message
    message_ids: list[int] = []
    for message in messages:
        response = send(resolved_token, resolved_chat_id, message, api_base, timeout)
        result = response.get("result") if isinstance(response.get("result"), dict) else {}
        message_id = result.get("message_id") if isinstance(result, dict) else None
        if isinstance(message_id, int):
            message_ids.append(message_id)
    return {
        "dry_run": False,
        "digest_path": str(digest_path),
        "message_count": len(messages),
        "sent_message_ids": message_ids,
    }


def normalize_operator_decision(raw: dict[str, object]) -> dict[str, object]:
    candidate_id = normalize_text(raw.get("candidate_id"))
    decision = normalize_text(raw.get("decision"))
    if not candidate_id:
        raise ValueError("Operator decision requires candidate_id")
    if decision not in OPERATOR_DECISIONS:
        raise ValueError(f"Unknown Operator decision: {decision}")
    reason_codes = raw.get("reason_codes") if isinstance(raw.get("reason_codes"), list) else []
    filter_update = raw.get("filter_update") if isinstance(raw.get("filter_update"), dict) else {}
    return {
        "decision_id": normalize_text(raw.get("decision_id")) or f"operator_{uuid.uuid4().hex}",
        "candidate_id": candidate_id,
        "created_at": normalize_text(raw.get("created_at")) or utc_now(),
        "actor": normalize_text(raw.get("actor")) or "operator",
        "decision": decision,
        "reason_codes": [normalize_text(reason) for reason in reason_codes if normalize_text(reason)],
        "notes": normalize_text(raw.get("notes")) or "unknown",
        "reusable_filter_update": bool(raw.get("reusable_filter_update")) or decision == "filter-update-needed",
        "filter_update": filter_update,
    }


def filter_update_row(decision: dict[str, object]) -> dict[str, object]:
    filter_update = decision.get("filter_update") if isinstance(decision.get("filter_update"), dict) else {}
    return {
        "update_id": f"flt_{uuid.uuid4().hex}",
        "candidate_id": normalize_text(decision.get("candidate_id")),
        "created_at": utc_now(),
        "source_decision_id": normalize_text(decision.get("decision_id")),
        "reason_codes": label_list(decision, "reason_codes"),
        "proposed_change": normalize_text(filter_update.get("proposed_change")) or "unknown",
        "target_doc": normalize_text(filter_update.get("target_doc")) or "docs/opportunity-filter-v3.md",
        "notes": normalize_text(decision.get("notes")),
        "status": "open",
    }


def apply_operator_feedback_rows(data_dir: Path, week: str, raw_rows: list[dict[str, object]], source_layer: str = "operator-feedback") -> dict[str, object]:
    paths = ensure_layout(data_dir, week)
    decisions = [normalize_operator_decision(row) for row in raw_rows]
    events = read_jsonl(paths["events"])
    statuses = status_by_candidate_for_week(events, week)
    decisions_written = 0
    events_written = 0
    filter_updates_written = 0

    for decision in decisions:
        candidate_id = normalize_text(decision.get("candidate_id"))
        append_jsonl(paths["operator_decisions"], decision)
        decisions_written += 1
        from_status = statuses.get(candidate_id, "raw")
        to_status = normalize_text(decision.get("decision"))
        event = event_row(
            candidate_id,
            source_layer,
            from_status,
            to_status,
            label_list(decision, "reason_codes"),
            [f"ledger/operator_decisions.jsonl#{decision['decision_id']}"],
            normalize_text(decision.get("notes")),
            week,
        )
        append_jsonl(paths["events"], event)
        events_written += 1
        statuses[candidate_id] = to_status
        if bool(decision.get("reusable_filter_update")):
            append_jsonl(paths["filter_updates"], filter_update_row(decision))
            filter_updates_written += 1

    digest_path = write_digest(data_dir, week)
    write_batch_report(data_dir, week)
    return {
        "decisions_written": decisions_written,
        "events_written": events_written,
        "filter_updates_written": filter_updates_written,
        "digest_path": str(digest_path),
    }


def apply_operator_feedback(data_dir: Path, week: str, input_path: Path) -> dict[str, object]:
    return apply_operator_feedback_rows(data_dir, week, read_jsonl(input_path), "operator-feedback")


def telegram_chat_matches(update_chat_id: object, allowed_chat_id: str) -> bool:
    if not allowed_chat_id:
        return True
    return normalize_text(update_chat_id) == normalize_text(allowed_chat_id)


def telegram_reason_slug(value: str) -> str:
    text = re.sub(r"[^a-z0-9-]+", "-", value.lower()).strip("-")
    return text[:60] or "telegram-feedback"


def telegram_decision_from_command(text: str) -> dict[str, object]:
    parts = text.strip().split()
    if len(parts) < 2:
        return {}
    command = parts[0].split("@", 1)[0].lower()
    decision = TELEGRAM_FEEDBACK_COMMANDS.get(command)
    if not decision:
        return {}
    candidate_id = normalize_text(parts[1])
    if not candidate_id.startswith("cand_"):
        return {}
    notes = " ".join(parts[2:]).strip()
    reason = telegram_reason_slug(notes) if notes else "telegram-feedback"
    row: dict[str, object] = {
        "candidate_id": candidate_id,
        "decision": decision,
        "reason_codes": [reason],
        "notes": notes or f"Telegram command {command}",
        "actor": "operator",
    }
    if decision == "filter-update-needed":
        row["reusable_filter_update"] = True
        row["filter_update"] = {"proposed_change": notes or "Review reusable Telegram filter feedback."}
    return row


def telegram_decision_from_callback(data: str) -> dict[str, object]:
    # Format: osfb|proof|cand_x or osfb:pf:cand_x
    normalized = data.replace(":", "|")
    parts = normalized.split("|")
    if len(parts) < 3 or parts[0] != "osfb":
        return {}
    decision = TELEGRAM_FEEDBACK_CALLBACKS.get(parts[1])
    candidate_id = normalize_text(parts[2])
    if not decision or not candidate_id.startswith("cand_"):
        return {}
    reason = telegram_reason_slug(parts[3]) if len(parts) >= 4 else "telegram-callback"
    row: dict[str, object] = {
        "candidate_id": candidate_id,
        "decision": decision,
        "reason_codes": [reason],
        "notes": f"Telegram callback {parts[1]}",
        "actor": "operator",
    }
    if decision == "filter-update-needed":
        row["reusable_filter_update"] = True
        row["filter_update"] = {"proposed_change": "Review reusable Telegram callback feedback."}
    return row


def telegram_feedback_rows_from_updates(updates: list[dict[str, object]], chat_id: str) -> tuple[list[dict[str, object]], list[str], int]:
    rows: list[dict[str, object]] = []
    callback_ids: list[str] = []
    ignored = 0
    for update in updates:
        if not isinstance(update, dict):
            ignored += 1
            continue
        message = update.get("message") if isinstance(update.get("message"), dict) else {}
        callback = update.get("callback_query") if isinstance(update.get("callback_query"), dict) else {}
        row: dict[str, object] = {}
        callback_id = ""
        if message:
            chat = message.get("chat") if isinstance(message.get("chat"), dict) else {}
            if not telegram_chat_matches(chat.get("id"), chat_id):
                ignored += 1
                continue
            row = telegram_decision_from_command(normalize_text(message.get("text")))
        elif callback:
            message_from_callback = callback.get("message") if isinstance(callback.get("message"), dict) else {}
            chat = message_from_callback.get("chat") if isinstance(message_from_callback.get("chat"), dict) else {}
            if not telegram_chat_matches(chat.get("id"), chat_id):
                ignored += 1
                continue
            row = telegram_decision_from_callback(normalize_text(callback.get("data")))
            callback_id = normalize_text(callback.get("id"))
        if row:
            row["created_at"] = utc_now()
            rows.append(row)
            if callback_id:
                callback_ids.append(callback_id)
        else:
            ignored += 1
    return rows, callback_ids, ignored


def telegram_get_updates(token: str, api_base: str, offset: int, timeout: int) -> dict[str, object]:
    query = urllib.parse.urlencode({"offset": offset, "timeout": 0, "allowed_updates": json.dumps(["message", "callback_query"])})
    url = f"{api_base.rstrip('/')}/bot{token}/getUpdates?{query}"
    request = urllib.request.Request(url, headers={"User-Agent": "opportunity-scanner-local"})
    response = None
    try:
        response = urllib.request.urlopen(request, timeout=timeout)
        payload = json.loads(response.read().decode("utf-8"))
    finally:
        if response is not None:
            response.close()
    return payload if isinstance(payload, dict) else {}


def telegram_answer_callback(token: str, api_base: str, callback_query_id: str, text: str, timeout: int) -> dict[str, object]:
    url = f"{api_base.rstrip('/')}/bot{token}/answerCallbackQuery"
    body = json.dumps({"callback_query_id": callback_query_id, "text": text}, ensure_ascii=True).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json", "User-Agent": "opportunity-scanner-local"}, method="POST")
    response = None
    try:
        response = urllib.request.urlopen(request, timeout=timeout)
        payload = json.loads(response.read().decode("utf-8"))
    finally:
        if response is not None:
            response.close()
    return payload if isinstance(payload, dict) else {}


def read_telegram_feedback_state(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def write_telegram_feedback_state(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_telegram_feedback(
    data_dir: Path,
    week: str,
    token: str,
    chat_id: str,
    api_base: str,
    timeout: int,
    dry_run: bool,
    input_path: Path | None = None,
    updates_fetcher: Callable[[str, str, int, int], dict[str, object]] | None = None,
    callback_answerer: Callable[[str, str, str, str, int], dict[str, object]] | None = None,
) -> dict[str, object]:
    paths = ensure_layout(data_dir, week)
    resolved_token = token or env_telegram_token()
    resolved_chat_id = chat_id or env_telegram_chat_id()
    if input_path is not None:
        payload = json.loads(input_path.read_text(encoding="utf-8"))
        updates = payload if isinstance(payload, list) else safe_list(payload.get("result")) if isinstance(payload, dict) else []
        offset = 0
        first_live_poll_without_state = False
    else:
        if not resolved_token:
            raise ValueError("Missing TELEGRAM_BOT_TOKEN or TG_BOT_TOKEN")
        if not resolved_chat_id:
            raise ValueError("Missing TELEGRAM_CHAT_ID or TG_CHAT_ID")
        state = read_telegram_feedback_state(paths["telegram_feedback_state"])
        first_live_poll_without_state = "next_update_id" not in state
        offset = int(state.get("next_update_id", 0) or 0)
        fetch = updates_fetcher if updates_fetcher is not None else telegram_get_updates
        response = fetch(resolved_token, api_base, offset, timeout)
        if not response.get("ok", True):
            raise RuntimeError(normalize_text(response.get("description")) or "Telegram getUpdates failed")
        updates = safe_list(response.get("result"))
    typed_updates = [update for update in updates if isinstance(update, dict)]
    rows, callback_ids, ignored_count = telegram_feedback_rows_from_updates(typed_updates, resolved_chat_id)
    max_update_id = 0
    for update in typed_updates:
        update_id = update.get("update_id")
        if isinstance(update_id, int) and update_id > max_update_id:
            max_update_id = update_id
    if dry_run:
        return {
            "dry_run": True,
            "updates_seen": len(typed_updates),
            "decisions_found": len(rows),
            "callbacks_found": len(callback_ids),
            "ignored_count": ignored_count,
            "next_update_id": max_update_id + 1 if max_update_id else offset,
        }
    if first_live_poll_without_state:
        next_update_id = max_update_id + 1 if max_update_id else offset
        write_telegram_feedback_state(paths["telegram_feedback_state"], {"next_update_id": next_update_id, "updated_at": utc_now()})
        return {
            "dry_run": False,
            "primed": True,
            "updates_seen": len(typed_updates),
            "decisions_found": len(rows),
            "decisions_written": 0,
            "events_written": 0,
            "filter_updates_written": 0,
            "callbacks_answered": 0,
            "ignored_count": ignored_count,
            "next_update_id": next_update_id,
        }
    result = apply_operator_feedback_rows(data_dir, week, rows, "telegram-feedback") if rows else {
        "decisions_written": 0,
        "events_written": 0,
        "filter_updates_written": 0,
        "digest_path": "",
    }
    for update in typed_updates:
        append_jsonl(paths["telegram_feedback_updates"], {"created_at": utc_now(), "week": week, "update_id": update.get("update_id"), "handled": True})
    answer = callback_answerer if callback_answerer is not None else telegram_answer_callback
    answered = 0
    if resolved_token:
        for callback_id in callback_ids:
            answer(resolved_token, api_base, callback_id, "Feedback recorded.", timeout)
            answered += 1
    if max_update_id:
        write_telegram_feedback_state(paths["telegram_feedback_state"], {"next_update_id": max_update_id + 1, "updated_at": utc_now()})
    result.update(
        {
            "dry_run": False,
            "updates_seen": len(typed_updates),
            "decisions_found": len(rows),
            "callbacks_answered": answered,
            "ignored_count": ignored_count,
            "next_update_id": max_update_id + 1 if max_update_id else offset,
        }
    )
    return result


def increment_nested(table: dict[str, dict[str, int]], key: str, status: str) -> None:
    normalized_key = key or "unknown"
    table.setdefault(normalized_key, {})
    table[normalized_key][status] = table[normalized_key].get(status, 0) + 1


def source_lane_yield(
    candidates: list[dict[str, object]],
    statuses: dict[str, str],
) -> tuple[dict[str, dict[str, int]], dict[str, dict[str, int]]]:
    source_yield: dict[str, dict[str, int]] = {}
    lane_yield: dict[str, dict[str, int]] = {}
    for candidate in candidates:
        candidate_id = normalize_text(candidate.get("candidate_id"))
        status = statuses.get(candidate_id, "raw")
        increment_nested(source_yield, normalize_text(candidate.get("source")) or "unknown", status)
        lanes = active_lane_codes(candidate)
        if lanes:
            for lane in lanes:
                increment_nested(lane_yield, lane, status)
        else:
            increment_nested(lane_yield, "none", status)
    return source_yield, lane_yield


def reason_histogram(events: list[dict[str, object]]) -> dict[str, int]:
    histogram: dict[str, int] = {}
    for event in events:
        for reason in label_list(event, "reason_codes"):
            histogram[reason] = histogram.get(reason, 0) + 1
    return histogram


def proof_card_conversion(candidates: list[dict[str, object]], statuses: dict[str, str]) -> dict[str, object]:
    total = len(candidates)
    proof_like = [
        candidate
        for candidate in candidates
        if statuses.get(normalize_text(candidate.get("candidate_id")), "raw")
        in {"proof-card", "PRD-lite", "operator-proof-approved"}
    ]
    return {
        "candidate_count": total,
        "proof_card_count": len(proof_like),
        "conversion_rate": round(len(proof_like) / total, 4) if total else 0,
        "candidate_ids": [normalize_text(candidate.get("candidate_id")) for candidate in proof_like],
    }


def open_filter_updates(filter_updates: list[dict[str, object]]) -> list[dict[str, object]]:
    return [row for row in filter_updates if normalize_text(row.get("status")) == "open"]


def write_calibration_report(data_dir: Path, week: str) -> Path:
    paths = ensure_layout(data_dir, week)
    candidates = latest_candidates_for_week(data_dir, week)
    events = read_jsonl(paths["events"])
    statuses = status_by_candidate_for_week(events, week)
    source_yield, lane_yield = source_lane_yield(candidates, statuses)
    histogram = reason_histogram([event for event in events if normalize_text(event.get("week")) == week])
    conversion = proof_card_conversion(candidates, statuses)
    filter_updates = open_filter_updates(read_jsonl(paths["filter_updates"]))
    calibration = {
        "calibration_id": f"cal_{uuid.uuid4().hex}",
        "week": week,
        "created_at": utc_now(),
        "candidate_count": len(candidates),
        "source_yield": source_yield,
        "lane_yield": lane_yield,
        "reason_histogram": histogram,
        "proof_card_conversion": conversion,
        "open_filter_updates": filter_updates,
        "filter_drift_notes": [
            normalize_text(row.get("proposed_change")) for row in filter_updates if normalize_text(row.get("proposed_change"))
        ],
    }
    append_jsonl(paths["calibrations"], calibration)

    report_path = paths["reports"] / f"{week}-calibration.md"
    lines = [
        f"# Opportunity Scanner Calibration - {week}",
        "",
        f"- Generated at: `{calibration['created_at']}`",
        f"- Candidate count: `{len(candidates)}`",
        f"- Proof-card conversion: `{conversion['proof_card_count']}/{conversion['candidate_count']}`",
        "",
        "## Source-Lane Yield",
        "",
        "### Sources",
        "",
    ]
    if source_yield:
        for source, counts in sorted(source_yield.items()):
            rendered = ", ".join(f"{status}={count}" for status, count in sorted(counts.items()))
            lines.append(f"- `{source}`: {rendered}")
    else:
        lines.append("- none")
    lines.extend(["", "### Search Lanes", ""])
    if lane_yield:
        for lane, counts in sorted(lane_yield.items()):
            rendered = ", ".join(f"{status}={count}" for status, count in sorted(counts.items()))
            lines.append(f"- `{lane}`: {rendered}")
    else:
        lines.append("- none")
    lines.extend(["", "## Reason-Code Histogram", ""])
    if histogram:
        for reason, count in sorted(histogram.items(), key=lambda item: (-item[1], item[0])):
            lines.append(f"- `{reason}`: {count}")
    else:
        lines.append("- none")
    lines.extend(["", "## Proof-Card Conversion", ""])
    if conversion["candidate_ids"]:
        for candidate_id in conversion["candidate_ids"]:
            lines.append(f"- `{candidate_id}`")
    else:
        lines.append("- none")
    lines.extend(["", "## Filter Drift Notes", ""])
    if filter_updates:
        for row in filter_updates:
            lines.append(
                f"- `{row.get('update_id')}` {row.get('proposed_change') or 'unknown'} "
                f"(target: `{row.get('target_doc') or 'unknown'}`)"
            )
    else:
        lines.append("- none")
    report_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return report_path


def rescore_candidates(data_dir: Path, source_week: str, target_week: str, with_labels: bool) -> dict[str, object]:
    source_paths = ensure_layout(data_dir, source_week)
    target_paths = ensure_layout(data_dir, target_week)
    source_raw = source_paths["raw_week"]
    if not source_raw.exists():
        raise FileNotFoundError(f"No raw candidates for source week: {source_week}")
    ingest_result = ingest_candidates(source_raw, data_dir, target_week)
    label_result: dict[str, object] = {}
    if with_labels:
        label_result = label_candidates(data_dir, target_week)
    rescore = {
        "rescore_id": f"rsc_{uuid.uuid4().hex}",
        "created_at": utc_now(),
        "source_week": source_week,
        "target_week": target_week,
        "source_raw": str(source_raw),
        "with_labels": with_labels,
        "ingest": ingest_result,
        "label": label_result,
    }
    append_jsonl(target_paths["rescore_runs"], rescore)
    report_path = write_calibration_report(data_dir, target_week)
    return {
        "rescore_id": rescore["rescore_id"],
        "source_week": source_week,
        "target_week": target_week,
        "ingest": ingest_result,
        "label": label_result,
        "calibration_report_path": str(report_path),
    }


def esc(value: object) -> str:
    return html.escape(normalize_text(value), quote=True)


def dashboard_link(base: Path, target: Path, label: str) -> str:
    if target.exists():
        href = os.path.relpath(target, base.parent)
        return f'<a href="{esc(href)}">{esc(label)}</a>'
    return esc(label)


def write_dashboard(data_dir: Path, week: str) -> Path:
    paths = ensure_layout(data_dir, week)
    candidates = latest_candidates_for_week(data_dir, week)
    events = read_jsonl(paths["events"])
    statuses = status_by_candidate_for_week(events, week)
    cards = latest_row_by_candidate_for_week(read_jsonl(paths["opportunity_cards"]), week)
    aggregations = latest_row_by_candidate_for_week(read_jsonl(paths["aggregations"]), week)
    counts = grouped_status_counts(
        {normalize_text(candidate.get("candidate_id")): statuses.get(normalize_text(candidate.get("candidate_id")), "raw") for candidate in candidates}
    )
    dashboard_path = paths["reports"] / f"{week}-dashboard.html"
    report_links = [
        (paths["reports"] / f"{week}-batch-report.md", "batch"),
        (paths["reports"] / f"{week}-deep-review.md", "deep review"),
        (paths["reports"] / f"{week}-council-aggregation.md", "aggregation"),
        (paths["reports"] / f"{week}-digest.md", "digest"),
        (paths["reports"] / f"{week}-calibration.md", "calibration"),
    ]
    rows: list[str] = []
    for candidate in sorted(candidates, key=lambda row: normalize_text(row.get("project_name")).lower()):
        candidate_id = normalize_text(candidate.get("candidate_id"))
        card = cards.get(candidate_id, {})
        aggregation = aggregations.get(candidate_id, {})
        status = statuses.get(candidate_id, "raw")
        verdict = digest_verdict(candidate_id, statuses, card, aggregation)
        next_action = digest_next_action(card, aggregation)
        evidence = paths["evidence"] / f"{candidate_id}.md"
        rows.append(
            "<tr>"
            f"<td><code>{esc(status)}</code></td>"
            f"<td>{esc(candidate.get('project_name'))}</td>"
            f"<td>{esc(candidate.get('source'))}</td>"
            f"<td><code>{esc(verdict)}</code></td>"
            f"<td>{esc(next_action)}</td>"
            f"<td>{dashboard_link(dashboard_path, evidence, 'evidence')}</td>"
            "</tr>"
        )
    count_items = "".join(f"<li><code>{esc(status)}</code>: {count}</li>" for status, count in sorted(counts.items()))
    links = " ".join(dashboard_link(dashboard_path, path, label) for path, label in report_links)
    html_payload = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Opportunity Scanner Dashboard {esc(week)}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 24px; color: #202124; background: #f8f7f4; }}
    main {{ max-width: 1180px; margin: 0 auto; }}
    h1 {{ font-size: 28px; margin-bottom: 8px; }}
    .meta, .links {{ color: #5f6368; margin-bottom: 18px; }}
    .panel {{ background: #fff; border: 1px solid #ddd9d0; border-radius: 8px; padding: 16px; margin: 16px 0; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; }}
    th, td {{ text-align: left; border-bottom: 1px solid #e6e1d8; padding: 10px; vertical-align: top; font-size: 14px; }}
    th {{ font-size: 12px; text-transform: uppercase; color: #5f6368; letter-spacing: 0; }}
    code {{ background: #f1eee7; padding: 2px 4px; border-radius: 4px; }}
    a {{ color: #0b57d0; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
  </style>
</head>
<body>
  <main>
    <h1>Opportunity Scanner Dashboard - {esc(week)}</h1>
    <div class="meta">Generated at <code>{esc(utc_now())}</code>. Candidate count: <code>{len(candidates)}</code>.</div>
    <div class="panel">
      <h2>Status Counts</h2>
      <ul>{count_items or '<li>none</li>'}</ul>
    </div>
    <div class="panel links">
      <h2>Reports</h2>
      {links}
    </div>
    <div class="panel">
      <h2>Candidates</h2>
      <table>
        <thead><tr><th>Status</th><th>Project</th><th>Source</th><th>Verdict</th><th>Next Action</th><th>Evidence</th></tr></thead>
        <tbody>{''.join(rows) or '<tr><td colspan="6">none</td></tr>'}</tbody>
      </table>
    </div>
  </main>
</body>
</html>
"""
    dashboard_path.write_text(html_payload, encoding="utf-8")
    return dashboard_path


def grouped_status_counts(statuses: dict[str, str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for status in statuses.values():
        counts[status] = counts.get(status, 0) + 1
    return counts


def latest_candidates_for_week(data_dir: Path, week: str) -> list[dict[str, object]]:
    paths = ensure_layout(data_dir, week)
    week_rows = read_jsonl(paths["raw_week"])
    latest: dict[str, dict[str, object]] = {}
    for row in week_rows:
        latest[normalize_text(row.get("candidate_id"))] = row
    return list(latest.values())


def github_owner_repo(repo: str) -> tuple[str, str]:
    cleaned = normalize_text(repo).removeprefix("https://github.com/").strip("/")
    parts = [part for part in cleaned.split("/") if part]
    if len(parts) != 2:
        raise ValueError("GitHub repo must be in owner/name form")
    return parts[0], parts[1]


def github_issue_marker(candidate_id: str) -> str:
    return f"{GITHUB_ISSUE_MARKER_PREFIX}{candidate_id} -->"


def github_issue_title(candidate: dict[str, object], verdict: str) -> str:
    name = normalize_text(candidate.get("project_name")) or "unknown opportunity"
    title = f"Opportunity: {name} [{verdict}]"
    return truncate_text(title, 120)


def issue_label_slug(value: object) -> str:
    text = normalize_text(value).lower()
    text = re.sub(r"[^a-z0-9._:-]+", "-", text).strip("-")
    return text[:45] or "unknown"


def github_issue_number_from_url(value: object) -> int | None:
    text = normalize_text(value).rstrip("/")
    if not text:
        return None
    tail = text.rsplit("/", 1)[-1]
    if not tail.isdigit():
        return None
    return int(tail)


def github_issue_number(issue: dict[str, object]) -> int | None:
    raw_number = issue.get("number")
    if raw_number in ("", None):
        raw_number = issue.get("issue_number")
    if isinstance(raw_number, int):
        return raw_number
    text_number = normalize_text(raw_number)
    if text_number.isdigit():
        return int(text_number)
    return github_issue_number_from_url(issue.get("issue_url")) or github_issue_number_from_url(issue.get("html_url")) or github_issue_number_from_url(issue.get("url"))


def issue_labels_for_candidate(
    candidate: dict[str, object],
    card: dict[str, object],
    aggregation: dict[str, object],
    verdict: str,
) -> list[str]:
    labels = ["opportunity-scanner", f"verdict:{issue_label_slug(verdict)}"]
    source = issue_label_slug(candidate.get("source"))
    if source:
        labels.append(f"source:{source}")
    if verdict == "watchlist":
        labels.append("needs:evidence")
    elif verdict == "proof-card":
        labels.extend(["needs:operator-review", "needs:proof"])
    elif verdict == "PRD-lite":
        labels.append("needs:prd")
    elif verdict == "operator-proof-approved":
        labels.append("needs:proof")

    reason_codes = label_list(aggregation, "reason_codes") if aggregation else label_list(card, "reason_codes")
    reason_blob = " ".join(reason_codes).lower()
    risk_map = {
        "risk:legal": ("license", "legal", "rights", "tos", "brand", "copy"),
        "risk:platform": ("platform", "api", "dependency", "single-platform"),
        "risk:support": ("support", "onboarding", "integration", "custom"),
        "risk:distribution": ("distribution", "first-100", "channel", "reach"),
        "risk:payment": ("payment", "money", "monetization", "pricing"),
    }
    for label, terms in risk_map.items():
        if any(term in reason_blob for term in terms):
            labels.append(label)

    deduped: list[str] = []
    for label in labels:
        cleaned = label[:50]
        if cleaned not in deduped:
            deduped.append(cleaned)
    return deduped


def label_spec(label: str) -> tuple[str, str]:
    if label in GITHUB_ISSUE_LABEL_SPECS:
        return GITHUB_ISSUE_LABEL_SPECS[label]
    if label.startswith("verdict:"):
        return "1f883d", "Opportunity Scanner verdict."
    if label.startswith("source:"):
        return "c5def5", "Opportunity Scanner source lane."
    return "ededed", "Opportunity Scanner label."


def markdown_bullets(values: list[str], limit: int = 5) -> list[str]:
    rows: list[str] = []
    for value in values[:limit]:
        text = truncate_text(value, 260)
        if text:
            rows.append(f"- {text}")
    return rows or ["- none"]


def github_issue_body(
    candidate: dict[str, object],
    card: dict[str, object],
    aggregation: dict[str, object],
    verdict: str,
    week: str,
) -> str:
    candidate_id = normalize_text(candidate.get("candidate_id"))
    raw_text = candidate.get("raw_text") if isinstance(candidate.get("raw_text"), dict) else {}
    issue_excerpts = raw_text.get("issue_excerpts") if isinstance(raw_text.get("issue_excerpts"), list) else []
    discussion_excerpts = raw_text.get("discussion_excerpts") if isinstance(raw_text.get("discussion_excerpts"), list) else []
    reason_codes = label_list(aggregation, "reason_codes") if aggregation else label_list(card, "reason_codes")
    strict_total = strict_total_from_card(card) if card else 0
    money_signals = []
    if card:
        strongest = card.get("strongest_signals")
        if isinstance(strongest, dict) and isinstance(strongest.get("money"), list):
            money_signals = [normalize_text(item) for item in strongest.get("money", [])]
    first_channel = normalize_text(card.get("first_async_channel")) if card else ""
    main_blocker = ""
    if aggregation:
        blockers = safe_list(aggregation.get("missing_evidence")) or safe_list(aggregation.get("vetoes"))
        if blockers:
            main_blocker = truncate_text(blockers[0], 180)
    if not main_blocker and reason_codes:
        main_blocker = reason_codes[0]
    lines = [
        github_issue_marker(candidate_id),
        GITHUB_ISSUE_MANAGED_MARKER,
        "",
        "## Opportunity",
        "",
        f"- Verdict: **{verdict}**",
        f"- Strict score: `{strict_total}/34`" if strict_total else "- Strict score: `unknown`",
        f"- Source: `{normalize_text(candidate.get('source')) or 'unknown'}`",
        f"- License: `{normalize_text(candidate.get('license')) or 'unknown'}`",
        "",
        "## Product Read",
        "",
        f"- Buyer: {normalize_text(card.get('target_buyer')) if card else 'unknown'}",
        f"- Painful job: {normalize_text(card.get('painful_job')) if card else 'unknown'}",
        f"- Product angle: {normalize_text(card.get('product_angle')) if card else 'unknown'}",
        f"- Money signal: {money_signals[0] if money_signals else 'unknown'}",
        f"- First-100 lane: {first_channel or 'unknown'}",
        f"- Main blocker: {main_blocker or 'unknown'}",
        f"- Next action: {digest_next_action(card, aggregation)}",
        "",
        "## Evidence",
        "",
        f"- Project URL: {normalize_url(candidate.get('project_url')) or 'unknown'}",
        f"- Source URL: {normalize_url(candidate.get('source_url')) or 'unknown'}",
        f"- Description: {truncate_text(candidate.get('short_description'), 500) or 'unknown'}",
        "",
        "Issue excerpts:",
        "",
        *markdown_bullets([normalize_text(item) for item in issue_excerpts]),
        "",
        "Discussion excerpts:",
        "",
        *markdown_bullets([normalize_text(item) for item in discussion_excerpts]),
        "",
        "## Guardrails",
        "",
        "- This issue is a backlog mirror, not a build approval.",
        "- Build/proof work still requires Operator approval or a separate proof-card decision.",
        "- Keep evidence and assumptions separate when updating this issue.",
        f"- Scanner week: `{week}`",
        "",
    ]
    return "\n".join(lines)


def github_issue_mirror_rows_by_candidate(rows: list[dict[str, object]], repo: str) -> dict[str, dict[str, object]]:
    latest: dict[str, dict[str, object]] = {}
    for row in rows:
        if normalize_text(row.get("repo")).lower() != repo.lower():
            continue
        candidate_id = normalize_text(row.get("candidate_id"))
        if candidate_id and normalize_text(row.get("issue_url")):
            latest[candidate_id] = row
    return latest


def github_search_issue_by_candidate(client: object, repo: str, candidate_id: str) -> dict[str, object]:
    query = f"repo:{repo} type:issue in:body {candidate_id}"
    result = client.get_json("/search/issues", {"q": query, "per_page": 5})
    items = safe_list(result.get("items")) if isinstance(result, dict) else []
    marker = github_issue_marker(candidate_id)
    for item in items:
        if not isinstance(item, dict):
            continue
        title = normalize_text(item.get("title"))
        body_text = normalize_text(item.get("body"))
        if candidate_id in title or candidate_id in body_text or marker in body_text:
            return item
    for item in items:
        if isinstance(item, dict):
            return item
    return {}


def github_create_issue(client: object, repo: str, title: str, body: str) -> dict[str, object]:
    owner, name = github_owner_repo(repo)
    result = client.post_json(f"/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(name)}/issues", {"title": title, "body": body})
    return result if isinstance(result, dict) else {}


def github_update_issue(client: object, repo: str, issue_number: int, title: str, body: str, labels: list[str]) -> dict[str, object]:
    owner, name = github_owner_repo(repo)
    result = client.patch_json(
        f"/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(name)}/issues/{issue_number}",
        {"title": title, "body": body, "labels": labels},
    )
    return result if isinstance(result, dict) else {}


def github_create_issue_with_labels(client: object, repo: str, title: str, body: str, labels: list[str]) -> dict[str, object]:
    owner, name = github_owner_repo(repo)
    result = client.post_json(
        f"/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(name)}/issues",
        {"title": title, "body": body, "labels": labels},
    )
    return result if isinstance(result, dict) else {}


def github_create_issue_comment(client: object, repo: str, issue_number: int, body: str) -> dict[str, object]:
    owner, name = github_owner_repo(repo)
    result = client.post_json(
        f"/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(name)}/issues/{issue_number}/comments",
        {"body": body},
    )
    return result if isinstance(result, dict) else {}


def github_ensure_issue_label(client: object, repo: str, label: str) -> None:
    owner, name = github_owner_repo(repo)
    color, description = label_spec(label)
    try:
        client.post_json(
            f"/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(name)}/labels",
            {"name": label, "color": color, "description": description},
        )
    except urllib.error.HTTPError as exc:
        if exc.code != 422:
            raise


def github_ensure_issue_labels(client: object, repo: str, labels: list[str]) -> int:
    ensured = 0
    for label in labels:
        github_ensure_issue_label(client, repo, label)
        ensured += 1
    return ensured


def github_issue_row(
    candidate: dict[str, object],
    week: str,
    repo: str,
    verdict: str,
    issue: dict[str, object],
    action: str,
    labels: list[str] | None = None,
) -> dict[str, object]:
    return {
        "mirror_id": f"mir_{uuid.uuid4().hex}",
        "created_at": utc_now(),
        "week": week,
        "repo": repo,
        "candidate_id": normalize_text(candidate.get("candidate_id")),
        "candidate_name": normalize_text(candidate.get("project_name")),
        "verdict": verdict,
        "action": action,
        "issue_number": github_issue_number(issue),
        "issue_url": normalize_text(issue.get("html_url")) or normalize_text(issue.get("url")),
        "issue_state": normalize_text(issue.get("state")),
        "issue_title": normalize_text(issue.get("title")),
        "labels": labels or [],
    }


def mirrorable_candidates(
    data_dir: Path,
    week: str,
    verdicts: set[str],
) -> list[tuple[dict[str, object], dict[str, object], dict[str, object], str]]:
    paths = ensure_layout(data_dir, week)
    candidates = latest_candidates_for_week(data_dir, week)
    events = read_jsonl(paths["events"])
    statuses = status_by_candidate_for_week(events, week)
    cards = latest_row_by_candidate_for_week(read_jsonl(paths["opportunity_cards"]), week)
    aggregations = latest_row_by_candidate_for_week(read_jsonl(paths["aggregations"]), week)
    rows: list[tuple[dict[str, object], dict[str, object], dict[str, object], str]] = []
    for candidate in candidates:
        candidate_id = normalize_text(candidate.get("candidate_id"))
        card = cards.get(candidate_id, {})
        aggregation = aggregations.get(candidate_id, {})
        verdict = digest_verdict(candidate_id, statuses, card, aggregation)
        if verdict in verdicts and (card or aggregation):
            rows.append((candidate, card, aggregation, verdict))
    rows.sort(key=lambda item: (item[3], normalize_text(item[0].get("project_name")).lower()))
    return rows


def github_transition_comment(candidate: dict[str, object], previous_verdict: str, verdict: str, week: str) -> str:
    name = normalize_text(candidate.get("project_name")) or "this candidate"
    return "\n".join(
        [
            f"Opportunity Scanner updated **{name}** for `{week}`.",
            "",
            f"- Previous verdict: `{previous_verdict or 'unknown'}`",
            f"- Current verdict: `{verdict}`",
            "- This is a mirror update, not a build approval.",
        ]
    )


def mirror_github_issues(
    data_dir: Path,
    week: str,
    repo: str,
    verdicts: list[str],
    dry_run: bool,
    token: str,
    api_base: str,
    client: object | None = None,
) -> dict[str, object]:
    normalized_repo = "/".join(github_owner_repo(repo))
    selected_verdicts = {normalize_text(verdict) for verdict in verdicts if normalize_text(verdict)}
    paths = ensure_layout(data_dir, week)
    existing_rows = github_issue_mirror_rows_by_candidate(read_jsonl(paths["github_issue_mirrors"]), normalized_repo)
    candidates = mirrorable_candidates(data_dir, week, selected_verdicts)
    gh_client = client if client is not None else GitHubApiClient(token=token, api_base=api_base, timeout=HTTP_TIMEOUT_SECONDS)
    results: list[dict[str, object]] = []
    created_count = 0
    linked_count = 0
    skipped_count = 0
    updated_count = 0
    commented_count = 0
    labels_ensured_count = 0
    dry_run_count = 0

    for candidate, card, aggregation, verdict in candidates:
        candidate_id = normalize_text(candidate.get("candidate_id"))
        title = github_issue_title(candidate, verdict)
        body = github_issue_body(candidate, card, aggregation, verdict, week)
        labels = issue_labels_for_candidate(candidate, card, aggregation, verdict)
        existing = existing_rows.get(candidate_id)
        found = existing
        found_from_existing_ledger = bool(existing)
        if not found:
            found = github_search_issue_by_candidate(gh_client, normalized_repo, candidate_id)
        issue_number = github_issue_number(found)
        if found and issue_number is None:
            remote_found = github_search_issue_by_candidate(gh_client, normalized_repo, candidate_id)
            if remote_found:
                found = remote_found
                issue_number = github_issue_number(found)
        previous_verdict = normalize_text(found.get("verdict"))
        if found:
            action = "updated-existing" if found_from_existing_ledger else "linked-and-updated-github"
            if dry_run:
                dry_run_count += 1
                results.append(
                    {
                        "candidate_id": candidate_id,
                        "candidate_name": normalize_text(candidate.get("project_name")),
                        "verdict": verdict,
                        "action": f"would-{action}",
                        "issue_url": found.get("issue_url") or found.get("html_url"),
                        "labels": labels,
                    }
                )
                continue
            if issue_number is None:
                skipped_count += 1
                results.append(
                    {
                        "candidate_id": candidate_id,
                        "candidate_name": normalize_text(candidate.get("project_name")),
                        "verdict": verdict,
                        "action": "skipped-missing-issue-number",
                        "issue_url": found.get("issue_url") or found.get("html_url"),
                    }
                )
                continue
            labels_ensured_count += github_ensure_issue_labels(gh_client, normalized_repo, labels)
            updated = github_update_issue(gh_client, normalized_repo, issue_number, title, body, labels)
            updated.setdefault("number", issue_number)
            if not normalize_text(updated.get("html_url")):
                updated["html_url"] = found.get("issue_url") or found.get("html_url") or found.get("url")
            row = github_issue_row(candidate, week, normalized_repo, verdict, updated, action, labels)
            append_jsonl(paths["github_issue_mirrors"], row)
            if found_from_existing_ledger:
                updated_count += 1
            else:
                linked_count += 1
            if previous_verdict and previous_verdict != verdict:
                github_create_issue_comment(gh_client, normalized_repo, issue_number, github_transition_comment(candidate, previous_verdict, verdict, week))
                commented_count += 1
            results.append(row)
            continue
        if dry_run:
            dry_run_count += 1
            results.append(
                {
                    "candidate_id": candidate_id,
                    "candidate_name": normalize_text(candidate.get("project_name")),
                    "verdict": verdict,
                    "action": "would-create",
                    "title": title,
                    "labels": labels,
                }
            )
            continue
        labels_ensured_count += github_ensure_issue_labels(gh_client, normalized_repo, labels)
        created = github_create_issue_with_labels(gh_client, normalized_repo, title, body, labels)
        row = github_issue_row(candidate, week, normalized_repo, verdict, created, "created", labels)
        append_jsonl(paths["github_issue_mirrors"], row)
        created_count += 1
        results.append(row)

    return {
        "repo": normalized_repo,
        "week": week,
        "dry_run": dry_run,
        "verdicts": sorted(selected_verdicts),
        "candidate_count": len(candidates),
        "created_count": created_count,
        "linked_count": linked_count,
        "updated_count": updated_count,
        "commented_count": commented_count,
        "labels_ensured_count": labels_ensured_count,
        "skipped_count": skipped_count,
        "dry_run_count": dry_run_count,
        "results": results,
    }


def github_project_rows_by_issue(
    rows: list[dict[str, object]],
    project_key: str,
    project_owner: str = "",
    project_number: int = 0,
    project_id: str = "",
) -> dict[str, dict[str, object]]:
    latest: dict[str, dict[str, object]] = {}
    for row in rows:
        row_project_number = row.get("project_number")
        row_number = row_project_number if isinstance(row_project_number, int) else int(str(row_project_number)) if str(row_project_number).isdigit() else 0
        matches_key = normalize_text(row.get("project_key")) == project_key
        matches_id = bool(project_id) and normalize_text(row.get("project_id")) == project_id
        matches_owner_number = bool(project_owner) and normalize_text(row.get("project_owner")) == project_owner and row_number == project_number
        if not (matches_key or matches_id or matches_owner_number):
            continue
        issue_url = normalize_text(row.get("issue_url"))
        if issue_url and normalize_text(row.get("project_item_id")):
            latest[issue_url] = row
    return latest


def github_project_key(owner: str, number: int, project_id: str = "") -> str:
    if project_id:
        return f"id:{project_id}"
    return f"{owner}#{number}"


def github_project_issue_rows(data_dir: Path, week: str, repo: str) -> list[dict[str, object]]:
    paths = ensure_layout(data_dir, week)
    normalized_repo = "/".join(github_owner_repo(repo))
    rows = github_issue_mirror_rows_by_candidate(read_jsonl(paths["github_issue_mirrors"]), normalized_repo)
    result: list[dict[str, object]] = []
    for row in rows.values():
        issue_url = normalize_text(row.get("issue_url"))
        issue_number = github_issue_number(row)
        if issue_url and issue_number is not None:
            result.append(row)
    result.sort(key=lambda row: (normalize_text(row.get("verdict")), normalize_text(row.get("candidate_name"))))
    return result


def github_resolve_project_id(client: object, owner: str, number: int, project_id: str = "") -> dict[str, object]:
    if project_id:
        return {"project_id": project_id, "project_title": "", "project_url": ""}
    last_error = ""
    for owner_kind in ("user", "organization"):
        query = f"""
        query($login: String!, $number: Int!) {{
          {owner_kind}(login: $login) {{
            projectV2(number: $number) {{ id title url }}
          }}
        }}
        """
        try:
            payload = client.graphql(query, {"login": owner, "number": number})
        except GitHubApiError as exc:
            last_error = str(exc)
            continue
        data = safe_dict(payload.get("data"))
        project = safe_dict(safe_dict(data.get(owner_kind)).get("projectV2"))
        resolved_id = normalize_text(project.get("id"))
        if resolved_id:
            return {
                "project_id": resolved_id,
                "project_title": normalize_text(project.get("title")),
                "project_url": normalize_text(project.get("url")),
            }
    detail = f": {last_error}" if last_error else ""
    raise GitHubApiError(f"Could not resolve GitHub Project v2 {owner}#{number}{detail}")


def github_issue_content_id(client: object, repo: str, issue_number: int) -> dict[str, object]:
    owner, name = github_owner_repo(repo)
    query = """
    query($owner: String!, $name: String!, $number: Int!) {
      repository(owner: $owner, name: $name) {
        issue(number: $number) { id number title url }
      }
    }
    """
    payload = client.graphql(query, {"owner": owner, "name": name, "number": issue_number})
    issue = safe_dict(safe_dict(safe_dict(payload.get("data")).get("repository")).get("issue"))
    issue_id = normalize_text(issue.get("id"))
    if not issue_id:
        raise GitHubApiError(f"Could not resolve issue node id for {repo}#{issue_number}")
    return {
        "content_id": issue_id,
        "issue_number": issue.get("number"),
        "issue_url": normalize_text(issue.get("url")),
        "issue_title": normalize_text(issue.get("title")),
    }


def github_add_project_item(client: object, project_id: str, content_id: str) -> str:
    query = """
    mutation($projectId: ID!, $contentId: ID!) {
      addProjectV2ItemById(input: {projectId: $projectId, contentId: $contentId}) {
        item { id }
      }
    }
    """
    payload = client.graphql(query, {"projectId": project_id, "contentId": content_id})
    item_id = normalize_text(safe_dict(safe_dict(safe_dict(payload.get("data")).get("addProjectV2ItemById")).get("item")).get("id"))
    if not item_id:
        raise GitHubApiError("GitHub Project v2 add item did not return an item id")
    return item_id


def github_project_item_row(
    week: str,
    project_owner: str,
    project_number: int,
    project_id: str,
    project_title: str,
    project_url: str,
    mirror_row: dict[str, object],
    project_item_id: str,
    action: str,
) -> dict[str, object]:
    return {
        "sync_id": f"gp_{uuid.uuid4().hex}",
        "created_at": utc_now(),
        "week": week,
        "project_owner": project_owner,
        "project_number": project_number,
        "project_id": project_id,
        "project_key": github_project_key(project_owner, project_number, project_id),
        "project_title": project_title,
        "project_url": project_url,
        "candidate_id": normalize_text(mirror_row.get("candidate_id")),
        "candidate_name": normalize_text(mirror_row.get("candidate_name")),
        "verdict": normalize_text(mirror_row.get("verdict")),
        "issue_number": github_issue_number(mirror_row),
        "issue_url": normalize_text(mirror_row.get("issue_url")),
        "project_item_id": project_item_id,
        "action": action,
    }


def sync_github_project(
    data_dir: Path,
    week: str,
    repo: str,
    project_owner: str,
    project_number: int,
    project_id: str,
    dry_run: bool,
    token: str,
    api_base: str,
    client: object | None = None,
) -> dict[str, object]:
    if not project_owner and not project_id:
        raise ValueError("Project sync requires --project-owner or --project-id")
    if project_number <= 0 and not project_id:
        raise ValueError("Project sync requires --project-number when --project-id is not provided")
    paths = ensure_layout(data_dir, week)
    project_key = github_project_key(project_owner, project_number, project_id)
    existing = github_project_rows_by_issue(read_jsonl(paths["github_project_items"]), project_key, project_owner, project_number, project_id)
    issue_rows = github_project_issue_rows(data_dir, week, repo)
    results: list[dict[str, object]] = []
    skipped_count = 0
    dry_run_count = 0
    added_count = 0
    if dry_run:
        for row in issue_rows:
            issue_url = normalize_text(row.get("issue_url"))
            action = "skipped-existing-project-item" if issue_url in existing else "would-add"
            if action.startswith("skipped"):
                skipped_count += 1
            else:
                dry_run_count += 1
            results.append(
                {
                    "candidate_id": normalize_text(row.get("candidate_id")),
                    "candidate_name": normalize_text(row.get("candidate_name")),
                    "issue_url": issue_url,
                    "verdict": normalize_text(row.get("verdict")),
                    "action": action,
                }
            )
        return {
            "week": week,
            "repo": "/".join(github_owner_repo(repo)),
            "project_owner": project_owner,
            "project_number": project_number,
            "project_id": project_id,
            "project_key": project_key,
            "dry_run": True,
            "candidate_issue_count": len(issue_rows),
            "added_count": 0,
            "skipped_count": skipped_count,
            "dry_run_count": dry_run_count,
            "results": results,
        }

    gh_client = client if client is not None else GitHubApiClient(token=token, api_base=api_base, timeout=HTTP_TIMEOUT_SECONDS)
    project = github_resolve_project_id(gh_client, project_owner, project_number, project_id)
    resolved_project_id = normalize_text(project.get("project_id"))
    resolved_project_key = github_project_key(project_owner, project_number, resolved_project_id)
    existing = github_project_rows_by_issue(
        read_jsonl(paths["github_project_items"]),
        resolved_project_key,
        project_owner,
        project_number,
        resolved_project_id,
    )
    for row in issue_rows:
        issue_url = normalize_text(row.get("issue_url"))
        issue_number = github_issue_number(row)
        if issue_url in existing:
            skipped_count += 1
            results.append(
                {
                    "candidate_id": normalize_text(row.get("candidate_id")),
                    "candidate_name": normalize_text(row.get("candidate_name")),
                    "issue_url": issue_url,
                    "verdict": normalize_text(row.get("verdict")),
                    "action": "skipped-existing-project-item",
                    "project_item_id": existing[issue_url].get("project_item_id"),
                }
            )
            continue
        if issue_number is None:
            skipped_count += 1
            results.append({"issue_url": issue_url, "action": "skipped-missing-issue-number"})
            continue
        content = github_issue_content_id(gh_client, repo, issue_number)
        project_item_id = github_add_project_item(gh_client, resolved_project_id, normalize_text(content.get("content_id")))
        item_row = github_project_item_row(
            week,
            project_owner,
            project_number,
            resolved_project_id,
            normalize_text(project.get("project_title")),
            normalize_text(project.get("project_url")),
            row,
            project_item_id,
            "added",
        )
        append_jsonl(paths["github_project_items"], item_row)
        added_count += 1
        results.append(item_row)
    return {
        "week": week,
        "repo": "/".join(github_owner_repo(repo)),
        "project_owner": project_owner,
        "project_number": project_number,
        "project_id": resolved_project_id,
        "project_key": resolved_project_key,
        "dry_run": False,
        "candidate_issue_count": len(issue_rows),
        "added_count": added_count,
        "skipped_count": skipped_count,
        "dry_run_count": 0,
        "results": results,
    }


def label_missing_summary(label: dict[str, object]) -> str:
    missing = label.get("missing_evidence")
    if not isinstance(missing, list) or not missing:
        return "none"
    summaries: list[str] = []
    for item in missing[:3]:
        if not isinstance(item, dict):
            continue
        field = normalize_text(item.get("field")) or "unknown"
        severity = normalize_text(item.get("severity")) or "unknown"
        next_check = normalize_text(item.get("next_check")) or "unknown"
        summaries.append(f"{field} ({severity}): {next_check}")
    return " | ".join(summaries) if summaries else "unknown"


def label_uncertainty_summary(label: dict[str, object]) -> str:
    notes = label.get("uncertainty_notes")
    if not isinstance(notes, list) or not notes:
        return "unknown"
    return normalize_text(notes[0]) or "unknown"


def label_next_check(label: dict[str, object]) -> str:
    missing = label.get("missing_evidence")
    if not isinstance(missing, list) or not missing:
        return "none"
    high_items = [item for item in missing if isinstance(item, dict) and normalize_text(item.get("severity")) == "high"]
    chosen = high_items[0] if high_items else missing[0]
    if not isinstance(chosen, dict):
        return "unknown"
    return normalize_text(chosen.get("next_check")) or "unknown"


def label_triage_rationale(label: dict[str, object]) -> str:
    recommendation = normalize_text(label.get("status_recommendation")) or "unknown"
    reasons = label.get("reason_codes") if isinstance(label.get("reason_codes"), list) else []
    reason_text = ", ".join(normalize_text(reason) for reason in reasons if normalize_text(reason)) or "none"
    return f"{recommendation}; reasons: {reason_text}"


def non_negative_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a non-negative integer") from exc
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be a non-negative integer")
    return parsed


def write_batch_report(data_dir: Path, week: str) -> Path:
    paths = ensure_layout(data_dir, week)
    candidates = latest_candidates_for_week(data_dir, week)
    events = read_jsonl(paths["events"])
    labels = latest_label_by_candidate_for_week(read_jsonl(paths["labels"]), week)
    statuses = status_by_candidate_for_week(events, week)
    reasons = reason_codes_by_candidate_for_week(events, week)
    counts = grouped_status_counts({normalize_text(row.get("candidate_id")): statuses.get(normalize_text(row.get("candidate_id")), "raw") for row in candidates})
    report_path = paths["reports"] / f"{week}-batch-report.md"
    lines = [
        f"# Opportunity Scanner Batch Report - {week}",
        "",
        f"- Generated at: `{utc_now()}`",
        f"- Candidate count: `{len(candidates)}`",
        "",
        "## Status Counts",
        "",
    ]
    if counts:
        for status in sorted(counts):
            lines.append(f"- `{status}`: {counts[status]}")
    else:
        lines.append("- none")
    lines.extend(["", "## Candidates", ""])
    for candidate in sorted(candidates, key=lambda row: normalize_text(row.get("project_name")).lower()):
        candidate_id = normalize_text(candidate.get("candidate_id"))
        status = statuses.get(candidate_id, "raw")
        reason_codes = reasons.get(candidate_id, [])
        active_lanes = active_lane_codes(candidate)
        label = labels.get(candidate_id, {})
        label_confidence = normalize_text(label.get("confidence")) if label else "unknown"
        label_summary = normalize_text(label.get("summary")) if label else "unknown"
        lines.extend(
            [
                f"### {candidate.get('project_name')}",
                "",
                f"- Candidate ID: `{candidate_id}`",
                f"- Repo key: `{candidate.get('repo_key') or 'unknown'}`",
                f"- Fork family key: `{candidate.get('fork_family_key') or 'unknown'}`",
                f"- Status: `{status}`",
                f"- Reason codes: `{', '.join(reason_codes) if reason_codes else 'none'}`",
                f"- Active lanes: `{', '.join(active_lanes) if active_lanes else 'none'}`",
                f"- Weak label confidence: `{label_confidence}`",
                f"- Weak summary: {label_summary or 'unknown'}",
                f"- Missing evidence: {label_missing_summary(label) if label else 'unknown'}",
                f"- Uncertainty: {label_uncertainty_summary(label) if label else 'unknown'}",
                f"- Triage rationale: {label_triage_rationale(label) if label else 'unknown'}",
                f"- Next evidence check: {label_next_check(label) if label else 'unknown'}",
                f"- Project URL: {candidate.get('project_url') or 'unknown'}",
                f"- Source URL: {candidate.get('source_url') or 'unknown'}",
                f"- License: `{candidate.get('license') or 'unknown'}`",
                f"- Evidence: `ledger/evidence/{candidate_id}.md`",
                f"- Summary: {candidate.get('short_description') or 'unknown'}",
                "",
            ]
        )
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Opportunity Scanner local CLI")
    parser.add_argument("--data-dir", default="data", help="Local data directory")
    parser.add_argument("--week", default=default_week(), help="ISO week label, e.g. 2026-W23")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Create ledger directories")
    init_parser.set_defaults(command="init")

    run_parser = subparsers.add_parser("run", help="Ingest candidates, prefilter, and write report")
    run_parser.add_argument("--input", required=True, help="JSONL candidate input file")
    run_parser.set_defaults(command="run")

    report_parser = subparsers.add_parser("report", help="Regenerate weekly Markdown report")
    report_parser.set_defaults(command="report")

    label_parser = subparsers.add_parser("label", help="Apply weak-label baseline triage to weekly candidates")
    label_parser.set_defaults(command="label")

    deep_review_parser = subparsers.add_parser("deep-review", help="Create opportunity cards and council packets")
    deep_review_parser.add_argument("--max-candidates", type=non_negative_int, help="Maximum ranked candidates to deep-review")
    deep_review_parser.set_defaults(command="deep-review")

    aggregate_parser = subparsers.add_parser("council-aggregate", help="Aggregate structured council findings")
    aggregate_parser.add_argument("--input", required=True, help="JSONL council findings input file")
    aggregate_parser.set_defaults(command="council-aggregate")

    digest_parser = subparsers.add_parser("digest", help="Write weekly review digest and Telegram outbox markdown")
    digest_parser.set_defaults(command="digest")

    telegram_parser = subparsers.add_parser("send-telegram-digest", help="Send weekly digest from local Telegram outbox")
    telegram_parser.add_argument("--dry-run", action="store_true", help="Validate and summarize messages without sending")
    telegram_parser.add_argument("--skip-empty", action="store_true", help="Do not send when the Telegram digest has no ready shortlist")
    telegram_parser.add_argument("--chat-id", default="", help="Override TELEGRAM_CHAT_ID or TG_CHAT_ID")
    telegram_parser.add_argument("--api-base", default=TELEGRAM_API_BASE, help="Telegram Bot API base URL")
    telegram_parser.set_defaults(command="send-telegram-digest")

    feedback_parser = subparsers.add_parser("operator-feedback", help="Apply Operator feedback decisions from JSONL")
    feedback_parser.add_argument("--input", required=True, help="JSONL Operator feedback input file")
    feedback_parser.set_defaults(command="operator-feedback")

    calibration_parser = subparsers.add_parser("calibration", help="Write weekly calibration report")
    calibration_parser.set_defaults(command="calibration")

    dashboard_parser = subparsers.add_parser("dashboard", help="Write static local HTML operator dashboard")
    dashboard_parser.set_defaults(command="dashboard")

    mirror_parser = subparsers.add_parser("mirror-github-issues", help="Mirror serious candidates into GitHub Issues")
    mirror_parser.add_argument("--repo", required=True, help="Target GitHub repo in owner/name form")
    mirror_parser.add_argument("--dry-run", action="store_true", help="Preview issue creation without writing GitHub or mirror ledger")
    mirror_parser.add_argument(
        "--verdicts",
        nargs="+",
        default=list(GITHUB_ISSUE_MIRROR_DEFAULT_VERDICTS),
        help="Verdicts to mirror",
    )
    mirror_parser.add_argument("--api-base", default=GITHUB_API_BASE, help="GitHub API base URL")
    mirror_parser.set_defaults(command="mirror-github-issues")

    project_parser = subparsers.add_parser("sync-github-project", help="Add mirrored serious candidate issues to GitHub Projects v2")
    project_parser.add_argument("--repo", required=True, help="Source GitHub repo in owner/name form")
    project_parser.add_argument("--project-owner", default="", help="GitHub user or organization that owns the Project v2")
    project_parser.add_argument("--project-number", type=non_negative_int, default=0, help="Project v2 number")
    project_parser.add_argument("--project-id", default="", help="Project v2 node ID, if already known")
    project_parser.add_argument("--dry-run", action="store_true", help="Preview project item sync without GraphQL mutations")
    project_parser.add_argument("--api-base", default=GITHUB_API_BASE, help="GitHub API base URL")
    project_parser.set_defaults(command="sync-github-project")

    rescore_parser = subparsers.add_parser("rescore", help="Reprocess raw candidates from an earlier week")
    rescore_parser.add_argument("--source-week", required=True, help="Week whose raw candidate observations should be rescored")
    rescore_parser.add_argument("--target-week", help="Week to write rescored observations into; defaults to --week")
    rescore_parser.add_argument("--no-labels", action="store_true", help="Skip weak-label rerun during rescore")
    rescore_parser.set_defaults(command="rescore")

    repo_digest_parser = subparsers.add_parser("repo-digest", help="Persist bounded repo digest metadata for a serious candidate")
    repo_digest_parser.add_argument("--candidate-id", required=True, help="Candidate id to digest")
    repo_digest_parser.add_argument("--source-path", help="Local repository or file to pack with the bounded built-in digest")
    repo_digest_parser.add_argument("--digest-file", help="Existing digest artifact to copy into the candidate digest directory")
    repo_digest_parser.add_argument("--tool", default="builtin", help="Digest tool name recorded in metadata")
    repo_digest_parser.add_argument("--tool-version", default="unknown", help="Digest tool version recorded in metadata")
    repo_digest_parser.add_argument("--max-files", type=non_negative_int, default=80, help="Maximum text files to include")
    repo_digest_parser.add_argument("--max-bytes", type=non_negative_int, default=500000, help="Maximum source bytes to include")
    repo_digest_parser.add_argument("--force", action="store_true", help="Allow digesting non-serious candidates")
    repo_digest_parser.set_defaults(command="repo-digest")

    repo_digest_batch_parser = subparsers.add_parser(
        "repo-digest-batch",
        help="Clone and digest a capped batch of serious GitHub candidates",
    )
    repo_digest_batch_parser.add_argument("--max-candidates", type=non_negative_int, default=2, help="Maximum serious candidates to digest")
    repo_digest_batch_parser.add_argument("--max-files", type=non_negative_int, default=80, help="Maximum text files per digest")
    repo_digest_batch_parser.add_argument("--max-bytes", type=non_negative_int, default=500000, help="Maximum source bytes per digest")
    repo_digest_batch_parser.add_argument("--clone-timeout-seconds", type=non_negative_int, default=90, help="Per-repository git clone timeout")
    repo_digest_batch_parser.add_argument("--force", action="store_true", help="Allow digesting non-serious or already-digested candidates")
    repo_digest_batch_parser.add_argument("--dry-run", action="store_true", help="Select candidates without cloning or writing digests")
    repo_digest_batch_parser.set_defaults(command="repo-digest-batch")

    gh_archive_parser = subparsers.add_parser("gh-archive-momentum", help="Collect capped GH Archive-style public event momentum candidates")
    gh_archive_parser.add_argument("--input", required=True, help="Local GH Archive JSON or JSONL event fixture")
    gh_archive_parser.add_argument("--output", help="Output JSONL path; defaults to data/sources/gh-archive/<week>-momentum-candidates.jsonl")
    gh_archive_parser.add_argument("--ingest", action="store_true", help="Ingest emitted momentum candidates into the local ledger")
    gh_archive_parser.add_argument("--max-events", type=non_negative_int, default=1000, help="Maximum events to read")
    gh_archive_parser.add_argument("--max-repos", type=non_negative_int, default=20, help="Maximum repository candidates to emit")
    gh_archive_parser.add_argument("--min-events", type=non_negative_int, default=2, help="Minimum events required per repo")
    gh_archive_parser.add_argument("--issue-excerpts-per-repo", type=non_negative_int, default=4, help="Maximum event excerpts per repo")
    gh_archive_parser.set_defaults(command="gh-archive-momentum")

    ecosystems_parser = subparsers.add_parser("ecosystems-enrich", help="Capture small attributed ecosyste.ms metadata for GitHub candidates")
    ecosystems_parser.add_argument("--candidate-id", default="", help="Candidate id to enrich; defaults to capped GitHub candidates")
    ecosystems_parser.add_argument("--fixture", help="Local ecosyste.ms JSON or JSONL response fixture")
    ecosystems_parser.add_argument("--max-candidates", type=non_negative_int, default=10, help="Maximum candidates to enrich when no id is supplied")
    ecosystems_parser.add_argument("--api-base", default=ECOSYSTEMS_API_BASE, help="ecosyste.ms repos API base URL")
    ecosystems_parser.add_argument("--dry-run", action="store_true", help="Fetch/parse without writing enrichment rows")
    ecosystems_parser.set_defaults(command="ecosystems-enrich")

    github_parser = subparsers.add_parser("github-search", help="Collect public GitHub repository candidates")
    github_parser.add_argument("--query", required=True, help="GitHub repository search query; is:public is enforced")
    github_parser.add_argument("--output", help="Output JSONL path; defaults to data/sources/github/<week>-candidates.jsonl")
    github_parser.add_argument("--ingest", action="store_true", help="Ingest collected candidates into the local ledger")
    github_parser.add_argument("--max-candidates", type=int, default=10, help="Maximum candidates to collect")
    github_parser.add_argument("--per-page", type=int, default=10, help="Search page size, capped at 100")
    github_parser.add_argument("--issues-per-repo", type=int, default=3, help="Recent non-PR issues to excerpt per repo")
    github_parser.add_argument("--sort", default="updated", help="GitHub search sort field")
    github_parser.add_argument("--order", default="desc", choices=["asc", "desc"], help="GitHub search order")
    github_parser.add_argument("--api-base", default=GITHUB_API_BASE, help="GitHub API base URL")
    github_parser.set_defaults(command="github-search")

    gitlab_parser = subparsers.add_parser("gitlab-search", help="Collect public GitLab project candidates")
    gitlab_parser.add_argument("--search", required=True, help="GitLab project search string")
    gitlab_parser.add_argument("--output", help="Output JSONL path; defaults to data/sources/gitlab/<week>-candidates.jsonl")
    gitlab_parser.add_argument("--ingest", action="store_true", help="Ingest collected candidates into the local ledger")
    gitlab_parser.add_argument("--max-candidates", type=int, default=10, help="Maximum candidates to collect")
    gitlab_parser.add_argument("--per-page", type=int, default=10, help="Search page size, capped at 100")
    gitlab_parser.add_argument("--issues-per-project", type=int, default=3, help="Recent issues to excerpt per project")
    gitlab_parser.add_argument("--order-by", default="last_activity_at", help="GitLab project order field")
    gitlab_parser.add_argument("--sort", default="desc", choices=["asc", "desc"], help="GitLab project sort order")
    gitlab_parser.add_argument("--api-base", default=GITLAB_API_BASE, help="GitLab API base URL")
    gitlab_parser.set_defaults(command="gitlab-search")

    hn_parser = subparsers.add_parser("hn-demand", help="Mine public Hacker News discussions for demand clusters")
    hn_parser.add_argument("--feeds", nargs="+", default=list(HN_DEFAULT_FEEDS), choices=list(HN_FEEDS), help="HN feeds to scan")
    hn_parser.add_argument("--output", help="Output JSONL path; defaults to data/sources/hn/<week>-demand-candidates.jsonl")
    hn_parser.add_argument("--ingest", action="store_true", help="Ingest emitted demand candidates into the local ledger")
    hn_parser.add_argument("--max-stories", type=non_negative_int, default=80, help="Maximum stories to inspect")
    hn_parser.add_argument("--comments-per-story", type=non_negative_int, default=20, help="Maximum comments to inspect per story")
    hn_parser.add_argument("--max-total-items", type=non_negative_int, default=600, help="Maximum HN item fetches per run")
    hn_parser.add_argument("--max-clusters", type=non_negative_int, default=10, help="Maximum clusters to include in report")
    hn_parser.add_argument("--max-candidates", type=non_negative_int, default=5, help="Maximum strong clusters to emit as candidates")
    hn_parser.add_argument("--api-base", default=HN_API_BASE, help="Hacker News API base URL")
    hn_parser.set_defaults(command="hn-demand")

    reddit_parser = subparsers.add_parser("reddit-demand", help="Mine OAuth-authenticated public Reddit discussions for demand clusters")
    reddit_parser.add_argument("--subreddits", nargs="+", required=True, help="Subreddits to scan, e.g. webdev saas")
    reddit_parser.add_argument("--sort", default="hot", choices=list(REDDIT_ALLOWED_SORTS), help="Subreddit listing sort")
    reddit_parser.add_argument("--output", help="Output JSONL path; defaults to data/sources/reddit/<week>-demand-candidates.jsonl")
    reddit_parser.add_argument("--ingest", action="store_true", help="Ingest emitted demand candidates into the local ledger")
    reddit_parser.add_argument("--max-posts-per-subreddit", type=non_negative_int, default=10, help="Maximum posts per subreddit")
    reddit_parser.add_argument("--comments-per-post", type=non_negative_int, default=5, help="Maximum comments per post")
    reddit_parser.add_argument("--max-total-items", type=non_negative_int, default=80, help="Maximum post/comment documents per run")
    reddit_parser.add_argument("--max-clusters", type=non_negative_int, default=8, help="Maximum clusters to include in report")
    reddit_parser.add_argument("--max-candidates", type=non_negative_int, default=3, help="Maximum strong clusters to emit as candidates")
    reddit_parser.set_defaults(command="reddit-demand")

    telegram_feedback_parser = subparsers.add_parser("telegram-feedback", help="Apply Operator feedback from Telegram commands or callback buttons")
    telegram_feedback_parser.add_argument("--dry-run", action="store_true", help="Parse updates without writing ledger state")
    telegram_feedback_parser.add_argument("--input", help="Read Telegram getUpdates JSON from a file instead of polling the API")
    telegram_feedback_parser.add_argument("--chat-id", default="", help="Allowed Telegram chat id; defaults to TELEGRAM_CHAT_ID/TG_CHAT_ID")
    telegram_feedback_parser.add_argument("--api-base", default=TELEGRAM_API_BASE, help="Telegram Bot API base URL")
    telegram_feedback_parser.set_defaults(command="telegram-feedback")
    return parser


def main(argv: list[str]) -> int:
    load_env_file(Path(__file__).resolve().parent.parent / ".env")
    parser = build_parser()
    args = parser.parse_args(argv)
    data_dir = Path(args.data_dir)
    week = normalize_text(args.week)

    if args.command == "init":
        ensure_layout(data_dir, week)
        print(json.dumps({"data_dir": str(data_dir), "week": week, "status": "initialized"}, sort_keys=True))
        return 0

    if args.command == "run":
        result = ingest_candidates(Path(args.input), data_dir, week)
        print(json.dumps(result, sort_keys=True))
        return 0

    if args.command == "report":
        report_path = write_batch_report(data_dir, week)
        print(json.dumps({"report_path": str(report_path)}, sort_keys=True))
        return 0

    if args.command == "label":
        result = label_candidates(data_dir, week)
        print(json.dumps(result, sort_keys=True))
        return 0

    if args.command == "deep-review":
        result = deep_review_candidates(data_dir, week, args.max_candidates)
        print(json.dumps(result, sort_keys=True))
        return 0

    if args.command == "council-aggregate":
        result = council_aggregate(data_dir, week, Path(args.input))
        print(json.dumps(result, sort_keys=True))
        return 0

    if args.command == "digest":
        digest_path = write_digest(data_dir, week)
        print(json.dumps({"digest_path": str(digest_path)}, sort_keys=True))
        return 0

    if args.command == "send-telegram-digest":
        result = send_telegram_digest(
            data_dir=data_dir,
            week=week,
            token="",
            chat_id=args.chat_id,
            api_base=args.api_base,
            timeout=HTTP_TIMEOUT_SECONDS,
            dry_run=bool(args.dry_run),
            skip_empty=bool(args.skip_empty),
        )
        print(json.dumps(result, sort_keys=True))
        return 0

    if args.command == "operator-feedback":
        result = apply_operator_feedback(data_dir, week, Path(args.input))
        print(json.dumps(result, sort_keys=True))
        return 0

    if args.command == "calibration":
        report_path = write_calibration_report(data_dir, week)
        print(json.dumps({"report_path": str(report_path)}, sort_keys=True))
        return 0

    if args.command == "dashboard":
        dashboard_path = write_dashboard(data_dir, week)
        print(json.dumps({"dashboard_path": str(dashboard_path)}, sort_keys=True))
        return 0

    if args.command == "mirror-github-issues":
        result = mirror_github_issues(
            data_dir=data_dir,
            week=week,
            repo=args.repo,
            verdicts=args.verdicts,
            dry_run=bool(args.dry_run),
            token=env_github_token(),
            api_base=args.api_base,
        )
        print(json.dumps(result, sort_keys=True))
        return 0

    if args.command == "sync-github-project":
        result = sync_github_project(
            data_dir=data_dir,
            week=week,
            repo=args.repo,
            project_owner=normalize_text(args.project_owner),
            project_number=int(args.project_number),
            project_id=normalize_text(args.project_id),
            dry_run=bool(args.dry_run),
            token=env_github_token(),
            api_base=args.api_base,
        )
        print(json.dumps(result, sort_keys=True))
        return 0

    if args.command == "rescore":
        target_week = normalize_text(args.target_week) or week
        result = rescore_candidates(data_dir, normalize_text(args.source_week), target_week, not bool(args.no_labels))
        print(json.dumps(result, sort_keys=True))
        return 0

    if args.command == "repo-digest":
        result = run_repo_digest(
            data_dir=data_dir,
            week=week,
            candidate_id=args.candidate_id,
            source_path=Path(args.source_path) if args.source_path else None,
            digest_file=Path(args.digest_file) if args.digest_file else None,
            tool=args.tool,
            tool_version=args.tool_version,
            max_files=args.max_files,
            max_bytes=args.max_bytes,
            force=bool(args.force),
        )
        print(json.dumps(result, sort_keys=True))
        return 0

    if args.command == "repo-digest-batch":
        result = run_repo_digest_batch(
            data_dir=data_dir,
            week=week,
            max_candidates=args.max_candidates,
            max_files=args.max_files,
            max_bytes=args.max_bytes,
            clone_timeout_seconds=args.clone_timeout_seconds,
            force=bool(args.force),
            dry_run=bool(args.dry_run),
        )
        print(json.dumps(result, sort_keys=True))
        return 0

    if args.command == "gh-archive-momentum":
        output_path = Path(args.output) if args.output else data_dir / "sources" / "gh-archive" / f"{week}-momentum-candidates.jsonl"
        result = run_gh_archive_momentum(
            data_dir=data_dir,
            week=week,
            input_path=Path(args.input),
            output_path=output_path,
            max_events=args.max_events,
            max_repos=args.max_repos,
            min_events=args.min_events,
            issue_excerpts_per_repo=args.issue_excerpts_per_repo,
            ingest=bool(args.ingest),
        )
        print(json.dumps(result, sort_keys=True))
        return 0

    if args.command == "ecosystems-enrich":
        result = run_ecosystems_enrich(
            data_dir=data_dir,
            week=week,
            candidate_id=args.candidate_id,
            fixture_path=Path(args.fixture) if args.fixture else None,
            max_candidates=args.max_candidates,
            api_base=args.api_base,
            dry_run=bool(args.dry_run),
        )
        print(json.dumps(result, sort_keys=True))
        return 0

    if args.command == "github-search":
        output_path = Path(args.output) if args.output else data_dir / "sources" / "github" / f"{week}-candidates.jsonl"
        collection = collect_github_to_file(
            output_path=output_path,
            query=args.query,
            max_candidates=args.max_candidates,
            per_page=args.per_page,
            sort=args.sort,
            order=args.order,
            issues_per_repo=args.issues_per_repo,
            token=env_github_token(),
            api_base=args.api_base,
        )
        result: dict[str, object] = {"collection": collection}
        if args.ingest:
            result["ingest"] = ingest_candidates(output_path, data_dir, week)
        print(json.dumps(result, sort_keys=True))
        return 0

    if args.command == "gitlab-search":
        output_path = Path(args.output) if args.output else data_dir / "sources" / "gitlab" / f"{week}-candidates.jsonl"
        collection = collect_gitlab_to_file(
            output_path=output_path,
            search=args.search,
            max_candidates=args.max_candidates,
            per_page=args.per_page,
            order_by=args.order_by,
            sort=args.sort,
            issues_per_project=args.issues_per_project,
            token=env_gitlab_token(),
            api_base=args.api_base,
        )
        result: dict[str, object] = {"collection": collection}
        if args.ingest:
            result["ingest"] = ingest_candidates(output_path, data_dir, week)
        print(json.dumps(result, sort_keys=True))
        return 0

    if args.command == "hn-demand":
        output_path = Path(args.output) if args.output else data_dir / "sources" / "hn" / f"{week}-demand-candidates.jsonl"
        result = run_hn_demand(
            data_dir=data_dir,
            week=week,
            output_path=output_path,
            feeds=args.feeds,
            max_stories=args.max_stories,
            comments_per_story=args.comments_per_story,
            max_total_items=args.max_total_items,
            max_clusters=args.max_clusters,
            max_candidates=args.max_candidates,
            api_base=args.api_base,
            ingest=bool(args.ingest),
        )
        print(json.dumps(result, sort_keys=True))
        return 0

    if args.command == "reddit-demand":
        output_path = Path(args.output) if args.output else data_dir / "sources" / "reddit" / f"{week}-demand-candidates.jsonl"
        result = run_reddit_demand(
            data_dir=data_dir,
            week=week,
            output_path=output_path,
            subreddits=args.subreddits,
            sort=args.sort,
            max_posts_per_subreddit=args.max_posts_per_subreddit,
            comments_per_post=args.comments_per_post,
            max_total_items=args.max_total_items,
            max_clusters=args.max_clusters,
            max_candidates=args.max_candidates,
            ingest=bool(args.ingest),
        )
        print(json.dumps(result, sort_keys=True))
        return 0

    if args.command == "telegram-feedback":
        result = run_telegram_feedback(
            data_dir=data_dir,
            week=week,
            token="",
            chat_id=args.chat_id,
            api_base=args.api_base,
            timeout=HTTP_TIMEOUT_SECONDS,
            dry_run=bool(args.dry_run),
            input_path=Path(args.input) if args.input else None,
        )
        print(json.dumps(result, sort_keys=True))
        return 0

    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
