# 默认 Edge 与通用 ForceAdapt 设计（2026-09-23）

## 目标与完成边界

APEX 4 在 2.4G 或 USB-C DInput 下由常驻 relay 默认呈现为虚拟 DualSense Edge。
不配置任何游戏启动选项时，游戏可使用已经实现的按键、摇杆、模拟 L2/R2、M1–M4
独立 Edge 按键、六轴运动、普通震动，以及经通用安全翻译的原生自适应扳机输出。
同一个扳机翻译器适用于虚拟 Edge 和普通 DualSense，不查游戏 ID、游戏名或固定的
OW2 报告字节。游戏若不向 Edge 发出原生效果，可选择单个游戏的启动选项临时呈现为
普通 DualSense；启动选项只改变虚拟身份，退出恢复 Edge。

这不承诺每款游戏都会提供扳机效果。游戏、Steam Input 和 Proton 必须实际向所选
虚拟身份发送 DualSense output report。已记录的 OW2/Proton 组合只向普通
DualSense 发送动态效果，故仍需要该游戏的身份降级选项。

当前代码基线：默认 Edge 身份和输入链路已实现；`trigger_profile` 仅有
`disabled|ow2-safe`，后者只接受 OW2/Hanzo 的 R2 精确字节模式并拒绝 Edge。
本设计替代这些限制，保留已验收的 OW2 向量作为回归证据。

## 硬件能力范围

| 功能 | 目前证据 | 本设计要求 |
|---|---|---|
| 按键、摇杆、十字键、模拟 L2/R2 | relay 与游戏输入已验证 | 默认 Edge 持续可用；身份降级后普通 DualSense 输入可用 |
| M1–M4 独立按键 | SteamOS 实测 Edge 位映射 | 默认 Edge 保留四个独立位；降级时明确告知普通 DualSense 不具备这些 Edge 扩展位 |
| 六轴运动 | vendor/虚拟路径实测 | 默认 Edge 保留；手柄侧 gyro-mouse 开关导致无流时显式诊断 |
| 普通双马达震动 | 2.4G/有线实测 | 独立于 ForceAdapt 转发、清除，不让扳机策略改写普通震动 |
| L2/R2 ForceAdapt | mild 双侧、OW2 R2 rattle/resistance 实测 | 按效果类别双侧验证后由通用安全翻译器默认启用 |
| Touchpad 触控、麦克风、扬声器、音频式触觉 | 当前 APEX 4→虚拟 Edge 链路没有实体等价证据 | 不宣称已支持；可映射的实体按钮可提供显式替代，但不伪造触控面或音频端点 |
| RGB、屏幕等 APEX 4 专有硬件 | 有实体部件，现有 relay 没有安全的 Edge 输出映射 | 独立能力审计：存在明确游戏输出、可确认的 vendor 命令和实体验收后再加入；不成为通用扳机上线的隐式前提 |

能力范围以 APEX 4 的真实部件和经验证的协议为准。Flydigi 官方手册列出
ForceAdapt；Linux `hid-playstation` 依据 Edge PID `0x0df2` 识别扩展按键。
参考：[APEX 4 官方手册](https://shops.flydigi.com/pages/flydigi-apex4-gaming-controller-user-manual)、
[Linux hid-playstation 源码](https://github.com/torvalds/linux/blob/master/drivers/hid/hid-playstation.c)。

## 身份和效果策略解耦

常驻 user-systemd 服务的默认 `emulate` 为 `dualsense-edge`，最终默认
`trigger_profile` 为 `generic-safe`。普通游戏不设置启动选项。

`tools/proton-game.py --relay-profile dualsense --run -- %command%` 仅负责
Edge→普通 DualSense→Edge 的会话生命周期。临时 relay 继承同一
`generic-safe` 效果策略，不附加游戏专用效果模式。服务互斥、精确 HID 身份、
已验证 transport、异常退出恢复与游戏范围的物理设备过滤沿用现有实现。
若 preflight 或恢复失败，不启动游戏或不声称 Edge 已恢复。

既有 `ow2-safe` 精确模式可保留为测试对照和回滚路径，但不是默认或新游戏接入方式。
不能把该模式的强度、时序假设直接视作所有游戏的通用语义。

## 通用效果翻译

入口继续复用 `ds5.parse_output()`；`trigger_translation.parse()` 给出左右侧、
效果类别、区域、强度和频率。新增一个独立的 generic-safe 选择/约束层，依据
normalized effect 决定是否构建 ForceAdapt 命令：

| DualSense 效果 | APEX 4 候选行为 | 开放门禁 |
|---|---|---|
| Off/Normal | 同侧 Normal；会话退出或异常双侧 Normal | 现有清除路径及失败注入继续通过 |
| simple/zone resistance | mode 1，保留起始区域并限制阻力 | L2/R2、2.4G/有线的候选参数与保持时长验收 |
| simple/zone vibration | mode 2，保留位置与频率并限制强度 | L2/R2、2.4G/有线的频率/压力/强度候选验收 |
| weapon/bow breakpoint | mode 3，保留阻力到突破的可表达部分 | 单独实体参数和释放行为验收后开放 |
| galloping/machine | 按已确认硬件模式作明确标注的近似 | 单独实体效果验收后开放；不能只凭现有代码可编码就开放 |
| invalid、unknown、limited 或硬件未验收类型 | 不发送新的 ForceAdapt 命令 | 记录为 unsupported；已有活动效果仍受超时/Off 清除约束 |

同一类别的游戏输出使用同一规则，不依赖游戏名、AppID 或某一个完整原始报告。
区域、强度和频率的变换、上限及无法保留的语义必须在最终参数表中逐项说明。
OW2 捕获的 `0x26/0x21/0x05` 是其中一组回归向量，不能成为唯一通过样本。

在尚未取得类别实机验收时，该类别保持关闭。用户已认可这一 fail-closed 默认；
正式把 `generic-safe` 设为默认之前，必须完成目标类别的实机门禁，不能只改默认值。

## 有界状态与性能

每侧独立维护当前效果、最后有效变化、活动时限和 Off 重武装状态。游戏效果变化
不能无限延长活动时限；合法重复输出只做去重，不造成额外 HID 写入。Off 立即写同侧
Normal；UHID CLOSE/STOP、vendor 断连、身份重连、服务停止、写失败和异常退出都执行
双侧 Normal 或明确记录 UNKNOWN。重连只在新身份验证及初始双侧 Normal 成功后
重新武装，不回放旧代际 pending effect。

安全时限按效果模式和真实使用场景确定，不能把 OW2 的四秒诊断上限直接套给赛车等
可能长期保持阻力的游戏。所有实体模式都有有限上限与停止路径；时限、上限、Off
语义及触感验收共同决定最终默认参数。

实体写入服务始终 quiet：配置 `verbose=true` 不能在输入主循环重启高频日志；
写入、清除、身份和重连错误仍可见。完整 HID 抓包只在独立 dry-run/诊断会话启用。
物理输入到虚拟输入的延迟需要在连续动作、长会话与异常恢复后复测。

## 配置与迁移

最终新安装默认 `emulate=dualsense-edge`、`trigger_profile=generic-safe`。
保留显式 `disabled` 作为用户关闭扳机输出的选项；`ow2-safe` 可作为回退/对照。
升级既有配置时保留用户的背键、轴向和身份设置。旧配置中的 `disabled` 可能是安装
生成的旧默认，也可能是用户主动关闭，无法单凭值区分；迁移必须显式记录处理规则，
不得静默覆盖用户的主动关闭选择。现有 SteamOS 安装将在验收后执行一次有记录、
可恢复的配置迁移，此后不需要逐游戏维护扳机启动参数。

## 验收与交付

1. 软件：固定向量和参数边界覆盖所有支持类别、两侧、非法值、未知类型、Off、
   去重、超时、失败、重连；证明没有游戏 ID 或原始报告白名单。
2. 真实虚拟设备：在默认 Edge 身份注入多种 DualSense 输出，观察通用策略的最终
   ForceAdapt 决策；普通 DualSense 身份对同样输出得到相同决策。
3. 实体：按类别和侧别提交有界参数包，经持握者确认后测试；机器写入与持握者感受
   分开记录，写失败或复位 UNKNOWN 立即停止。
4. 游戏：至少一个实际向 Edge 发送原生效果的 PC 游戏无需启动选项，取得持续变化、
   Off 和用户可辨识效果；另用一个仅支持普通 DualSense 的游戏验证只降级身份的
   启动选项。若找不到会向 Edge 输出的游戏，默认 Edge 原生扳机的游戏层验收保持
   UNKNOWN，不以合成 UHID 结果替代。
5. 体验：长于现有十轮的动作块同时记录物理/虚拟松开时序；确认没有明显输入延迟，
   日常 Edge 背键、IMU、普通震动仍正常。
6. 交付：公开 installer 升级和回滚、SteamOS Gaming Mode 自启动、默认配置持久化、
   README 能力矩阵与不支持项、许可 notices 随安装物交付。合并、push、PR、发布
   仍各自遵守用户授权边界。

## 非目标与项目拆分

本规格的首个可交付增量是“默认 Edge + 通用双扳机安全翻译”。RGB、屏幕等可能与
Edge 输出对应的 APEX 4 专有能力单列后续能力审计和验收，不在此规格中猜 vendor
命令。无实体音频硬件证据时，不声称 DualSense 扬声器、麦克风或音频式触觉已实现。
也不伪造游戏没有发送的原生扳机输出，不自动把游戏切成普通 DualSense。
