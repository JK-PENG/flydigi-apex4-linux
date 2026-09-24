# SPDX-License-Identifier: MIT
import os
import pathlib
import subprocess
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class InstallTests(unittest.TestCase):
    def sandbox(self, tmp):
        root = pathlib.Path(tmp)
        home = root / "home"
        fake_bin = root / "bin"
        log = root / "systemctl.log"
        home.mkdir()
        fake_bin.mkdir()
        for name, body in {
                "python3": "#!/bin/sh\nexit 0\n",
                "sudo": "#!/bin/sh\nexit 0\n",
                "systemctl": (
                    "#!/bin/sh\n"
                    "printf '%s\\n' \"$*\" >> \"$APEX4_TEST_SYSTEMCTL_LOG\"\n"
                    "[ \"${1:-}\" = --user ] && shift\n"
                    "cmd=${1:-}; [ $# -gt 0 ] && shift\n"
                    "[ \"$cmd\" = \"${APEX4_TEST_FAIL_COMMAND:-}\" ] && exit 1\n"
                    "case \"$cmd\" in\n"
                    "  is-active) [ \"${1:-}\" = --quiet ] && shift; "
                    "if [ -e \"$APEX4_TEST_SYSTEMCTL_STATE/${1:-none}\" ]; "
                    "then echo active; exit 0; else echo inactive; "
                    "exit ${APEX4_TEST_INACTIVE_RC:-3}; fi ;;\n"
                    "  stop) [ \"${1:-}\" = \"${APEX4_TEST_IGNORE_STOP_UNIT:-}\" ] || "
                    "rm -f \"$APEX4_TEST_SYSTEMCTL_STATE/${1:-none}\" ;;\n"
                    "  disable) [ \"${1:-}\" = --now ] && shift; "
                    "rm -f \"$APEX4_TEST_SYSTEMCTL_STATE/${1:-none}\" ;;\n"
                    "  start|restart) touch \"$APEX4_TEST_SYSTEMCTL_STATE/${1:-none}\" ;;\n"
                    "esac\n"
                    "exit 0\n"),
        }.items():
            path = fake_bin / name
            path.write_text(body, encoding="utf-8")
            path.chmod(0o755)
        env = dict(
            os.environ,
            HOME=str(home),
            XDG_DATA_HOME=str(root / "data"),
            XDG_CONFIG_HOME=str(root / "config"),
            APEX4_TEST_SYSTEMCTL_LOG=str(log),
            APEX4_TEST_SYSTEMCTL_STATE=str(root / "systemctl-state"),
            PATH=str(fake_bin) + os.pathsep + os.environ["PATH"],
        )
        (root / "systemctl-state").mkdir()
        return root, env, log

    def run_install(self, env, *args):
        return subprocess.run(
            ["bash", str(ROOT / "install.sh")] + list(args),
            cwd=ROOT, env=env, capture_output=True, text=True)

    def test_runtime_install_includes_license_notices(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, env, _log = self.sandbox(tmp)
            result = self.run_install(env, "--force", "--no-hide-pad")
            self.assertEqual(result.returncode, 0, result.stderr)
            installed = root / "data" / "flydigi-apex4"
            for name in ("LICENSE", "THIRD_PARTY_NOTICES.md"):
                with self.subTest(name=name):
                    self.assertTrue((installed / name).is_file(),
                                    "%s was not installed" % name)
                    self.assertEqual(
                        (installed / name).read_bytes(),
                        (ROOT / name).read_bytes())

    def test_upgrade_replaces_stale_tree_and_restarts_service(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, env, log = self.sandbox(tmp)
            installed = root / "data" / "flydigi-apex4"
            installed.mkdir(parents=True)
            (installed / "stale.py").write_text("obsolete\n", encoding="utf-8")
            result = self.run_install(env, "--force", "--no-hide-pad")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((installed / "stale.py").exists())
            calls = log.read_text(encoding="utf-8")
            self.assertIn("--user stop apex4-relay-manual.service", calls)
            self.assertIn("--user stop flydigi-apex4.service", calls)
            self.assertIn("--user restart flydigi-apex4.service", calls)

    def test_no_hide_pad_removes_owned_previous_environment_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, env, _log = self.sandbox(tmp)
            hide = root / "config" / "environment.d" / "apex4-ds5.conf"
            hide.parent.mkdir(parents=True)
            hide.write_text("old hide\n", encoding="utf-8")
            result = self.run_install(env, "--force", "--no-hide-pad")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(hide.exists())

    def test_upgrade_refuses_to_replace_runtime_if_manual_writer_will_not_stop(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, env, _log = self.sandbox(tmp)
            installed = root / "data" / "flydigi-apex4"
            installed.mkdir(parents=True)
            marker = installed / "keep.txt"
            marker.write_text("current runtime\n", encoding="utf-8")
            manual = "apex4-relay-manual.service"
            (root / "systemctl-state" / manual).touch()
            env["APEX4_TEST_IGNORE_STOP_UNIT"] = manual
            result = self.run_install(env, "--force", "--no-hide-pad")
            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(marker.exists())
            self.assertIn("did not stop", result.stderr)

    def test_upgrade_refuses_when_systemd_state_cannot_be_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, env, _log = self.sandbox(tmp)
            installed = root / "data" / "flydigi-apex4"
            installed.mkdir(parents=True)
            marker = installed / "keep.txt"
            marker.write_text("current runtime\n", encoding="utf-8")
            env["APEX4_TEST_FAIL_COMMAND"] = "is-active"
            result = self.run_install(env, "--force", "--no-hide-pad")
            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(marker.exists())
            self.assertIn("could not verify", result.stderr)

    def test_upgrade_accepts_verified_inactive_with_not_found_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            _root, env, _log = self.sandbox(tmp)
            env["APEX4_TEST_INACTIVE_RC"] = "4"
            result = self.run_install(env, "--force", "--no-hide-pad")
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_upgrade_rolls_back_when_service_enable_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, env, _log = self.sandbox(tmp)
            installed = root / "data" / "flydigi-apex4"
            installed.mkdir(parents=True)
            marker = installed / "keep.txt"
            marker.write_text("current runtime\n", encoding="utf-8")
            env["APEX4_TEST_FAIL_COMMAND"] = "enable"
            result = self.run_install(env, "--force", "--no-hide-pad")
            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(marker.exists())
            self.assertIn("restoring previous runtime", result.stderr)

    def test_upgrade_and_failed_restart_preserve_existing_config_bytes(self):
        original = (b'{ "trigger_profile" : "disabled", "paddle_bits": '
                    b'[2,3,4,5], "gyro_map": "-pitch,yaw,roll" }\n')
        for fail_command in (None, "enable"):
            with self.subTest(fail_command=fail_command), \
                    tempfile.TemporaryDirectory() as tmp:
                root, env, _log = self.sandbox(tmp)
                config_path = (root / "config" / "flydigi-apex4"
                               / "config.json")
                config_path.parent.mkdir(parents=True)
                config_path.write_bytes(original)
                if fail_command:
                    env["APEX4_TEST_FAIL_COMMAND"] = fail_command
                result = self.run_install(env, "--force", "--no-hide-pad")
                self.assertEqual(result.returncode == 0, fail_command is None,
                                 result.stderr)
                self.assertEqual(config_path.read_bytes(), original)

    def test_uninstall_stops_manual_writer_before_removing_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, env, log = self.sandbox(tmp)
            installed = root / "data" / "flydigi-apex4"
            (installed / "tools").mkdir(parents=True)
            (installed / "tools" / "rumble-off.py").write_text(
                "# test\n", encoding="utf-8")
            result = self.run_install(env, "--uninstall")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(installed.exists())
            calls = log.read_text(encoding="utf-8")
            self.assertIn("--user stop apex4-relay-manual.service", calls)


if __name__ == "__main__":
    unittest.main()
