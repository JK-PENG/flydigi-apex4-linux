# SPDX-License-Identifier: MIT
import pathlib
import tempfile
import unittest

from apex4ds5 import relay_lock


class RelayLockTests(unittest.TestCase):
    def test_second_relay_is_refused_until_first_releases_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "relay.lock"
            first = relay_lock.RelayLock(path)
            try:
                with self.assertRaises(relay_lock.RelayBusy):
                    relay_lock.RelayLock(path)
            finally:
                first.close()
            second = relay_lock.RelayLock(path)
            second.close()

    def test_lock_file_records_holder_pid_without_relaxing_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "relay.lock"
            guard = relay_lock.RelayLock(path)
            try:
                self.assertEqual(int(path.read_text()), guard.pid)
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            finally:
                guard.close()


if __name__ == "__main__":
    unittest.main()
