# SteamOS hardware validation

This is the canonical runbook for proving the complete physical APEX 4 to
virtual DualSense path. It separates software checks, live read-only evidence,
bounded hardware writes, and native-game acceptance; passing one level never
implies that a later level passed.

## 2026-09-23 generic-safe 集中候选包（尚未执行实体测试）

后续更新：本节的初始授权包已**部分执行并暂停**。L2 mode 2 补测有触感；
L2/R2 独立 mode 1 均无持握者阻力反馈，mode 3 未发送。不得继续照本节命令
自动执行剩余实体项；先读[当日负样本](evidence/2026-09-23-generic-candidate-steamos.txt)，
核对实际输入/写入时序与手柄状态，重新提出有界授权包。

本地候选默认仍为 `trigger_profile=disabled`；此节不改变先前 OW2 验收。
`tools/forceadapt-test.py --candidate NAME` 与
`tools/relay-trigger-test.py --candidate NAME` 均默认预览；后者的 `--write`
写虚拟 DualSense 输出，若 live relay 选了实体 profile 也可能间接触发实体效果，
所以两种 `--write` 都要等持握者确认。`forceadapt-test.py` 的实体写入只经
`VerifiedTransport`，并持有 relay 互斥锁；`relay-trigger-test.py` 只接受唯一、
精确的本项目虚拟 Sony 身份，适合 relay 已运行时注入，不能同时抢 relay 锁。
固定候选的默认预览不打开实体节点或发送 `0xEC`，因此可与日常 relay 并行；
既有非候选 mild 预览仍执行只读身份检查。

| 固定候选 | 侧/模式 | 五字节参数 | 最长活动 | 清除 |
|---|---|---|---|---|
| `l2-rattle-32` | L2 / 2 | `00 01 20 15 00` | 1 秒 | 双侧 Normal |
| `l2-resistance-40` | L2 / 1 | `00 28 00 00 00` | 1 秒 | 双侧 Normal |
| `l2-breakpoint-20` | L2 / 3 | `3c 14 14 00 00` | 1 秒 | 双侧 Normal |
| `r2-breakpoint-20` | R2 / 3 | `3c 14 14 00 00` | 1 秒 | 双侧 Normal |
| `l2-resistance-hold15` | L2 / 1 | `00 28 00 00 00` | 15 秒 | 双侧 Normal |
| `r2-resistance-hold15` | R2 / 1 | `00 28 00 00 00` | 15 秒 | 双侧 Normal |

六项合计活动上限 34 秒，不包含每项前后的 Normal 与换线时间。长保持不是
既有一秒 mild 授权的延续，必须单独列在持握者确认包内。先在 2.4G 逐项，
如目标要同时声称 USB-C 通用支持，同晚对尚缺侧别/模式补有线证据；即使重复
全部六项，活动上限也为 68 秒。不要因为已有 OW2 R2 有线样本就推断 L2
rattle、mode 3 或 15 秒保持已在有线通过。任何异常触感、错误侧、写入失败、
Normal UNKNOWN 或恢复不唯一立即停止；未通过的 mode 不进入默认 release。

晚间执行前先做无需持握的只读预检：核对 SteamOS 安装版本/脏 checkout、
一份默认 Edge、当前配置仍 disabled、物理接口 DeviceType/连接、Steam Input、
Proton 物理设备过滤、已安装游戏及其中至少一个会向 Edge 发出原生扳机输出的
候选。若游戏候选缺失，实体模式块可独立完成，但默认 Edge 真游戏层为 UNKNOWN。
所有可能显示游戏的 Steam/Proton 命令另行提前通知并等待确认。

持握者同意上述精确侧别、参数、时长和自动清除后，停止 daily relay 并确认
独占锁，再对每个固定候选运行一次
`python3 tools/forceadapt-test.py --write --candidate NAME`；每项结束记录机器的完整 `05 a0` 写入/双侧 Normal
及持握者触感。别把工具退出 0 当作实体触感 PASS。完成后恢复唯一 Edge；
只有已通过的类别才进入下一轮真实虚拟 UHID dry-run 与游戏测试。注入工具另有
`l2-zone-rattle-32`、`r2-zone-resistance-40`、`l2-zone-weapon-20` 和
`r2-machine-unsupported` 固定诊断向量，最后一项必须无 ForceAdapt 写入。

### mode 1 后续诊断：完整私有输入时间线

本节是已批准的**离线采样方法**，不是新的实体写入授权。当前 mode 1 的
L2/R2 负样本仍有效、默认仍 disabled；继续任何写入前，必须重新说明侧别、
固定参数、时长、总预算及异常停止条件，等持握者明确确认。
`--observe-forceadapt-echo` 只对一个已命名固定候选或单侧 mild 生效，
必须同时显式 `--write`；它从同一已验证 fd **读取**已有 `0xA0` echo，
不发送额外命令。`A0_ECHO_OBSERVED` 不是固件应用效果或实体触感 PASS；
未观察到和读取失败分别记为 NOT_OBSERVED、UNKNOWN。

先在 Deck 的私有验证目录保存完整的物理输入，避免终端/工具结果长度上限再次
截断。`mktemp` 与 `umask 077` 保证原始文件仅当前用户可读写；不把完整输入、
设备地址或凭据提交到版本库。监视开始打印 `READY` 后，才通知持握者动作：

```sh
umask 077
APEX4_INPUT_LOG=$(mktemp "${XDG_RUNTIME_DIR:-/tmp}/apex4-input.XXXXXX")
set -o pipefail
python3 -u tools/input-source-watch.py --physical-only --seconds 120 \
  | tee "$APEX4_INPUT_LOG" | awk '/^READY/ {print; fflush()}'
stat -c '%a %n' "$APEX4_INPUT_LOG"  # 期望权限 600
```

在同一 Deck 上，用诊断工具实际打印的 `WRITE accepted t=` 与
`Normal reset complete t=` 填入 `APEX4_EFFECT_T`、`APEX4_NORMAL_T`。
下例筛选 R2 `ABS_GAS=0x009`；L2 改为 `ABS_BRAKE=0x00a`。一个完整周期必须
按顺序在**真实效果窗口内**出现低值、至少 64、再回到不超过 5；只有零星事件
或整条命令（含身份验证）时间窗都不能冒充重叠证据。

```sh
awk -v lo="$APEX4_EFFECT_T" -v hi="$APEX4_NORMAL_T" -v code='code=0x009' '
  $2=="source=physical" && $4==code {
    split($1,t,"="); split($5,v,"="); x=t[2]+0; y=v[2]+0
    if (x<lo || x>hi) next
    n++; if (n==1 || y<min) min=y; if (n==1 || y>max) max=y
    if (state==0 && y<=5) state=1
    else if (state==1 && y>=64) state=2
    else if (state==2 && y<=5) {cycles++; state=1}
  }
  END {printf "events=%d min=%d max=%d full_cycles=%d\n",n,min,max,cycles;
       if (n==0) exit 2}
' "$APEX4_INPUT_LOG"
```

只把事件数、范围、完整周期数与机器/持握者结论写入脱敏证据；若
`full_cycles=0`，触感阴性仍不足以诊断效果时机。读取失败、错侧、卡滞或
Normal UNKNOWN 必须停止，不按“没有感觉”直接提高强度或改游戏翻译。
上述 `awk` 在五条合成 R2 事件（`0,32,128,4,0`，时刻 `10.1..10.5`，
效果窗口 `10..11`）上得到 `events=5 min=0 max=128 full_cycles=1`；
错误侧或窗口外事件均以状态 2 退出。该离线验证只证明筛选逻辑，
不补足 2026-09-23 被截断的实机输入日志。

## Operator coordination and safety

Interactive hardware tests have two participants: the process operator and the
person holding the controller. Use this sequence whenever a person must press,
move, reconnect, or feel the pad:

1. State the exact action, side, effect strength, duration, and reset behavior.
2. Wait for an explicit ready response before starting the test.
3. Start long-lived capture first and print `READY`; only then tell the holder
   to act. Do not rely on a fixed countdown delivered through a chat UI.
4. Have the holder report completion or physical feel, then stop the capture.
5. Record both machine evidence and the holder's observation. Either one alone
   is insufficient for a physical-effect claim.

Never put SSH credentials, addresses, controller MAC addresses, or other local
secrets in committed logs. Stop any installed relay service before a foreground
relay so two processes never own the same physical output path.

The first real ForceAdapt write on a new controller/transport must be one side,
`mild`, about one second, with automatic Normal cleanup. The bundled tools cap a
single test at two seconds. Do not test medium/strong, rattle, breakpoint, raw
vendor commands, configuration commands, firmware commands, or factory reset
without separate protocol evidence and explicit authority.

## Acceptance levels

| Level | Evidence | Pass condition |
|---|---|---|
| 1. Software | unit/regression tests and syntax checks | every command exits 0 |
| 2. Virtual dry-run | real UHID output, parser, translation, packet log | correct side/effect; no physical ForceAdapt write |
| 3. Bounded hardware | `forceadapt-test.py --write` | identity accepted, holder feels only the requested side, Normal restored |
| 4. Live relay | virtual DS5 output through the real relay | physical side/effect, dedupe and every applicable reset path pass |
| 5. Native game | Steam Input Off, a PC game with native DualSense output | non-Normal game effect reaches the pad and game exit restores Normal |

Keep game validation last. A successful synthetic report proves the relay, not
that a particular Proton/game combination emits native DualSense effects.

## 1. Baseline and software gates

Preserve unrelated work before testing:

```sh
git status --short --branch
git diff --check
python3 -m unittest discover -s tests -v
python3 -m py_compile apex4-ds5 apex4ds5/*.py tools/*.py
sh -n install.sh
```

On the target Linux/SteamOS host:

```sh
./install.sh --check
python3 tools/apex4-probe.py
```

`--check` validates `/dev/uhid`, `uhid`/`hid_playstation`, the vendor node,
DeviceType, and gravity. Treat a bad gravity result as a real IMU failure even
when buttons and ForceAdapt pass. A preceding `0xEC` query can make some firmware
replies arrive late; the live relay stays fail-closed and retries silently
delayed identities with bounded 5/10/20/30-second backoff.

## 2. M1-M4: physical vendor to virtual Edge

Start the relay without adaptive-trigger writes. Use the measured bit order for
the controller/profile under test:

```sh
./apex4-ds5 --paddle-bits 2,3,4,5
```

Prefer the one-button-at-a-time capture. It prompts for a single named button,
waits for exactly that press, and records it, so the press order is measured
rather than assumed -- the assumption is what went wrong once already:

```sh
python3 tools/paddle-capture.py --paddle-bits 2,3,4,5 \
    --names "left of switch,right of switch,left grip,right grip" --rounds 2
```

`tools/relay-path-watch.py paddles --seconds 90` does the same path check with
less ceremony and is fine when you only need to know that four distinct
press/release pairs arrive:

```sh
python3 tools/relay-path-watch.py paddles --seconds 90
```

With `--paddle-bits 2,3,4,5` on a retail APEX 4, the measured non-zero sequences
are:

```text
vendor : 04 08 10 20
virtual: 80 40 20 10
```

Those virtual bits mean Edge paddle-right, paddle-left, Fn2 and Fn1. Require
four distinct press/release pairs in the virtual raw HID report. A lack of
events on the kernel's Edge evdev node alone is not a failure: some
`hid-playstation` versions do not publish the four Edge extensions there even
though the raw virtual HID report used by Steam contains them.

**The `M` labels are not in left-to-right order**, which the `paddles` list used
to assume. On an APEX 4 the player-facing order is `M2, M4, [power switch], M3,
M1`; the pad's own markings read `M1 M3 [switch] M4 M2` because they are read
with the pad turned over, and turning it over swaps left and right. A capture
that reads the markings from a back view therefore yields a **mirrored** mapping
that looks self-consistent and is still wrong. Decide the result on Steam's
front-facing test page, or by asking which hand reaches the button -- never on a
back view.

The **raw bit order is also not stable across firmware/profiles**: the original
pad reported labelled `M1..M4` as bits `3,5,4,2`, while the SteamOS-tested
firmware `6837` reports `2,3,4,5`. That difference belongs to `paddle_bits` and
is fixed with `"paddle_bits": [..]` or `--paddle-bits`; do not reorder the
user-facing `paddles` targets to hide a raw-layout difference.

## 3. IMU path

First test the physical vendor stream without enabling ForceAdapt:

```sh
python3 tools/relay-path-watch.py imu --seconds 30
```

When available, the tool also opens the same physical pad's interface-1 mouse
event node and reports `gyro-mouse X/Y events`; this is diagnostic only. After
`READY`, rotate and tilt the controller clearly without touching sticks,
triggers, or buttons. A pass requires at least one changing accelerometer axis
**and** one changing gyro axis in the documented fields. The printed nonconstant
raw offsets help distinguish a disabled sensor from a firmware layout move;
changing only mouse, button, stick, or counter data is not an IMU relay pass.

If the report is entirely static, first use
[Flydigi's documented calibration](https://help.flydigi.com/docs/fkx0zfqn0857a4qm):
hold `SELECT+START+Up` to enter, leave the pad level and untouched for at least
three seconds, rotate each stick twice, press each trigger through its range
twice, then short-press `SELECT+START+Up` to exit. Re-run the same capture after
calibration and after a power cycle. Do not treat a plausible static gravity
vector as live motion.

The next non-writing diagnostic follows the
[reported APEX 4 gyro-mouse toggle](https://github.com/libsdl-org/SDL/issues/10161):
start this monitor, wait for `READY`, short-press the small round/`+` button beside
Home once, and then rotate/tilt the pad. Press the same button again at the end to
restore its prior gyro-mouse state. If mouse X/Y events appear while vendor IMU
fields remain static, record that split result; it does not justify sending an
unknown sensor-enable HID command.

On the SteamOS validation pad, this toggle-on run is what restored the vendor
stream; the zero-field captures that looked like an IMU failure had been taken
with the toggle off.

Then run the relay and locate its `Motion Sensors` event node:

```sh
python3 tools/motion-read.py /dev/input/eventN 10
python3 tools/ts-check.py /dev/input/eventN 10
```

Require changing accelerometer/gyro events and a timestamp advancing at real
time. The original measured pad should read about 1 g at rest. If the physical
fields are zero, the virtual motion test cannot repair the failure.

## 4. Adaptive triggers

Start at Level 2, which writes only to the virtual controller:

```sh
./apex4-ds5 --trigger-dry-run --trigger-debug
# second terminal; --write here means virtual DS5 output, not a raw vendor write
python3 tools/relay-trigger-test.py --write --side right --repeat 5 --duration 1
```

The relay must print only one changed trigger decision for five duplicates and
the exact translated `05 a0 ...` packet, prefixed `DRY-RUN`. The physical
trigger must not change.

For the first direct hardware check, stop the relay and use the identity-gated
tool:

```sh
python3 tools/forceadapt-test.py --side right --effect mild
python3 tools/forceadapt-test.py --write --side right --effect mild --duration 1
```

Only after that passes, test the full relay through the single-cycle bounded
diagnostic; do not enable a generic compatibility translator:

```sh
./apex4-ds5 --emulate dualsense --trigger-one-shot-mild-right --trigger-debug
python3 tools/relay-trigger-test.py --write --side right --repeat 5 --duration 1
```

Repeat left and right separately. Verify initial Normal, exactly one physical
write for duplicate effects, explicit Off, the inactivity watchdog, SIGINT,
SIGTERM, virtual close, and disconnect/reconnect. A disconnect can make the
best-effort clear return `ENODEV`; that is acceptable only if the old fd is
closed and the new generation is identity-gated and initialized with both sides
Normal before any pending effect.

An effect received while identity is pending may be retained only while output
is still live. If it expires before identity succeeds, it must be discarded and
must not be replayed after a delayed attach.

## 5. Native game, last

Use a PC title documented to emit native DualSense adaptive-trigger reports.
Disable Steam Input for that title and run with `--trigger-debug`. Capture:

1. the game seeing the virtual DualSense/Edge;
2. a non-Normal `DS5 L2/R2` line;
3. the translated `APEX4 L2/R2` line;
4. physical confirmation of the matching trigger behavior;
5. explicit Off or lifecycle Normal after leaving the game.

Steam Input On may replace the controller with an Xbox-shaped device and is not
evidence that the game emitted DualSense effects.

The autostart path belongs to this level rather than beside it: switch the unit on
with `./apex4-autostart on`, reboot into Gaming Mode, and confirm the relay is
running and the virtual Edge exists **before** launching the title. Then run the
relay with one-off flags without disturbing that setting:

```sh
./apex4-relay start -- --trigger-dry-run --trigger-debug   # read-only half first
./apex4-relay start -- --adaptive-triggers --trigger-debug # real writes
```

Leaving the game, stopping the relay and pulling the pad must each end with both
triggers Normal; `./apex4-relay stop` is the cheap way to check that the virtual
controller really goes away with the process.

## Current SteamOS evidence (2026-09-10)

On a SteamOS kernel `6.16.12-valve24.5-1-neptune-616-gb2f7cfe85e45`, an APEX 4
DeviceType 84, firmware `6837`, produced:

- 46/46 unit and regression tests passing, on the development machine and on the
  Deck;
- the identity gate accepting both transports: over the 2.4 GHz dongle and over
  cable, with a wireless-to-wired hot plug leaving the relay and the virtual
  device running;
- physically confirmed R2 and L2 mild resistance through the live relay, on the
  dongle and again over cable, with single-side selection and automatic Normal
  reset;
- live deduplication through the real relay: three identical virtual-DS5 trigger
  reports produced exactly one physical write;
- a reproduced initial `0xEC` timeout followed by successful retry;
- M1-M4 vendor sequence `04/08/10/20` and virtual Edge sequence `40/10/20/80`
  passing with `paddle_bits=2,3,4,5`, so the raw order differs from the `3,5,4,2`
  the older pad uses -- but the holder reports the resulting order looks wrong in
  Steam's own controller test, so the label-to-button mapping stays an open
  question (2026-09-11 notes below) rather than a settled one;
- the virtual IMU path and the pose signs passing, and the virtual-DS5 timestamp
  advancing at real time (`tools/ts-check.py`, ratio ~0.996);
- `install.sh` run end to end on the Deck: vendor node, identity, gravity and
  `/dev/uhid` gates passed, the user unit was enabled, and the virtual DualSense
  Edge came up under `systemctl --user`.

The IMU result that an earlier session recorded as a failure needs its correction
kept: with the pad's gyro-mouse toggle **off** the whole vendor sensor stream is
zero, which is what those 6613/62191/61691-frame captures measured. Toggling the
small round button beside Home back on makes the fields update, and the relay
then serves a working virtual IMU with correct pose signs. A dead vendor stream
is therefore a pad-side gate, not a relay fault -- check the toggle before
concluding anything about the sensors.

## Gaming Mode and the first native-game attempt (2026-09-11)

The autostart level was verified by rebooting the same host into Gaming Mode
rather than logging in on the desktop:

- SSH answered 12 seconds after boot; `sshd` is explicitly enabled on that host
  (SteamOS leaves it off by default);
- the user unit `flydigi-apex4.service` was enabled and entered active at
  00:00:17, about six seconds into the boot, with `NRestarts=0`;
- the virtual DualSense Edge (`054c:0df2`, `DRIVER=playstation`) existed before
  any manual command;
- `loginctl` reported session 1 as `sddm-autologin` with `Desktop=gamescope`, so
  it was Gaming Mode and not the desktop session;
- `apex4-autostart.desktop` and `apex4-relay.desktop` were both on the Desktop
  and pointed into the installed tree under `~/.local/share/flydigi-apex4/`.

The native-game level was then attempted with Overwatch 2, Steam Input off
(`"UseSteamControllerConfig" "0"`), and the relay running one-off observation
flags (`./apex4-relay start -- --trigger-dry-run --trigger-debug`), which creates
the virtual device and prints what arrives without writing the pad:

- at 00:22:37 the game initialized both triggers with Normal (`0x05`) blocks:
  `DS5 R2: normal type=0x05` and `DS5 L2: normal type=0x05`;
- Wine's `winedevice.exe` held `/dev/hidraw13` and re-opened it later in the
  session, so the game's HID stack was really talking to the virtual device;
- after ten seconds of sustained fire plus a reload, the log still held only
  that Normal initialization pair: no weapon-class effect had ever been sent.

This is an unfinished attempt, not a pass: the game saw the controller and ran
its trigger-output path, but sent only Normal. Overwatch 2's trigger support is
listed as wired, and the virtual device already presents on the USB bus, so the
next checks belong to the game's own logic -- which button is fire, which
weapon, and its DualSense trigger setting. Forza Horizon 6 was set aside for
this level: its PC build does not emit native DualSense trigger reports.

That reading turned out to be too generous. A second attempt the same day, with
the relay's `--verbose` flag on, is recorded below.

### Level 5 is blocked by device exposure, not by the game (2026-09-11)

> Historical interpretation, corrected 2026-09-13: device leakage was real,
> but masking did not fix effect output. The claim that winebus never consults
> SDL hints is false for the reviewed Proton 10 build. Off/LED packets were not
> attributed to a writer. See the current workflow at the end of this document.

The attempt was repeated with `--trigger-dry-run --trigger-debug --verbose`,
which prints *every* output report the virtual device receives, not only changed
trigger decisions. Steam Input was verified off for the title
(`UseSteamControllerConfig` = `0`, ForceOff) and the in-game setting
`启用DUALSENSE无线控制器扳机效果` ("Enable DualSense Trigger Feedback") was on.
The holder charged Hanzo's bow repeatedly in the practice range.

Across the whole session the virtual DualSense received 24 output reports:

- 21 with `valid_flag0 = 0x00` -- nothing valid, lightbar-class traffic;
- 1 player-LED/brightness setup;
- exactly 2 carrying trigger blocks, both the same attach-time initialization
  that sets both triggers to `0x05` (Off) with both motor bytes `0x00`.

No rumble ever reached the virtual pad. The holder felt rumble throughout and --
the decisive part -- **could still play, and still felt rumble, after the relay
was stopped and the virtual device had disappeared**.

The only path to this pad's motors is its vendor HID interface, so something
other than the relay was writing it. Wine was exposing the physical pad
directly: `winedevice.exe` held `hidraw9` (its Game Pad collection, 5 input
items and **no** output item), `hidraw10` (mouse), `hidraw11` (`0xFFA0`) and
`hidraw12` (`0xFFEE`) for the whole session.

`install.sh --hide-pad` writes SDL ignore hints only. Those cover SDL, which is
what Steam and native games use, but **Wine's `winebus` enumerates
`/dev/hidraw*` itself and never consults them**. Under Proton the game therefore
sees two controllers -- the physical APEX 4 and the virtual DualSense -- and this
title drove the physical one, leaving the virtual DualSense with nothing but a
defensive trigger init.

So level 5 is not blocked by the game's trigger logic, and not by Wine dropping
writes. It is blocked by the physical pad leaking through to the game. Whatever
is tried next has to hide the pad from Wine too. The relay itself needs only the
`0xFFA0` vendor node (IMU and haptics) and the pad's evdev node (sticks,
triggers, buttons), so masking the Game Pad and mouse hidraw nodes should leave
it working -- but that is a change to device permissions and belongs in a
decision, not in a runbook step.

### Back-paddle order, resolved (2026-09-11)

The order the holder reported as wrong was captured one labelled button at a
time on the retail pad, with the relay running live and a timestamped read-only
logger on both hidraw nodes. Pressing `M1`, `M2`, `M3`, `M4` in order produced
vendor bits `0x04, 0x08, 0x10, 0x20`, so `paddle_bits=2,3,4,5` was correct all
along; the fault was in `paddles`.

The labels are not laid out left to right. On this pad, in the player's
left-to-right order, the four buttons are `M2` (outer, left grip), `M4`, the
power switch, `M3`, `M1` (outer, right grip). The default `paddles` list had
been built on the assumption that the index ran left to right, so the mapping
came out crossed and mirrored.

The fix is one line: `paddles` becomes
`["paddle-right", "paddle-left", "fn2", "fn1"]` (was
`["paddle-left", "fn1", "fn2", "paddle-right"]`).

Verified on the same host, same pad, two consecutive rounds:

```text
22:09:06  VENDOR 0x04 -> VIRTUAL 0x80  paddle-right
22:09:09  VENDOR 0x08 -> VIRTUAL 0x40  paddle-left
22:09:11  VENDOR 0x10 -> VIRTUAL 0x20  fn2
22:09:13  VENDOR 0x20 -> VIRTUAL 0x10  fn1
22:09:14..22:09:22  identical second round
```

and then by the holder on Steam's own front-facing controller test: reaching
with the left hand to the left grip button now lights the left side, and the
whole chain runs left to right in the player's frame.

Two things this cost, worth not repeating:

- An intermediate fix that mapped the buttons left-to-right **as seen from the
  back** passed the machine check and was still mirrored. The back view swaps
  left and right, so it cannot be used to decide this mapping.
- The earlier session's `04/08/10/20` reading was taken with the holder pressing
  in an unrecorded order, which is why a correct `paddle_bits` sat next to a
  wrong `paddles`. Prompt for one named button at a time and record the physical
  position, not just the bit.

The virtual bits still do not run `paddle1..paddle4` in screen order, and should
not: SDL numbers the Edge paddles by hand (`paddle1` = right, `paddle2` = left,
`paddle3` = right Fn, `paddle4` = left Fn), which is its own convention. Judge
this mapping by physical position, not by the numbers.

### Hiding the pad from Wine works (2026-09-11)

The masking idea above was tried, reversibly: `chmod 000` on the pad's `hidraw9`
(Game Pad), `hidraw10` (mouse) and `hidraw12` (`0xFFEE`), then on `hidraw11`
(`0xFFA0`) as well -- the relay already had `hidraw11` open, so the `chmod` stops
new opens without disturbing the running relay. There is no `setfacl` on the
host, but `chmod 660` restores the original mode and re-enables the access ACL,
and a dongle replug or a reboot restores everything anyway.

With all four nodes blocked, Wine's device process held only the virtual
DualSense and unrelated peripherals -- no physical pad node at all -- and the
game moved to the virtual pad:

- the holder could walk, aim and fire normally, which is only possible if the
  game was reading the relay's virtual DualSense;
- the game set the lightbar and initialized both triggers to `0x05` over the
  virtual device, i.e. it drove it as a DualSense rather than as a generic pad.

So the device-exposure problem is real, and this is a working way around it. It
is not applied anywhere: it changes device permissions, needs root, and the
relay keeps the vendor node only because it already had it open, so a pad
reconnect needs the permission restored and the relay restarted. Any real fix
belongs in `install.sh`/udev with that reconnect case handled.

What it did **not** fix: Overwatch 2 still sent nothing to the virtual pad after
its attach-time initialization -- no rumble during sustained fire and no trigger
effect, with `--verbose` showing an empty report stream, and the same with the
in-game 震动 and 启用DUALSENSE无线控制器扳机效果 settings toggled off and on
again. One reading, untested: on PC the DualSense's haptics are audio-endpoint
based, and a UHID device exposes no audio function, so a title may detect a
DualSense, set it up, and then send no haptics at all. That would explain the
missing rumble but not the missing trigger effects, which are plain HID output
reports.

## Level 5 troubleshooting notes

Four things that cost time here and are cheap to check first. The raw captures
behind the claims above are kept in [evidence/](evidence/README.md) -- the relay
journal, the paddle logger and the Steam-side values -- so they can be checked
without booking another hardware session.

### Steam Input for the title must be off, and it does not stay off

Steam keeps the per-title setting in `userdata/<id>/config/localconfig.vdf`,
under `apps -> <appid> -> UseSteamControllerConfig`. The values are not
guessable; this mapping comes from the me3 project
(`crates/cli/src/commands/launch/steam.rs`), which deserializes exactly that key
with `serde_repr`, so the integers are the discriminants:

| Value | Meaning |
|---|---|
| `0` | ForceOff |
| `1` | Default |
| `2` | ForceOn |

At `2` Steam takes the DualSense and hands the game an Xbox-shaped device, so the
game never sees a DualSense and no amount of game-side fiddling will help. It was
found back at `2` partway through this work after having been set to `0` earlier,
so check the current value instead of trusting an earlier run. Steam's
`~/.steam/steam/logs/controller.txt` records the transitions as `Opted-in
Controller Mask Forced Off` / `Forced On` with timestamps.

### `--verbose` is how you tell "the game sent nothing" from "the relay ignored it"

`--trigger-debug` prints only changed trigger decisions, so a silent log is
ambiguous -- that ambiguity is what produced the wrong conclusion on the first
attempt. `--verbose` prints every output report the virtual device receives,
before any parsing:

```sh
./apex4-relay start -- --trigger-dry-run --trigger-debug --verbose
```

At the time of that capture it printed `output report: <first 16 bytes>` and
`rumble -> pad: left N right N` when a level is forwarded. Byte 1 of a `0x02`
(USB) report is `valid_flag0`: bit 0 rumble, bit 2 right trigger, bit 3 left
trigger. Reports with `valid_flag0 = 0x00` carry nothing and are usually lightbar
traffic. Note the truncation: `payload[:16]` covers the right trigger block but
not the left, which starts at common byte 21. Since 2026-09-13 `--verbose`
prints the complete report; `--hid-debug` additionally logs the UHID route and
GET/SET_REPORT results. Do not infer writer identity from either log.

### Most Overwatch 2 weapons have no trigger feedback at all

From Blizzard's own patch notes (2023-10-31, "Rumble Updates"), trigger feedback
hangs off named abilities rather than off firing:

- Hanzo -- Bow charge (hold primary fire; the easiest one to observe)
- Roadhog -- Chain Hook activation, impact and retraction
- Winston -- Primal Rage punch hit
- Genji -- Dragonblade swing hit
- D.Va -- Defense Matrix, Boosters
- Mercy -- Caduceus Staff secondary fire, Caduceus Blaster
- Reaper -- Shadowstep

Everything else was given rumble only, so "held fire for ten seconds and saw
nothing" is the expected result and says nothing about the relay.

### Verify SDL's Edge numbering on the host rather than trusting this document

Steam loads its own SDL3 rather than the system one, so the library that matters
is the one the Steam client has mapped:

```sh
grep -o "/[^ ]*libSDL3[^ ]*" /proc/$(pgrep -f 'steam ' | head -1)/maps | sort -u
strings -a <that path> | grep -c 'paddle1:b16,paddle2:b15,paddle3:b14,paddle4:b13'
```

A hit means that build numbers the Edge paddles `paddle1` = right rear,
`paddle2` = left rear, `paddle3` = right Fn, `paddle4` = left Fn. SDL3's
`SDL_gamepad.h` names them by hand and calls the Edge out explicitly, which is
why the numbering looks shuffled next to a left-to-right reading of the pad.

## 2026-09-13 Proton diagnostic workflow

本节替代前文“隐藏物理手柄即可解决 Level 5”的推断；原始采集和历史实验保留。
屏蔽物理设备确实改变了游戏输入来源，但屏蔽后仍未观察到动态扳机报告。
主机发出的 Off/LED 初始化没有写入者 PID，不能据此归因到游戏。

源码复核依据是 Valve Wine `proton_10.0` 的提交
`b8fdff8e1f855b5276ec4ddca0f31b2792554322`：

- [bus_udev.c](https://github.com/ValveSoftware/wine/blob/b8fdff8e1f855b5276ec4ddca0f31b2792554322/dlls/winebus.sys/bus_udev.c#L1738)
  在创建设备前调用 SDL 忽略列表检查；“winebus 永远不读取 SDL 变量”不成立。
- [main.c](https://github.com/ValveSoftware/wine/blob/b8fdff8e1f855b5276ec4ddca0f31b2792554322/dlls/winebus.sys/main.c#L543)
  支持按 VID/PID 设置 `PROTON_DISABLE_HIDRAW`，无需更改 Linux 设备权限。
- [Proton #8672](https://github.com/ValveSoftware/Proton/issues/8672) 记录过环境变量未传到
  服务进程的问题，所以必须核对实际 Proton 构建和 Wine 设备进程的有效变量。
- [Proton #5900](https://github.com/ValveSoftware/Proton/issues/5900) 区分 HID 扳机与四声道
  触觉音频。缺少音频端点尚不是 OW2 扳机失败的已证实根因；USB/IP 留作后备方案。

### 1. 固定运行基线和过滤范围

先检查远端 checkout、安装目录和服务 `ExecStart`，保留未提交改动和现有背键配置。
`apex4-relay` 优先选择安装目录中的程序，因此从 checkout 调用脚本也可能运行旧代码。
必须将已审查的改动同步到实际执行目录，再启动诊断。

游戏启动入口新增 `tools/proton-game.py`，默认只预览过滤后的变量：

```sh
python3 tools/proton-game.py
```

在 Steam 的本游戏启动选项中使用以下模板，替换绝对路径并保留已有启动包装器：

```text
/absolute/path/tools/proton-game.py --run --debug -- %command%
```

OW2 已证明普通 DualSense 有动态输出而 Edge 没有。安装包含 profile-session 功能的版本后，
该游戏可把模板改为以下形式；其他游戏不应未经对照就照搬：

```text
/home/deck/.local/share/flydigi-apex4/tools/proton-game.py --run --relay-profile dualsense -- %command%
```

默认 `relay-profile=unchanged`，原有包装器行为不变。`dualsense` 模式要求启动前只有已安装
Edge 服务运行，拒绝与 `--probe` 组合；确认临时 `054c:0ce6` 后才启动游戏，游戏退出或
包装器在子进程等待阶段收到 SIGINT/SIGTERM 时会转发信号；子进程退出后尝试停止临时
relay、启动日常服务并确认 `054c:0df2`。进入/恢复阶段信号处理与异常清理仍有缺口，见
[复盘](RETROSPECTIVE.md)，不能声明任意阶段均自动恢复。它不改变
`adaptive_triggers`，也不授权真实扳机写入。SIGKILL 无法被同进程捕获，恢复命令为：

```sh
systemctl --user stop apex4-relay-manual.service
systemctl --user restart flydigi-apex4.service
```

工具保留已有 VID/PID 名单，只加入物理 `0x04b4/0x2412`。若已有白名单，会移除其中的
物理 APEX 4；若配置会阻断虚拟 Sony 身份则拒绝启动并提示人工检查。它不修改文件权限、
注册表、持久配置或 relay 服务。移除本次启动包装器即可回退。

`--debug` 请求 `PROTON_LOG=+hid,+plugplay`；只采集短窗口，以免输入日志过大。
在 Wine 的枚举日志和 Windows 探针中确认物理 APEX 4 不再暴露为可用设备，且虚拟
`054c:0ce6` 或 `054c:0df2` 存在；仅看到进程曾打开某 hidraw 节点不足以判定枚举结果。
特别检查实际 `winedevice.exe` 环境是否收到以下三个键，不要导出完整环境或凭据：

```text
PROTON_DISABLE_HIDRAW=0x04b4/0x2412
SDL_GAMECONTROLLER_IGNORE_DEVICES=0x04b4/0x2412
SDL_JOYSTICK_IGNORE_DEVICES=0x04b4/0x2412
```

### 2. 在同一 Proton 启动链中运行 Windows 探针

`tools/windows-hid-probe.c` 是独立实现的 Windows C 程序，无第三方运行库依赖。
开发机可用 MinGW-w64 编译；Zig 也可交叉编译，编译器不属于 relay 的生产依赖：

```sh
mkdir -p build
x86_64-w64-mingw32-gcc -std=c11 -O2 -Wall -Wextra -Werror \
  tools/windows-hid-probe.c -lsetupapi -lhid -o build/windows-hid-probe.exe
# 或：zig cc -target x86_64-windows-gnu，加上相同的源文件、选项和库
```

本地已用 Zig 0.16.0 生成 x86-64 PE 文件；`build/` 被 git 忽略，需单独将 exe 同步到
SteamOS。源码入库，二进制不提交。已有 Python 测试会用宿主 C 编译器运行同一源文件的
portable 部分，交叉检查四组输出字节和设备选择限制；这不是 Windows 运行验证。

先启动只打印扳机结果的 relay：

```sh
./apex4-relay start -- --trigger-dry-run --trigger-debug --hid-debug
```

临时把本游戏启动选项设为：

```text
/absolute/path/tools/proton-game.py --run --debug --probe /absolute/path/windows-hid-probe.exe -- %command%
```

它保留 Steam 原有运行时、Proton 和游戏 prefix，只把识别到的 `proton run` 或
`proton waitforexitandrun` 的目标替换成探针，去掉原游戏参数；无法识别启动链时直接报错。
此时点击游戏的“启动”会运行探针，不会进入游戏。将 `--probe` 及参数移除可恢复。

默认探针只读：列出 Windows HID 枚举身份、报告长度，并读取本项目虚拟设备的已知
Feature Report 和 Input Report。它不打印设备路径、序列号或 Feature 数据。某个
`HidD_GetInputReport` 失败会明确显示；本 relay 尚不实现该快照请求，不能据此单独
判定流式输入失败。默认进程退出 0 仅表示枚举完成，须逐项检查 `RESULT`。

只有显式 `--write --device N` 才会发出固定 mild/Off 输出。N 来自本次只读枚举；
目标必须同时匹配 Sony VID/PID、游戏手柄 usage 和 48 字节输出长度；产品名须为本 relay
的名字，或在 Proton 改名为 `Wireless Controller` 时，读取 `0x09` 并逐字节匹配本项目
公开的去标识化配对模板。通用 Sony 名字本身不允许写入，模板内容也不会打印。
真实 Sony 手柄和 Flydigi 原始接口均会被拒绝。一次选择一侧和一种 API：

```text
windows-hid-probe.exe --device N --write --side right --method writefile
windows-hid-probe.exe --device N --write --side right --method setoutput
```

通过 Steam 包装器传参时，分别追加 `--probe-arg=--device --probe-arg=N`、
`--probe-arg=--write --probe-arg=--side --probe-arg=right`、
`--probe-arg=--method --probe-arg=writefile`（或 `setoutput`），放在 `-- %command%` 前。
首次始终配合 dry-run relay；真实触感测试另等持握者确认。

每次 mild 后约一秒尝试 Off；Ctrl+C 会提前进入 Off。API 超时会取消调用；Off 失败时
尝试另一条已知输出 API。取消失败会返回 3 并明确记录 reset UNKNOWN，此时必须通过
relay 停止/复位处理，不能声称自动 reset 已成功。

成功要求：Windows API 返回成功，relay 的 `HID OUTPUT` 或 `HID SET_REPORT` 捕获了同样
的完整字节，`DS5 R2` 非 Normal 转译与随后 Off 均出现。只得到 `WRITE_TEST applied=1`
不能宣称真实扳机通过。

### 3. 游戏对照及后续分支

先记录 Steam/relay 空闲窗口，再启动游戏，保持过滤、Proton 构建和半藏蓄力动作一致。
新增 `--emulate dualsense` 可临时切换普通 DualSense 身份，不覆盖配置文件；普通型号没有
Edge 扩展按键，测试期间背键对应功能不可作为该身份的验收目标。

```sh
./apex4-relay start -- --emulate dualsense --trigger-dry-run --trigger-debug --hid-debug
```

| 观察 | 下一步 |
|---|---|
| Windows 探针看不到虚拟 Sony 设备 | 排查过滤变量、Proton 枚举、实际运行代码与权限 |
| Linux 注入通过，但 Windows 某条 API 失败或无对应 UHID 输出 | 沿该 API 的 Wine/Proton 日志定位，不改 ForceAdapt 映射 |
| 两条 API 均通过，只有普通 DualSense 在游戏中产生效果 | 排查 Edge 身份/特有报告兼容性，保留普通身份作为临时选项 |
| 两种身份都无游戏效果，但探针通过 | 对比已知原生效果游戏和 Proton 版本；记录游戏握手请求及其失败 |
| 证据指向同 USB 父设备下的音频/ContainerID 要求 | 再评估 openflydigi 的 USB/IP 方案，单独验证和评估依赖 |

`--hid-debug` 记录完整主机输出、单调时钟时间及 GET/SET_REPORT 返回状态，默认关闭。
它不猜测发送者 PID、不伪造未知 Feature Report，也不改变现有硬件写入门禁。
这张表是执行前的决策矩阵；2026-09-20 的 OW2 结果记录在本节末尾。

### Proton 11 首次只读验证（2026-09-13）

已在 SteamOS 验证 `proton-11.0-2c-x86_64`，使用其清单指定的 Steam Linux Runtime 4。
为保留原 checkout 的未提交内容和原安装目录，使用独立诊断目录运行新 relay，保持
`--trigger-dry-run --trigger-debug --hid-debug`。远端 57 项 Python/运行测试通过，
1 项需要 C 编译器的 portable 测试跳过（本地已通过）。

独立测试 prefix 中，三个过滤变量均出现在 `winedevice.exe` 的实际环境中。Windows
只读枚举未出现 `04b4:2412`，虚拟 Edge 则为：

```text
DEVICE 0 vid=054c pid=0df2 version=0000 usage=0001/0005 input=64 output=48 relay=0
  product=Wireless Controller
```

`relay=0` 是探针旧产品名检查拒绝了 Proton 重写后的名字，不是设备不存在。已补充
去标识化配对模板匹配分支并通过本地回归、交叉编译；该分支的 Windows 实测待继续。
本轮没有发送 mild/Off 探针效果，也没有进行 OW2 实际游戏验收。

启动环境有三个注意点：独立 `STEAM_COMPAT_DATA_PATH` 目录须预先创建；从 systemd
临时服务运行需要传入当前图形会话的 DISPLAY；Windows 控制台输出未必进入 Proton
日志，本次用 Windows `cmd.exe /c` 将探针 stdout/stderr 重定向到专用测试文件才取得结果。
首次复用了 OW2 AppID，用户报告看到了 OW2 启动；已核对命令目标为探针，并结束启动链。
后续独立探针不借用 OW2 AppID，且启动前先与用户协调；在游戏实际启动链中的验证另行安排。

随后经用户确认，在 AppID=0 的独立 prefix 中复测通过：`PAIRING_TEMPLATE_MATCH=1`、
虚拟 Edge `relay=1`，四项 Feature Report 和 Windows Input Report 均返回成功，物理
APEX 4 未出现在枚举中。注意仍出现 `28de:11ff` Steam 虚拟手柄，因此这还不是游戏的
“只使用虚拟 Sony”环境验证。Input Report 成功也可能由 Wine 缓存满足；对应窗口中
没有输入类型的 UHID GET_REPORT，不能据此声称 relay 实现了输入快照。
只读摘录与 relay 对照见 [evidence](evidence/2026-09-13-windows-readonly.txt)。
下一步经用户确认后，通过 dry-run relay 分别测试 WriteFile 和 HidD_SetOutputReport。

### Windows 输出验证（2026-09-13）

用户确认后，在上述 AppID=0 独立 prefix 中完成右侧 mild/Off 报文测试，relay 始终
dry-run。`HidD_SetOutputReport` 两次返回成功；relay 收到完整 48 字节 mild，约
1.0004 秒后收到完整 Off，并分别转译为 ForceAdapt mode 1 和 mode 0。

`WriteFile` 同样返回 TRUE，原生错误为 0，但返回字节数为 47；relay 收到的报文确为
完整 48 字节。探针先前将长度不符自行转换为错误 29，不能把该值解释为 Windows 原生
失败。对照 [Wine hidclass 源码](https://github.com/ValveSoftware/wine/blob/proton_11.0/dlls/hidclass.sys/device.c)，
WRITE_REPORT 的 completion 会减去非零 report ID 的一个字节。探针已保留原始返回值，
并允许完整长度或该单字节计数差异；更短的返回仍失败。本地回归和交叉编译通过，修正
计数的最终二进制尚未再次实测，原始 API 成功和完整接收已有本轮记录。

两条 Windows API 在本构建下均到达 `UHID_OUTPUT`，并不要求 `HidD_SetOutputReport`
一定变成 `UHID_SET_REPORT`。摘录见 [Windows 输出证据](evidence/2026-09-13-windows-output.txt)。
现在可排除“这两条 Windows API 普遍不能给 relay 发效果”的推断；下一步应在真实 OW2
启动环境验证过滤和动态效果，继续保持 dry-run，等确认收到游戏效果后再安排真实触感。

## OW2 native-game closure (2026-09-20)

Proton Experimental `experimental-11.0-20260910b-x86_64` 下完成了真实 OW2 对照。
启动包装器的三个过滤变量均出现在 OW2 `winedevice.exe` 环境中；Wine 持有虚拟 Sony
hidraw，不持有物理 `04b4:2412` 节点。

第一次 Edge 动作窗口记录为零，但后来发现 Steam 重启启动了已安装 Edge 服务，同时
诊断 Edge relay 也在运行。游戏连接的是另一份 relay，因此该样本无效。停止两份服务、
确认一个 relay 进程、一个 `/dev/uhid` 持有者和一个虚拟 Sony 节点后重新测试：

| 身份 | 半藏完整蓄力三次 | 结论 |
|---|---|---|
| DualSense `054c:0ce6` | 每次均产生 R2 `0x26` vibration、`0x21` resistance、`0x05` Off | native dynamic dry-run PASS |
| Edge `054c:0df2` | 动作窗口 0 output、0 decoded effect | 当前 OW2/Proton 组合不输出 Edge 动态效果 |

普通 DualSense 动作窗口的原始报告重复率很高；state manager 只在效果变化时转译，未向
APEX 4 重复写入。Edge 结论只适用于本次游戏/运行时，不外推为所有游戏不支持 Edge。

随后按既有授权增加 `--trigger-one-shot-mild-right`：只在普通 DualSense、同 fd 身份门禁
成功后工作；第一条 R2 非 Normal 固定映射为 resistance `(60,40)`，L2/后续效果忽略，
游戏 Off 可提前清除，最迟一秒强制双侧 Normal，随后锁定到 relay 重启。它不能与
`--adaptive-triggers`、`--no-adaptive-triggers` 或 `--trigger-dry-run` 组合。

第二轮实际测试的机器证据为一次 R2 mild、一次超时 Normal、零写失败；持握者确认感觉
到 R2 阻力。游戏退出后 relay shutdown 再写双侧 Normal，relay 停止后 `/dev/uhid`
持有者为零，日常 Edge 服务恢复。由此 Level 5 获得**受限物理 PASS**：游戏到硬件链路
成立，但 OW2 原始 mode 2 rattle 和 mode 1 resistance 参数仍只有 dry-run 证据。

此次还增加了进程级 relay lock。脚本层互斥无法阻止 Steam 重启后自启动服务与手动
relay 并存；现在第二进程会在打开手柄或创建虚拟设备前被拒绝，lock 文件权限 `0600`
并记录持有 PID。完整摘录见
[2026-09-20-ow2-native-game.txt](evidence/2026-09-20-ow2-native-game.txt)。

### OW2 profile-session 非游戏验证（2026-09-20）

在独立诊断目录同步新模块，未覆盖远端脏 checkout 或旧安装目录。最终远端共运行 78 项
测试，77 通过，1 项因无 C 编译器跳过；Python 编译通过。预览模式打印过滤器与
`Edge -> DualSense -> Edge` 计划，日常服务和虚拟 Edge 均未改变。

真实服务切换前确认：已安装 Edge 服务 active、手动服务 inactive、项目虚拟 Edge 名称与
`054c:0df2` 同时匹配，并且 `adaptive_triggers=false`。随后用无害 Python 子进程代替游戏：
子进程窗口内手动服务 active，项目普通 DualSense `054c:0ce6` 存在；子进程退出后手动
服务 inactive，已安装服务 active，Edge `054c:0df2` 恢复且只有一个 relay 进程。补强
后的最终复测同时证明临时窗口恰好一个普通 DualSense、零 Edge，恢复后恰好一个 Edge、
零普通 DualSense。

第二次让无害子进程返回 17，包装器原样返回 17，仍恢复 Edge。两轮对应的手动 relay
日志均无 `APEX4 L2/R2`、ForceAdapt 或写失败行。本验证证明非游戏身份与异常退出闭环，
不等于实际 OW2 包装器启动通过。脱敏摘录见
[2026-09-20-controller-profile-session.txt](evidence/2026-09-20-controller-profile-session.txt)。

随后把 `b820aee` 的完整运行时先解包到新目录并通过 Python 编译/包装器预览，再停止日常
服务、原子交换安装目录并启动新版本。旧安装目录保留为可恢复备份；新服务启动后恰好
一个 Edge、零普通 DualSense，进程锁权限为 `0600`。从已安装路径再次运行无害子进程，
临时窗口恰好一个普通 DualSense，退出后恢复恰好一个 Edge，日志仍无扳机写入。

OW2 的启动选项已从旧 `--run --debug` 模式改为
`--run --relay-profile dualsense -- %command%`。修改前备份 `localconfig.vdf`，重启 Steam
后新值仍为一份、旧值为零，且没有 OW2 进程出现。实际点击启动仍需提前通知并确认。

用户确认启动后完成了第一次真实包装器会话。启动前为一个 Edge、零普通 DualSense；
Steam AppID `2357570` 启动后同时观察到实际 `Overwatch.exe` 和包装器进程，日常服务停止、
手动服务 active，并且恰好一个普通 DualSense、零 Edge。约一分钟后用户报告游戏已退出；
包装器与 OW2 进程均消失，手动服务 inactive，日常服务 active，恢复为恰好一个 Edge、
零普通 DualSense 和一个 relay 进程。对应窗口无异常、ForceAdapt 或写失败行。

因此真实游戏的自动身份生命周期获得机器级 PASS。该轮配置仍为
`adaptive_triggers=false`，没有实体扳机反馈。随后用户明确确认手柄能正常控制 OW2
菜单，因此自动身份生命周期与游戏输入均为 PASS；完整游戏扳机参数仍未获授权实机写入。

### 2026-09-21 生命周期修复与 bounded dry-run 检查点

SteamOS 关机期间，本地完成 profile 全阶段信号覆盖、10 秒 systemd 命令 timeout、
子进程有界退出、session lock/InvocationID 所有权、分侧 effect freshness、2 秒 pending
TTL 和非法 active-zone mask 拒绝。新增的 R2-only bounded resistance policy 支持 dry-run，
最多三周期、每周期一秒、三十秒交互窗口，参数限制为 `start>=60, strength<=40`，忽略 L2/rattle。

修正三十秒窗口后的本地 97 项测试通过。此前 SteamOS 运行 96 项，其中 95 通过、
1 项因无 C 编译器跳过；
Python compilation 与 shell syntax 通过。正常无游戏 profile 会话和忽略 SIGTERM 的
子进程均恢复唯一 Edge，后者包装器返回 143 且无残留进程。

bounded dry-run 连续注入四个 R2 mild/Off 周期，只产生前三组最终 mode 1 `(60,40)` 与
mode 0 Normal，第四组被总周期预算拒绝。该窗口没有实体 ForceAdapt 写入。`dbde16f`
已用可回滚目录交换部署；OW2 启动选项持久化为
`--relay-profile dualsense --relay-trigger-mode bounded-dry-run`，但没有启动 OW2。
完整摘录见 [2026-09-21-lifecycle-bounded-validation.txt](evidence/2026-09-21-lifecycle-bounded-validation.txt)。

随后第一次实际启动 OW2 bounded dry-run。用户完成三次半藏完整蓄力，relay 在
20:28:53 和 20:29:00 分别输出 R2 mode 1 `(60,40)` 并于一秒后 Normal；原十秒
总窗口在 20:29:03 到期并再次强制 Normal，第三次蓄力被拒绝。没有实体写入或 write
failure，退出后恢复唯一 Edge。结论是周期和复位逻辑 PASS，但十秒窗口不适配三次正常
人工操作；默认值改为三十秒，仍保留三周期/每周期一秒上限，等待重复游戏 dry-run。

三十秒修正版 `e2338b8` 在 SteamOS 运行 97 项测试（96 通过、1 项无 C 编译器跳过）。
按 7 秒间隔注入三个虚拟 mild/Off 周期时三次均输出 mode 1 `(60,40)` 与 Normal，第四次
仍被预算拒绝。修正版已部署，Steam bounded-dry-run 启动选项无需改变；下一门禁是重复
实际 OW2 三次蓄力 dry-run。

第二次实际 OW2 bounded dry-run 使用三十秒窗口。用户完成三次完整半藏蓄力，relay 在
20:43:30、20:43:33、20:43:36 分别输出 R2 mode 1 `(60,40)`，每次随后输出 Normal；
没有第四周期、write failure 或实体写入。游戏退出后 OW2/包装器/手动服务均消失，恢复
日常服务、恰好一个 Edge、零普通 DualSense 和一个 relay 进程。该结果完成持续游戏输入
到受限最终 packet 的 dry-run 验收；不等于实体重复 resistance 已通过。

为使实体门禁可审核，新增固定 allowlist 的 `bounded-write` wrapper mode；它只去掉
`--trigger-dry-run`，其余 side/mode/参数/周期预算与已通过的 dry-run 完全相同。`4cf1515`
本地 99 项测试通过，SteamOS 运行 99 项（98 通过、1 项无 C 编译器跳过），preview
明确显示 physical R2 resistance 范围并已部署。Steam 配置仍为 bounded-dry-run，
`bounded-write` 计数为零、`adaptive_triggers=false`，因此本步骤没有实体写入。

### 2026-09-21 综合原生输出采样

部署 `d98d88c` 并把 OW2 启动选项切为 `translation-dry-run` 后，完成一次无实体写入的
同步动作块。只读输入监视器在动作窗口观察到物理 Flydigi 与虚拟 Sony 成对事件，常驻
Valve Xbox 源没有按键或扳机事件；因此 Xbox 图标在当前范围限定为非阻塞界面行为，
不再进行无证据的设备屏蔽或映射修改。

三次 R2 周期均为 `0x26 -> 0x21 -> 0x05`：rattle 到达 R2=12/11/14，resistance
在 0.720/0.736/0.719 秒后到达 R2=228/129/255，Off 均在 R2=0。由此否定“阻力总在
压到底后才到达”。完整报告显示 compatibility 与 semantic 对 `0x26` 分别为
mode 2 `(0,1,120,21,0)` / `(0,1,32,21,0)`，对 `0x21` 分别为 mode 1
`(1,64,0,0,0)` / `(0,96,0,0,0)`。完整脱敏报告已成为
`tests/fixtures/ow2-hanzo-2026-09-21.json` 的自动回放数据。

正常退出后机器核对为 OW2=0、包装器=0、日常服务 active、手动服务 inactive、恰好
一个 Edge、零普通 DualSense、一个 relay，完成 DELIVERY_PLAN 的 C 门禁。该轮没有
ForceAdapt 写入；不能据此接受 rattle 32、resistance 96 或 compatibility 参数。
下一步必须按 mode 2 / mode 1 分开说明侧别、参数、时限、次数和 Normal 行为并获得
持握者明确授权。详见
[2026-09-21-ow2-synchronized-capture.txt](evidence/2026-09-21-ow2-synchronized-capture.txt)。

随后实现单周期 `--trigger-bounded-native-right` 候选：R2 mode 2 保留
`(0,1,32,21,0)`，后续 mode 1 保留 start=0、把 semantic strength 96 限制为 40；
两种变化共用首个效果起算的一秒 deadline，Off 可提前清除，后续周期锁止。L2 与其他
模式忽略。固定包装器提供 `native-dry-run` 和 `native-write`，二者策略完全相同，前者
额外禁止 transport 写入。

`f3a1f57` 本地 117 项通过；SteamOS 运行 117 项，116 通过、1 项无 C 编译器跳过。
在真实虚拟 DualSense 上重放上述捕获报告，`native-dry-run` 依次打印 mode 2
`(0,1,32,21,0)`、mode 1 `(0,40,0,0,0)` 和 timeout 双侧 Normal，无 write failure。
运行时已可回滚部署，最终唯一 Edge/单 relay 恢复。Steam 仍为 `translation-dry-run`，
无 `native-write`，全局 adaptive=false；本步骤没有启动游戏或发送实体效果。下一步必须
先向持握者说明并获批这个精确单周期包。证据见
[2026-09-21-bounded-native-candidate.txt](evidence/2026-09-21-bounded-native-candidate.txt)。

持握者随后明确批准一次 R2 原生单周期实体包。OW2 在 22:24:12.199 写入 mode 2
`(0,1,32,21,0)`，0.736 秒后写入 mode 1 `(0,40,0,0,0)`；首效果一秒时双侧
Normal，无 write failure。持握者明确感觉到震动和阻力。游戏 `0x05` Off 在安全
Normal 约 2.33 秒后才到达，因此该样本没有直接证明 Off 清除仍活动的效果。

持握者报告松开后有一段更强震动。完整输出报告显示 Off 后约 15 ms，游戏另发普通
rumble `(255,255)`，持续约 0.13 秒；扳机此前已是 Normal。该感觉属于游戏释放/射击
的普通马达反馈，不是 mode 2 重启或扳机复位失败。退出后 OW2/包装器为零，日常服务
active、手动服务 inactive、唯一 Edge/单 relay 恢复；Steam 选项已从临时
`native-write` 精确恢复为 `translation-dry-run`，全局 adaptive=false。详见
[2026-09-21-bounded-native-physical.txt](evidence/2026-09-21-bounded-native-physical.txt)。
持握者随后确认 R2 已完全恢复正常行程，无残余阻力或持续震动。

为合并剩余的重复周期与活动期 Off 清除门禁，`ded4178` 新增
`--trigger-bounded-native-session-right`：沿用已感知的 R2 mode 2/1 上限，最多三周期/
30 秒，每周期从首个效果起最多 4 秒，总活动输出最多 12 秒。Off 先到则 R2 Normal 并
重新武装；deadline 先到则双侧 Normal，之后必须等 Off 才能重新武装。第 4 周期拒绝。

本地 124 项全通过；其中 session deadline 与新输出同时到达的失败测试先发现“提前标记
complete 会跳过 reset”，修正为由 expire 执行双侧 Normal 后转绿。SteamOS 运行 124
项，123 通过、1 项无 C 编译器跳过。真实捕获报告经虚拟 DualSense dry-run 重放四轮，
只有前三轮各产生 mode 2、mode 1 和 Off→R2 Normal，第 4 轮无非 Normal，write failure
为零。`ded4178` 已可回滚部署；Steam 仍为 translation-dry-run、session-write=0、
adaptive=false，未启动游戏或实体写入。证据见
[2026-09-21-bounded-native-session-candidate.txt](evidence/2026-09-21-bounded-native-session-candidate.txt)。

持握者随后明确批准三周期实体块。三轮在约 13.1 秒内完成，分别于首个效果后
1.304/1.386/1.838 秒收到游戏 Off 并写 R2 Normal；每轮 mode 2 到 mode 1 间隔约
0.72 秒。没有四秒 timeout、write failure、错误侧别或第四周期。持握者确认三轮均
感觉到震动与阻力，每次松开后 R2 正常。这同时完成重复周期和 active-effect Off 清除
的机器/用户门禁。

正常退出后 OW2/包装器为零、日常服务 active、手动服务 inactive、唯一 Edge/单 relay
恢复。Steam 选项已精确恢复为 translation-dry-run，session-write=0、adaptive=false。
D 阶段由此在 OW2/2.4 GHz/R2/有界语义范围内完成；不外推至 L2、有线、无限制参数或
其他游戏。证据见
[2026-09-21-bounded-native-session-physical.txt](evidence/2026-09-21-bounded-native-session-physical.txt)。

E 阶段先修复安装交付遗漏：临时 XDG/HOME 的真实安装测试先因缺少 LICENSE 与
THIRD_PARTY_NOTICES 失败，最小修复把两份根文件加入既有复制清单后转绿。`8e159d7`
本地 125 项通过；SteamOS 125 项中 124 通过、1 项无 C 编译器跳过。两份文件在 staging
和最终安装目录均与验证归档逐字一致，可回滚部署后唯一 Edge/单 relay 恢复。

安装路径的只读 2.4G self-test 同时通过 uhid、hid_playstation、`/dev/uhid` 权限、
DeviceType 84 dongle identity 和 1.02 g gravity sensor stream。Steam 仍为
translation-dry-run、session-write=0、adaptive=false，未启动游戏或实体写入。证据见
[2026-09-21-stage-e-packaging.txt](evidence/2026-09-21-stage-e-packaging.txt)。

最终有线块先识别 DeviceType 84/wired；首次 self-test 只有 0.12 g，未把它冒充 PASS。
持握者短按 Home 旁小圆/`+` 键打开已知 pad-side gyro gate 后，同一测试为 1.00 g PASS。
经明确授权的一次 OW2 有线 R2 周期在 0.718 秒由 mode 2 变为 mode 1，一秒时双侧
Normal，无 write failure；持握者确认震动、阻力及松开后正常。退出后恢复唯一 Edge，
启动选项精确恢复为 translation-dry-run，write=0、adaptive=false。

返回 Edge 后只读背键序列为 vendor `04 08 10 20`、virtual `80 40 20 10`；IMU 捕获
10,000 帧，accel 三轴与 gyro 三轴均有范围变化，并同时记录 10,259 个 gyro-mouse X/Y
事件，因此不是只用鼠标活动冒充 IMU。E 技术回归由此完成。OW2 动态 L2 记录为 N/A，
沿用既有 cable L2 mild/rumble 实体验收，不再重复无新信息的写入。证据见
[2026-09-21-stage-e-cable-regression.txt](evidence/2026-09-21-stage-e-cable-regression.txt)。

### 2026-09-22 生产路径审查与加固

两条独立 review 均阻止把旧 HEAD 称为生产版：公开 `adaptive_triggers` 仍走未同等验收的
compatibility translator；字符串 `"false"` 会因 truthiness 开启写入；installer 合并覆盖
活动目录且不 restart，uninstall 漏停 manual writer；无输出时 unrestricted effect 可无限
保持。模式 4/5、独立写工具锁和 0x11/0x12 契约也需收紧。

修复后，命名 `ow2-safe` 只接受本次捕获的 R2 0x26/0x21/0x05 精确参数与顺序，使用
实测 caps，逐周期 4 秒 reset，Off 才重新武装且无三周期产品限制。配置改为严格
`trigger_profile=disabled|ow2-safe`，旧 boolean 只做类型安全迁移；compatibility 不再可
配置为 live path。installer 使用完整 staging/compile、等待 writer 停止、原子替换、显式
restart/active 核对和失败回滚；卸载先停 manual writer。

本地 145 项全通过；SteamOS 145 项中 144 通过、1 项无 C 编译器跳过。公开 installer
真实升级成功并保留旧 runtime，安装服务从新路径运行，旧 false 配置迁移为 disabled。
最后五周期 dry-run 因手柄离线、Edge=0 被 profile preflight 安全拒绝，未启动 manual
relay/游戏或写硬件。手柄在线后需补该门禁与修后独立复审。证据见
[2026-09-22-production-hardening.txt](evidence/2026-09-22-production-hardening.txt)。
