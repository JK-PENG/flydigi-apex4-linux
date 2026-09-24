# SPDX-License-Identifier: MIT
import importlib.machinery
import importlib.util
import json
import io
import contextlib
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from apex4ds5 import forceadapt, trigger_identity, trigger_state, trigger_translation
from apex4ds5._ds5 import ds5


ROOT = pathlib.Path(__file__).resolve().parents[1]
TOOL_LOADER = importlib.machinery.SourceFileLoader(
    "relay_trigger_test", str(ROOT / "tools" / "relay-trigger-test.py"))
TOOL_SPEC = importlib.util.spec_from_loader("relay_trigger_test", TOOL_LOADER)
RELAY_TRIGGER_TEST = importlib.util.module_from_spec(TOOL_SPEC)
TOOL_LOADER.exec_module(RELAY_TRIGGER_TEST)


def output_report(side, effect_type, params=()):
    report = bytearray(64)
    report[0] = ds5.DS_OUTPUT_REPORT_USB
    if side == "right":
        report[1] = ds5.FLAG0_RIGHT_TRIGGER
        report[11] = effect_type
        report[12:22] = bytes(list(params) + [0] * (10 - len(params)))
    else:
        report[1] = ds5.FLAG0_LEFT_TRIGGER
        report[22] = effect_type
        report[23:33] = bytes(list(params) + [0] * (10 - len(params)))
    return bytes(report)


class DualSenseParserTests(unittest.TestCase):
    def test_safe_relay_tool_builds_parseable_bounded_vectors(self):
        mild = RELAY_TRIGGER_TEST.output_report("left", 0x01)
        off = RELAY_TRIGGER_TEST.output_report("right", 0x05)
        self.assertEqual(len(mild), 48)
        self.assertEqual(ds5.parse_output(mild)["effects"][0].key(),
                         ("left", 0x01, bytes([60, 40] + [0] * 8)))
        self.assertEqual(ds5.parse_output(off)["effects"][0].key(),
                         ("right", 0x05, bytes(10)))
        with self.assertRaises(ValueError):
            RELAY_TRIGGER_TEST.output_report("right", 0xEE)

    def test_fixed_generic_vectors_decode_to_expected_effects(self):
        from apex4ds5.generic_trigger import GenericSafeTranslator
        expected = {
            "l2-rattle-32": forceadapt.rattle("left", 0, 1, 32, 21),
            "l2-resistance-40": forceadapt.resistance("left", 0, 40),
            "r2-resistance-hold15": forceadapt.resistance("right", 0, 40),
            "l2-breakpoint-20": forceadapt.breakpoint("left", 60, 20, 20),
            "r2-breakpoint-20": forceadapt.breakpoint("right", 60, 20, 20),
            "l2-zone-rattle-32": forceadapt.rattle("left", 0, 1, 32, 21),
            "r2-zone-resistance-40": forceadapt.resistance("right", 0, 40),
            "l2-zone-weapon-20": forceadapt.breakpoint("left", 60, 20, 20),
            "r2-machine-unsupported": None,
        }
        candidate_mapper = GenericSafeTranslator(
            enabled_modes=frozenset({0, 1, 2, 3}))
        for name, mapped in expected.items():
            with self.subTest(name=name):
                report, off = RELAY_TRIGGER_TEST.candidate_reports(name)
                parsed = ds5.parse_output(report)["effects"]
                self.assertEqual(len(parsed), 1)
                self.assertEqual(candidate_mapper(parsed[0]), mapped)
                self.assertEqual(ds5.parse_output(off)["effects"][0].type,
                                 0x05)

    def test_virtual_injector_rejects_spoofed_or_ambiguous_identity(self):
        edge = ("HID_ID=0003:0000054C:00000DF2\n"
                "HID_NAME=Apex 4 (DualSense Edge)\n")
        spoofed = edge.replace("(DualSense Edge)", "(DualSense Edge) spoof")
        paths = ["/dev/hidraw1", "/dev/hidraw2"]
        with mock.patch.object(RELAY_TRIGGER_TEST.glob, "glob",
                               return_value=paths), \
                mock.patch("builtins.open", side_effect=lambda path: io.StringIO(
                    spoofed if "hidraw1" in path else edge)):
            self.assertEqual(RELAY_TRIGGER_TEST.virtual_node(), "/dev/hidraw2")
        with mock.patch.object(RELAY_TRIGGER_TEST.glob, "glob",
                               return_value=paths), \
                mock.patch("builtins.open",
                           side_effect=lambda path: io.StringIO(edge)):
            self.assertIsNone(RELAY_TRIGGER_TEST.virtual_node())

    def test_virtual_injector_closes_fd_when_off_write_is_short(self):
        reports = []

        def short_off(_fd, report):
            reports.append(report)
            return len(report) if len(reports) == 1 else 0

        with mock.patch.object(sys, "argv", ["relay-trigger-test.py", "--write",
                                             "--candidate", "l2-rattle-32"]), \
                mock.patch.object(RELAY_TRIGGER_TEST, "virtual_node",
                                  return_value="/dev/hidraw-test"), \
                mock.patch.object(RELAY_TRIGGER_TEST.os, "open",
                                  return_value=12), \
                mock.patch.object(RELAY_TRIGGER_TEST.os, "write",
                                  side_effect=short_off), \
                mock.patch.object(RELAY_TRIGGER_TEST.os, "close") as close, \
                mock.patch.object(RELAY_TRIGGER_TEST.time, "monotonic",
                                  side_effect=(10.0, 11.0)), \
                mock.patch.object(RELAY_TRIGGER_TEST.time, "sleep"), \
                mock.patch.object(RELAY_TRIGGER_TEST.signal, "signal"), \
                contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(OSError, "short virtual DS5 write"):
                RELAY_TRIGGER_TEST.main()
        self.assertEqual(len(reports), 2)
        close.assert_called_once_with(12)

    def test_extracts_right_and_left_effect_vectors(self):
        right = ds5.parse_output(output_report("right", 0x21, [1, 2, 3]))
        left = ds5.parse_output(output_report("left", 0x25, [4, 5, 6]))
        self.assertEqual(right["effects"][0].key(),
                         ("right", 0x21, bytes([1, 2, 3] + [0] * 7)))
        self.assertEqual(left["effects"][0].key(),
                         ("left", 0x25, bytes([4, 5, 6] + [0] * 7)))

    def test_rejects_malformed_and_unrelated_reports(self):
        self.assertEqual(ds5.parse_output(b"\x02\x0c")["effects"], [])
        self.assertEqual(ds5.parse_output(bytes([0x99]) + bytes(63))["effects"], [])

    def test_preserves_rumble_with_trigger_bits(self):
        report = bytearray(output_report("right", 5))
        report[1] |= ds5.FLAG0_MOTOR
        report[3], report[4] = 17, 29
        self.assertEqual(ds5.parse_output(report)["rumble"], (29, 17))

    def test_extracts_bluetooth_effect_at_its_extra_transport_offset(self):
        report = bytearray(65)
        report[0] = ds5.DS_OUTPUT_REPORT_BT
        report[2] = ds5.FLAG0_LEFT_TRIGGER
        report[23] = 0x26
        report[24:34] = bytes(range(10))
        effect = ds5.parse_output(report)["effects"][0]
        self.assertEqual(effect.key(), ("left", 0x26, bytes(range(10))))


class TranslationTests(unittest.TestCase):
    def effect(self, side, type_, params=()):
        return ds5.TriggerEffect(side, type_, bytes(list(params) + [0] * (10 - len(params))))

    def test_normal_clears_the_requested_side(self):
        mapped = trigger_translation.translate(self.effect("left", 5))
        self.assertEqual(mapped, forceadapt.normal("left"))

    def test_simple_resistance_preserves_start_and_strength(self):
        mapped = trigger_translation.translate(self.effect("right", 1, [90, 200]))
        self.assertEqual(mapped, forceadapt.ForceAdaptEffect("right", 1,
                                                            (90, 200, 0, 0, 0)))

    def test_simple_weapon_becomes_breakpoint(self):
        mapped = trigger_translation.translate(self.effect("right", 2, [10, 20, 150]))
        self.assertEqual(mapped, forceadapt.ForceAdaptEffect("right", 3,
                                                            (10, 20, 150, 0, 0)))

    def test_simple_vibration_becomes_rattle(self):
        mapped = trigger_translation.translate(self.effect("left", 6, [11, 22, 33]))
        self.assertEqual(mapped, forceadapt.ForceAdaptEffect("left", 2,
                                                            (33, 22, 22, 11, 0)))

    def test_official_feedback_and_weapon_vectors(self):
        feedback = trigger_translation.parse(self.effect(
            "right", 0x21, [0b11111100, 0x03, 0x49, 0x92, 0x24, 0]))
        weapon = trigger_translation.parse(self.effect("left", 0x25, [0x24, 0, 7]))
        self.assertEqual((feedback.kind, feedback.start_zone, feedback.end_zone),
                         ("resistance", 2, 9))
        self.assertEqual((weapon.kind, weapon.start_zone, weapon.end_zone,
                          weapon.strength), ("breakpoint", 2, 5, 255))

    def test_bow_galloping_and_machine_have_documented_fallbacks(self):
        bow = trigger_translation.translate(self.effect("right", 0x22, [0x24, 0, 0x3F]))
        gallop = trigger_translation.translate(self.effect("left", 0x23,
                                                           [0x24, 0, 0x0B, 7]))
        machine = trigger_translation.translate(self.effect("right", 0x27,
                                                            [0x24, 0, 0x3F, 9, 3]))
        self.assertEqual(bow.mode, forceadapt.MODE_BREAKPOINT)
        self.assertEqual(gallop.mode, forceadapt.MODE_RATTLE)
        self.assertEqual(machine.mode, forceadapt.MODE_RATTLE)
        self.assertEqual(machine.params, (57, 223, 223, 9, 0))

    def test_semantically_invalid_known_effects_do_not_generate_commands(self):
        invalid = (
            self.effect("right", 0x25, [4, 0, 7]),
            self.effect("right", 0x22, [3, 0, 0x3F]),
            self.effect("left", 0x23, [0x24, 0, 0x19, 7]),
            self.effect("left", 0x27, [0x24, 0, 0x3F, 0, 3]),
            self.effect("right", 0x26, [0, 0xFC, 0, 0, 0, 0, 0, 0, 9]),
        )
        for effect in invalid:
            with self.subTest(effect=effect):
                self.assertEqual(trigger_translation.parse(effect).kind, "invalid")
                self.assertIsNone(trigger_translation.translate(effect))

    def test_limited_effect_types_are_explicitly_unsupported(self):
        for type_, params in ((0x11, [60, 40]),
                              (0x12, [10, 20, 30])):
            with self.subTest(type_=type_):
                effect = self.effect("right", type_, params)
                normalized = trigger_translation.parse(effect)
                self.assertEqual(normalized.kind, "unsupported")
                self.assertIn("limited", normalized.detail)
                self.assertIsNone(trigger_translation.translate(effect))
                self.assertIsNone(
                    trigger_translation.translate_semantic(effect))

    def test_game_specific_mapping_vectors_match_mit_reference(self):
        cases = (
            ("right", 0x21, [0xFF, 3, 0xFF], 1, (110, 50, 0, 0, 0)),
            ("right", 0x21, [0], 1, (120, 1, 0, 0, 0)),
            ("right", 0x21, [0xFF, 3, 2], 1, (1, 64, 0, 0, 0)),
            ("right", 0x21, [8, 2], 1, (1, 1, 0, 0, 0)),
            ("right", 0x25, [20, 0, 2], 3, (70, 20, 20, 0, 0)),
            ("right", 0x25, [20, 0, 6], 3, (70, 60, 20, 0, 0)),
            ("right", 0x25, [20, 0, 1], 3, (20, 10, 20, 0, 0)),
            ("right", 0x25, [20, 0, 3], 3, (50, 30, 1, 0, 1)),
            ("right", 0x25, [20, 0, 4], 2, (50, 1, 10, 10, 10)),
            ("right", 0x25, [12, 0, 7], 3, (70, 0, 12, 0, 0)),
            ("right", 0x25, [36, 0, 6], 3, (10, 36, 70, 0, 0)),
            ("right", 0x25, [68, 0, 7], 3, (70, 50, 68, 0, 0)),
            ("right", 0x25, [4, 1, 5], 3, (80, 200, 90, 0, 0)),
            ("right", 0x25, [64, 1, 3], 3, (120, 150, 60, 0, 0)),
            ("right", 0x25, [72, 0, 4], 3, (64, 72, 0, 4, 1)),
            ("right", 0x26, [240, 2, 0, 0, 0, 0, 0, 0, 17],
             2, (15, 1, 90, 17, 0)),
            ("left", 0x21, [0], 1, (120, 1, 0, 0, 0)),
            ("left", 0x21, [252], 1, (1, 96, 0, 0, 0)),
            ("left", 0x21, [192, 3, 0, 0, 0, 4], 1, (140, 5, 0, 0, 0)),
            ("left", 0x21, [128, 0, 0, 0, 44], 1, (128, 44, 0, 0, 0)),
            ("left", 0x25, [36, 0, 6], 3, (64, 36, 0, 6, 1)),
            ("left", 0x26, [240, 3, 0, 0, 0, 0, 0, 0, 9],
             1, (30, 73, 0, 0, 0)),
            ("left", 0x26, [200, 1, 2, 7, 6, 5, 0, 0, 11],
             2, (55, 1, 7, 11, 0)),
        )
        for side, type_, params, mode, expected in cases:
            with self.subTest(side=side, type=type_, params=params):
                mapped = trigger_translation.translate(
                    self.effect(side, type_, params), left_motor=73)
                self.assertEqual((mapped.mode, mapped.params), (mode, expected))

        self.assertIsNone(trigger_translation.translate(
            self.effect("left", 0x26, [0xFF, 3, 0, 0xFF])))

    def test_semantic_ow2_vectors_preserve_decoded_strength(self):
        vibration = self.effect(
            "right", 0x26, [0xFF, 3, 0, 0, 0, 0, 0, 0, 21])
        feedback = self.effect(
            "right", 0x21, [0xFF, 3, 0x49, 0x92, 0x24, 0])
        compat_vibration = trigger_translation.translate(vibration)
        semantic_vibration = trigger_translation.translate_semantic(vibration)
        compat_feedback = trigger_translation.translate(feedback)
        semantic_feedback = trigger_translation.translate_semantic(feedback)
        decoded_feedback = trigger_translation.parse(feedback)
        self.assertEqual(compat_vibration.params, (0, 1, 120, 21, 0))
        self.assertEqual(semantic_vibration.params, (0, 1, 32, 21, 0))
        self.assertEqual(compat_feedback.params, (1, 64, 0, 0, 0))
        self.assertEqual(semantic_feedback.params,
                         (0, decoded_feedback.strength, 0, 0, 0))

    def test_captured_ow2_fixture_replays_full_reports_and_decisions(self):
        path = ROOT / "tests" / "fixtures" / "ow2-hanzo-2026-09-21.json"
        self.assertTrue(path.exists(), "captured OW2 fixture is missing")
        fixture = json.loads(path.read_text())
        self.assertEqual(fixture["provenance"], "captured")
        for name, expected_type in (("rattle", 0x26),
                                    ("resistance", 0x21),
                                    ("off", 0x05)):
            report = bytes.fromhex(fixture["vectors"][name]["report"])
            effect = next(item for item in ds5.parse_output(report)["effects"]
                          if item.side == "right")
            self.assertEqual(effect.type, expected_type)
            compat = trigger_translation.translate(effect)
            semantic = trigger_translation.translate_semantic(effect)
            self.assertEqual(
                [compat.mode, list(compat.params)],
                fixture["vectors"][name]["compat"])
            self.assertEqual(
                [semantic.mode, list(semantic.params)],
                fixture["vectors"][name]["semantic"])
        self.assertEqual(
            [(item["rattle_r2"], item["resistance_r2"], item["off_r2"])
             for item in fixture["actions"]],
            [(12, 228, 0), (11, 129, 0), (14, 255, 0)])

    def test_ow2_safe_translation_accepts_only_captured_right_patterns(self):
        rattle = self.effect(
            "right", 0x26, [0xFF, 3, 0, 0, 0, 0, 0, 0, 21])
        resistance = self.effect(
            "right", 0x21, [0xFF, 3, 0x92, 0x24, 0x49, 0x12])
        off = self.effect("right", 0x05)
        self.assertEqual(
            trigger_translation.translate_ow2_safe(rattle),
            forceadapt.rattle("right", 0, 1, 32, 21))
        self.assertEqual(
            trigger_translation.translate_ow2_safe(resistance),
            forceadapt.resistance("right", 0, 96))
        self.assertEqual(
            trigger_translation.translate_ow2_safe(off),
            forceadapt.normal("right"))
        self.assertIsNone(trigger_translation.translate_ow2_safe(
            self.effect("left", 0x26,
                        [0xFF, 3, 0, 0, 0, 0, 0, 0, 21])))
        self.assertIsNone(trigger_translation.translate_ow2_safe(
            self.effect("right", 0x26,
                        [0xFF, 2, 0, 0, 0, 0, 0, 0, 21])))
        self.assertIsNone(trigger_translation.translate_ow2_safe(
            self.effect("right", 0x01, [60, 40])))

    def test_unknown_and_noop_effects_do_not_generate_commands(self):
        self.assertIsNone(trigger_translation.translate(self.effect("right", 0)))
        self.assertIsNone(trigger_translation.translate(self.effect("right", 0xEE)))

    def test_invalid_side_and_short_parameter_blocks_are_rejected(self):
        self.assertIsNone(trigger_translation.parse(ds5.TriggerEffect("middle", 1, bytes(10))))
        self.assertIsNone(trigger_translation.parse(ds5.TriggerEffect("left", 1, b"\x01")))


class PacketBuilderTests(unittest.TestCase):
    def test_exact_normal_and_resistance_packets(self):
        self.assertEqual(
            forceadapt.build_packet(forceadapt.normal("right")),
            bytes([0x05, 0xA0, 0x01, 1, 2, 0] + [0] * 9))
        self.assertEqual(
            forceadapt.build_packet(forceadapt.resistance("left", 60, 40)),
            bytes([0x05, 0xA0, 0x01, 1, 1, 1, 60, 40] + [0] * 7))

    def test_side_mode_and_parameters_are_bounded(self):
        effect = forceadapt.ForceAdaptEffect("left", forceadapt.MODE_RATTLE,
                                             (-10, 999, 2, 500, 1))
        packet = forceadapt.build_packet(effect)
        self.assertEqual(packet[4], forceadapt.SIDE_LEFT)
        self.assertEqual(packet[5], forceadapt.MODE_RATTLE)
        self.assertEqual(packet[6:11], bytes([0, 255, 2, 255, 1]))
        with self.assertRaises(ValueError):
            forceadapt.ForceAdaptEffect("both", 1, (0, 0, 0, 0, 0))
        with self.assertRaises(ValueError):
            forceadapt.ForceAdaptEffect("left", 0xA0, (0, 0, 0, 0, 0))
        for undocumented in (forceadapt.MODE_LOCK,
                             forceadapt.MODE_VIBRATION):
            with self.subTest(undocumented=undocumented), \
                    self.assertRaises(ValueError):
                forceadapt.ForceAdaptEffect(
                    "left", undocumented, (0, 0, 0, 0, 0))

    def test_race_match_input_at_zero_is_cleared(self):
        effect = forceadapt.ForceAdaptEffect("right", forceadapt.MODE_RESISTANCE,
                                             (0, 30, 1, 0, 0))
        self.assertEqual(forceadapt.build_packet(effect)[8], 0)


class FakeTransport:
    def __init__(self):
        self.effects = []

    def write_effect(self, effect):
        self.effects.append(effect)
        return forceadapt.build_packet(effect)


class FailingTransport:
    def write_effect(self, effect):
        raise OSError("test write failure")


class StateManagerTests(unittest.TestCase):
    def setUp(self):
        self.now = [10.0]
        self.transport = FakeTransport()
        self.manager = trigger_state.TriggerStateManager(
            transport=self.transport, clock=lambda: self.now[0], reset_timeout=5.0)

    def effect(self, side="right", type_=1, params=(60, 40)):
        return ds5.TriggerEffect(side, type_, bytes(list(params) + [0] * (10 - len(params))))

    def test_deduplicates_and_sends_effect_changes(self):
        self.manager.handle(self.effect())
        self.manager.handle(self.effect())
        self.manager.handle(self.effect(params=(60, 80)))
        self.assertEqual(len(self.transport.effects), 2)

    def test_unknown_effect_does_not_replace_last_state(self):
        self.manager.handle(self.effect())
        self.manager.handle(self.effect(type_=0xEE, params=()))
        self.assertEqual(len(self.transport.effects), 1)
        self.assertEqual(self.manager.last["right"].mode, forceadapt.MODE_RESISTANCE)

    def test_debug_comparison_logs_context_and_both_translation_profiles(self):
        logs = []
        manager = trigger_state.TriggerStateManager(
            dry_run=True, debug=True, clock=lambda: self.now[0],
            logger=logs.append,
            comparison_translator=trigger_translation.translate_semantic)
        manager.handle(
            self.effect("right", 0x26,
                        [0xFF, 3, 0, 0, 0, 0, 0, 0, 21]),
            context={"t": 12.25, "physical_l2": 0, "physical_r2": 173})
        comparison = next(line for line in logs if line.startswith("COMPARE R2"))
        self.assertIn("compat=mode=2 params=(0, 1, 120, 21, 0)", comparison)
        self.assertIn("semantic=mode=2 params=(0, 1, 32, 21, 0)", comparison)
        self.assertIn("t=12.250000 physical_l2=0 physical_r2=173", comparison)

    def test_semantic_compare_cli_requires_trigger_dry_run(self):
        rejected = subprocess.run(
            [sys.executable, str(ROOT / "apex4-ds5"),
             "--trigger-compare-semantic", "--calib"],
            capture_output=True, text=True)
        self.assertEqual(rejected.returncode, 2)
        self.assertIn("requires --trigger-dry-run", rejected.stderr)
        allowed = subprocess.run(
            [sys.executable, str(ROOT / "apex4-ds5"),
             "--trigger-compare-semantic", "--trigger-dry-run", "--calib"],
            capture_output=True, text=True)
        self.assertEqual(allowed.returncode, 0, allowed.stderr)

    def test_output_timeout_clears_both_triggers(self):
        self.manager.handle(self.effect())
        self.now[0] += 5.1
        self.assertTrue(self.manager.expire())
        self.assertEqual(self.transport.effects[-2:],
                         [forceadapt.normal("left"), forceadapt.normal("right")])

    def test_inactivity_watchdog_is_quiet_until_an_active_effect_is_due(self):
        self.assertIsNone(self.manager.expire())
        self.manager.handle(self.effect())
        self.now[0] += 4.9
        self.assertIsNone(self.manager.expire())

    def test_unrelated_output_does_not_extend_active_effect_timeout(self):
        self.manager.handle(self.effect())
        self.now[0] += 5.1
        self.manager.note_output()
        self.assertTrue(self.manager.expire())

    def test_fresh_effect_on_other_side_does_not_extend_stale_side(self):
        self.manager.handle(self.effect(side="left"))
        self.now[0] += 4.0
        self.manager.handle(self.effect(side="right"))
        self.now[0] += 1.1
        self.assertTrue(self.manager.expire())

    def test_failed_initial_clear_prevents_pending_effect_replay(self):
        logs = []
        manager = trigger_state.TriggerStateManager(
            queue_pending=True, logger=logs.append)
        manager.handle(self.effect())
        self.assertFalse(manager.attach(FailingTransport()))
        self.assertEqual(manager.last, {"left": None, "right": None})
        self.assertTrue(any("clear failed" in line for line in logs))

    def test_disconnect_shutdown_and_disable_attempt_reset(self):
        self.manager.handle(self.effect())
        self.manager.detach("disconnect")
        self.assertEqual(self.transport.effects[-2:],
                         [forceadapt.normal("left"), forceadapt.normal("right")])
        other = FakeTransport()
        self.manager.attach(other)
        self.manager.disable()
        self.assertEqual(other.effects,
                         [forceadapt.normal("left"), forceadapt.normal("right"),
                          forceadapt.normal("left"), forceadapt.normal("right")])

    def test_latest_effect_waits_for_identity_and_replays_once(self):
        logs = []
        manager = trigger_state.TriggerStateManager(
            transport=None, queue_pending=True, debug=True, logger=logs.append)
        first = self.effect(params=(60, 40))
        latest = self.effect(params=(70, 80))
        self.assertFalse(manager.handle(first))
        self.assertFalse(manager.handle(first))
        self.assertFalse(manager.handle(latest))
        transport = FakeTransport()
        self.assertTrue(manager.attach(transport))
        self.assertEqual(transport.effects,
                         [forceadapt.normal("left"), forceadapt.normal("right"),
                          forceadapt.resistance("right", 70, 80)])

    def test_reset_while_identity_is_pending_prevents_stale_replay(self):
        manager = trigger_state.TriggerStateManager(
            transport=None, queue_pending=True)
        manager.handle(self.effect())
        manager.clear_all("virtual DualSense closed", force=True)
        transport = FakeTransport()
        self.assertTrue(manager.attach(transport))
        self.assertEqual(transport.effects,
                         [forceadapt.normal("left"), forceadapt.normal("right")])

    def test_output_timeout_discards_an_unverified_pending_effect(self):
        manager = trigger_state.TriggerStateManager(
            transport=None, queue_pending=True, reset_timeout=2.0,
            clock=lambda: self.now[0])
        manager.handle(self.effect())
        self.now[0] += 2.1
        self.assertFalse(manager.expire())
        transport = FakeTransport()
        self.assertTrue(manager.attach(transport))
        self.assertEqual(transport.effects,
                         [forceadapt.normal("left"), forceadapt.normal("right")])

    def test_stale_pending_effect_is_not_replayed_without_expire_poll(self):
        manager = trigger_state.TriggerStateManager(
            transport=None, queue_pending=True, reset_timeout=0,
            pending_ttl=2.0, clock=lambda: self.now[0])
        manager.handle(self.effect())
        self.now[0] += 100.0
        transport = FakeTransport()
        self.assertTrue(manager.attach(transport))
        self.assertEqual(transport.effects,
                         [forceadapt.normal("left"), forceadapt.normal("right")])

    def test_one_shot_mild_caps_first_right_effect_for_one_second(self):
        gate = trigger_state.OneShotMildGate(clock=lambda: self.now[0])
        manager = trigger_state.TriggerStateManager(
            transport=self.transport, clock=lambda: self.now[0], effect_filter=gate)
        manager.handle(self.effect(type_=6, params=(11, 22, 33)))
        manager.handle(self.effect(params=(1, 255)))
        manager.handle(self.effect(side="left", params=(1, 255)))
        self.assertEqual(self.transport.effects,
                         [forceadapt.resistance("right", 60, 40)])
        self.now[0] += 0.99
        self.assertIsNone(gate.expire(manager))
        self.now[0] += 0.02
        self.assertTrue(gate.expire(manager))
        self.assertEqual(self.transport.effects[-2:],
                         [forceadapt.normal("left"), forceadapt.normal("right")])
        count = len(self.transport.effects)
        manager.handle(self.effect(params=(1, 255)))
        self.assertEqual(len(self.transport.effects), count)

    def test_one_shot_mild_does_not_arm_before_identity_attach(self):
        gate = trigger_state.OneShotMildGate(clock=lambda: self.now[0])
        manager = trigger_state.TriggerStateManager(
            transport=None, queue_pending=False, clock=lambda: self.now[0],
            effect_filter=gate)
        self.assertFalse(manager.handle(self.effect(type_=6, params=(11, 22, 33))))
        self.assertTrue(manager.attach(self.transport))
        manager.handle(self.effect(type_=6, params=(11, 22, 33)))
        self.assertEqual(self.transport.effects[-1],
                         forceadapt.resistance("right", 60, 40))

    def test_one_shot_mild_accepts_game_off_as_early_reset(self):
        gate = trigger_state.OneShotMildGate(clock=lambda: self.now[0])
        manager = trigger_state.TriggerStateManager(
            transport=self.transport, clock=lambda: self.now[0], effect_filter=gate)
        manager.handle(self.effect(type_=6, params=(11, 22, 33)))
        manager.handle(self.effect(type_=5, params=()))
        self.assertEqual(self.transport.effects,
                         [forceadapt.resistance("right", 60, 40),
                          forceadapt.normal("right")])
        self.now[0] += 2.0
        self.assertIsNone(gate.expire(manager))

    def test_bounded_dynamic_gate_adapts_rattle_to_verified_resistance(self):
        gate = trigger_state.BoundedDynamicGate(clock=lambda: self.now[0])
        manager = trigger_state.TriggerStateManager(
            transport=self.transport, clock=lambda: self.now[0],
            effect_filter=gate)
        manager.handle(self.effect(type_=6, params=(11, 22, 33)))
        self.assertEqual(self.transport.effects,
                         [forceadapt.resistance("right", 60, 40)])
        manager.handle(self.effect(side="left", params=(1, 255)))
        manager.handle(self.effect(params=(1, 255)))
        manager.handle(self.effect(params=(80, 20)))
        self.assertEqual(self.transport.effects, [
            forceadapt.resistance("right", 60, 40),
            forceadapt.resistance("right", 80, 20),
        ])

    def test_bounded_dynamic_deadline_does_not_slide_and_requires_normal(self):
        gate = trigger_state.BoundedDynamicGate(
            duration=1.0, max_cycles=2, session_duration=10.0,
            clock=lambda: self.now[0])
        manager = trigger_state.TriggerStateManager(
            transport=self.transport, clock=lambda: self.now[0],
            effect_filter=gate)
        manager.handle(self.effect(params=(1, 255)))
        self.now[0] += 0.9
        manager.handle(self.effect(params=(80, 20)))
        self.now[0] += 0.11
        self.assertTrue(gate.expire(manager))
        count = len(self.transport.effects)
        manager.handle(self.effect(params=(90, 10)))
        self.assertEqual(len(self.transport.effects), count)
        manager.handle(self.effect(type_=5, params=()))
        manager.handle(self.effect(params=(90, 10)))
        self.assertEqual(self.transport.effects[-1],
                         forceadapt.resistance("right", 90, 10))

    def test_bounded_dynamic_total_cycle_budget_cannot_be_rearmed(self):
        gate = trigger_state.BoundedDynamicGate(
            duration=1.0, max_cycles=1, session_duration=10.0,
            clock=lambda: self.now[0])
        manager = trigger_state.TriggerStateManager(
            transport=self.transport, clock=lambda: self.now[0],
            effect_filter=gate)
        manager.handle(self.effect())
        manager.handle(self.effect(type_=5, params=()))
        count = len(self.transport.effects)
        manager.handle(self.effect(params=(80, 20)))
        self.assertEqual(len(self.transport.effects), count)

    def test_bounded_dynamic_default_window_allows_three_human_paced_cycles(self):
        gate = trigger_state.BoundedDynamicGate(clock=lambda: self.now[0])
        manager = trigger_state.TriggerStateManager(
            transport=self.transport, clock=lambda: self.now[0],
            effect_filter=gate)
        for index in range(3):
            manager.handle(self.effect(params=(60 + index * 10, 40)))
            manager.handle(self.effect(type_=5, params=()))
            self.now[0] += 7.0
        resistance = [effect for effect in self.transport.effects
                      if effect.mode == forceadapt.MODE_RESISTANCE]
        self.assertEqual(len(resistance), 3)

    def test_bounded_dynamic_session_deadline_still_forces_reset_on_output(self):
        gate = trigger_state.BoundedDynamicGate(
            duration=1.0, max_cycles=3, session_duration=1.0,
            clock=lambda: self.now[0])
        manager = trigger_state.TriggerStateManager(
            transport=self.transport, clock=lambda: self.now[0],
            effect_filter=gate)
        manager.handle(self.effect())
        self.now[0] += 1.01
        manager.handle(self.effect(params=(80, 20)))
        self.assertTrue(gate.expire(manager))
        self.assertEqual(self.transport.effects[-2:],
                         [forceadapt.normal("left"), forceadapt.normal("right")])

    def test_bounded_dynamic_does_not_resume_after_transport_disconnect(self):
        gate = trigger_state.BoundedDynamicGate(clock=lambda: self.now[0])
        manager = trigger_state.TriggerStateManager(
            transport=self.transport, clock=lambda: self.now[0],
            effect_filter=gate)
        manager.handle(self.effect())
        manager.detach("test disconnect")
        replacement = FakeTransport()
        self.assertTrue(manager.attach(replacement))
        count = len(replacement.effects)
        manager.handle(self.effect(params=(80, 20)))
        self.assertEqual(len(replacement.effects), count)

    def test_bounded_native_gate_preserves_captured_mode_change_with_caps(self):
        gate = trigger_state.BoundedNativeGate(clock=lambda: self.now[0])
        manager = trigger_state.TriggerStateManager(
            transport=self.transport, clock=lambda: self.now[0],
            translator=trigger_translation.translate_semantic,
            effect_filter=gate)
        manager.handle(self.effect(
            type_=0x26, params=(0xFF, 3, 0, 0, 0, 0, 0, 0, 21)))
        self.assertEqual(
            self.transport.effects[-1],
            forceadapt.rattle("right", 0, 1, 32, 21))
        self.now[0] += 0.72
        manager.handle(self.effect(
            type_=0x21, params=(0xFF, 3, 0x92, 0x24, 0x49, 0x12)))
        self.assertEqual(
            self.transport.effects[-1],
            forceadapt.resistance("right", 0, 40))
        self.now[0] += 0.29
        self.assertTrue(gate.expire(manager))
        self.assertEqual(self.transport.effects[-2:],
                         [forceadapt.normal("left"),
                          forceadapt.normal("right")])
        count = len(self.transport.effects)
        manager.handle(self.effect(
            type_=0x26, params=(0xFF, 3, 0, 0, 0, 0, 0, 0, 21)))
        self.assertEqual(len(self.transport.effects), count)

    def test_bounded_native_gate_rejects_left_and_other_modes(self):
        gate = trigger_state.BoundedNativeGate(clock=lambda: self.now[0])
        manager = trigger_state.TriggerStateManager(
            transport=self.transport, clock=lambda: self.now[0],
            translator=trigger_translation.translate_semantic,
            effect_filter=gate)
        manager.handle(self.effect(side="left", type_=0x26,
                                   params=(0xFF, 3, 0, 0, 0, 0, 0, 0, 21)))
        manager.handle(self.effect(type_=0x02, params=(20, 40, 30)))
        self.assertEqual(self.transport.effects, [])

    def test_bounded_native_gate_off_clears_early_and_cannot_rearm(self):
        gate = trigger_state.BoundedNativeGate(clock=lambda: self.now[0])
        manager = trigger_state.TriggerStateManager(
            transport=self.transport, clock=lambda: self.now[0],
            translator=trigger_translation.translate_semantic,
            effect_filter=gate)
        rattle = self.effect(
            type_=0x26, params=(0xFF, 3, 0, 0, 0, 0, 0, 0, 21))
        manager.handle(rattle)
        manager.handle(self.effect(type_=0x05, params=()))
        self.assertEqual(self.transport.effects[-1],
                         forceadapt.normal("right"))
        count = len(self.transport.effects)
        manager.handle(rattle)
        self.assertEqual(len(self.transport.effects), count)
        self.now[0] += 2.0
        self.assertIsNone(gate.expire(manager))

    def test_bounded_native_session_accepts_three_off_rearmed_cycles(self):
        gate = trigger_state.BoundedNativeGate(
            duration=4.0, max_cycles=3, session_duration=30.0,
            clock=lambda: self.now[0])
        manager = trigger_state.TriggerStateManager(
            transport=self.transport, clock=lambda: self.now[0],
            translator=trigger_translation.translate_semantic,
            effect_filter=gate)
        rattle = self.effect(
            type_=0x26, params=(0xFF, 3, 0, 0, 0, 0, 0, 0, 21))
        resistance = self.effect(
            type_=0x21, params=(0xFF, 3, 0x92, 0x24, 0x49, 0x12))
        off = self.effect(type_=0x05, params=())
        for _index in range(3):
            manager.handle(rattle)
            self.now[0] += 0.72
            manager.handle(resistance)
            self.now[0] += 0.5
            manager.handle(off)
            self.now[0] += 2.0
        self.assertEqual(
            [effect.mode for effect in self.transport.effects],
            [forceadapt.MODE_RATTLE, forceadapt.MODE_RESISTANCE,
             forceadapt.MODE_NORMAL] * 3)
        count = len(self.transport.effects)
        manager.handle(rattle)
        self.assertEqual(len(self.transport.effects), count)

    def test_bounded_native_session_deadline_does_not_slide(self):
        gate = trigger_state.BoundedNativeGate(
            duration=4.0, max_cycles=2, session_duration=30.0,
            clock=lambda: self.now[0])
        manager = trigger_state.TriggerStateManager(
            transport=self.transport, clock=lambda: self.now[0],
            translator=trigger_translation.translate_semantic,
            effect_filter=gate)
        manager.handle(self.effect(
            type_=0x26, params=(0xFF, 3, 0, 0, 0, 0, 0, 0, 21)))
        self.now[0] += 3.8
        manager.handle(self.effect(
            type_=0x21, params=(0xFF, 3, 0x92, 0x24, 0x49, 0x12)))
        self.now[0] += 0.21
        self.assertTrue(gate.expire(manager))
        self.assertEqual(self.transport.effects[-2:],
                         [forceadapt.normal("left"),
                          forceadapt.normal("right")])
        count = len(self.transport.effects)
        manager.handle(self.effect(
            type_=0x26, params=(0xFF, 3, 0, 0, 0, 0, 0, 0, 21)))
        self.assertEqual(len(self.transport.effects), count)
        manager.handle(self.effect(type_=0x05, params=()))
        manager.handle(self.effect(
            type_=0x26, params=(0xFF, 3, 0, 0, 0, 0, 0, 0, 21)))
        self.assertEqual(self.transport.effects[-1].mode,
                         forceadapt.MODE_RATTLE)

    def test_bounded_native_session_deadline_clears_on_late_output(self):
        gate = trigger_state.BoundedNativeGate(
            duration=4.0, max_cycles=3, session_duration=4.0,
            clock=lambda: self.now[0])
        manager = trigger_state.TriggerStateManager(
            transport=self.transport, clock=lambda: self.now[0],
            translator=trigger_translation.translate_semantic,
            effect_filter=gate)
        manager.handle(self.effect(
            type_=0x26, params=(0xFF, 3, 0, 0, 0, 0, 0, 0, 21)))
        self.now[0] += 4.01
        manager.handle(self.effect(
            type_=0x21, params=(0xFF, 3, 0x92, 0x24, 0x49, 0x12)))
        self.assertTrue(gate.expire(manager))
        self.assertEqual(self.transport.effects[-2:],
                         [forceadapt.normal("left"),
                          forceadapt.normal("right")])

    def test_ow2_safe_gate_rearms_without_a_cycle_limit(self):
        gate = trigger_state.Ow2SafeGate(clock=lambda: self.now[0])
        manager = trigger_state.TriggerStateManager(
            transport=self.transport, clock=lambda: self.now[0],
            translator=trigger_translation.translate_ow2_safe,
            effect_filter=gate)
        rattle = self.effect(
            type_=0x26, params=(0xFF, 3, 0, 0, 0, 0, 0, 0, 21))
        resistance = self.effect(
            type_=0x21, params=(0xFF, 3, 0x92, 0x24, 0x49, 0x12))
        off = self.effect(type_=0x05, params=())
        for _index in range(5):
            manager.handle(rattle)
            self.now[0] += 0.72
            manager.handle(resistance)
            self.now[0] += 0.5
            manager.handle(off)
            self.now[0] += 1.0
        self.assertEqual(
            [effect.mode for effect in self.transport.effects],
            [forceadapt.MODE_RATTLE, forceadapt.MODE_RESISTANCE,
             forceadapt.MODE_NORMAL] * 5)

    def test_ow2_safe_gate_requires_rattle_then_resistance_then_off(self):
        gate = trigger_state.Ow2SafeGate(clock=lambda: self.now[0])
        manager = trigger_state.TriggerStateManager(
            transport=self.transport, clock=lambda: self.now[0],
            translator=trigger_translation.translate_ow2_safe,
            effect_filter=gate)
        rattle = self.effect(
            type_=0x26, params=(0xFF, 3, 0, 0, 0, 0, 0, 0, 21))
        resistance = self.effect(
            type_=0x21, params=(0xFF, 3, 0x92, 0x24, 0x49, 0x12))
        off = self.effect(type_=0x05, params=())
        manager.handle(resistance)
        self.assertEqual(self.transport.effects, [])
        manager.handle(rattle)
        manager.handle(resistance)
        manager.handle(rattle)
        manager.handle(off)
        self.assertEqual(
            [effect.mode for effect in self.transport.effects],
            [forceadapt.MODE_RATTLE, forceadapt.MODE_RESISTANCE,
             forceadapt.MODE_NORMAL])

    def test_ow2_safe_gate_timeout_waits_for_off_before_rearming(self):
        gate = trigger_state.Ow2SafeGate(clock=lambda: self.now[0])
        manager = trigger_state.TriggerStateManager(
            transport=self.transport, clock=lambda: self.now[0],
            translator=trigger_translation.translate_ow2_safe,
            effect_filter=gate)
        rattle = self.effect(
            type_=0x26, params=(0xFF, 3, 0, 0, 0, 0, 0, 0, 21))
        manager.handle(rattle)
        self.now[0] += 4.01
        self.assertTrue(gate.expire(manager))
        count = len(self.transport.effects)
        manager.handle(rattle)
        self.assertEqual(len(self.transport.effects), count)
        manager.handle(self.effect(type_=0x05, params=()))
        manager.handle(rattle)
        self.assertEqual(self.transport.effects[-1].mode,
                         forceadapt.MODE_RATTLE)

    def test_ow2_safe_lifecycle_reset_starts_a_fresh_cycle(self):
        gate = trigger_state.Ow2SafeGate(clock=lambda: self.now[0])
        manager = trigger_state.TriggerStateManager(
            transport=self.transport, clock=lambda: self.now[0],
            translator=trigger_translation.translate_ow2_safe,
            effect_filter=gate)
        rattle = self.effect(
            type_=0x26, params=(0xFF, 3, 0, 0, 0, 0, 0, 0, 21))
        manager.handle(rattle)
        self.assertTrue(manager.reset_lifecycle("test UHID close"))
        manager.handle(rattle)
        self.assertEqual(
            [effect.mode for effect in self.transport.effects],
            [forceadapt.MODE_RATTLE, forceadapt.MODE_NORMAL,
             forceadapt.MODE_NORMAL, forceadapt.MODE_RATTLE])

    def test_ow2_safe_rearms_only_after_verified_transport_reattach(self):
        gate = trigger_state.Ow2SafeGate(clock=lambda: self.now[0])
        manager = trigger_state.TriggerStateManager(
            transport=self.transport, clock=lambda: self.now[0],
            translator=trigger_translation.translate_ow2_safe,
            effect_filter=gate)
        rattle = self.effect(
            type_=0x26, params=(0xFF, 3, 0, 0, 0, 0, 0, 0, 21))
        manager.handle(rattle)
        manager.detach("test vendor disconnect")
        replacement = FakeTransport()
        self.assertTrue(manager.attach(replacement))
        manager.handle(rattle)
        self.assertEqual(replacement.effects[-1].mode,
                         forceadapt.MODE_RATTLE)

    def test_bounded_dynamic_cli_allows_dry_run_but_refuses_live_mode_mix(self):
        allowed = subprocess.run(
            [sys.executable, str(ROOT / "apex4-ds5"),
             "--emulate", "dualsense", "--trigger-bounded-mild-right",
             "--trigger-dry-run", "--calib"],
            capture_output=True, text=True)
        self.assertEqual(allowed.returncode, 0, allowed.stderr)
        for conflict in ("--adaptive-triggers", "--trigger-one-shot-mild-right"):
            with self.subTest(conflict=conflict):
                result = subprocess.run(
                    [sys.executable, str(ROOT / "apex4-ds5"),
                     "--trigger-bounded-mild-right", conflict],
                    capture_output=True, text=True)
                self.assertEqual(result.returncode, 2)
                self.assertIn("cannot be combined", result.stderr)

    def test_bounded_native_cli_allows_dry_run_but_refuses_mode_mix(self):
        allowed = subprocess.run(
            [sys.executable, str(ROOT / "apex4-ds5"),
             "--emulate", "dualsense", "--trigger-bounded-native-right",
             "--trigger-dry-run", "--calib"],
            capture_output=True, text=True)
        self.assertEqual(allowed.returncode, 0, allowed.stderr)
        for conflict in ("--adaptive-triggers",
                         "--trigger-bounded-mild-right",
                         "--trigger-one-shot-mild-right"):
            with self.subTest(conflict=conflict):
                result = subprocess.run(
                    [sys.executable, str(ROOT / "apex4-ds5"),
                     "--trigger-bounded-native-right", conflict],
                    capture_output=True, text=True)
                self.assertEqual(result.returncode, 2)
                self.assertIn("cannot be combined", result.stderr)

    def test_bounded_native_session_cli_is_a_distinct_mode(self):
        allowed = subprocess.run(
            [sys.executable, str(ROOT / "apex4-ds5"),
             "--emulate", "dualsense",
             "--trigger-bounded-native-session-right",
             "--trigger-dry-run", "--calib"],
            capture_output=True, text=True)
        self.assertEqual(allowed.returncode, 0, allowed.stderr)
        for conflict in ("--adaptive-triggers",
                         "--trigger-bounded-native-right",
                         "--trigger-bounded-mild-right"):
            with self.subTest(conflict=conflict):
                result = subprocess.run(
                    [sys.executable, str(ROOT / "apex4-ds5"),
                     "--trigger-bounded-native-session-right", conflict],
                    capture_output=True, text=True)
                self.assertEqual(result.returncode, 2)
                self.assertIn("cannot be combined", result.stderr)

    def test_ow2_safe_cli_is_explicit_and_conflicts_with_other_modes(self):
        allowed = subprocess.run(
            [sys.executable, str(ROOT / "apex4-ds5"),
             "--emulate", "dualsense", "--trigger-ow2-safe-right",
             "--trigger-dry-run", "--calib"],
            capture_output=True, text=True)
        self.assertEqual(allowed.returncode, 0, allowed.stderr)
        for conflict in ("--adaptive-triggers",
                         "--trigger-bounded-native-right",
                         "--trigger-bounded-native-session-right"):
            with self.subTest(conflict=conflict):
                result = subprocess.run(
                    [sys.executable, str(ROOT / "apex4-ds5"),
                     "--trigger-ow2-safe-right", conflict],
                    capture_output=True, text=True)
                self.assertEqual(result.returncode, 2)
                self.assertIn("cannot be combined", result.stderr)

    def test_named_ow2_safe_profile_requires_plain_dualsense(self):
        rejected = subprocess.run(
            [sys.executable, str(ROOT / "apex4-ds5"),
             "--trigger-profile", "ow2-safe", "--calib"],
            capture_output=True, text=True)
        self.assertEqual(rejected.returncode, 2)
        self.assertIn("requires --emulate dualsense", rejected.stderr)
        for selector in (("--trigger-profile", "ow2-safe"),
                         ("--adaptive-triggers",)):
            with self.subTest(selector=selector):
                accepted = subprocess.run(
                    [sys.executable, str(ROOT / "apex4-ds5"),
                     "--emulate", "dualsense"] + list(selector)
                    + ["--calib"], capture_output=True, text=True)
                self.assertEqual(accepted.returncode, 0, accepted.stderr)

    def test_ow2_safe_quiet_overrides_verbose_and_refuses_debug_flags(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "config.json"
            path.write_text(json.dumps({"verbose": True}), encoding="utf-8")
            quiet = subprocess.run(
                [sys.executable, str(ROOT / "apex4-ds5"),
                 "--config", str(path), "--emulate", "dualsense",
                 "--trigger-ow2-safe-right", "--quiet-output", "--calib"],
                capture_output=True, text=True)
            self.assertEqual(quiet.returncode, 0, quiet.stderr)
            self.assertNotIn("settings      :", quiet.stdout)
            automatic = subprocess.run(
                [sys.executable, str(ROOT / "apex4-ds5"),
                 "--config", str(path), "--emulate", "dualsense",
                 "--trigger-profile", "ow2-safe", "--calib"],
                capture_output=True, text=True)
            self.assertEqual(automatic.returncode, 0, automatic.stderr)
            self.assertNotIn("settings      :", automatic.stdout)
        for conflict in ("--verbose", "--hid-debug", "--trigger-debug"):
            with self.subTest(conflict=conflict):
                result = subprocess.run(
                    [sys.executable, str(ROOT / "apex4-ds5"),
                     "--trigger-ow2-safe-right", "--quiet-output", conflict],
                    capture_output=True, text=True)
                self.assertEqual(result.returncode, 2)
                self.assertIn("cannot be combined", result.stderr)

    def test_one_shot_cli_refuses_modes_that_weaken_its_contract(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "apex4-ds5"),
             "--trigger-one-shot-mild-right", "--trigger-dry-run"],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("cannot be combined", result.stderr)


class IdentityProbeTests(unittest.TestCase):
    def test_silent_probe_retries_with_bounded_exponential_backoff(self):
        probe = trigger_identity.IdentityProbe(7, 10.0)
        self.assertTrue(probe.request_due(10.0))
        probe.mark_requested(10.0)
        self.assertFalse(probe.request_due(10.14))
        self.assertTrue(probe.request_due(10.15))

        message, retry_in = probe.timeout_result(12.0)
        self.assertIn("no valid command 0xEC identity reply", message)
        self.assertEqual(retry_in, 5.0)
        self.assertFalse(probe.resume_if_due(16.99))
        self.assertTrue(probe.resume_if_due(17.0))

        _message, retry_in = probe.timeout_result(19.0)
        self.assertEqual(retry_in, 10.0)
        self.assertTrue(probe.resume_if_due(29.0))
        _message, retry_in = probe.timeout_result(31.0)
        self.assertEqual(retry_in, 20.0)
        self.assertTrue(probe.resume_if_due(51.0))
        _message, retry_in = probe.timeout_result(53.0)
        self.assertEqual(retry_in, 30.0)

    def test_rejected_identity_is_terminal_for_that_generation(self):
        probe = trigger_identity.IdentityProbe(9, 1.0)
        probe.mark_rejected("unsupported DeviceType 85")
        message, retry_in = probe.timeout_result(3.0)
        self.assertEqual(message, "unsupported DeviceType 85")
        self.assertIsNone(retry_in)
        self.assertFalse(probe.resume_if_due(100.0))


class TransportGateTests(unittest.TestCase):
    def test_read_only_identity_request_is_exact_and_separate_from_allowlist(self):
        from apex4ds5 import legacy
        self.assertEqual(legacy.device_info_request(),
                         bytes([0x05, 0xEC] + [0] * 10))
        self.assertNotIn(legacy.CMD_GET_DEVICE_INFO,
                         forceadapt.ALLOWED_RUNTIME_COMMANDS)

    def test_identity_must_match_verified_apex4(self):
        writes = []
        identity = {"device_type": 84, "firmware": (0x68, 0x30),
                    "connection": "wired"}
        transport = forceadapt.VerifiedTransport.verify(
            9, "/dev/hidraw-test", node_checker=lambda _node: True,
            identity_reader=lambda _fd: identity,
            writer=lambda fd, packet: writes.append((fd, packet)) or len(packet))
        transport.write_effect(forceadapt.resistance("right", 60, 40))
        self.assertEqual(writes[0][1][0:3], bytes([0x05, 0xA0, 0x01]))

        with self.assertRaises(forceadapt.IdentityError):
            forceadapt.VerifiedTransport.verify(
                9, "/dev/hidraw-test", node_checker=lambda _node: True,
                identity_reader=lambda _fd: {"device_type": 85})
        with self.assertRaises(forceadapt.IdentityError):
            forceadapt.VerifiedTransport.verify(
                9, "/dev/hidraw-test", node_checker=lambda _node: False,
                identity_reader=lambda _fd: identity)

    def test_node_is_checked_before_the_read_only_identity_request(self):
        reads = []
        with self.assertRaises(forceadapt.IdentityError):
            forceadapt.VerifiedTransport.verify(
                9, "/dev/not-the-vendor-node",
                node_checker=lambda _node: False,
                identity_reader=lambda fd: reads.append(fd))
        self.assertEqual(reads, [])

    def test_transport_has_no_raw_command_passthrough(self):
        self.assertFalse(hasattr(forceadapt.VerifiedTransport, "write_raw"))
        self.assertEqual(forceadapt.ALLOWED_RUNTIME_COMMANDS, frozenset({0xA0}))


if __name__ == "__main__":
    unittest.main()
