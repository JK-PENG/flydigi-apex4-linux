# SPDX-FileCopyrightText: 2026 Mikalai Kaliaha
# SPDX-License-Identifier: MIT
"""DualSense adaptive-trigger parsing and APEX 4 effect translation.

The game-specific mappings for effect types 1/2/5/6/0x21/0x25/0x26 are adapted
from openflydigi's MIT-licensed relay at commit 8477300.  Bow, Galloping and
Machine have no exact Flydigi vocabulary equivalent and use conservative,
documented approximations built only from confirmed ForceAdapt modes.
"""
from dataclasses import dataclass

from . import forceadapt


TYPE_NOOP = 0x00
TYPE_SIMPLE_FEEDBACK = 0x01
TYPE_SIMPLE_WEAPON = 0x02
TYPE_OFF = 0x05
TYPE_SIMPLE_VIBRATION = 0x06
TYPE_LIMITED_FEEDBACK = 0x11
TYPE_LIMITED_WEAPON = 0x12
TYPE_FEEDBACK = 0x21
TYPE_BOW = 0x22
TYPE_GALLOPING = 0x23
TYPE_WEAPON = 0x25
TYPE_VIBRATION = 0x26
TYPE_MACHINE = 0x27

OW2_R2_VIBRATION_PARAMS = tuple(bytes.fromhex("ff030000000000001500"))
OW2_R2_FEEDBACK_PARAMS = tuple(bytes.fromhex("ff039224491200000000"))


@dataclass(frozen=True)
class NormalizedTriggerEffect:
    side: str
    kind: str
    raw_type: int
    raw_params: tuple
    start_zone: int = None
    end_zone: int = None
    strength: int = 0
    frequency: int = 0
    detail: str = ""

    def describe(self):
        fields = [self.kind, "type=0x%02X" % self.raw_type]
        if self.start_zone is not None:
            fields.append("start=%s" % self.start_zone)
        if self.end_zone is not None:
            fields.append("end=%s" % self.end_zone)
        if self.strength:
            fields.append("strength=%s" % self.strength)
        if self.frequency:
            fields.append("frequency=%s" % self.frequency)
        if self.detail:
            fields.append(self.detail)
        return " ".join(fields)


def _valid_zone_pair(params, min_start, max_start, max_end):
    mask = params[0] | (params[1] << 8)
    zones = [zone for zone in range(10) if mask & (1 << zone)]
    if (len(zones) != 2 or not min_start <= zones[0] <= max_start
            or not zones[0] < zones[1] <= max_end):
        return None
    return zones[0], zones[1]


def _zone_strengths(params):
    active = params[0] | (params[1] << 8)
    packed = sum(params[2 + index] << (8 * index) for index in range(4))
    return tuple((((packed >> (3 * zone)) & 7) + 1)
                 if active & (1 << zone) else 0 for zone in range(10))


def _strength_byte(level):
    return max(0, min(255, round(int(level) * 255 / 8)))


def parse(effect):
    """Return a semantic effect, or None for a malformed block."""
    if getattr(effect, "side", None) not in ("left", "right"):
        return None
    params = bytes(getattr(effect, "params", b""))
    if len(params) != 10:
        return None
    side, type_ = effect.side, int(effect.type) & 0xFF
    p = tuple(params)

    if type_ == TYPE_NOOP:
        return NormalizedTriggerEffect(side, "noop", type_, p)
    if type_ == TYPE_OFF:
        return NormalizedTriggerEffect(side, "normal", type_, p)
    if type_ == TYPE_SIMPLE_FEEDBACK:
        return NormalizedTriggerEffect(side, "resistance", type_, p,
                                       p[0], None, p[1])
    if type_ == TYPE_SIMPLE_WEAPON:
        return NormalizedTriggerEffect(side, "breakpoint", type_, p,
                                       p[0], p[1], p[2])
    if type_ in (TYPE_LIMITED_FEEDBACK, TYPE_LIMITED_WEAPON):
        return NormalizedTriggerEffect(
            side, "unsupported", type_, p,
            detail="limited effect has no confirmed ForceAdapt mapping")
    if type_ == TYPE_SIMPLE_VIBRATION:
        return NormalizedTriggerEffect(side, "vibration", type_, p,
                                       p[2], None, p[1], p[0])
    if type_ in (TYPE_FEEDBACK, TYPE_VIBRATION):
        if (p[0] | (p[1] << 8)) & ~0x03FF:
            return NormalizedTriggerEffect(
                side, "invalid", type_, p, detail="active zones outside 0..9")
        strengths = _zone_strengths(p)
        active = [zone for zone, value in enumerate(strengths) if value]
        start = active[0] if active else None
        end = active[-1] if active else None
        strength = _strength_byte(max(strengths) if active else 0)
        return NormalizedTriggerEffect(
            side, "resistance" if type_ == TYPE_FEEDBACK else "vibration",
            type_, p, start, end, strength, p[8] if type_ == TYPE_VIBRATION else 0,
            "zones=%s" % (",".join(map(str, strengths))))
    if type_ in (TYPE_WEAPON, TYPE_BOW):
        limits = (2, 7, 8) if type_ == TYPE_WEAPON else (1, 8, 8)
        pair = _valid_zone_pair(p, *limits)
        if pair is None:
            return NormalizedTriggerEffect(
                side, "invalid", type_, p, detail="invalid zone pair")
        start, end = pair
        strength = _strength_byte((p[2] & 7) + 1)
        if type_ == TYPE_BOW:
            snap = _strength_byte(((p[2] >> 3) & 7) + 1)
            strength = max(strength, snap)
        return NormalizedTriggerEffect(
            side, "breakpoint" if type_ == TYPE_WEAPON else "bow",
            type_, p, start, end, strength)
    if type_ == TYPE_GALLOPING:
        pair = _valid_zone_pair(p, 0, 8, 9)
        first_foot, second_foot = (p[2] >> 3) & 7, p[2] & 7
        if (pair is None or first_foot > 6 or second_foot <= first_foot
                or p[3] == 0):
            return NormalizedTriggerEffect(
                side, "invalid", type_, p, detail="invalid galloping parameters")
        start, end = pair
        return NormalizedTriggerEffect(side, "galloping", type_, p, start, end,
                                       96, p[3],
                                       "feet=%d,%d" % (first_foot, second_foot))
    if type_ == TYPE_MACHINE:
        pair = _valid_zone_pair(p, 1, 8, 9)
        if pair is None or p[3] == 0:
            return NormalizedTriggerEffect(
                side, "invalid", type_, p, detail="invalid machine parameters")
        start, end = pair
        amplitude = max(p[2] & 7, (p[2] >> 3) & 7)
        return NormalizedTriggerEffect(side, "machine", type_, p, start, end,
                                       _strength_byte(amplitude), p[3],
                                       "period=%d" % p[4])
    return NormalizedTriggerEffect(side, "unsupported", type_, p)


def _effect(side, mode, values=()):
    values = list(values[:5]) + [0] * (5 - len(values[:5]))
    return forceadapt.ForceAdaptEffect(side, mode, tuple(values))


def _zone_to_byte(zone):
    return 0 if zone is None else round(max(0, min(9, zone)) * 255 / 9)


def translate(effect, left_motor=0):
    """Translate a raw DualSense effect into a typed ForceAdapt effect.

    Unknown, malformed, no-op, and unsafe debug types return None.  None means
    leave the physical trigger unchanged, never guess a vendor command.
    """
    normalized = parse(effect)
    if (normalized is None
            or normalized.kind in ("noop", "unsupported", "invalid")):
        return None
    side, type_, p = normalized.side, normalized.raw_type, normalized.raw_params

    # Exact mappings from openflydigi's MIT PS5DataManager transcription.
    if type_ == TYPE_SIMPLE_FEEDBACK:
        return _effect(side, forceadapt.MODE_RESISTANCE, (p[0], p[1]))
    if type_ == TYPE_SIMPLE_WEAPON:
        return _effect(side, forceadapt.MODE_BREAKPOINT, (p[0], p[1], p[2]))
    if type_ == TYPE_OFF:
        return forceadapt.normal(side)
    if type_ == TYPE_SIMPLE_VIBRATION:
        return _effect(side, forceadapt.MODE_RATTLE, (p[2], p[1], p[1], p[0]))

    if side == "right":
        if type_ == TYPE_FEEDBACK:
            if p[0] == 0xFF and p[1] == 3 and p[2] == 0xFF:
                return _effect(side, forceadapt.MODE_RESISTANCE, (110, 50, 0))
            if p[0] == 0:
                return _effect(side, forceadapt.MODE_RESISTANCE, (120, 1))
            if p[0] == 0xFF and p[1] == 3:
                return _effect(side, forceadapt.MODE_RESISTANCE, (1, 64))
            return _effect(side, forceadapt.MODE_RESISTANCE, (1, 1))
        if type_ == TYPE_WEAPON:
            if p[0] == 20:
                if p[2] == 2:
                    return _effect(side, forceadapt.MODE_BREAKPOINT, (70, 20, 20, 0))
                if p[2] == 6:
                    return _effect(side, forceadapt.MODE_BREAKPOINT, (70, 60, 20, 0))
                if p[2] == 1:
                    return _effect(side, forceadapt.MODE_BREAKPOINT, (20, 10, 20, 0))
                if p[2] == 3:
                    return _effect(side, forceadapt.MODE_BREAKPOINT, (50, 30, 1, 0, 1))
                return _effect(side, forceadapt.MODE_RATTLE, (50, 1, 10, 10, 10))
            if p[0] == 12:
                return _effect(side, forceadapt.MODE_BREAKPOINT, (70, 0, 12, 0))
            if p[0] == 36 and p[2] <= 6:
                return _effect(side, forceadapt.MODE_BREAKPOINT,
                               (10, 36, 10 + p[2] * 10, 0))
            if p[0] == 68:
                return _effect(side, forceadapt.MODE_BREAKPOINT, (70, 50, 68, 0))
            if p[0] == 4 and p[1] == 1 and p[2] in (5, 7):
                return _effect(side, forceadapt.MODE_BREAKPOINT, (80, 200, 90, 0))
            if p[0] == 64 and p[1] == 1 and p[2] == 3:
                return _effect(side, forceadapt.MODE_BREAKPOINT, (120, 150, 60, 0))
            return _effect(side, forceadapt.MODE_BREAKPOINT,
                           (64, p[0], 0, p[2], 1))
        if type_ == TYPE_VIBRATION:
            return _effect(side, forceadapt.MODE_RATTLE,
                           (255 - p[0], 1, ((p[1] + 1) * 30) & 0xFF, p[8]))
    else:
        if type_ == TYPE_FEEDBACK:
            if p[0] == 0:
                out = [120, 1, 0, 0, 0]
            elif p[0] == 252 or (p[0] == 192 and p[1] == 3):
                out = [1, 96, 0, 0, 0]
            else:
                out = [0, 1, 0, 0, 0]
            if p[1] == 3:
                out[0], out[1] = 140, (p[5] + 1) & 0xFF
            if p[0] == 128:
                out[0], out[1] = 128, p[4]
            return _effect(side, forceadapt.MODE_RESISTANCE, out)
        if type_ == TYPE_WEAPON:
            return _effect(side, forceadapt.MODE_BREAKPOINT,
                           (64, p[0], 0, p[2], 1))
        if type_ == TYPE_VIBRATION:
            if p[0] == 240 and p[1] == 3 and p[3] == 0:
                return _effect(side, forceadapt.MODE_RESISTANCE,
                               (30, max(0, min(255, int(left_motor)))))
            if p[0] == 0xFF and p[1] == 3 and p[3] == 0xFF:
                return None
            strength = (((p[1] + 1) * 30) & 0xFF) if p[2] == 0 \
                else max(p[2], p[3], p[4], p[5])
            return _effect(side, forceadapt.MODE_RATTLE,
                           (255 - p[0], 1, strength, p[8]))

    # Known firmware effects without a one-to-one Flydigi equivalent.  These
    # approximations retain the active travel region and dominant intensity.
    if type_ == TYPE_BOW:
        start = _zone_to_byte(normalized.start_zone)
        end = _zone_to_byte(normalized.end_zone)
        return _effect(side, forceadapt.MODE_BREAKPOINT,
                       (start, max(1, end - start), max(1, normalized.strength)))
    if type_ in (TYPE_GALLOPING, TYPE_MACHINE):
        return _effect(side, forceadapt.MODE_RATTLE,
                       (_zone_to_byte(normalized.start_zone),
                        max(1, normalized.strength), max(1, normalized.strength),
                        max(1, normalized.frequency)))
    return None


def translate_semantic(effect, left_motor=0):
    """Map decoded semantics without Flydigi's game-pattern special cases.

    This is an experimental comparison profile.  It is intentionally separate
    from ``translate`` until real-game capture and hardware evidence decide
    which compatibility exceptions are useful.
    """
    normalized = parse(effect)
    if (normalized is None
            or normalized.kind in ("noop", "unsupported", "invalid")):
        return None
    side, type_, p = normalized.side, normalized.raw_type, normalized.raw_params
    if type_ == TYPE_OFF:
        return forceadapt.normal(side)
    if type_ == TYPE_SIMPLE_FEEDBACK:
        return forceadapt.resistance(side, p[0], p[1])
    if type_ == TYPE_SIMPLE_WEAPON:
        return forceadapt.breakpoint(side, p[0], p[1], p[2])
    if type_ == TYPE_SIMPLE_VIBRATION:
        return forceadapt.rattle(side, p[2], 1, p[1], p[0])
    if type_ == TYPE_FEEDBACK:
        if normalized.start_zone is None or not normalized.strength:
            return None
        return forceadapt.resistance(
            side, _zone_to_byte(normalized.start_zone), normalized.strength)
    if type_ == TYPE_VIBRATION:
        if (normalized.start_zone is None or not normalized.strength
                or not normalized.frequency):
            return None
        return forceadapt.rattle(
            side, _zone_to_byte(normalized.start_zone), 1,
            normalized.strength, normalized.frequency)
    if type_ in (TYPE_WEAPON, TYPE_BOW):
        if normalized.start_zone is None or normalized.end_zone is None:
            return None
        start = _zone_to_byte(normalized.start_zone)
        end = _zone_to_byte(normalized.end_zone)
        return forceadapt.breakpoint(
            side, start, max(1, end - start), max(1, normalized.strength))
    if type_ in (TYPE_GALLOPING, TYPE_MACHINE):
        if normalized.start_zone is None:
            return None
        return forceadapt.rattle(
            side, _zone_to_byte(normalized.start_zone), 1,
            max(1, normalized.strength), max(1, normalized.frequency))
    return None


def translate_ow2_safe(effect, left_motor=0):
    """Translate only the physically accepted OW2/Hanzo R2 effect patterns."""
    normalized = parse(effect)
    if normalized is None or normalized.side != "right":
        return None
    if normalized.raw_type == TYPE_OFF:
        return forceadapt.normal("right")
    if (normalized.raw_type == TYPE_VIBRATION
            and normalized.raw_params == OW2_R2_VIBRATION_PARAMS):
        return translate_semantic(effect, left_motor)
    if (normalized.raw_type == TYPE_FEEDBACK
            and normalized.raw_params == OW2_R2_FEEDBACK_PARAMS):
        return translate_semantic(effect, left_motor)
    return None
