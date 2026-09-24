# Native DualSense adaptive triggers and APEX 4 ForceAdapt

This is the reverse half of the relay:

```text
Game
  -> virtual DualSense /dev/uhid output report
  -> apex4ds5._ds5.ds5.parse_output
  -> apex4ds5.trigger_translation
  -> apex4ds5.trigger_state
  -> apex4ds5.forceadapt
  -> APEX 4 0xFFA0 vendor HID
```

Implementation status: **unit/mock tests, live UHID dry-run and a bounded Linux
hardware test are verified over the 2.4 GHz dongle and over cable**. Both trigger
sides are physically confirmed through the actual relay on both transports and
restore Normal. OW2 has a game-triggered fixed R2 mild proof and a normal
automatic identity-switch/restore session with holder-confirmed menu control.
OW2 now also has three repeated bounded R2 rattle-to-resistance cycles cleared
by game Off with holder-confirmed effects and normal release. L2/game coverage,
cable repetition and the broader failure-path/release regression remain pending.
See [RETROSPECTIVE.md](RETROSPECTIVE.md) for the corrected evidence boundaries
and [VALIDATION.md](VALIDATION.md) for the dated runbook.

The 2026-09-21 synchronized no-write capture preserved complete OW2 reports and
physical R2 timing. Three cycles started `0x26` at R2=11..14, changed to `0x21`
about 0.72 seconds later at R2=129..255, and cleared with `0x05` at R2=0. It
also observed no Xbox-source input during the action window and restored one
Edge after exit. This closes capture/timing and input-path diagnosis, not
physical acceptance of native rattle or resistance parameters.

## What arrives from the virtual DualSense

Linux calls event type 6 `UHID_OUTPUT`; older headers and discussions call the
same event `UHID_OUTPUT_EV`. The binding also handles `UHID_SET_REPORT` for hosts
that use the control path. A USB output report starts with `0x02`; Bluetooth uses
`0x31` with one extra transport byte. In their common body:

| Field | Meaning |
|---|---|
| `flag0 & 0x04` | right trigger block is valid |
| `flag0 & 0x08` | left trigger block is valid |
| common bytes 10..20 | right type plus ten parameters |
| common bytes 21..31 | left type plus ten parameters |

`ds5.parse_output()` already owned these offsets and is reused. It returns one
side-specific raw `TriggerEffect` per valid block; malformed or unrelated
reports produce no effect and never raise inside the relay.

Known DualSense modes:

| Type | Meaning | Translation |
|---|---|---|
| `0x00` | empty/no-op block | do nothing |
| `0x01` | simple feedback/resistance | ForceAdapt Race/resistance |
| `0x02` | simple weapon/breakpoint | ForceAdapt breakthrough |
| `0x05` | Off | ForceAdapt Normal |
| `0x06` | simple vibration | ForceAdapt rattle |
| `0x21` | zone-based Feedback | openflydigi's game-tested mapping |
| `0x22` | Bow | nearest breakthrough approximation |
| `0x23` | Galloping | nearest bounded rattle approximation |
| `0x25` | zone-based Weapon | openflydigi's game-tested mapping |
| `0x26` | zone-based Vibration | openflydigi's game-tested mapping |
| `0x27` | Machine | nearest bounded rattle approximation |

The semantic parser decodes the 10-zone masks, packed 3-bit strengths, weapon
start/end zones and frequencies into `NormalizedTriggerEffect`. Translation is
not byte passthrough: DualSense and ForceAdapt do not share an effect vocabulary.
Unknown types, malformed blocks, limited legacy modes without a confirmed
mapping, and DualSense debug/calibration modes return no command. In particular,
an unknown effect does **not** clear the previous effect.

## The APEX 4 ForceAdapt report

APEX 4 is Flydigi's old/DInput protocol. Its live trigger report is 15 bytes:

```text
05 A0 01 AA SS MM P0 P1 P2 P3 P4 00 00 00 00
```

| Byte | Meaning |
|---|---|
| 0 | output report id `0x05` |
| 1 | confirmed DInput ForceAdapt command `0xA0` |
| 2 | effect family `0x01` |
| 3 | apply flag, normally `1` |
| 4 | side: `1` left, `2` right |
| 5 | mode |
| 6..10 | five mode-specific parameters |
| 11..14 | zero fill |

There is no checksum or CRC in this old-protocol frame. A successful HID write
is not treated as a physical ACK, so the low-latency path does not block waiting
for one. The pad holds the effect until another live effect or Normal arrives.

ForceAdapt modes used by native translation:

| Mode | Behavior | Parameters |
|---|---|---|
| 0 | Normal/clear | none |
| 1 | constant resistance after a start | start, strength, match-input |
| 2 | recoil/rattle | start, pressure, strength, frequency, match-input |
| 3 | resisting band then breakthrough | start, travel, resistance, unused, match-input |

Modes 4 and 5 are known vocabulary but native game translation does not select
them. Every field is clamped to its byte range and typed constructors clamp
parameters with a non-zero hardware minimum. Race's documented start-zero quirk
clears `match-input` rather than emitting the ineffective combination.

## Write safety and identity

`VerifiedTransport` is a capability, not a generic HID wrapper. It is created
only after all of these checks pass:

1. the sysfs HID id is exactly `04b4:2412`;
2. the report descriptor begins with the `0xFFA0` vendor collection;
3. a read-only command `0xEC` identity reply is received on that same fd;
4. connection is wired or the 2.4 GHz dongle;
5. DeviceType is the hardware-validated retail APEX 4 value `84` or `103`;
6. firmware identity bytes are present.

Firmware is logged but not pinned to a two-version allowlist: the repository's
measured type-84 pad and the public retail validation use multiple legitimate k2
firmware revisions. DeviceType plus exact interface identity is the capability
gate. Other regional k2 DeviceTypes remain disabled until physical evidence is
available.

The final transport checks the fully built packet again. Its entire runtime
command allowlist is `{0xA0}`. It has no `write_raw` API. Configuration, profile,
flash, factory-reset, firmware and OTA commands are unreachable through this
path and are never probed.

## State and reset semantics

`TriggerStateManager` tracks the last effect independently for L2 and R2. It
sends only changes, so a game repeating the same DualSense output does not flood
the vendor interface. Writes are 15 bytes to an already non-blocking fd, have no
ACK wait, and happen only on effect changes; this keeps them off the 250 Hz input
report path in practice without adding a worker or queue.

Both sides receive Normal on:

- initial verified attach and every vendor reconnect;
- explicit DualSense Off;
- virtual DualSense `UHID_CLOSE` or `UHID_STOP`;
- vendor read/write failure or physical disconnect (best effort);
- feature disable through the state-manager lifecycle;
- SIGINT, SIGTERM, normal return and exceptions.

There is an optional `trigger_reset_timeout_s` output-inactivity watchdog. It is
zero by default: native games may write an effect once and expect real DualSense
hardware to hold it. Normal game exit is detected through UHID lifecycle events,
which avoids truncating legitimate long resistance.

Some APEX 4 reconnects enumerate before their vendor command channel answers.
The identity gate remains closed and retries the read-only `0xEC` probe after
quiet 5/10/20/30-second backoffs. A parsed unsupported identity is terminal for
that device generation. Pending game effects also participate in the watchdog:
an effect that expires while identity is pending is discarded and cannot be
replayed after a delayed attach.

The 2026-09-21 revision makes freshness side-specific and gives queued
effects a two-second TTL even when the general inactivity timeout is disabled.
Only a valid mapped effect refreshes its side; LED, rumble, unknown effects and
the other trigger do not keep a stale side active. Local and SteamOS regression,
profile lifecycle and bounded dry-run validation pass; actual game and physical
feedback validation remain separate.

## Debug and dry-run

`--trigger-debug` prints only changed/unsupported effect decisions:

```text
DS5 R2: resistance type=0x21 start=2 end=9 strength=...
APEX4 R2: mode=1 params=(...) packet=05 a0 01 ...
```

`--trigger-dry-run` implies trigger diagnostics and disables all ForceAdapt
writes even if the config file enables them. It still creates the virtual
DualSense and runs the real report parser and translator.

For a standalone packet and identity check, `tools/forceadapt-test.py` is also
dry-run by default. `--write` is required for a real command; the tool exposes
only Normal and fixed mild/medium/strong resistance, limits duration to two
seconds, and always clears both sides in `finally`.

`--trigger-bounded-native-right` is the first capture-derived hardware
candidate. It uses semantic translation but permits only one R2 rattle to
resistance sequence, caps rattle strength/frequency to 32/21 and resistance
strength to 40, and applies one non-sliding one-second deadline to the whole
sequence. `native-dry-run` and `native-write` expose the same fixed wrapper
arguments. The write mode is not enabled by deployment and still requires
holder authorization.

The first authorized OW2 physical run of this candidate passed the mode-change
check: the holder felt mode 2 vibration and capped mode 1 resistance, while the
machine sent bilateral Normal at the shared one-second deadline. Game Off came
later, after the trigger was already Normal. A stronger post-release sensation
was traced to ordinary `(255,255)` motor rumble for about 0.13 seconds, not a
second ForceAdapt effect. Repeated cycles and Off clearing while active remain
outside this result.

The follow-up session candidate keeps those physical caps and permits three R2
cycles within 30 seconds. Game Off clears/rearms; a four-second cycle deadline
instead sends bilateral Normal and waits for Off, so repeated output cannot
extend a cycle. Captured-report replay passes and a fourth cycle is rejected.
`native-session-write` is installed but not enabled and requires a broader
holder authorization before it can change the remaining acceptance status.

That authorization and run are now complete. Three OW2 R2 actions each
produced rattle, capped resistance and game-Off Normal before the deadline;
the holder felt both modes in every cycle and confirmed normal trigger travel
after every release. No timeout clear substituted for Off. This completes the
bounded repeated R2 native-game acceptance for OW2 over 2.4 GHz. L2 in OW2,
cable repetition and unrestricted parameters remain separate boundaries.

The targeted USB-C/DInput regression now also passes one bounded semantic R2
cycle with holder-confirmed vibration, resistance and normal release. After
returning to Edge, all four paddles and a 10,000-frame live six-axis IMU run
passed. OW2 emitted no dynamic L2 in the validated scenario, so OW2 L2 is N/A;
existing synthetic/cable L2 mild evidence remains the transport-side check.

## Steam and games

Use **Steam Input Off** for the native test path. The game must see the virtual
DualSense/Edge and emit its own `0x02` trigger blocks. Steam Input On can replace
the device with an Xbox-shaped abstraction; it should not be expected to invent
DualSense adaptive resistance.

The acceptance chain is separate at each level:

1. unit/parser/packet tests;
2. dry-run sees a non-Normal effect and the intended `0xA0` packet;
3. the safe hardware tool produces mild resistance and auto-reset;
4. the relay drives left and right effects over both wired and 2.4 GHz;
5. a native DualSense PC game changes resistance dynamically and exit clears it.

Levels 1 through 4 are complete. On 2026-09-10 a SteamOS host passed all 46
unit/regression tests, created a virtual `054c:0df2` DualSense Edge, and
delivered a 48-byte USB output report through real `UHID_OUTPUT`. Dry-run
diagnostics decoded `DS5 R2` resistance and emitted the expected `05 a0 ...`
APEX 4 packet without touching the physical trigger. The standalone writer then
verified `04b4:2412`, usage page `0xFFA0`, DeviceType 84, firmware `6837` and
dongle transport. The user physically confirmed left and right mild resistance
through the actual relay, on the dongle and again over cable. Dedupe, explicit
Off, inactivity reset, SIGINT/SIGTERM and disconnect/reconnect cleanup passed;
an induced first identity timeout recovered in the same process after the
five-second backoff.

Level 5 has a constrained PASS as of 2026-09-20. After filtering the physical
pad, OW2/Proton Experimental emitted `0x26 -> 0x21 -> 0x05` R2 sequences for
ordinary DualSense; a clean Edge run emitted none. In the authorized hardware
test the relay replaced the first game effect with one fixed mild resistance,
the holder felt it, and the one-second timeout restored both sides Normal with
no write failure. This proves the native game-to-pad physical path, but not the
hardware behavior of OW2's original rattle/resistance parameters. See
[VALIDATION.md](VALIDATION.md) and the
[sanitized evidence](evidence/2026-09-20-ow2-native-game.txt).

## Provenance

Compatibility constants and direct semantic candidates are now documented
separately in [TRANSLATION.md](TRANSLATION.md). Production writes use the
accepted `ow2-safe` exact-pattern profile; the compatibility mapping is kept
for comparison/replay and cannot be selected by the named runtime config.
Captured OW2 full reports are replayed from
`tests/fixtures/ow2-hanzo-2026-09-21.json`; their dated context and limitations
are in
[2026-09-21-ow2-synchronized-capture.txt](evidence/2026-09-21-ow2-synchronized-capture.txt).

The game-specific translation table is adapted from the MIT-licensed
`mkaliaha/openflydigi` implementation at commit
`8477300f1bd0cdd0e4a277a544aa9b151c623e62`. `ReynArts/ApexSenseBridge` was read
only to corroborate public APEX 4 packet and hardware behavior. It is
GPL-3.0-or-later; no source from it is copied or mechanically rewritten here.
See `THIRD_PARTY_NOTICES.md`.
