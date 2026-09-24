#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Read-only live checks for the physical-vendor -> virtual-DS5 path."""
import argparse
import glob
import os
import select
import signal
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from apex4ds5 import legacy  # noqa: E402


DS5_IDS = {
    "HID_ID=0003:0000054C:00000CE6",
    "HID_ID=0003:0000054C:00000DF2",
}
SENSOR_NAMES = (
    "accel_x", "accel_y", "accel_z",
    "gyro_pitch", "gyro_yaw", "gyro_roll",
)
INPUT_EVENT = struct.Struct("llHHi")
EV_REL = 0x02
REL_X, REL_Y = 0x00, 0x01


def virtual_node():
    """Find this relay's virtual DualSense/Edge hidraw node, not a real pad."""
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


def physical_mouse_event():
    """Find the APEX 4 interface-1 mouse event node when udev exposes it."""
    candidates = glob.glob("/dev/input/by-id/usb-Flydigi_*-if01-event-mouse")
    for link in sorted(candidates):
        node = os.path.realpath(link)
        base = "/sys/class/input/%s/device/id" % os.path.basename(node)
        try:
            vendor = int(open(os.path.join(base, "vendor")).read().strip(), 16)
            product = int(open(os.path.join(base, "product")).read().strip(), 16)
        except (OSError, ValueError):
            continue
        if vendor == legacy.VENDOR_ID and product == legacy.PRODUCT_ID:
            return node
    return None


def open_read(path):
    return os.open(path, os.O_RDONLY | os.O_NONBLOCK)


def watch_paddles(vendor, virtual, seconds, stopped):
    fds = {open_read(vendor): "vendor", open_read(virtual): "virtual"}
    last = {"vendor": None, "virtual": None}
    sequence = {"vendor": [], "virtual": []}
    print("READY paddles: %s -> %s" % (vendor, virtual), flush=True)
    print("Press labelled M1, M2, M3, M4 once each, in that order.", flush=True)
    end = time.monotonic() + seconds
    try:
        while not stopped and time.monotonic() < end:
            ready, _, _ = select.select(list(fds), [], [], 0.2)
            for fd in ready:
                kind = fds[fd]
                data = os.read(fd, 128)
                if kind == "vendor":
                    if len(data) < legacy.REPORT_LEN or data[0] != legacy.INPUT_REPORT_ID:
                        continue
                    mask = data[7] & 0x3C
                else:
                    if len(data) < 11 or data[0] != 0x01:
                        continue
                    mask = data[10] & 0xF0
                if mask == last[kind]:
                    continue
                print("%-7s mask 0x%02x" % (kind, mask), flush=True)
                if mask:
                    sequence[kind].append(mask)
                last[kind] = mask
    finally:
        for fd in fds:
            os.close(fd)
    print("vendor sequence : %s" % " ".join("%02x" % v for v in sequence["vendor"]))
    print("virtual sequence: %s" % " ".join("%02x" % v for v in sequence["virtual"]))
    return 0 if len(sequence["vendor"]) >= 4 and len(sequence["virtual"]) >= 4 else 1


def _s16(data, lo, hi=None):
    if hi is None:
        return struct.unpack_from("<h", data, lo)[0]
    return int.from_bytes(bytes((data[lo], data[hi])), "little", signed=True)


def imu_passed(frames, sensors):
    """Require live values from both halves of the six-axis sensor."""
    changed = {name for name, (low, high) in sensors.items()
               if low is not None and low != high}
    return bool(frames and changed.intersection(SENSOR_NAMES[:3])
                and changed.intersection(SENSOR_NAMES[3:]))


def mouse_motion_events(data):
    """Count non-zero X/Y relative events from the gyro-mouse interface."""
    count = 0
    for offset in range(0, len(data) - INPUT_EVENT.size + 1, INPUT_EVENT.size):
        _, _, event_type, code, value = INPUT_EVENT.unpack_from(data, offset)
        if event_type == EV_REL and code in (REL_X, REL_Y) and value:
            count += 1
    return count


def watch_imu(vendor, seconds, stopped, mouse_event=None):
    vendor_fd = open_read(vendor)
    fds = {vendor_fd: "vendor"}
    if mouse_event:
        try:
            fds[open_read(mouse_event)] = "mouse"
        except OSError as exc:
            print("mouse monitor unavailable: %s: %s" % (mouse_event, exc),
                  file=sys.stderr, flush=True)
            mouse_event = None
    byte_low = [None] * legacy.REPORT_LEN
    byte_high = [None] * legacy.REPORT_LEN
    sensors = {name: [None, None] for name in SENSOR_NAMES}
    frames = 0
    mouse_events = 0
    print("READY imu: %s%s" % (
        vendor, " + %s" % mouse_event if mouse_event else ""), flush=True)
    print("Move and tilt the pad without touching sticks, triggers, or buttons.", flush=True)
    end = time.monotonic() + seconds
    try:
        while not stopped and time.monotonic() < end:
            ready, _, _ = select.select(list(fds), [], [], 0.2)
            if not ready:
                continue
            for fd in ready:
                if fds[fd] == "mouse":
                    mouse_events += mouse_motion_events(
                        os.read(fd, INPUT_EVENT.size * 64))
                    continue
                data = os.read(fd, 64)
                if len(data) != legacy.REPORT_LEN or data[0] != legacy.INPUT_REPORT_ID:
                    continue
                frames += 1
                for offset, value in enumerate(data):
                    byte_low[offset] = (value if byte_low[offset] is None
                                        else min(byte_low[offset], value))
                    byte_high[offset] = (value if byte_high[offset] is None
                                         else max(byte_high[offset], value))
                ax, ay, az = struct.unpack_from("<3h", data, 11)
                values = {
                    "accel_x": ax,
                    "accel_y": ay,
                    "accel_z": az,
                    "gyro_pitch": _s16(data, 26),
                    "gyro_yaw": _s16(data, 18, 20),
                    "gyro_roll": _s16(data, 29),
                }
                for name, value in values.items():
                    low, high = sensors[name]
                    sensors[name] = [value if low is None else min(low, value),
                                     value if high is None else max(high, value)]
    finally:
        for fd in fds:
            os.close(fd)
    print("frames: %d" % frames)
    for name, (low, high) in sensors.items():
        print("%-10s %s..%s" % (name, low, high))
    changed_offsets = [index for index, (low, high)
                       in enumerate(zip(byte_low, byte_high))
                       if low is not None and low != high]
    print("nonconstant raw byte offsets: %s"
          % (" ".join(str(index) for index in changed_offsets) or "none"))
    if mouse_event:
        print("gyro-mouse X/Y events: %d" % mouse_events)
    passed = imu_passed(frames, sensors)
    if mouse_events and not passed:
        print("diagnosis: gyro-mouse moved but vendor IMU did not pass")
    return 0 if passed else 1


def main():
    parser = argparse.ArgumentParser(
        description="Read-only validation of relay paddles or physical IMU data")
    parser.add_argument("mode", choices=("paddles", "imu"))
    parser.add_argument("--seconds", type=float, default=30.0)
    parser.add_argument("--vendor", help="APEX 4 vendor hidraw (default: autodetect)")
    parser.add_argument("--virtual", help="relay virtual DS5 hidraw (default: autodetect)")
    parser.add_argument("--mouse-event",
                        help="physical gyro-mouse event node (default: autodetect)")
    args = parser.parse_args()
    if not 1.0 <= args.seconds <= 300.0:
        parser.error("--seconds must be between 1 and 300")
    vendor = args.vendor or legacy.find_vendor_node()
    if not vendor:
        parser.error("APEX 4 0xFFA0 vendor node not found")
    stopped = []
    signal.signal(signal.SIGINT, lambda *_: stopped.append(True))
    signal.signal(signal.SIGTERM, lambda *_: stopped.append(True))
    if args.mode == "imu":
        mouse_event = args.mouse_event or physical_mouse_event()
        return watch_imu(vendor, args.seconds, stopped, mouse_event)
    virtual = args.virtual or virtual_node()
    if not virtual:
        parser.error("relay virtual DualSense/Edge hidraw node not found")
    return watch_paddles(vendor, virtual, args.seconds, stopped)


if __name__ == "__main__":
    sys.exit(main())
