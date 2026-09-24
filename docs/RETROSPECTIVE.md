# APEX 4 项目复盘与后续推进依据

> **2026-09-24：项目已终止。** 本文保留历史复盘；当前结论与终止原因见
> [PROJECT_CLOSURE.md](PROJECT_CLOSURE.md)，不再按旧交付计划推进。

当前执行路线见 [DELIVERY_PLAN.md](DELIVERY_PLAN.md)；下文保留阶段审查历史。

## 2026-09-21 原生目标纠偏与进度调整

用户报告 OW2 始终为 Xbox 键位，并指出效果应由游戏原生 DualSense 适配决定。
这一判断正确：游戏输出决定类型、变化与 Off，relay 负责协议和能力映射。
bounded/early-trigger 的一秒固定 resistance 是受限诊断，不能当作完整原生反馈。

最新实体测试仅首个周期执行，机器 mode 1 `(60,40)` 与随后双侧 Normal 写入成功，
持握者明确“没感觉到”；不继续第二、三次，退出后已恢复 dry-run。
后续 `f213d72` 将游戏 rattle 输入改为同一 resistance；实际游戏 dry-run 显示
21:14:23 `0x26` 与 mode 1 输出、21:14:24 Normal。它证明替换路径，不能证明
无感的原因或修正版实体效果。此前“已经定位为满压时机”的说法撤回为待验证假设。

加速方式是减少无新信息的人工循环：先离线完成语义表和同步采样，再把输入来源、
Xbox 图标与效果时间轴合并到一次 dry-run。准备精确模式/参数后集中进行获批实体测试，
不逐个脉冲要求退出、改配置、重新启动。正常退出通过和 99 项软件测试不覆盖全部异常
恢复，仍只按具体场景记 PASS。详见当前交付计划的门禁和停损点。

该综合 dry-run 随后取得了所需证据：动作窗口只有物理 Flydigi 与虚拟 Sony 成对事件，
常驻 Xbox 源无按键/扳机事件，因此 Xbox 图标不再作为映射故障处理。三次 R2 周期均在
R2=11..14 收到 `0x26`，约 0.72 秒后在 R2=129..255 收到 `0x21`，释放 R2=0 时收到
`0x05`。这否定“阻力总在压到底后才到达”，也显示 compatibility 与 decoded semantic
在 rattle 强度、resistance 起始区/强度上存在实质差异。下一步应分模式获批真实参数，
而不是继续提前触发固定 `(60,40)`。完整报告见可执行 fixture 与同步证据文件。

审查日期：2026-09-20。审查基线：`0ac0c8b`，以及未提交的整体路线图。
本轮只审查并修改文档；未连接 Deck、未启动游戏、未执行实体写入。
部署状态引用本项目上轮记录（运行时代码 `b820aee`），不是本轮远端实时核验。

## 总体判断

技术路线可达原始目标：游戏原生 DualSense HID 输出，经独立 parser、translation、
state manager 与 identity-gated ForceAdapt transport 驱动 APEX 4。无需重新选择协议
或把 Steam Input 当作效果生成器。但项目目前达到的是**可行性与受限链路验证**，
还没有完成“持续、随游戏动作变化且异常可恢复”的动态扳机产品验收。

原计划把异常恢复放到后期、把重复 mild 当作动态能力的下一步，顺序需要调整。
应先修复会话与效果生命周期，再验证翻译语义和模式专属边界，然后进行持握者确认的
持续动态测试。完整参数可以继续显式 opt-in，默认开启不是项目成功的必要条件。

## 现有结论的有效范围

| 结论 | 复核判断 | 不能推导出的结论 |
|---|---|---|
| 普通 DualSense 收到 OW2 R2 `0x26 -> 0x21 -> 0x05` | 本次游戏/Proton/场景下有直接日志证据 | 所有 PC 游戏或所有 Proton 版本均支持 |
| 干净单 Edge 对照窗口无动态输出 | 保留为该场景负结果；普通身份是可行兼容方案 | OW2 永远不支持 Edge；根因已确定为 PID |
| 第一次双 relay 的 Edge 零输出 | 无效样本，原纠正正确 | 可以加入有效对照样本计数 |
| 单次 R2 固定 `(60,40)` resistance 被感觉到 | 游戏报告触发实体效果的链路成立 | 原始 rattle/resistance 的触感、强度、频率或连续变化已通过 |
| 自动切换、正常退出恢复、菜单控制 | 一次真实 OW2 会话和用户确认成立 | 崩溃、任意阶段 SIGTERM、SIGKILL、并发会话均恢复 |
| 2.4G/有线双侧 mild | 既有记录支持这些指定测试 | 所有模式、参数、固件以及 DeviceType 103 均由本项目实测 |
| HID write 成功、Normal write 成功 | 主机侧发送成功 | 硬件 ACK 或实体必定已解除阻力；仍需触感/观察证据 |
| 78 个测试通过 | 本轮重新执行通过 | 未覆盖异常、效果忠实性、长期稳定性也通过 |

来源：[原生游戏证据](evidence/2026-09-20-ow2-native-game.txt)、
[身份会话证据](evidence/2026-09-20-controller-profile-session.txt)、
[协议和验收说明](DSX.md)。DeviceType 103 的允许依据是公开参考验证，需与本项目
DeviceType 84/firmware 6837 的实测分开标注。

## 已确认的代码缺口与影响

### P0：会话恢复并未覆盖完整生命周期

`tools/proton-game.py::run_profiled_command` 先进入 `RelayProfileSession`，
才调用 `run_child` 注册 SIGINT/SIGTERM。子进程结束后又先恢复旧 handler，才执行
会话清理。因此切换进入及恢复阶段存在 SIGTERM 默认终止空窗。

本轮用独立 Python 子进程、假的 session（无 systemd/HID）复现：在 `__enter__`
发送 SIGTERM，返回 `-15`，未观察到恢复标记。它证明 handler 覆盖空窗，不是一次
新的 Deck 故障报告。`__enter__` 中的 `except BaseException` 不能捕获默认 SIGTERM。

`run_child` 只向直接子进程转发信号，无期限 `wait()`；异常分支调用 `terminate()`
后不等待终止。不能保证 Steam/Proton 后代退出后才恢复身份。
`game_session.py` 的外部命令也没有 timeout；5 秒仅限制 sysfs 等待，不能限制
整个服务操作。现有信号测试是 fake child 主动调用 handler，未覆盖这些窗口。

修复验收：进入、游戏等待、恢复三个阶段都覆盖取消；所有外部操作有界；直接子进程
与后代的存活语义有真实 subprocess 测试；先核实本次拥有的进程结束再恢复。
SIGKILL/进程崩溃可采用独立 user-systemd 恢复机制，或清楚保留手动恢复限制，不能
继续宣称“任何异常自动恢复”。

### P0：效果时效与 reset 语义尚不满足受限动态测试

`apex4-ds5` 对任何已识别 report ID 调用 `note_output()`；
`TriggerStateManager.handle` 在判断效果是否有效前也刷新一个全局时间。
因此灯光/rumble/另一侧输出能延续已有阻力。默认 watchdog 为零是兼容性选择，
不提供持续时间保护。

离线复现：R2 resistance 后模拟时间推进到 10 秒、调用 `note_output()`，在
`reset_timeout=1` 下 `expire()` 仍返回 None，末次效果 mode=1。
另一个 fake transport 在默认 timeout=0、`queue_pending=True` 下输出
`[Normal L2, Normal R2, 旧 resistance]`：延迟 attach 能重放无 TTL 的 pending。
这不证明每次重连都会重放，但否定了“从不重放过期效果”的无条件保证。

`OneShotMildGate` 的一秒检查由主循环协作执行，不是硬件独立定时器；不应描述为
进程卡死或主循环繁忙时仍绝对一秒解除。`clear_all` 是复位尝试；失败后
UNKNOWN 不能计入安全验收 PASS。

修复验收：分别定义 L2/R2 有效输出时钟、非续期活动 deadline、pending TTL/代际
失效和 reset 失败状态；无关/未知报告不能延长测试预算。模拟 EAGAIN、短写、断连、
reset 失败、延迟身份确认和主循环积压；新连接必须重新确认，不自动补发旧动作。

### P1：进程锁不是游戏会话所有权锁

`relay_lock.py` 保护单 relay 进程，但包装器预检、stop/start、restore 没有会话锁。
两个包装器可能同时通过预检，随后通过 `apex4-relay start/stop` 相互停止对方。
恢复命令会停止项目服务，却不核验其是否仍属于本会话。锁路径还取决于
`XDG_RUNTIME_DIR`，存在新旧版本或不同环境绕过同一锁域的情况。

修复验收：切换前持有唯一会话租约/锁，记录本次 service invocation 所有权；
冲突立即拒绝且不触碰已有会话。恢复只处理本次资源。添加双包装器竞争、人工介入、
服务重启与不同环境路径的测试。身份检查还需与服务/PID 对应，不能只靠名称和 VID/PID。

### P1：翻译是兼容映射，不等于通用语义忠实性

`trigger_translation.translate` 虽然先解析 normalized effect，主要 `0x21/0x25/0x26`
分支仍使用原始字节特判和左右不同规则。例如 R2 feedback 的一般 fallback 固定到
`(1,1)`，`0x26` 强度使用 `((p[1]+1)*30)&0xff`。因此不能仅凭 parser 解出区域/强度
就认定映射保留这些语义；上游兼容经验也不是当前硬件的触感验收。

下一步补合法区域/强度/频率的参数扫描与不变量，区分“协议支持”“上游特例”
“近似 fallback”“本地实测”。先评估 generic normalized mapping 与现有特例差异，
保持 OW2 已知向量回归，再决定保留、限制或替换具体分支。无需整层重写。

### P1：数值范围、模式安全及性能不能互相替代

`forceadapt.py` 的 byte clamp 只保证可编码，不是已验证安全强度。
本项目的 resistance `(60,40)` mild 不能用来证明 rattle 的 pressure/strength/frequency
也 mild。OW2 `0x26` 目前映射为 **MODE_RATTLE=2**，不是 MODE_VIBRATION=5；计划
必须用精确模式命名。rattle 的保守候选值仍需独立持握者验收。

输入循环直接进行非阻塞 HID write，没有独立 worker；这可以继续保留，但需测量
输入间隔/循环延迟及高频“变化效果”（不仅相同效果去重）。在出现数据前不引入新线程。
本轮没有新的延迟或 rattle 硬件测量。

## 推进过程复盘

有效做法：先探针再游戏；纠正双 relay 无效样本；把“没感觉到”与后续成功分开；
保留远端脏 checkout；使用独立测试目录与可回滚安装；请求持握者动作前确认。

需要改进：

- 最初过早把物理设备泄漏当作完整根因；后来滤除后仍无输出、再做身份对照才收敛。
  后续每个假设都应有能否定它的观察，零输出也必须先确认观察的是游戏实际连接对象。
- “78 测试 PASS”“异常会恢复”“锁防止重复实例”混用了不同范围；以后声明必须对应
  场景与失败注入，不能用方法调用的 mock 替代真实进程生命周期。
- 默认日志不打印成功写入，所以“没有 ForceAdapt 日志”单独不能证明没有写入。
  本次无写入结论还有 `adaptive_triggers=false` 和无覆盖参数支持；应保留这些配置证据。
- 文档顶部状态与后文历史出现矛盾（DSX 仍说原生游戏待验证）；当前状态集中放在
  CONTINUE，历史证据追加更正，计划只写未来事项及门禁。
- 方案/计划篇幅多于已落实的异常测试，且旧实施计划的复选框未更新。
  已执行的旧计划作为历史设计，不再当作当前完成状态；以后按验收证据更新当前清单。
- 附件与终端中使用过认证口令；后续避免把口令放进搜索、命令文本、日志或文档，使用
  受保护的交互认证。此次文档不保留连接凭据。

## 修订后的推进顺序与完成定义

1. **G1：先补恢复与所有权。** 修复 P0 信号空窗、有界等待，P1 会话互斥/资源归属。
   用真实短命子进程做退出/信号/失败注入；再在 Deck 做已明确范围的无游戏演练。
2. **G2：效果状态及语义审计。** 补独立超时、pending、reset 失败测试；为现有翻译
   建立参数化不变量。把已采集游戏输出转为脱敏重放 fixture，原始完整报告缺失则明确
   标注为依据摘录重建，不能冒充原始捕获。
3. **G3：一套可 dry-run 的受限策略。** 策略与 transport 分开，允许相同策略在 fake、
   dry-run 和真实 transport 上执行；CLI 使用互斥模式选择及独立 write 授权。
   明确 Normal 后重新武装条件，并同时限制每周期、总会话时间及次数，防止 Off 高频
   重新武装绕过预算。定额 mild 可作为调试，但不是最终动态验收。
4. **G4：分模式动态实机。** resistance 与 rattle 分开批准候选参数和时限，先单侧、
   再重复动作；只有上一阶段机器与用户证据均通过才扩大。若 OW2 无真实 L2 动态输出，
   保留 OW2 L2=N/A，另用合成输出/其他已具备的游戏验证 L2，不让未知英雄机制阻塞项目。
5. **G5：游戏价值与发布。** 同一会话观察游戏非 Normal→实际效果变化→Off/退出解除，
   用户可辨识至少两种受支持变化；2.4G/有线、游戏输入/IMU/普通震动、退出后 Edge
   背键做针对性回归，测试安装升级与回滚。检查许可交付物后再请求发布决定。

全项目完成不要求其他型号、GUI/Decky、所有游戏或默认无限制写入。首版可以明确
只支持经验证的模式与游戏；必须真实完成持续动态映射和异常清除，并公开不支持项。
启动选项目前是手动 opt-in，代码并没有 OW2 AppID allowlist；它不是自动识别游戏的数据库。

## 可验证的下一批工作

| 优先级 | 交付物 | 验收门禁 |
|---|---|---|
| P0 | 全生命周期取消、外部命令 timeout、等待退出 | 进入/运行/恢复每阶段注入 SIGTERM；无孤儿进程；恢复结果可确认 |
| P0 | 每侧 freshness、活动 deadline、pending 失效 | LED/另一侧/未知报告不能续期；旧代际效果不重放；reset 失败停止并报告 UNKNOWN |
| P1 | 会话所有权与锁域统一 | 两个包装器争用时一个成功、另一个无副作用；人工介入不被误清理 |
| P1 | 翻译向量和模式候选表 | 合法参数边界、无意外取模/语义丢失；标明近似与未实测 |
| P1 | 策略与 dry-run 共用 | 同一输入在 dry-run 与 fake transport 的最终 effect 完全一致 |
| 硬件门禁 | 受限 resistance/rattle 实测 | 每次获侧别/模式/参数/时限确认；机器与用户均通过；失败即停 |

## 本轮检查与限制

本地 `python3 -m unittest discover -s tests`：78/78 PASS。
三个无硬件复现结果：`SIGTERM_during_enter=-15, restore=False`；
`unrelated_output_prevents_expiry=True`；`pending_attach_modes=[0,0,1]`。
这些结果定位已实现行为与表述的差距，不是修复验收；本轮未修改生产代码。

许可：仓库已有 `THIRD_PARTY_NOTICES.md`，记录 MIT 来源与 GPL 参考用途。
本轮未重新联网审查上游，也没有完成独立法律审查。后续 `8e159d7` 已用失败优先的
临时安装测试修复运行时遗漏，安装脚本现在复制仓库根 LICENSE/THIRD_PARTY_NOTICES，
SteamOS 部署文件与验证归档逐字一致；独立法律审查仍不在本项目测试结论内。

整体路线图位于 `../.omx/plans/2026-09-20-apex4-overall-roadmap.md`，已按本次门禁修订。

## 2026-09-21 SteamOS 离线期间的本地修复

以下变更已实现，并在本节末尾补充 SteamOS 软件/dry-run 验证；仍没有新的游戏或实体
硬件证据：

- SIGINT/SIGTERM handler 现在覆盖 profile 进入、子进程等待和恢复全过程；取消发生在
  进入阶段时不会启动游戏，恢复阶段的信号不会中断清理。
- user-systemd 查询和 `apex4-relay` 控制命令有 10 秒上限。游戏子进程收到终止信号后
  等待 5 秒，仍不退出则 terminate、随后 kill，并执行有界 reap。
- profile session 新增独占锁；启动后记录手动 service 的 systemd InvocationID，恢复前
  核对所有权。发现 service 被替换或日常 Edge 在会话中被人工启动时拒绝误停。
- trigger freshness 改为 L2/R2 分侧、只由有效映射效果续期；普通 output、未知效果或
  另一侧效果不再延长陈旧阻力。pending 默认 2 秒 TTL，attach 即使没有先 poll expire
  也不会重放过期效果。
- `0x21/0x26` active-zone mask 超过合法 0..9 区域时现在 fail closed。
- 新增 `--trigger-bounded-mild-right`：最多三个 R2 resistance 周期，start 不小于 60、
  strength 不大于 40，每周期最多 1 秒，交互窗口最多 30 秒。忽略 L2 和 rattle；支持
  `--trigger-dry-run`，与 unrestricted/one-shot 写入模式互斥；transport disconnect
  会永久锁止本次策略，不会在重新连接后继续旧周期。

最终本地验证：97/97 tests PASS，Python compilation、shell syntax、`git diff --check`
PASS。SteamOS：95 tests PASS、1 项无 C 编译器跳过；InvocationID 所有权、正常切换、
忽略 SIGTERM 子进程的有界退出、唯一 Edge 恢复和四周期/三次接受的 bounded dry-run
通过。`dbde16f` 已可回滚部署，Steam 启动选项已切到 bounded dry-run。下一门禁是实际
OW2 dry-run；此前不得进行新的实体写入。

第一次实际 OW2 bounded dry-run 中，用户完成三次蓄力；前两次分别在相隔约 7 秒的
时点被接受，原 10 秒总窗口随后强制 Normal，第三次被拒绝。安全预算按设计生效，
但窗口不符合正常人工节奏。默认窗口据此改为 30 秒；周期数仍为 3、每周期仍为 1 秒，
所以最大活动输出时间仍不超过 3 秒。该修订需重新部署并复测游戏 dry-run。

三十秒修正版 `e2338b8` 随后在 SteamOS 运行 97 项测试（96 PASS、1 C-compiler skip）。
以 7 秒间隔注入三个虚拟周期时三次均输出 `(60,40)`/Normal，紧接的第四次仍被拒绝；
修正版已可回滚部署。重复实际 OW2 dry-run 中，三次半藏蓄力分别产生三组
`(60,40)`/Normal，退出后恢复唯一 Edge，无错误或实体写入。G3 的实际游戏 dry-run
门禁由此通过；下一步是单独授权的 bounded physical resistance，不包含 rattle。

物理门禁所需的固定 `bounded-write` 包装器模式随后通过本地 99 项测试和 SteamOS
99 项测试（98 PASS、1 C-compiler skip），并部署为 `4cf1515`。preview 明确打印 R2、
mode 1、`start>=60`、`strength<=40`、每周期一秒、最多三周期/三十秒。Steam 仍保留
`bounded-dry-run`，没有启用真实写入。
