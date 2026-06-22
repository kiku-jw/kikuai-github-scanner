from pathlib import Path
import importlib.util
import json
import shutil
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_github_monitor.py"
SPEC = importlib.util.spec_from_file_location("run_github_monitor", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Cannot load run_github_monitor module")
monitor = importlib.util.module_from_spec(SPEC)
sys.modules["run_github_monitor"] = monitor
SPEC.loader.exec_module(monitor)


class FakeRunner:
    def __init__(self, fail_step: str = "") -> None:
        self.fail_step = fail_step
        self.commands: list[list[str]] = []

    def __call__(self, command: list[str], cwd: Path, env: dict[str, str]) -> object:
        self.commands.append(command)
        step = command_name(command)
        if step == self.fail_step:
            return monitor.CommandOutcome(1, "", f"failed with {env.get('GITHUB_TOKEN', '')}")
        if step == "github-search":
            return monitor.CommandOutcome(0, json.dumps({"collection": {"candidate_count": 2}}), "")
        if step == "send-telegram-digest" and "--dry-run" in command:
            return monitor.CommandOutcome(0, json.dumps({"dry_run": True, "message_count": 1, "character_count": 123}), "")
        if step == "send-telegram-digest":
            return monitor.CommandOutcome(0, json.dumps({"dry_run": False, "message_count": 1, "sent_message_ids": [42]}), "")
        return monitor.CommandOutcome(0, json.dumps({f"{step}_path": f"data/{step}.md"}), "")


def command_name(command: list[str]) -> str:
    index = command.index("--week")
    return command[index + 2]


class GitHubMonitorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="github-monitor-test-"))

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir)

    def write_config(self, payload: dict[str, object]) -> Path:
        config_path = self.tmp_dir / "github-monitor.json"
        config_path.write_text(json.dumps(payload), encoding="utf-8")
        return config_path

    def base_config(self) -> dict[str, object]:
        return {
            "enabled": True,
            "data_dir": str(self.tmp_dir / "data"),
            "default_max_candidates": 3,
            "per_page": 5,
            "issues_per_repo": 1,
            "deep_review_max_candidates": 2,
            "total_candidate_cap": 6,
            "send_telegram": False,
            "write_calibration": True,
            "write_dashboard": True,
            "github_queries": [
                {
                    "id": "enabled-lane",
                    "enabled": True,
                    "query": "hosted dashboard language:Python stars:>50",
                },
                {
                    "id": "disabled-lane",
                    "enabled": False,
                    "query": "broad ai dashboard language:Python stars:>100",
                },
            ],
        }

    def test_load_config_applies_defaults_and_skips_disabled_lanes(self) -> None:
        config = monitor.load_monitor_config(self.write_config(self.base_config()))

        lanes = monitor.enabled_lanes(config)

        self.assertEqual(len(lanes), 1)
        self.assertEqual(lanes[0].lane_id, "enabled-lane")
        self.assertEqual(lanes[0].max_candidates, 3)
        self.assertEqual(lanes[0].per_page, 5)
        self.assertEqual(lanes[0].issues_per_repo, 1)

    def test_load_config_rejects_total_cap_excess(self) -> None:
        payload = self.base_config()
        payload["total_candidate_cap"] = 2

        with self.assertRaises(monitor.MonitorConfigError):
            monitor.load_monitor_config(self.write_config(payload))

    def test_run_monitor_dry_run_executes_pipeline_and_writes_log(self) -> None:
        fake = FakeRunner()
        result = monitor.run_monitor(self.write_config(self.base_config()), "2026-W23", False, fake, {})
        names = [command_name(command) for command in fake.commands]

        self.assertEqual(
            names,
            [
                "github-search",
                "label",
                "deep-review",
                "digest",
                "calibration",
                "dashboard",
                "send-telegram-digest",
            ],
        )
        self.assertIn("--dry-run", fake.commands[-1])
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["candidate_counts"], {"by_lane": {"enabled-lane": 2}, "total_collected": 2})
        self.assertTrue(Path(str(result["run_log_path"])).exists())
        log_text = Path(str(result["run_log_path"])).read_text(encoding="utf-8")
        self.assertIn("send-telegram-digest-dry-run", log_text)
        self.assertNotIn("disabled-lane", json.dumps(result["candidate_counts"]))

    def test_run_monitor_can_enrich_and_digest_before_deep_review(self) -> None:
        payload = self.base_config()
        payload["ecosystems_enrich"] = True
        payload["ecosystems_max_candidates"] = 2
        payload["repo_digest_batch"] = True
        payload["repo_digest_max_candidates"] = 1
        payload["repo_digest_max_files"] = 8
        payload["repo_digest_max_bytes"] = 9000
        payload["repo_digest_clone_timeout_seconds"] = 12
        fake = FakeRunner()

        monitor.run_monitor(self.write_config(payload), "2026-W23", False, fake, {})

        names = [command_name(command) for command in fake.commands]
        self.assertEqual(
            names,
            [
                "github-search",
                "label",
                "ecosystems-enrich",
                "repo-digest-batch",
                "deep-review",
                "digest",
                "calibration",
                "dashboard",
                "send-telegram-digest",
            ],
        )
        digest_command = fake.commands[3]
        self.assertIn("--max-files", digest_command)
        self.assertIn("8", digest_command)
        self.assertIn("--clone-timeout-seconds", digest_command)
        self.assertIn("12", digest_command)

    def test_send_requires_config_flag(self) -> None:
        with self.assertRaises(monitor.MonitorConfigError):
            monitor.run_monitor(self.write_config(self.base_config()), "2026-W23", True, FakeRunner(), {})

    def test_send_runs_after_dry_run_when_config_allows_it(self) -> None:
        payload = self.base_config()
        payload["send_telegram"] = True
        fake = FakeRunner()

        result = monitor.run_monitor(self.write_config(payload), "2026-W23", True, fake, {})

        self.assertEqual(command_name(fake.commands[-2]), "send-telegram-digest")
        self.assertIn("--dry-run", fake.commands[-2])
        self.assertEqual(command_name(fake.commands[-1]), "send-telegram-digest")
        self.assertNotIn("--dry-run", fake.commands[-1])
        self.assertIn("--skip-empty", fake.commands[-1])
        telegram = result["telegram"]
        self.assertIsInstance(telegram, dict)
        self.assertIn("send", telegram)

    def test_failure_writes_sanitized_run_log(self) -> None:
        payload = self.base_config()
        fake = FakeRunner(fail_step="label")
        env = {"GITHUB_TOKEN": "secret-token-value"}

        with self.assertRaises(monitor.MonitorRunError):
            monitor.run_monitor(self.write_config(payload), "2026-W23", False, fake, env)

        logs = list((self.tmp_dir / "data" / "runs").glob("*.json"))
        self.assertEqual(len(logs), 1)
        log_text = logs[0].read_text(encoding="utf-8")
        self.assertIn('"status": "failed"', log_text)
        self.assertIn("Step failed: label", log_text)
        self.assertNotIn("secret-token-value", log_text)
        self.assertIn("[REDACTED]", log_text)


if __name__ == "__main__":
    unittest.main()
