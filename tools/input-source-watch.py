#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Read-only, time-aligned physical/Sony/Xbox input-source observer."""
import argparse
import os
import re
import select
import signal
import struct
import time


EV_KEY, EV_ABS = 0x01, 0x03
TRIGGER_ABS_CODES = {
    "physical": frozenset((0x09, 0x0A)),
    "sony": frozenset((0x02, 0x05)),
    "xbox": frozenset((0x02, 0x05)),
}
GAMEPAD_KEY_MIN, GAMEPAD_KEY_MAX = 0x130, 0x13E
INPUT_EVENT = struct.Struct("llHHi")


def parse_devices(text):
    devices = []
    for block in text.split("\n\n"):
        identity = re.search(
            r"^I:.*Vendor=([0-9a-fA-F]{4}) Product=([0-9a-fA-F]{4})",
            block, re.MULTILINE)
        name = re.search(r'^N: Name="(.*)"$', block, re.MULTILINE)
        handlers = re.search(r"^H: Handlers=(.*)$", block, re.MULTILINE)
        if not identity or not name or not handlers:
            continue
        values = handlers.group(1).split()
        event = next((value for value in values if value.startswith("event")), None)
        devices.append({
            "vendor": identity.group(1).lower(),
            "product": identity.group(2).lower(),
            "name": name.group(1),
            "handlers": values,
            "event": event,
        })
    return devices


def candidate_sources(devices):
    found = {}
    for device in devices:
        if not device["event"] or not any(h.startswith("js")
                                            for h in device["handlers"]):
            continue
        name = device["name"]
        source = None
        if (device["vendor"], device["product"]) == ("04b4", "2412") \
                and name == "Flydigi Flydigi VADER3":
            source = "physical"
        elif device["vendor"] == "054c" \
                and name in ("Apex 4 (DualSense)", "Apex 4 (DualSense Edge)"):
            source = "sony"
        elif (device["vendor"], device["product"]) == ("28de", "11ff") \
                and name.startswith("Microsoft X-Box 360 pad"):
            source = "xbox"
        if source and source not in found:
            item = dict(device)
            item["source"] = source
            found[source] = item
    return [found[source] for source in ("physical", "sony", "xbox")
            if source in found]


def monitor_sources(candidates, physical_only=False):
    """Keep the physical trigger observable while the virtual relay is stopped."""
    if physical_only:
        return [item for item in candidates if item["source"] == "physical"]
    return candidates


def format_event(source, timestamp, event_type, code, value):
    if event_type == EV_ABS and code in TRIGGER_ABS_CODES.get(source, ()):
        kind = "abs"
    elif (event_type == EV_KEY
          and GAMEPAD_KEY_MIN <= code <= GAMEPAD_KEY_MAX):
        kind = "key"
    else:
        return None
    return ("t=%.6f source=%s type=%s code=0x%03x value=%d"
            % (timestamp, source, kind, code, value))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=float, default=45.0)
    parser.add_argument("--physical-only", action="store_true",
                        help="watch the physical pad even while the virtual relay is stopped")
    args = parser.parse_args()
    if not 5.0 <= args.seconds <= 120.0:
        parser.error("--seconds must be between 5 and 120")
    with open("/proc/bus/input/devices", encoding="utf-8", errors="replace") as stream:
        candidates = monitor_sources(
            candidate_sources(parse_devices(stream.read())), args.physical_only)
    if not any(item["source"] == "physical" for item in candidates):
        parser.error("physical Flydigi gamepad source not found")
    if (not args.physical_only
            and not any(item["source"] == "sony" for item in candidates)):
        parser.error("virtual Sony gamepad source not found")
    fds = {}
    try:
        for item in candidates:
            path = "/dev/input/%s" % item["event"]
            try:
                fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
            except OSError as exc:
                parser.error("cannot read %s input source: %s"
                             % (item["source"], exc))
            fds[fd] = item["source"]
        print("READY input sources: %s"
              % ", ".join("%s=%s" % (item["source"], item["name"])
                          for item in candidates), flush=True)
        stopped = []
        signal.signal(signal.SIGINT, lambda *_: stopped.append(True))
        signal.signal(signal.SIGTERM, lambda *_: stopped.append(True))
        end = time.monotonic() + args.seconds
        while not stopped and time.monotonic() < end:
            ready, _, _ = select.select(list(fds), [], [], 0.2)
            for fd in ready:
                try:
                    data = os.read(fd, INPUT_EVENT.size * 64)
                except BlockingIOError:
                    continue
                for offset in range(0, len(data) - INPUT_EVENT.size + 1,
                                    INPUT_EVENT.size):
                    _sec, _usec, event_type, code, value = \
                        INPUT_EVENT.unpack_from(data, offset)
                    line = format_event(
                        fds[fd], time.monotonic(), event_type, code, value)
                    if line:
                        print(line, flush=True)
    finally:
        for fd in fds:
            os.close(fd)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
