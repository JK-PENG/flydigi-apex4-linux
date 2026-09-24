# SPDX-License-Identifier: MIT
"""Fail-closed virtual-controller profile switching for one game session."""
import fcntl
import os
import pathlib
import subprocess
import tempfile
import time


DAILY_UNIT = "flydigi-apex4.service"
MANUAL_UNIT = "apex4-relay-manual.service"
EDGE_IDENTITY = ("0003:0000054C:00000DF2", "Apex 4 (DualSense Edge)")
DUALSENSE_IDENTITY = ("0003:0000054C:00000CE6", "Apex 4 (DualSense)")
BOUNDED_DRY_RUN_ARGS = (
    "--trigger-bounded-mild-right", "--trigger-dry-run",
    "--trigger-debug", "--hid-debug")
BOUNDED_WRITE_ARGS = (
    "--trigger-bounded-mild-right", "--trigger-debug", "--hid-debug")
TRANSLATION_DRY_RUN_ARGS = (
    "--trigger-dry-run", "--trigger-debug", "--hid-debug",
    "--trigger-compare-semantic")
NATIVE_DRY_RUN_ARGS = (
    "--trigger-bounded-native-right", "--trigger-dry-run",
    "--trigger-debug", "--hid-debug")
NATIVE_WRITE_ARGS = (
    "--trigger-bounded-native-right", "--trigger-debug", "--hid-debug")
NATIVE_SESSION_DRY_RUN_ARGS = (
    "--trigger-bounded-native-session-right", "--trigger-dry-run",
    "--trigger-debug", "--hid-debug")
NATIVE_SESSION_WRITE_ARGS = (
    "--trigger-bounded-native-session-right", "--trigger-debug", "--hid-debug")
OW2_SAFE_DRY_RUN_ARGS = (
    "--trigger-ow2-safe-right", "--trigger-dry-run",
    "--trigger-debug", "--hid-debug")
OW2_SAFE_WRITE_ARGS = ("--trigger-ow2-safe-right", "--quiet-output")


class RelaySessionError(RuntimeError):
    pass


def default_lock_path():
    runtime = pathlib.Path("/run/user") / str(os.getuid())
    if runtime.is_dir():
        return runtime / "flydigi-apex4-profile-session.lock"
    private = pathlib.Path(tempfile.gettempdir()) / (
        "flydigi-apex4-%d" % os.getuid())
    private.mkdir(mode=0o700, exist_ok=True)
    return private / "profile-session.lock"


def identity_count(sysfs_root, identity):
    """Count this project's exact virtual HID identity in hidraw sysfs."""
    count = 0
    for path in pathlib.Path(sysfs_root).glob("hidraw*/device/uevent"):
        try:
            fields = dict(
                line.split("=", 1)
                for line in path.read_text(encoding="utf-8").splitlines()
                if "=" in line)
        except OSError:
            continue
        if (fields.get("HID_ID"), fields.get("HID_NAME")) == identity:
            count += 1
    return count


def identity_present(sysfs_root, identity):
    return identity_count(sysfs_root, identity) > 0


class RelayProfileSession:
    def __init__(self, relay_script, *, run=subprocess.run, sleep=time.sleep,
                 sysfs_root="/sys/class/hidraw", timeout=5.0,
                 command_timeout=10.0, lock_path=None, relay_args=()):
        self.relay_script = str(relay_script)
        self.run = run
        self.sleep = sleep
        self.sysfs_root = pathlib.Path(sysfs_root)
        self.timeout = max(0.0, float(timeout))
        self.command_timeout = max(0.1, float(command_timeout))
        relay_args = tuple(relay_args)
        if relay_args not in ((), BOUNDED_DRY_RUN_ARGS, BOUNDED_WRITE_ARGS,
                              TRANSLATION_DRY_RUN_ARGS, NATIVE_DRY_RUN_ARGS,
                              NATIVE_WRITE_ARGS, NATIVE_SESSION_DRY_RUN_ARGS,
                              NATIVE_SESSION_WRITE_ARGS, OW2_SAFE_DRY_RUN_ARGS,
                              OW2_SAFE_WRITE_ARGS):
            raise ValueError("profile session relay arguments are not allowlisted")
        self.relay_args = relay_args
        self.lock_path = pathlib.Path(lock_path) if lock_path else default_lock_path()
        self._lock_fd = None
        self._manual_invocation = None
        self._restore_required = False

    def _acquire_lock(self):
        fd = os.open(str(self.lock_path), os.O_RDWR | os.O_CREAT, 0o600)
        os.fchmod(fd, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            os.close(fd)
            raise RelaySessionError(
                "another controller profile session is already active") from exc
        os.ftruncate(fd, 0)
        os.write(fd, ("%d\n" % os.getpid()).encode())
        self._lock_fd = fd

    def _release_lock(self):
        if self._lock_fd is None:
            return
        fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
        os.close(self._lock_fd)
        self._lock_fd = None

    def _unit_active(self, unit):
        try:
            result = self.run(
                ["systemctl", "--user", "is-active", unit],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=self.command_timeout)
        except subprocess.TimeoutExpired as exc:
            raise RelaySessionError(
                "user service state check timed out after %.1fs"
                % self.command_timeout) from exc
        except OSError as exc:
            raise RelaySessionError("cannot inspect user service state: %s" % exc) from exc
        return result.returncode == 0

    def preflight(self):
        if not self._unit_active(DAILY_UNIT):
            raise RelaySessionError("installed Edge relay service is not active")
        if self._unit_active(MANUAL_UNIT):
            raise RelaySessionError("manual relay is active; refusing automatic switch")
        if identity_count(self.sysfs_root, EDGE_IDENTITY) != 1:
            raise RelaySessionError("expected exactly one project Edge identity")
        if identity_count(self.sysfs_root, DUALSENSE_IDENTITY) != 0:
            raise RelaySessionError("ordinary DualSense identity is already present")

    def _unit_invocation(self, unit):
        try:
            result = self.run(
                ["systemctl", "--user", "show", unit,
                 "--property=InvocationID", "--value"],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                text=True, timeout=self.command_timeout)
        except subprocess.TimeoutExpired as exc:
            raise RelaySessionError(
                "service ownership check timed out after %.1fs"
                % self.command_timeout) from exc
        except OSError as exc:
            raise RelaySessionError(
                "cannot inspect service ownership: %s" % exc) from exc
        value = (result.stdout or "").strip() if result.returncode == 0 else ""
        if not value:
            raise RelaySessionError(
                "temporary relay has no verifiable systemd invocation")
        return value

    def _run_checked(self, argv, phase):
        try:
            result = self.run(argv, timeout=self.command_timeout)
        except subprocess.TimeoutExpired as exc:
            raise RelaySessionError(
                "%s timed out after %.1fs" % (phase, self.command_timeout)) from exc
        except OSError as exc:
            raise RelaySessionError("%s: %s" % (phase, exc)) from exc
        if result.returncode != 0:
            raise RelaySessionError(
                "%s (exit status %d)" % (phase, result.returncode))

    def _wait_profile(self, identity, absent_identity, failure):
        deadline = time.monotonic() + self.timeout
        while True:
            if (identity_count(self.sysfs_root, identity) == 1
                    and identity_count(self.sysfs_root, absent_identity) == 0):
                return
            if time.monotonic() >= deadline:
                raise RelaySessionError(failure)
            self.sleep(min(0.1, max(0.0, deadline - time.monotonic())))

    def restore(self):
        if not self._restore_required:
            return
        errors = []
        try:
            daily_active = self._unit_active(DAILY_UNIT)
            manual_active = self._unit_active(MANUAL_UNIT)
            if daily_active:
                if (manual_active
                        or identity_count(self.sysfs_root, EDGE_IDENTITY) != 1
                        or identity_count(self.sysfs_root, DUALSENSE_IDENTITY) != 0):
                    raise RelaySessionError(
                        "daily Edge service became active during this session")
                self._restore_required = False
                self._manual_invocation = None
                return
            if manual_active:
                current = self._unit_invocation(MANUAL_UNIT)
                if current != self._manual_invocation:
                    raise RelaySessionError(
                        "temporary relay ownership changed; refusing to stop it")
        except RelaySessionError:
            raise
        try:
            if manual_active:
                self._run_checked(
                    [self.relay_script, "stop"],
                    "could not stop temporary DualSense relay")
        except RelaySessionError as exc:
            errors.append(str(exc))
        try:
            self._run_checked(
                ["systemctl", "--user", "start", DAILY_UNIT],
                "could not start installed Edge relay service")
        except RelaySessionError as exc:
            errors.append(str(exc))
        try:
            self._wait_profile(
                EDGE_IDENTITY, DUALSENSE_IDENTITY,
                "exclusive Edge identity did not return after restoration")
        except RelaySessionError as exc:
            errors.append(str(exc))
        if errors:
            raise RelaySessionError("; ".join(errors))
        self._restore_required = False
        self._manual_invocation = None

    def __enter__(self):
        self._acquire_lock()
        try:
            self.preflight()
            self._restore_required = True
            self._run_checked(
                [self.relay_script, "start", "--", "--emulate", "dualsense"]
                + list(self.relay_args),
                "could not start temporary DualSense relay")
            self._manual_invocation = self._unit_invocation(MANUAL_UNIT)
            self._wait_profile(
                DUALSENSE_IDENTITY, EDGE_IDENTITY,
                "exclusive temporary DualSense identity did not appear")
        except BaseException as switch_error:
            try:
                if self._restore_required:
                    self.restore()
            except RelaySessionError as restore_error:
                self._release_lock()
                raise RelaySessionError(
                    "%s; Edge restoration also failed: %s"
                    % (switch_error, restore_error)) from switch_error
            self._release_lock()
            raise
        return self

    def __exit__(self, exc_type, exc, traceback):
        try:
            self.restore()
        except RelaySessionError as restore_error:
            if exc is not None:
                raise RelaySessionError(
                    "game command failed (%s); Edge restoration also failed: %s"
                    % (exc, restore_error)) from restore_error
            raise
        finally:
            self._release_lock()
        return False
