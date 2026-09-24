#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Extract deduplicated trigger transitions from relay HID-debug logs."""
import ast
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from apex4ds5._ds5 import ds5  # noqa: E402


HID_OUTPUT = re.compile(
    r"HID t=([0-9.]+) OUTPUT rtype=\d+ len=\d+ data=([0-9a-fA-F ]+)")
COMPARISON = re.compile(
    r"COMPARE (L2|R2): compat=(none|mode=\d+ params=\([^)]*\)) "
    r"semantic=(none|mode=\d+ params=\([^)]*\)) "
    r"t=([0-9.]+) physical_l2=(-?\d+) physical_r2=(-?\d+)")
MAPPING = re.compile(r"mode=(\d+) params=(\([^)]*\))")


def _mapping(text):
    if text == "none":
        return None
    match = MAPPING.fullmatch(text)
    if not match:
        raise ValueError("invalid mapping record")
    params = ast.literal_eval(match.group(2))
    return {"mode": int(match.group(1)), "params": list(params)}


def extract_lines(lines):
    records = []
    last = {"left": None, "right": None}
    for line in lines:
        comparison = COMPARISON.search(line)
        if comparison:
            records.append({
                "kind": "comparison",
                "side": "left" if comparison.group(1) == "L2" else "right",
                "t": float(comparison.group(4)),
                "compat": _mapping(comparison.group(2)),
                "semantic": _mapping(comparison.group(3)),
                "physical_l2": int(comparison.group(5)),
                "physical_r2": int(comparison.group(6)),
            })
            continue
        output = HID_OUTPUT.search(line)
        if not output:
            continue
        try:
            report = bytes.fromhex(output.group(2))
        except ValueError:
            continue
        for effect in ds5.parse_output(report)["effects"]:
            key = effect.key()
            if key == last[effect.side]:
                continue
            last[effect.side] = key
            records.append({
                "kind": "effect",
                "t": float(output.group(1)),
                "side": effect.side,
                "type": "0x%02x" % effect.type,
                "params": bytes(effect.params).hex(),
                "report": report.hex(),
            })
    return records


def main():
    for record in extract_lines(sys.stdin):
        print(json.dumps(record, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
