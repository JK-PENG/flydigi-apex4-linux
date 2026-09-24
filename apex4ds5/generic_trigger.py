# SPDX-License-Identifier: MIT
"""Game-independent, bounded DualSense to APEX 4 trigger decisions.

This module only constructs typed effects. Physical writes remain behind the
verified transport and the relay's per-side lifecycle gate.
"""
from . import forceadapt, trigger_translation


# Breakpoint and rhythmic approximations need separate physical acceptance.
GENERIC_RELEASE_MODES = frozenset({
    forceadapt.MODE_NORMAL,
    forceadapt.MODE_RESISTANCE,
    forceadapt.MODE_RATTLE,
})


class GenericSafeTranslator:
    def __init__(self, enabled_modes=None):
        self.enabled_modes = frozenset(
            GENERIC_RELEASE_MODES if enabled_modes is None else enabled_modes)

    def __call__(self, raw_effect, left_motor=0):
        normalized = trigger_translation.parse(raw_effect)
        if normalized is None or normalized.kind in (
                "noop", "unsupported", "invalid", "galloping", "machine"):
            return None
        candidate = trigger_translation.translate_semantic(
            raw_effect, left_motor)
        if candidate is None or candidate.mode not in self.enabled_modes:
            return None
        side = candidate.side
        if candidate.mode == forceadapt.MODE_NORMAL:
            return forceadapt.normal(side)
        if not normalized.strength:
            return None
        if candidate.mode == forceadapt.MODE_RESISTANCE:
            return forceadapt.resistance(
                side, candidate.params[0], min(40, candidate.params[1]))
        if candidate.mode == forceadapt.MODE_RATTLE:
            if not normalized.frequency:
                return None
            return forceadapt.rattle(
                side, candidate.params[0], 1,
                min(32, candidate.params[2]),
                min(21, candidate.params[3]))
        if candidate.mode == forceadapt.MODE_BREAKPOINT:
            if normalized.kind == "breakpoint" and not normalized.end_zone:
                return None
            return forceadapt.breakpoint(
                side, max(60, candidate.params[0]),
                min(20, candidate.params[1]),
                min(20, candidate.params[2]))
        return None
