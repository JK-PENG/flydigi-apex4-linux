#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Preview or apply game-scoped APEX 4 filters; no Linux permission changes.

Steam launch option: /absolute/path/tools/proton-game.py --run -- %command%
The relay normally runs separately. ``--relay-profile dualsense`` temporarily
switches an installed Edge service for a verified game session, changing only
the virtual identity unless an explicit diagnostic trigger mode is requested.
The installed trigger profile is otherwise inherited. Requires a Proton build
supporting PROTON_DISABLE_HIDRAW and propagation to its device service (see
VALIDATION.md).
"""
import argparse
import os
import re
import signal
import subprocess
import sys
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from apex4ds5.game_session import (  # noqa: E402
    BOUNDED_DRY_RUN_ARGS, BOUNDED_WRITE_ARGS,
    NATIVE_DRY_RUN_ARGS, NATIVE_SESSION_DRY_RUN_ARGS,
    NATIVE_SESSION_WRITE_ARGS, NATIVE_WRITE_ARGS, TRANSLATION_DRY_RUN_ARGS,
    OW2_SAFE_DRY_RUN_ARGS, OW2_SAFE_WRITE_ARGS,
    RelayProfileSession, RelaySessionError)

PHYSICAL = "0x04b4/0x2412"
SONY = {"0x054c/0x0ce6", "0x054c/0x0df2"}
FILTER_KEYS = ("SDL_GAMECONTROLLER_IGNORE_DEVICES", "SDL_JOYSTICK_IGNORE_DEVICES",
               "PROTON_DISABLE_HIDRAW")


class ForwardedSignals:
    """Keep cancellation observable across switch, child, and restore phases."""

    def __init__(self):
        self.pending = None
        self.child = None
        self.previous = {}

    def __enter__(self):
        for number in (signal.SIGINT, signal.SIGTERM):
            self.previous[number] = signal.getsignal(number)
            signal.signal(number, self._handle)
        return self

    def __exit__(self, *_exc):
        for number, handler in self.previous.items():
            signal.signal(number, handler)
        self.previous = {}

    def _handle(self, number, _frame):
        if self.pending is None:
            self.pending = number
        if self.child is not None:
            try:
                self.child.send_signal(number)
            except ProcessLookupError:
                pass

    def attach_child(self, child):
        self.child = child
        if self.pending is not None:
            try:
                child.send_signal(self.pending)
            except ProcessLookupError:
                pass

    def detach_child(self):
        self.child = None

    def status(self, child_status=0):
        if self.pending is not None:
            return 128 + self.pending
        return child_status if child_status >= 0 else 128 - child_status


def device_list(value):
    items = [item.strip().lower() for item in value.split(",") if item.strip()]
    if any(not re.fullmatch(r"0x[0-9a-f]{4}/0x[0-9a-f]{4}", item) for item in items):
        raise ValueError("expected a comma-separated VID/PID list, not a global switch or file")
    return list(dict.fromkeys(items))


def game_environment(environ):
    result = dict(environ)
    for key in ("SDL_GAMECONTROLLER_IGNORE_DEVICES_EXCEPT",
                "SDL_JOYSTICK_IGNORE_DEVICES_EXCEPT"):
        if key in result:
            items = device_list(result[key])
            if not SONY.issubset(items):
                raise ValueError("%s excludes a virtual DualSense identity; review it first" % key)
            # SDL gives an existing allowlist priority over its ignore list.
            result[key] = ",".join(item for item in items if item != PHYSICAL)
    for key in FILTER_KEYS:
        items = device_list(result.get(key, ""))
        if SONY.intersection(items):
            raise ValueError("%s hides a virtual DualSense identity; review it first" % key)
        if PHYSICAL not in items:
            items.append(PHYSICAL)
        result[key] = ",".join(items)
    return result


def probe_command(command, probe, probe_args):
    """Replace only a recognized Proton target, keeping Steam's runtime chain."""
    matches = [i for i in range(1, len(command) - 1)
               if command[i] in ("run", "waitforexitandrun")
               and os.path.basename(command[i - 1]) == "proton"]
    if len(matches) != 1:
        raise ValueError("cannot identify one Proton run target; inspect the launch chain first")
    return command[:matches[0] + 1] + [probe] + list(probe_args)


def _terminate_and_reap(child, grace=1.0):
    try:
        child.terminate()
    except ProcessLookupError:
        return
    try:
        child.wait(timeout=max(0.1, grace))
    except subprocess.TimeoutExpired:
        try:
            child.kill()
        except ProcessLookupError:
            return
        try:
            child.wait(timeout=max(0.1, grace))
        except (OSError, subprocess.SubprocessError):
            pass
    except (OSError, subprocess.SubprocessError):
        pass


def _run_child(command, environ, popen, forwarded, shutdown_timeout,
               poll_interval, clock):
    child = popen(command, env=environ)
    forwarded.attach_child(child)
    shutdown_deadline = None
    try:
        while True:
            try:
                return child.wait(timeout=poll_interval)
            except subprocess.TimeoutExpired:
                if forwarded.pending is None:
                    continue
                if shutdown_deadline is None:
                    shutdown_deadline = clock() + shutdown_timeout
                if clock() < shutdown_deadline:
                    continue
                try:
                    child.terminate()
                except ProcessLookupError:
                    return -forwarded.pending
                try:
                    return child.wait(timeout=max(1.0, poll_interval))
                except subprocess.TimeoutExpired:
                    try:
                        child.kill()
                    except ProcessLookupError:
                        return -forwarded.pending
                    return child.wait(timeout=max(1.0, poll_interval))
            except BaseException:
                _terminate_and_reap(child)
                raise
    finally:
        forwarded.detach_child()


def run_child(command, environ, popen=subprocess.Popen, forwarded=None,
              shutdown_timeout=5.0, poll_interval=0.1,
              clock=time.monotonic):
    """Run an exact argv while forwarding terminal signals for safe cleanup."""
    if forwarded is not None:
        status = _run_child(command, environ, popen, forwarded,
                            max(0.0, float(shutdown_timeout)),
                            max(0.001, float(poll_interval)), clock)
        return forwarded.status(status)
    with ForwardedSignals() as owned:
        status = _run_child(command, environ, popen, owned,
                            max(0.0, float(shutdown_timeout)),
                            max(0.001, float(poll_interval)), clock)
        return owned.status(status)


def run_profiled_command(command, environ, relay_script,
                         session_factory=RelayProfileSession,
                         popen=subprocess.Popen, relay_args=()):
    with ForwardedSignals() as forwarded:
        session = (session_factory(relay_script, relay_args=relay_args)
                   if relay_args else session_factory(relay_script))
        with session:
            if forwarded.pending is not None:
                return forwarded.status()
            status = run_child(command, environ, popen=popen,
                               forwarded=forwarded)
        return forwarded.status(status)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="execute the supplied command")
    parser.add_argument("--debug", action="store_true", help="request short-session Proton HID logs")
    parser.add_argument("--probe", help="replace the game's executable with this Windows probe in the same runtime")
    parser.add_argument("--probe-arg", action="append", default=[],
                        help="one probe argument; use --probe-arg=--device for flags")
    parser.add_argument("--relay-profile", choices=("unchanged", "dualsense"),
                        default="unchanged",
                        help="temporarily switch an installed Edge relay for this game")
    parser.add_argument("--relay-trigger-mode",
                        choices=("unchanged", "bounded-dry-run", "bounded-write",
                                 "translation-dry-run", "native-dry-run",
                                 "native-write", "native-session-dry-run",
                                 "native-session-write", "ow2-safe-dry-run",
                                 "ow2-safe-write"),
                        default="unchanged",
                        help="safe trigger diagnostics for a profiled game session")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.relay_profile == "dualsense" and args.probe:
        parser.error("--relay-profile dualsense cannot be combined with --probe")
    if (args.relay_trigger_mode != "unchanged"
            and args.relay_profile != "dualsense"):
        parser.error("--relay-trigger-mode requires --relay-profile dualsense")
    try:
        environ = game_environment(os.environ)
    except ValueError as exc:
        parser.error(str(exc))
    if args.debug:
        # Set explicitly: PROTON_LOG=+hid,+plugplay adds these to Proton's
        # default logging channels. Do not dump the caller's entire environment.
        environ["PROTON_LOG"] = "+hid,+plugplay"
    for key in FILTER_KEYS + (("PROTON_LOG",) if args.debug else ()):
        print("%s=%s" % (key, environ[key]), flush=True)
    for key in ("SDL_GAMECONTROLLER_IGNORE_DEVICES_EXCEPT",
                "SDL_JOYSTICK_IGNORE_DEVICES_EXCEPT"):
        if key in environ:
            print("%s=%s" % (key, environ[key]), flush=True)
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if args.probe:
        try:
            command = probe_command(command, os.path.abspath(args.probe), args.probe_arg)
        except ValueError as exc:
            parser.error(str(exc))
        print("Probe selected: replacing the game target, preserving its Proton/runtime chain.", flush=True)
        if args.run and not os.path.isfile(args.probe):
            parser.error("probe executable does not exist")
    elif args.probe_arg:
        parser.error("--probe-arg requires --probe")
    if args.relay_profile == "dualsense":
        print("Relay plan: Edge -> DualSense -> Edge (identity-only; installed "
              "trigger profile inherited).", flush=True)
    if args.relay_trigger_mode == "bounded-dry-run":
        print("Trigger plan: bounded R2 dry-run; no ForceAdapt write.", flush=True)
    elif args.relay_trigger_mode == "bounded-write":
        print("Trigger plan: physical R2 resistance, start>=60, strength<=40, "
              "<=1s, <=3 cycles in 30s.", flush=True)
    elif args.relay_trigger_mode == "translation-dry-run":
        print("Trigger plan: compat vs semantic translation dry-run; "
              "no ForceAdapt write.", flush=True)
    elif args.relay_trigger_mode == "native-dry-run":
        print("Trigger plan: single-cycle R2 native candidate dry-run; "
              "no ForceAdapt write.", flush=True)
    elif args.relay_trigger_mode == "native-write":
        print("Trigger plan: single-cycle physical R2 native candidate; "
              "mode 2 strength<=32, mode 1 strength<=40, "
              "<=1s total, <=1 cycle.", flush=True)
    elif args.relay_trigger_mode == "native-session-dry-run":
        print("Trigger plan: three-cycle R2 native session dry-run; "
              "no ForceAdapt write.", flush=True)
    elif args.relay_trigger_mode == "native-session-write":
        print("Trigger plan: physical three-cycle R2 native session; "
              "mode 2 strength<=32, mode 1 strength<=40, "
              "<=4s each, <=3 cycles in 30s.", flush=True)
    elif args.relay_trigger_mode == "ow2-safe-dry-run":
        print("Trigger plan: OW2-safe continuous R2 dry-run; captured OW2 "
              "patterns only; no ForceAdapt write.", flush=True)
    elif args.relay_trigger_mode == "ow2-safe-write":
        print("Trigger plan: OW2-safe continuous physical R2; captured OW2 "
              "patterns only, mode 2 strength<=32, mode 1 strength<=40, "
              "<=4s per cycle, Off required to rearm.", flush=True)
    if not args.run:
        print("Preview only. No command started and no device permissions changed.")
        return 0
    if not command:
        parser.error("--run requires a command after --")
    if args.relay_profile == "unchanged":
        os.execvpe(command[0], command, environ)
    relay_script = os.path.join(PROJECT_ROOT, "apex4-relay")
    if args.relay_trigger_mode == "bounded-dry-run":
        relay_args = BOUNDED_DRY_RUN_ARGS
    elif args.relay_trigger_mode == "bounded-write":
        relay_args = BOUNDED_WRITE_ARGS
    elif args.relay_trigger_mode == "translation-dry-run":
        relay_args = TRANSLATION_DRY_RUN_ARGS
    elif args.relay_trigger_mode == "native-dry-run":
        relay_args = NATIVE_DRY_RUN_ARGS
    elif args.relay_trigger_mode == "native-write":
        relay_args = NATIVE_WRITE_ARGS
    elif args.relay_trigger_mode == "native-session-dry-run":
        relay_args = NATIVE_SESSION_DRY_RUN_ARGS
    elif args.relay_trigger_mode == "native-session-write":
        relay_args = NATIVE_SESSION_WRITE_ARGS
    elif args.relay_trigger_mode == "ow2-safe-dry-run":
        relay_args = OW2_SAFE_DRY_RUN_ARGS
    elif args.relay_trigger_mode == "ow2-safe-write":
        relay_args = OW2_SAFE_WRITE_ARGS
    else:
        relay_args = ()
    try:
        return run_profiled_command(command, environ, relay_script,
                                    relay_args=relay_args)
    except RelaySessionError as exc:
        print("Relay profile session failed: %s" % exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
