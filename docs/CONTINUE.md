# Where this stands, and how to pick it up

> **2026-09-24：项目已终止。** [终止存档](PROJECT_CLOSURE.md)是当前状态入口；
> 以下交接和“Next steps”只作历史记录，不再授权继续部署、游戏启动或实体测试。

Written so that this can be continued cold — by a person, or by a model in a new
session with no memory of how any of it was found. Read
[PROTOCOL.md](PROTOCOL.md) for the pad, [DUALSENSE.md](DUALSENSE.md) for the
emulation side, and [DSX.md](DSX.md) for the implemented adaptive-trigger path
and its current hardware acceptance record. Use [VALIDATION.md](VALIDATION.md)
for the reproducible SteamOS test procedure and current evidence rules.

## 2026-09-23 交接补记

默认 Edge + 通用安全扳机方案见
[设计](superpowers/specs/2026-09-23-default-edge-generic-forceadapt-design.md)和
[实施计划](superpowers/plans/2026-09-23-default-edge-generic-forceadapt.md)。
本地已新增双侧 generic 翻译、独立时限 gate、可选 `generic-safe` profile、
固定且默认 dry-run 的晚间实体/虚拟向量；**配置默认仍是 disabled**，
SteamOS 当前安装及 OW2 启动选项没有迁移。软件可编码、硬件触感与原生游戏
输出分开判定；mode 3 和 Galloping/Machine 尚未开放。继续工作时先看本地
`git status` 和 SteamOS 实际状态，不从本节推断远端版本。2026-09-23 对
先前两个 Deck IP 的 SSH 只读尝试均超时，尚未盘点已安装游戏或 Proton 过滤。
同日后续 Deck 恢复可达，已只读完成远端源码/已安装服务/配置/游戏库存审计；
远端源码仍有用户改动，未触碰。首个独立候选在 SteamOS 全套测试中发现固定候选
预览会多余查询实体 `0xEC`，修正候选 `eb916a4` 的远端 175 项测试通过（1 项
环境 skip）。持握者切换陀螺开关并移动后 IMU 恢复，静置重力 1.00 g；公开
installer 已升级一次，但 `trigger_profile` 默认仍 disabled、现有配置字节不变。
Edge 和普通 DualSense 身份的真实 UHID dry-run 均得到同一有界 mode 1/2 与 Off，
未验收类型无写入，最终恢复唯一 Edge。没有启动游戏。之后在持握者明确授权下
执行了部分实体项：L2 mode 2 补测触感通过；L2/R2 单独 mode 1 写入与归零成功，
但持握者均未感到阻力，另有 L2 `(60,40)` 对照亦无触感。物理输入/效果时间戳
尚未完整对齐，旧 OW2 R2 序列正样本仍保留；不要推断 mode 1 的根因或默认开放。
mode 3 未发送，实体块已暂停。新增的同 fd `0xA0` echo 观察工具仅离线实现，
最新独立归档在 SteamOS 通过 186 项测试（1 项环境 skip），未执行新实体写入，
也未替换日常安装；默认仍 disabled。本轮只读枚举 Edge=0，不能称当前手柄在线，
但日常服务 active、手动服务 inactive。离线门禁见
[mode 1 软件证据](evidence/2026-09-23-mode1-observability-software.txt)。
详细负样本和机器结果见 [2026-09-23 证据](evidence/2026-09-23-generic-candidate-steamos.txt)。
实体步骤集中在 [VALIDATION.md](VALIDATION.md#2026-09-23-generic-safe-集中候选包尚未执行实体测试)，
但该初始包已部分执行且暂停；恢复前须先重审负样本、提出新范围并等待确认。

## What works today

The original development Apex 4 on its 2.4 GHz dongle, presented to games as a
DualSense:

* gyro on all three axes, analogue triggers, sticks, hat, face buttons, shoulders,
  stick clicks, Home as the PS button
* the four back paddles as real buttons, by presenting a DualSense **Edge** --
  same feature reports, one different product id, four bits in a byte already
  being written. Confirmed in Steam, which shows an Edge and binds all four, and
  now confirmed in the holder's hands on the SteamOS pad: each button lands on
  the Edge input in the same place, left to right in the player's frame. The
  pad's `M` labels are *not* in that order, so the list is not the naive one --
  [VALIDATION.md](VALIDATION.md)
* rumble in both directions, two motors independently
* survives the pad sleeping, being switched off and coming back
* native DualSense adaptive-trigger parsing, semantic normalization, APEX 4
  ForceAdapt translation, strict identity/command gates, deduplication, dry-run
  diagnostics and reset lifecycle; software tests, live UHID dry-run and actual
  left/right relay writes pass on SteamOS over the 2.4 GHz dongle and over cable
* settings in `~/.config/flydigi-apex4/config.json`; flags override it

The original development pad passes `./install.sh --check` with gravity reading
1.00 g, which exercises the whole input chain rather than a file list. A separate
SteamOS validation host passed `/dev/uhid`, vendor-node and DeviceType gates, over
both the dongle and cable, and its firmware/profile `6837` passes the gyro path
too -- an earlier session read a dead vendor sensor stream as an IMU failure; the
pad's gyro-mouse toggle was off, and the stream (and with it the virtual IMU) is
live again once it is on. `install.sh` now runs end to end on that host, with the
relay coming up as a user service and surviving a Gaming Mode reboot on its own.

## What does not

| | |
|---|---|
| Adaptive-trigger hardware | Live relay passes on dongle/cable; exact-pattern `ow2-safe` has repeated 2.4 GHz rattle→capped-resistance→game-Off physical PASS plus a bounded USB-C PASS. General/uncapped patterns remain unaccepted — [evidence](evidence/2026-09-21-bounded-native-session-physical.txt) |
| Native game under Proton | OW2/Proton Experimental emits `0x26 -> 0x21 -> 0x05` for ordinary DualSense but no action output for Edge under a clean comparison. The deployed opt-in wrapper passes a real OW2 Edge -> DualSense -> Edge session, and the holder confirmed normal menu control. Unrestricted game effects remain disabled — [evidence](evidence/2026-09-20-controller-profile-session.txt) |
| SteamOS firmware `6837` IMU | Passes once the pad's gyro-mouse toggle is on; the earlier zero-field captures measured the toggle being off, not a sensor fault — [VALIDATION.md](VALIDATION.md) |
| Back-paddle order | Resolved on the SteamOS pad 2026-09-11: `paddle_bits=2,3,4,5` was right, `paddles` was crossed and mirrored, and the labels are not in left-to-right order. Fixed and confirmed by the holder in Steam. The older development pad's `paddle_bits=3,5,4,2` came from a capture that did not record press order, so it may hide the same kind of error — [VALIDATION.md](VALIDATION.md) |
| Bluetooth | no gyro, no rumble, and it cannot be fixed: no vendor interface, and the pad only transmits on input change |
| Other old-dialect pads | Vader 3/4, Direwolf 3/4, Apex 3 share the framing; the constants are per-model and must be measured |

## Method, because the numbers are the product

Anyone extending this to another pad should copy the method, not the constants.

**Anchor to physics, not to your own hands.** Gyro scales were obtained by turning
the pad a full circle and integrating — but a hand-made turn is not exactly 360°,
so the number is only as good as the turn. Two of the three axes were re-anchored
against the accelerometer: rotating about any horizontal axis sweeps gravity through
the same angle, and that sweep is independent of how well the turn was made. It
came out at 365° and 359° for two axes, confirming both scales at once. Yaw cannot
be done this way — rotating about gravity does not move gravity — so it stays the
least certain number here.

**Fit, don't eyeball.** The accelerometer was calibrated by an axis-aligned
ellipsoid fit over 614k resting samples, using only the constraint that gravity has
one length. It found a per-axis scale (792.2 / 803.5 / 792.2 LSB per g) and, more
usefully, a −98 LSB offset on Y that hand-reading of static poses had estimated as
−57 from two poses whose magnitude was visibly wrong. Residual |a| = 1.0000 ± 0.0024.

**Signs are not derivable.** Handedness analysis tells you whether a pad's own axes
agree with each other; it does not tell you how they should land in a consumer's
frame. Two of the three derived signs turned out inverted in practice (roll's
happened to be right). Fix them in a game, or with Steam driving gyro-to-mouse —
a controller test page's icons are too small to see a sign error, which is how one
of them survived a whole session.

**Check the consumer you actually care about.** The kernel and SDL are different
readers of the same virtual controller and they disagree in both directions: SDL
applies calibration offsets the kernel throws away (which produced a phantom yaw
drift), and it parses the Edge's extra buttons that this machine's kernel never
registered on its evdev node. Testing through the kernel's nodes alone would have
called one of those a success and the other a failure, wrongly.

**Watch out for interpretation errors that look like hardware faults.** A battery
byte read as a percentage said "4%" for a session while the pad's own display showed
nearly full: it is a 0..5 level. And the pad's Y accelerometer offset means it reads
+0.12 g on Y while "flat", because it rests tilted back on its own curved underside.

## The measurement kit

`tools/`, all standard-library Python:

| Tool | Use |
|---|---|
| `selftest.py` | the whole chain, one command; also `./install.sh --check` |
| `apex4-probe.py` | list hidraw nodes, dump descriptors, flag the vendor collection |
| `apex4-raw.py` | capture a stream to a file (timestamp + payload) |
| `apex4-windows.py`, `apex4-classes.py`, `apex4-decode.py` | slice a capture by time, by frame class, or decode it under the known layout |
| `accel-fit.py` | the ellipsoid fit — feed it several captures |
| `apex4-gyroscale.py` | integrate rotations; `--` compares against the accel sweep |
| `tilt-analyse.py`, `pose-sign.py` | static poses, for scales and signs |
| `drift-check.py`, `ts-check.py` | is the gyro really zero at rest; does the DS5 timestamp advance at real time |
| `button-watch.py` | log evdev codes and vendor bits side by side — how the Home key and the paddle bit order were found |
| `motion-read.py` | read the kernel's DualSense motion node in physical units |
| `relay-path-watch.py` | read-only physical-vendor/virtual-DS5 paddle and IMU validation |
| `paddle-capture.py` | the same path, but one named button at a time, so the press order is recorded rather than assumed |
| `relay-trigger-test.py` | bounded, known mild/Off output through the virtual relay; dry-run unless `--write` |
| `ff-test.py`, `rumble-off.py` | rumble through the kernel; silence the motors |
| `forceadapt-test.py` | identity-gated, bounded ForceAdapt test; dry-run unless `--write` |
| `proton-game.py` | preview/apply game-scoped physical-device filters; optional OW2-only Edge -> DualSense -> Edge relay session |
| `windows-hid-probe.c` | read-only Windows enumeration/handshake; explicit selected-node mild/Off output through WriteFile or HidD_SetOutputReport |

A capture is worth more than a live experiment: the same recording can be re-sliced
when a hypothesis changes, and several of the findings here came from re-reading old
captures rather than taking new ones.

## Next steps, in the order they are worth doing

**Current delivery route (2026-09-21):** follow
[DELIVERY_PLAN.md](DELIVERY_PLAN.md). Complete one offline translation/safety and
capture-preparation batch, combine input-source diagnosis with one game dry-run,
then request a concrete physical test block. Stop iterating fixed mild timing
as the primary acceptance path. Xbox glyphs alone are not a blocker unless
input-path conflict is demonstrated.

Latest runtime `d98d88c` is deployed and the OW2 launch
option is `translation-dry-run`. It records full HID reports, compat/semantic
decisions and physical trigger positions, without ForceAdapt writes. Local
110/110 tests including the captured fixture and SteamOS 108 pass/1 compiler
skip for the deployed candidate are green. The first remote
smoke exposed a missing runtime import; it was regression-tested and corrected
before deployment. Input baseline found physical Flydigi, virtual Sony and a
resident Valve Xbox gamepad; Steam logs still show ForceOff and the Sony mapping
as non-XInput.

The synchronized game dry-run is captured in
`evidence/2026-09-21-ow2-synchronized-capture.txt`. During the holder's actions,
physical Flydigi and virtual Sony events were paired and the Xbox source emitted
none. Three `0x26 -> 0x21 -> 0x05` cycles began at R2=11..14, changed after
about 0.72 seconds at R2=129..255, and cleared at R2=0. This rejects the old
full-travel timing hypothesis. Complete raw reports are replayed by
`tests/fixtures/ow2-hanzo-2026-09-21.json`. Normal exit then left zero OW2 and
wrapper processes, daily active/manual inactive, one Edge, zero ordinary
DualSense and one relay. C is complete. Next prepare separate, explicit mode 2
and mode 1 physical authorization packages.

That D candidate is now implemented and deployed as `f3a1f57`. It uses the
semantic translator, permits one R2 game cycle, preserves mode 2 rattle at
`(0,1,32,21,0)`, caps the following mode 1 resistance to `(0,40,0,0,0)`, and
shares one non-sliding one-second deadline across both changes. Off clears
early; L2, other modes and later cycles are ignored. Local 117/117 and SteamOS
116 pass/1 compiler skip are green; captured-report replay under real
`native-dry-run` produced mode 2 -> mode 1 -> bilateral Normal. The installed
runtime is updated, but Steam remains `translation-dry-run`, native-write is
absent and adaptive=false. The next action is holder authorization for exactly
this one-cycle physical package; see
`evidence/2026-09-21-bounded-native-candidate.txt`.

The holder authorized and completed that package. OW2 produced mode 2
`(0,1,32,21,0)`, changed after 0.736 seconds to capped mode 1
`(0,40,0,0,0)`, and the shared one-second deadline sent bilateral Normal with
no write failure. The holder distinctly felt vibration and resistance. Game
Off arrived about 2.33 seconds after the safety Normal; immediately afterward
OW2 sent conventional rumble `(255,255)` for about 0.13 seconds, explaining the
reported stronger release vibration without a second trigger cycle. Exit
restored one Edge, and the holder confirmed normal final R2 travel with no
residual effect. The persisted option is back to translation-dry-run with
native-write absent and adaptive=false. Repeated cycles and active-effect Off
clearing remain separate acceptance questions; see
`evidence/2026-09-21-bounded-native-physical.txt`.

Accelerated follow-up `ded4178` is deployed but disabled. The new
`native-session-*` policy retains the accepted R2 mode caps, allows up to three
cycles in 30 seconds, gives each cycle one non-sliding four-second deadline and
requires game Off before rearming. Local 124/124 and SteamOS 123 pass/1 compiler
skip are green. Four captured cycles through the real virtual controller under
dry-run produced exactly three rattle/resistance/Off-Normal sequences and no
fourth non-Normal output. Steam remains translation-dry-run, session-write is
absent and adaptive=false. One explicitly authorized three-shot physical block
can now test repeated feedback and active-effect Off clearing together; see
`evidence/2026-09-21-bounded-native-session-candidate.txt`.

That physical block now passes. Three OW2 actions each produced mode 2, mode 1
and game Off -> R2 Normal in 1.30/1.39/1.84 seconds; no timeout, write failure,
wrong side or fourth cycle occurred. The holder felt vibration and resistance
in all three and confirmed normal R2 travel after every release. Exit restored
one Edge, and Steam is back to translation-dry-run with session-write absent
and adaptive=false. Stage D is complete for scoped 2.4 GHz OW2 R2 behavior.
Continue with E packaging/notices and consolidated regression; do not repeat
this physical block without a new reason. Evidence:
`evidence/2026-09-21-bounded-native-session-physical.txt`.

Stage E automation is now deployed as `8e159d7`. A temporary-prefix installer
test first reproduced missing LICENSE/notices, then passed after the installer
copied both exact files. Local 125/125 and SteamOS 124 pass/1 compiler skip are
green; the deployed notice files byte-match the validated archive. Installed
2.4 GHz self-test passes uhid, hid_playstation, writable uhid, DeviceType 84
dongle identity and 1.02 g sensor stream. Safe Steam settings remain unchanged.
The remaining holder work can be consolidated into one cable native sample and
one returned-Edge input/paddle/gyro/rumble regression instead of repeating 2.4
GHz trigger acceptance. Evidence: `evidence/2026-09-21-stage-e-packaging.txt`.

That final holder block passes. Wired DeviceType 84 self-test reached 1.00 g
after the documented pad-side gyro toggle; one bounded OW2 cable cycle produced
mode 2, capped mode 1 and bilateral one-second Normal, with both effects felt
and normal release confirmed. Exit restored one Edge and the safe option.
Returned-Edge paddles matched vendor `04/08/10/20` to virtual
`80/40/20/10`; a 10,000-frame motion run changed all accel/gyro axes. Final
state is one Edge/relay, no OW2, translation-dry-run, no write mode and
adaptive=false. This completed the pre-review E hardware regression, not the
production release gate described immediately below. Evidence:
`evidence/2026-09-21-stage-e-cable-regression.txt`.

Do not publish the earlier HEAD as production. Independent review found that
the accepted bounded semantic path differed from the public compatibility write
path, config truthiness could enable writes, and install/uninstall was not a
convergent writer-safe upgrade. Commits `85cb93b`, `9bf7a54` and `5d35156`
replace that with exact-pattern continuous `ow2-safe`, strict named config,
four-second per-cycle reset, a narrower mode allowlist/shared writer lock, and
an atomic restart/rollback installer. Local 145/145 and SteamOS 144 pass/1 C
compiler skip pass; the public installer upgraded successfully from the active
installation and migrated the existing false config to disabled. The pad is
currently absent, so the identity-gated five-cycle real-virtual dry-run stopped
before the manual relay. After the holder reconnects: run that dry-run, obtain
post-fix code/architecture review, then request one final production-profile
game block and explicit persistence/release decisions. Evidence:
`evidence/2026-09-22-production-hardening.txt`.

Offline hardening is now review-clean at `0691bac`: systemd query failures fail
closed, UHID lifecycle and verified physical reconnect reset only the continuous
OW2-safe gate, and bounded diagnostic disconnect latching remains unchanged.
Final local 148/148, py_compile, shell syntax, shellcheck and diff checks pass;
independent code review is APPROVE and architecture status CLEAR with no
remaining medium-or-higher/watch item. The Deck went offline before this final
archive could be installed. Tonight's remaining sequence is strictly:
install final archive -> controller-present five-cycle ow2-safe dry-run ->
holder-approved five-action OW2 production block -> exit/Edge recovery -> decide
whether to persist ow2-safe-write. No more offline design work or repeated mild
diagnostics is required.

Update after the first production block: do not persist or publish yet. The
holder's instructed five actions passed, but during five additional actions the
fourth/fifth sometimes fired about one second after physical R2 release. Machine
trigger sequences still showed ten valid rattle/resistance/game-Off cycles and
no write failure. The session synchronously logged 35,127 full HID lines and
16,987 repeated L2 unsupported lines because production write mode incorrectly
included hid/trigger debug. Steam was rolled back to translation-dry-run.
`c4f36af` removes both debug flags from write mode only; local 149/149 and
SteamOS 148 pass/1 compiler skip pass, and the quiet fix is installed but not
enabled. Next run must pair physical and virtual R2 timing with at least five
quiet production actions before reconsidering persistence. Evidence:
`evidence/2026-09-22-production-input-latency.txt`.

That synchronized quiet retest now passes. Ten physical R2 releases paired with
ten virtual Sony releases at 0.060..6.995 ms (3.249 ms mean), relay debug output
and write/timeout failures were zero, and the holder observed no delayed shot in
any of ten actions. Exit restored one Edge and the test-only production option
was rolled back to translation-dry-run. The latency regression is closed; the
only remaining decisions are whether to persist `ow2-safe-write` for OW2 and
whether to merge/push/create a PR/release. Do not infer those authorizations
from the successful test.

Final quiet enforcement is deployed: `ow2-safe-write` includes
`--quiet-output`, every live OW2-safe route overrides persisted verbose and
rejects verbose/HID/trigger debug, while dry-run diagnostics and unconditional
safety errors remain. Local 150/150 and SteamOS 149 pass/1 compiler skip are
green; final code review APPROVE and architecture CLEAR report no remaining
medium-or-higher/watch. The project has met its scoped technical production
goal. Current Steam state is intentionally still translation-dry-run with one
Edge; enabling `ow2-safe-write`, and merge/push/PR/release, each require the
user's explicit decision.

The previous `f213d72` bounded physical attempt produced successful
resistance/Normal writes but the holder felt nothing: physical acceptance FAIL.
Its early-trigger dry-run confirms only `0x26 -> fixed (60,40) -> Normal`; the
cause of failed perception is unproven. The holder reports Xbox glyphs
throughout. The newest exit check found the daily service active, manual service
inactive, and no OW2 process.

Remaining acceptance requires game-driven changes with documented translation
semantics and holder-confirmed effects, not just repeated fixed mild pulses.
Normal switching and observed direct-child recovery are verified scenarios;
do not extend these results to all Proton descendants or arbitrary failures.

### Earlier checkpoints and superseded next-step ordering

The following dated checkpoints preserve the development sequence. Their
deployment names and “next gate” text are historical; the route above takes
precedence.

**2026-09-20 review correction:** follow [RETROSPECTIVE.md](RETROSPECTIVE.md)
before the older steps below. First fix session signal windows, bounded process
cleanup, ownership/concurrency, and effect freshness/pending semantics. Then
validate translation properties and a policy that also runs in dry-run. Only
after these gates should new physical rattle/resistance tests begin. Normal OW2
exit and input passed; arbitrary failure recovery and sustained dynamic physical
feedback have not passed. Repeated fixed mild pulses are not the final goal.

**2026-09-21 deployed checkpoint:** G1/G2 fixes and the R2-only bounded
resistance policy passed SteamOS validation and are deployed as `dbde16f`.
The remote suite ran 96 tests (95 pass, one C-compiler skip). Normal and
SIGTERM-ignore child sessions restored a unique Edge; four virtual dry-run
cycles produced exactly three `(60,40)` resistance/Normal pairs. The OW2 launch
option now selects bounded dry-run. The policy still ignores rattle and L2,
allows at most three one-second cycles in a thirty-second window. The first OW2
dry-run proved the former ten-second window accepted only two of three
human-paced charges. The corrected `e2338b8` build passed three synthetic cycles
at seven-second spacing, rejected the fourth, and is deployed. A repeated actual
OW2 dry-run then accepted all three holder actions as `(60,40)`/Normal cycles
and restored a unique Edge after exit. The next gate is the first bounded
physical repeating-resistance test; every new physical write remains pending —
[evidence](evidence/2026-09-21-lifecycle-bounded-validation.txt).

The fixed `bounded-write` wrapper mode is implemented and deployed as
`4cf1515`; local 99/99 tests and SteamOS 98 pass/1 compiler skip are green.
It is not enabled: the persisted Steam option is still `bounded-dry-run`, there
is no `bounded-write` option in `localconfig.vdf`, and `adaptive_triggers=false`.
Enabling it now requires holder approval of R2-only mode 1 resistance,
`start>=60`, `strength<=40`, at most three one-second cycles in thirty seconds.

1. **Decide the remaining OW2 hardware-write boundary.** The opt-in launch wrapper
   now fails closed unless one installed Edge relay is active, switches to an
   ordinary DualSense, preserves the game exit status, and verifies Edge after
   cleanup. Normal, exit-17 and installed-path harmless-child runs passed on
   SteamOS with no ForceAdapt writes. Commit `b820aee` is deployed behind a
   recoverable old-install backup, and Steam retained the OW2
   `--relay-profile dualsense` option across its restart. A real OW2 launch then
   showed one ordinary DualSense during the game and restored one Edge after
   exit, with no duplicate relay or error; the holder then confirmed normal
   menu control. Keep full OW2 rattle/resistance writes pending until separately
   authorized and hardware-accepted. See
   [profile-session evidence](evidence/2026-09-20-controller-profile-session.txt)
   and [native-game evidence](evidence/2026-09-20-ow2-native-game.txt).
2. **Follow the corrected Proton workflow for other titles.** The 2026-09-11 masking experiment
   demonstrated device leakage, but did not resolve missing dynamic effects.
   On 2026-09-13 source review confirmed that Proton 10 winebus reads the SDL
   ignore list and supports `PROTON_DISABLE_HIDRAW` by VID/PID. First verify the
   installed relay and actual Proton build, then validate the game-scoped filter.
   The Windows probe, both output APIs and OW2 filter path now pass; repeat the
   same evidence sequence rather than assuming another title behaves identically.
   Initialization Off/LED packets have no writer PID in the relay log, so they
   must not be attributed to the game without additional evidence. Details,
   commands and pass/fail branches: [VALIDATION.md](VALIDATION.md#2026-09-13-proton-diagnostic-workflow).
   The 2026-09-20 local baseline passes 78 tests, Python compilation and shell
   syntax checks; the x86-64 Windows probe builds with warnings treated as errors.
   A first isolated-prefix run on Proton 11.0-2c now confirms filter propagation
   and Windows enumeration without the physical APEX. Proton renamed the virtual
   Edge to `Wireless Controller`, which the probe refused. Its new fallback
   requires an exact readback of the relay's sanitized pairing fixture; Windows
   verification of that fallback subsequently passed: four Feature Report calls
   and the Windows Input Report call succeeded. This was an isolated AppID=0
   prefix, still containing a Steam virtual gamepad. Both Windows output APIs
   subsequently delivered complete mild/Off reports to the dry-run relay and
   translated correctly. WriteFile reports 47 bytes for a complete 48-byte HID
   report; the probe now accounts for Wine's report-ID count convention. See
   [output evidence](evidence/2026-09-13-windows-output.txt) and the completed
   [OW2 comparison](evidence/2026-09-20-ow2-native-game.txt).
3. **Re-measure the older development pad's `paddle_bits` the same way.** The
   SteamOS pad's `2,3,4,5` turned out correct while sitting next to a wrong
   `paddles`, because the capture that produced it never recorded press order.
   The development pad's `3,5,4,2` came from the same kind of capture. Prompt for
   one named button at a time, record the physical position, and judge the result
   on Steam's front-facing test page -- a back view is mirrored and will confirm
   a wrong answer -- [VALIDATION.md](VALIDATION.md).
4. **Re-run the `6837` IMU monitor after any firmware or profile change.** It
   passes today, but only while the pad's gyro-mouse toggle is on, and that is a
   pad-side gate the monitor should keep watching for: a silent vendor stream is
   the first symptom, and it is easy to misread as a relay fault.
5. After the firmware-specific stream behavior is understood, revisit the SDL
   patch. `SDL_hidapi_flydigi.c` already opens the vendor interface but does not
   expose its sensors ([issue #10161](https://github.com/libsdl-org/SDL/issues/10161)).
   A patch must detect live motion rather than assume every APEX 4 stream updates.
6. Later, if wanted: a GUI whose value is *live sensor and button inspection* for
   measuring other pads (a settings panel would only duplicate the config file), a
   Decky plugin for handheld installs, and per-model constants for the other
   old-dialect pads.

## Environment this was developed on

* Bazzite (Fedora atomic), kernel 7.1.8, user `deck`, on a desktop machine.
* Pad on its 2.4 GHz dongle and, later, over a cable -- `04b4:2412` either way,
  firmware `04 15`, CPU `wch ch573`. The product string differs between the two
  ("Flydigi VADER3" vs "Flydigi APEX 4"), so match on ids, never on the name.
* Relay under `systemd-run --user`; logs in the user journal.
* An Apex 5 was **not** available. Where this document says something about the
  newer generation, it comes from openflydigi, not from measurement here.
* Additional adaptive-trigger acceptance: SteamOS kernel
  `6.16.12-valve24.5-1-neptune-616-gb2f7cfe85e45`, DeviceType 84, firmware
  `6837`, over both the 2.4 GHz dongle and cable. ForceAdapt passed on both
  transports, and the gyro path passes while the pad's gyro-mouse toggle is on
  -- the earlier "DInput IMU fields did not update" reading was that toggle
  being off, not a sensor fault.
* That SteamOS host has no `setfacl`, and `sudo` there wants a password.
* **The SteamOS host's own checkout is not this repository's tip.** As of
  2026-09-11 it sat at `8e0346c` with 25 uncommitted entries and remains
  deliberately untouched. The installed runtime is now a clean `b820aee`
  archive under `~/.local/share/flydigi-apex4/`; its previous contents are in a
  recoverable backup. Do not infer installed code from the dirty checkout.
* The paddle correction was applied to that host's
  `~/.config/flydigi-apex4/config.json` by hand, because an explicit `paddles`
  there overrides the code default; two timestamped backups sit next to it. The
  host therefore behaves correctly only while that file keeps the corrected
  list -- regenerating it from the legacy installation backup would bring the
  wrong mapping back.
* Device map on that host, dongle attached: `hidraw9` Game Pad (5 input items,
  **no** output item, so it cannot be rumbled), `hidraw10` gyro mouse,
  `hidraw11` `0xFFA0` (the relay's node -- IMU in, haptics out), `hidraw12`
  `0xFFEE` (has an output item), and the relay's virtual Edge on a node of its
  own. The relay needs only `hidraw11` and the pad's evdev node.
