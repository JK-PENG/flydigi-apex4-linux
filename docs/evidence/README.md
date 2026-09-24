# Raw evidence

Primary captures kept so that a later session does not have to take the summaries
in [VALIDATION.md](../VALIDATION.md) on trust, and does not have to re-run a
hardware session to check them. Small on purpose: these are the windows that
carry the reported findings, not whole journals.

The host appears as `Machine` with user `deck`, which is how the journal writes
them. Credentials, addresses, MAC addresses and Steam account ids were scanned
for and are not present in any file here; the scan is part of the procedure, not
a one-off -- repeat it before adding another capture.

## 2026-09-11-relay-journal.txt

`journalctl --user -u apex4-relay-manual.service --since "2026-09-11 22:08:00"`
on the SteamOS host, covering the whole second native-game attempt. The relay was
running `--trigger-dry-run --trigger-debug --verbose`.

What it shows, and what the summaries claim:

- **68 `output report:` lines in total.** Grouped by their first four bytes:
  29 × `02 00 14`, 16 × `02 00 00`, 15 × `02 00 04`, 6 × `02 0d 17`, 2 ×
  `02 a0 80`.
- **Only the `02 0d 17` reports carry trigger blocks** (`valid_flag0 = 0x0d`,
  i.e. rumble + right trigger + left trigger valid), and every one of them is an
  attach-time initialization: both trigger types `0x05` (Off) with both motor
  bytes `0x00`. Six of them, one per relay restart or game attach; never an
  effect.
- The 60 reports starting `02 00` have no rumble/trigger bits in `valid_flag0`;
  the two `02 a0 80` reports also have no trigger-valid bits. Other flags may
  still select audio/LED behavior, so these are not globally "nothing valid".
- **No `rumble -> pad:` line anywhere**, so the relay never forwarded a rumble
  level. This is the line that makes the "the game was driving the physical pad,
  not the virtual one" conclusion checkable rather than asserted.

`DRY-RUN APEX4 ...` lines immediately before a report are the relay's own
lifecycle clears on attach/shutdown, not game-driven output; the `mode=0` is
Normal. Correction (2026-09-13): UHID output events do not contain the writer
PID. The capture proves host output reached the virtual device; it does not
attribute Off/LED initialization to Overwatch rather than Steam or a driver.
The later successful physical-device masking also did not produce dynamic
effects. Preserve the raw capture; use the corrected workflow in VALIDATION.md
before concluding a complete root cause.

## 2026-09-11-paddle-capture.txt

The read-only logger on both the vendor and virtual hidraw nodes during the
back-paddle capture, `journalctl --user -u apex4-padlog.service`. Each line is a
mask transition with a timestamp, so presses can be paired with what the holder
said they pressed.

The two conclusive rounds are at 22:09:06-22:09:13 and 22:09:14-22:09:22, and
they are identical:

```text
VENDOR 0x04 -> VIRTUAL 0x80  paddle-right
VENDOR 0x08 -> VIRTUAL 0x40  paddle-left
VENDOR 0x10 -> VIRTUAL 0x20  fn2
VENDOR 0x20 -> VIRTUAL 0x10  fn1
```

Earlier blocks in the same file are the runs that produced the wrong answer, and
are kept for that reason: 21:46-21:47 is the pre-fix mapping, and 22:00 is the
intermediate fix that mapped the buttons "left to right as seen from the back"
-- which passed its own machine check and was still mirrored. Both are worth
reading next to the final rounds.

## 2026-09-11-steam-controller-log.txt

`~/.steam/steam/logs/controller.txt`, filtered to the lines that name the Steam
Input state. `Opted-in Controller Mask Forced Off` / `Forced On` with timestamps
is how you tell from outside the UI what Steam thinks the per-title setting is,
and when it changed.

## 2026-09-11-steam-input-setting.txt

The `apps` block of `userdata/<id>/config/localconfig.vdf`, with the account id
left out of the filename. It is the on-disk counterpart to the log above and to
the enum table in VALIDATION.md:

```text
"2357570"  (Overwatch 2)   "UseSteamControllerConfig"  "0"   -> ForceOff
"3280350"                  "UseSteamControllerConfig"  "2"   -> ForceOn
```

The same file earlier in the session had Overwatch 2 at `2`, which is why the
troubleshooting notes say to re-check this value instead of trusting an earlier
run.

## 2026-09-13-windows-readonly.txt

Sanitized excerpt from the independent-prefix Proton 11.0-2c probe run, with
normalized Windows line endings and matching relay handshake lines. The pairing
template fallback accepted the Proton-renamed Edge. Four Feature Report calls
and the Windows Input Report call succeeded. Physical APEX enumeration was
absent, but a Steam virtual gamepad was present; this is not native-game or
Sony-only environment acceptance. No output-effect API was tested in this run.

## 2026-09-13-windows-output.txt

Subsequent Windows output tests against the dry-run relay. Both APIs delivered
complete 48-byte mild/Off reports. WriteFile's native success and 47-byte count
are separated from the probe's former synthetic error 29. The excerpt records
the count-check correction without relabeling the original probe result.

## 2026-09-20-ow2-native-game.txt

Clean single-relay Edge versus ordinary DualSense comparison plus the constrained
physical closure. It preserves the invalid-first-sample correction, representative
game effects, machine write/reset evidence, the holder's physical confirmation,
and the concurrent-relay defect that the process lock now prevents.

## 2026-09-20-controller-profile-session.txt

Software and non-game SteamOS evidence for the OW2-only profile wrapper. It
records preview non-mutation, the verified Edge -> DualSense -> Edge transition,
exit-code preservation, backed-up deployment, persisted Steam configuration and
the first actual OW2 automatic switch/restore session. Trigger writes remained
disabled; the holder subsequently confirmed normal OW2 menu control.

## 2026-09-21-lifecycle-bounded-validation.txt

SteamOS verification after the lifecycle review: regression tests, normal and
SIGTERM profile recovery, cycle-budgeted bounded R2 dry-run, atomic runtime
deployment and persisted Steam launch option. No game or physical trigger write
occurred in this evidence window.

## 2026-09-21-input-source-baseline.txt

Read-only baseline for the Xbox-glyph question. It records the simultaneous
Sony and Valve Xbox-style identities, OW2 ForceOff, Steam's non-XInput mapping
for the virtual DualSense, and the remaining limitation: retained logs do not
link every Steam controller index to the game input consumer.

## 2026-09-21-translation-candidate.txt

Comparison-only semantic translator, synchronized capture tooling, the failed
first remote smoke and its regression fix, corrected SteamOS validation,
recoverable deployment, and the persisted `translation-dry-run` launch option.

## 2026-09-21-ow2-synchronized-capture.txt

One no-write OW2 action block aligned physical R2 position, input-source
events, complete native DualSense output reports and compatibility/semantic
translation decisions. It records three `0x26 -> 0x21 -> 0x05` cycles, rejects
the full-travel timing hypothesis, and bounds the Xbox glyph observation to a
non-blocking UI behavior. The complete sanitized vectors are executable replay
data in `tests/fixtures/ow2-hanzo-2026-09-21.json`.

## 2026-09-21-bounded-native-candidate.txt

One-cycle R2 candidate derived from the synchronized capture. It documents the
semantic mode 2 to capped mode 1 sequence, shared one-second deadline, fixed
dry-run/write wrapper allowlists, local and SteamOS verification, recoverable
deployment, and the exact still-unapproved physical authorization boundary.

## 2026-09-21-bounded-native-physical.txt

The explicitly authorized one-cycle OW2 physical run. It preserves machine
timestamps for mode 2, capped mode 1, the one-second bilateral Normal, later
game Off, holder-confirmed vibration/resistance, the separately identified
post-release conventional rumble, exit recovery and safe launch-option rollback.

## 2026-09-21-bounded-native-session-candidate.txt

The accelerated three-cycle/Off-rearmed candidate. It records the fixed
four-second per-cycle, three-cycle/30-second bounds, the session-deadline reset
regression, local and SteamOS results, four-cycle virtual replay with the fourth
rejected, recoverable deployment and the exact unapproved physical boundary.

## 2026-09-21-bounded-native-session-physical.txt

The three-cycle OW2 physical acceptance block. It records all mode 2, mode 1
and game-Off/Normal timestamps, holder confirmation for both effects and normal
release, absence of timeout/write failures, three-cycle latching, normal exit
recovery and restoration of the safe launch option.

## 2026-09-21-stage-e-packaging.txt

Installer test-first repair for shipping LICENSE/notices, local and SteamOS
regression, byte-verified recoverable runtime deployment, safe final settings,
and the installed read-only 2.4 GHz identity/sensor self-test.

## 2026-09-21-stage-e-cable-regression.txt

USB-C/DInput identity and sensor preflight, bounded native R2 sample with holder
feedback, exit and safe-option restoration, exact returned-Edge paddle
sequences, and a 10,000-frame six-axis IMU motion capture.

## 2026-09-22-production-hardening.txt

Independent release BLOCK findings, fail-closed `ow2-safe` continuous profile,
strict config migration, restricted write surface, shared writer lock, atomic
installer/rollback behavior, local and SteamOS results, and the one remaining
controller-present five-cycle dry-run gate.

## 2026-09-22-production-input-latency.txt

Ten-cycle OW2-safe production run, the holder's preserved delayed-shot negative
result, 35k-line synchronous debug-log correlation, safe configuration rollback,
the quiet write-wrapper fix candidate and the required synchronized retest gate.
