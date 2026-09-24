# SPDX-License-Identifier: MIT
"""Settings file, so that nobody has to edit code to move a paddle.

JSON rather than TOML on purpose: `tomllib` only arrived in Python 3.11, and this
has to run on whatever a Steam Deck or an LTS distribution ships. The whole
project has no dependencies and that is worth keeping -- on an immutable system a
`pip install` line in the instructions costs somebody an evening.

Precedence is defaults < config file < command-line flags, so a flag can always
be used to try something out without touching the file.
"""
import json
import os

APP = "flydigi-apex4"
TRIGGER_PROFILES = ("disabled", "ow2-safe", "generic-safe")
DEFAULTS = {
    # Which controller to present: "dualsense" or "dualsense-edge". The Edge has
    # four extra buttons of its own, so paddles can map to real buttons there
    # instead of being folded into touchpad halves and stick clicks.
    "emulate": "dualsense-edge",
    # What the four back paddles do, indexed by the pad's own M1..M4 labels.
    # Any pad: tp-left, tp-right, l3, r3, none
    # Edge only: paddle-left, paddle-right, fn1, fn2
    #
    # The labels are NOT in left-to-right order, which this list used to assume.
    # On an APEX 4 the four sit, in the player's left-to-right order, as
    # M2 (outer, left grip), M4, [power switch], M3, M1 (outer, right grip) --
    # so M1+M2 are the two grip buttons and M3+M4 the two beside the switch.
    # The pad's own markings show M1 M3 [switch] M4 M2, because they are read
    # with the pad turned over, and turning it over swaps left and right; the
    # player-facing order above is the reverse of that. Measured one button at
    # a time on a retail pad and checked against Steam's front-facing test page
    # (a "back view" reading gives a mirrored result); see docs/VALIDATION.md.
    # This list therefore lands each button on the Edge input in the same place.
    "paddles": ["paddle-right", "paddle-left", "fn2", "fn1"],
    # Vendor report bits for M1..M4. Older measured pads use 3,5,4,2; at least
    # one newer firmware/profile reports the labelled buttons as 2,3,4,5.
    "paddle_bits": [3, 5, 4, 2],
    # Pad axes -> DualSense axes. A leading minus inverts that axis.
    "gyro_map": "pitch,yaw,roll",
    "accel_map": "-x,z,y",
    # DualSense input report rate, Hz.
    "rate_hz": 250,
    # Seconds the pad may be absent before the virtual controller is taken away
    # too. A pad that naps leaves the USB bus and comes back, and a game holding
    # the controller should not lose it over that -- but a pad switched off for
    # good should not leave a phantom in Steam either. 0 keeps it forever.
    "drop_after_s": 30,
    # Log every output report from the game, and every rumble level sent on.
    "verbose": False,
    # Physical trigger output is off unless an explicit, hardware-accepted
    # profile is selected. Older adaptive_triggers booleans are migrated by
    # load(); new files always use the named profile.
    "trigger_profile": "disabled",
    # Optional inactivity watchdog.  Zero preserves real DualSense semantics:
    # an effect may legitimately be written once and held until UHID_CLOSE or
    # an explicit Off.  CLOSE/STOP, disconnect and shutdown always clear it.
    "trigger_reset_timeout_s": 0.0,
}


def path(explicit=None):
    if explicit:
        return os.path.expanduser(explicit)
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, APP, "config.json")


def load(explicit=None):
    """Defaults merged with the config file. Returns (settings, source)."""
    settings = dict(DEFAULTS)
    target = path(explicit)
    try:
        with open(target) as handle:
            stored = json.load(handle)
    except FileNotFoundError:
        return settings, None
    except ValueError as exc:
        # A broken file is worth complaining about rather than silently
        # falling back: someone edited it and expects the edit to matter.
        raise SystemExit("%s: %s" % (target, exc))
    if not isinstance(stored, dict):
        raise SystemExit("%s: expected an object at the top level" % target)
    if "adaptive_triggers" in stored:
        if "trigger_profile" in stored:
            raise SystemExit(
                "%s: cannot combine trigger_profile with adaptive_triggers"
                % target)
        if not isinstance(stored["adaptive_triggers"], bool):
            raise SystemExit(
                "%s: adaptive_triggers must be a JSON boolean" % target)
        stored = dict(stored)
        stored["trigger_profile"] = (
            "ow2-safe" if stored.pop("adaptive_triggers") else "disabled")
    if ("trigger_profile" in stored
            and stored["trigger_profile"] not in TRIGGER_PROFILES):
        raise SystemExit(
            "%s: trigger_profile must be one of %s"
            % (target, ", ".join(TRIGGER_PROFILES)))
    unknown = sorted(set(stored) - set(DEFAULTS))
    if unknown:
        print("%s: ignoring unknown key(s): %s" % (target, ", ".join(unknown)))
    settings.update({k: v for k, v in stored.items() if k in DEFAULTS})
    return settings, target


def write_default(explicit=None, force=False):
    """Write a commented-by-example config, without clobbering an existing one."""
    target = path(explicit)
    if os.path.exists(target) and not force:
        return target, False
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w") as handle:
        json.dump(DEFAULTS, handle, indent=2)
        handle.write("\n")
    return target, True
