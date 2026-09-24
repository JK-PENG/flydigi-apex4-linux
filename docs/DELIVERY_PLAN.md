# 原生动态扳机交付计划（2026-09-22 生产加固修订）

> **历史计划，已停止执行（2026-09-24）。** 当前结论与终止原因见
> [PROJECT_CLOSURE.md](PROJECT_CLOSURE.md)；以下步骤不再是待执行任务。

> 2026-09-23 目标更新：用户已确认“默认 DualSense Edge + 通用自适应扳机；仅在游戏
> 不支持 Edge 时通过单游戏启动选项降级普通 DualSense”。本文以下 OW2 专用路线保留为
> 已执行历史和证据边界，不再是后续实施顺序。当前实施入口为
> [默认 Edge 与通用 ForceAdapt 计划](superpowers/plans/2026-09-23-default-edge-generic-forceadapt.md)。

## 目标与当前结论

首个交付目标：APEX 4 在 SteamOS 下，按支持的 PC 游戏实际发送的 DualSense 效果，
连续产生可辨识的反馈变化，按游戏 Off 清除，并在退出/异常时安全恢复。
允许清楚记录的硬件近似和保守强度上限；不以“任意一次阻力被感觉到”替代目标。

本文件是后续工作的当前执行顺序，取代旧路线中“继续 fixed mild/early-trigger 试触感”
作为主线的安排。历史实验保留在 VALIDATION 和 evidence；CONTINUE 负责当前交接状态。
本地 `.omx/plans/2026-09-20-apex4-overall-roadmap.md` 保留历史并指向本文件。

截至 2026-09-22 当前记录：

- `85cb93b`/`9bf7a54`/`5d35156` 已部署：命名 `ow2-safe` 连续 profile、严格配置门禁、
  每周期 4 秒 reset、精确 OW2 模式/顺序、共享 writer lock 和可回滚原子 installer。
- OW2 普通 DualSense 的三轮 2.4G 与一次有线实体反馈通过；三轮均由 game Off 清除，
  持握者确认震动、阻力和松开后正常。Edge 恢复、背键和六轴 IMU 回归通过。
- Xbox 图标期间物理 Flydigi 与虚拟 Sony 输入成对、常驻 Xbox 源无事件，限定为非阻塞
  界面行为；OW2 动态 L2=N/A，沿用已有 synthetic/cable L2 mild 证据。
- 本地 145/145 PASS；SteamOS 144 PASS/1 compiler skip。公开 installer 已真实升级、
  重启到新安装路径并保留旧 runtime；旧 false 配置迁移为 `trigger_profile=disabled`。
- 手柄当前离线，最终五周期 real-virtual dry-run 被唯一 Edge preflight 安全拒绝，未启动
  manual relay、游戏或硬件写入。Steam 仍为 `translation-dry-run`，未启用生产写 profile。

## 为什么调整

原生模式的时序应由游戏控制。当前 bounded 模式忽略/替换部分效果并在一秒后清除，
目的是控制诊断写入风险。它改变类型、参数和保持时长；30 秒、三次及 early-trigger
测试证明诊断策略执行正确，不能证明游戏原生反馈正确。

保留诊断模式，停止围绕半藏调整压力时机/固定脉冲以追求“感觉到”。
不要为图标、更多游戏、GUI 或全面架构重构开新长线。先闭合一个支持场景的真实反馈。

## A：一次离线准备，产出一个候选版本

无需持握者操作，可连续完成。默认不用新增运行时依赖或新守护进程。

1. **效果语义表与重放向量。** 审查 `trigger_translation.py` 的 `0x21/0x26/0x05`
   主路径及左右差异。明确哪些字段来自 normalized 语义，哪些是上游特例/近似。
   检查区域、强度、频率、零效果和合法边界；避免以现有实现自身作为唯一正确性标准。
   OW2 完整原始报告若缺失，标记重建向量，后续统一补采，不冒充原始抓包。
2. **分离诊断替换与原生转译。** 尽量复用现有 unrestricted translator/state manager，
   将强度限制作为模式专属策略；保留游戏的效果变化顺序及 Off。不能把 `0x26` 一律
   换成固定 resistance 后宣称保留 vibration 语义。硬件不支持的近似需文档化。
   先检查通用映射是否足够，只修改证明有问题的分支。
3. **验证仍未闭合的生命周期关键项。** 重点覆盖主循环 deadline 到期时新的报告、
   reset 失败锁止、未知输出/Off 续期、断连后不回放旧效果。会话命令超时并不证明
   systemd job 或 Proton 后代都退出；保留这些限制，物理候选所依赖的清理路径必须可证。
4. **准备单一采样入口。** 复用 `--hid-debug` 和现有采集工具，补足统一单调时钟下的
   物理 R2 模拟值、原始输出、转译决策/过滤原因、write 与 reset 结果。检查采样自身
   不阻塞输入循环，日志有界且脱敏。能复用现有工具时不另造框架。

出口：一个候选提交 + 针对性回归 + 最终全量回归 + 脱敏重放结果。
同一批本地改动完成后只做一次远端验证/部署，失败再改。不要每个测试新增都部署。
尚未完成翻译/复位门禁时，不开始新的实体测试。

## B：一次只读调查，按证据处理 Xbox 图标

先检查现有 Steam 设置和历史日志，不启动游戏即可查明的内容先做。
需要实际进程时，与 C 的游戏 dry-run 合并采样。

记录物理 APEX、虚拟 Sony、Steam/Deck 虚拟 Xbox 的枚举和可能使用者；核对 Steam Input
有效设置及 Proton 过滤变量。只读枚举、打开 fd、手柄图标分别代表不同证据，不能相互替代。

- 发现两条活跃输入路径或重复事件：做最小、可回滚、限定该游戏的排除对照，再复测。
- 只有图标不符，输入无重复、原生报告与动作对应：记录为界面兼容问题，不阻塞扳机路径。
- 无法确认来源：标 UNKNOWN，带入一次集中采样；不猜测“游戏只支持 Xbox 图标”。

调查以一个诊断批次为限；没有新证据不反复改 VID/PID、全局屏蔽设备或切换 Proton。
项目不要求 PlayStation 图标作为物理反馈验收的前置条件。

## C：一次集中游戏 dry-run

事先把候选版本、采集、退出恢复和分析脚本准备好。沿用用户要求：启动前通知并确认，
操作前通知并等持握者就绪；已批准的同一测试块不逐次重复索取授权。

推荐一个短动作块：缓慢压入/释放 R2、正常完整蓄力/释放、持续保持、退出。
每个动作给出可重复说明，至少记录三次有效周期；不要求赶在诊断一秒预算内判断触感。
这轮无实体扳机输出，可一次收集：

- 输入源、Xbox 图标现象、真实 R2 位置与动作时间；
- 游戏 `0x26 -> 0x21 -> 0x05` 原始序列及原生转译结果；
- 是否有输入重复、游戏 Off 是否对应释放、效果延迟；
- 正常退出后的唯一 Edge 和 service 恢复。

出口：针对候选版本的一份时间对齐记录。由它判断早晚时机假设，确定物理测试的
具体模式/参数/保持规则；不能再只凭秒级 journal 行推断扳机已压到底。
如果采样已充分、软件策略没变，下一轮无需再重复三次相同 dry-run。

## D：一次事先批准的实体测试块

先提交具体的侧别、模式、参数上限、最大保持时间、总预算和退出/reset 行为，
按用户既有要求等持握者确认。此前的 resistance 授权不涵盖新 rattle 参数。
默认关闭真实写入；不靠全局 adaptive=true 来简化测试操作。

第一步可用已知 `(60,40)` 单次短测试作为阳性对照，确认当日设备能产生触感；只在
需要隔离硬件状态时做一次。随后在批准范围内测试语义保留的游戏效果：
游戏选择开始/变化/Off，安全上限约束强度与异常保持。安全超时触发应标为“被截断”，
不能把截断样本计作完整原生保持语义 PASS。

同一获批块中可依次检查多个动作，实时看日志并反馈；错误、异常感受或 reset UNKNOWN
立即终止该块。根据观测选择下一项，不要求每个周期退出游戏、修改启动配置并重启 Steam。
若现有工具无法安全控制同一会话，则使用明确分开的两轮；不为减少一次重启新建复杂控制面。

成功条件：游戏触发连续变化，最终硬件效果能被持握者辨识，Off/退出恢复均有机器与
用户证据。rattle 尚未验收时不得宣称完整 OW2 反馈；可发布明确限定模式的实验版。
结束恢复 dry-run，并验证配置持久化及唯一 Edge。

## E：集中回归与交付

2.4G 首个场景闭合后，集中补有线、左右通道、重连/异常清理、输入/gyro/rumble、
返回 Edge 后背键、安装升级回滚和许可 notices 随包交付。OW2 若无 L2 动态报告，
用合成或其他已有场景验收 L2，标注 OW2 L2=N/A，不等待猜测英雄动作。
全面性能优化、其他型号/游戏、Decky/GUI 延后。合并、push、PR/发布仍需用户决定。

## 执行规则与停损点

- 每项工作必须对应一个未闭合的验收问题；已通过的相同探针不无理由重跑。
- 测试数不是进度目标；新测试要区分候选行为与既有缺陷。
- 一个候选版本一次综合部署，按提交记录安装内容与回滚路径。
- 预计用户参与为“一次综合 dry-run + 一次获批实体测试块”，不是通过承诺；发现
  reset 或模式参数问题时必须补验证，不能为减少轮次放宽门禁。
- 连续两次触感失败而机器写入成功：停止改压力/时机，回到阳性对照与同步输入采样。
- 当前 early-trigger 替换只是诊断能力，暂停其实体复测作为主线。没有实体对照证据前，
  不将“时机已修复”写入完成状态。

## 下一步与待办

- [x] 完成 A 的翻译语义表、关键安全回归、可重放数据和统一采样准备。
- [x] 完成 B：动作窗口无 Xbox 输入事件，图标限定为非阻塞界面差异。
- [x] C 综合 dry-run：动作、原始报告、时间轴及退出后唯一 Edge/service 恢复均通过。
- [x] D 三周期实体模式变化与 active game-Off 清除通过；每轮用户确认效果与正常恢复。
- [x] E 技术回归：许可/notices、安装、2.4G/有线、返回 Edge 背键与 IMU 通过；仅发布决定待用户授权。
- [ ] 生产发布门禁：`ow2-safe` 与原子安装已修复、复审通过；待最终提交安装、手柄在线五周期 dry-run 和生产配置验收。

本计划调整不启用任何实体写入，也不视为新游戏启动或 rattle 测试授权。

当前候选 `f3a1f57` 已部署；本地 117 tests PASS，SteamOS 116 PASS/1 compiler skip。
真实夹具经 `native-dry-run` 重放为 mode 2 `(0,1,32,21,0)` → mode 1
`(0,40,0,0,0)` → Normal，并共用首个效果起算的一秒截止时间。Steam 启动选项仍为
`translation-dry-run`，`native-write` 已在一次获批测试后恢复为 0，全局 adaptive=false。
持握者已明确感觉到 mode 2 震动和 mode 1 阻力；一秒 timeout 双侧 Normal、正常退出与
唯一 Edge 恢复通过，并确认最终 R2 行程完全正常、无残余。松开后的增强震动已由报告证明是游戏普通 rumble `(255,255)`，
不是扳机二次触发。由于游戏 Off 晚于 timeout，本样本未直接验收活动效果由 Off 清除。

加速后的 `ded4178` 候选把剩余 D 项合并：R2 同参数、最多三周期/30 秒、每周期最多
4 秒、总活动最多 12 秒；Off 在 deadline 前到达即写 R2 Normal 并重新武装，deadline
先到则双侧 Normal 且等待 Off 才能重新武装。四轮真实报告 dry-run 只接受前三轮，
本地 124 PASS、SteamOS 123 PASS/1 compiler skip，已部署但仍未启用。下一步只需一次
明确获批的三次及时释放实体块，不再重复游戏 dry-run。

该实体块已完成：三轮均为 mode 2 → mode 1 → 游戏 Off → R2 Normal，分别在约
1.30/1.39/1.84 秒完成，没有 safety timeout、write failure、错误侧别或第四周期。
持握者确认三轮均感觉到震动和阻力，且每次松开后 R2 正常。退出与唯一 Edge 恢复、
`translation-dry-run` 安全配置恢复通过。D 阶段闭合，进入 E 集中回归与交付。

E 自动部分已推进到 `8e159d7`：安装测试先复现 notices 缺失，再修复为复制根 LICENSE
与 THIRD_PARTY_NOTICES；本地 125 PASS、SteamOS 124 PASS/1 compiler skip，已部署且
文件字节一致。安装运行时的 2.4G 自检通过 uhid、hid_playstation、vendor identity 与
1.02 g sensor stream。剩余人工项应合并为一次有线原生短样本和返回 Edge 后输入/背键/
gyro/rumble 核对，不再重复已闭合的 2.4G 三周期测试。

有线最终块已通过：DeviceType 84 wired 自检在打开手柄侧 gyro toggle 后为 1.00 g；
单周期 mode 2→mode 1→一秒双侧 Normal 获机器与用户 PASS。退出恢复唯一 Edge 后，
背键 vendor `04/08/10/20` 对应 virtual `80/40/20/10`；IMU 10,000 帧的 accel/gyro
六轴均动态。最终安全配置再次核对通过。OW2 未观察到动态 L2，按计划记录 L2=N/A；
已有 cable L2 mild 与 rumble 证据不做无理由重复。项目技术目标已完成，merge/push/PR/
release 仍需用户明确决定。

独立发布审查随后阻止了直接发布：已验收路径与公开 compatibility 写路径不同、配置
truthiness、安装升级/卸载、无限保持和文档漂移均为 P0。`85cb93b`/`9bf7a54`/
`5d35156` 已修复为命名 `ow2-safe` 连续 profile、严格 `trigger_profile`、每周期 4 秒
reset、精确 OW2 模式/顺序、共享 writer lock 与可回滚原子 installer。本地 145 PASS、
SteamOS 144 PASS/1 compiler skip，公开 installer 真实升级成功。手柄当前离线使最终
五周期 real-virtual dry-run 被身份门禁拒绝；今晚恢复手柄后先补这一步，再做修后复审和
一次生产 profile 连续实机验收。当前仍是 disabled/translation-dry-run，不冒充生产启用。

## 今晚最终集中门禁

无需再重复早期 mild/三周期诊断。持握者回家后按一个连续块完成：

1. 连接已验证的 2.4G 或 USB-C DInput，确认 installed self-test、daily active、唯一 Edge。
2. 用捕获 fixture 在 `ow2-safe-dry-run` 下重放五周期；要求五组
   mode 2→mode 1→Off/Normal、零 write failure，证明不再三周期锁止。
3. 对最终提交运行修后独立 code-reviewer/architect；任一 HIGH/BLOCK 则不进入实体生产块。
4. 提前通知并取得生产 profile 实体授权，再临时把 OW2 per-game option 改为
   `ow2-safe-write`。连续完成至少五次及时释放；第 4/5 次必须仍有可辨识效果，所有 Off
   清除、无 timeout/write failure/错误侧别，退出恢复唯一 Edge。
5. 持握者确认效果与恢复后，单独决定是否把 OW2 option 保留为生产启用；全局
   `trigger_profile` 继续 disabled，其他游戏保持 Edge/无写入。未获决定则恢复 dry-run。
6. 最后更新证据与状态；merge、push、PR、tag/release 仍分别需要用户明确授权。

停损：任何身份不唯一、未知输出取代 accepted pattern、复位 UNKNOWN、异常强度、服务
无法恢复或审查 BLOCK，立即恢复 disabled/dry-run 并停止。游戏启动和实体写入继续遵守
“先通知、等确认、再执行”。

离线修后复审现已完成：`0691bac` 本地 148 PASS，独立 code review=APPROVE、
architecture=CLEAR，无剩余 medium-or-higher/watch。SteamOS 在最终提交安装前离线，因此
上述清单第 2/4/5 项与最终 archive 安装仍留到今晚；第 3 项已完成且不再阻塞。

首次 `ow2-safe-write` 五周期机器/持握者门禁通过，但持握者随后追加五轮，在第 4/5 轮
观察到松开 R2 后约一秒才射箭。生产验收据此重新打开并立即恢复 translation-dry-run。
该会话 569 秒内同步写入 35,127 条 HID 日志和 16,987 条重复 L2 unsupported 行；生产
wrapper 误带 `--hid-debug --trigger-debug` 是高概率输入阻塞源，但尚无同步输入时间线证明。
`c4f36af` 已让 write profile 静默、dry-run 保留调试；本地 149 PASS、SteamOS 148 PASS/
1 compiler skip，已部署未启用。最终门禁改为静默模式下同步观察 physical/virtual R2，
至少五轮无延迟射击后才允许持久化或发布。

静默模式同步复测现已通过：10/10 物理 R2 松开均配对到虚拟 Sony，relay 延迟
0.060..6.995 ms、平均 3.249 ms，debug lines=0、write/timeout failure=0；持握者十轮均
未观察到延迟射箭。退出恢复唯一 Edge 后按授权边界恢复 translation-dry-run。生产技术
门禁由此闭合；是否持久化 `ow2-safe-write`、merge/push/PR/release 仍分别等待用户决定。

最终 `a13046f` 进一步把 quiet 变成代码级不可旁路契约：wrapper 固定 `--quiet-output`，
所有 live OW2-safe 路径覆盖 config verbose 并拒绝三种 debug，dry-run 和无条件错误日志
保留。最终本地 150 PASS、SteamOS 149 PASS/1 compiler skip；code review=APPROVE、
architecture=CLEAR，无剩余 medium-or-higher/watch。技术生产目标完成，当前仍安全回滚为
translation-dry-run，等待持久化和仓库发布决定。
