# SPDX-License-Identifier: MIT
import os
import io
import contextlib
import importlib.machinery
import importlib.util
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from apex4ds5 import legacy, relay_lock


ROOT = pathlib.Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "forceadapt-test.py"
LOADER = importlib.machinery.SourceFileLoader("forceadapt_tool", str(TOOL))
SPEC = importlib.util.spec_from_loader("forceadapt_tool", LOADER)
MODULE = importlib.util.module_from_spec(SPEC)
LOADER.exec_module(MODULE)


class ForceAdaptToolTests(unittest.TestCase):
    def test_same_fd_echo_counter_ignores_unrelated_frames(self):
        self.assertTrue(hasattr(MODULE, "count_forceadapt_echoes"),
                        "bounded same-fd echo observer is missing")
        now = [10.0]
        unrelated = bytearray(legacy.REPORT_LEN)
        unrelated[0] = legacy.INPUT_REPORT_ID
        unrelated[legacy.CMD_ECHO_OFFSET] = legacy.CMD_GET_DEVICE_INFO
        observed = bytearray(unrelated)
        observed[legacy.CMD_ECHO_OFFSET] = legacy.CMD_FORCEADAPT
        frames = [bytes(unrelated), bytes(observed)]

        def waiter(readers, _writers, _errors, seconds):
            if frames:
                return readers, [], []
            now[0] += seconds
            return [], [], []

        self.assertEqual(MODULE.count_forceadapt_echoes(
            7, 10.05, clock=lambda: now[0], waiter=waiter,
            reader=lambda _fd, _size: frames.pop(0)), 1)

    def test_same_fd_echo_counter_propagates_read_failure(self):
        self.assertTrue(hasattr(MODULE, "count_forceadapt_echoes"),
                        "bounded same-fd echo observer is missing")
        with self.assertRaisesRegex(OSError, "read failed"):
            MODULE.count_forceadapt_echoes(
                7, 10.05, clock=lambda: 10.0,
                waiter=lambda readers, *_args: (readers, [], []),
                reader=lambda _fd, _size: (_ for _ in ()).throw(
                    OSError("read failed")))

    def test_same_fd_echo_counter_is_bounded_without_reply(self):
        now = [10.0]
        waits = []

        def waiter(_readers, _writers, _errors, seconds):
            waits.append(seconds)
            now[0] += seconds
            return [], [], []

        self.assertEqual(MODULE.count_forceadapt_echoes(
            7, 10.05, clock=lambda: now[0], waiter=waiter,
            reader=lambda _fd, _size: self.fail("no fd was ready")), 0)
        self.assertLessEqual(max(waits), 0.02)
        self.assertAlmostEqual(now[0], 10.05)

    def test_same_fd_echo_counter_retries_nonblocking_read(self):
        frame = bytearray(legacy.REPORT_LEN)
        frame[0] = legacy.INPUT_REPORT_ID
        frame[legacy.CMD_ECHO_OFFSET] = legacy.CMD_FORCEADAPT
        now = [10.0]
        reads = [0]

        def waiter(readers, _writers, _errors, _seconds):
            if reads[0] < 2:
                now[0] += 0.01
                return readers, [], []
            now[0] = 10.05
            return [], [], []

        def reader(_fd, _size):
            reads[0] += 1
            if reads[0] == 1:
                raise BlockingIOError()
            return bytes(frame)

        self.assertEqual(MODULE.count_forceadapt_echoes(
            7, 10.05, clock=lambda: now[0],
            waiter=waiter, reader=reader), 1)

    def test_fixed_candidates_have_exact_effects_and_bounded_durations(self):
        from apex4ds5 import forceadapt
        expected = {
            "l2-rattle-32": (forceadapt.rattle("left", 0, 1, 32, 21), 1.0),
            "l2-resistance-40": (forceadapt.resistance("left", 0, 40), 1.0),
            "l2-resistance-hold15":
                (forceadapt.resistance("left", 0, 40), 15.0),
            "r2-resistance-hold15":
                (forceadapt.resistance("right", 0, 40), 15.0),
            "l2-breakpoint-20":
                (forceadapt.breakpoint("left", 60, 20, 20), 1.0),
            "r2-breakpoint-20":
                (forceadapt.breakpoint("right", 60, 20, 20), 1.0),
        }
        self.assertEqual(MODULE.FIXED_PHYSICAL_CANDIDATES, expected)

    def test_candidate_preview_never_requires_hardware_or_writes(self):
        result = subprocess.run(
            [sys.executable, str(TOOL), "--candidate", "l2-rattle-32"],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("mode=2 params=(0, 1, 32, 21, 0)", result.stdout)
        self.assertIn("DRY-RUN auto-reset", result.stdout)
        self.assertIn("No ForceAdapt command was written", result.stdout)

    def test_candidate_preview_does_not_probe_a_live_vendor_node(self):
        with mock.patch.object(sys, "argv", [str(TOOL), "--candidate",
                                             "l2-rattle-32"]), \
                mock.patch.object(MODULE.legacy, "find_vendor_node",
                                  return_value=None) as find_node, \
                contextlib.redirect_stdout(io.StringIO()):
            status = MODULE.main()
        self.assertEqual(status, 0)
        find_node.assert_not_called()

    def test_fixed_candidate_rejects_arbitrary_duration_or_side(self):
        for extra in (("--duration", "20"), ("--side", "right"),
                      ("--effect", "strong")):
            with self.subTest(extra=extra):
                result = subprocess.run(
                    [sys.executable, str(TOOL), "--candidate",
                     "l2-rattle-32", *extra], capture_output=True, text=True)
                self.assertEqual(result.returncode, 2)

    def test_echo_observation_rejects_unapproved_cli_combinations(self):
        cases = (
            ("--observe-forceadapt-echo", "--candidate", "l2-rattle-32"),
            ("--observe-forceadapt-echo", "--write", "--effect", "medium",
             "--side", "left"),
            ("--observe-forceadapt-echo", "--write", "--effect", "strong",
             "--side", "right"),
            ("--observe-forceadapt-echo", "--write", "--effect", "mild",
             "--side", "both"),
            ("--observe-forceadapt-echo", "--write", "--effect", "mild"),
        )
        for argv in cases:
            with self.subTest(argv=argv):
                result = subprocess.run(
                    [sys.executable, str(TOOL), *argv],
                    capture_output=True, text=True)
                self.assertEqual(result.returncode, 2)
                self.assertIn("echo observation requires", result.stderr)

    def test_failed_final_normal_is_not_reported_as_success(self):
        from apex4ds5 import forceadapt

        class TestTransport:
            identity = {"device_type": 84, "firmware": (0, 1),
                        "connection": "wired"}

            def __init__(self):
                self.effects = []

            def write_effect(self, mapped):
                self.effects.append(mapped)
                if len(self.effects) == 4:
                    raise OSError("injected final Normal failure")
                return forceadapt.build_packet(mapped)

        class TestGuard:
            def close(self):
                pass

        transport = TestTransport()
        with mock.patch.object(sys, "argv", [str(TOOL), "--write",
                                             "--candidate", "l2-rattle-32"]), \
                mock.patch.object(MODULE.relay_lock, "RelayLock",
                                  return_value=TestGuard()), \
                mock.patch.object(MODULE.legacy, "find_vendor_node",
                                  return_value="/dev/hidraw-test"), \
                mock.patch.object(MODULE.os, "open", return_value=7), \
                mock.patch.object(MODULE.os, "close"), \
                mock.patch.object(MODULE.time, "sleep"), \
                mock.patch.object(MODULE.signal, "signal"), \
                mock.patch.object(forceadapt.VerifiedTransport, "verify",
                                  return_value=transport), \
                contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            status = MODULE.main()
        self.assertNotEqual(status, 0)
        self.assertEqual(transport.effects[-2:],
                         [forceadapt.normal("left"),
                          forceadapt.normal("right")])

    def test_write_reports_monotonic_effect_and_reset_boundaries(self):
        from apex4ds5 import forceadapt

        class TestTransport:
            identity = {"device_type": 84, "firmware": (0, 1),
                        "connection": "dongle"}

            def __init__(self):
                self.effects = []

            def write_effect(self, mapped):
                self.effects.append(mapped)
                return forceadapt.build_packet(mapped)

        class TestGuard:
            def close(self):
                pass

        transport = TestTransport()
        output = io.StringIO()
        with mock.patch.object(sys, "argv", [str(TOOL), "--write",
                                             "--candidate", "l2-rattle-32"]), \
                mock.patch.object(MODULE.relay_lock, "RelayLock",
                                  return_value=TestGuard()), \
                mock.patch.object(MODULE.legacy, "find_vendor_node",
                                  return_value="/dev/hidraw-test"), \
                mock.patch.object(MODULE.os, "open", return_value=7), \
                mock.patch.object(MODULE.os, "close"), \
                mock.patch.object(MODULE.time, "sleep"), \
                mock.patch.object(MODULE.time, "monotonic",
                                  side_effect=(12.5, 13.5)), \
                mock.patch.object(MODULE.signal, "signal"), \
                mock.patch.object(forceadapt.VerifiedTransport, "verify",
                                  return_value=transport), \
                contextlib.redirect_stdout(output):
            status = MODULE.main()
        self.assertEqual(status, 0)
        self.assertIn("WRITE accepted t=12.500000", output.getvalue())
        self.assertIn("Normal reset complete t=13.500000", output.getvalue())
        self.assertEqual(transport.effects,
                         [forceadapt.normal("left"), forceadapt.normal("right"),
                          forceadapt.rattle("left", 0, 1, 32, 21),
                          forceadapt.normal("left"), forceadapt.normal("right")])

    def test_echo_observation_uses_existing_writes_and_shortens_sleep(self):
        from apex4ds5 import forceadapt

        class TestTransport:
            identity = {"device_type": 84, "firmware": (0, 1),
                        "connection": "dongle"}

            def __init__(self):
                self.effects = []

            def write_effect(self, mapped):
                self.effects.append(mapped)
                return forceadapt.build_packet(mapped)

        class TestGuard:
            def close(self):
                pass

        transport = TestTransport()
        output = io.StringIO()
        with mock.patch.object(sys, "argv", [str(TOOL), "--write",
                                             "--candidate", "l2-rattle-32",
                                             "--observe-forceadapt-echo"]), \
                mock.patch.object(MODULE.relay_lock, "RelayLock",
                                  return_value=TestGuard()), \
                mock.patch.object(MODULE.legacy, "find_vendor_node",
                                  return_value="/dev/hidraw-test"), \
                mock.patch.object(MODULE.os, "open", return_value=7), \
                mock.patch.object(MODULE.os, "close"), \
                mock.patch.object(MODULE.time, "sleep") as sleep, \
                mock.patch.object(MODULE.time, "monotonic",
                                  side_effect=(10.0, 10.1, 10.25, 11.12)), \
                mock.patch.object(MODULE, "count_forceadapt_echoes",
                                  side_effect=(0, 1)) as observe, \
                mock.patch.object(MODULE.signal, "signal"), \
                mock.patch.object(forceadapt.VerifiedTransport, "verify",
                                  return_value=transport), \
                contextlib.redirect_stdout(output):
            status = MODULE.main()
        self.assertEqual(status, 0)
        self.assertEqual(observe.call_count, 2)
        self.assertAlmostEqual(sleep.call_args.args[0], 0.85)
        self.assertIn("A0_ECHO_OBSERVED count=1", output.getvalue())
        self.assertEqual(transport.effects,
                         [forceadapt.normal("left"), forceadapt.normal("right"),
                          forceadapt.rattle("left", 0, 1, 32, 21),
                          forceadapt.normal("left"), forceadapt.normal("right")])

    def test_echo_predrain_failure_clears_without_non_normal_write(self):
        from apex4ds5 import forceadapt

        class TestTransport:
            identity = {"device_type": 84, "firmware": (0, 1),
                        "connection": "dongle"}

            def __init__(self):
                self.effects = []

            def write_effect(self, mapped):
                self.effects.append(mapped)
                return forceadapt.build_packet(mapped)

        class TestGuard:
            def close(self):
                pass

        transport = TestTransport()
        errors = io.StringIO()
        with mock.patch.object(sys, "argv", [str(TOOL), "--write",
                                             "--candidate", "l2-rattle-32",
                                             "--observe-forceadapt-echo"]), \
                mock.patch.object(MODULE.relay_lock, "RelayLock",
                                  return_value=TestGuard()), \
                mock.patch.object(MODULE.legacy, "find_vendor_node",
                                  return_value="/dev/hidraw-test"), \
                mock.patch.object(MODULE.os, "open", return_value=7), \
                mock.patch.object(MODULE.os, "close"), \
                mock.patch.object(MODULE.time, "monotonic",
                                  side_effect=(10.0, 10.1)), \
                mock.patch.object(MODULE, "count_forceadapt_echoes",
                                  side_effect=OSError("injected read failure")), \
                mock.patch.object(MODULE.signal, "signal"), \
                contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(errors), \
                mock.patch.object(forceadapt.VerifiedTransport, "verify",
                                  return_value=transport):
            with self.assertRaisesRegex(OSError, "injected read failure"):
                MODULE.main()
        self.assertEqual(transport.effects,
                         [forceadapt.normal("left"), forceadapt.normal("right"),
                          forceadapt.normal("left"), forceadapt.normal("right")])
        self.assertIn("A0_ECHO_UNKNOWN", errors.getvalue())

    def test_echo_read_failure_after_effect_is_unknown_and_still_resets(self):
        from apex4ds5 import forceadapt

        class TestTransport:
            identity = {"device_type": 84, "firmware": (0, 1),
                        "connection": "dongle"}

            def __init__(self):
                self.effects = []

            def write_effect(self, mapped):
                self.effects.append(mapped)
                return forceadapt.build_packet(mapped)

        class TestGuard:
            def close(self):
                pass

        transport = TestTransport()
        output = io.StringIO()
        with mock.patch.object(sys, "argv", [str(TOOL), "--write",
                                             "--effect", "mild", "--side", "left",
                                             "--duration", "2",
                                             "--observe-forceadapt-echo"]), \
                mock.patch.object(MODULE.relay_lock, "RelayLock",
                                  return_value=TestGuard()), \
                mock.patch.object(MODULE.legacy, "find_vendor_node",
                                  return_value="/dev/hidraw-test"), \
                mock.patch.object(MODULE.os, "open", return_value=7), \
                mock.patch.object(MODULE.os, "close"), \
                mock.patch.object(MODULE.time, "sleep") as sleep, \
                mock.patch.object(MODULE.time, "monotonic",
                                  side_effect=(10.0, 10.1, 10.3, 12.2)), \
                mock.patch.object(MODULE, "count_forceadapt_echoes",
                                  side_effect=(0, OSError("injected read failure"))), \
                mock.patch.object(MODULE.signal, "signal"), \
                mock.patch.object(forceadapt.VerifiedTransport, "verify",
                                  return_value=transport), \
                contextlib.redirect_stdout(output):
            status = MODULE.main()
        self.assertEqual(status, 0)
        self.assertIn("A0_ECHO_UNKNOWN (read failed)", output.getvalue())
        self.assertAlmostEqual(sleep.call_args.args[0], 1.8)
        self.assertEqual(transport.effects,
                         [forceadapt.normal("left"), forceadapt.normal("right"),
                          forceadapt.resistance("left", 60, 40),
                          forceadapt.normal("left"), forceadapt.normal("right")])

    def test_echo_observation_does_not_mask_final_normal_failure(self):
        from apex4ds5 import forceadapt

        class TestTransport:
            identity = {"device_type": 84, "firmware": (0, 1),
                        "connection": "dongle"}

            def __init__(self):
                self.effects = []

            def write_effect(self, mapped):
                self.effects.append(mapped)
                if len(self.effects) == 4:
                    raise OSError("injected Normal failure")
                return forceadapt.build_packet(mapped)

        class TestGuard:
            def close(self):
                pass

        transport = TestTransport()
        output = io.StringIO()
        with mock.patch.object(sys, "argv", [str(TOOL), "--write",
                                             "--candidate", "l2-rattle-32",
                                             "--observe-forceadapt-echo"]), \
                mock.patch.object(MODULE.relay_lock, "RelayLock",
                                  return_value=TestGuard()), \
                mock.patch.object(MODULE.legacy, "find_vendor_node",
                                  return_value="/dev/hidraw-test"), \
                mock.patch.object(MODULE.os, "open", return_value=7), \
                mock.patch.object(MODULE.os, "close"), \
                mock.patch.object(MODULE.time, "sleep"), \
                mock.patch.object(MODULE.time, "monotonic",
                                  side_effect=(10.0, 10.1, 10.2)), \
                mock.patch.object(MODULE, "count_forceadapt_echoes",
                                  side_effect=(0, 1)), \
                mock.patch.object(MODULE.signal, "signal"), \
                mock.patch.object(forceadapt.VerifiedTransport, "verify",
                                  return_value=transport), \
                contextlib.redirect_stdout(output), \
                contextlib.redirect_stderr(io.StringIO()):
            status = MODULE.main()
        self.assertEqual(status, 1)
        self.assertIn("A0_ECHO_OBSERVED", output.getvalue())
        self.assertNotIn("Triggers restored to Normal", output.getvalue())
        self.assertEqual(transport.effects[-2:],
                         [forceadapt.normal("left"),
                          forceadapt.normal("right")])

    def test_real_write_refuses_when_relay_lock_is_held(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ, XDG_RUNTIME_DIR=tmp)
            guard = relay_lock.RelayLock(
                pathlib.Path(tmp) / "flydigi-apex4-relay.lock")
            try:
                result = subprocess.run(
                    [sys.executable, str(TOOL), "--write"],
                    env=env, capture_output=True, text=True)
            finally:
                guard.close()
            self.assertEqual(result.returncode, 2)
            self.assertIn("another flydigi relay is already running",
                          result.stderr)


if __name__ == "__main__":
    unittest.main()
