# ForceAdapt mode 1 诊断可观察性实施计划

> **历史计划，已停止执行（2026-09-24）。** 最终状态见
> [项目终止存档](../../PROJECT_CLOSURE.md)；下列实体步骤不得自动续行。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不新增 vendor 命令、不增加实体效果时长的前提下，为下次获批的固定测试同时保存完整物理输入与有界 `0xA0` echo 观察，区分更多失败层级。

**Architecture:** 只扩展现有 `tools/forceadapt-test.py` 的显式诊断路径，同 fd 非阻塞读取初始 Normal 后残留回复以及效果写入后的 `0xA0` echo；任何观察结果都不当作实体触感 ACK。现有 `input-source-watch.py --physical-only` 不再改代码，通过私有 `tee` 文件保留完整输出并在时间窗内摘要。

**Tech Stack:** Python 3 标准库、`unittest`、Linux hidraw/evdev、bash/systemd。无新增生产依赖。

## 执行快照

代码提交 `ad43a4e` 与补强测试提交 `2c72125` 已完成；最新本地 186 项测试
通过。HEAD 归档在 SteamOS 独立目录经 SHA 对照通过 186 项测试（1 项编译器
相关 skip）、Python 编译、shell 语法、纯预览及 CLI 拒绝路径。没有调用真实
`--write`、启动游戏、停服务或改已安装配置。私有输入日志的合成窗口筛选通过；
当前设备在线状态未确认，实体 `0xA0` echo/触感仍需新的精确授权。

## Global Constraints

- 规格：[mode 1 可观察性设计](../specs/2026-09-23-mode1-observability-design.md)；总项目设计仍是[默认 Edge 与通用 ForceAdapt](../specs/2026-09-23-default-edge-generic-forceadapt-design.md)。
- 只处理诊断工具和文档，不改 `apex4-ds5` 生产主循环、`GENERIC_RELEASE_MODES`、Steam 启动选项或已安装配置；mode 1 默认继续关闭。
- 新参数仅限既有固定 `--candidate`，或单侧 `--effect mild --duration 0.1..2.0`；必须同时显式 `--write --observe-forceadapt-echo`。拒绝 medium/strong、both、dry-run 与任意 raw 参数。
- `VerifiedTransport`/`RelayLock`/精确接口与 DeviceType 门禁不变；不添加任何 vendor 命令。观察总计初始清理最多 100 ms、效果后最多 100 ms，后者计入原有效果截止时间。
- 新实体写入或游戏启动均需新的精确用户授权；本计划只有离线代码、测试、文档与 SteamOS 软件回归。保留远端脏 checkout 和 `.omx/`，不 push。

---

## 文件责任

| 文件 | 责任 |
|---|---|
| `tools/forceadapt-test.py` | 明确 opt-in、同 fd 回执计数、时限不延长及双侧 Normal |
| `tests/test_forceadapt_tool.py` | 无新写入、CLI 约束、echo 观察、异常和截止行为 |
| `docs/VALIDATION.md` | 私有完整输入记录与筛选步骤、下一次授权前置条件 |
| `docs/evidence/2026-09-23-generic-candidate-steamos.txt` | 保留既有负样本并链接新诊断方法；不把软件绿灯改写为实体 PASS |

### Task 1: 有界同 fd echo 观察（离线）

**Files:** `tools/forceadapt-test.py`, `tests/test_forceadapt_tool.py`

**Interfaces:**
- Consumes: `legacy.command_echo(frame) -> int | None`、`legacy.CMD_FORCEADAPT`、`VerifiedTransport.verify(fd,node)`、现有固定 `ForceAdaptEffect`。
- Produces: `count_forceadapt_echoes(fd, deadline, *, clock, waiter, reader) -> int`；CLI `--observe-forceadapt-echo` 只在授权范围内可选。计数仅表示同 fd 的 `0xA0` echo，**不是**具体 mode 的物理 ACK。

- [ ] **Step 1: 写失败测试。** 在 `tests/test_forceadapt_tool.py` 用有完整 32 字节结构的合成 vendor 输入帧（报告 id `0x04`、echo 位 `legacy.CMD_ECHO_OFFSET`）测试有/无 `0xA0`、`BlockingIOError` 与读取 `OSError`；用注入 transport 的 `main()` 测 CLI 拒绝 `--observe-forceadapt-echo` 的 dry-run、medium/strong/both，以及有界候选路径只产生 `[Normal L, Normal R, effect, Normal L, Normal R]`。计时测试令观察消耗 0.05 s，断言后续 `sleep` 不超过 `duration-0.05` 且清除失败仍非零。示例关键断言：

```python
frame = bytearray(legacy.REPORT_LEN)
frame[0] = legacy.INPUT_REPORT_ID
frame[legacy.CMD_ECHO_OFFSET] = legacy.CMD_FORCEADAPT
now = [10.0]
def fake_clock():
    return now[0]
def fake_waiter(readers, _writers, _errors, _seconds):
    now[0] = 10.11
    return (readers, [], [])
self.assertEqual(tool.count_forceadapt_echoes(
    7, 10.1, clock=fake_clock,
    waiter=fake_waiter, reader=lambda _fd, _size: bytes(frame)), 1)
```

- [ ] **Step 2: 运行红灯。** `python3 -m unittest tests.test_forceadapt_tool -v`；新增用例必须因缺函数/缺 CLI 门禁而 FAIL，不因拼写、模拟 fd 或构造帧错误失败。
- [ ] **Step 3: 加最小同 fd 计数函数。** `select.select` 每次最多等待 `min(0.02, deadline-now)`；只读 64 字节输入帧，`legacy.command_echo(data)==legacy.CMD_FORCEADAPT` 才加一；`BlockingIOError` 继续，其他 `OSError` 交给调用方标 UNKNOWN；绝不写任何命令。

```python
import select

def count_forceadapt_echoes(fd, deadline, *, clock=time.monotonic,
                            waiter=select.select, reader=os.read):
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
```

- [ ] **Step 4: 加 CLI 门禁与时序。** 解析后拒绝未搭配 `--write` 的观察、`--effect medium|strong`、`--side both`；保持现有 `--candidate` 与 `--effect` 互斥。唯一非候选入口必须显式为 `--effect mild --side left|right`。写入前已完成的初始双侧 Normal 后，用同一 fd 最多 100 ms 清空排队回复；若该段读取失败，进入 `finally` 双侧 Normal 且不发送非 Normal。写入固定效果成功后记 `t_effect=time.monotonic()`，观察至 `min(t_effect+0.1,t_effect+duration)`；打印 `A0_ECHO_OBSERVED count=N` / `A0_ECHO_NOT_OBSERVED` / 读取失败的 `A0_ECHO_UNKNOWN`。再 `time.sleep(max(0,t_effect+duration-time.monotonic()))`，不能使用原 `time.sleep(duration)` 额外延长窗口。保持原 `finally` 双侧 Normal 与失败返回非零。

```python
parser.add_argument("--observe-forceadapt-echo", action="store_true",
                    help="bounded same-fd diagnostic of the existing 0xA0 echo")
# After parse_args, before opening or writing a device:
if args.observe_forceadapt_echo and (
        not args.write or
        (not args.candidate and
         (args.effect != "mild" or args.side not in ("left", "right")))):
    parser.error("echo observation requires --write and a fixed candidate or one-side mild")

# Inside the existing write try/finally, after its two initial Normal writes:
if args.observe_forceadapt_echo:
    count_forceadapt_echoes(fd, time.monotonic() + 0.1,
                             clock=time.monotonic)
transport.write_effect(effect)
t_effect = time.monotonic()
if args.observe_forceadapt_echo:
    try:
        echoes = count_forceadapt_echoes(
            fd, min(t_effect + 0.1, t_effect + duration),
            clock=time.monotonic)
        print("A0_ECHO_%s count=%d"
              % ("OBSERVED" if echoes else "NOT_OBSERVED", echoes))
    except OSError:
        print("A0_ECHO_UNKNOWN (read failed)")
    time.sleep(max(0, t_effect + duration - time.monotonic()))
else:
    time.sleep(duration)
```

  上述为 `main()` 内关键顺序；已有实际代码在效果循环、SIGTERM 和 `finally` 周围，编辑时不要复制第二个写入/复位路径。初始排队回复与后续 echo 仍可能无法逐帧归属，文档与日志必须保持该限制。
- [ ] **Step 5: 绿灯与回归。** `python3 -m unittest tests.test_forceadapt_tool tests.test_adaptive_triggers tests.test_regressions -v`，随后 `python3 -m unittest discover -s tests -q`、`python3 -m compileall -q apex4ds5 tools apex4-ds5`、`git diff --check` 全部退出 0；`--candidate l2-resistance-40` 不加 `--write` 的本地预览仍不打开实体节点。
- [ ] **Step 6: 精确本地提交。** 仅 `git add tools/forceadapt-test.py tests/test_forceadapt_tool.py && git commit -m 'test: observe bounded ForceAdapt echo without extra writes'`。

### Task 2: 完整私有输入日志与 SteamOS 软件门禁（离线/无需持柄）

**Files:** `docs/VALIDATION.md`, `docs/evidence/2026-09-23-generic-candidate-steamos.txt`。

**Interfaces:**
- Consumes: Task 1 的 `WRITE accepted t=...`、`Normal reset complete t=...` 与 `A0_ECHO_*`，及现有 `input-source-watch.py --physical-only` 文本行。
- Produces: 一个可复制的私有日志采集/筛选流程，原始事件不进入 git，脱敏摘要能证明按压是否跨越真实效果窗口。

- [ ] **Step 1: 写运行手册。** 在 `docs/VALIDATION.md` 的 2026-09-23 节追加下列私有日志流程，明确工具执行前后仍需持握者单独批准；`APEX4_INPUT_LOG` 是任务专用变量，不存密码或 MAC：

```sh
umask 077
APEX4_INPUT_LOG=$(mktemp "${XDG_RUNTIME_DIR:-/tmp}/apex4-input.XXXXXX")
set -o pipefail
python3 -u tools/input-source-watch.py --physical-only --seconds 120 \
  | tee "$APEX4_INPUT_LOG" | awk '/^READY/ {print; fflush()}'
```

  测试后用同一主机单调时钟的 `t_effect` 和 `t_normal`，只筛该侧；以下以 R2 `0x009` 为例，L2 改为 `0x00a`。要求至少一个“低值→≥64→≤5”的完整序列，不只取到零星事件：

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

- [ ] **Step 2: 验证摘要命令。** 用下列 5 行合成输入替代真实日志、`APEX4_EFFECT_T=10`、`APEX4_NORMAL_T=11` 跑上段 `awk`，期望 `events=5 min=0 max=128 full_cycles=1`；再把 `code=0x009` 改成错误侧 `0x00a`、把全部 `t` 改到 11 之后，确认都不能得到有事件 PASS。仅将命令与样本摘要写入文档，不把原始输入日志或本机路径提交。

```text
t=10.100000 source=physical type=abs code=0x009 value=0
t=10.200000 source=physical type=abs code=0x009 value=32
t=10.300000 source=physical type=abs code=0x009 value=128
t=10.400000 source=physical type=abs code=0x009 value=4
t=10.500000 source=physical type=abs code=0x009 value=0
```
- [ ] **Step 3: SteamOS 软件回归。** 从唯一提交做归档与 SHA，放独立验证目录；远端脏 checkout 不动，已安装默认仍 disabled。运行 177 项以上全套测试、Python compile、CLI 负面组合和 `--candidate` 纯 dry-run；不使用 `--write`，不启动 Steam/游戏，不停 daily relay。回执观察只能被测试桩验证，不能称 SteamOS 物理 ACK PASS。
- [ ] **Step 4: 精确提交文档。** 只 stage `docs/VALIDATION.md` 和必要的脱敏证据更新；不 push、merge 或改当前 Steam 启动选项。

## 完成门禁

此子计划仅在本地/SteamOS 软件检查通过、无新增 vendor 写命令、既有 Normal/锁/身份行为不变、私有日志筛选可复现时完成。下一次实体测试的参数与动作需重新提交持握者批准；mode 1 实体可用性、默认 Edge+generic-safe 的生产验收、Proton 输入源和 Edge 游戏输出均仍为独立未闭合门禁。
