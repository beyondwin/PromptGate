from datetime import datetime
import json
import tempfile
import unittest
from pathlib import Path

from promptgate.hooks import format_hook_install_report, install_hook


ROOT = Path(__file__).resolve().parents[1]


class PromptGateHookInstallDryRunTest(unittest.TestCase):
    def test_codex_dry_run_uses_codex_home_without_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / "codex"

            report = install_hook(
                "codex",
                apply=False,
                project_root=ROOT,
                env={"CODEX_HOME": str(codex_home)},
            )

            self.assertTrue(report.ok)
            self.assertEqual(report.adapter, "codex")
            self.assertEqual(report.mode, "dry-run")
            self.assertEqual(Path(report.target_path), codex_home / "config.json")
            self.assertFalse((codex_home / "config.json").exists())
            self.assertFalse(report.target_exists)
            self.assertFalse(report.parent_exists)
            self.assertFalse(report.parent_created)
            self.assertFalse(report.installed)
            self.assertTrue(report.changed)
            self.assertIsNone(report.backup_path)
            self.assertFalse(report.doctor_ran)
            self.assertIsNone(report.doctor_ok)

    def test_claude_dry_run_uses_claude_config_dir_without_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            claude_dir = Path(tmp) / "claude"

            report = install_hook(
                "claude",
                apply=False,
                project_root=ROOT,
                env={"CLAUDE_CONFIG_DIR": str(claude_dir)},
            )

            self.assertTrue(report.ok)
            self.assertEqual(report.adapter, "claude")
            self.assertEqual(Path(report.target_path), claude_dir / "settings.json")
            self.assertFalse((claude_dir / "settings.json").exists())
            self.assertTrue(report.changed)

    def test_missing_hook_script_fails_in_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = install_hook(
                "codex",
                target=Path(tmp) / "config.json",
                apply=False,
                project_root=Path(tmp),
                env={},
            )

            self.assertFalse(report.ok)
            self.assertIn("missing hook script", report.error)
            self.assertFalse((Path(tmp) / "config.json").exists())

    def test_json_report_contains_stable_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = install_hook(
                "codex",
                target=Path(tmp) / "config.json",
                apply=False,
                project_root=ROOT,
                env={},
            )

            payload = json.loads(format_hook_install_report(report, as_json=True))

            self.assertEqual(
                {
                    "ok",
                    "adapter",
                    "mode",
                    "target_path",
                    "hook_script_path",
                    "target_exists",
                    "parent_exists",
                    "parent_created",
                    "installed",
                    "changed",
                    "backup_path",
                    "doctor_ran",
                    "doctor_ok",
                    "error",
                },
                set(payload),
            )


class PromptGateHookInstallApplyTest(unittest.TestCase):
    def test_apply_creates_missing_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "nested" / "config.json"

            report = install_hook(
                "codex",
                target=target,
                apply=True,
                skip_doctor=True,
                project_root=ROOT,
                env={},
            )

            self.assertTrue(report.ok)
            self.assertTrue(target.exists())
            payload = json.loads(target.read_text(encoding="utf-8"))
            hook = payload["promptgate"]["hooks"]["UserPromptSubmit"]
            self.assertEqual(hook["command"], "python3")
            self.assertEqual(
                hook["args"],
                [str(ROOT / "adapters/codex/hooks/user-prompt-submit.example.py")],
            )
            self.assertTrue(report.changed)
            self.assertTrue(report.installed)
            self.assertTrue(report.parent_created)
            self.assertIsNone(report.backup_path)
            self.assertFalse(report.doctor_ran)

    def test_apply_merges_existing_json_and_preserves_unrelated_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "settings.json"
            target.write_text(
                json.dumps(
                    {
                        "theme": "dark",
                        "promptgate": {
                            "enabled": True,
                            "hooks": {
                                "OtherHook": {
                                    "command": "echo",
                                    "args": ["ok"],
                                }
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )

            report = install_hook(
                "claude",
                target=target,
                apply=True,
                skip_doctor=True,
                project_root=ROOT,
                env={},
            )

            payload = json.loads(target.read_text(encoding="utf-8"))
            self.assertTrue(report.ok)
            self.assertEqual(payload["theme"], "dark")
            self.assertTrue(payload["promptgate"]["enabled"])
            self.assertEqual(payload["promptgate"]["hooks"]["OtherHook"]["command"], "echo")
            self.assertEqual(
                payload["promptgate"]["hooks"]["UserPromptSubmit"]["args"],
                [str(ROOT / "adapters/claude/hooks/user-prompt-submit.example.py")],
            )

    def test_apply_creates_backup_before_modifying_existing_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "config.json"
            original = b'{"theme":"dark"}\n'
            target.write_bytes(original)

            report = install_hook(
                "codex",
                target=target,
                apply=True,
                skip_doctor=True,
                project_root=ROOT,
                env={},
                now=lambda: datetime(2026, 5, 15, 1, 2, 3),
            )

            backup = Path(tmp) / "config.json.promptgate-backup-20260515010203"
            self.assertTrue(report.ok)
            self.assertEqual(Path(report.backup_path), backup)
            self.assertEqual(backup.read_bytes(), original)

    def test_apply_is_idempotent_when_hook_block_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "config.json"

            first = install_hook(
                "codex",
                target=target,
                apply=True,
                skip_doctor=True,
                project_root=ROOT,
                env={},
            )
            second = install_hook(
                "codex",
                target=target,
                apply=True,
                skip_doctor=True,
                project_root=ROOT,
                env={},
            )

            self.assertTrue(first.ok)
            self.assertTrue(second.ok)
            self.assertTrue(second.installed)
            self.assertFalse(second.changed)
            self.assertIsNone(second.backup_path)
            self.assertEqual(list(Path(tmp).glob("*.promptgate-backup-*")), [])

    def test_invalid_json_fails_without_backup_or_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "config.json"
            target.write_bytes(b"{invalid")

            report = install_hook(
                "codex",
                target=target,
                apply=True,
                skip_doctor=True,
                project_root=ROOT,
                env={},
            )

            self.assertFalse(report.ok)
            self.assertIn("target JSON is invalid", report.error)
            self.assertEqual(target.read_bytes(), b"{invalid")
            self.assertEqual(list(Path(tmp).glob("*.promptgate-backup-*")), [])

    def test_non_object_promptgate_key_fails_without_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "config.json"
            original = '{"promptgate": false}\n'
            target.write_text(original, encoding="utf-8")

            report = install_hook(
                "codex",
                target=target,
                apply=True,
                skip_doctor=True,
                project_root=ROOT,
                env={},
            )

            self.assertFalse(report.ok)
            self.assertEqual(report.error, "promptgate key must be an object")
            self.assertEqual(target.read_text(encoding="utf-8"), original)

    def test_apply_runs_doctor_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "config.json"

            report = install_hook(
                "codex",
                target=target,
                apply=True,
                project_root=ROOT,
                env={},
            )

            self.assertTrue(report.ok)
            self.assertTrue(report.doctor_ran)
            self.assertTrue(report.doctor_ok)

    def test_human_report_describes_apply_skip_doctor(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = install_hook(
                "codex",
                target=Path(tmp) / "config.json",
                apply=True,
                skip_doctor=True,
                project_root=ROOT,
                env={},
            )

            output = format_hook_install_report(report)

            self.assertIn("Mode: apply", output)
            self.assertIn("Doctor: skipped by --skip-doctor", output)
            self.assertIn("Result: OK", output)


if __name__ == "__main__":
    unittest.main()
