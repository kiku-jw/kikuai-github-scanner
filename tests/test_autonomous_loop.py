from pathlib import Path
import datetime
import importlib.util
import json
import shutil
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_autonomous_loop.py"
SPEC = importlib.util.spec_from_file_location("run_autonomous_loop", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Cannot load run_autonomous_loop module")
loop = importlib.util.module_from_spec(SPEC)
sys.modules["run_autonomous_loop"] = loop
SPEC.loader.exec_module(loop)


class FakeRunner:
    def __init__(self, fail_name: str = "") -> None:
        self.fail_name = fail_name
        self.commands: list[list[str]] = []

    def __call__(self, command: list[str], cwd: Path, env: dict[str, str]) -> object:
        self.commands.append(command)
        name = command_name(command)
        if name == self.fail_name:
            return loop.CommandOutcome(1, "", f"failed with {env.get('GITHUB_TOKEN', '')}")
        payload = {"ok": True, "name": name}
        if name == "github-monitor":
            payload = {"status": "success", "candidate_counts": {"total_collected": 1}}
        if name == "sync-github-project":
            payload = {"added_count": 1, "skipped_count": 0, "dry_run_count": 0, "candidate_issue_count": 1}
        if name == "reddit-demand":
            payload = {"collection": {"post_count": 1, "comment_count": 1, "candidate_count": 1}}
        if name == "ecosystems-enrich":
            payload = {"candidate_count": 1, "enrichment_count": 1, "written_count": 1, "dry_run": False}
        if name == "repo-digest-batch":
            payload = {"candidate_count": 1, "digested_count": 1, "failed_count": 0, "dry_run": False}
        if name == "oss-bounty-radar":
            payload = {"candidate_count": 2, "skipped_count": 3}
        if name == "send-telegram-digest" and "--dry-run" in command:
            payload = {"dry_run": True, "message_count": 1}
        if name == "send-telegram-digest" and "--dry-run" not in command:
            payload = {"dry_run": False, "sent_message_ids": [42]}
        if name == "telegram-feedback":
            payload = {"decisions_written": 1, "ignored_count": 1, "callbacks_answered": 1, "filter_updates_written": 0}
        return loop.CommandOutcome(0, json.dumps(payload), "")


class FakeFailureIssueClient:
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
        }


def command_name(command: list[str]) -> str:
    if command and command[0].endswith("run_radar.sh"):
        return "oss-bounty-radar-scan"
    if command[1].endswith("run_github_monitor.py"):
        return "github-monitor"
    index = command.index("--week")
    return command[index + 2]


class AutonomousLoopTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="autonomous-loop-test-"))

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir)

    def write_config(self, payload: dict[str, object]) -> Path:
        path = self.tmp_dir / "autonomous-loop.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def base_config(self) -> dict[str, object]:
        return {
            "enabled": True,
            "data_dir": str(self.tmp_dir / "data"),
            "state_path": str(self.tmp_dir / "data" / "runs" / "state.json"),
            "lock_path": str(self.tmp_dir / "data" / "runs" / "loop.lock"),
            "lock_stale_minutes": 180,
            "max_jobs_per_tick": 2,
            "send_telegram": True,
            "jobs": [
                {
                    "id": "github-monitor-daily",
                    "type": "github-monitor",
                    "enabled": True,
                    "interval_hours": 24,
                    "config": "config/github-monitor.json",
                    "mirror_github_issues": True,
                    "mirror_repo": "kiku-jw/kikuai-github-scanner",
                    "send_telegram": True,
                },
                {
                    "id": "hn-demand-daily",
                    "type": "hn-demand",
                    "enabled": True,
                    "interval_hours": 24,
                    "max_stories": 2,
                    "comments_per_story": 1,
                    "max_total_items": 5,
                    "max_clusters": 1,
                    "max_candidates": 1,
                    "ingest": True,
                    "post_pipeline": True,
                    "deep_review_max_candidates": 1,
                    "mirror_github_issues": True,
                    "mirror_repo": "kiku-jw/kikuai-github-scanner",
                    "send_telegram": True,
                },
            ],
        }

    def with_failure_reporting(self, payload: dict[str, object]) -> dict[str, object]:
        payload["failure_issue_reporting"] = {
            "enabled": True,
            "repo": "kiku-jw/kikuai-github-scanner",
            "labels": ["opportunity-scanner", "autonomous-loop", "type:failure"],
        }
        return payload

    def test_load_env_file_into_does_not_overwrite_existing_values(self) -> None:
        env_path = self.tmp_dir / ".env"
        env_path.write_text(
            "\n".join(
                [
                    "GITHUB_TOKEN=file-token",
                    "TELEGRAM_CHAT_ID='12345'",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        env = {"GITHUB_TOKEN": "process-token"}

        loaded = loop.load_env_file_into(env, env_path)

        self.assertEqual(env["GITHUB_TOKEN"], "process-token")
        self.assertEqual(env["TELEGRAM_CHAT_ID"], "12345")
        self.assertEqual(loaded, ["TELEGRAM_CHAT_ID"])

    def test_due_jobs_run_and_update_state(self) -> None:
        fake = FakeRunner()
        config_path = self.write_config(self.base_config())

        result = loop.run_autonomous_loop(
            config_path=config_path,
            week="2026-W24",
            send_requested=True,
            dry_run=False,
            force=False,
            runner=fake,
            env={"GITHUB_TOKEN": "secret-token"},
            now=datetime.datetime(2026, 6, 13, tzinfo=datetime.timezone.utc),
        )

        names = [command_name(command) for command in fake.commands]
        self.assertEqual(
            names,
            [
                "github-monitor",
                "mirror-github-issues",
                "send-telegram-digest",
                "send-telegram-digest",
                "hn-demand",
                "label",
                "deep-review",
                "digest",
                "calibration",
                "dashboard",
                "mirror-github-issues",
                "send-telegram-digest",
                "send-telegram-digest",
            ],
        )
        self.assertEqual(result["status"], "success")
        self.assertIn("--skip-empty", fake.commands[-1])
        self.assertEqual(result["health_summary"]["succeeded_jobs"], 2)
        self.assertEqual(result["health_summary"]["failed_jobs"], 0)
        self.assertEqual(result["health_summary"]["mirror_counts"]["created"], 0)
        self.assertNotIn("--send", fake.commands[0])
        self.assertIn("--skip-empty", fake.commands[3])
        state = json.loads((self.tmp_dir / "data" / "runs" / "state.json").read_text(encoding="utf-8"))
        jobs = state["jobs"]
        self.assertIn("github-monitor-daily", jobs)
        self.assertIn("hn-demand-daily", jobs)
        self.assertEqual(jobs["github-monitor-daily"]["last_status"], "success")
        log_text = Path(str(result["run_log_path"])).read_text(encoding="utf-8")
        self.assertNotIn("secret-token", log_text)

    def test_not_due_jobs_skip_without_commands(self) -> None:
        payload = self.base_config()
        state_path = Path(str(payload["state_path"]))
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps(
                {
                    "jobs": {
                        "github-monitor-daily": {"last_success_at": "2026-06-13T00:00:00Z"},
                        "hn-demand-daily": {"last_success_at": "2026-06-13T00:00:00Z"},
                    }
                }
            ),
            encoding="utf-8",
        )
        fake = FakeRunner()

        result = loop.run_autonomous_loop(
            config_path=self.write_config(payload),
            week="2026-W24",
            send_requested=True,
            dry_run=False,
            force=False,
            runner=fake,
            env={},
            now=datetime.datetime(2026, 6, 13, 1, tzinfo=datetime.timezone.utc),
        )

        self.assertEqual(fake.commands, [])
        self.assertEqual(result["status"], "noop")
        self.assertTrue(all(job["status"] == "skipped" for job in result["jobs"]))

    def test_dry_run_does_not_update_state_or_send(self) -> None:
        payload = self.base_config()
        fake = FakeRunner()

        result = loop.run_autonomous_loop(
            config_path=self.write_config(payload),
            week="2026-W24",
            send_requested=True,
            dry_run=True,
            force=True,
            runner=fake,
            env={},
            now=datetime.datetime(2026, 6, 13, tzinfo=datetime.timezone.utc),
        )

        self.assertEqual(fake.commands, [])
        self.assertEqual(result["status"], "success")
        self.assertFalse((self.tmp_dir / "data" / "runs" / "state.json").exists())
        self.assertTrue(all(job["status"] == "dry-run" for job in result["jobs"]))

    def test_project_sync_runs_after_issue_mirror_when_configured(self) -> None:
        payload = self.base_config()
        payload["max_jobs_per_tick"] = 1
        payload["jobs"][0]["sync_github_project"] = True
        payload["jobs"][0]["project_owner"] = "kiku-jw"
        payload["jobs"][0]["project_number"] = 1
        fake = FakeRunner()

        result = loop.run_autonomous_loop(
            config_path=self.write_config(payload),
            week="2026-W24",
            send_requested=False,
            dry_run=False,
            force=True,
            runner=fake,
            env={"GITHUB_TOKEN": "secret-token"},
            now=datetime.datetime(2026, 6, 13, tzinfo=datetime.timezone.utc),
        )

        names = [command_name(command) for command in fake.commands]
        self.assertEqual(names, ["github-monitor", "mirror-github-issues", "sync-github-project", "send-telegram-digest"])
        project_command = fake.commands[2]
        self.assertIn("--project-owner", project_command)
        self.assertIn("--project-number", project_command)
        self.assertEqual(result["health_summary"]["project_counts"]["added"], 1)

    def test_project_sync_missing_target_is_skipped_without_blocking_job(self) -> None:
        payload = self.base_config()
        payload["max_jobs_per_tick"] = 1
        payload["jobs"][0]["sync_github_project"] = True
        fake = FakeRunner()

        result = loop.run_autonomous_loop(
            config_path=self.write_config(payload),
            week="2026-W24",
            send_requested=False,
            dry_run=False,
            force=True,
            runner=fake,
            env={"GITHUB_TOKEN": "secret-token"},
            now=datetime.datetime(2026, 6, 13, tzinfo=datetime.timezone.utc),
        )

        names = [command_name(command) for command in fake.commands]
        self.assertEqual(names, ["github-monitor", "mirror-github-issues", "send-telegram-digest"])
        self.assertEqual(result["status"], "success")

    def test_post_pipeline_can_run_enrichment_and_digest_before_deep_review(self) -> None:
        payload = self.base_config()
        payload["max_jobs_per_tick"] = 1
        hn_job = payload["jobs"][1]
        hn_job["ecosystems_enrich"] = True
        hn_job["ecosystems_max_candidates"] = 2
        hn_job["repo_digest_batch"] = True
        hn_job["repo_digest_max_candidates"] = 1
        hn_job["repo_digest_max_files"] = 7
        hn_job["repo_digest_max_bytes"] = 8000
        hn_job["repo_digest_clone_timeout_seconds"] = 9
        payload["jobs"] = [hn_job]
        fake = FakeRunner()

        result = loop.run_autonomous_loop(
            config_path=self.write_config(payload),
            week="2026-W24",
            send_requested=True,
            dry_run=False,
            force=True,
            runner=fake,
            env={"GITHUB_TOKEN": "secret-token"},
            now=datetime.datetime(2026, 6, 13, tzinfo=datetime.timezone.utc),
        )

        names = [command_name(command) for command in fake.commands]
        self.assertEqual(
            names,
            [
                "hn-demand",
                "label",
                "ecosystems-enrich",
                "repo-digest-batch",
                "deep-review",
                "digest",
                "calibration",
                "dashboard",
                "mirror-github-issues",
                "send-telegram-digest",
                "send-telegram-digest",
            ],
        )
        digest_command = fake.commands[3]
        self.assertIn("--max-candidates", digest_command)
        self.assertIn("1", digest_command)
        self.assertIn("--max-files", digest_command)
        self.assertIn("7", digest_command)
        self.assertEqual(result["health_summary"]["enrichment_counts"]["written_count"], 1)
        self.assertEqual(result["health_summary"]["repo_digest_counts"]["digested_count"], 1)

    def test_health_check_reports_stale_and_due_jobs_without_state_write(self) -> None:
        payload = self.base_config()
        payload["health_stale_grace_hours"] = 2
        state_path = Path(str(payload["state_path"]))
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps(
                {
                    "jobs": {
                        "github-monitor-daily": {
                            "last_status": "success",
                            "last_success_at": "2026-06-13T00:00:00Z",
                            "last_finished_at": "2026-06-13T00:00:00Z",
                        },
                        "hn-demand-daily": {
                            "last_status": "success",
                            "last_success_at": "2026-06-13T23:00:00Z",
                            "last_finished_at": "2026-06-13T23:00:00Z",
                        },
                    }
                }
            ),
            encoding="utf-8",
        )

        result = loop.autonomous_loop_health(
            config_path=self.write_config(payload),
            env={"TELEGRAM_BOT_TOKEN": "bot", "TELEGRAM_CHAT_ID": "123", "GH_TOKEN": "gh"},
            now=datetime.datetime(2026, 6, 14, 3, tzinfo=datetime.timezone.utc),
        )

        by_id = {str(job["job_id"]): job for job in result["jobs"]}
        self.assertEqual(result["status"], "stale")
        self.assertEqual(result["stale_job_count"], 1)
        self.assertTrue(by_id["github-monitor-daily"]["stale"])
        self.assertTrue(by_id["github-monitor-daily"]["due"])
        self.assertFalse(by_id["hn-demand-daily"]["stale"])
        self.assertTrue(result["telegram_configured"])
        self.assertTrue(result["github_configured"])

    def test_reddit_demand_and_telegram_feedback_jobs_are_orchestrated(self) -> None:
        payload = self.base_config()
        payload["max_jobs_per_tick"] = 2
        payload["jobs"] = [
            {
                "id": "reddit-demand-weekly",
                "type": "reddit-demand",
                "enabled": True,
                "interval_hours": 168,
                "subreddits": ["webdev", "SaaS"],
                "sort": "hot",
                "max_posts_per_subreddit": 2,
                "comments_per_post": 1,
                "max_total_items": 6,
                "max_clusters": 2,
                "max_candidates": 1,
                "ingest": False,
                "post_pipeline": False,
            },
            {
                "id": "telegram-feedback",
                "type": "telegram-feedback",
                "enabled": True,
                "interval_hours": 4,
            },
        ]
        fake = FakeRunner()

        result = loop.run_autonomous_loop(
            config_path=self.write_config(payload),
            week="2026-W24",
            send_requested=False,
            dry_run=False,
            force=True,
            runner=fake,
            env={
                "TELEGRAM_BOT_TOKEN": "secret-bot",
                "TELEGRAM_CHAT_ID": "12345",
                "REDDIT_USER_AGENT": "kikuai-github-scanner-test/1.0",
                "REDDIT_CLIENT_ID": "reddit-client",
                "REDDIT_CLIENT_SECRET": "reddit-secret",
            },
            now=datetime.datetime(2026, 6, 13, tzinfo=datetime.timezone.utc),
        )

        names = [command_name(command) for command in fake.commands]
        self.assertEqual(names, ["reddit-demand", "telegram-feedback"])
        reddit_command = fake.commands[0]
        self.assertIn("--subreddits", reddit_command)
        self.assertIn("webdev", reddit_command)
        self.assertEqual(result["health_summary"]["reddit_counts"]["candidates"], 1)
        self.assertEqual(result["health_summary"]["feedback_counts"]["decisions_written"], 1)

    def test_oss_bounty_radar_job_runs_external_scan_and_import(self) -> None:
        payload = self.base_config()
        payload["max_jobs_per_tick"] = 1
        payload["jobs"] = [
            {
                "id": "oss-bounty-radar-daily",
                "type": "oss-bounty-radar",
                "enabled": True,
                "interval_hours": 24,
                "external_command": ["../oss-bounty-radar/scripts/run_radar.sh"],
                "input": "../oss-bounty-radar/reports/latest.json",
                "max_candidates": 4,
                "min_score": 14,
                "source_verdicts": ["candidate", "watchlist"],
                "ingest": True,
                "post_pipeline": False,
            }
        ]
        fake = FakeRunner()

        result = loop.run_autonomous_loop(
            config_path=self.write_config(payload),
            week="2026-W24",
            send_requested=False,
            dry_run=False,
            force=True,
            runner=fake,
            env={},
            now=datetime.datetime(2026, 6, 13, tzinfo=datetime.timezone.utc),
        )

        names = [command_name(command) for command in fake.commands]
        self.assertEqual(names, ["oss-bounty-radar-scan", "oss-bounty-radar"])
        import_command = fake.commands[1]
        self.assertIn("--ingest", import_command)
        self.assertIn("--min-score", import_command)
        self.assertIn("14", import_command)
        self.assertEqual(result["health_summary"]["oss_bounty_counts"]["candidate_count"], 2)
        self.assertEqual(result["health_summary"]["oss_bounty_counts"]["skipped_count"], 3)

    def test_existing_lock_blocks_run(self) -> None:
        payload = self.base_config()
        lock_path = Path(str(payload["lock_path"]))
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.write_text("locked\n", encoding="utf-8")

        with self.assertRaises(loop.LoopRunError):
            loop.run_autonomous_loop(
                config_path=self.write_config(payload),
                week="2026-W24",
                send_requested=False,
                dry_run=False,
                force=False,
                runner=FakeRunner(),
                env={},
                now=datetime.datetime(2026, 6, 13, tzinfo=datetime.timezone.utc),
            )

    def test_job_failure_is_partial_and_redacted(self) -> None:
        fake = FakeRunner(fail_name="label")

        result = loop.run_autonomous_loop(
            config_path=self.write_config(self.base_config()),
            week="2026-W24",
            send_requested=False,
            dry_run=False,
            force=False,
            runner=fake,
            env={"GITHUB_TOKEN": "secret-token"},
            now=datetime.datetime(2026, 6, 13, tzinfo=datetime.timezone.utc),
        )

        self.assertEqual(result["status"], "partial-failure")
        failed = [job for job in result["jobs"] if job["status"] == "failed"]
        self.assertEqual(len(failed), 1)
        log_text = Path(str(result["run_log_path"])).read_text(encoding="utf-8")
        self.assertNotIn("secret-token", log_text)
        self.assertIn("[REDACTED]", log_text)

    def test_failed_job_creates_failure_issue_and_stores_state(self) -> None:
        fake = FakeRunner(fail_name="label")
        failure_client = FakeFailureIssueClient()

        result = loop.run_autonomous_loop(
            config_path=self.write_config(self.with_failure_reporting(self.base_config())),
            week="2026-W24",
            send_requested=False,
            dry_run=False,
            force=False,
            runner=fake,
            env={"GITHUB_TOKEN": "secret-token"},
            now=datetime.datetime(2026, 6, 13, tzinfo=datetime.timezone.utc),
            failure_client=failure_client,
        )

        self.assertEqual(result["status"], "partial-failure")
        self.assertEqual(len(failure_client.created), 1)
        self.assertEqual(result["failure_issue_notifications"][0]["action"], "created-failure-issue")
        created_body = str(failure_client.created[0]["body"]["body"])
        self.assertIn("autonomous-loop-failure=hn-demand-daily", created_body)
        self.assertNotIn("secret-token", created_body)
        self.assertIn("[REDACTED]", created_body)
        state = json.loads((self.tmp_dir / "data" / "runs" / "state.json").read_text(encoding="utf-8"))
        hn_state = state["jobs"]["hn-demand-daily"]
        self.assertEqual(hn_state["open_failure_issue_number"], 1)
        log_text = Path(str(result["run_log_path"])).read_text(encoding="utf-8")
        self.assertIn("health_summary", log_text)

    def test_repeated_failure_updates_existing_failure_issue_without_duplicate(self) -> None:
        payload = self.with_failure_reporting(self.base_config())
        state_path = Path(str(payload["state_path"]))
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps(
                {
                    "jobs": {
                        "hn-demand-daily": {
                            "last_success_at": "2026-06-01T00:00:00Z",
                            "open_failure_issue_number": 12,
                            "open_failure_issue_url": "https://github.com/kiku-jw/kikuai-github-scanner/issues/12",
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        failure_client = FakeFailureIssueClient()

        result = loop.run_autonomous_loop(
            config_path=self.write_config(payload),
            week="2026-W24",
            send_requested=False,
            dry_run=False,
            force=True,
            runner=FakeRunner(fail_name="label"),
            env={"GITHUB_TOKEN": "secret-token"},
            now=datetime.datetime(2026, 6, 13, tzinfo=datetime.timezone.utc),
            failure_client=failure_client,
        )

        self.assertEqual(result["status"], "partial-failure")
        self.assertEqual(failure_client.created, [])
        self.assertEqual(len(failure_client.updated), 1)
        self.assertIn("/issues/12", failure_client.updated[0]["path"])
        notifications = result["failure_issue_notifications"]
        self.assertTrue(any(row["action"] == "updated-failure-issue" for row in notifications))

    def test_recovered_job_comments_and_clears_open_failure_state(self) -> None:
        payload = self.with_failure_reporting(self.base_config())
        state_path = Path(str(payload["state_path"]))
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps(
                {
                    "jobs": {
                        "github-monitor-daily": {
                            "last_success_at": "2026-06-01T00:00:00Z",
                            "open_failure_issue_number": 21,
                            "open_failure_issue_url": "https://github.com/kiku-jw/kikuai-github-scanner/issues/21",
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        failure_client = FakeFailureIssueClient()

        result = loop.run_autonomous_loop(
            config_path=self.write_config(payload),
            week="2026-W24",
            send_requested=False,
            dry_run=False,
            force=True,
            runner=FakeRunner(),
            env={"GITHUB_TOKEN": "secret-token"},
            now=datetime.datetime(2026, 6, 13, tzinfo=datetime.timezone.utc),
            failure_client=failure_client,
        )

        self.assertEqual(result["status"], "success")
        self.assertEqual(len(failure_client.comments), 1)
        self.assertIn("recovered", str(failure_client.comments[0]["body"]["body"]))
        state = json.loads((self.tmp_dir / "data" / "runs" / "state.json").read_text(encoding="utf-8"))
        github_state = state["jobs"]["github-monitor-daily"]
        self.assertNotIn("open_failure_issue_number", github_state)
        self.assertEqual(github_state["last_recovery_issue_action"], "commented-recovery")


if __name__ == "__main__":
    unittest.main()
