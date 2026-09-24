# SPDX-License-Identifier: MIT
import importlib.util
import importlib.machinery
import pathlib
import subprocess
import struct
import sys
import unittest
from unittest import mock

from apex4ds5 import legacy, padin, trigger_translation
from apex4ds5._ds5 import ds5


ROOT = pathlib.Path(__file__).resolve().parents[1]
LOADER = importlib.machinery.SourceFileLoader("apex4_relay", str(ROOT / "apex4-ds5"))
SPEC = importlib.util.spec_from_loader("apex4_relay", LOADER)
RELAY = importlib.util.module_from_spec(SPEC)
LOADER.exec_module(RELAY)
WATCH_LOADER = importlib.machinery.SourceFileLoader(
    "relay_path_watch", str(ROOT / "tools" / "relay-path-watch.py"))
WATCH_SPEC = importlib.util.spec_from_loader("relay_path_watch", WATCH_LOADER)
RELAY_PATH_WATCH = importlib.util.module_from_spec(WATCH_SPEC)
WATCH_LOADER.exec_module(RELAY_PATH_WATCH)
CAPTURE_LOADER = importlib.machinery.SourceFileLoader(
    "paddle_capture", str(ROOT / "tools" / "paddle-capture.py"))
CAPTURE_SPEC = importlib.util.spec_from_loader("paddle_capture", CAPTURE_LOADER)
PADDLE_CAPTURE = importlib.util.module_from_spec(CAPTURE_SPEC)
CAPTURE_LOADER.exec_module(PADDLE_CAPTURE)


class ExistingFeatureRegressionTests(unittest.TestCase):
    def load_input_source_watch(self):
        path = ROOT / "tools" / "input-source-watch.py"
        self.assertTrue(path.exists(), "input-source-watch tool is missing")
        spec = importlib.util.spec_from_file_location("input_source_watch", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def load_trigger_capture_extract(self):
        path = ROOT / "tools" / "trigger-capture-extract.py"
        self.assertTrue(path.exists(), "trigger capture extractor is missing")
        spec = importlib.util.spec_from_file_location("trigger_capture_extract", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_input_report_keeps_sticks_triggers_buttons_motion(self):
        state = ds5.InputState()
        state.lx, state.ly, state.rx, state.ry = 1, 2, 3, 4
        state.l2, state.r2 = 5, 6
        state.buttons0, state.buttons1, state.buttons2 = ds5.CROSS, ds5.L1, ds5.PS_HOME
        state.gyro = [100, -200, 300]
        state.accel = [-400, 500, -600]
        report = state.pack()
        self.assertEqual(report[0:7], bytes([1, 1, 2, 3, 4, 5, 6]))
        self.assertTrue(report[8] & ds5.CROSS)
        self.assertTrue(report[9] & ds5.L1)
        self.assertTrue(report[10] & ds5.PS_HOME)
        self.assertNotEqual(report[16:28], bytes(12))

    def test_relay_exposes_semantic_translation_for_runtime_comparison(self):
        self.assertIs(RELAY.trigger_translation, trigger_translation)

    def test_edge_paddles_still_use_four_independent_bits(self):
        state = ds5.InputState()
        report = bytearray(state.pack())
        RELAY.apply_paddles(report, state, (True, True, True, True),
                            ("paddle-left", "fn1", "fn2", "paddle-right"))
        self.assertEqual(report[10] & 0xF0, 0xF0)
        self.assertEqual(RELAY.PRODUCT_DUALSENSE_EDGE, 0x0DF2)

    def test_paddle_bit_order_can_match_a_firmware_or_profile_variant(self):
        report = bytearray(legacy.REPORT_LEN)
        report[0] = legacy.INPUT_REPORT_ID
        report[7] = 1 << 2
        reading = legacy.Reading(bytes(report), paddle_bits=(2, 3, 4, 5))
        self.assertEqual(reading.paddles, (True, False, False, False))
        self.assertEqual(RELAY.parse_paddle_bits("2,3,4,5"), (2, 3, 4, 5))
        with self.assertRaises(SystemExit):
            RELAY.parse_paddle_bits("2,2,4,5")
        with self.assertRaises(SystemExit):
            RELAY.parse_paddle_bits("0,1,2,3")

    def test_default_paddles_follow_the_pads_physical_layout(self):
        """The M labels are not left to right, so the default list looks odd.

        Measured one button at a time on a retail APEX 4, 2026-09-11
        (docs/VALIDATION.md): pressing M1..M4 gives vendor bits 0x04/0x08/
        0x10/0x20, and in the player's own left-to-right order the labels run
        M2, M4, M3, M1. The default must land those on the Edge inputs in the
        same places. Reading the labels from the back flips left and right and
        would "confirm" the mirrored answer, which is what went wrong before.
        """
        label_bits = {"M1": 0x04, "M2": 0x08, "M3": 0x10, "M4": 0x20}
        player_order = ("M2", "M4", "M3", "M1")
        edge_bit = {"paddle-left": 0x40, "fn1": 0x10,
                    "fn2": 0x20, "paddle-right": 0x80}
        targets = dict(zip(("M1", "M2", "M3", "M4"),
                           RELAY.config.DEFAULTS["paddles"]))
        self.assertEqual([edge_bit[targets[label]] for label in player_order],
                         [0x40, 0x10, 0x20, 0x80])
        # ... and the vendor bits that carry those labels, left to right.
        self.assertEqual([label_bits[label] for label in player_order],
                         [0x08, 0x20, 0x10, 0x04])
        self.assertEqual(RELAY.parse_paddle_bits("2,3,4,5"), (2, 3, 4, 5))

    def test_capture_tool_agrees_with_the_relay_on_the_edge_bits(self):
        """The capture tool names the same bits the relay writes.

        Two files hold the same four constants. If they drift, a capture run
        reports the wrong button and looks perfectly self-consistent doing it,
        which is the failure mode this tool exists to prevent.
        """
        self.assertEqual(
            (RELAY.EDGE_FN1, RELAY.EDGE_FN2,
             RELAY.EDGE_PADDLE_LEFT, RELAY.EDGE_PADDLE_RIGHT),
            (0x10, 0x20, 0x40, 0x80))
        self.assertEqual(set(PADDLE_CAPTURE.EDGE_MEANING),
                         {RELAY.EDGE_FN1, RELAY.EDGE_FN2,
                          RELAY.EDGE_PADDLE_LEFT, RELAY.EDGE_PADDLE_RIGHT})
        self.assertEqual(PADDLE_CAPTURE.VENDOR_PADDLE_MASK, 0x3C)
        self.assertEqual(PADDLE_CAPTURE.VIRTUAL_PADDLE_OFFSET, 10)
        self.assertEqual(PADDLE_CAPTURE.VIRTUAL_PADDLE_MASK, 0xF0)
        self.assertEqual(PADDLE_CAPTURE.VIRTUAL_REPORT_ID, 0x01)

    def test_imu_live_check_requires_accel_and_gyro_motion(self):
        static = {name: [0, 0] for name in RELAY_PATH_WATCH.SENSOR_NAMES}
        accel_only = dict(static, accel_x=[-100, 100])
        gyro_only = dict(static, gyro_yaw=[-100, 100])
        both = dict(accel_only, gyro_yaw=[-100, 100])
        self.assertFalse(RELAY_PATH_WATCH.imu_passed(0, both))
        self.assertFalse(RELAY_PATH_WATCH.imu_passed(100, static))
        self.assertFalse(RELAY_PATH_WATCH.imu_passed(100, accel_only))
        self.assertFalse(RELAY_PATH_WATCH.imu_passed(100, gyro_only))
        self.assertTrue(RELAY_PATH_WATCH.imu_passed(100, both))

    def test_imu_wake_diagnostic_counts_only_xy_mouse_motion(self):
        event = struct.Struct("llHHi")
        payload = b"".join((
            event.pack(0, 0, 0x02, 0x00, 4),
            event.pack(0, 0, 0x02, 0x01, -3),
            event.pack(0, 0, 0x02, 0x08, 1),
            event.pack(0, 0, 0x01, 0x110, 1),
            event.pack(0, 0, 0x02, 0x00, 0),
        ))
        self.assertEqual(RELAY_PATH_WATCH.mouse_motion_events(payload), 2)

    def test_input_source_watch_classifies_only_gamepad_event_nodes(self):
        tool = self.load_input_source_watch()
        sample = """
I: Bus=0003 Vendor=04b4 Product=2412 Version=0111
N: Name="Flydigi Flydigi VADER3"
H: Handlers=event26 js1

I: Bus=0003 Vendor=054c Product=0ce6 Version=8000
N: Name="Apex 4 (DualSense)"
H: Handlers=event25 js0

I: Bus=0003 Vendor=054c Product=0ce6 Version=8000
N: Name="Apex 4 (DualSense) Motion Sensors"
H: Handlers=event28 js2

I: Bus=0003 Vendor=28de Product=11ff Version=0001
N: Name="Microsoft X-Box 360 pad 0"
H: Handlers=event31 js3
"""
        sources = tool.candidate_sources(tool.parse_devices(sample))
        self.assertEqual(
            [(item["source"], item["event"]) for item in sources],
            [("physical", "event26"),
             ("sony", "event25"),
             ("xbox", "event31")])

    def test_input_source_watch_formats_only_relevant_changes(self):
        tool = self.load_input_source_watch()
        self.assertEqual(
            tool.format_event("sony", 12.5, tool.EV_ABS, 0x05, 173),
            "t=12.500000 source=sony type=abs code=0x005 value=173")
        self.assertEqual(
            tool.format_event("xbox", 13.0, tool.EV_KEY, 0x130, 1),
            "t=13.000000 source=xbox type=key code=0x130 value=1")
        self.assertIsNone(tool.format_event("sony", 13.0, tool.EV_ABS, 0x00, 1))
        self.assertIsNone(tool.format_event("physical", 13.0,
                                            tool.EV_ABS, 0x02, 128))
        self.assertEqual(
            tool.format_event("physical", 13.0, tool.EV_ABS, 0x09, 255),
            "t=13.000000 source=physical type=abs code=0x009 value=255")

    def test_physical_only_input_watch_does_not_require_virtual_sony(self):
        tool = self.load_input_source_watch()
        self.assertTrue(hasattr(tool, "monitor_sources"),
                        "physical-only source selection is missing")
        sources = [{"source": "physical", "event": "event25"},
                   {"source": "sony", "event": "event27"}]
        self.assertEqual(tool.monitor_sources(sources, physical_only=True),
                         [sources[0]])
        self.assertEqual(tool.monitor_sources(sources, physical_only=False),
                         sources)
        help_text = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "input-source-watch.py"),
             "--help"], capture_output=True, text=True)
        self.assertEqual(help_text.returncode, 0, help_text.stderr)
        self.assertIn("--physical-only", help_text.stdout)

    def test_trigger_capture_extract_keeps_full_unique_effect_transitions(self):
        tool = self.load_trigger_capture_extract()
        report = bytearray(48)
        report[0], report[1], report[11] = 0x02, 0x04, 0x26
        report[12:22] = bytes([0xFF, 3, 0, 0, 0, 0, 0, 0, 21, 0])
        line = "HID t=12.500000 OUTPUT rtype=1 len=48 data=%s" % report.hex(" ")
        records = tool.extract_lines([line, line])
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["kind"], "effect")
        self.assertEqual(records[0]["side"], "right")
        self.assertEqual(records[0]["type"], "0x26")
        self.assertEqual(records[0]["params"], "ff030000000000001500")
        self.assertEqual(records[0]["report"], report.hex())

    def test_trigger_capture_extract_keeps_translation_comparison_context(self):
        tool = self.load_trigger_capture_extract()
        line = ("COMPARE R2: compat=mode=2 params=(0, 1, 120, 21, 0) "
                "semantic=mode=2 params=(0, 1, 32, 21, 0) "
                "t=12.500000 physical_l2=0 physical_r2=173")
        records = tool.extract_lines([line])
        self.assertEqual(records, [{
            "kind": "comparison", "side": "right", "t": 12.5,
            "compat": {"mode": 2, "params": [0, 1, 120, 21, 0]},
            "semantic": {"mode": 2, "params": [0, 1, 32, 21, 0]},
            "physical_l2": 0, "physical_r2": 173,
        }])

    def test_analogue_range_scaling_and_neutral_survive(self):
        state = padin.PadState({padin.ABS_X: (-128, 127),
                                padin.ABS_BRAKE: (0, 1023)})
        state.abs[padin.ABS_X] = -1
        state.abs[padin.ABS_BRAKE] = 1023
        self.assertEqual(state.stick(padin.ABS_X), 128)
        self.assertEqual(state.axis(padin.ABS_BRAKE), 255)

    def test_rumble_packet_and_stop_detection_are_unchanged(self):
        self.assertEqual(legacy.haptic_packet(0x34, 0x12),
                         bytes([0x05, 0x0F, 0x34, 0x12]))
        stop = bytearray(64)
        stop[0] = ds5.DS_OUTPUT_REPORT_USB
        self.assertTrue(RELAY.is_rumble_stop(stop))

    def test_device_info_parser_distinguishes_supported_model_and_connection(self):
        reply = bytearray(32)
        reply[0] = legacy.INPUT_REPORT_ID
        reply[3] = legacy.DEVICE_TYPE_APEX4
        reply[9], reply[10] = 0x30, 0x68
        reply[13] = 1
        reply[15] = legacy.CMD_GET_DEVICE_INFO
        info = legacy.parse_device_info(reply)
        self.assertEqual(info["device_type"], 84)
        self.assertEqual(info["connection"], "wired")

    def test_vendor_reconnect_gets_a_new_generation_without_losing_pad_state(self):
        link = RELAY.PadLink()
        with mock.patch.object(legacy, "find_vendor_node",
                               return_value="/dev/hidraw-test"), \
                mock.patch.object(padin, "find_pad",
                                  return_value=(None, None, None)), \
                mock.patch.object(RELAY.os, "open", side_effect=(31, 32)), \
                mock.patch.object(RELAY.os, "close"), \
                mock.patch("builtins.print"):
            self.assertTrue(link.open())
            self.assertEqual((link.vendor_fd, link.vendor_generation), (31, 1))
            link.drop("vendor_fd")
            self.assertTrue(link.open())
            self.assertEqual((link.vendor_fd, link.vendor_generation), (32, 2))


if __name__ == "__main__":
    unittest.main()
