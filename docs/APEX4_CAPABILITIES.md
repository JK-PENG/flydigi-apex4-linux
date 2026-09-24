# APEX 4 实体能力与 Edge 仿真边界

本表区分「手柄上有部件」「relay 已实现」和「本项目实机通过」。官方
[APEX 4 手册](https://shops.flydigi.com/pages/flydigi-apex4-gaming-controller-user-manual)
确认 ForceAdapt 等产品能力；具体 Linux 路径和验收结论以仓库证据为准。
截至 2026-09-23，通用 `generic-safe` 仍是本地候选，不能据此宣称默认生产可用。

| 能力 | APEX 4 实体与虚拟 Edge 对应 | 当前实现／实机证据 | 下一门禁 |
|---|---|---|---|
| 摇杆、十字键、主按键、模拟 L2/R2 | 物理输入 → Edge 输入报告 | relay 已实现；游戏控制与输入源见 [输入证据](evidence/2026-09-21-input-source-baseline.txt) | 默认 generic 集成后查延迟回归 |
| M1–M4 | 四个物理背键 → Edge 四个扩展位 | 2.4G 和回归有线记录见 [背键捕获](evidence/2026-09-11-paddle-capture.txt)、[有线复测](evidence/2026-09-21-stage-e-cable-regression.txt) | 默认 Edge 与身份降级往返后复测；普通 DualSense 不提供四扩展位 |
| 六轴运动 | 物理 vendor IMU → Edge IMU | 实现及有线实机移动见 [协议](PROTOCOL.md)、[有线复测](evidence/2026-09-21-stage-e-cable-regression.txt) | 默认路径回归；传感器静止须检查手柄陀螺开关 |
| 普通双马达震动 | Edge output rumble → APEX 4 马达 | 已实现、2.4G/有线已有分离测试；它不是扳机触觉 | 确认 generic 改动不改变普通震动 |
| L2/R2 ForceAdapt mode 0/1 | 实体扳机 → Edge 自适应扳机输出翻译 | 旧记录有双侧 mild 和 OW2 R2 mode 1 正样本；2026-09-23 直接写入的 L2/R2 独立 mode 1 均未被持握者感到，详见[新负样本](evidence/2026-09-23-generic-candidate-steamos.txt) | 对齐实际按压与效果写入、核查手柄状态并解决证据冲突前，不默认开放通用 mode 1 |
| L2/R2 ForceAdapt mode 2 | 实体扳机 → Edge vibration/recoil | OW2 R2 `(0,1,32,21,0)` 在 2.4G/有线实体通过；L2 未通过 | L2 同参数及自动 Normal 集中实测 |
| L2/R2 ForceAdapt mode 3 | 实体扳机 → Edge weapon/bow 近似 | 协议可构造，但本项目缺该参数实体与释放验收；默认关闭 | 双侧固定 `(60,20,20,0,0)` 经确认再开放 |
| Galloping/Machine | 可近似为 mode 2，非同一触感语义 | 解码及兼容近似存在，无独立语义实机验收；通用策略关闭 | 如确有游戏输出，另订固定参数和实机门禁 |
| 触摸板触控 | 没有已证实的 APEX 4 触控表面等价输入 | 不声称仿真触点；现有按钮映射不等于触控 | 仅能提供明确标注的按键替代 |
| 麦克风、扬声器、音频式触觉 | 当前虚拟 HID 没有 USB 音频端点 | 未实现；不能因 Edge VID/PID 推断支持 | 若发现实体等价与可验证音频路径，单独立项 |
| RGB、屏幕 | APEX 4 有专有部件，不属于已证实的 Edge 输出映射 | 本轮不发送任何新 vendor 命令 | 需明确输出来源、只读协议研究与另行实机授权 |

连接边界：本轮 ForceAdapt 仅针对已验证的 USB-C DInput 与 2.4G；蓝牙缺少
可用的 `0xFFA0` vendor 接口，不能套用同一物理写入承诺。身份和写入门禁见
[DSX](DSX.md)；缺失能力保持显式未支持，不伪造游戏未发送的效果。
