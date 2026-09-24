#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Capture the back paddles one named button at a time, read-only.

`relay-path-watch.py paddles` prompts for "M1, M2, M3, M4 in that order" and
assumes the holder presses them in label order. That assumption is exactly what
went wrong once: the run that produced `paddle_bits=2,3,4,5` never recorded
which button was actually pressed, so a correct `paddle_bits` sat next to a
wrong `paddles` for a whole session and nobody could tell.

This tool removes the assumption. It prompts for one button, waits for exactly
that press, pairs it with the virtual report it produced, and moves on. Give the
buttons names you have agreed with the holder *before* starting.

Two traps this cannot protect you from, both learned the hard way:

* The `M` labels are read with the pad turned over, and turning it over swaps
  left and right. A back-view description therefore yields a mirrored mapping
  that looks self-consistent and is still wrong.
* The result that matters is the one on Steam's front-facing controller test, or
  the one you get by asking which hand reaches the button. Decide it there, not
  from a drawing of the back.

Run it from the checkout so `apex4ds5` is importable, with the relay already
running so the virtual node exists:

    python3 tools/paddle-capture.py --paddle-bits 2,3,4,5 \
        --names "left of switch,right of switch,left grip,right grip"
"""
import argparse
import glob
import os
import select
import signal
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from apex4ds5 import legacy  # noqa: E402

VIRTUAL_REPORT_ID = 0x01
VIRTUAL_PADDLE_OFFSET = 10
VIRTUAL_PADDLE_MASK = 0xF0
VENDOR_PADDLE_MASK = 0x3C

# DualSense Edge extra-button bits, straight out of hid-playstation's
# DS_EDGE_BUTTONS_* and SDL_hidapi_ps5.c.
EDGE_MEANING = {
    0x10: "fn1 (left Fn)",
    0x20: "fn2 (right Fn)",
    0x40: "paddle-left (left rear)",
    0x80: "paddle-right (right rear)",
}
DS5_IDS = ("HID_ID=0003:0000054C:00000DF2", "HID_ID=0003:0000054C:00000CE6")


def virtual_node():
    """Find this relay's virtual DualSense/Edge node, not a real controller."""
    for path in sorted(glob.glob("/dev/hidraw*")):
        uevent = "/sys/class/hidraw/%s/device/uevent" % os.path.basename(path)
        try:
            text = open(uevent).read()
        except OSError:
            continue
        if (any(identity in text for identity in DS5_IDS)
                and "HID_NAME=Apex 4 (DualSense" in text):
            return path
    return None


def open_read(path):
    return os.open(path, os.O_RDONLY | os.O_NONBLOCK)


def main():
    parser = argparse.ArgumentParser(
        description="Read-only, one-button-at-a-time paddle capture")
    parser.add_argument("--paddle-bits", default="2,3,4,5",
                        help="vendor bits for M1..M4, as for the relay")
    parser.add_argument("--names",
                        default="button 1,button 2,button 3,button 4",
                        help="what to call the four buttons in the prompts; "
                             "agree these with the holder first")
    parser.add_argument("--rounds", type=int, default=2,
                        help="passes over the four buttons; a repeat is a control")
    parser.add_argument("--seconds", type=float, default=25.0,
                        help="how long to wait for each press")
    parser.add_argument("--vendor", help="APEX 4 vendor hidraw (default: autodetect)")
    parser.add_argument("--virtual", help="relay virtual DS5 hidraw (default: autodetect)")
    args = parser.parse_args()

    bits = tuple(int(v) for v in args.paddle_bits.split(","))
    if len(bits) != 4 or set(bits) != {2, 3, 4, 5}:
        parser.error("--paddle-bits must be a permutation of 2,3,4,5")
    names = [n.strip() for n in args.names.split(",")]
    if len(names) != 4 or not all(names):
        parser.error("--names needs exactly four non-empty names")

    vendor = args.vendor or legacy.find_vendor_node()
    virtual = args.virtual or virtual_node()
    if not vendor:
        parser.error("APEX 4 0xFFA0 vendor node not found")
    if not virtual:
        parser.error("relay virtual DualSense/Edge node not found -- is it running?")

    vfd, ufd = open_read(vendor), open_read(virtual)
    stopped = []
    signal.signal(signal.SIGINT, lambda *_: stopped.append(True))
    signal.signal(signal.SIGTERM, lambda *_: stopped.append(True))

    print("vendor  : %s" % vendor, flush=True)
    print("virtual : %s" % virtual, flush=True)
    print("paddle_bits = %s (M1..M4 read from these vendor bits)" % (bits,), flush=True)

    vendor_events = []   # (monotonic, mask)
    virtual_events = []  # (monotonic, mask)

    def pump(duration):
        end = time.monotonic() + duration
        while not stopped and time.monotonic() < end:
            ready, _, _ = select.select([vfd, ufd], [], [], 0.05)
            for fd in ready:
                try:
                    data = os.read(fd, 128)
                except OSError:
                    continue
                now = time.monotonic()
                if fd == vfd:
                    if (len(data) < legacy.REPORT_LEN
                            or data[0] != legacy.INPUT_REPORT_ID):
                        continue
                    mask = data[7] & VENDOR_PADDLE_MASK
                    if mask != (vendor_events[-1][1] if vendor_events else None):
                        vendor_events.append((now, mask))
                else:
                    if (len(data) < VIRTUAL_PADDLE_OFFSET + 1
                            or data[0] != VIRTUAL_REPORT_ID):
                        continue
                    mask = data[VIRTUAL_PADDLE_OFFSET] & VIRTUAL_PADDLE_MASK
                    if mask != (virtual_events[-1][1] if virtual_events else None):
                        virtual_events.append((now, mask))

    results = []
    for rnd in range(1, args.rounds + 1):
        print("\n--- pass %d of %d ---" % (rnd, args.rounds), flush=True)
        for name in names:
            if stopped:
                break
            before = len(vendor_events)
            print("READY: press and release ONLY %s  (waiting up to %.0fs)"
                  % (name, args.seconds), flush=True)
            deadline = time.monotonic() + args.seconds
            press = None
            while not stopped and time.monotonic() < deadline:
                pump(0.2)
                for stamp, mask in vendor_events[before:]:
                    if mask:
                        press = (stamp, mask)
                        break
                if press:
                    pump(0.4)      # let the release and the virtual report land
                    break
            if not press:
                print("  %s: NO PRESS SEEN" % name, flush=True)
                results.append((rnd, name, None, None))
                continue

            stamp, vmask = press
            vm = None
            for t, mask in virtual_events:
                if t >= stamp - 0.05 and mask:
                    vm = mask
                    break
            print("  %-22s vendor 0x%02x -> virtual %s  %s"
                  % (name, vmask,
                     "0x%02x" % vm if vm is not None else "none",
                     EDGE_MEANING.get(vm, "")), flush=True)
            results.append((rnd, name, vmask, vm))

    print("\n=== labelled press -> vendor bit -> virtual Edge bit ===")
    print("%-5s %-22s %-8s %-8s %s"
          % ("pass", "button", "vendor", "virtual", "virtual means"))
    for rnd, name, vmask, vm in results:
        print("%-5d %-22s %-8s %-8s %s"
              % (rnd, name,
                 "0x%02x" % vmask if vmask is not None else "-",
                 "0x%02x" % vm if vm is not None else "-",
                 EDGE_MEANING.get(vm, "")))

    print("\ndistinct vendor masks, first-appearance order : %s"
          % " ".join("0x%02x" % m for m in
                     dict.fromkeys(m for _, m in vendor_events if m)))
    print("distinct virtual masks, first-appearance order: %s"
          % " ".join("0x%02x" % m for m in
                     dict.fromkeys(m for _, m in virtual_events if m)))
    print("\nJudge this on Steam's front-facing controller test, or by which hand\n"
          "reaches the button. A back view is mirrored and will confirm a wrong\n"
          "answer.")

    os.close(vfd)
    os.close(ufd)
    return 0


if __name__ == "__main__":
    sys.exit(main())
