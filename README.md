# flydigi-legacy-ds5

> **项目已于 2026-09-24 按所有者决定停止开发。** 当前代码与测试记录作为研究
> 存档保留，不代表通用自适应扳机已达到生产默认要求。请先阅读
> [终止存档](docs/PROJECT_CLOSURE.md)；下文为终止前的历史使用与验证说明。

Gyroscope and analogue triggers from a **Flydigi Apex 4** on Linux, by presenting
it to games as a DualSense.

Flydigi's older pads (Apex 3/4, Vader 3/4, Direwolf 3/4) carry a 6-axis IMU that
nothing on Linux reads. SDL recognises the Apex 4, its paddles and its rumble, but
not its sensors; Flydigi's own Windows app is the only thing that ever exposed
them, and openflydigi — the good Linux tool for these pads — covers the *newer*
protocol generation only. So the sensors sit in a vendor HID interface that is
already open and nobody parses.

This reads them and relays the pad into a virtual DualSense on `/dev/uhid`, where
the kernel's `hid-playstation` picks it up as a genuine PS5 controller. A game then
gets gyro, analogue triggers, rumble and translated native DualSense adaptive
trigger effects with no Steam Input in the path.

**The measurements are the point of this repository**, more than the code. The
code can be rewritten by anyone holding the pad; the constants took a session of
turning a gamepad in the air.

| Document | What is in it |
|---|---|
| [docs/PROTOCOL.md](docs/PROTOCOL.md) | the pad: interfaces, report map, command channel, calibration, what Bluetooth can and cannot do |
| [docs/DUALSENSE.md](docs/DUALSENSE.md) | the emulation side: uhid, feature reports, report layouts, rumble, udev, and the traps in each |
| [docs/DSX.md](docs/DSX.md) | adaptive triggers — report parsing, translation, ForceAdapt framing and safety |
| [docs/VALIDATION.md](docs/VALIDATION.md) | reproducible SteamOS hardware runbook, operator timing, evidence and PASS/FAIL rules |
| [docs/CONTINUE.md](docs/CONTINUE.md) | state of play, method, the measurement kit, next steps |

## Status

The original development pad works in daily use on the 2.4 GHz dongle and over
a cable. Specifically:

- gyro, all three axes, no enable command, gyro-mouse off, 1000 Hz
- analogue triggers, sticks, hat, face buttons, shoulders, stick clicks
- the four back paddles as **real buttons**: the relay presents a DualSense
  **Edge** by default, which has four buttons of its own, so Steam and games can
  bind them like any other. Plain DualSense is still available, and there the
  paddles fold into touchpad halves and stick clicks instead
- the Home key as the PS button (it is a Consumer-page usage, not a gamepad button)
- rumble both ways, two motors independently
- native DualSense adaptive-trigger report parsing and APEX 4 ForceAdapt
  translation. Unit/mock tests, live UHID dry-run, identity-gated standalone
  writes and the full relay path on both triggers are verified on SteamOS
  over the 2.4 GHz dongle and over cable. OW2 on Proton uses ordinary DualSense
  identity and the exact-pattern `ow2-safe` profile: repeated accepted
  rattle-to-resistance/Off cycles pass over 2.4 GHz and a bounded USB-C sample
  passes. General/uncapped translation and other game patterns remain unaccepted
- survives the pad sleeping, being switched off, and coming back
- on the second, SteamOS validation pad, gyro passes too. Its vendor sensor
  stream goes silent while its gyro-mouse toggle is off, which an earlier
  session misread as a sensor failure

Not done:

- **the older development pad's paddle bits**: the SteamOS pad's back-paddle
  order is fixed and holder-confirmed (the `M` labels are not in left-to-right
  order, and the old `paddles` default had them crossed and mirrored). The
  development pad's `paddle_bits` came from a capture that did not record press
  order, so it wants re-measuring the same way before it is trusted
- **Bluetooth**: buttons, sticks, hat and analogue triggers work; **gyro and
  rumble cannot** — there is no vendor interface over Bluetooth, and the pad only
  transmits on input change, so rotation alone sends nothing at all. The relay
  says so once at startup instead of pretending
- **other old-dialect models** (Vader 3/4, Direwolf 3/4, Apex 3) share the framing
  but need their own scales — `tools/` is how you measure them

## Requirements

Linux with `uhid` and `hid_playstation` (any kernel since 5.12; `install.sh`
loads `uhid` and makes it load at boot), `python3`, and
**no dependencies at all** — the whole thing is standard library, which is
deliberate: on an immutable distribution, a `pip install` line in the instructions
costs somebody an evening.

## Install

```sh
git clone https://github.com/Jackwmtr/flydigi-apex4-linux
cd flydigi-apex4-linux
./install.sh --check          # diagnose only, changes nothing
./install.sh                  # hides the physical pad from SDL by default
./install.sh --no-hide-pad    # keep the physical pad visible instead
./install.sh --desktop        # same, plus the two desktop launchers below
```

Upgrades stage and compile a complete runtime, stop both daily and transient
relay writers, atomically replace the installed tree, explicitly restart and
verify the service, and retain the previous runtime as a uniquely named backup.
If enable/restart fails, the installer restores that backup. Uninstall likewise
stops the transient writer before removing files.

`--check` is the part that matters on a machine that is not mine: it reports which
of the four things failed rather than "it does not work" — is the pad there and is
it this model, is the vendor node readable, is `/dev/uhid` writable, are the kernel
modules present. Then it brings a virtual DualSense up briefly and watches whether
the sensors move, so the whole chain is tested rather than the file list.

### On a Steam Deck

The same two commands, with three things that are specific to SteamOS and worth
knowing before you start:

* **`sudo` needs a password, and most Decks have none set.** Run `passwd` once
  first. Without it the udev rule cannot be installed, and that rule is what makes
  `/dev/uhid` writable — so the relay would have nothing to create its controller
  on. This is the one step that genuinely requires root.
* **A major SteamOS update can reset `/etc`**, taking the udev rule and the
  `modules-load.d` entry with it. Re-run `./install.sh` after one; everything in
  `$HOME` survives.
* **The rootfs being read-only does not matter.** Nothing is installed outside
  `/etc` and `$HOME`, so `steamos-readonly disable` is not needed.

Gaming Mode is fine: the relay is a user service and starts with the session.

Hiding the pad writes an `environment.d` file with both spellings of SDL's ignore
hint (SDL3 renamed it, and an application ignores the one it does not know). **It
is only safe together with the autostart unit**, which is why `install.sh` enables
that: with the pad hidden and the relay not running, there is no controller at
all. `--no-hide-pad` opts out.

**Verify these hints inside the actual Proton device service.** The physical pad
was still exposed in the captured game session. Valve's Proton 10 winebus does
read the SDL ignore list and supports per-device `PROTON_DISABLE_HIDRAW`; the
earlier assertion that Wine always ignores SDL hints was incorrect. The
game-scoped `tools/proton-game.py` previews filters by default and applies them
only with `--run -- %command%`. See the dated correction and Windows probe
workflow in [docs/VALIDATION.md](docs/VALIDATION.md#2026-09-13-proton-diagnostic-workflow).

In the tested OW2/Proton scenario, ordinary DualSense produced dynamic trigger
output while Edge did not. After installing this version, its per-game
Steam launch option can switch identities only for that process and restore the
normal Edge service afterward:

```text
/home/deck/.local/share/flydigi-apex4/tools/proton-game.py --run --relay-profile dualsense --relay-trigger-mode ow2-safe-write -- %command%
```

This exact installed path has completed a real OW2 launch with one ordinary
DualSense during the game and one Edge restored after exit. The holder also
confirmed that the controller operated the OW2 menu normally, closing the
user-facing input check as well as the machine-level lifecycle check.

The next generic-safe release will use the same wrapper for any game that
does not output to Edge, but with **identity-only** arguments:

```text
/home/deck/.local/share/flydigi-apex4/tools/proton-game.py --run --relay-profile dualsense -- %command%
```

That command already inherits the installed relay trigger profile; it does
not need an OW2 translator. It is a planned configuration, not the currently
accepted OW2 production option. The physical APEX 4 input filter and a real
Edge-output game still need SteamOS verification before generic-safe becomes
the installation default.

The `ow2-safe` profile is deliberately narrow: only the captured and physically
accepted Hanzo R2 vibration/resistance patterns are translated, strength is
capped, each cycle has a four-second deadline, and game Off is required before
the next cycle. Unknown effects and other games fail closed. Edge-only M1-M4
mappings are unavailable while OW2 sees the ordinary controller. Other games
stay on Edge unless separately validated and configured. If a wrapper is killed
with SIGKILL before cleanup, recover with:

```sh
systemctl --user stop apex4-relay-manual.service
systemctl --user restart flydigi-apex4.service
```

## Run

```sh
systemctl --user enable --now flydigi-apex4      # installed by install.sh
```

Or by hand, which is how you try things out:

```sh
./apex4-ds5 --write-config               # settings file, then edit it
./apex4-ds5 --dump                       # decode and print, create no device
./apex4-ds5 --calib                      # the constants, and what the served
                                         # DualSense calibration implies
./apex4-ds5 --paddles "paddle-right,paddle-left,fn2,fn1"
./apex4-ds5 --gyro-map "pitch,yaw,-roll" # a minus inverts that axis
./apex4-ds5 --trigger-dry-run --trigger-debug
./apex4-ds5 --trigger-dry-run --trigger-debug --hid-debug
./apex4-ds5 --emulate dualsense --trigger-dry-run --hid-debug # one-run identity comparison
./apex4-ds5 --emulate dualsense --trigger-profile ow2-safe
```

Settings live in `~/.config/flydigi-apex4/config.json` — which controller to
present (`dualsense-edge` or `dualsense`), paddle assignments, axis maps, report
rate, raw `paddle_bits` order, and the named `trigger_profile` (`disabled` or
`ow2-safe`). Older boolean `adaptive_triggers` files are migrated strictly:
JSON `false` becomes `disabled`, JSON `true` becomes `ow2-safe`, and strings are
rejected. Flags override the file, so anything can be tried without editing it.

Two different things decide where a paddle lands, and they are easy to confuse.
`paddles` says what each of the pad's `M1`..`M4` labels *does*; the labels are
**not** in left-to-right order (see [docs/PROTOCOL.md](docs/PROTOCOL.md)), which
is why the default list looks shuffled. `paddle_bits` says which vendor report
bit each label uses, and that varies by firmware/profile: the original pad uses
`3,5,4,2`, the SteamOS-tested one `2,3,4,5`, selectable with
`--paddle-bits 2,3,4,5`.

## Autostart, and switching it off for a minute

Two scripts in the repository root exist so that nobody has to remember systemd
details, and so that a controller can be handed back to the physical pad without
uninstalling anything:

```sh
./apex4-autostart on|off|status     # what the next boot does
./apex4-relay     start|stop|status # what happens right now
```

They stay independent on purpose. `./apex4-relay stop` silences the relay until
the next boot and leaves the autostart setting alone; `./apex4-autostart off` is
the one that decides what a boot does, and it stops the running relay as it goes
so the machine is never left half-configured. `./apex4-relay start -- <flags>`
runs the relay once with extra command-line flags — that is how the game-level
test drives a dry run without touching the settings file.

Autostart is a user service, `WantedBy=default.target`. That is what makes it work
on a Steam Deck: SteamOS logs the `deck` user in at boot, the user manager starts,
and the relay comes up with it — in Gaming Mode as well as on the desktop, and
after a full shutdown as well as a restart. `install.sh --desktop` drops two
launchers on the desktop that open these scripts in a terminal with a small menu;
they call the installed copy under `~/.local/share/flydigi-apex4/`, so they keep
working if the checkout is moved or deleted.

One interaction to keep in mind: with the pad hidden from SDL (the default), a
stopped relay means **no controller at all** — the physical pad is hidden and the
virtual one does not exist. Use `./apex4-relay start` to get it back, or
`./install.sh --uninstall` to go back to the pad alone.

## Adaptive triggers

For current acceptance limits and the remaining delivery work, see the
[delivery plan](docs/DELIVERY_PLAN.md) and
[translation profiles](docs/TRANSLATION.md). Fixed mild/early-trigger diagnostic
effects are retained as diagnostics and are not the production path.

Status: **implemented and safely hardware-verified on this Linux relay over the
2.4 GHz dongle and over cable**. A SteamOS host created the virtual DualSense
Edge, accepted synthetic native trigger output in live UHID dry-run, and
produced physically confirmed left- and right-trigger mild resistance through
the actual relay on both transports, each followed by Normal reset. Game-driven
effects now reach the pad from OW2 through the accepted `ow2-safe` profile:
repeated R2 mode-2 vibration changes to capped mode-1 resistance, game Off
clears and rearms the next cycle, and a four-second watchdog clears silence.
Three repeated 2.4 GHz actions and one USB-C action were physically confirmed
by the holder. OW2 emitted no action effects for Edge in a clean comparison, so
the wrapper temporarily uses ordinary DualSense. See
[docs/VALIDATION.md](docs/VALIDATION.md) and the
[three-cycle evidence](docs/evidence/2026-09-21-bounded-native-session-physical.txt).

The intended path is:

```text
Game -> virtual DualSense output report -> parser -> normalized effect
     -> APEX 4 translation -> identity-gated 0xA0 ForceAdapt write
```

Start with dry-run. It creates and runs the normal virtual controller, receives
the game's output, and prints the exact packet without writing a ForceAdapt
command to the pad:

```sh
./apex4-ds5 --trigger-dry-run --trigger-debug
```

For a holder-coordinated hardware proof within a mild-only authorization, the
one-shot mode requires ordinary DualSense and allows one fixed R2 mild effect
for at most one second before latching Normal:

```sh
./apex4-ds5 --emulate dualsense --trigger-one-shot-mild-right --trigger-debug
```

Preview the production OW2 policy without hardware writes with:

```sh
./apex4-ds5 --emulate dualsense --trigger-ow2-safe-right \
  --trigger-dry-run --trigger-debug
```

It accepts only the captured OW2 R2 rattle/resistance byte patterns, requires
their accepted order, caps rattle strength at 32 and resistance at 40, clears
after four seconds of silence, and requires Off before rearming. L2 and every
unknown effect are ignored. The installed wrapper exposes matching
`ow2-safe-dry-run` and `ow2-safe-write` modes for the per-game Steam option.

For a game with native DualSense support, set **Steam Input to Off for that
game**. Steam Input may wrap the virtual controller as Xbox; its Xbox-shaped
abstraction does not synthesize DualSense resistance effects. Seeing an APEX 4
or a DualSense in Steam is not by itself proof that the game emitted an effect.

Enable the accepted profile for one plain-DualSense run with:

```sh
./apex4-ds5 --emulate dualsense --trigger-profile ow2-safe
```

Or set `"trigger_profile": "ow2-safe"` together with
`"emulate": "dualsense"` in the config. `--adaptive-triggers` is retained only
as a deprecated alias for that same safe profile; it no longer selects the old
compatibility mapping. `--no-adaptive-triggers` selects `disabled`. Live
OW2-safe output forcibly disables verbose/HID/trigger debug logging even if an
old config has `"verbose": true`; write/reset/identity failures remain
unconditional. Use `--trigger-debug --hid-debug` only with dry-run diagnostics.

Hardware writes fail closed. The relay requires VID/PID `04b4:2412`, the
`0xFFA0` vendor collection, a valid read-only `0xEC` identity reply, a wired or
2.4 GHz connection, and the hardware-validated APEX 4 DeviceType `84` or `103`.
No other Flydigi model receives ForceAdapt packets. The only allowed live
command is `0xA0`; there is no arbitrary raw-command option.

The relay clears both triggers on startup/reconnect, explicit Off, UHID
`CLOSE`/`STOP`, vendor disconnect or write failure, feature shutdown, SIGINT,
SIGTERM and normal/exceptional exit. Identical effects are sent only once. The
OW2-safe profile independently enforces a non-sliding four-second active-cycle
deadline even if the general diagnostic `trigger_reset_timeout_s` is zero.

The bounded test tool is dry-run by default and offers only Normal plus three
fixed resistance levels:

```sh
python3 tools/forceadapt-test.py --side right --effect mild
# Stop the relay first, then perform the first real one-second test:
systemctl --user stop flydigi-apex4
python3 tools/forceadapt-test.py --write --side right --effect mild --duration 1
systemctl --user start flydigi-apex4
```

It verifies identity before a real write and restores both triggers to Normal
on completion, Ctrl+C, SIGTERM or exception. Bluetooth is unsupported because
it exposes no vendor interface. Bow/Galloping/Machine effects have documented
best-effort mappings to the nearest APEX 4 breakpoint/rattle vocabulary; unknown
or unsafe DualSense modes are ignored rather than guessed.

If the motors ever stick on: `tools/rumble-off.py` works with the relay stopped.

To undo everything: `./install.sh --uninstall`. It silences the motors first,
stops and removes the service (including names this project used earlier), deletes
the install tree, the settings file and the `environment.d` entry, and removes the
udev rule and the `modules-load.d` entry with the one `sudo` it needs. The `uhid`
module is left loaded, which is harmless — it just stops loading by itself. Restart
Steam afterwards so it sees the physical pad again.

## Not an Apex 4?

The framing in [docs/PROTOCOL.md](docs/PROTOCOL.md) is shared across the old
generation, but **the sensor scales are per-model** and differ by more than 3×
between axes on this one pad alone. Running with the wrong constants gives a gyro
that quietly lies, which is worse than one that does not work. `tools/` contains
what was used here: probe the interfaces, capture the stream, fit the
accelerometer, integrate known rotations for the gyro.

Patches adding a model are welcome; patches adding one *without* measured constants
are not.

## Credit

`apex4ds5/_ds5/` is vendored from [openflydigi](https://github.com/mkaliaha/openflydigi)
(MIT, Mikalai Kaliaha) — the `/dev/uhid` binding, the DualSense report codec and the
descriptors captured off real hardware. That project carries an inputtino attribution
  of its own; see `apex4ds5/_ds5/NOTICE`. The adaptive-trigger translation also
  uses openflydigi's MIT mapping; see `THIRD_PARTY_NOTICES.md`. Everything else
  here is MIT, see `LICENSE`.

Bug found in it while doing this, worth passing on: its `motion.py` hard-codes
`DS5_ACCEL_RAW_PER_G = 10000` citing inputtino, but the blob shipped in its own
`ds5_usb.py` — captured off real hardware — implies 8192, so its accelerometer
reads about 22% low.
