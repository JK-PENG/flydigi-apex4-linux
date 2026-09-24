# SPDX-License-Identifier: MIT
"""Safe Flydigi APEX 4 (k2) ForceAdapt runtime protocol.

The legacy/DInput controller accepts one confirmed live-effect command on its
0xFFA0 vendor collection.  This module intentionally exposes typed effects,
not a raw command escape hatch: command 0xA0 is the complete write allowlist.
"""
from dataclasses import dataclass
import os


CMD_REPORT_ID = 0x05
CMD_SET_FORCE_TRIGGER_DINPUT = 0xA0
FORCE_TRIGGER_EFFECT_FAMILY = 0x01
PACKET_SIZE = 15
ALLOWED_RUNTIME_COMMANDS = frozenset({CMD_SET_FORCE_TRIGGER_DINPUT})

SIDE_LEFT = 1
SIDE_RIGHT = 2
SIDE_IDS = {"left": SIDE_LEFT, "right": SIDE_RIGHT}

MODE_NORMAL = 0
MODE_RESISTANCE = 1
MODE_RATTLE = 2
MODE_BREAKPOINT = 3
MODE_LOCK = 4
MODE_VIBRATION = 5
# Modes 4/5 exist in external vocabularies but have no project hardware
# acceptance. Keep the runtime writer limited to the confirmed 0..3 set.
ALLOWED_MODES = frozenset({MODE_NORMAL, MODE_RESISTANCE,
                           MODE_RATTLE, MODE_BREAKPOINT})

# These two retail variants have public, physical ForceAdapt validation.  Other
# k2 entries in Flydigi's model table stay refused until equivalent evidence is
# available; sharing VID/PID alone is deliberately not enough.
SUPPORTED_DEVICE_TYPES = frozenset({84, 103})
SUPPORTED_CONNECTIONS = frozenset({"dongle", "wired"})


class IdentityError(RuntimeError):
    """The selected HID node was not proven safe for ForceAdapt writes."""


def _byte(value):
    return max(0, min(255, int(value)))


@dataclass(frozen=True)
class ForceAdaptEffect:
    """One side-specific, typed ForceAdapt effect with five wire parameters."""

    side: str
    mode: int
    params: tuple = (0, 0, 0, 0, 0)

    def __post_init__(self):
        if self.side not in SIDE_IDS:
            raise ValueError("ForceAdapt side must be left or right")
        mode = int(self.mode)
        if mode not in ALLOWED_MODES:
            raise ValueError("ForceAdapt mode is outside the runtime allowlist")
        if len(self.params) != 5:
            raise ValueError("ForceAdapt effects need exactly five parameters")
        params = tuple(_byte(value) for value in self.params)
        if mode == MODE_NORMAL:
            params = (0, 0, 0, 0, 0)
        object.__setattr__(self, "mode", mode)
        object.__setattr__(self, "params", params)

    def key(self):
        return self.side, self.mode, self.params


def normal(side):
    return ForceAdaptEffect(side, MODE_NORMAL)


def resistance(side, start, strength, match_input=False):
    return ForceAdaptEffect(
        side, MODE_RESISTANCE,
        (_byte(start), max(1, _byte(strength)), 1 if match_input else 0, 0, 0))


def breakpoint(side, start, travel, strength, match_input=False):
    return ForceAdaptEffect(
        side, MODE_BREAKPOINT,
        (_byte(start), max(1, _byte(travel)), max(1, _byte(strength)),
         0, 1 if match_input else 0))


def rattle(side, start, pressure, strength, frequency, match_input=False):
    return ForceAdaptEffect(
        side, MODE_RATTLE,
        (_byte(start), max(1, _byte(pressure)), max(1, _byte(strength)),
         max(1, _byte(frequency)), 1 if match_input else 0))


def build_packet(effect, apply=True):
    """Build the confirmed 15-byte k2 DInput ForceAdapt report."""
    if not isinstance(effect, ForceAdaptEffect):
        raise TypeError("build_packet accepts ForceAdaptEffect only")
    params = list(effect.params)
    # Flydigi's live builder clears match-input when resistance begins at zero.
    if effect.mode == MODE_RESISTANCE and params[0] == 0 and params[2] == 1:
        params[2] = 0
    packet = bytes([
        CMD_REPORT_ID,
        CMD_SET_FORCE_TRIGGER_DINPUT,
        FORCE_TRIGGER_EFFECT_FAMILY,
        1 if apply else 0,
        SIDE_IDS[effect.side],
        effect.mode,
    ] + params + [0] * 4)
    if len(packet) != PACKET_SIZE:
        raise AssertionError("invalid ForceAdapt packet size")
    return packet


def _validate_packet(packet):
    """Last-line write guard, independent of the typed builder."""
    return (len(packet) == PACKET_SIZE
            and packet[0] == CMD_REPORT_ID
            and packet[1] in ALLOWED_RUNTIME_COMMANDS
            and packet[2] == FORCE_TRIGGER_EFFECT_FAMILY
            and packet[3] in (0, 1)
            and packet[4] in (SIDE_LEFT, SIDE_RIGHT)
            and packet[5] in ALLOWED_MODES
            and packet[11:15] == bytes(4))


def identity_description(info):
    firmware = info.get("firmware") or (0, 0)
    return ("APEX 4 DeviceType %s, firmware %02x%02x, %s"
            % (info.get("device_type", "?"), firmware[0], firmware[1],
               info.get("connection", "unknown")))


class VerifiedTransport:
    """A write-only capability created after node and identity verification."""

    def __init__(self, fd, node, identity, writer=os.write):
        self.fd = fd
        self.node = node
        self.identity = dict(identity)
        self._writer = writer

    @classmethod
    def accept_identity(cls, fd, node, info, node_checker=None, writer=os.write):
        """Validate an identity reply already received by an event loop."""
        from . import legacy
        node_checker = node_checker or legacy.is_vendor_node
        if not node or not node_checker(node):
            raise IdentityError(
                "ForceAdapt refused: node is not 04b4:2412 usage-page 0xFFA0")
        if not isinstance(info, dict):
            raise IdentityError("ForceAdapt refused: no valid command 0xEC identity reply")
        if info.get("device_type") not in SUPPORTED_DEVICE_TYPES:
            raise IdentityError(
                "ForceAdapt refused: unsupported DeviceType %r"
                % info.get("device_type"))
        if info.get("connection") not in SUPPORTED_CONNECTIONS:
            raise IdentityError(
                "ForceAdapt refused: unsupported connection %r"
                % info.get("connection"))
        firmware = info.get("firmware")
        if not (isinstance(firmware, tuple) and len(firmware) == 2
                and all(isinstance(value, int) for value in firmware)):
            raise IdentityError("ForceAdapt refused: firmware identity is missing")
        return cls(fd, node, info, writer=writer)

    @classmethod
    def verify(cls, fd, node, node_checker=None, identity_reader=None,
               writer=os.write):
        """Blocking verifier for bounded tools; the relay uses accept_identity."""
        from . import legacy
        node_checker = node_checker or legacy.is_vendor_node
        if not node or not node_checker(node):
            raise IdentityError(
                "ForceAdapt refused: node is not 04b4:2412 usage-page 0xFFA0")
        identity_reader = identity_reader or legacy.read_device_info_fd
        try:
            info = identity_reader(fd)
        except (OSError, ValueError) as exc:
            raise IdentityError("ForceAdapt refused: identity read failed: %s" % exc) from exc
        return cls.accept_identity(fd, node, info, node_checker=lambda _node: True,
                                   writer=writer)

    def write_effect(self, effect):
        packet = build_packet(effect)
        if not _validate_packet(packet):
            raise ValueError("ForceAdapt packet failed the runtime command allowlist")
        written = self._writer(self.fd, packet)
        if written != len(packet):
            raise OSError("short ForceAdapt write (%d/%d)" % (written, len(packet)))
        return packet
