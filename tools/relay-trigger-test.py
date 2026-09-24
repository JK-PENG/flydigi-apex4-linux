#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Inject a fixed DS5 effect into this relay's virtual controller.

Dry-run by default. This writes a known DualSense output report, never a raw
Flydigi command; whether it reaches hardware depends on the relay mode.
"""
import argparse
import glob
import os
import signal
import sys
import time


DS5_IDS = {
    "0003:0000054C:00000CE6",
    "0003:0000054C:00000DF2",
}
DS5_NAMES = {"Apex 4 (DualSense)", "Apex 4 (DualSense Edge)"}
USB_REPORT_LEN = 48
MILD_START = 60
MILD_STRENGTH = 40
FIXED_CANDIDATE_VECTORS = {
    "l2-rattle-32": ("left", 0x06, (21, 32, 0), 1.0),
    "l2-resistance-40": ("left", 0x01, (0, 40), 1.0),
    "l2-resistance-hold15": ("left", 0x01, (0, 40), 15.0),
    "r2-resistance-hold15": ("right", 0x01, (0, 40), 15.0),
    "l2-breakpoint-20": ("left", 0x02, (60, 20, 20), 1.0),
    "r2-breakpoint-20": ("right", 0x02, (60, 20, 20), 1.0),
    "l2-zone-rattle-32":
        ("left", 0x26, tuple(bytes.fromhex("ff030000000000001500")), 1.0),
    "r2-zone-resistance-40":
        ("right", 0x21, tuple(bytes.fromhex("ff039224491200000000")), 1.0),
    "l2-zone-weapon-20": ("left", 0x25, (0x24, 0, 7), 1.0),
    "r2-machine-unsupported": ("right", 0x27, (0x24, 0, 0x3F, 9, 3), 1.0),
}


def virtual_node():
    matches = []
    for path in sorted(glob.glob("/dev/hidraw*")):
        uevent = "/sys/class/hidraw/%s/device/uevent" % os.path.basename(path)
        try:
            with open(uevent) as handle:
                fields = dict(line.split("=", 1)
                              for line in handle.read().splitlines() if "=" in line)
        except OSError:
            continue
        if (fields.get("HID_ID") in DS5_IDS
                and fields.get("HID_NAME") in DS5_NAMES):
            matches.append(path)
    return matches[0] if len(matches) == 1 else None


def _fixed_report(side, effect_type, params):
    report = bytearray(USB_REPORT_LEN)
    report[0] = 0x02
    if side == "right":
        report[1] = 0x04
        offset = 11
    elif side == "left":
        report[1] = 0x08
        offset = 22
    else:
        raise ValueError("side must be left or right")
    report[offset] = effect_type
    report[offset + 1:offset + 11] = bytes(params) + bytes(10 - len(params))
    return bytes(report)


def output_report(side, effect_type):
    """Preserve the original fixed mild/Off test interface."""
    if effect_type == 0x01:
        return _fixed_report(side, effect_type, (MILD_START, MILD_STRENGTH))
    if effect_type == 0x05:
        return _fixed_report(side, effect_type, ())
    raise ValueError("only mild resistance and Off are allowed")


def candidate_reports(name):
    """Return one repository-fixed output vector and its same-side Off."""
    side, type_, params, _duration = FIXED_CANDIDATE_VECTORS[name]
    return _fixed_report(side, type_, params), output_report(side, 0x05)


def write_exact(fd, report):
    written = os.write(fd, report)
    if written != len(report):
        raise OSError("short virtual DS5 write (%d/%d)" % (written, len(report)))


def main():
    parser = argparse.ArgumentParser(
        description="Bounded mild trigger test through the live relay")
    parser.add_argument("--write", action="store_true",
                        help="write to this relay's virtual DualSense/Edge")
    parser.add_argument("--candidate", choices=tuple(FIXED_CANDIDATE_VECTORS),
                        help="one fixed generic-safe DualSense report")
    parser.add_argument("--side", choices=("left", "right"), default=None)
    parser.add_argument("--duration", type=float, default=None)
    parser.add_argument("--repeat", type=int, default=1,
                        help="send 1..5 duplicates to test relay deduplication")
    args = parser.parse_args()
    if not 1 <= args.repeat <= 5:
        parser.error("--repeat must be between 1 and 5")
    if args.candidate:
        if args.side is not None or args.duration is not None or args.repeat != 1:
            parser.error("--candidate has fixed side, duration and one report")
        applied, off = candidate_reports(args.candidate)
        duration = FIXED_CANDIDATE_VECTORS[args.candidate][3]
        label = args.candidate
    else:
        duration = 1.0 if args.duration is None else args.duration
        if not 0.1 <= duration <= 2.0:
            parser.error("--duration must be between 0.1 and 2.0 seconds")
        side = args.side or "right"
        applied = output_report(side, 0x01)
        off = output_report(side, 0x05)
        label = "mild %s" % side
    print("%s: %s" % (label, applied.hex(" ")))
    print("Off: %s" % off.hex(" "))
    print("active duration <= %.1fs; automatic same-side Off" % duration)
    if not args.write:
        print("No virtual output was written. Add --write after the relay is ready.")
        return 0
    node = virtual_node()
    if not node:
        parser.error("relay virtual DualSense/Edge hidraw node not found")
    fd = os.open(node, os.O_WRONLY)
    interrupted = []
    signal.signal(signal.SIGINT, lambda *_: interrupted.append(True))
    signal.signal(signal.SIGTERM, lambda *_: interrupted.append(True))
    try:
        for _ in range(args.repeat):
            write_exact(fd, applied)
            time.sleep(0.05)
        end = time.monotonic() + duration
        while not interrupted and time.monotonic() < end:
            time.sleep(min(0.05, end - time.monotonic()))
    finally:
        try:
            write_exact(fd, off)
        finally:
            os.close(fd)
    print("wrote %d %s report(s), then Off, via %s"
          % (args.repeat, label, node))
    return 0


if __name__ == "__main__":
    sys.exit(main())
