# 当前对称 PD 候选的承地静站力矩观测

## 适用范围

用户选择继续判断实际工况的力矩余量。本轮从[左膝实际力矩记录](2026-10-21-lizard2-left-knee-joint-force.md)的已验证报告接入当前完整候选：四膝肘 Kp=220、Kd 约 14.95，全部其它 PD、限位、力矩上限、速度上限及求解器保持不变。胸俯仰上限为 280 N·m，其它关节按既有配置，膝肘为 180 N·m。

仅解除 USD 唯一世界固定关节，按中立碰撞网格最低点加原 0.001 m 间隙放置；开启重力、自由根、平地、全部零位置/速度目标。复用[既有静站](2026-10-19-lizard2-loaded-standing.md)的 5 s 窗口、0.005 s 步长、支撑与停止判据；自然落地尾段仍属允许支撑。本轮不加入手工移重/步态，不调增益追求通过，不改正式资产或训练配方。

## 验收条件

- 新 `--force_reference --approved_force_sha256` 入口必须绑定已完成的当前对称 PD 力矩报告及 manifest；禁止同时传增益覆盖。读回全部 PD、力矩与速度上限和原报告相等，自由基座和逐 body 重力开启。
- USD 层规范化后只增加一个世界关节禁用属性，URDF 与网格字节沿用；实际 actor 姿态按实际 q 与自由根变换复算 FK，误差小于 1e-5。
- 每步采原始 incoming wrench、DOF 投影、显式 actuation 输入和实际 backend targets；保持前序步平均力矩口径，不以 PD shadow 代替。核摩擦、armature、tendon、限位余量和速度条件，区分驱动与其它轴向贡献。
- 原静站最后 1 s 判据保持：下沉不超过 0.02 m、倾角不超过 0.1 rad、关节偏差不超过 0.1 rad、竖直速度不超过 0.05 m/s、每足支持力至少 5 N、总平均支持力与重量差不超过 20%。停止线沿用原值，另复用前序半限速停止。报告失败须非零退出。
- 物理最多一次 5 s，失败不追加增益扫描；离线复读全部 1000 帧，独立复算停止与静站判词。错误投影、上限和成功判词须被拒绝。

## 结果

首次启动在造环境前因新 manifest 没有历史顶层 `target` 字段而失败；保留失败目录，改为读取 `target_binding` 后继续，未消耗物理步。随后唯一物理观测完成 1000 步、5 s，无停止条件触发，但 `standing_force_observation_standing_failed`，进程退出 1；没有重试物理或调整参数。

| 关节 | 全程最大绝对步平均力矩 N·m | 最后 1 s 最大 N·m | 上限 N·m | 最大占比 |
|---|---:|---:|---:|---:|
| 左肩外展 | 74.619728 | 59.090328 | 180 | 41.4554% |
| 胸俯仰 | 106.680260 | 76.977119 | 280 | 38.1001% |
| 左前肘 | 29.562342 | 24.660103 | 180 | 16.4235% |
| 右前肘 | 29.610123 | 24.632832 | 180 | 16.4501% |
| 左后膝 | 9.131509 | 8.628948 | 180 | 5.0731% |
| 右后膝 | 9.295332 | 8.857268 | 180 | 5.1641% |

全体关节最高占比为左肩外展的 41.4554%；全部关节达到 99% 上限的采样数和连续时间均为零。这里的“余量”仅指本工况已观测载荷相对配置 cap 的余量，不是电机实际最大/连续能力或所有动作的裕度。

最后 1 s 静站失败项由离线数据独立复算为 `root_drop`、`lf_elbow_joint`、`rf_elbow_joint`。终点根下沉 0.0349850655 m，左右前肘分别偏离零目标 0.1218678802 / 0.1216704547 rad；左右后膝分别 0.0434169210 / 0.0447525643 rad。全程最大关节偏差 0.1381054223 rad。倾角、竖直速度、四足支持及总支持力判据通过；最后 1 s 总平均支持力 706.3289409 N，重量 706.3238919 N。终点尾段支持约 34.32 N，故不称全部重量只由四足承担。

这证明当前承地姿态存在可观静差，不能把悬空小动作的 0.002 rad 保持精度通过外推到承重；同时本观测没有表现出力矩 cap 不足。增大 cap 不会解决未限幅时的静差。仍保留当前候选与原误差边界，不自动加 PD、加前馈或降低 cap，不据此要求 RL 前先完成手工步态。

全部原始 wrench 投影与后端 DOF 标量最大差 7.62939453125e-6 N·m；显式输入、摩擦与 armature 为零，无 tendon。各关节限位余量及速度占比见复读报告，未触及原停止线；在本轮已核条件下支持将活动轴步平均载荷归于 drive。自由根下初末两份全体 actor/FK 最大分量差 8.66699218838e-7。保持原速度通道异常的未解决状态，不使用 shadow 宣称真实力矩余量。

静站入口原有自检通过；复读真实报告通过；分别将真实样本投影加 1 N·m、上限加 1 N·m、失败状态伪装为成功，三者均被拒绝。仓库离线全套 `ALL_OFFLINE_CHECKS_PASSED (37/37 in 55.3s)`，事项/验收格式检查通过。上述为执行者工具验证，不是事项关闭所需的新上下文审核。

## 证据引用

- 工具提交 `2a91a60`：`rl_exp/tools/diagnose/palm_spatial_standing.py`，新增显式当前候选受载观测；`rl_exp/tools/diagnose/palm_standing_force_audit.py`，不起物理的复读入口。
- 原始报告：`rl_exp/out/lizard2_b_standing_force_20261022_run02/report.json`，SHA256 `5a4c6a3f4572ab8db566637c64c67933ee5aa3857092b1fe7ed1b102724453c6`。
- 实际采样源码：同目录 `source.py`，SHA256 `4b04746f0fcd0661eb1676da15b470908835d329055fb026f57ce72ec494a319`；另保留 tracking/runtime 依赖快照及报告内哈希，未把共享 tracking 文件的其它在办改动纳入本轮提交。
- 隔离配置：同目录 `standing_manifest.json`，SHA256 `2f39ca4e6268d90cee08600510f05a3eae78c1272fdbeebb811ba911405569f2`；USD、URDF、网格、初末实体和全部逐步采样保留在本机，不承诺入仓。
- 复读：同目录 `force_audit_final.json`；错误证据对照 `negative_audit.json` 及三个 `negative_*_report.json`。
- 首次适配失败：`rl_exp/out/lizard2_b_standing_force_20261022/failure.json`；成功采完但判词失败的物理日志：`rl_exp/out/lizard2_standing_force_physics_20261022_run02.log`。
- 仓库检查日志：`rl_exp/out/lizard2_standing_force_offline_20261022.log`。

从仓根离线复读，输出须不存在：

```cmd
E:\IsaacLab\env_isaaclab\Scripts\python.exe -B rl_exp/tools/diagnose/palm_standing_force_audit.py --report rl_exp/out/lizard2_b_standing_force_20261022_run02/report.json --out rl_exp/out/lizard2_b_standing_force_20261022_run02/force_audit_replay.json
```

物理复跑命令（须另有运行预算；本轮不再执行）：

```cmd
E:\IsaacLab\env_isaaclab\Scripts\python.exe -B rl_exp/tools/diagnose/palm_spatial_standing.py --force_reference rl_exp/out/lizard2_b_joint_force_probe_20261021/report.json --approved_force_sha256 13929c53eccdb51d454ade60cf071c3eaa614bf5c90684dd2e06f4017d2485ef --out rl_exp/out/lizard2_b_standing_force_replay --headless --device cuda:0
```

## 未覆盖边界

仅覆盖当前中立姿态短时承地负载；没有证明静站全部原判据通过，也不覆盖抬腿、行走、冲击、额外载荷、不同姿态或全 ROM。未降低 cap 制造真实限幅正例；步平均载荷不排除子步尖峰，不等于硬件峰值/连续额定或热电流余量。不能据此确定最终可降低到多少；保持速度异常、有效边界和集成缺口在原 B/C/E/D 事项内，运动性能仍交 S6，未关闭任何事项。
