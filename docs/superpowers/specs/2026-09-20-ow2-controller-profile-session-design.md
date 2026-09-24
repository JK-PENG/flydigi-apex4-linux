# OW2 Controller Profile Session Design

## Goal

Make the already verified OW2 path usable without manually stopping the normal
DualSense Edge relay: an explicitly opted-in Steam launch switches the virtual
controller to ordinary DualSense before the game, then restores the normal Edge
service after the game exits.

## Scope

- The first documented consumer is OW2. The mechanism is not enabled globally
  and is not evidence that other games need ordinary DualSense.
- The normal relay remains DualSense Edge so M1-M4 keep working outside this
  game session.
- Profile switching does not enable adaptive-trigger hardware writes. The
  existing `adaptive_triggers` configuration and hardware safety gates remain
  authoritative.
- The existing filter-only launch option remains unchanged unless
  `--relay-profile dualsense` is explicitly present.
- Probe replacement and automatic profile switching cannot be combined; a
  diagnostic probe must keep its relay setup explicit.

## Selected Approach

Extend `tools/proton-game.py` with an opt-in relay session and keep the service
operations in a focused `apex4ds5.game_session` module. The wrapper performs a
read-only preflight, asks the existing `apex4-relay` controller to replace the
installed service with a transient ordinary-DualSense relay, waits for the
expected virtual identity, runs the unchanged Proton command as an argv array,
and restores the installed service in `finally`.

This reuses the project's user-systemd lifecycle and process lock. A new daemon
would duplicate service ownership and state, while changing UHID identity inside
the long-running relay would require an invasive virtual-device teardown and
recreation path.

## Components

### `apex4ds5/game_session.py`

`RelayProfileSession` owns only service/profile lifecycle. It receives an
explicit relay-control script path and injectable command runner, clock/sleeper,
and sysfs root so all behavior can be tested without systemd or hardware.

Before switching it requires:

1. `flydigi-apex4.service` is active.
2. `apex4-relay-manual.service` is inactive.
3. the project's virtual Edge identity is present as `054c:0df2` with
   `HID_NAME=Apex 4 (DualSense Edge)`.

It then runs the existing relay controller with
`start -- --emulate dualsense`, waits for `054c:0ce6` plus
`HID_NAME=Apex 4 (DualSense)`, and marks restoration as required before any
mutating operation. Restoration stops the transient relay, starts the installed
service, and waits for the Edge identity. Failure to establish the temporary
identity prevents the game from starting; restoration is still attempted.

### `tools/proton-game.py`

Add `--relay-profile {unchanged,dualsense}` with `unchanged` as the default.
Preview mode prints the planned switch but changes no service. Run mode uses the
session context around a child process only for `dualsense`; the unchanged path
keeps the current `execvpe` behavior.

The child receives the existing filtered environment and exact command argv.
SIGINT and SIGTERM are forwarded to it, after which normal unwinding restores
the relay. The child's exit status is preserved when restoration succeeds.

## Failure Handling

- Invalid starting state: fail closed before changing services or launching the
  game.
- Temporary relay start/readiness failure: attempt restoration, report the
  failing phase, and do not launch the game.
- Game error or wrapper exception: restore in `finally`.
- Restore failure: return failure and print exact recovery commands; never claim
  Edge was restored without observing its identity.
- SIGINT/SIGTERM: forward to the game and restore after it exits.
- SIGKILL or host power loss cannot be caught in-process. A reboot starts the
  enabled daily service; before that, `systemctl --user restart
  flydigi-apex4.service` is the explicit recovery operation.

## Testing

Python `unittest` covers preflight refusal, successful switch/restore ordering,
temporary identity timeout with restoration, preview non-mutation, probe
conflict, child argv/environment preservation, exit-code preservation, and
restoration after child failure. Existing filter and probe tests remain green.

SteamOS validation is staged:

1. Install to a disposable/test tree and run unit/compile/shell checks.
2. Run a non-game fake child through the wrapper and observe Edge -> DualSense
   -> Edge without trigger writes.
3. Only after advance notice and confirmation, launch OW2 and verify the same
   identity transition. No new physical trigger write is part of this step.

## Acceptance Criteria

- OW2 is the only documented opt-in game.
- Default wrapper behavior is byte-for-byte compatible at the command boundary.
- The game never starts when the relay preflight or temporary identity fails.
- Normal exit, child failure, SIGINT, and SIGTERM restore the installed Edge
  service and verified Edge identity.
- The implementation adds no runtime dependency and performs no raw HID write.
