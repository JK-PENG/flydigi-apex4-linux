# SPDX-License-Identifier: MIT
import importlib.util
import os
import pathlib
import signal
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/proton-game.py"


class ProtonGameTests(unittest.TestCase):
    def load_tool(self):
        self.assertTrue(TOOL.exists(), "game-scoped filter tool is missing")
        spec = importlib.util.spec_from_file_location("proton_game", TOOL)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_filter_preserves_other_devices_and_leaves_sony_available(self):
        tool = self.load_tool()
        original = {"SDL_GAMECONTROLLER_IGNORE_DEVICES": "0x1234/0x5678",
                    "PROTON_DISABLE_HIDRAW": "0x1111/0x2222", "PATH": "/bin"}
        result = tool.game_environment(original)
        self.assertEqual(result["SDL_GAMECONTROLLER_IGNORE_DEVICES"],
                         "0x1234/0x5678,0x04b4/0x2412")
        self.assertEqual(result["PROTON_DISABLE_HIDRAW"],
                         "0x1111/0x2222,0x04b4/0x2412")
        self.assertNotIn("0x054c", result["PROTON_DISABLE_HIDRAW"])
        self.assertNotIn("SDL_JOYSTICK_IGNORE_DEVICES", original)
        self.assertEqual(tool.game_environment(result), result)

    def test_conflicting_sony_filters_and_whitelists_are_rejected(self):
        tool = self.load_tool()
        for env in ({"PROTON_DISABLE_HIDRAW": "1"},
                    {"SDL_GAMECONTROLLER_IGNORE_DEVICES": "0x054C/0x0DF2"},
                    {"SDL_GAMECONTROLLER_IGNORE_DEVICES_EXCEPT": "0x04b4/0x2412"}):
            with self.subTest(env=env), self.assertRaises(ValueError):
                tool.game_environment(env)

    def test_whitelist_cannot_override_the_physical_exclusion(self):
        tool = self.load_tool()
        result = tool.game_environment({
            "SDL_GAMECONTROLLER_IGNORE_DEVICES_EXCEPT":
                "0x054c/0x0ce6,0x054c/0x0df2,0x04b4/0x2412,0x1234/0x5678"})
        self.assertEqual(result["SDL_GAMECONTROLLER_IGNORE_DEVICES_EXCEPT"],
                         "0x054c/0x0ce6,0x054c/0x0df2,0x1234/0x5678")

    def test_default_prints_only_filter_keys_and_does_not_execute(self):
        self.load_tool()
        env = dict(os.environ, APEX4_TEST_SECRET="do-not-print")
        for key in list(env):
            if key.startswith(("SDL_", "PROTON_")):
                env.pop(key)
        result = subprocess.run([sys.executable, str(TOOL), "--", "/no/such/game"],
                                env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("0x04b4/0x2412", result.stdout)
        self.assertNotIn("do-not-print", result.stdout)

    def test_run_passes_arguments_without_shell_interpretation(self):
        self.load_tool()
        env = {k: v for k, v in os.environ.items()
               if not k.startswith(("SDL_", "PROTON_"))}
        argument = "spaces ; $(literal) `literal`"
        result = subprocess.run([sys.executable, str(TOOL), "--run", "--",
                                 sys.executable, "-c",
                                 "import os,sys; print(sys.argv[1]); print(os.environ['PROTON_DISABLE_HIDRAW'])",
                                 argument], env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(argument, result.stdout)
        self.assertIn("0x04b4/0x2412", result.stdout)

    def test_probe_uses_the_original_proton_chain_and_drops_game_arguments(self):
        tool = self.load_tool()
        self.assertTrue(hasattr(tool, "probe_command"), "same-runtime probe replacement is missing")
        command = ["/runtime/reaper", "--", "/runtime/proton", "waitforexitandrun",
                   "/games/Overwatch.exe", "game-only-argument"]
        result = tool.probe_command(command, "/test/probe.exe", ["--device", "2"])
        self.assertEqual(result, command[:4] + ["/test/probe.exe", "--device", "2"])
        self.assertIn("game-only-argument", command)
        with self.assertRaises(ValueError):
            tool.probe_command(["/games/launcher", "game.exe"], "/test/probe.exe", [])

    def test_dualsense_profile_preview_plans_switch_without_starting_command(self):
        env = {k: v for k, v in os.environ.items()
               if not k.startswith(("SDL_", "PROTON_"))}
        result = subprocess.run(
            [sys.executable, str(TOOL), "--relay-profile", "dualsense", "--",
             "/no/such/game"], env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Edge -> DualSense -> Edge", result.stdout)
        self.assertIn("identity-only", result.stdout)
        self.assertNotIn("OW2 opt-in", result.stdout)
        self.assertIn("Preview only", result.stdout)

    def test_probe_cannot_implicitly_mutate_relay_profile(self):
        result = subprocess.run(
            [sys.executable, str(TOOL), "--relay-profile", "dualsense",
             "--probe", "/test/probe.exe", "--", "/runtime/proton", "run",
             "/games/game.exe"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("cannot be combined", result.stderr)

    def test_bounded_dry_run_requires_dualsense_profile_and_previews_safely(self):
        rejected = subprocess.run(
            [sys.executable, str(TOOL), "--relay-trigger-mode",
             "bounded-dry-run", "--", "/no/such/game"],
            capture_output=True, text=True)
        self.assertEqual(rejected.returncode, 2)
        self.assertIn("requires --relay-profile dualsense", rejected.stderr)
        preview = subprocess.run(
            [sys.executable, str(TOOL), "--relay-profile", "dualsense",
             "--relay-trigger-mode", "bounded-dry-run", "--",
             "/no/such/game"], capture_output=True, text=True)
        self.assertEqual(preview.returncode, 0, preview.stderr)
        self.assertIn("bounded R2 dry-run", preview.stdout)

    def test_bounded_write_preview_states_physical_scope(self):
        preview = subprocess.run(
            [sys.executable, str(TOOL), "--relay-profile", "dualsense",
             "--relay-trigger-mode", "bounded-write", "--",
             "/no/such/game"], capture_output=True, text=True)
        self.assertEqual(preview.returncode, 0, preview.stderr)
        self.assertIn("physical R2 resistance", preview.stdout)
        self.assertIn("3 cycles", preview.stdout)

    def test_translation_dry_run_preview_states_comparison_scope(self):
        preview = subprocess.run(
            [sys.executable, str(TOOL), "--relay-profile", "dualsense",
             "--relay-trigger-mode", "translation-dry-run", "--",
             "/no/such/game"], capture_output=True, text=True)
        self.assertEqual(preview.returncode, 0, preview.stderr)
        self.assertIn("compat vs semantic", preview.stdout)
        self.assertIn("no ForceAdapt write", preview.stdout)

    def test_native_candidate_previews_state_exact_physical_scope(self):
        dry_run = subprocess.run(
            [sys.executable, str(TOOL), "--relay-profile", "dualsense",
             "--relay-trigger-mode", "native-dry-run", "--",
             "/no/such/game"], capture_output=True, text=True)
        self.assertEqual(dry_run.returncode, 0, dry_run.stderr)
        self.assertIn("single-cycle R2 native candidate", dry_run.stdout)
        self.assertIn("no ForceAdapt write", dry_run.stdout)
        write = subprocess.run(
            [sys.executable, str(TOOL), "--relay-profile", "dualsense",
             "--relay-trigger-mode", "native-write", "--",
             "/no/such/game"], capture_output=True, text=True)
        self.assertEqual(write.returncode, 0, write.stderr)
        self.assertIn("mode 2 strength<=32", write.stdout)
        self.assertIn("mode 1 strength<=40", write.stdout)
        self.assertIn("<=1 cycle", write.stdout)

    def test_native_session_previews_state_full_bounded_scope(self):
        dry_run = subprocess.run(
            [sys.executable, str(TOOL), "--relay-profile", "dualsense",
             "--relay-trigger-mode", "native-session-dry-run", "--",
             "/no/such/game"], capture_output=True, text=True)
        self.assertEqual(dry_run.returncode, 0, dry_run.stderr)
        self.assertIn("three-cycle R2 native session", dry_run.stdout)
        self.assertIn("no ForceAdapt write", dry_run.stdout)
        write = subprocess.run(
            [sys.executable, str(TOOL), "--relay-profile", "dualsense",
             "--relay-trigger-mode", "native-session-write", "--",
             "/no/such/game"], capture_output=True, text=True)
        self.assertEqual(write.returncode, 0, write.stderr)
        self.assertIn("mode 2 strength<=32", write.stdout)
        self.assertIn("mode 1 strength<=40", write.stdout)
        self.assertIn("<=4s each", write.stdout)
        self.assertIn("<=3 cycles in 30s", write.stdout)

    def test_ow2_safe_profile_previews_continuous_bounded_scope(self):
        dry_run = subprocess.run(
            [sys.executable, str(TOOL), "--relay-profile", "dualsense",
             "--relay-trigger-mode", "ow2-safe-dry-run", "--",
             "/no/such/game"], capture_output=True, text=True)
        self.assertEqual(dry_run.returncode, 0, dry_run.stderr)
        self.assertIn("OW2-safe continuous R2", dry_run.stdout)
        self.assertIn("no ForceAdapt write", dry_run.stdout)
        write = subprocess.run(
            [sys.executable, str(TOOL), "--relay-profile", "dualsense",
             "--relay-trigger-mode", "ow2-safe-write", "--",
             "/no/such/game"], capture_output=True, text=True)
        self.assertEqual(write.returncode, 0, write.stderr)
        self.assertIn("captured OW2 patterns only", write.stdout)
        self.assertIn("mode 2 strength<=32", write.stdout)
        self.assertIn("mode 1 strength<=40", write.stdout)
        self.assertIn("<=4s per cycle", write.stdout)
        self.assertIn("Off required to rearm", write.stdout)

    def test_profiled_command_wraps_exact_child_in_relay_session(self):
        tool = self.load_tool()
        events = []
        seen = {}

        class FakeSession:
            def __init__(self, relay_script):
                seen["relay_script"] = relay_script

            def __enter__(self):
                events.append("session-enter")
                return self

            def __exit__(self, *_exc):
                events.append("session-exit")

        class FakeChild:
            def wait(self, timeout=None):
                events.append("child-wait")
                return 17

            def send_signal(self, number):
                events.append(("signal", number))

        def fake_popen(command, env):
            events.append("child-start")
            seen["command"] = command
            seen["environment"] = env
            return FakeChild()

        command = ["/runtime/proton", "run", "/games/game.exe", "literal ; arg"]
        environ = {"PATH": "/bin", "PROTON_DISABLE_HIDRAW": "0x04b4/0x2412"}
        status = tool.run_profiled_command(
            command, environ, "/installed/apex4-relay",
            session_factory=FakeSession, popen=fake_popen)
        self.assertEqual(status, 17)
        self.assertEqual(events,
                         ["session-enter", "child-start", "child-wait", "session-exit"])
        self.assertEqual(seen["command"], command)
        self.assertEqual(seen["environment"], environ)
        self.assertEqual(seen["relay_script"], "/installed/apex4-relay")

    def test_profiled_command_restores_session_when_child_wait_fails(self):
        tool = self.load_tool()
        events = []

        class FakeSession:
            def __init__(self, _relay_script):
                pass

            def __enter__(self):
                events.append("session-enter")

            def __exit__(self, *_exc):
                events.append("session-exit")

        class BrokenChild:
            terminated = False

            def wait(self, timeout=None):
                if self.terminated:
                    events.append("child-reaped")
                    return -signal.SIGTERM
                raise RuntimeError("child wait failed")

            def send_signal(self, _number):
                pass

            def terminate(self):
                events.append("child-terminate")
                self.terminated = True

        with self.assertRaisesRegex(RuntimeError, "child wait failed"):
            tool.run_profiled_command(
                ["/game"], {"PATH": "/bin"}, "/installed/apex4-relay",
                session_factory=FakeSession,
                popen=lambda command, env: BrokenChild())
        self.assertEqual(events,
                         ["session-enter", "child-terminate", "child-reaped",
                          "session-exit"])

    def test_run_child_forwards_termination_and_returns_shell_signal_status(self):
        tool = self.load_tool()
        installed = {}
        restored = []
        forwarded = []

        def fake_signal(number, handler):
            if callable(handler):
                installed[number] = handler
            else:
                restored.append((number, handler))

        class SignalledChild:
            def wait(self, timeout=None):
                installed[signal.SIGTERM](signal.SIGTERM, None)
                return -signal.SIGTERM

            def send_signal(self, number):
                forwarded.append(number)

        original_signal = tool.signal.signal
        original_getsignal = tool.signal.getsignal
        tool.signal.signal = fake_signal
        tool.signal.getsignal = lambda number: "original-%d" % number
        try:
            status = tool.run_child(
                ["/game"], {"PATH": "/bin"},
                popen=lambda command, env: SignalledChild())
        finally:
            tool.signal.signal = original_signal
            tool.signal.getsignal = original_getsignal
        self.assertEqual(status, 128 + signal.SIGTERM)
        self.assertEqual(forwarded, [signal.SIGTERM])
        self.assertEqual(restored, [
            (signal.SIGINT, "original-%d" % signal.SIGINT),
            (signal.SIGTERM, "original-%d" % signal.SIGTERM),
        ])

    def test_run_child_kills_process_that_ignores_forwarded_sigterm(self):
        tool = self.load_tool()
        events = []

        class StuckChild:
            killed = False
            signalled = False

            def wait(self, timeout=None):
                if self.killed:
                    return -signal.SIGKILL
                if not self.signalled:
                    self.signalled = True
                    os.kill(os.getpid(), signal.SIGTERM)
                raise subprocess.TimeoutExpired("/game", timeout)

            def send_signal(self, number):
                events.append(("signal", number))

            def terminate(self):
                events.append("terminate")

            def kill(self):
                events.append("kill")
                self.killed = True

        status = tool.run_child(
            ["/game"], {"PATH": "/bin"},
            popen=lambda command, env: StuckChild(),
            shutdown_timeout=0.0, poll_interval=0.001)
        self.assertEqual(status, 128 + signal.SIGTERM)
        self.assertEqual(events,
                         [("signal", signal.SIGTERM), "terminate", "kill"])

    def test_sigterm_during_session_enter_restores_without_launching_child(self):
        code = """
import importlib.util, os, signal
spec = importlib.util.spec_from_file_location('proton_game', %r)
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)
class Session:
    def __init__(self, _relay_script): pass
    def __enter__(self):
        print('session-enter', flush=True)
        os.kill(os.getpid(), signal.SIGTERM)
        print('session-enter-returned', flush=True)
        return self
    def __exit__(self, *_exc): print('session-restored', flush=True)
def forbidden_popen(*_args, **_kwargs):
    print('child-launched', flush=True)
    raise AssertionError('child must not launch after cancellation')
status = tool.run_profiled_command(
    ['/game'], {'PATH': '/bin'}, '/relay',
    session_factory=Session, popen=forbidden_popen)
print('status=%%d' %% status, flush=True)
""" % str(TOOL)
        result = subprocess.run([sys.executable, "-c", code],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("session-restored", result.stdout)
        self.assertIn("status=%d" % (128 + signal.SIGTERM), result.stdout)
        self.assertNotIn("child-launched", result.stdout)

    def test_sigterm_during_session_restore_finishes_restoration(self):
        code = """
import importlib.util, os, signal
spec = importlib.util.spec_from_file_location('proton_game', %r)
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)
class Session:
    def __init__(self, _relay_script): pass
    def __enter__(self): return self
    def __exit__(self, *_exc):
        print('restore-start', flush=True)
        os.kill(os.getpid(), signal.SIGTERM)
        print('restore-finished', flush=True)
class Child:
    def wait(self, timeout=None): return 0
    def send_signal(self, _number): pass
status = tool.run_profiled_command(
    ['/game'], {'PATH': '/bin'}, '/relay', session_factory=Session,
    popen=lambda *_args, **_kwargs: Child())
print('status=%%d' %% status, flush=True)
""" % str(TOOL)
        result = subprocess.run([sys.executable, "-c", code],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("restore-finished", result.stdout)
        self.assertIn("status=%d" % (128 + signal.SIGTERM), result.stdout)
