#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Bounded, identity-gated APEX 4 ForceAdapt test.  Dry-run by default."""
import argparse
import os
import select
import signal
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from apex4ds5 import forceadapt, legacy, relay_lock  # noqa: E402


SAFE_EFFECTS = {
    "mild": (60, 40),
    "medium": (55, 80),
    "strong": (50, 120),
}

# Fixed proposals only. They are not permission to perform a hardware test:
# --write still requires a holder-approved, precisely scoped test window.
FIXED_PHYSICAL_CANDIDATES = {
    "l2-rattle-32": (forceadapt.rattle("left", 0, 1, 32, 21), 1.0),
    "l2-resistance-40": (forceadapt.resistance("left", 0, 40), 1.0),
    "l2-resistance-hold15": (forceadapt.resistance("left", 0, 40), 15.0),
    "r2-resistance-hold15": (forceadapt.resistance("right", 0, 40), 15.0),
    "l2-breakpoint-20": (forceadapt.breakpoint("left", 60, 20, 20), 1.0),
    "r2-breakpoint-20": (forceadapt.breakpoint("right", 60, 20, 20), 1.0),
}


def count_forceadapt_echoes(fd, deadline, *, clock=time.monotonic,
                            waiter=select.select, reader=os.read):
    """Count existing 0xA0 echoes on one fd without sending a command."""
    count = 0
    while True:
        remaining = deadline - clock()
        if remaining <= 0:
            return count
        if not waiter([fd], [], [], min(0.02, remaining))[0]:
            continue
        try:
            data = reader(fd, 64)
        except BlockingIOError:
            continue
        if legacy.command_echo(data) == legacy.CMD_FORCEADAPT:
            count += 1


def selected_effects(side, name):
    sides = ("left", "right") if side == "both" else (side,)
    if name == "normal":
        return [forceadapt.normal(item) for item in sides]
    start, strength = SAFE_EFFECTS[name]
    return [forceadapt.resistance(item, start, strength) for item in sides]


def print_packet(prefix, effect):
    print("%s %s: mode=%d params=%s packet=%s"
          % (prefix, effect.side, effect.mode, effect.params,
             forceadapt.build_packet(effect).hex(" ")))


def main():
    parser = argparse.ArgumentParser(
        description="Safely test confirmed APEX 4 ForceAdapt resistance")
    parser.add_argument("--write", action="store_true",
                        help="perform the identity-gated hardware write")
    parser.add_argument("--observe-forceadapt-echo", action="store_true",
                        help="bounded same-fd observation of the existing 0xA0 echo")
    parser.add_argument("--candidate", choices=tuple(FIXED_PHYSICAL_CANDIDATES),
                        help="one fixed generic-safe physical candidate")
    parser.add_argument("--side", choices=("left", "right", "both"),
                        default=None)
    parser.add_argument("--effect", choices=("normal", "mild", "medium", "strong"),
                        default=None)
    parser.add_argument("--duration", type=float, default=None,
                        help="effect duration, 0.1..2.0 seconds (default: 1.0)")
    args = parser.parse_args()
    if args.observe_forceadapt_echo and (
            not args.write or
            (not args.candidate and
             (args.effect != "mild" or args.side not in ("left", "right")))):
        parser.error("echo observation requires --write and a fixed candidate "
                     "or one-side mild")
    if args.candidate:
        if any(value is not None for value in (args.side, args.effect,
                                                args.duration)):
            parser.error("--candidate has fixed side, effect and duration")
        selected, duration = FIXED_PHYSICAL_CANDIDATES[args.candidate]
        effects = [selected]
    else:
        duration = 1.0 if args.duration is None else args.duration
        if not 0.1 <= duration <= 2.0:
            parser.error("--duration must be between 0.1 and 2.0 seconds")
        effects = selected_effects(args.side or "right", args.effect or "mild")
    non_normal = any(item.mode != forceadapt.MODE_NORMAL for item in effects)

    guard = None
    if args.write:
        try:
            guard = relay_lock.RelayLock()
        except relay_lock.RelayBusy as exc:
            print(str(exc), file=sys.stderr)
            return 2

    # A fixed candidate preview is a pure packet calculation. Probing a live
    # vendor fd for 0xEC here can race the daily relay and is not needed until
    # the explicitly requested write path.
    node = (legacy.find_vendor_node()
            if args.write or not args.candidate else None)
    fd = None
    transport = None
    if node is None:
        if args.write:
            print("No APEX 4 04b4:2412/0xFFA0 vendor interface found.", file=sys.stderr)
            guard.close()
            return 2
        reason = ("candidate dry-run" if args.candidate else
                  "no APEX 4 vendor interface present")
        print("identity: not checked (%s)" % reason)
    else:
        try:
            fd = os.open(node, os.O_RDWR | os.O_NONBLOCK)
            transport = forceadapt.VerifiedTransport.verify(fd, node)
        except (OSError, forceadapt.IdentityError) as exc:
            if fd is not None:
                os.close(fd)
            if guard is not None:
                guard.close()
            print(str(exc), file=sys.stderr)
            return 2
        print("identity: verified %s on %s"
              % (forceadapt.identity_description(transport.identity), node))

    if not args.write:
        for effect in effects:
            print_packet("DRY-RUN apply", effect)
        if non_normal:
            for side in ("left", "right"):
                print_packet("DRY-RUN auto-reset", forceadapt.normal(side))
        if fd is not None:
            os.close(fd)
        if guard is not None:
            guard.close()
        print("No ForceAdapt command was written. Add --write for the bounded test.")
        return 0

    signal.signal(signal.SIGTERM,
                  lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    print("active duration <= %.1fs; automatic bilateral Normal" % duration)
    clear_failed = False
    try:
        # Always remove inherited state before the requested effect.
        transport.write_effect(forceadapt.normal("left"))
        transport.write_effect(forceadapt.normal("right"))
        if args.observe_forceadapt_echo:
            # Initial Normal replies cannot be attributed to the candidate.
            # Drain for a bounded interval before applying the effect.
            try:
                count_forceadapt_echoes(
                    fd, time.monotonic() + 0.1, clock=time.monotonic)
            except OSError:
                print("A0_ECHO_UNKNOWN (preclear read failed)", file=sys.stderr)
                raise
        for effect in effects:
            print_packet("WRITE apply", effect)
            transport.write_effect(effect)
            applied_at = time.monotonic()
            print("WRITE accepted t=%.6f" % applied_at)
            if args.observe_forceadapt_echo:
                deadline = applied_at + duration
                try:
                    echoes = count_forceadapt_echoes(
                        fd, min(applied_at + 0.1, deadline),
                        clock=time.monotonic)
                    print("A0_ECHO_%s count=%d"
                          % ("OBSERVED" if echoes else "NOT_OBSERVED", echoes))
                except OSError:
                    print("A0_ECHO_UNKNOWN (read failed)")
                time.sleep(max(0.0, deadline - time.monotonic()))
        if non_normal and not args.observe_forceadapt_echo:
            time.sleep(duration)
    except KeyboardInterrupt:
        print("interrupted; clearing triggers")
    finally:
        for side in ("left", "right"):
            try:
                transport.write_effect(forceadapt.normal(side))
            except OSError as exc:
                clear_failed = True
                print("clear %s failed: %s" % (side, exc), file=sys.stderr)
        os.close(fd)
        guard.close()
    if clear_failed:
        print("Trigger Normal reset is UNKNOWN; stop physical tests.",
              file=sys.stderr)
        return 1
    print("Normal reset complete t=%.6f" % time.monotonic())
    print("Triggers restored to Normal.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
