from pathlib import Path
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "opportunity_scanner.py"
FIXTURE = ROOT / "fixtures" / "manual-candidates.jsonl"
SPEC = importlib.util.spec_from_file_location("opportunity_scanner", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Cannot load opportunity_scanner module")
scanner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scanner)


class FakeGitHubClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def get_json(self, path: str, params: dict[str, object]) -> object:
        self.calls.append((path, params))
        if path == "/search/repositories":
            return {
                "items": [
                    {"full_name": "private/skip", "private": True},
                    {"full_name": "owner/tool", "private": False},
                    {"full_name": "owner/other", "private": False},
                ]
            }
        if path == "/repos/owner/tool":
            return {
                "id": 100,
                "node_id": "R_100",
                "full_name": "owner/tool",
                "html_url": "https://github.com/owner/tool",
                "description": "CLI tool with hosted cloud dashboard requests",
                "license": {"spdx_id": "MIT", "name": "MIT License"},
                "fork": True,
                "private": False,
                "source": {"full_name": "upstream/tool"},
                "topics": ["cli", "dashboard"],
                "stargazers_count": 50,
                "forks_count": 8,
                "open_issues_count": 3,
                "updated_at": "2026-06-01T00:00:00Z",
                "pushed_at": "2026-06-01T00:00:00Z",
                "has_issues": True,
            }
        if path == "/repos/owner/tool/issues":
            return [
                {
                    "title": "Hosted version?",
                    "body": "Setup is painful. We need managed cloud pricing.",
                    "comments": 4,
                    "updated_at": "2026-06-01T00:00:00Z",
                    "html_url": "https://github.com/owner/tool/issues/1",
                },
                {
                    "title": "Pull request masquerading as issue",
                    "pull_request": {},
                },
            ]
        if path == "/repos/owner/other":
            raise scanner.GitHubApiError("should not be called when max cap is 1")
        return {}


class FakeGitLabClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def get_json(self, path: str, params: dict[str, object]) -> object:
        self.calls.append((path, params))
        if path == "/projects":
            return [
                {"id": 1, "path_with_namespace": "private/skip", "visibility": "private"},
                {
                    "id": 2,
                    "path_with_namespace": "owner/tool",
                    "web_url": "https://gitlab.com/owner/tool",
                    "visibility": "public",
                    "description": "CLI tool with hosted dashboard setup pain",
                    "star_count": 40,
                    "forks_count": 3,
                    "open_issues_count": 2,
                    "last_activity_at": "2026-06-01T00:00:00Z",
                    "topics": ["cli", "dashboard"],
                    "forked_from_project": {"path_with_namespace": "upstream/tool"},
                },
                {
                    "id": 3,
                    "path_with_namespace": "owner/other",
                    "web_url": "https://gitlab.com/owner/other",
                    "visibility": "public",
                },
            ]
        if path == "/projects/2/issues":
            return [
                {
                    "title": "Hosted version?",
                    "description": "Setup is painful and we need managed cloud pricing.",
                    "updated_at": "2026-06-01T00:00:00Z",
                    "web_url": "https://gitlab.com/owner/tool/-/issues/1",
                }
            ]
        if path == "/projects/3/issues":
            raise scanner.GitLabApiError("should not be called when max cap is 1")
        return {}


class FakeHackerNewsClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.items: dict[int, dict[str, object]] = {
            100: {
                "id": 100,
                "type": "story",
                "title": "Ask HN: How do developers manage customer onboarding exports?",
                "text": (
                    "I hate manually building reports for SaaS users. "
                    "Is there a tool that can turn CSV exports into dashboards?"
                ),
                "score": 80,
                "kids": [101, 102, 103],
            },
            101: {
                "id": 101,
                "type": "comment",
                "parent": 100,
                "text": "We are a small SaaS team currently using spreadsheets. It is painful and a hosted dashboard would help.",
                "kids": [104],
            },
            102: {
                "id": 102,
                "type": "comment",
                "parent": 100,
                "deleted": True,
                "text": "deleted painful comment",
            },
            103: {
                "id": 103,
                "type": "comment",
                "parent": 100,
                "text": "Developers need a simple report export API, doing it manually is annoying.",
            },
            104: {
                "id": 104,
                "type": "comment",
                "parent": 101,
                "text": "An extension or one-click template for onboarding reports would be useful.",
            },
            200: {
                "id": 200,
                "type": "story",
                "title": "Ask HN: Crypto trading bot alternatives?",
                "text": "Looking for an investment trading workaround.",
                "score": 40,
                "kids": [],
            },
        }

    def get_json(self, path: str, params: dict[str, object]) -> object:
        self.calls.append((path, params))
        if path == "/askstories.json":
            return [100, 200]
        if path == "/showstories.json":
            return []
        if path.startswith("/item/") and path.endswith(".json"):
            item_id = int(path.removeprefix("/item/").removesuffix(".json"))
            return self.items.get(item_id, {})
        return {}


class FakeRedditClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def get_json(self, path: str, params: dict[str, object]) -> object:
        self.calls.append((path, params))
        if path == "/r/webdev/hot":
            return {
                "data": {
                    "children": [
                        {
                            "kind": "t3",
                            "data": {
                                "id": "p1",
                                "subreddit": "webdev",
                                "title": "How do you handle customer export reports?",
                                "selftext": "I hate manually building reports for SaaS customers. Is there a tool for hosted dashboards?",
                                "permalink": "/r/webdev/comments/p1/export_reports/",
                                "score": 42,
                            },
                        },
                        {
                            "kind": "t3",
                            "data": {
                                "id": "p2",
                                "title": "Removed post",
                                "selftext": "[removed]",
                                "permalink": "/r/webdev/comments/p2/removed/",
                            },
                        },
                    ]
                }
            }
        if path == "/r/webdev/comments/p1":
            return [
                {},
                {
                    "data": {
                        "children": [
                            {
                                "kind": "t1",
                                "data": {
                                    "id": "c1",
                                    "body": "We use spreadsheets currently. Manual report exports are painful and a simple API would help developers.",
                                    "permalink": "/r/webdev/comments/p1/export_reports/c1/",
                                    "score": 7,
                                },
                            },
                            {"kind": "t1", "data": {"id": "c2", "body": "[deleted]"}},
                        ]
                    }
                },
            ]
        return {"data": {"children": []}}


class FakeGitHubIssueClient:
    def __init__(self, existing: object = None) -> None:
        self.existing = existing or []
        self.searches: list[dict[str, object]] = []
        self.created: list[dict[str, object]] = []
        self.updated: list[dict[str, object]] = []
        self.comments: list[dict[str, object]] = []
        self.labels: list[dict[str, object]] = []

    def get_json(self, path: str, params: dict[str, object]) -> object:
        self.searches.append({"path": path, "params": params})
        if path == "/search/issues":
            return {"items": self.existing}
        return {}

    def post_json(self, path: str, body: dict[str, object]) -> object:
        if path.endswith("/labels"):
            self.labels.append({"path": path, "body": body})
            return {"name": body.get("name")}
        if path.endswith("/comments"):
            self.comments.append({"path": path, "body": body})
            return {"id": len(self.comments), "body": body.get("body")}
        self.created.append({"path": path, "body": body})
        number = len(self.created)
        return {
            "number": number,
            "html_url": f"https://github.com/kiku-jw/kikuai-github-scanner/issues/{number}",
            "state": "open",
            "title": body.get("title"),
            "labels": body.get("labels", []),
        }

    def patch_json(self, path: str, body: dict[str, object]) -> object:
        self.updated.append({"path": path, "body": body})
        tail = path.rstrip("/").rsplit("/", 1)[-1]
        number = int(tail) if tail.isdigit() else 0
        return {
            "number": number,
            "html_url": f"https://github.com/kiku-jw/kikuai-github-scanner/issues/{number}",
            "state": "open",
            "title": body.get("title"),
            "labels": body.get("labels", []),
        }


class FakeGitHubProjectClient:
    def __init__(self) -> None:
        self.queries: list[dict[str, object]] = []

    def graphql(self, query: str, variables: dict[str, object]) -> dict[str, object]:
        self.queries.append({"query": query, "variables": variables})
        if "projectV2(number" in query:
            return {
                "data": {
                    "organization": None,
                    "user": {"projectV2": {"id": "PVT_project", "title": "Opportunity Backlog", "url": "https://github.com/users/kiku-jw/projects/1"}},
                }
            }
        if "repository(owner" in query:
            return {
                "data": {
                    "repository": {
                        "issue": {
                            "id": "I_issue",
                            "number": variables.get("number"),
                            "title": "Opportunity",
                            "url": f"https://github.com/kiku-jw/kikuai-github-scanner/issues/{variables.get('number')}",
                        }
                    }
                }
            }
        if "addProjectV2ItemById" in query:
            return {"data": {"addProjectV2ItemById": {"item": {"id": "PVTI_item"}}}}
        return {"data": {}}


class OpportunityScannerCliTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="opportunity-scanner-test-"))

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir)

    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        command = [sys.executable, str(SCRIPT), "--data-dir", str(self.tmp_dir / "data"), "--week", "2026-W23"]
        command.extend(args)
        return subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=True)

    def read_jsonl(self, path: Path) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                parsed = json.loads(line)
                self.assertIsInstance(parsed, dict)
                rows.append(parsed)
        return rows

    def test_load_env_file_reads_tokens_without_overwriting_process_env(self) -> None:
        env_path = self.tmp_dir / ".env"
        env_path.write_text(
            "\n".join(
                [
                    "TELEGRAM_BOT_TOKEN=file-token",
                    "TELEGRAM_CHAT_ID='12345'",
                    "CUSTOM_SCANNER_ENV=value",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        keys = ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "CUSTOM_SCANNER_ENV"]
        previous = {key: os.environ.get(key) for key in keys}
        try:
            os.environ["TELEGRAM_BOT_TOKEN"] = "process-token"
            os.environ.pop("TELEGRAM_CHAT_ID", None)
            os.environ.pop("CUSTOM_SCANNER_ENV", None)

            loaded = scanner.load_env_file(env_path)

            self.assertEqual(os.environ["TELEGRAM_BOT_TOKEN"], "process-token")
            self.assertEqual(os.environ["TELEGRAM_CHAT_ID"], "12345")
            self.assertEqual(os.environ["CUSTOM_SCANNER_ENV"], "value")
            self.assertNotIn("TELEGRAM_BOT_TOKEN", loaded)
            self.assertIn("TELEGRAM_CHAT_ID", loaded)
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def test_run_creates_ledger_events_evidence_and_report(self) -> None:
        result = self.run_cli("run", "--input", str(FIXTURE))
        payload = json.loads(result.stdout)
        self.assertEqual(payload["input_count"], 3)
        self.assertEqual(payload["normalized_count"], 3)

        data_dir = self.tmp_dir / "data"
        candidates = self.read_jsonl(data_dir / "ledger" / "candidates.jsonl")
        events = self.read_jsonl(data_dir / "ledger" / "events.jsonl")
        report = data_dir / "reports" / "2026-W23-batch-report.md"

        self.assertEqual(len(candidates), 3)
        self.assertTrue(report.exists())
        self.assertGreaterEqual(len(events), 6)

        statuses: dict[str, str] = {}
        reasons: dict[str, list[str]] = {}
        for event in events:
            statuses[str(event["candidate_id"])] = str(event["to_status"])
            event_reasons = event["reason_codes"]
            self.assertIsInstance(event_reasons, list)
            reasons[str(event["candidate_id"])] = [str(reason) for reason in event_reasons]

        candidates_by_name = {str(row["project_name"]): row for row in candidates}
        signal_id = str(candidates_by_name["Signal CLI Helper"]["candidate_id"])
        no_url_id = str(candidates_by_name["No URL Idea"]["candidate_id"])
        thin_id = str(candidates_by_name["Thin Lib"]["candidate_id"])

        self.assertEqual(statuses[signal_id], "codex-review")
        self.assertIn("rescue-signal", reasons[signal_id])
        self.assertEqual(statuses[no_url_id], "machine-reject")
        self.assertIn("missing-url", reasons[no_url_id])
        self.assertEqual(statuses[thin_id], "needs-evidence")
        self.assertIn("thin-evidence", reasons[thin_id])

        for candidate in candidates:
            evidence = data_dir / "ledger" / "evidence" / f"{candidate['candidate_id']}.md"
            self.assertTrue(evidence.exists())

        report_text = report.read_text(encoding="utf-8")
        self.assertIn("Signal CLI Helper", report_text)
        self.assertIn("machine-reject", report_text)
        self.assertIn("codex-review", report_text)

    def test_init_creates_layout(self) -> None:
        self.run_cli("init")
        data_dir = self.tmp_dir / "data"
        self.assertTrue((data_dir / "raw" / "2026-W23").exists())
        self.assertTrue((data_dir / "ledger" / "evidence").exists())
        self.assertTrue((data_dir / "reports").exists())

    def test_duplicate_run_keeps_single_candidate_rows_and_appends_evidence(self) -> None:
        self.run_cli("run", "--input", str(FIXTURE))
        self.run_cli("run", "--input", str(FIXTURE))

        data_dir = self.tmp_dir / "data"
        candidates = self.read_jsonl(data_dir / "ledger" / "candidates.jsonl")
        raw_rows = self.read_jsonl(data_dir / "raw" / "2026-W23" / "candidates.jsonl")
        events = self.read_jsonl(data_dir / "ledger" / "events.jsonl")

        self.assertEqual(len(candidates), 3)
        self.assertEqual(len(raw_rows), 6)
        self.assertGreaterEqual(len(events), 12)

        signal = None
        for candidate in candidates:
            if candidate["project_name"] == "Signal CLI Helper":
                signal = candidate
        self.assertIsNotNone(signal)
        evidence = data_dir / "ledger" / "evidence" / f"{signal['candidate_id']}.md"
        evidence_text = evidence.read_text(encoding="utf-8")
        self.assertIn("---", evidence_text)
        self.assertEqual(evidence_text.count("# Evidence - Signal CLI Helper"), 2)

    def test_cross_source_same_repo_merges_without_status_downgrade(self) -> None:
        fixture = self.tmp_dir / "cross-source.jsonl"
        rows = [
            {
                "source": "github-search",
                "source_url": "https://github.com/example/signal-cli",
                "project_url": "https://github.com/example/signal-cli",
                "project_name": "Signal CLI Helper",
                "repository": "example/signal-cli",
                "license": "MIT",
                "short_description": "CLI with hosted dashboard requests.",
                "raw_metadata": {},
                "raw_text": {
                    "readme_excerpt": "A CLI tool.",
                    "issue_excerpts": ["Please add hosted cloud dashboard pricing."],
                    "discussion_excerpts": [],
                    "marketplace_or_store_text": "",
                    "external_mentions": [],
                },
                "search_lanes": {
                    "active_abandoned_forks": False,
                    "cli_to_ui_gap": True,
                    "commercial_intent_density": True,
                    "academic_hobbyist_bias": False,
                },
                "collector_notes": "",
            },
            {
                "source": "awesome-list",
                "source_url": "https://github.com/sindresorhus/awesome",
                "project_url": "https://github.com/example/signal-cli/",
                "project_name": "Signal CLI Helper",
                "repository": "example/signal-cli",
                "license": "MIT",
                "short_description": "Same repo from a thinner source.",
                "raw_metadata": {},
                "raw_text": {
                    "readme_excerpt": "Listed project.",
                    "issue_excerpts": [],
                    "discussion_excerpts": [],
                    "marketplace_or_store_text": "",
                    "external_mentions": [],
                },
                "search_lanes": {
                    "active_abandoned_forks": False,
                    "cli_to_ui_gap": False,
                    "commercial_intent_density": False,
                    "academic_hobbyist_bias": False,
                },
                "collector_notes": "",
            },
        ]
        fixture.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

        self.run_cli("run", "--input", str(fixture))
        data_dir = self.tmp_dir / "data"
        candidates = self.read_jsonl(data_dir / "ledger" / "candidates.jsonl")
        events = self.read_jsonl(data_dir / "ledger" / "events.jsonl")

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["repo_key"], "github.com/example/signal-cli")
        self.assertEqual(candidates[0]["fork_family_key"], "github.com/example/signal-cli")

        final_event = events[-1]
        self.assertEqual(final_event["to_status"], "codex-review")
        self.assertIn("status-preserved", final_event["reason_codes"])

    def test_fork_family_merges_as_same_candidate(self) -> None:
        fixture = self.tmp_dir / "fork-family.jsonl"
        rows = [
            {
                "source": "github-search",
                "source_url": "https://github.com/original/tool",
                "project_url": "https://github.com/original/tool",
                "project_name": "Original Tool",
                "repository": "original/tool",
                "license": "MIT",
                "short_description": "Original project with thin evidence.",
                "raw_metadata": {},
                "raw_text": {
                    "readme_excerpt": "Original project.",
                    "issue_excerpts": [],
                    "discussion_excerpts": [],
                    "marketplace_or_store_text": "",
                    "external_mentions": [],
                },
                "search_lanes": {
                    "active_abandoned_forks": False,
                    "cli_to_ui_gap": False,
                    "commercial_intent_density": False,
                    "academic_hobbyist_bias": False,
                },
                "collector_notes": "",
            },
            {
                "source": "github-forks",
                "source_url": "https://github.com/fork-owner/tool",
                "project_url": "https://github.com/fork-owner/tool",
                "project_name": "Forked Tool",
                "repository": "fork-owner/tool",
                "license": "MIT",
                "short_description": "Active fork with renewed demand.",
                "raw_metadata": {"fork_family_key": "original/tool"},
                "raw_text": {
                    "readme_excerpt": "Active maintained fork.",
                    "issue_excerpts": ["Can we get a managed hosted version?"],
                    "discussion_excerpts": [],
                    "marketplace_or_store_text": "",
                    "external_mentions": [],
                },
                "search_lanes": {
                    "active_abandoned_forks": True,
                    "cli_to_ui_gap": False,
                    "commercial_intent_density": True,
                    "academic_hobbyist_bias": False,
                },
                "collector_notes": "",
            },
        ]
        fixture.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

        self.run_cli("run", "--input", str(fixture))
        data_dir = self.tmp_dir / "data"
        candidates = self.read_jsonl(data_dir / "ledger" / "candidates.jsonl")
        raw_rows = self.read_jsonl(data_dir / "raw" / "2026-W23" / "candidates.jsonl")
        events = self.read_jsonl(data_dir / "ledger" / "events.jsonl")

        self.assertEqual(len(candidates), 1)
        self.assertEqual(len(raw_rows), 2)
        self.assertEqual(candidates[0]["fork_family_key"], "github.com/original/tool")
        self.assertEqual(events[-1]["to_status"], "codex-review")

    def test_late_fork_family_enrichment_uses_identity_alias(self) -> None:
        first = self.tmp_dir / "first.jsonl"
        second = self.tmp_dir / "second.jsonl"
        third = self.tmp_dir / "third.jsonl"
        first.write_text(
            json.dumps(
                {
                    "source": "awesome-list",
                    "source_url": "https://github.com/list",
                    "project_url": "https://github.com/fork-owner/tool",
                    "project_name": "Fork Tool",
                    "repository": "fork-owner/tool",
                    "license": "MIT",
                    "short_description": "Thin first sighting.",
                    "raw_metadata": {},
                    "raw_text": {},
                    "search_lanes": {},
                    "collector_notes": "",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        second.write_text(
            json.dumps(
                {
                    "source": "github-search",
                    "source_url": "https://github.com/fork-owner/tool",
                    "project_url": "https://github.com/fork-owner/tool",
                    "project_name": "Fork Tool",
                    "repository": "fork-owner/tool",
                    "license": "MIT",
                    "short_description": "GitHub detail reveals upstream source.",
                    "raw_metadata": {"fork_family_key": "original/tool"},
                    "raw_text": {},
                    "search_lanes": {},
                    "collector_notes": "",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        third.write_text(
            json.dumps(
                {
                    "source": "github-forks",
                    "source_url": "https://github.com/another-fork/tool",
                    "project_url": "https://github.com/another-fork/tool",
                    "project_name": "Another Fork Tool",
                    "repository": "another-fork/tool",
                    "license": "MIT",
                    "short_description": "Another fork in the same family.",
                    "raw_metadata": {"fork_family_key": "original/tool"},
                    "raw_text": {},
                    "search_lanes": {},
                    "collector_notes": "",
                }
            )
            + "\n",
            encoding="utf-8",
        )

        self.run_cli("run", "--input", str(first))
        self.run_cli("run", "--input", str(second))
        self.run_cli("run", "--input", str(third))

        data_dir = self.tmp_dir / "data"
        candidates = self.read_jsonl(data_dir / "ledger" / "candidates.jsonl")
        aliases = self.read_jsonl(data_dir / "ledger" / "identity_aliases.jsonl")
        events = self.read_jsonl(data_dir / "ledger" / "events.jsonl")

        self.assertEqual(len(candidates), 1)
        alias_values = {str(row["alias"]) for row in aliases}
        self.assertIn("repo:github.com/fork-owner/tool", alias_values)
        self.assertIn("family:github.com/original/tool", alias_values)
        self.assertIn("identity-alias-merged", [reason for event in events for reason in event["reason_codes"]])

    def test_rescue_fork_reopens_rejected_family(self) -> None:
        fixture = self.tmp_dir / "rescue-reopen.jsonl"
        rows = [
            {
                "source": "github-search",
                "source_url": "https://github.com/original/tool",
                "project_url": "https://github.com/original/tool",
                "project_name": "Original Tool",
                "repository": "original/tool",
                "license": "MIT",
                "short_description": "Original failed deterministic prefilter.",
                "raw_metadata": {"prefilter_hints": {"no_usable_data": True}},
                "raw_text": {},
                "search_lanes": {},
                "collector_notes": "",
            },
            {
                "source": "github-forks",
                "source_url": "https://github.com/fork-owner/tool",
                "project_url": "https://github.com/fork-owner/tool",
                "project_name": "Forked Tool",
                "repository": "fork-owner/tool",
                "license": "MIT",
                "short_description": "Active fork with hosted demand.",
                "raw_metadata": {"fork_family_key": "original/tool"},
                "raw_text": {"issue_excerpts": ["Need managed cloud pricing."]},
                "search_lanes": {"active_abandoned_forks": True, "commercial_intent_density": True},
                "collector_notes": "",
            },
        ]
        fixture.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

        self.run_cli("run", "--input", str(fixture))
        events = self.read_jsonl(self.tmp_dir / "data" / "ledger" / "events.jsonl")

        self.assertEqual(events[-1]["to_status"], "codex-review")
        self.assertIn("rescue-reopen", events[-1]["reason_codes"])

    def test_non_public_source_is_machine_rejected(self) -> None:
        fixture = self.tmp_dir / "non-public.jsonl"
        fixture.write_text(
            json.dumps(
                {
                    "source": "github-search",
                    "source_url": "https://github.com/private/tool",
                    "project_url": "https://github.com/private/tool",
                    "project_name": "Private Tool",
                    "repository": "private/tool",
                    "license": "MIT",
                    "short_description": "Should not be collected.",
                    "raw_metadata": {
                        "private": True,
                        "collection": {
                            "api_surface": "github-rest",
                            "visibility": "private",
                            "auth_required": True,
                        },
                    },
                    "raw_text": {},
                    "search_lanes": {},
                    "collector_notes": "",
                }
            )
            + "\n",
            encoding="utf-8",
        )

        self.run_cli("run", "--input", str(fixture))
        events = self.read_jsonl(self.tmp_dir / "data" / "ledger" / "events.jsonl")

        self.assertEqual(events[-1]["to_status"], "machine-reject")
        self.assertIn("non-public-source", events[-1]["reason_codes"])

    def test_github_search_caps_public_query_and_maps_candidate_contract(self) -> None:
        client = FakeGitHubClient()
        candidates = scanner.github_search_repositories(
            client,
            "hosted dashboard",
            max_candidates=1,
            per_page=10,
            sort="updated",
            order="desc",
            issues_per_repo=2,
        )

        self.assertEqual(len(candidates), 1)
        candidate = candidates[0]
        self.assertEqual(candidate["repo_key"], "github.com/owner/tool")
        self.assertEqual(candidate["fork_family_key"], "github.com/upstream/tool")
        self.assertEqual(candidate["license"], "MIT")
        self.assertTrue(candidate["search_lanes"]["active_abandoned_forks"])
        self.assertTrue(candidate["search_lanes"]["commercial_intent_density"])
        metadata = candidate["raw_metadata"]
        self.assertEqual(metadata["collection"]["visibility"], "public")
        self.assertFalse(metadata["collection"]["auth_required"])

        search_calls = [call for call in client.calls if call[0] == "/search/repositories"]
        detail_calls = [call for call in client.calls if call[0].startswith("/repos/") and not call[0].endswith("/issues")]
        issue_calls = [call for call in client.calls if call[0].endswith("/issues")]
        self.assertEqual(search_calls[0][1]["q"], "hosted dashboard is:public")
        self.assertEqual(len(detail_calls), 1)
        self.assertEqual(len(issue_calls), 1)

    def test_github_public_query_rejects_private_search(self) -> None:
        with self.assertRaises(ValueError):
            scanner.public_github_query("hosted dashboard is:private")

    def test_gitlab_search_caps_public_projects_and_maps_candidate_contract(self) -> None:
        client = FakeGitLabClient()
        candidates = scanner.gitlab_search_projects(
            client,
            "hosted dashboard",
            max_candidates=1,
            per_page=10,
            order_by="last_activity_at",
            sort="desc",
            issues_per_project=2,
        )

        self.assertEqual(len(candidates), 1)
        candidate = candidates[0]
        self.assertEqual(candidate["repo_key"], "gitlab.com/owner/tool")
        self.assertEqual(candidate["fork_family_key"], "gitlab.com/upstream/tool")
        self.assertEqual(candidate["license"], "unknown")
        self.assertTrue(candidate["search_lanes"]["active_abandoned_forks"])
        self.assertTrue(candidate["search_lanes"]["commercial_intent_density"])
        metadata = candidate["raw_metadata"]
        self.assertEqual(metadata["provider"], "gitlab")
        self.assertEqual(metadata["collection"]["visibility"], "public")
        self.assertFalse(metadata["collection"]["auth_required"])

        project_calls = [call for call in client.calls if call[0] == "/projects"]
        issue_calls = [call for call in client.calls if call[0].endswith("/issues")]
        self.assertEqual(project_calls[0][1]["visibility"], "public")
        self.assertEqual(project_calls[0][1]["per_page"], 10)
        self.assertEqual(len(issue_calls), 1)

    def test_gh_archive_momentum_fixture_maps_public_events_and_ingests(self) -> None:
        events_path = self.tmp_dir / "gh-archive-events.jsonl"
        events = [
            {
                "type": "IssuesEvent",
                "created_at": "2026-06-15T01:00:00Z",
                "repo": {"name": "owner/tool"},
                "payload": {
                    "issue": {
                        "title": "Hosted dashboard please",
                        "body": "Setup is painful and we need a managed dashboard.",
                        "html_url": "https://github.com/owner/tool/issues/1",
                    }
                },
            },
            {
                "type": "IssueCommentEvent",
                "created_at": "2026-06-15T02:00:00Z",
                "repo": {"name": "owner/tool"},
                "payload": {
                    "comment": {
                        "body": "A one-click hosted version would save manual work.",
                        "html_url": "https://github.com/owner/tool/issues/1#issuecomment-1",
                    }
                },
            },
            {
                "type": "WatchEvent",
                "created_at": "2026-06-15T03:00:00Z",
                "repo": {"name": "owner/noise"},
                "payload": {},
            },
        ]
        events_path.write_text("\n".join(json.dumps(row) for row in events) + "\n", encoding="utf-8")

        output_path = self.tmp_dir / "data" / "sources" / "gh-archive" / "2026-W23-momentum-candidates.jsonl"
        result = self.run_cli(
            "gh-archive-momentum",
            "--input",
            str(events_path),
            "--output",
            str(output_path),
            "--max-events",
            "3",
            "--max-repos",
            "2",
            "--min-events",
            "2",
            "--ingest",
        )
        payload = json.loads(result.stdout)
        self.assertEqual(payload["collection"]["candidate_count"], 1)

        emitted = self.read_jsonl(output_path)
        self.assertEqual(len(emitted), 1)
        candidate = emitted[0]
        self.assertEqual(candidate["source"], "gh-archive-momentum")
        self.assertEqual(candidate["project_url"], "https://github.com/owner/tool")
        self.assertEqual(candidate["raw_metadata"]["event_count"], 2)
        self.assertFalse(candidate["raw_metadata"]["collection"]["raw_events_stored"])
        self.assertTrue(candidate["search_lanes"]["demand_pain_cluster"])

        ledger_candidates = self.read_jsonl(self.tmp_dir / "data" / "ledger" / "candidates.jsonl")
        self.assertEqual(len(ledger_candidates), 1)

    def test_hn_item_normalization_skips_deleted_and_dead_items(self) -> None:
        deleted = scanner.hn_document_from_item(
            {"id": 1, "type": "comment", "deleted": True, "text": "painful setup"},
            "askstories",
            100,
        )
        dead = scanner.hn_document_from_item(
            {"id": 2, "type": "comment", "dead": True, "text": "painful setup"},
            "askstories",
            100,
        )
        usable = scanner.hn_document_from_item(
            {"id": 3, "type": "comment", "text": "Setup is <p>painful</p>"},
            "askstories",
            100,
        )

        self.assertEqual(deleted, {})
        self.assertEqual(dead, {})
        self.assertEqual(usable["text"], "Setup is painful")
        self.assertEqual(usable["url"], "https://news.ycombinator.com/item?id=3")

    def test_hn_comment_traversal_respects_comment_and_fetch_caps(self) -> None:
        client = FakeHackerNewsClient()
        story = client.items[100]

        comments, fetched = scanner.hn_comment_documents(
            client,
            story,
            "askstories",
            comments_per_story=2,
            max_items=3,
        )

        self.assertLessEqual(len(comments), 2)
        self.assertLessEqual(fetched, 3)
        self.assertEqual([comment["id"] for comment in comments], [101, 103])
        self.assertNotIn(102, [comment["id"] for comment in comments])

    def test_hn_pain_phrase_extractor_and_scoring_emit_only_strong_safe_clusters(self) -> None:
        client = FakeHackerNewsClient()
        collection = scanner.hn_collect_documents(
            client,
            ["askstories"],
            max_stories=2,
            comments_per_story=3,
            max_total_items=10,
        )
        clusters = scanner.hn_build_demand_clusters(collection["documents"])

        self.assertTrue(scanner.hn_extract_pain_phrases("I hate manual reports. Is there a tool for developers?"))
        candidate_clusters = [
            cluster for cluster in clusters if cluster["score"]["verdict"] == "candidate"
        ]
        rejected_clusters = [
            cluster for cluster in clusters if cluster["score"]["verdict"] == "rejected"
        ]

        self.assertTrue(candidate_clusters)
        self.assertTrue(any("crypto" in "\n".join(cluster["score"]["hard_reasons"]) for cluster in rejected_clusters))
        self.assertGreaterEqual(candidate_clusters[0]["score"]["total"], 10)

    def test_hn_demand_ingest_writes_candidate_report_and_calibration_lane_without_telegram_noise(self) -> None:
        client = FakeHackerNewsClient()
        data_dir = self.tmp_dir / "data"
        output_path = data_dir / "sources" / "hn" / "2026-W23-demand-candidates.jsonl"

        result = scanner.run_hn_demand(
            data_dir=data_dir,
            week="2026-W23",
            output_path=output_path,
            feeds=["askstories"],
            max_stories=2,
            comments_per_story=3,
            max_total_items=10,
            max_clusters=10,
            max_candidates=5,
            api_base=scanner.HN_API_BASE,
            ingest=True,
            client=client,
        )

        self.assertEqual(result["collection"]["candidate_count"], 1)
        self.assertTrue(Path(result["report_path"]).exists())
        emitted = self.read_jsonl(output_path)
        self.assertEqual(len(emitted), 1)
        candidate = emitted[0]
        self.assertEqual(candidate["source"], "hn-demand")
        self.assertTrue(candidate["search_lanes"]["demand_pain_cluster"])
        self.assertEqual(candidate["raw_metadata"]["collection"]["visibility"], "public")
        self.assertFalse(candidate["raw_metadata"]["collection"]["auth_required"])

        ledger_candidates = self.read_jsonl(data_dir / "ledger" / "candidates.jsonl")
        events = self.read_jsonl(data_dir / "ledger" / "events.jsonl")
        self.assertEqual(len(ledger_candidates), 1)
        self.assertEqual(events[-1]["to_status"], "codex-review")
        self.assertIn("rescue-signal", events[-1]["reason_codes"])

        calibration = scanner.write_calibration_report(data_dir, "2026-W23")
        self.assertIn("demand-pain-cluster", calibration.read_text(encoding="utf-8"))

        digest = scanner.write_digest(data_dir, "2026-W23")
        outbox = data_dir / "outbox" / "telegram" / "2026-W23-digest.md"
        self.assertTrue(digest.exists())
        outbox_text = outbox.read_text(encoding="utf-8")
        self.assertIn("No ready ideas passed all filters this week.", outbox_text)
        self.assertNotIn("HN demand:", outbox_text)

    def test_reddit_demand_requires_oauth_credentials_without_fake_client(self) -> None:
        with self.assertRaises(scanner.RedditApiError):
            scanner.collect_reddit_demand_to_file(
                output_path=self.tmp_dir / "reddit.jsonl",
                subreddits=["webdev"],
                sort="hot",
                max_posts_per_subreddit=1,
                comments_per_post=0,
                max_total_items=1,
                max_clusters=1,
                max_candidates=1,
                week="2026-W23",
                user_agent="",
            )

    def test_reddit_demand_uses_caps_skips_removed_and_maps_candidate_contract(self) -> None:
        client = FakeRedditClient()
        data_dir = self.tmp_dir / "data"
        output_path = data_dir / "sources" / "reddit" / "2026-W23-demand-candidates.jsonl"

        result = scanner.run_reddit_demand(
            data_dir=data_dir,
            week="2026-W23",
            output_path=output_path,
            subreddits=["webdev"],
            sort="hot",
            max_posts_per_subreddit=2,
            comments_per_post=2,
            max_total_items=5,
            max_clusters=5,
            max_candidates=2,
            ingest=True,
            client=client,
        )

        self.assertEqual(result["collection"]["post_count"], 1)
        self.assertEqual(result["collection"]["comment_count"], 1)
        self.assertEqual(result["collection"]["candidate_count"], 1)
        candidate = self.read_jsonl(output_path)[0]
        self.assertEqual(candidate["source"], "reddit-demand")
        self.assertEqual(candidate["raw_metadata"]["collection"]["api_surface"], "reddit-oauth-api")
        self.assertTrue(candidate["raw_metadata"]["collection"]["auth_required"])
        self.assertNotIn("[removed]", json.dumps(candidate))
        events = self.read_jsonl(data_dir / "ledger" / "events.jsonl")
        self.assertEqual(events[-1]["to_status"], "codex-review")

    def test_label_command_writes_schema_report_and_no_weak_machine_reject(self) -> None:
        self.run_cli("run", "--input", str(FIXTURE))
        result = self.run_cli("label")
        payload = json.loads(result.stdout)
        self.assertEqual(payload["candidate_count"], 3)
        self.assertEqual(payload["labels_written"], 2)
        self.assertEqual(payload["skipped_hard_gate_count"], 1)

        data_dir = self.tmp_dir / "data"
        labels = self.read_jsonl(data_dir / "ledger" / "labels.jsonl")
        events = self.read_jsonl(data_dir / "ledger" / "events.jsonl")
        report_text = (data_dir / "reports" / "2026-W23-batch-report.md").read_text(encoding="utf-8")

        self.assertEqual(len(labels), 2)
        label = labels[0]
        inferred_fields = label["inferred_fields"]
        self.assertIsInstance(inferred_fields, dict)
        target_buyer = inferred_fields["target_buyer"]
        self.assertIsInstance(target_buyer, dict)
        self.assertIn("value", target_buyer)
        self.assertIn("confidence", target_buyer)
        self.assertIn("evidence_refs", target_buyer)
        self.assertIn("unknown_allowed", target_buyer)

        missing = label["missing_evidence"]
        self.assertIsInstance(missing, list)
        self.assertTrue(missing)
        first_missing = missing[0]
        self.assertIn("type", first_missing)
        self.assertIn("blocking_for", first_missing)
        self.assertIn("next_check", first_missing)

        weak_machine_rejects = [
            event for event in events if event["layer"] == "weak-label-triage" and event["to_status"] == "machine-reject"
        ]
        self.assertEqual(weak_machine_rejects, [])
        self.assertEqual(scanner.weak_layer_machine_reject_violations(events), [])
        self.assertIn("Weak label confidence", report_text)
        self.assertIn("Missing evidence", report_text)
        self.assertIn("Next evidence check", report_text)

    def test_unknown_fields_remain_unknown_for_thin_candidate(self) -> None:
        self.run_cli("run", "--input", str(FIXTURE))
        self.run_cli("label")

        labels = self.read_jsonl(self.tmp_dir / "data" / "ledger" / "labels.jsonl")
        thin_label = None
        for label in labels:
            if "Thin Lib" in str(label["summary"]):
                thin_label = label
        self.assertIsNotNone(thin_label)
        inferred_fields = thin_label["inferred_fields"]
        self.assertEqual(inferred_fields["target_buyer"]["value"], "unknown")
        self.assertEqual(inferred_fields["monetization"]["value"], "unknown")
        self.assertEqual(thin_label["confidence"], "low")
        self.assertEqual(thin_label["status_recommendation"], "needs-evidence")

    def test_low_confidence_rescue_signal_does_not_downgrade_codex_review(self) -> None:
        fixture = self.tmp_dir / "sparse-rescue.jsonl"
        fixture.write_text(
            json.dumps(
                {
                    "source": "github-forks",
                    "source_url": "https://github.com/fork-owner/sparse",
                    "project_url": "https://github.com/fork-owner/sparse",
                    "project_name": "Sparse Rescue",
                    "repository": "fork-owner/sparse",
                    "license": "MIT",
                    "short_description": "Maintained fork with sparse public text.",
                    "raw_metadata": {"fork_family_key": "original/sparse"},
                    "raw_text": {
                        "readme_excerpt": "Maintained fork.",
                        "issue_excerpts": [],
                        "discussion_excerpts": [],
                        "marketplace_or_store_text": "",
                        "external_mentions": [],
                    },
                    "search_lanes": {
                        "active_abandoned_forks": True,
                        "cli_to_ui_gap": False,
                        "commercial_intent_density": False,
                        "academic_hobbyist_bias": False,
                    },
                    "collector_notes": "",
                }
            )
            + "\n",
            encoding="utf-8",
        )

        self.run_cli("run", "--input", str(fixture))
        self.run_cli("label")
        events = self.read_jsonl(self.tmp_dir / "data" / "ledger" / "events.jsonl")
        labels = self.read_jsonl(self.tmp_dir / "data" / "ledger" / "labels.jsonl")

        self.assertEqual(labels[-1]["confidence"], "low")
        self.assertEqual(labels[-1]["status_recommendation"], "needs-evidence")
        self.assertEqual(events[-1]["layer"], "weak-label-triage")
        self.assertEqual(events[-1]["to_status"], "codex-review")
        self.assertIn("status-preserved", events[-1]["reason_codes"])

    def test_forbidden_weak_status_falls_back_without_final_reject(self) -> None:
        to_status, reason_codes, notes = scanner.resolved_weak_label_transition(
            "needs-evidence",
            "reject",
            ["weak-negative"],
        )
        self.assertEqual(to_status, "needs-evidence")
        self.assertIn("weak-final-reject-blocked", reason_codes)
        self.assertIn("forbidden", notes)

    def test_machine_reject_audit_detects_non_prefilter_transition(self) -> None:
        events = [
            {
                "layer": "weak-label-triage",
                "from_status": "needs-evidence",
                "to_status": "machine-reject",
            }
        ]
        self.assertEqual(len(scanner.weak_layer_machine_reject_violations(events)), 1)

    def test_deep_review_creates_opportunity_card_and_council_packets(self) -> None:
        self.run_cli("run", "--input", str(FIXTURE))
        self.run_cli("label")
        result = self.run_cli("deep-review")
        payload = json.loads(result.stdout)
        self.assertEqual(payload["cards_written"], 1)
        self.assertEqual(payload["packets_written"], 6)

        data_dir = self.tmp_dir / "data"
        cards = self.read_jsonl(data_dir / "ledger" / "opportunity_cards.jsonl")
        packets = self.read_jsonl(data_dir / "ledger" / "council_packets.jsonl")
        events = self.read_jsonl(data_dir / "ledger" / "events.jsonl")
        report_text = (data_dir / "reports" / "2026-W23-deep-review.md").read_text(encoding="utf-8")

        self.assertEqual(len(cards), 1)
        card = cards[0]
        self.assertEqual(card["week"], "2026-W23")
        self.assertEqual(card["verdict_recommendation"], "watchlist")
        self.assertIn("scores", card)
        self.assertIn("strict_scorecard", card)
        self.assertIn("kill_criteria", card)
        self.assertIn("proof-card-blocked-by-missing-evidence", card["reason_codes"])
        self.assertEqual(set(packet["lane"] for packet in packets), set(scanner.COUNCIL_LANES))
        self.assertTrue(all(packet["week"] == "2026-W23" for packet in packets))
        self.assertEqual(events[-1]["layer"], "codex-deep-pass")
        self.assertEqual(events[-1]["to_status"], "watchlist")
        self.assertIn("Opportunity Cards", report_text)
        self.assertIn("Council packets: `6`", report_text)

    def test_repo_digest_and_ecosystems_enrichment_attach_to_deep_review_packets(self) -> None:
        self.run_cli("run", "--input", str(FIXTURE))
        data_dir = self.tmp_dir / "data"
        candidates = self.read_jsonl(data_dir / "ledger" / "candidates.jsonl")
        signal = candidates[0]
        rejected = candidates[1]

        source_dir = self.tmp_dir / "source-repo"
        source_dir.mkdir()
        (source_dir / "README.md").write_text(
            "# Signal CLI Helper\n\nHosted dashboard setup is painful for users.\n",
            encoding="utf-8",
        )
        with self.assertRaises(ValueError):
            scanner.run_repo_digest(
                data_dir=data_dir,
                week="2026-W23",
                candidate_id=str(rejected["candidate_id"]),
                source_path=source_dir,
                digest_file=None,
                tool="builtin",
                tool_version="test",
                max_files=10,
                max_bytes=10000,
                force=False,
            )

        self.run_cli("label")
        digest_result = self.run_cli(
            "repo-digest",
            "--candidate-id",
            str(signal["candidate_id"]),
            "--source-path",
            str(source_dir),
            "--tool-version",
            "test",
        )
        digest_payload = json.loads(digest_result.stdout)
        self.assertEqual(digest_payload["status"], "ok")
        meta_path = data_dir / "repo_digests" / str(signal["candidate_id"]) / "digest-meta.json"
        self.assertTrue(meta_path.exists())
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        self.assertEqual(meta["included_file_count"], 1)
        self.assertGreater(meta["token_estimate"], 0)

        ecosystems_fixture = self.tmp_dir / "ecosystems.json"
        ecosystems_fixture.write_text(
            json.dumps(
                [
                    {
                        "full_name": "example/signal-cli",
                        "description": "Useful CLI with dashboard demand.",
                        "license": "mit",
                        "language": "Python",
                        "topics": ["cli", "dashboard", "hosted"],
                        "archived": False,
                        "fork": False,
                        "stargazers_count": 340,
                        "forks_count": 48,
                        "open_issues_count": 12,
                        "pushed_at": "2026-06-01T00:00:00.000Z",
                        "last_synced_at": "2026-06-10T00:00:00.000Z",
                        "homepage": "https://example.com",
                        "metadata": {"files": {"readme": "README.md", "license": "LICENSE"}},
                    }
                ]
            ),
            encoding="utf-8",
        )
        enrich_result = self.run_cli(
            "ecosystems-enrich",
            "--candidate-id",
            str(signal["candidate_id"]),
            "--fixture",
            str(ecosystems_fixture),
        )
        enrich_payload = json.loads(enrich_result.stdout)
        self.assertEqual(enrich_payload["written_count"], 1)
        enrichments = self.read_jsonl(data_dir / "ledger" / "ecosystems_enrichments.jsonl")
        self.assertEqual(enrichments[0]["raw_response_stored"], False)
        self.assertEqual(enrichments[0]["derived_fields"]["language"], "Python")

        self.run_cli("deep-review")
        cards = self.read_jsonl(data_dir / "ledger" / "opportunity_cards.jsonl")
        packets = self.read_jsonl(data_dir / "ledger" / "council_packets.jsonl")
        self.assertIn("repo_digest", cards[0])
        self.assertEqual(cards[0]["repo_digest"]["included_file_count"], 1)
        self.assertIn("external_enrichment", cards[0])
        self.assertEqual(cards[0]["external_enrichment"]["fields"]["language"], "Python")
        self.assertIn("repo_digest", packets[0]["evidence_packet"])
        self.assertIn("external_enrichment", packets[0]["evidence_packet"])

    def test_repo_digest_batch_clones_only_serious_github_candidates(self) -> None:
        self.run_cli("run", "--input", str(FIXTURE))
        self.run_cli("label")
        data_dir = self.tmp_dir / "data"

        clone_calls: list[tuple[str, int]] = []

        def fake_clone(url: str, target_path: Path, timeout_seconds: int) -> None:
            clone_calls.append((url, timeout_seconds))
            target_path.mkdir(parents=True)
            (target_path / "README.md").write_text(
                "# Signal CLI Helper\n\nHosted setup and dashboard exports are recurring user pain.\n",
                encoding="utf-8",
            )

        result = scanner.run_repo_digest_batch(
            data_dir=data_dir,
            week="2026-W23",
            max_candidates=2,
            max_files=10,
            max_bytes=10000,
            clone_timeout_seconds=11,
            force=False,
            dry_run=False,
            clone_runner=fake_clone,
        )

        self.assertEqual(result["candidate_count"], 1)
        self.assertEqual(result["digested_count"], 1)
        self.assertEqual(clone_calls, [("https://github.com/example/signal-cli.git", 11)])
        meta_rows = self.read_jsonl(data_dir / "ledger" / "repo_digest_meta.jsonl")
        self.assertEqual(len(meta_rows), 1)
        self.assertEqual(meta_rows[0]["repository"], "example/signal-cli")

        second = scanner.run_repo_digest_batch(
            data_dir=data_dir,
            week="2026-W23",
            max_candidates=2,
            max_files=10,
            max_bytes=10000,
            clone_timeout_seconds=11,
            force=False,
            dry_run=True,
            clone_runner=fake_clone,
        )

        self.assertEqual(second["candidate_count"], 0)

    def test_deep_review_proof_card_requires_no_proof_blocking_missing_evidence(self) -> None:
        candidate = {
            "candidate_id": "cand_clear",
            "project_name": "Clear Candidate",
            "project_url": "https://github.com/example/clear",
            "license": "MIT",
            "short_description": "Hosted dashboard for recurring monitoring reports and exports.",
            "raw_metadata": {
                "preview_cost_cap": "$1",
                "failed_job_cost_cap": "$1",
                "built_in_substitution_residue": "workflow export package",
            },
            "raw_text": {
                "issue_excerpts": ["Setup is painful", "Need hosted version with pricing"],
            },
            "search_lanes": {"commercial_intent_density": True, "cli_to_ui_gap": True},
        }
        label = {
            "pain_phrases": ["setup is painful", "need hosted version"],
            "money_signals": ["pricing", "paid"],
            "risk_hints": [],
            "missing_evidence": [],
            "inferred_fields": {
                "target_buyer": {"value": "developers"},
                "painful_job": {"value": "recurring monitoring reports"},
                "distribution_channel": {"value": "marketplace with first 100 prospects"},
                "support_load": {"value": "low"},
                "legal_license": {"value": "MIT"},
                "product_angle": {"value": "hosted version"},
                "demo_or_proof": {"value": "paid preview"},
            },
        }

        verdict, reason_codes, rationale = scanner.opportunity_verdict(candidate, label, "watchlist-candidate")

        self.assertEqual(verdict, "proof-card")
        self.assertIn("proof-card-ready", reason_codes)
        self.assertIn("Strict scorecard", rationale)

    def test_deep_review_max_candidates_caps_ranked_queue(self) -> None:
        self.run_cli("run", "--input", str(FIXTURE))
        self.run_cli("label")

        result = self.run_cli("deep-review", "--max-candidates", "0")
        payload = json.loads(result.stdout)

        self.assertEqual(payload["cards_written"], 0)
        self.assertEqual(payload["packets_written"], 0)
        self.assertEqual(payload["skipped_count"], 3)
        cards = scanner.read_jsonl(self.tmp_dir / "data" / "ledger" / "opportunity_cards.jsonl")
        packets = scanner.read_jsonl(self.tmp_dir / "data" / "ledger" / "council_packets.jsonl")
        self.assertEqual(cards, [])
        self.assertEqual(packets, [])

    def test_deep_review_max_candidates_rejects_negative_cap(self) -> None:
        with self.assertRaises(subprocess.CalledProcessError) as context:
            self.run_cli("deep-review", "--max-candidates", "-1")

        self.assertIn("must be a non-negative integer", context.exception.stderr)

    def test_deep_review_function_rejects_negative_cap(self) -> None:
        with self.assertRaises(ValueError):
            scanner.deep_review_candidates(self.tmp_dir / "data", "2026-W23", -1)

    def test_deep_review_priority_prefers_known_license_before_raw_money_keywords(self) -> None:
        label = {
            "money_signals": ["hosted", "pricing"],
            "pain_phrases": ["setup pain"],
            "missing_evidence": [],
        }
        known_license = {
            "source": "github-search",
            "license": "MIT",
            "search_lanes": {"commercial_intent_density": True},
        }
        unknown_license = {
            "source": "github-search",
            "license": "unknown",
            "search_lanes": {"commercial_intent_density": True},
        }

        self.assertGreater(
            scanner.deep_review_priority(known_license, label, "watchlist-candidate"),
            scanner.deep_review_priority(unknown_license, label, "watchlist-candidate"),
        )

    def test_council_aggregate_records_veto_conflict_and_parks(self) -> None:
        self.run_cli("run", "--input", str(FIXTURE))
        self.run_cli("label")
        self.run_cli("deep-review")

        data_dir = self.tmp_dir / "data"
        card = self.read_jsonl(data_dir / "ledger" / "opportunity_cards.jsonl")[0]
        candidate_id = str(card["candidate_id"])
        first_findings_path = self.tmp_dir / "council-findings-1.jsonl"
        second_findings_path = self.tmp_dir / "council-findings-2.jsonl"
        first_findings = [
            {
                "candidate_id": candidate_id,
                "lane": "market-payment",
                "verdict": "pass",
                "confidence": "high",
                "strongest_evidence": ["Paid hosted analog exists."],
                "missing_evidence": [],
                "reason_codes": ["money-nearby"],
                "next_check": "Confirm pricing page.",
            },
        ]
        second_findings = [
            {
                "candidate_id": candidate_id,
                "lane": "legal-platform-risk",
                "verdict": "veto",
                "confidence": "high",
                "strongest_evidence": ["Brand-copy risk is unresolved."],
                "missing_evidence": ["License and brand clearance."],
                "reason_codes": ["legal-platform-veto"],
                "next_check": "Check license and brand-safe angle.",
            },
        ]
        first_findings_path.write_text("\n".join(json.dumps(row) for row in first_findings) + "\n", encoding="utf-8")
        second_findings_path.write_text("\n".join(json.dumps(row) for row in second_findings) + "\n", encoding="utf-8")

        self.run_cli("council-aggregate", "--input", str(first_findings_path))
        result = self.run_cli("council-aggregate", "--input", str(second_findings_path))
        payload = json.loads(result.stdout)
        self.assertEqual(payload["findings_written"], 1)
        self.assertEqual(payload["aggregations_written"], 1)

        aggregations = self.read_jsonl(data_dir / "ledger" / "aggregations.jsonl")
        events = self.read_jsonl(data_dir / "ledger" / "events.jsonl")
        report_text = (data_dir / "reports" / "2026-W23-council-aggregation.md").read_text(encoding="utf-8")
        aggregation = aggregations[-1]

        self.assertEqual(aggregation["final_machine_verdict"], "park")
        self.assertTrue(aggregation["vetoes"])
        self.assertTrue(aggregation["conflicts"])
        self.assertIn("legal-platform-veto", aggregation["reason_codes"])
        self.assertEqual(events[-1]["layer"], "council-aggregator")
        self.assertEqual(events[-1]["to_status"], "park")
        self.assertIn("Conflicts: `1`", report_text)
        self.assertIn("Vetoes: `1`", report_text)

    def test_council_aggregate_requires_market_payment_before_proof_card(self) -> None:
        card = {
            "card_id": "card_1",
            "candidate_id": "cand_1",
            "project_name": "Candidate",
            "strict_scorecard": {"total": 27},
        }
        findings = [
            {
                "candidate_id": "cand_1",
                "lane": "pain-signal",
                "verdict": "pass",
                "confidence": "high",
                "strongest_evidence": ["Repeated pain."],
                "missing_evidence": [],
                "reason_codes": ["pain-confirmed"],
                "next_check": "none",
            },
            {
                "candidate_id": "cand_1",
                "lane": "distribution-first-100",
                "verdict": "pass",
                "confidence": "high",
                "strongest_evidence": ["Async channel exists."],
                "missing_evidence": [],
                "reason_codes": ["distribution-confirmed"],
                "next_check": "none",
            },
            {
                "candidate_id": "cand_1",
                "lane": "buildability-support",
                "verdict": "pass",
                "confidence": "high",
                "strongest_evidence": ["Small MVP."],
                "missing_evidence": [],
                "reason_codes": ["buildability-confirmed"],
                "next_check": "none",
            },
            {
                "candidate_id": "cand_1",
                "lane": "legal-platform-risk",
                "verdict": "pass",
                "confidence": "high",
                "strongest_evidence": ["Permissive license."],
                "missing_evidence": [],
                "reason_codes": ["legal-clear"],
                "next_check": "none",
            },
        ]

        aggregation = scanner.aggregate_findings("cand_1", findings, card)
        self.assertEqual(aggregation["final_machine_verdict"], "watchlist")
        self.assertIn("money-signal-required-before-proof-card", aggregation["reason_codes"])

    def test_council_aggregate_can_promote_to_proof_card_with_market_pass(self) -> None:
        card = {
            "card_id": "card_1",
            "candidate_id": "cand_1",
            "project_name": "Candidate",
            "strict_scorecard": {"total": 27},
        }
        findings = []
        for lane in scanner.COUNCIL_LANES:
            findings.append(
                {
                    "candidate_id": "cand_1",
                    "lane": lane,
                    "verdict": "pass",
                    "confidence": "high",
                    "strongest_evidence": [f"{lane} evidence."],
                    "missing_evidence": [],
                    "reason_codes": [f"{lane}-pass"],
                    "next_check": "none",
                }
            )

        aggregation = scanner.aggregate_findings("cand_1", findings, card)
        self.assertEqual(aggregation["final_machine_verdict"], "proof-card")
        self.assertIn("council-proof-card-ready", aggregation["reason_codes"])

    def test_council_aggregate_requires_strict_score_before_proof_card(self) -> None:
        card = {"card_id": "card_1", "candidate_id": "cand_1", "project_name": "Candidate", "strict_scorecard": {"total": 21}}
        findings = []
        for lane in scanner.COUNCIL_LANES:
            findings.append(
                {
                    "candidate_id": "cand_1",
                    "lane": lane,
                    "verdict": "pass",
                    "confidence": "high",
                    "strongest_evidence": [f"{lane} evidence."],
                    "missing_evidence": [],
                    "reason_codes": [f"{lane}-pass"],
                    "next_check": "none",
                }
            )

        aggregation = scanner.aggregate_findings("cand_1", findings, card)
        self.assertEqual(aggregation["final_machine_verdict"], "watchlist")
        self.assertIn("strict-score-required-before-proof-card", aggregation["reason_codes"])

    def test_digest_writes_review_markdown_and_telegram_outbox(self) -> None:
        self.run_cli("run", "--input", str(FIXTURE))
        self.run_cli("label")
        self.run_cli("deep-review")

        result = self.run_cli("digest")
        payload = json.loads(result.stdout)
        digest_path = Path(payload["digest_path"])
        outbox_path = self.tmp_dir / "data" / "outbox" / "telegram" / "2026-W23-digest.md"
        self.assertTrue(digest_path.exists())
        self.assertTrue(outbox_path.exists())
        digest_text = digest_path.read_text(encoding="utf-8")
        outbox_text = outbox_path.read_text(encoding="utf-8")
        self.assertNotEqual(digest_text, outbox_text)
        self.assertIn("Proof-Card Candidates", digest_text)
        self.assertIn("Signal CLI Helper", digest_text)
        self.assertIn("Next action:", digest_text)
        self.assertIn("ledger/evidence/", digest_text)
        self.assertIn("No ready ideas passed all filters", outbox_text)
        self.assertIn("Kept out of Telegram: watchlist=", outbox_text)
        self.assertNotIn("Signal CLI Helper", outbox_text)
        self.assertNotIn("First 100:", outbox_text)
        self.assertNotIn("Candidate ID", outbox_text)
        self.assertNotIn("ledger/", outbox_text)

    def test_digest_ignores_stale_cards_from_other_weeks(self) -> None:
        self.run_cli("run", "--input", str(FIXTURE))
        self.run_cli("label")
        self.run_cli("deep-review")
        data_dir = self.tmp_dir / "data"

        scanner.rescore_candidates(data_dir, "2026-W23", "2026-W24", True)
        scanner.write_digest(data_dir, "2026-W24")

        outbox_text = (data_dir / "outbox" / "telegram" / "2026-W24-digest.md").read_text(encoding="utf-8")
        self.assertIn("No ready ideas passed all filters", outbox_text)
        self.assertNotIn("Signal CLI Helper - watchlist", outbox_text)

    def test_telegram_digest_only_includes_ready_candidates(self) -> None:
        candidates = {
            "cand_ready": {
                "candidate_id": "cand_ready",
                "project_name": "Ready Helper",
                "project_url": "https://github.com/acme/ready-helper",
            },
            "cand_watch": {
                "candidate_id": "cand_watch",
                "project_name": "Maybe Helper",
                "project_url": "https://github.com/acme/maybe-helper",
            },
        }
        cards = {
            "cand_ready": {
                "verdict_recommendation": "proof-card",
                "strict_scorecard": {"total": 29, "zero_score_items": []},
                "target_buyer": "solo developers",
                "painful_job": "turn a noisy repo signal into a buyer-ready report",
                "product_angle": "one-click hosted report generator",
                "strongest_signals": {"money": ["paid competitors exist"]},
                "first_async_channel": "GitHub Marketplace search: repo report",
                "missing_evidence": [],
                "reason_codes": ["proof-card-ready"],
                "next_validation_step": "sell one manual report before build",
            },
            "cand_watch": {
                "verdict_recommendation": "watchlist",
                "strict_scorecard": {"total": 22, "zero_score_items": []},
                "target_buyer": "solo developers",
                "painful_job": "unknown",
                "product_angle": "dashboard",
                "strongest_signals": {"money": []},
                "first_async_channel": "unknown",
                "missing_evidence": [],
                "reason_codes": ["strict-challenger"],
                "next_validation_step": "collect payment evidence",
            },
        }

        text = scanner.telegram_human_digest("2026-W23", candidates, {}, cards, {})

        self.assertIn("Ready shortlist: 1 candidate", text)
        self.assertIn("Ready Helper - proof-card (29/34)", text)
        self.assertIn("First 100: GitHub Marketplace search: repo report", text)
        self.assertNotIn("Maybe Helper", text)
        self.assertIn("Kept out of Telegram: watchlist=1", text)
        self.assertNotIn("Candidate ID", text)
        self.assertNotIn("ledger/", text)

    def test_telegram_digest_honors_operator_proof_approval(self) -> None:
        candidates = {
            "cand_approved": {
                "candidate_id": "cand_approved",
                "project_name": "Approved Helper",
                "project_url": "https://github.com/acme/approved-helper",
            }
        }
        cards = {
            "cand_approved": {
                "verdict_recommendation": "watchlist",
                "strict_scorecard": {"total": 24, "zero_score_items": []},
                "target_buyer": "solo founders",
                "painful_job": "ship a buyer-visible proof faster",
                "product_angle": "PRD-lite generator",
                "strongest_signals": {"money": ["Operator approved after manual review"]},
                "first_async_channel": "specific Reddit pain thread list",
                "missing_evidence": [],
                "reason_codes": ["operator-approved"],
                "next_validation_step": "scope PRD-lite",
            }
        }
        statuses = {"cand_approved": "operator-proof-approved"}

        text = scanner.telegram_human_digest("2026-W23", candidates, statuses, cards, {})

        self.assertIn("Ready shortlist: 1 candidate", text)
        self.assertIn("Approved Helper - Operator-approved (24/34)", text)
        self.assertNotIn("watchlist candidate", text)

    def test_send_telegram_digest_dry_run_does_not_require_token(self) -> None:
        self.run_cli("run", "--input", str(FIXTURE))
        self.run_cli("label")
        self.run_cli("deep-review")
        self.run_cli("digest")

        result = self.run_cli("send-telegram-digest", "--dry-run")
        payload = json.loads(result.stdout)

        self.assertTrue(payload["dry_run"])
        self.assertEqual(payload["message_count"], 1)
        self.assertIn("2026-W23-digest.md", payload["digest_path"])
        self.assertGreater(payload["character_count"], 0)

    def test_telegram_digest_messages_chunk_under_api_limit(self) -> None:
        long_text = "\n".join([f"line {number} " + ("x" * 180) for number in range(80)])
        messages = scanner.telegram_digest_messages(long_text)

        self.assertGreater(len(messages), 1)
        self.assertTrue(all(len(message) <= scanner.TELEGRAM_MESSAGE_LIMIT for message in messages))
        self.assertIn("Opportunity Scanner Digest (1/", messages[0])

    def test_send_telegram_digest_uses_sender_without_leaking_token(self) -> None:
        self.run_cli("run", "--input", str(FIXTURE))
        self.run_cli("label")
        self.run_cli("deep-review")
        self.run_cli("digest")
        sent: list[dict[str, object]] = []

        def fake_sender(token: str, chat_id: str, text: str, api_base: str, timeout: int) -> dict[str, object]:
            sent.append(
                {
                    "token": token,
                    "chat_id": chat_id,
                    "text": text,
                    "api_base": api_base,
                    "timeout": timeout,
                }
            )
            return {"ok": True, "result": {"message_id": len(sent)}}

        result = scanner.send_telegram_digest(
            data_dir=self.tmp_dir / "data",
            week="2026-W23",
            token="secret-token",
            chat_id="12345",
            api_base="https://telegram.example",
            timeout=7,
            dry_run=False,
            sender=fake_sender,
        )

        self.assertFalse(result["dry_run"])
        self.assertEqual(result["message_count"], 1)
        self.assertEqual(result["sent_message_ids"], [1])
        self.assertNotIn("secret-token", json.dumps(result))
        self.assertEqual(sent[0]["token"], "secret-token")
        self.assertEqual(sent[0]["chat_id"], "12345")
        self.assertIn("Opportunity Scanner - 2026-W23", str(sent[0]["text"]))
        self.assertNotIn("Candidate ID", str(sent[0]["text"]))

    def test_send_telegram_digest_skip_empty_avoids_no_ready_message(self) -> None:
        self.run_cli("run", "--input", str(FIXTURE))
        self.run_cli("label")
        self.run_cli("deep-review")
        self.run_cli("digest")
        sent: list[dict[str, object]] = []

        def fake_sender(token: str, chat_id: str, text: str, api_base: str, timeout: int) -> dict[str, object]:
            sent.append({"text": text})
            return {"ok": True, "result": {"message_id": len(sent)}}

        result = scanner.send_telegram_digest(
            data_dir=self.tmp_dir / "data",
            week="2026-W23",
            token="secret-token",
            chat_id="12345",
            api_base="https://telegram.example",
            timeout=7,
            dry_run=False,
            skip_empty=True,
            sender=fake_sender,
        )

        self.assertTrue(result["skipped"])
        self.assertEqual(result["reason"], "no-ready-candidates")
        self.assertEqual(result["message_count"], 0)
        self.assertEqual(sent, [])

    def test_mirror_github_issues_creates_watchlist_issue_with_marker(self) -> None:
        self.run_cli("run", "--input", str(FIXTURE))
        self.run_cli("label")
        self.run_cli("deep-review")
        client = FakeGitHubIssueClient()

        result = scanner.mirror_github_issues(
            data_dir=self.tmp_dir / "data",
            week="2026-W23",
            repo="kiku-jw/kikuai-github-scanner",
            verdicts=["watchlist", "proof-card"],
            dry_run=False,
            token="",
            api_base=scanner.GITHUB_API_BASE,
            client=client,
        )

        self.assertEqual(result["candidate_count"], 1)
        self.assertEqual(result["created_count"], 1)
        self.assertEqual(len(client.created), 1)
        self.assertTrue(client.labels)
        created_body = str(client.created[0]["body"]["body"])
        self.assertIn("<!-- opportunity-scanner:candidate_id=", created_body)
        self.assertIn("## Evidence", created_body)
        self.assertNotIn("/Users/", created_body)
        self.assertNotIn("ledger/evidence", created_body)
        self.assertIn("opportunity-scanner", client.created[0]["body"]["labels"])
        self.assertIn("verdict:watchlist", client.created[0]["body"]["labels"])
        mirror_rows = self.read_jsonl(self.tmp_dir / "data" / "ledger" / "github_issue_mirrors.jsonl")
        self.assertEqual(len(mirror_rows), 1)
        self.assertEqual(mirror_rows[0]["action"], "created")

    def test_mirror_github_issues_dry_run_and_existing_ledger_do_not_create_duplicates(self) -> None:
        self.run_cli("run", "--input", str(FIXTURE))
        self.run_cli("label")
        self.run_cli("deep-review")
        client = FakeGitHubIssueClient()
        data_dir = self.tmp_dir / "data"

        dry_run = scanner.mirror_github_issues(
            data_dir=data_dir,
            week="2026-W23",
            repo="kiku-jw/kikuai-github-scanner",
            verdicts=["watchlist"],
            dry_run=True,
            token="",
            api_base=scanner.GITHUB_API_BASE,
            client=client,
        )
        self.assertEqual(dry_run["dry_run_count"], 1)
        self.assertEqual(client.created, [])
        self.assertFalse((data_dir / "ledger" / "github_issue_mirrors.jsonl").exists())

        created = scanner.mirror_github_issues(
            data_dir=data_dir,
            week="2026-W23",
            repo="kiku-jw/kikuai-github-scanner",
            verdicts=["watchlist"],
            dry_run=False,
            token="",
            api_base=scanner.GITHUB_API_BASE,
            client=client,
        )
        second = scanner.mirror_github_issues(
            data_dir=data_dir,
            week="2026-W23",
            repo="kiku-jw/kikuai-github-scanner",
            verdicts=["watchlist"],
            dry_run=False,
            token="",
            api_base=scanner.GITHUB_API_BASE,
            client=client,
        )

        self.assertEqual(created["created_count"], 1)
        self.assertEqual(second["updated_count"], 1)
        self.assertEqual(len(client.created), 1)
        self.assertEqual(len(client.updated), 1)
        mirror_rows = self.read_jsonl(data_dir / "ledger" / "github_issue_mirrors.jsonl")
        self.assertEqual([row["action"] for row in mirror_rows], ["created", "updated-existing"])

    def test_mirror_github_issues_links_existing_remote_issue(self) -> None:
        self.run_cli("run", "--input", str(FIXTURE))
        self.run_cli("label")
        self.run_cli("deep-review")
        client = FakeGitHubIssueClient(
            [
                {
                    "number": 17,
                    "html_url": "https://github.com/kiku-jw/kikuai-github-scanner/issues/17",
                    "state": "open",
                    "title": "Existing opportunity",
                }
            ]
        )

        result = scanner.mirror_github_issues(
            data_dir=self.tmp_dir / "data",
            week="2026-W23",
            repo="kiku-jw/kikuai-github-scanner",
            verdicts=["watchlist"],
            dry_run=False,
            token="",
            api_base=scanner.GITHUB_API_BASE,
            client=client,
        )

        self.assertEqual(result["linked_count"], 1)
        self.assertEqual(client.created, [])
        self.assertEqual(len(client.updated), 1)
        mirror_rows = self.read_jsonl(self.tmp_dir / "data" / "ledger" / "github_issue_mirrors.jsonl")
        self.assertEqual(mirror_rows[0]["action"], "linked-and-updated-github")

    def test_mirror_github_issues_comments_when_verdict_changes(self) -> None:
        self.run_cli("run", "--input", str(FIXTURE))
        self.run_cli("label")
        self.run_cli("deep-review")
        data_dir = self.tmp_dir / "data"
        card = self.read_jsonl(data_dir / "ledger" / "opportunity_cards.jsonl")[0]
        candidate_id = str(card["candidate_id"])
        scanner.append_jsonl(
            data_dir / "ledger" / "github_issue_mirrors.jsonl",
            {
                "repo": "kiku-jw/kikuai-github-scanner",
                "candidate_id": candidate_id,
                "candidate_name": "Signal CLI Helper",
                "verdict": "proof-card",
                "action": "created",
                "issue_number": 9,
                "issue_url": "https://github.com/kiku-jw/kikuai-github-scanner/issues/9",
                "issue_state": "open",
                "issue_title": "Opportunity: Signal CLI Helper [proof-card]",
            },
        )
        client = FakeGitHubIssueClient()

        result = scanner.mirror_github_issues(
            data_dir=data_dir,
            week="2026-W23",
            repo="kiku-jw/kikuai-github-scanner",
            verdicts=["watchlist"],
            dry_run=False,
            token="",
            api_base=scanner.GITHUB_API_BASE,
            client=client,
        )

        self.assertEqual(result["updated_count"], 1)
        self.assertEqual(result["commented_count"], 1)
        self.assertEqual(len(client.comments), 1)
        self.assertIn("Previous verdict: `proof-card`", str(client.comments[0]["body"]["body"]))

    def test_sync_github_project_dry_run_and_live_add_are_idempotent(self) -> None:
        self.run_cli("run", "--input", str(FIXTURE))
        self.run_cli("label")
        self.run_cli("deep-review")
        data_dir = self.tmp_dir / "data"
        issue_client = FakeGitHubIssueClient()
        scanner.mirror_github_issues(
            data_dir=data_dir,
            week="2026-W23",
            repo="kiku-jw/kikuai-github-scanner",
            verdicts=["watchlist"],
            dry_run=False,
            token="",
            api_base=scanner.GITHUB_API_BASE,
            client=issue_client,
        )

        dry_run = scanner.sync_github_project(
            data_dir=data_dir,
            week="2026-W23",
            repo="kiku-jw/kikuai-github-scanner",
            project_owner="kiku-jw",
            project_number=1,
            project_id="",
            dry_run=True,
            token="",
            api_base=scanner.GITHUB_API_BASE,
            client=FakeGitHubProjectClient(),
        )
        self.assertEqual(dry_run["dry_run_count"], 1)

        project_client = FakeGitHubProjectClient()
        first = scanner.sync_github_project(
            data_dir=data_dir,
            week="2026-W23",
            repo="kiku-jw/kikuai-github-scanner",
            project_owner="kiku-jw",
            project_number=1,
            project_id="",
            dry_run=False,
            token="",
            api_base=scanner.GITHUB_API_BASE,
            client=project_client,
        )
        second = scanner.sync_github_project(
            data_dir=data_dir,
            week="2026-W23",
            repo="kiku-jw/kikuai-github-scanner",
            project_owner="kiku-jw",
            project_number=1,
            project_id="",
            dry_run=False,
            token="",
            api_base=scanner.GITHUB_API_BASE,
            client=project_client,
        )
        post_add_dry_run = scanner.sync_github_project(
            data_dir=data_dir,
            week="2026-W23",
            repo="kiku-jw/kikuai-github-scanner",
            project_owner="kiku-jw",
            project_number=1,
            project_id="",
            dry_run=True,
            token="",
            api_base=scanner.GITHUB_API_BASE,
            client=FakeGitHubProjectClient(),
        )

        self.assertEqual(first["added_count"], 1)
        self.assertEqual(second["skipped_count"], 1)
        self.assertEqual(post_add_dry_run["skipped_count"], 1)
        self.assertEqual(post_add_dry_run["dry_run_count"], 0)
        self.assertIn("user(login", str(project_client.queries[0]["query"]))
        self.assertNotIn("organization(login", str(project_client.queries[0]["query"]))
        rows = self.read_jsonl(data_dir / "ledger" / "github_project_items.jsonl")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["project_item_id"], "PVTI_item")

    def test_telegram_feedback_commands_and_callbacks_write_operator_decisions(self) -> None:
        self.run_cli("run", "--input", str(FIXTURE))
        data_dir = self.tmp_dir / "data"
        candidate = self.read_jsonl(data_dir / "ledger" / "candidates.jsonl")[0]
        candidate_id = str(candidate["candidate_id"])
        updates_path = self.tmp_dir / "telegram-updates.json"
        updates_path.write_text(
            json.dumps(
                {
                    "ok": True,
                    "result": [
                        {
                            "update_id": 10,
                            "message": {
                                "chat": {"id": "12345"},
                                "text": f"/proof {candidate_id} looks close",
                            },
                        },
                        {
                            "update_id": 11,
                            "callback_query": {
                                "id": "cb1",
                                "data": f"osfb|park|{candidate_id}",
                                "message": {"chat": {"id": "12345"}},
                            },
                        },
                        {
                            "update_id": 12,
                            "message": {"chat": {"id": "999"}, "text": f"/reject {candidate_id} wrong chat"},
                        },
                        {
                            "update_id": 13,
                            "callback_query": {
                                "id": "cb-bad",
                                "data": f"osfb|unknown|{candidate_id}",
                                "message": {"chat": {"id": "12345"}},
                            },
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )
        answered: list[str] = []

        def fake_answer(token: str, api_base: str, callback_query_id: str, text: str, timeout: int) -> dict[str, object]:
            answered.append(callback_query_id)
            return {"ok": True}

        result = scanner.run_telegram_feedback(
            data_dir=data_dir,
            week="2026-W23",
            token="secret-token",
            chat_id="12345",
            api_base=scanner.TELEGRAM_API_BASE,
            timeout=7,
            dry_run=False,
            input_path=updates_path,
            callback_answerer=fake_answer,
        )

        self.assertEqual(result["decisions_written"], 2)
        self.assertEqual(result["ignored_count"], 2)
        self.assertEqual(answered, ["cb1"])
        decisions = self.read_jsonl(data_dir / "ledger" / "operator_decisions.jsonl")
        self.assertEqual([row["decision"] for row in decisions[-2:]], ["operator-proof-approved", "operator-park"])

    def test_telegram_feedback_first_live_poll_primes_offset_without_decisions(self) -> None:
        self.run_cli("run", "--input", str(FIXTURE))
        data_dir = self.tmp_dir / "data"
        candidate = self.read_jsonl(data_dir / "ledger" / "candidates.jsonl")[0]
        candidate_id = str(candidate["candidate_id"])

        def fake_fetch(token: str, api_base: str, offset: int, timeout: int) -> dict[str, object]:
            return {
                "ok": True,
                "result": [
                    {
                        "update_id": 101,
                        "message": {
                            "chat": {"id": "12345"},
                            "text": f"/proof {candidate_id} stale old command",
                        },
                    }
                ],
            }

        result = scanner.run_telegram_feedback(
            data_dir=data_dir,
            week="2026-W23",
            token="secret-token",
            chat_id="12345",
            api_base=scanner.TELEGRAM_API_BASE,
            timeout=7,
            dry_run=False,
            updates_fetcher=fake_fetch,
        )

        self.assertTrue(result["primed"])
        self.assertEqual(result["decisions_found"], 1)
        self.assertEqual(result["decisions_written"], 0)
        self.assertFalse((data_dir / "ledger" / "operator_decisions.jsonl").exists())
        state = json.loads((data_dir / "ledger" / "telegram_feedback_state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["next_update_id"], 102)

    def test_operator_feedback_writes_decision_event_and_filter_update(self) -> None:
        self.run_cli("run", "--input", str(FIXTURE))
        self.run_cli("label")
        self.run_cli("deep-review")
        card = self.read_jsonl(self.tmp_dir / "data" / "ledger" / "opportunity_cards.jsonl")[0]
        candidate_id = str(card["candidate_id"])
        feedback_path = self.tmp_dir / "operator-feedback.jsonl"
        feedback_path.write_text(
            json.dumps(
                {
                    "candidate_id": candidate_id,
                    "decision": "operator-reject",
                    "reason_codes": ["not-close-to-me"],
                    "notes": "Operator would not use this.",
                    "reusable_filter_update": True,
                    "filter_update": {
                        "proposed_change": "Down-rank tools Operator would not personally use.",
                        "target_doc": "docs/opportunity-filter-v2.md",
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )

        result = self.run_cli("operator-feedback", "--input", str(feedback_path))
        payload = json.loads(result.stdout)
        self.assertEqual(payload["decisions_written"], 1)
        self.assertEqual(payload["events_written"], 1)
        self.assertEqual(payload["filter_updates_written"], 1)

        data_dir = self.tmp_dir / "data"
        decisions = self.read_jsonl(data_dir / "ledger" / "operator_decisions.jsonl")
        filter_updates = self.read_jsonl(data_dir / "ledger" / "filter_updates.jsonl")
        events = self.read_jsonl(data_dir / "ledger" / "events.jsonl")
        digest_text = (data_dir / "reports" / "2026-W23-digest.md").read_text(encoding="utf-8")

        self.assertEqual(decisions[-1]["decision"], "operator-reject")
        self.assertEqual(filter_updates[-1]["status"], "open")
        self.assertEqual(events[-1]["layer"], "operator-feedback")
        self.assertEqual(events[-1]["to_status"], "operator-reject")
        self.assertIn("Opportunity Scanner Digest", digest_text)

    def test_calibration_report_tracks_yield_reasons_and_filter_drift(self) -> None:
        self.run_cli("run", "--input", str(FIXTURE))
        self.run_cli("label")
        self.run_cli("deep-review")
        card = self.read_jsonl(self.tmp_dir / "data" / "ledger" / "opportunity_cards.jsonl")[0]
        feedback_path = self.tmp_dir / "operator-feedback.jsonl"
        feedback_path.write_text(
            json.dumps(
                {
                    "candidate_id": str(card["candidate_id"]),
                    "decision": "filter-update-needed",
                    "reason_codes": ["filter-too-generous"],
                    "notes": "Use this as a reusable filter lesson.",
                    "filter_update": {"proposed_change": "Tighten brand-copy risk handling."},
                }
            )
            + "\n",
            encoding="utf-8",
        )
        self.run_cli("operator-feedback", "--input", str(feedback_path))

        result = self.run_cli("calibration")
        payload = json.loads(result.stdout)
        report = Path(payload["report_path"])
        self.assertTrue(report.exists())
        report_text = report.read_text(encoding="utf-8")
        calibrations = self.read_jsonl(self.tmp_dir / "data" / "ledger" / "calibrations.jsonl")

        self.assertIn("Source-Lane Yield", report_text)
        self.assertIn("Reason-Code Histogram", report_text)
        self.assertIn("Proof-Card Conversion", report_text)
        self.assertIn("Filter Drift Notes", report_text)
        self.assertIn("manual-fixture", report_text)
        self.assertIn("filter-too-generous", report_text)
        self.assertEqual(calibrations[-1]["week"], "2026-W23")
        self.assertTrue(calibrations[-1]["open_filter_updates"])

    def test_rescore_reprocesses_old_raw_week_into_target_week(self) -> None:
        self.run_cli("run", "--input", str(FIXTURE))
        result = self.run_cli("rescore", "--source-week", "2026-W23", "--target-week", "2026-W24")
        payload = json.loads(result.stdout)
        self.assertEqual(payload["source_week"], "2026-W23")
        self.assertEqual(payload["target_week"], "2026-W24")
        self.assertIn("calibration_report_path", payload)

        data_dir = self.tmp_dir / "data"
        raw_target = self.read_jsonl(data_dir / "raw" / "2026-W24" / "candidates.jsonl")
        rescore_runs = self.read_jsonl(data_dir / "ledger" / "rescore_runs.jsonl")
        report = data_dir / "reports" / "2026-W24-calibration.md"

        self.assertEqual(len(raw_target), 3)
        self.assertEqual(rescore_runs[-1]["source_week"], "2026-W23")
        self.assertEqual(rescore_runs[-1]["target_week"], "2026-W24")
        self.assertTrue(report.exists())

    def test_dashboard_writes_static_html_with_candidate_links(self) -> None:
        self.run_cli("run", "--input", str(FIXTURE))
        self.run_cli("label")
        self.run_cli("deep-review")
        self.run_cli("digest")
        self.run_cli("calibration")

        result = self.run_cli("dashboard")
        payload = json.loads(result.stdout)
        dashboard = Path(payload["dashboard_path"])
        self.assertTrue(dashboard.exists())
        html_text = dashboard.read_text(encoding="utf-8")
        self.assertIn("<!doctype html>", html_text)
        self.assertIn("Opportunity Scanner Dashboard", html_text)
        self.assertIn("Signal CLI Helper", html_text)
        self.assertIn("Status Counts", html_text)
        self.assertIn("../ledger/evidence/", html_text)


if __name__ == "__main__":
    unittest.main()
