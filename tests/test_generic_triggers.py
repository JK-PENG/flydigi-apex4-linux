# SPDX-License-Identifier: MIT
"""Contract tests for the opt-in, game-independent trigger policy."""
import unittest

from apex4ds5 import forceadapt, trigger_state
from apex4ds5._ds5 import ds5

try:
    from apex4ds5.generic_trigger import GenericSafeTranslator
except ImportError:
    GenericSafeTranslator = None


def effect(side, type_, params=()):
    return ds5.TriggerEffect(
        side, type_, bytes(list(params) + [0] * (10 - len(params))))


class GenericTranslationTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(GenericSafeTranslator,
                             "generic-safe translator has not been implemented")
        self.mapper = GenericSafeTranslator()

    def test_off_clears_only_the_reported_side(self):
        for side in ("left", "right"):
            with self.subTest(side=side):
                self.assertEqual(self.mapper(effect(side, 0x05)),
                                 forceadapt.normal(side))

    def test_simple_and_zone_resistance_are_symmetric_and_capped(self):
        for side in ("left", "right"):
            with self.subTest(side=side):
                self.assertEqual(self.mapper(effect(side, 0x01, [60, 200])),
                                 forceadapt.resistance(side, 60, 40))
                self.assertEqual(self.mapper(effect(
                    side, 0x21, bytes.fromhex("ff039224491200000000"))),
                    forceadapt.resistance(side, 0, 40))

    def test_simple_and_zone_vibration_are_symmetric_and_capped(self):
        for side in ("left", "right"):
            with self.subTest(side=side):
                self.assertEqual(self.mapper(effect(side, 0x06, [99, 200, 30])),
                                 forceadapt.rattle(side, 30, 1, 32, 21))
                self.assertEqual(self.mapper(effect(
                    side, 0x26, bytes.fromhex("ff030000000000001500"))),
                    forceadapt.rattle(side, 0, 1, 32, 21))

    def test_breakpoint_is_a_candidate_but_not_released(self):
        for side in ("left", "right"):
            with self.subTest(side=side):
                raw = effect(side, 0x02, [20, 90, 100])
                self.assertIsNone(self.mapper(raw))
                candidate = GenericSafeTranslator(
                    enabled_modes=frozenset({0, 1, 2, 3}))(raw)
                self.assertEqual(candidate,
                                 forceadapt.breakpoint(side, 60, 20, 20))

    def test_unknown_invalid_empty_and_zero_effects_fail_closed(self):
        cases = (
            effect("right", 0x00),
            effect("right", 0xEE),
            effect("left", 0x11, [60, 40]),
            effect("left", 0x21),
            effect("right", 0x26, [0xFF, 0xFC, 0, 0, 0, 0, 0, 0, 21]),
            effect("left", 0x01, [60, 0]),
            effect("right", 0x06, [0, 40, 20]),
            effect("right", 0x06, [20, 0, 20]),
            effect("right", 0x02, [60, 0, 20]),
        )
        for raw in cases:
            with self.subTest(raw=raw):
                self.assertIsNone(self.mapper(raw))

    def test_galloping_and_machine_require_separate_semantic_acceptance(self):
        mapper = GenericSafeTranslator(enabled_modes=frozenset({0, 1, 2, 3}))
        for type_, params in ((0x23, [0x24, 0, 0x0B, 7]),
                              (0x27, [0x24, 0, 0x3F, 9, 3])):
            with self.subTest(type_=type_):
                self.assertIsNone(mapper(effect("right", type_, params)))


class RecordingTransport:
    def __init__(self, fail=False):
        self.effects = []
        self.fail = fail

    def write_effect(self, mapped):
        if self.fail:
            raise OSError("injected write failure")
        self.effects.append(mapped)
        return forceadapt.build_packet(mapped)


class GenericGateTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(hasattr(trigger_state, "GenericSafeGate"),
                        "generic-safe lifecycle gate has not been implemented")
        self.now = [10.0]
        self.clock = lambda: self.now[0]
        self.gate = trigger_state.GenericSafeGate(clock=self.clock)
        self.transport = RecordingTransport()
        self.logs = []
        self.manager = trigger_state.TriggerStateManager(
            transport=self.transport, clock=self.clock, reset_timeout=0,
            logger=self.logs.append, effect_filter=self.gate,
            translator=GenericSafeTranslator())

    def test_timeout_clears_only_due_side_and_off_rearms_it(self):
        self.manager.handle(effect(
            "right", 0x26, bytes.fromhex("ff030000000000001500")))
        self.now[0] += 1.0
        self.manager.handle(effect("left", 0x01, [60, 40]))
        self.now[0] += 3.1
        self.assertTrue(self.gate.expire(self.manager))
        self.assertEqual(self.manager.last["right"], forceadapt.normal("right"))
        self.assertEqual(self.manager.last["left"],
                         forceadapt.resistance("left", 60, 40))
        count = len(self.transport.effects)
        self.manager.handle(effect("right", 0x01, [60, 40]))
        self.assertEqual(len(self.transport.effects), count)
        self.manager.handle(effect("right", 0x05))
        self.manager.handle(effect("right", 0x01, [60, 40]))
        self.assertEqual(self.transport.effects[-1],
                         forceadapt.resistance("right", 60, 40))

    def test_mode_changes_and_repeats_never_extend_deadline(self):
        self.manager.handle(effect("right", 0x01, [60, 40]))
        first_deadline = self.gate.deadline["right"]
        self.now[0] += 1.0
        self.manager.handle(effect("right", 0x01, [61, 40]))
        self.assertEqual(self.gate.deadline["right"], first_deadline)
        self.manager.handle(effect("right", 0x06, [21, 32, 10]))
        self.assertEqual(self.gate.deadline["right"], 15.0)
        self.now[0] += 1.0
        self.manager.handle(effect("right", 0x01, [62, 40]))
        self.assertEqual(self.gate.deadline["right"], 15.0)
        self.now[0] = 15.1
        self.assertTrue(self.gate.expire(self.manager))

    def test_mode_one_has_finite_fifteen_second_cap(self):
        self.manager.handle(effect("left", 0x01, [60, 40]))
        self.now[0] = 24.9
        self.assertIsNone(self.gate.expire(self.manager))
        self.now[0] = 25.0
        self.assertTrue(self.gate.expire(self.manager))
        self.assertEqual(self.transport.effects[-1], forceadapt.normal("left"))

    def test_unknown_and_opposite_side_do_not_rearm_a_timed_out_side(self):
        self.manager.handle(effect("right", 0x06, [21, 32, 10]))
        self.now[0] = 14.1
        self.assertTrue(self.gate.expire(self.manager))
        count = len(self.transport.effects)
        self.manager.handle(effect("right", 0xEE))
        self.manager.handle(effect("left", 0x01, [60, 40]))
        self.manager.handle(effect("right", 0x06, [21, 32, 10]))
        self.assertEqual(len(self.transport.effects), count + 1)

    def test_failed_clear_aborts_until_verified_attach_succeeds(self):
        self.manager.handle(effect("right", 0x01, [60, 40]))
        self.transport.fail = True
        self.assertFalse(self.manager.reset_lifecycle("test close"))
        self.assertTrue(self.gate.waiting_off["right"])
        self.manager.detach("failed clear")
        self.assertFalse(self.manager.attach(RecordingTransport(fail=True)))
        self.assertTrue(self.gate.waiting_off["right"])
        fresh = RecordingTransport()
        self.assertTrue(self.manager.attach(fresh))
        self.assertEqual(fresh.effects,
                         [forceadapt.normal("left"), forceadapt.normal("right")])
        self.assertFalse(self.gate.waiting_off["right"])
        self.manager.handle(effect("right", 0x01, [60, 40]))
        self.assertEqual(fresh.effects[-1],
                         forceadapt.resistance("right", 60, 40))

    def test_failed_side_timeout_latches_both_sides_off(self):
        self.manager.handle(effect("right", 0x06, [21, 32, 10]))
        self.now[0] += 1.0
        self.manager.handle(effect("left", 0x01, [60, 40]))
        self.transport.fail = True
        self.now[0] = 14.1
        self.assertFalse(self.gate.expire(self.manager))
        self.assertTrue(self.gate.waiting_off["left"])
        self.assertTrue(self.gate.waiting_off["right"])
        self.assertIsNone(self.gate.deadline["left"])
        self.assertIsNone(self.gate.deadline["right"])
        self.assertFalse(self.manager.handle(effect("left", 0x01, [61, 40])))


if __name__ == "__main__":
    unittest.main()
