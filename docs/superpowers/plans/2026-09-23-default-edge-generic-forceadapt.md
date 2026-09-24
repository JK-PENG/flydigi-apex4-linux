# 默认 Edge 与通用 ForceAdapt 实施计划

> **历史计划，已停止执行（2026-09-24）。** 最终状态见
> [项目终止存档](../../PROJECT_CLOSURE.md)；下列任务与授权均不得自动续行。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 不配置游戏启动选项时呈现具备通用安全自适应扳机的 DualSense Edge；仅对不向 Edge 输出的游戏，以身份降级启动选项切换普通 DualSense，并沿用同一个扳机翻译器。

**Architecture:** 复用现有 `ds5.parse_output`、normalized parser、身份验证 transport、relay 和 user-systemd 会话。新增按效果类别工作的 generic-safe translator 与双侧独立状态 gate；虚拟身份由常驻配置或单游戏会话选择，效果策略与身份无关。游戏输出缺失时不合成效果，未知或未验收效果保持无写入。

**Tech Stack:** Python 3 标准库、`unittest`、Linux UHID/hidraw/evdev、SteamOS user-systemd、Steam/Proton。无新增生产依赖。

## 2026-09-23 执行快照

- O1 本地翻译、双侧时限 gate、`generic-safe` 可选 profile 与身份降级说明已作逻辑提交；
  当前默认 `trigger_profile=disabled`，mode 3 与 Galloping/Machine 未开放。
- O2 固定实体/虚拟候选、安全失败测试和预备发布配置保留测试已在本地；最近
  全套 175 项测试通过。预备测试模拟未来默认改为 generic-safe，确认既有显式
  disabled、背键/轴向配置和安装失败回滚时的配置字节仍被保留；尚未执行真实迁移。
  Deck 后来重新可达：已只读确认远端脏 checkout、已安装服务 active、唯一虚拟 Edge、
  已安装运行时默认 disabled、用户配置未显式覆盖 profile、Steam 库和环境变量。
  首个独立候选包的远端全套测试有 1 项失败：固定候选预览多余的实体 `0xEC` 身份探针
  在在线 relay 场景偶发取不到回复；修正候选 `eb916a4` 已通过 SteamOS 175 项测试
  （1 项编译器相关 skip）。随后两次安装前自检的重力均为 2.09 g，3 秒被动 IMU
  采样的 3001 帧六轴字段完全不变；持握者确认后切换手柄侧陀螺开关并移动，六轴恢复，
  静置自检重力 1.00 g。已通过公开 installer 升级一次，旧运行时保留、配置字节不变且
  默认 disabled。Edge/普通 DualSense 真实 UHID dry-run 的左右 mode 1/2、Off 和
  未支持类型拒绝通过，最后恢复唯一 Edge；`env/apex4-ds5.conf` 未改。
  负样本见 [证据](../../evidence/2026-09-23-generic-candidate-steamos.txt)。
- 下一次先完成持握者批准的缺失模式实体门禁；Proton 输入源与实际 Edge 游戏
  仍需单独验证。仅在无用户 `PROTON_DISABLE_HIDRAW` 冲突并证实物理设备被 Proton
  暴露时，处理全局过滤。H1 的六项固定实体候选与游戏启动均须分别提前说明并等
  持握者确认；实体块曾获批准并部分执行，但因负样本已暂停，不能把旧批准当作
  自动继续其余模式的许可。
- H1 已获六项实体块授权，但在 L2 mode 2 补测触感 PASS 后，L2 mode 1 独立短/长
  保持均未感到阻力；额外获批的 L2 已知 mild `(60,40)` 两秒对照也未感到。
  R2 `(0,40)` 15 秒独立保持机器写入/归零通过、持握者亦未感到阻力。旧 OW2 R2
  序列正样本保留，不以旧 PASS 覆盖当前负样本。输入监视的时序证据尚不完整，
  mode 3 与额外 L2 start-zero 补测未发送。实体块暂停、默认保持 disabled，先诊断
  mode 1 及手柄状态，再决定是否调整通用策略；详见上述证据。
- 不得把当前软件回归写成 Task 5–7 的 SteamOS、实机或原生游戏 PASS。有关实体
  参数和自动清除的集中测试包见 [VALIDATION](../../VALIDATION.md#2026-09-23-generic-safe-集中候选包尚未执行实体测试)。

## Global Constraints

- 规格依据：[默认 Edge 与通用 ForceAdapt 设计](../specs/2026-09-23-default-edge-generic-forceadapt-design.md)。
- 计划基线：本地 `feature/apex4-adaptive-triggers` 的 `39651b6` 及既存未跟踪 `.omx/`；SteamOS 安装版本、连接及配置会变化，O2 开始时重新只读核对，不从本计划推断当前在线状态。
- 当前默认 Edge 身份 `0x054c:0x0df2`、M1–M4、IMU、普通 rumble、可恢复安装与用户服务均复用；不要分叉第二个 relay。
- ForceAdapt 只经 `VerifiedTransport`、`04b4:2412/0xFFA0`、read-only 身份验证、现有 `0xA0` allowlist 写入；不得探测 raw、firmware、factory、profile 命令。
- `ow2-safe` 与既有负面延迟样本保留为回归/回退；通用 profile 不查 AppID、游戏名或 OW2 完整参数字节。
- 当前 SteamOS checkout 及 `.omx/` 属于用户资产；先查状态，增量修改，按授权路径精确 stage、可本地逻辑提交，不 push/merge/PR。
- 游戏可见启动、持握者动作及任何新 mode/侧别/时长实体写入，提前说明精确范围并等确认；白天只执行离线和无实体写入检查。
- Live 输出继续 quiet，配置 `verbose=true` 不能重新引入高频同步 journal；错误、未知 reset 与安全停机可观察。

---

## 执行节奏与关键路径

| 批次 | 时间窗口 | 工作 | 退出门禁 |
|---|---|---|---|
| O1 | 白天，连续离线批次 | Task 1–4：现有资产与游戏库存、纯翻译、双侧 gate、默认 Edge 集成、身份降级测试 | 本地针对性和全套回归通过；一份候选参数表；未动实体写入 |
| O2 | 白天，至多一次远端候选部署 | Task 5：Edge/普通身份合成 UHID、Proton 输入源、重连/超时、quiet 与安装回滚 | 真实虚拟设备 dry-run 通过；退出唯一 Edge；候选仍未默认实体写入 |
| H1 前半 | 一个工作日晚间，目标 20–30 分钟 | Task 6：一次持握者块内验收缺失的 mode/侧别 | 每种有机器、触感和 Normal 证据；异常即停止 |
| H1 后半 | 同一个晚间，目标 40–60 分钟 | Task 7：验收通过后一次性设置默认 generic-safe、验证 Edge 游戏和普通身份降级 | 无启动选项的 Edge 与身份降级游戏均有原生输出/触感/恢复证据 |
| O3 | 当晚或次日离线收尾 | Task 7 文档、最终回归和独立审查 | 用户决定仓库发布；不重复已通过实体动作 |

排期目标为 **1–2 个离线工作日 + 1 个工作日晚间 60–90 分钟**，不是把每个效果拆成一晚；复杂度或真实游戏可用性会改变日历时间。优先在 O1 的第一小时只读枚举已安装游戏和 Proton/Steam Input 状态，寻找**实际向 Edge 输出扳机效果**的游戏；并行推进代码。若 SteamOS 白天关机，O2 的本地归档先完成，晚上开机后先做无需持握的安装/dry-run，再进入 H1。若无游戏候选，立即报告需要用户已有游戏/安装选择，不等到晚间才暴露依赖。只有找不到 Edge 输出游戏、某个模式实测失败或 reset/输入延迟异常才安排有针对性的第二晚，不重复全部已通过项目。

## 文件职责与复用边界

| 文件 | 本轮职责 |
|---|---|
| `apex4ds5/trigger_translation.py` | 沿用 raw→normalized 解码；现有 `translate_semantic` 和 OW2 向量作为参照，不把兼容特判升级为通用算法 |
| `apex4ds5/generic_trigger.py`（新增） | 单一 generic-safe 效果类别 allowlist、候选参数上限与纯映射，输出 `ForceAdaptEffect | None` |
| `apex4ds5/trigger_state.py` | 增加双侧独立活动 deadline/Off 重武装 gate；在 manager 中增加单侧 Normal 清除，复用 attach/detach/lifecycle |
| `apex4ds5/config.py`、`apex4-ds5` | 命名 profile、默认身份与最终默认策略、quiet、translator/gate 装配；不复制游戏解析主循环 |
| `apex4ds5/game_session.py`、`tools/proton-game.py` | 普通 DualSense 降级时只改身份，继承 generic-safe；保留 preflight 与恢复 |
| `env/apex4-ds5.conf`、`install.sh` | 审计物理 APEX 4 在 Steam/Proton 的可见性；若需要全局过滤，只添加精确 VID/PID 并在已有用户过滤配置冲突时 fail closed |
| `tools/forceadapt-test.py`、`tools/relay-trigger-test.py` | 前者扩展固定、身份验证、自动 Normal 的实体 mode 2/3 候选；后者注入固定 Edge/普通输出报文；均默认 dry-run |
| `tests/test_generic_triggers.py`（新增）及现有 `tests/test_*` | 语义、两侧、状态、配置、降级、输入性能和安装回归 |
| `docs/TRANSLATION.md`、`docs/VALIDATION.md`、`README.md`、`docs/CONTINUE.md` | 参数及不支持项、单次人工测试包、默认体验、验收事实 |

### Task 1: 通用翻译和硬件能力表（O1）

**Files:**
- Create: `apex4ds5/generic_trigger.py`
- Create: `tests/test_generic_triggers.py`
- Create: `docs/APEX4_CAPABILITIES.md`
- Modify: `docs/TRANSLATION.md`

**Interfaces:**
- Consumes: `trigger_translation.parse(raw) -> NormalizedTriggerEffect | None`、`translate_semantic(raw, left_motor=0) -> ForceAdaptEffect | None`。
- Produces: `GenericSafeTranslator(enabled_modes=None)(raw_effect, left_motor=0) -> ForceAdaptEffect | None`；默认使用 `GENERIC_RELEASE_MODES={0,1,2}`，Task 2/3 使用同一 callable。

- [ ] **Step 1: 只读硬件能力审计。** 从 `docs/PROTOCOL.md`、`docs/DSX.md`、`docs/evidence/` 与 Flydigi 官方 APEX 4 手册建立 `docs/APEX4_CAPABILITIES.md`：每项写明实体部件、DualSense/Edge 对应输出、现有 relay 实现、是否经过本项目实机验证、下一门禁。RGB/屏幕、触摸板、音频项目仅分类，不发新 vendor 命令。
- [ ] **Step 2: 写失败测试。** 在 `tests/test_generic_triggers.py` 用 `ds5.TriggerEffect` 覆盖 L2/R2 的 Off、simple/zone resistance、simple/zone vibration、weapon/bow、galloping/machine、空 zone、越界 zone、zero/unknown/limited，以及 OW2 捕获向量。至少包含：

```python
from apex4ds5.generic_trigger import GenericSafeTranslator
from apex4ds5 import forceadapt, trigger_state
from apex4ds5._ds5 import ds5
import unittest

class GenericTranslationTests(unittest.TestCase):
    def test_generic_mapping_is_side_symmetric(self):
        mapper = GenericSafeTranslator(enabled_modes=frozenset({0, 1, 2}))
        for side in ("left", "right"):
            raw = ds5.TriggerEffect(side, 0x26,
                                    bytes.fromhex("ff030000000000001500"))
            self.assertEqual(mapper(raw).mode, forceadapt.MODE_RATTLE)
            self.assertEqual(mapper(raw).params, (0, 1, 32, 21, 0))
        self.assertIsNone(mapper(ds5.TriggerEffect(
            "right", 0xEE, bytes(10))))
```

- [ ] **Step 3: 运行红灯。** `python3 -m unittest tests.test_generic_triggers -v`；预期因 `GenericSafeTranslator` 尚不存在而 FAIL。
- [ ] **Step 4: 实现纯映射。** 先使用已验收 mode 0/1/2 上限：mode 1 strength≤40；mode 2 pressure≤1、strength≤32、frequency≤21；mode 3 候选 travel≤20、strength≤20，但 `enabled_modes` 在实体批准前不含 3。下列函数行为是本任务的接口，不添加游戏名或完整字节匹配：

```python
class GenericSafeTranslator:
    def __init__(self, enabled_modes=None):
        if enabled_modes is None:
            enabled_modes = GENERIC_RELEASE_MODES
        self.enabled_modes = frozenset(enabled_modes)

    def __call__(self, raw_effect, left_motor=0):
        normalized = trigger_translation.parse(raw_effect)
        if normalized is None or normalized.kind in (
                "noop", "unsupported", "invalid"):
            return None
        candidate = trigger_translation.translate_semantic(
            raw_effect, left_motor)
        if candidate is None or candidate.mode not in self.enabled_modes:
            return None
        side = candidate.side
        if candidate.mode == forceadapt.MODE_NORMAL:
            return forceadapt.normal(side)
        if not normalized.strength:
            return None
        if candidate.mode == forceadapt.MODE_RESISTANCE:
            return forceadapt.resistance(
                side, candidate.params[0], min(40, candidate.params[1]))
        if candidate.mode == forceadapt.MODE_RATTLE:
            if not normalized.frequency:
                return None
            return forceadapt.rattle(
                side, candidate.params[0], 1,
                min(32, candidate.params[2]),
                min(21, candidate.params[3]))
        if candidate.mode == forceadapt.MODE_BREAKPOINT:
            return forceadapt.breakpoint(
                side, max(60, candidate.params[0]),
                min(20, candidate.params[1]),
                min(20, candidate.params[2]))
        return None
```

```python
GENERIC_RELEASE_MODES = frozenset({
    forceadapt.MODE_NORMAL,
    forceadapt.MODE_RESISTANCE,
    forceadapt.MODE_RATTLE,
})
```

  该集合在 mode 3 物理门禁通过前不含 `MODE_BREAKPOINT`；Task 7 只能在证据 PASS 后改此一处。

  mode 3 起点不早于 60 是安全近似，需在文档标出原始起点可能丢失。对 simple vibration 的 zero frequency/strength 和 mode 3 后备效果建立固定测试，不以现有函数自己的输出作唯一 oracle。`docs/TRANSLATION.md` 逐项标注保留、截断、近似与未验收。
- [ ] **Step 5: 运行绿灯。** `python3 -m unittest tests.test_generic_triggers tests.test_adaptive_triggers -v`；预期 PASS；检查 `git diff --check -- . ':!docs/evidence/*'`。
- [ ] **Step 6: 仅提交本任务路径。** `git add apex4ds5/generic_trigger.py tests/test_generic_triggers.py docs/APEX4_CAPABILITIES.md docs/TRANSLATION.md && git commit -m 'feat: add generic safe trigger mapping'`。

### Task 2: 双侧独立生命周期与安全时限（O1）

**Files:**
- Modify: `apex4ds5/trigger_state.py`
- Test: `tests/test_generic_triggers.py`

**Interfaces:**
- Consumes: Task 1 的 `GenericSafeTranslator` 最终效果；`TriggerStateManager` 的 `effect_filter` 接口。
- Produces: `GenericSafeGate(clock=time.monotonic, mode_seconds={1:15.0,2:4.0,3:4.0})`、`TriggerStateManager.clear_side(side, reason="reset", force=False) -> bool`。

- [ ] **Step 1: 写失败测试。** 同时覆盖：L2/R2 并发不互相续期；rattle→resistance 不滑动 deadline；mode 1 候选最多 15 秒、mode 2/3 最多 4 秒；Off 只清对应侧；deadline 先到必须等该侧 Off 才重新武装；LED/rumble/unknown 不续期；reset 失败不算 PASS；vendor detach 后旧效果不重放，已验证新 attach 并初始双 Normal 成功后可恢复。示例：

```python
class FakeTransport:
    def __init__(self):
        self.effects = []

    def write_effect(self, effect):
        self.effects.append(effect)
        return forceadapt.build_packet(effect)

class GenericGateTests(unittest.TestCase):
    def test_generic_timeout_clears_only_due_side(self):
        clock = [10.0]
        gate = trigger_state.GenericSafeGate(clock=lambda: clock[0])
        manager = trigger_state.TriggerStateManager(
            transport=FakeTransport(), clock=lambda: clock[0],
            effect_filter=gate,
            translator=GenericSafeTranslator())
        manager.handle(ds5.TriggerEffect("right", 0x26,
                                        bytes.fromhex("ff030000000000001500")))
        clock[0] += 1.0
        manager.handle(ds5.TriggerEffect("left", 0x01,
                                        bytes([60, 40]) + bytes(8)))
        clock[0] += 3.1
        self.assertTrue(gate.expire(manager))
        self.assertEqual(manager.last["right"], forceadapt.normal("right"))
        self.assertEqual(manager.last["left"].mode,
                         forceadapt.MODE_RESISTANCE)
```

- [ ] **Step 2: 运行红灯。** `python3 -m unittest tests.test_generic_triggers -v`；预期缺 `GenericSafeGate`/`clear_side` 的测试 FAIL。
- [ ] **Step 3: 实现最小 gate。** 每侧状态只包括 `deadline` 与 `waiting_off`，`deadline=None` 表示当前无活动效果；首次非 Normal 依据模式给绝对 deadline，后续合法变化不延长；Off 清同侧并重武装；`expire()` 逐侧调用 `clear_side()`。使用下列状态转移，不接受无限时长：

```python
class GenericSafeGate:
    def __init__(self, clock=time.monotonic,
                 mode_seconds=None):
        self.clock = clock
        self.mode_seconds = dict(mode_seconds or {1: 15.0, 2: 4.0, 3: 4.0})
        self.deadline = {"left": None, "right": None}
        self.waiting_off = {"left": False, "right": False}

    def __call__(self, effect):
        side = effect.side
        if effect.mode == forceadapt.MODE_NORMAL:
            if self.deadline[side] is None and not self.waiting_off[side]:
                return None
            self.deadline[side] = None
            self.waiting_off[side] = False
            return effect
        if self.waiting_off[side]:
            return None
        now = self.clock()
        if self.deadline[side] is None:
            self.deadline[side] = now + self.mode_seconds[effect.mode]
        if now >= self.deadline[side]:
            return None
        return effect

    def expire(self, manager):
        due = [side for side in ("left", "right")
               if self.deadline[side] is not None
               and self.clock() >= self.deadline[side]]
        if not due:
            return None
        ok = True
        for side in due:
            self.deadline[side] = None
            self.waiting_off[side] = True
            ok = bool(manager.clear_side(
                side, "generic safe cycle timeout", force=True)) and ok
        return ok

    def abort(self):
        for side in ("left", "right"):
            self.deadline[side] = None
            self.waiting_off[side] = True

    def reset_lifecycle(self):
        for side in ("left", "right"):
            self.deadline[side] = None
            self.waiting_off[side] = False
```

  `clear_side` 仅清目标侧的 pending/last 状态并调用现有 `_send(forceadapt.normal(side))`；`clear_all` 仍负责全局关闭且保留现有失败语义。若 timeout 的单侧 clear 失败，沿用主循环的失败后双侧清除/断连路径，不能静默重新武装。`reset_lifecycle()` 只有双侧 Normal 成功才调用 generic gate 的 reset hook；失败时调用 abort 并走已有 transport 断连路径，测试必须证明旧效果不会重播。

```python
def clear_side(self, side, reason="reset", force=False):
    if side not in ("left", "right"):
        raise ValueError("trigger side must be left or right")
    self.pending[side] = None
    self.pending_at[side] = None
    effect = forceadapt.normal(side)
    if not force and self.last[side] == effect:
        return True
    try:
        sent = self._send(effect, "reason=%s" % reason)
    except OSError as exc:
        self.logger("APEX4 %s clear failed: %s"
                    % (SIDE_LABELS[side], exc))
        return False
    if sent:
        self.last[side] = effect
        self.last_effect_at[side] = None
    return sent
```
- [ ] **Step 4: 回归。** `python3 -m unittest tests.test_generic_triggers tests.test_adaptive_triggers tests.test_uhid -v`；预期 PASS，既有 OW2 三周期策略与 reconnect 测试不变。
- [ ] **Step 5: 仅提交本任务路径。** `git add apex4ds5/trigger_state.py tests/test_generic_triggers.py && git commit -m 'feat: bound generic trigger effects per side'`。

### Task 3: 默认 Edge 装配与配置迁移（O1，实体仍关闭）

**Files:**
- Modify: `apex4ds5/config.py`, `apex4-ds5`
- Test: `tests/test_config.py`, `tests/test_adaptive_triggers.py`, `tests/test_regressions.py`

**Interfaces:**
- Consumes: `GenericSafeTranslator`、`GenericSafeGate`。
- Produces: `trigger_profile=generic-safe` 的 CLI/config 选择与 quiet live 装配；此任务只把 profile 变为可选，`DEFAULTS["trigger_profile"]` 暂保留 `disabled`。

- [ ] **Step 1: 写失败测试。** `--emulate dualsense-edge --trigger-profile generic-safe --calib` 必须返回 0；直接 live generic 与 config `verbose=true` 组合不得产生高频输出；`--trigger-debug`/`--hid-debug` 与 live generic 冲突；旧 `ow2-safe` 在 Edge 下的拒绝保持；未知 profile 拒绝。示例：

```python
def test_generic_profile_accepts_default_edge_identity(self):
    result = subprocess.run(
        [sys.executable, str(ROOT / "apex4-ds5"),
         "--emulate", "dualsense-edge",
         "--trigger-profile", "generic-safe", "--calib"],
        capture_output=True, text=True)
    self.assertEqual(result.returncode, 0, result.stderr)
```

- [ ] **Step 2: 运行红灯。** `python3 -m unittest tests.test_config tests.test_adaptive_triggers -v`；预期 generic profile 被 CLI 拒绝。
- [ ] **Step 3: 最小装配。** `config.TRIGGER_PROFILES` 增加 `generic-safe`；`apex4-ds5` 的 profile 选择分支构造 Task 1/2 的 translator/gate，Edge 不再被这类 profile 拒绝。将现有 live quiet 判定扩展到 generic；dry-run 仍可诊断。保留 `ow2-safe` 及旧 boolean 的严格迁移，不把旧 `true` 自动改成未经用户选择的 generic。

```python
TRIGGER_PROFILES = ("disabled", "ow2-safe", "generic-safe")

# apex4-ds5 的 gate/translator 选择结果；交给现有 manager 只装配一次
if settings["trigger_profile"] == "generic-safe":
    safety_gate = trigger_state.GenericSafeGate()
    translator = generic_trigger.GenericSafeTranslator()
elif settings["trigger_profile"] == "ow2-safe":
    safety_gate = trigger_state.Ow2SafeGate()
    translator = trigger_translation.translate_ow2_safe
else:
    safety_gate = None
    translator = trigger_translation.translate
```

  上段仅替换现有配置 profile 分支；`--trigger-*` 有界测试参数继续优先于配置并保留各自原 gate。创建一次 `TriggerStateManager`，令其 `translator` 为上段 `translator`、`effect_filter` 为上段 `safety_gate`。此步暂不修改 fresh-install 默认值，SteamOS 当前 `disabled` 不变。
- [ ] **Step 4: 全回归与静态检查。** `python3 -m unittest discover -s tests`、`python3 -m compileall -q apex4ds5 tools apex4-ds5`、`bash -n install.sh apex4-autostart apex4-relay`、`git diff --check`；均预期 PASS。
- [ ] **Step 5: 仅提交本任务路径。** `git add apex4ds5/config.py apex4-ds5 tests/test_config.py tests/test_adaptive_triggers.py tests/test_regressions.py && git commit -m 'feat: route generic profile through Edge relay'`。

### Task 4: 身份降级只改身份，默认游戏输入源可用（O1）

**Files:**
- Modify: `tools/proton-game.py`, `apex4ds5/game_session.py`, `env/apex4-ds5.conf`, `install.sh`（只在只读环境审计证明需要且可无冲突合并时）
- Test: `tests/test_game_session.py`, `tests/test_proton_game.py`, `tests/test_install.py`
- Modify: `docs/DUALSENSE.md`, `README.md`

**Interfaces:**
- Consumes: Task 3 的 `trigger_profile=generic-safe` 与现有 `RelayProfileSession(relay_args=())`。
- Produces: 没有触发器模式参数的 `--relay-profile dualsense --run -- %command%`；普通游戏无启动选项。

- [ ] **Step 1: 只读环境与游戏库存。** 枚举 Steam 库 `appmanifest_*.acf`、Steam Input 状态及 Steam 启动环境；优先确定一个已安装、能向 Edge 发原生扳机报告的 PC 游戏。查看当前 SDL ignore、`PROTON_DISABLE_HIDRAW` 是否与用户设置冲突。只读探针使用隔离 prefix/AppID 0；任何可能显示游戏的命令另行通知。
- [ ] **Step 2: 写失败测试。** 在 generic config 下，profile 会话调用仍必须是 `apex4-relay start -- --emulate dualsense`，不包含 `--trigger-ow2-safe-right` 或任何 per-game translator；正常退出恢复一份 Edge。新增环境测试证明物理 VID/PID 被屏蔽但两种虚拟 Sony VID/PID 均不被屏蔽。

```python
def test_identity_only_downgrade_inherits_generic_profile(self):
    write_uevent(self.sysfs, "hidraw0", *game_session.EDGE_IDENTITY)
    relay_args = ()
    fake = FakeCommands(self.sysfs, relay_args=relay_args)
    session = self.session(fake)
    with session:
        pass
    self.assertIn(
        ["/installed/apex4-relay", "start", "--", "--emulate",
         "dualsense"], fake.calls)
```

- [ ] **Step 3: 运行红灯并作最小修改。** `python3 -m unittest tests.test_game_session tests.test_proton_game -v`；如现有代码已满足调用顺序，测试应先改为验证仍缺失的默认 Proton 输入源合同，再实现。`tools/proton-game.py` 的对外说明去除“OW2-only”措辞；无 `--relay-trigger-mode` 时继续传 `relay_args=()`。
- [ ] **Step 4: 需要全局 Proton 物理过滤时集中处理。** 只在 O1 探针确认 Wine 同时暴露物理 APEX 4、且目标 Steam user environment 没有需要保留的其他 `PROTON_DISABLE_HIDRAW` 值时，将 `PROTON_DISABLE_HIDRAW=0x04b4/0x2412` 加入本项目 `env/apex4-ds5.conf`；冲突则保留现场并输出精确合并需求，不覆盖用户环境。更新 installer 的环境文件测试，并安排 Steam 重启后只读核验。已存在的 per-game 过滤 helper 保留为诊断/降级路径。

```text
SDL_JOYSTICK_IGNORE_DEVICES=0x04b4/0x2412
SDL_GAMECONTROLLER_IGNORE_DEVICES=0x04b4/0x2412
PROTON_DISABLE_HIDRAW=0x04b4/0x2412
```
- [ ] **Step 5: 全回归和提交。** `python3 -m unittest tests.test_game_session tests.test_proton_game tests.test_install -v`、`bash -n install.sh`、`git diff --check` 均 PASS；只 stage 本任务路径并提交 `feat: make DualSense downgrade identity-only`。

### Task 5: 单批离线集成、候选部署与夜间包准备（O2）

**Files:**
- Modify: `tools/forceadapt-test.py`（固定、identity-gated mode 2/3 实体候选与 Normal）
- Modify: `tools/relay-trigger-test.py`（固定、可回放的 mode 2/3 DualSense 报文；默认 dry-run、明确 write）
- Test: `tests/test_forceadapt_tool.py`, `tests/test_adaptive_triggers.py`, `tests/test_regressions.py`
- Modify: `docs/VALIDATION.md`, `docs/TRANSLATION.md`, `docs/CONTINUE.md`

**Interfaces:**
- Consumes: Task 1–4 的 generic-safe 候选、已有 `VerifiedTransport`/`RelayLock`、现有 UHID 报告构建工具。
- Produces: 一个含 L2/R2 固定报文、最终 ForceAdapt 结果和自动 Normal 的有界人工测试包；一次可回滚远端候选版本。

- [ ] **Step 1: 写固定测试向量和阴性路径。** `forceadapt-test.py` 新增 `--candidate` 固定名 `l2-rattle-32`, `l2-resistance-40`, `l2-resistance-hold15`, `r2-resistance-hold15`, `l2-breakpoint-20`, `r2-breakpoint-20`；除两项 `hold15` 外的四个短候选各≤1 秒，长保持只允许同一个已验收 mild 抵抗强度 40 保持≤15 秒，不提供任意参数/raw passthrough。`relay-trigger-test.py` 只接受版本库内固定命名的 DS5 报告与 Off。验证未加 `--write` 不碰虚拟/物理节点、`--write` 拒绝 relay lock 冲突和非项目 Sony、短写报错且 `finally` 发送 Normal/Off。保留 OW2 实测向量，新增非 OW2 简单、分区、武器、机器类和左右反例。

```python
FIXED_PHYSICAL_CANDIDATES = {
    "l2-rattle-32": forceadapt.rattle("left", 0, 1, 32, 21),
    "l2-resistance-40": forceadapt.resistance("left", 0, 40),
    "l2-resistance-hold15": forceadapt.resistance("left", 0, 40),
    "r2-resistance-hold15": forceadapt.resistance("right", 0, 40),
    "l2-breakpoint-20": forceadapt.breakpoint("left", 60, 20, 20),
    "r2-breakpoint-20": forceadapt.breakpoint("right", 60, 20, 20),
}
FIXED_CANDIDATE_SECONDS = {
    "l2-rattle-32": 1.0,
    "l2-resistance-40": 1.0,
    "l2-resistance-hold15": 15.0,
    "r2-resistance-hold15": 15.0,
    "l2-breakpoint-20": 1.0,
    "r2-breakpoint-20": 1.0,
}
```

- [ ] **Step 2: 跑红灯、实现固定入口、跑绿灯。** `python3 -m unittest tests.test_forceadapt_tool tests.test_adaptive_triggers tests.test_regressions -v`；新候选入口先 FAIL，再复用现有 `VerifiedTransport`/`RelayLock` 与两个 tool 的节点/报告函数；单次命令持有锁、自动双侧 Normal 后退出，不新增运行时依赖。
- [ ] **Step 3: 仅一批远端验证。** 先本地全套单测/编译/shell/diff，再从唯一候选提交生成归档和 SHA。SteamOS 远端保持脏 checkout 不动，解包到独立验证目录；运行测试、编译、wrapper preview 和配置检查；以公开 installer 可回滚升级一次。手柄无需持握，候选的当前安装配置继续 `trigger_profile=disabled`。
- [ ] **Step 4: 真实虚拟 Edge 与普通身份 dry-run。** 先确认 daily Edge 唯一，再短暂切换一次 diagnostic relay，注入各类别报文，核对两侧最终 mode/参数/Off、未知无写入和唯一 Edge 恢复；vendor identity gate 用独立的现有只读 probe 核验，不把 dry-run 冒充实体身份验收。普通身份用现有 profile session 的无害 child/报文重复。不要启动游戏或发送实体 mode 2/3。
- [ ] **Step 5: 封装一次晚间测试包。** 先列出上述六个候选的确切 5 字节参数、四次≤1 秒与两次≤15 秒自动 Normal、六次/总活动≤34 秒、断连停止与退出恢复；已通过的 `(60,40)` mild 不重复。15 秒双侧保持在同一授权包中单独列明，持握者可一次确认整个块；若未批准长保持，将 release mode 1 最大时长降至已有实体验收范围，不能标记长保持通过。预先验证独立只读物理/虚拟输入监视 READY 命令，游戏/持握者动作当晚再启动。输出一页夜间 runbook，写明成功/失败分支。
- [ ] **Step 6: 精确 stage 并提交** 代码、测试、当前运行手册；`.omx/` 保持本地不入版本库，不 push。

### Task 6: 一次集中模式/侧别实体验收（H1 前半，持握者确认后）

**Files:**
- Add: `docs/evidence/generic-forceadapt-physical.txt`（脱敏机器/用户证据，正文记录实际执行日期）
- Modify: `docs/VALIDATION.md`, `docs/CONTINUE.md`

**Interfaces:**
- Consumes: Task 5 的唯一候选归档、参数表、固定注入工具与游戏候选。
- Produces: 每个候选 mode/侧别的机器写入、Normal 和持握者触感结论；是否开放 mode 3 与长保持时限的明确结论。

- [ ] **Step 1: 预检并说明授权包。** 确认 DeviceType/连接、唯一 Edge、旧配置 disabled、Steam Input 与游戏候选；把每侧/模式/参数/保持时间/总预算/自动 Normal 与停损条件发给持握者，等确认后才开始实体写入。若无法确认唯一身份，整块停止。
- [ ] **Step 2: 同一硬件块补齐未通过类别。** 一次停止 daily service，按固定顺序测试 L2 mode 2 `(start=0,pressure=1,strength=32,frequency=21)`、L2 mode 1 `(start=0,strength=40)`、L2/R2 mode 3 候选 `(start=60,travel=20,strength=20)`；这四个候选各最多一秒后双侧 Normal。若同一授权包已覆盖长保持，再分别测 L2 与 R2 mode 1 `(0,40)` 最长 15 秒保持与 Normal。异常触感/错误侧/Normal UNKNOWN 立即停。已通过的 R2 mode 1/2 与双侧 `(60,40)` 不重复。记录机器与用户两列，随后恢复唯一 Edge。
- [ ] **Step 3: 对结果作当晚决策。** 任何类别实体 FAIL/UNKNOWN 不开放该类别；mode 3 通过才在 Task 1 的 release `enabled_modes` 加入 3。最长 mode 1 保持未验收时，release 时限收缩到已验收值。此时先恢复 daily Edge，不重复已通过效果。真实游戏检验交由 Task 7 在默认 generic config 已设置后做。

### Task 7: 默认开启、身份降级实测与最终交付（H1 后半/O3）

**Files:**
- Modify: `apex4ds5/config.py`, `apex4-ds5`, `tests/test_config.py`, `tests/test_generic_triggers.py`, `tests/test_game_session.py`
- Modify: `README.md`, `docs/DUALSENSE.md`, `docs/DSX.md`, `docs/TRANSLATION.md`, `docs/CONTINUE.md`, `docs/DELIVERY_PLAN.md`
- Modify: SteamOS 现有 `~/.config/flydigi-apex4/config.json` 与 OW2 Steam 本地启动选项（仅验收成功后，先备份精确匹配再替换）

**Interfaces:**
- Consumes: Task 6 的受支持 mode 集合、参数上限与完成证据。
- Produces: 新安装默认 Edge+generic-safe，当前 SteamOS 安装完成一次安全迁移；OW2 启动选项只降级身份。

- [ ] **Step 1: 离线预先写失败测试。** 新配置模板默认 `emulate=dualsense-edge` 和 `trigger_profile=generic-safe`；显式旧 `disabled` 保留；普通身份会话无触发器覆盖；mode 3 仅在 Task 6 实体 PASS 时列入 release capability。测试安装升级保存背键/轴向配置、一次精确备份与回滚。此步可在 O1 完成，减少晚间等待。
- [ ] **Step 2: 运行红灯、最小实现、运行绿灯。** 通过修改 `DEFAULTS["trigger_profile"]` 与 release enabled mode 常量完成默认切换；现有 SteamOS 配置中的旧 `disabled` 先原样备份，再仅更新该一项为 `generic-safe`，其余映射逐字保留。OW2 启动选项去掉 `--relay-trigger-mode`，只保留普通身份会话；Steam 停止时单次改写、重启后验证持久化。
- [ ] **Step 3: 当晚游戏验收。** 本地/SteamOS 软件检查与最终 installer 升级集中一次。默认 Edge 游戏不配置启动选项；提前通知后启动 O1 选出的游戏，一次动作块记录 native output→generic 最终 effect→实体触感→Off/退出，配独立物理/虚拟输入延迟监视。若该游戏没有 Edge 输出，标 UNKNOWN 并停止“默认 Edge 真游戏 PASS”声明。
- [ ] **Step 4: 普通身份降级对照。** 当前 config 已是 generic-safe；对 OW2 或另一普通身份游戏，启动选项只放 `--relay-profile dualsense --run -- %command%`，不指定 `--relay-trigger-mode`。提前通知并确认后运行短动作块，核对临时普通身份使用同一 generic 映射、正常控制、Off、退出恢复唯一 Edge。两次游戏启动合并在同一晚间，不在二者之间改 translator。
- [ ] **Step 5: 最终回归。** 本地全套 unittest、Python compile、shellcheck/diff；SteamOS 已安装树只运行相关 smoke。登录/重启后无启动选项游戏看到一份 Edge，OW2 游戏中恰好一份普通 DualSense、退出再得一份 Edge；输入/IMU/背键/普通 rumble 和至少一次双扳机 generic-safe 效果保持有效。独立监视的连续 10 次物理→虚拟释放全部配对、单次延迟≤25 ms，持握者无延迟动作；超阈值或监视缺样时保留 UNKNOWN/FAIL 并排查，不凭主循环日志推断正常。
- [ ] **Step 6: 文档与审查。** 将 README 的能力矩阵标记为“已验收/保守近似/未支持”；记录 mode 3 或 Edge 游戏若未通过的精确缺口，保留早期负面样本。对最终差异做独立代码与架构复审，CRITICAL/HIGH/BLOCK 不得发布。
- [ ] **Step 7: 精确提交与发布边界。** 仅 stage 本任务路径与脱敏证据作本地提交；合并、push、PR、tag 和 release 必须分别获得用户明确要求。RGB/屏幕映射的后续能力审计单列，不把通用 ForceAdapt 的交付拖成无边界项目。

## 失败分支与最短完成定义

- O1 若找不到 Edge 原生输出游戏：立即报告候选缺失，软件和 synthetic/hardware 门禁继续；真实 Edge 游戏层保持 UNKNOWN。若需要购买/安装新游戏，等待用户选择，不擅自扩大范围。
- H1 若 L2 rattle/mode 3 参数出现不适或 reset UNKNOWN：该类别默认关闭，保留已有 0/1/2 中经确认的部分；不能写“全部支持”。只针对失败模式改候选与一次复测。
- 游戏若未输出 Edge trigger：只对该游戏使用普通身份降级；不新增游戏效果特判。若普通身份也不输出，检查 Steam Input/Proton/游戏原生支持后标明不适用。
- 输入时序再次异常：保留负样本，恢复 disabled/dry-run，先量物理→虚拟输入和 relay 日志，再修复；不以软件 PASS 覆盖用户报告。

完成必须同时满足：默认 Edge 无游戏启动选项；通用已验收效果在 Edge/普通身份输出同一有界映射；真实 Edge 游戏有 native output→APEX 4 的机器与持握者证据；普通身份降级只改身份；退出/重连/超时恢复；日常输入性能无回归。若任一真实游戏依赖缺失，交付保留明确 PARTIAL 状态而不延长其余已完成工作。

## 规格覆盖自检

| 已批准规格的要求 | 本计划的闭合任务 |
|---|---|
| 默认 Edge 的现有输入、背键、IMU、rumble 与真实硬件范围 | Task 1 能力表、Task 7 最终回归 |
| 无游戏白名单的 L2/R2 效果语义与未知类型 fail closed | Task 1 translator、Task 2 双侧 gate、Task 5 固定向量 |
| 游戏只降级身份并沿用同一策略 | Task 3 装配、Task 4 会话/环境、Task 7 普通身份游戏对照 |
| mode/侧别实机验证、reset/断连/quiet 与输入延迟 | Task 2、Task 5、Task 6、Task 7 |
| 新安装默认、既有配置保护、SteamOS 安装与文档 | Task 3 暂存候选、Task 7 验收后激活 |
| 真实 Edge 游戏发送 native output 的边界 | Task 4 提前找候选、Task 7 实测；缺失则 UNKNOWN |
