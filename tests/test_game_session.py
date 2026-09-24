# SPDX-License-Identifier: MIT
import pathlib
import shutil
import subprocess
import tempfile
import unittest

from apex4ds5 import game_session


def write_uevent(root, node, hid_id, name):
    path = pathlib.Path(root) / node / "device"
    path.mkdir(parents=True, exist_ok=True)
    (path / "uevent").write_text(
        "HID_ID=%s\nHID_NAME=%s\n" % (hid_id, name), encoding="utf-8")


class FakeCommands:
    def __init__(self, sysfs, daily=True, manual=False,
                 create_dualsense=True, restore_edge=True,
                 keep_edge_during_switch=False,
                 keep_dualsense_during_restore=False, relay_args=()):
        self.sysfs = pathlib.Path(sysfs)
        self.daily = daily
        self.manual = manual
        self.create_dualsense = create_dualsense
        self.restore_edge = restore_edge
        self.keep_edge_during_switch = keep_edge_during_switch
        self.keep_dualsense_during_restore = keep_dualsense_during_restore
        self.manual_invocation = "manual-invocation-1"
        self.relay_args = tuple(relay_args)
        self.calls = []

    def set_identity(self, identity):
        for path in self.sysfs.glob("hidraw*"):
            shutil.rmtree(path)
        if identity is not None:
            write_uevent(self.sysfs, "hidraw0", *identity)

    def __call__(self, argv, **kwargs):
        self.calls.append(list(argv))
        if argv[:3] == ["systemctl", "--user", "is-active"]:
            unit = argv[3]
            active = self.daily if unit == game_session.DAILY_UNIT else self.manual
            return subprocess.CompletedProcess(argv, 0 if active else 3)
        if (argv[:3] == ["systemctl", "--user", "show"]
                and game_session.MANUAL_UNIT in argv):
            return subprocess.CompletedProcess(
                argv, 0, stdout=self.manual_invocation + "\n")
        if argv == (["/installed/apex4-relay", "start", "--", "--emulate",
                     "dualsense"] + list(self.relay_args)):
            self.daily = False
            self.manual = True
            self.set_identity(game_session.DUALSENSE_IDENTITY
                              if self.create_dualsense else None)
            if self.keep_edge_during_switch:
                write_uevent(self.sysfs, "hidraw1", *game_session.EDGE_IDENTITY)
        elif argv == ["/installed/apex4-relay", "stop"]:
            self.manual = False
            self.set_identity(None)
        elif argv == ["systemctl", "--user", "start", game_session.DAILY_UNIT]:
            self.daily = True
            self.set_identity(game_session.EDGE_IDENTITY if self.restore_edge else None)
            if self.keep_dualsense_during_restore:
                write_uevent(self.sysfs, "hidraw1", *game_session.DUALSENSE_IDENTITY)
        return subprocess.CompletedProcess(argv, 0)


class RelayProfileSessionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.sysfs = pathlib.Path(self.directory.name)

    def session(self, fake):
        return game_session.RelayProfileSession(
            "/installed/apex4-relay", run=fake, sleep=lambda _seconds: None,
            sysfs_root=self.sysfs, timeout=0,
            lock_path=self.sysfs / "profile-session.lock")

    def test_preflight_accepts_exact_project_edge(self):
        write_uevent(self.sysfs, "hidraw0", "0003:0000054C:00000DF2",
                     "Apex 4 (DualSense Edge)")
        self.session(FakeCommands(self.sysfs)).preflight()

    def test_preflight_rejects_active_manual_relay(self):
        write_uevent(self.sysfs, "hidraw0", "0003:0000054C:00000DF2",
                     "Apex 4 (DualSense Edge)")
        with self.assertRaisesRegex(game_session.RelaySessionError,
                                    "manual relay is active"):
            self.session(FakeCommands(self.sysfs, manual=True)).preflight()

    def test_preflight_rejects_non_project_sony_device(self):
        write_uevent(self.sysfs, "hidraw0", "0003:0000054C:00000DF2",
                     "DualSense Edge Wireless Controller")
        with self.assertRaisesRegex(game_session.RelaySessionError,
                                    "project Edge identity"):
            self.session(FakeCommands(self.sysfs)).preflight()

    def test_preflight_rejects_duplicate_project_edge_identities(self):
        write_uevent(self.sysfs, "hidraw0", *game_session.EDGE_IDENTITY)
        write_uevent(self.sysfs, "hidraw1", *game_session.EDGE_IDENTITY)
        with self.assertRaisesRegex(game_session.RelaySessionError,
                                    "exactly one project Edge identity"):
            self.session(FakeCommands(self.sysfs)).preflight()

    def test_context_switches_to_dualsense_then_restores_edge(self):
        write_uevent(self.sysfs, "hidraw0", *game_session.EDGE_IDENTITY)
        fake = FakeCommands(self.sysfs)
        with self.session(fake):
            self.assertTrue(game_session.identity_present(
                self.sysfs, game_session.DUALSENSE_IDENTITY))
        self.assertTrue(game_session.identity_present(
            self.sysfs, game_session.EDGE_IDENTITY))
        mutations = [call for call in fake.calls
                     if "is-active" not in call and "show" not in call]
        self.assertEqual(mutations, [
            ["/installed/apex4-relay", "start", "--", "--emulate", "dualsense"],
            ["/installed/apex4-relay", "stop"],
            ["systemctl", "--user", "start", game_session.DAILY_UNIT],
        ])

    def test_missing_temporary_identity_restores_edge_before_raising(self):
        write_uevent(self.sysfs, "hidraw0", *game_session.EDGE_IDENTITY)
        fake = FakeCommands(self.sysfs, create_dualsense=False)
        with self.assertRaisesRegex(game_session.RelaySessionError,
                                    "temporary DualSense identity"):
            with self.session(fake):
                self.fail("game body must not run")
        self.assertTrue(game_session.identity_present(
            self.sysfs, game_session.EDGE_IDENTITY))
        self.assertIn(["systemctl", "--user", "start", game_session.DAILY_UNIT],
                      fake.calls)

    def test_temporary_profile_rejects_leftover_edge_identity(self):
        write_uevent(self.sysfs, "hidraw0", *game_session.EDGE_IDENTITY)
        fake = FakeCommands(self.sysfs, keep_edge_during_switch=True)
        with self.assertRaisesRegex(game_session.RelaySessionError,
                                    "exclusive temporary DualSense identity"):
            with self.session(fake):
                self.fail("game body must not run with both identities")

    def test_restore_requires_edge_identity_to_return(self):
        write_uevent(self.sysfs, "hidraw0", *game_session.EDGE_IDENTITY)
        fake = FakeCommands(self.sysfs, restore_edge=False)
        with self.assertRaisesRegex(game_session.RelaySessionError,
                                    "Edge identity did not return"):
            with self.session(fake):
                pass

    def test_restore_rejects_leftover_dualsense_identity(self):
        write_uevent(self.sysfs, "hidraw0", *game_session.EDGE_IDENTITY)
        fake = FakeCommands(self.sysfs, keep_dualsense_during_restore=True)
        with self.assertRaisesRegex(game_session.RelaySessionError,
                                    "exclusive Edge identity"):
            with self.session(fake):
                pass

    def test_system_command_timeout_is_reported_as_session_error(self):
        def timed_out(argv, **kwargs):
            self.assertIn("timeout", kwargs)
            raise subprocess.TimeoutExpired(argv, kwargs["timeout"])

        session = game_session.RelayProfileSession(
            "/installed/apex4-relay", run=timed_out,
            sleep=lambda _seconds: None, sysfs_root=self.sysfs, timeout=0)
        try:
            session.preflight()
        except Exception as exc:
            self.assertIsInstance(exc, game_session.RelaySessionError)
            self.assertIn("timed out", str(exc))
        else:
            self.fail("a timed-out system command must fail the session")

    def test_second_profile_session_is_refused_without_service_mutation(self):
        write_uevent(self.sysfs, "hidraw0", *game_session.EDGE_IDENTITY)
        first_commands = FakeCommands(self.sysfs)
        first = self.session(first_commands)
        first.__enter__()
        second_commands = FakeCommands(self.sysfs, daily=False, manual=True)
        second = self.session(second_commands)
        try:
            with self.assertRaisesRegex(game_session.RelaySessionError,
                                        "profile session is already active"):
                second.__enter__()
            self.assertEqual(second_commands.calls, [])
        finally:
            first.__exit__(None, None, None)

    def test_restore_refuses_to_stop_replaced_manual_service(self):
        write_uevent(self.sysfs, "hidraw0", *game_session.EDGE_IDENTITY)
        fake = FakeCommands(self.sysfs)
        session = self.session(fake)
        session.__enter__()
        mutation_count = len(fake.calls)
        fake.manual_invocation = "manual-invocation-replaced"
        with self.assertRaisesRegex(game_session.RelaySessionError,
                                    "ownership changed"):
            session.__exit__(None, None, None)
        later = fake.calls[mutation_count:]
        self.assertNotIn(["/installed/apex4-relay", "stop"], later)
        self.assertNotIn(
            ["systemctl", "--user", "start", game_session.DAILY_UNIT], later)

    def test_restore_refuses_when_daily_service_was_started_mid_session(self):
        write_uevent(self.sysfs, "hidraw0", *game_session.EDGE_IDENTITY)
        fake = FakeCommands(self.sysfs)
        session = self.session(fake)
        session.__enter__()
        mutation_count = len(fake.calls)
        fake.daily = True
        with self.assertRaisesRegex(game_session.RelaySessionError,
                                    "daily Edge service became active"):
            session.__exit__(None, None, None)
        later = fake.calls[mutation_count:]
        self.assertNotIn(["/installed/apex4-relay", "stop"], later)

    def test_bounded_dry_run_uses_the_fixed_safe_relay_arguments(self):
        write_uevent(self.sysfs, "hidraw0", *game_session.EDGE_IDENTITY)
        relay_args = game_session.BOUNDED_DRY_RUN_ARGS
        fake = FakeCommands(self.sysfs, relay_args=relay_args)
        session = game_session.RelayProfileSession(
            "/installed/apex4-relay", run=fake,
            sleep=lambda _seconds: None, sysfs_root=self.sysfs, timeout=0,
            lock_path=self.sysfs / "profile-session.lock",
            relay_args=relay_args)
        with session:
            pass
        self.assertIn(
            ["/installed/apex4-relay", "start", "--", "--emulate",
             "dualsense"] + list(relay_args), fake.calls)

    def test_bounded_write_uses_the_fixed_safe_relay_arguments(self):
        write_uevent(self.sysfs, "hidraw0", *game_session.EDGE_IDENTITY)
        relay_args = game_session.BOUNDED_WRITE_ARGS
        fake = FakeCommands(self.sysfs, relay_args=relay_args)
        session = game_session.RelayProfileSession(
            "/installed/apex4-relay", run=fake,
            sleep=lambda _seconds: None, sysfs_root=self.sysfs, timeout=0,
            lock_path=self.sysfs / "profile-session.lock",
            relay_args=relay_args)
        with session:
            pass
        self.assertIn(
            ["/installed/apex4-relay", "start", "--", "--emulate",
             "dualsense"] + list(relay_args), fake.calls)

    def test_translation_dry_run_uses_the_fixed_safe_relay_arguments(self):
        write_uevent(self.sysfs, "hidraw0", *game_session.EDGE_IDENTITY)
        relay_args = game_session.TRANSLATION_DRY_RUN_ARGS
        fake = FakeCommands(self.sysfs, relay_args=relay_args)
        session = game_session.RelayProfileSession(
            "/installed/apex4-relay", run=fake,
            sleep=lambda _seconds: None, sysfs_root=self.sysfs, timeout=0,
            lock_path=self.sysfs / "profile-session.lock",
            relay_args=relay_args)
        with session:
            pass
        self.assertIn(
            ["/installed/apex4-relay", "start", "--", "--emulate",
             "dualsense"] + list(relay_args), fake.calls)

    def test_native_dry_run_uses_the_fixed_safe_relay_arguments(self):
        write_uevent(self.sysfs, "hidraw0", *game_session.EDGE_IDENTITY)
        relay_args = game_session.NATIVE_DRY_RUN_ARGS
        fake = FakeCommands(self.sysfs, relay_args=relay_args)
        session = game_session.RelayProfileSession(
            "/installed/apex4-relay", run=fake,
            sleep=lambda _seconds: None, sysfs_root=self.sysfs, timeout=0,
            lock_path=self.sysfs / "profile-session.lock",
            relay_args=relay_args)
        with session:
            pass
        self.assertIn(
            ["/installed/apex4-relay", "start", "--", "--emulate",
             "dualsense"] + list(relay_args), fake.calls)

    def test_native_write_uses_the_fixed_safe_relay_arguments(self):
        write_uevent(self.sysfs, "hidraw0", *game_session.EDGE_IDENTITY)
        relay_args = game_session.NATIVE_WRITE_ARGS
        fake = FakeCommands(self.sysfs, relay_args=relay_args)
        session = game_session.RelayProfileSession(
            "/installed/apex4-relay", run=fake,
            sleep=lambda _seconds: None, sysfs_root=self.sysfs, timeout=0,
            lock_path=self.sysfs / "profile-session.lock",
            relay_args=relay_args)
        with session:
            pass
        self.assertIn(
            ["/installed/apex4-relay", "start", "--", "--emulate",
             "dualsense"] + list(relay_args), fake.calls)

    def test_native_session_dry_run_uses_fixed_relay_arguments(self):
        write_uevent(self.sysfs, "hidraw0", *game_session.EDGE_IDENTITY)
        relay_args = game_session.NATIVE_SESSION_DRY_RUN_ARGS
        fake = FakeCommands(self.sysfs, relay_args=relay_args)
        session = game_session.RelayProfileSession(
            "/installed/apex4-relay", run=fake,
            sleep=lambda _seconds: None, sysfs_root=self.sysfs, timeout=0,
            lock_path=self.sysfs / "profile-session.lock",
            relay_args=relay_args)
        with session:
            pass
        self.assertIn(
            ["/installed/apex4-relay", "start", "--", "--emulate",
             "dualsense"] + list(relay_args), fake.calls)

    def test_native_session_write_uses_fixed_relay_arguments(self):
        write_uevent(self.sysfs, "hidraw0", *game_session.EDGE_IDENTITY)
        relay_args = game_session.NATIVE_SESSION_WRITE_ARGS
        fake = FakeCommands(self.sysfs, relay_args=relay_args)
        session = game_session.RelayProfileSession(
            "/installed/apex4-relay", run=fake,
            sleep=lambda _seconds: None, sysfs_root=self.sysfs, timeout=0,
            lock_path=self.sysfs / "profile-session.lock",
            relay_args=relay_args)
        with session:
            pass
        self.assertIn(
            ["/installed/apex4-relay", "start", "--", "--emulate",
             "dualsense"] + list(relay_args), fake.calls)

    def test_ow2_safe_dry_run_uses_fixed_relay_arguments(self):
        write_uevent(self.sysfs, "hidraw0", *game_session.EDGE_IDENTITY)
        relay_args = game_session.OW2_SAFE_DRY_RUN_ARGS
        fake = FakeCommands(self.sysfs, relay_args=relay_args)
        session = game_session.RelayProfileSession(
            "/installed/apex4-relay", run=fake,
            sleep=lambda _seconds: None, sysfs_root=self.sysfs, timeout=0,
            lock_path=self.sysfs / "profile-session.lock",
            relay_args=relay_args)
        with session:
            pass
        self.assertIn(
            ["/installed/apex4-relay", "start", "--", "--emulate",
             "dualsense"] + list(relay_args), fake.calls)

    def test_ow2_safe_write_uses_fixed_relay_arguments(self):
        self.assertEqual(
            game_session.OW2_SAFE_WRITE_ARGS,
            ("--trigger-ow2-safe-right", "--quiet-output"))
        self.assertIn("--trigger-debug", game_session.OW2_SAFE_DRY_RUN_ARGS)
        self.assertIn("--hid-debug", game_session.OW2_SAFE_DRY_RUN_ARGS)
        write_uevent(self.sysfs, "hidraw0", *game_session.EDGE_IDENTITY)
        relay_args = game_session.OW2_SAFE_WRITE_ARGS
        fake = FakeCommands(self.sysfs, relay_args=relay_args)
        session = game_session.RelayProfileSession(
            "/installed/apex4-relay", run=fake,
            sleep=lambda _seconds: None, sysfs_root=self.sysfs, timeout=0,
            lock_path=self.sysfs / "profile-session.lock",
            relay_args=relay_args)
        with session:
            pass
        self.assertIn(
            ["/installed/apex4-relay", "start", "--", "--emulate",
             "dualsense"] + list(relay_args), fake.calls)


if __name__ == "__main__":
    unittest.main()
