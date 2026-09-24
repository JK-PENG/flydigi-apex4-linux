# SPDX-License-Identifier: MIT
import importlib.util
import pathlib
import shutil
import subprocess
import tempfile
import unittest

from apex4ds5._ds5 import ds5, ds5_usb

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools/windows-hid-probe.c"


class WindowsProbeTests(unittest.TestCase):
    def test_portable_vectors_match_linux_injector_and_guard_targets(self):
        self.assertTrue(SOURCE.exists(), "Windows HID probe source is missing")
        compiler = shutil.which("cc")
        if not compiler:
            self.skipTest("a development C compiler is needed for portable probe tests")
        with tempfile.TemporaryDirectory() as temp:
            binary = str(pathlib.Path(temp) / "probe")
            built = subprocess.run([compiler, "-std=c11", "-Wall", "-Wextra", "-Werror",
                                    "-DPROBE_PORTABLE_TEST", str(SOURCE), "-o", binary],
                                   capture_output=True, text=True)
            self.assertEqual(built.returncode, 0, built.stderr)
            run = subprocess.run([binary], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
        spec = importlib.util.spec_from_file_location("injector", ROOT / "tools/relay-trigger-test.py")
        injector = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(injector)
        lines = run.stdout.splitlines()
        self.assertEqual(len(lines), 5, "missing renamed-relay fingerprint verification")
        self.assertEqual(bytes.fromhex(lines[4]), b'\x09' + ds5_usb.FEATURE_REPORTS[9])
        for line, (side, effect) in zip(lines[:4], (("left", 1), ("left", 5), ("right", 1), ("right", 5))):
            report = bytes.fromhex(line)
            self.assertEqual(report, injector.output_report(side, effect))
            self.assertEqual(ds5.parse_output(report)["effects"][0].side, side)
