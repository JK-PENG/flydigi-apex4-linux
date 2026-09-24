# SPDX-License-Identifier: MIT
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from apex4ds5 import config


class ConfigTests(unittest.TestCase):
    def write_config(self, root, value):
        path = pathlib.Path(root) / "config.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def test_adaptive_triggers_requires_json_boolean(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_config(tmp, {"adaptive_triggers": "false"})
            with self.assertRaisesRegex(
                    SystemExit, "adaptive_triggers must be a JSON boolean"):
                config.load(str(path))

    def test_adaptive_triggers_accepts_both_boolean_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            for value, expected in ((False, "disabled"),
                                    (True, "ow2-safe")):
                with self.subTest(value=value, expected=expected):
                    path = self.write_config(
                        tmp, {"adaptive_triggers": value})
                    settings, _source = config.load(str(path))
                    self.assertEqual(settings["trigger_profile"], expected)

    def test_trigger_profile_is_explicit_and_validated(self):
        self.assertEqual(config.DEFAULTS["trigger_profile"], "disabled")
        self.assertNotIn("adaptive_triggers", config.DEFAULTS)
        with tempfile.TemporaryDirectory() as tmp:
            for value in ("disabled", "ow2-safe"):
                with self.subTest(value=value):
                    path = self.write_config(tmp, {"trigger_profile": value})
                    settings, _source = config.load(str(path))
                    self.assertEqual(settings["trigger_profile"], value)
            path = self.write_config(tmp, {"trigger_profile": "compat"})
            with self.assertRaisesRegex(
                    SystemExit, "trigger_profile must be one of"):
                config.load(str(path))

    def test_trigger_profile_and_legacy_switch_cannot_be_combined(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_config(
                tmp, {"trigger_profile": "disabled",
                      "adaptive_triggers": False})
            with self.assertRaisesRegex(
                    SystemExit, "cannot combine trigger_profile"):
                config.load(str(path))

    def test_generic_safe_is_selectable_without_changing_current_default(self):
        self.assertEqual(config.DEFAULTS["trigger_profile"], "disabled")
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_config(tmp, {"trigger_profile": "generic-safe"})
            settings, _source = config.load(str(path))
            self.assertEqual(settings["trigger_profile"], "generic-safe")
        root = pathlib.Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [sys.executable, str(root / "apex4-ds5"),
             "--emulate", "dualsense-edge", "--trigger-profile",
             "generic-safe", "--calib"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_live_generic_profile_is_quiet_but_dry_run_allows_debug(self):
        root = pathlib.Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_config(tmp, {"verbose": True})
            base = [sys.executable, str(root / "apex4-ds5"),
                    "--config", str(path), "--trigger-profile",
                    "generic-safe", "--calib"]
            quiet = subprocess.run(base, capture_output=True, text=True)
            self.assertEqual(quiet.returncode, 0, quiet.stderr)
            self.assertNotIn("settings      :", quiet.stdout)
            for flag in ("--verbose", "--hid-debug", "--trigger-debug"):
                with self.subTest(flag=flag):
                    rejected = subprocess.run(base + [flag], capture_output=True,
                                              text=True)
                    self.assertEqual(rejected.returncode, 2)
            allowed = subprocess.run(
                base + ["--trigger-dry-run", "--trigger-debug"],
                capture_output=True, text=True)
            self.assertEqual(allowed.returncode, 0, allowed.stderr)

    def test_explicit_disabled_survives_future_generic_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_config(
                tmp, {"trigger_profile": "disabled",
                      "paddle_bits": [2, 3, 4, 5],
                      "gyro_map": "-pitch,yaw,roll"})
            with mock.patch.dict(config.DEFAULTS,
                                 {"trigger_profile": "generic-safe"}):
                settings, _source = config.load(str(path))
            self.assertEqual(settings["trigger_profile"], "disabled")
            self.assertEqual(settings["paddle_bits"], [2, 3, 4, 5])
            self.assertEqual(settings["gyro_map"], "-pitch,yaw,roll")

    def test_default_writer_does_not_rewrite_existing_user_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "config.json"
            original = (b'{ "trigger_profile" : "disabled", "paddles": '
                        b'["fn1", "fn2", "paddle-left", "paddle-right"] }\n')
            path.write_bytes(original)
            with mock.patch.dict(config.DEFAULTS,
                                 {"trigger_profile": "generic-safe"}):
                target, written = config.write_default(str(path))
            self.assertEqual(target, str(path))
            self.assertFalse(written)
            self.assertEqual(path.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
