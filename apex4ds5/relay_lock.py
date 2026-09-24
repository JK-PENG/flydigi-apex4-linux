# SPDX-License-Identifier: MIT
"""Process-level guard preventing two relay instances from owning one pad."""
import fcntl
import os
from pathlib import Path
import tempfile


class RelayBusy(RuntimeError):
    pass


def default_path():
    base = os.environ.get("XDG_RUNTIME_DIR")
    if base:
        return Path(base) / "flydigi-apex4-relay.lock"
    private = Path(tempfile.gettempdir()) / ("flydigi-apex4-%d" % os.getuid())
    private.mkdir(mode=0o700, exist_ok=True)
    return private / "relay.lock"


class RelayLock:
    def __init__(self, path=None):
        self.path = Path(path) if path is not None else default_path()
        self.pid = os.getpid()
        self.fd = os.open(str(self.path), os.O_RDWR | os.O_CREAT, 0o600)
        os.fchmod(self.fd, 0o600)
        try:
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            try:
                holder = os.read(self.fd, 32).decode(errors="replace").strip()
            finally:
                os.close(self.fd)
                self.fd = None
            raise RelayBusy(
                "another flydigi relay is already running%s"
                % (" (pid %s)" % holder if holder else "")) from exc
        os.ftruncate(self.fd, 0)
        os.write(self.fd, ("%d\n" % self.pid).encode())
        os.fsync(self.fd)

    def close(self):
        if self.fd is None:
            return
        fcntl.flock(self.fd, fcntl.LOCK_UN)
        os.close(self.fd)
        self.fd = None

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()
