# 左后膝当前小动作的后端力矩读数与上限占比

## 适用范围

2026-10-21 用户明确要求沿用左后膝单轴和五轴组合，先确认力矩读数可信度，再检查保持/运动力矩、是否接近 180 N·m 上限及误差对应关系。本轮沿用[四膝肘统一候选](2026-10-21-lizard2-symmetric-knee-elbow-pd.md)：四个 Kp=220、Kd 各约 14.95，其余增益、上限、资产、armature、求解器及停止条件不变。不延伸为四肢复测、不进行最大负载或低上限饱和试验。

## 验收条件

一次物理进程、两例各 3400 步，共 6800 步，不重试。固定根 z=2 m、31 body 开重力、无承地或额外砝码；先 `rl_combined` 的五轴同方向 ±0.02 rad，再 `rl_knee_joint` 单轴；静置 5 s，正负各 6 s，2 s quintic 伸出、1 s 保持、2 s 返回、1 s 恢复，dt=0.005 s。安全停止线及原全组增量与左膝直接目标角判据继承[原左膝校准](2026-10-21-lizard2-left-knee-absolute-pd.md)，不新增全程 0.002 rad 要求。

新增 `--joint_force_probe` 只读采样，须与 `--left_knee_absolute_trial --symmetric_knee_elbow_pd` 一起使用。每个物理步后保存完整 incoming joint wrench、沿 DOF 的 projected force 和显式 actuation input；前两者是后端载荷接口，原 `reconstructed_pd_request_nm` 保留为估算。实际 USD 的 body1、活动轴与 backend body/DOF 列绑定；左膝为子 link `rl_knee` 的 joint-frame X 扭矩。不改变驱动力矩以校准接口。

[PhysX 关节载荷说明](https://nvidia-omniverse.github.io/PhysX/physx/5.6.0/docs/Articulations.html#link-incoming-joint-force)定义 incoming wrench 为父 link 向子 link 传递的每物理步平均载荷，活动轴投影包含 drive，也可能包含关节摩擦、显式力矩、位置限位和速度钳制；[Tensor API](https://docs.omniverse.nvidia.com/kit/docs/omni_physics/107.3/extensions/runtime/source/omni.physics.tensors/docs/api/python.html)定义 projected force 为沿运动方向投影的主动分量。故须检查贡献来源，不把整个六维载荷模长或局部 PD shadow 当作电机力矩。这里采用官方语义、原始六维重投影和独立自重静力三者交叉检查，不将两个共享后端的接口称为独立测力计。

## 结果

两例一次完整完成，物理退出 0，`joint_force_probe_symmetric_pd_left_knee_trial_verified`。原跟踪判据通过；原始帧、源代码快照和读回均留存。

| 工况 | 全程最大绝对步平均力矩 N·m | t>5 s 最大 N·m | 保持末段最大 N·m | 严格运动阶段最大 N·m | t>5 s 最大/180 |
|---|---:|---:|---:|---:|---:|
| `rl_combined` | 2.07315564 | 0.422717363 | 0.422079116 | 0.422069818 | 0.234843% |
| `rl_knee_joint` | 2.07315564 | 0.289712042 | 0.289624751 | 0.289623559 | 0.160951% |

两例全程峰值均出现在 t=0.015 s 的复位后瞬态，为 2.07315564156 N·m，占配置 180 N·m 的 1.1517531342%。不能将这项写成伸腿运动峰值。静置完成后的组合最大约 0.423 N·m，占上限约 0.235%；单轴约 0.290 N·m，占约 0.161%。两例各 3400 个样本中，达到或超过上限 99% 的样本均为零、连续时长为零。本轮未观察到接近上限或持续限幅；这不证明实际夹断阈值或瞬时子步峰值，也不是 180 N·m 极限能力验证。

读数归因检查：全部 30 DOF 的 raw wrench 重投影与后端 projected 标量最大差 `3.0517578125e-05 N·m`；显式 actuation input、friction properties 与 armature 读回均为零，无 tendon schema。左膝全程离位置限位至少约 1.1798 rad，速度读数远低于原 cap，接触为零。上述条件支持将本轮左膝活动轴的步平均传递力矩归于 drive，而非被动约束或额外力矩输入。

用原始 q 的保持窗口平均姿态，从 URDF 全部质心重力势能对左膝角中心差分（步长 1e-5 rad）独立计算保持力矩；静置、保持和返回窗口的平均载荷与该值最大残差 `0.000622045804098748 N·m`。例如零目标静置，后端约 −0.156621 N·m，独立重力约 −0.157232 N·m；组合负向保持约 −0.422074 对 −0.422682 N·m。支持读数单位、方向和当前静力尺度，不将微小残差视为全动态标定精度。

同一静置窗口，旧局部 PD shadow 约 −0.939204 N·m，与后端约 −0.156621 N·m 明显不同。此时位置差分速度约 1.16e-8 rad/s，而速度通道约 0.05116 rad/s，原速度读数偏置仍存在。不能再用该 shadow 量化实际力矩余量。日志仍有 TGS external-forces-every-iteration=False 的速度警告；本轮没有改求解器，也没有仅凭警告认定偏置根因。

保持末段力矩平稳（组合负向峰峰约 9.39e-6 N·m），没有本窗口持续增大的振荡。左膝组合直接目标角保持最大约 0.00199608 rad，单轴约 0.00139715 rad，均通过既定保持判据；运动瞬态误差仍高于 0.002 rad，与保持精度分开报告。当前小动作的精度偏差没有表现为力矩上限不足，暂不增加 cap 或继续加 PD。

独立复算全部 6800 帧的目标、backend 目标列、原增量与新增直接误差判词相等；10 份 actor 快照×31 body 的完整 XML/Rodrigues/FK 最大分量差 `9.47154930361349e-07`。持久力矩复读工具同时核原始投影、贡献来源、静力及判词，位置 FK 最大差 `6.07365977511876e-07`。完整离线套件 `ALL_OFFLINE_CHECKS_PASSED (37/37 in 44.7s)`；未新增机器闸门，未声称完成事项关闭所需的新上下文审核。

判定：本轮两例后端力矩读数可在已核条件下解释为左膝步平均驱动力矩，远离配置上限，未见持续饱和；无需据此提高上限。四膝肘候选继续保留，真实最大能力、其它姿态/接触及速度偏置等缺口继续由原事项承接。

## 证据引用

- 源码提交 `dd4bbc0897e8215c4d347b82e721809aa403c8a8`，实际采样源码 SHA256 `fd0f2ccaf6269881fa96703dcf76c1efaf4695f2a67207307b24bb05d100114d`；已提交源码与 source.py 逐字节相同，未混入共享文件 RF/视频 WIP。
- `rl_exp/out/lizard2_b_joint_force_probe_20261021/report.json` SHA256 `13929c53eccdb51d454ade60cf071c3eaa614bf5c90684dd2e06f4017d2485ef`。
- `rl_exp/out/lizard2_b_joint_force_probe_20261021/tracking_manifest.json` SHA256 `2cfa367012c32f2b5589abac32e09d6284d2193ed73c7757f29ba87a56d1c442`。
- `rl_exp/out/lizard2_b_joint_force_probe_20261021/force_audit.json` SHA256 `02682b4afe0bf6104ac93776a8f08fd884d6f751f9e1aebf2f5dfe681e805fe4`。
- `rl_exp/out/lizard2_b_joint_force_probe_20261021/tracking_audit.json` SHA256 `553e7000b2fe3f3249155bc35f0707095bd801d6b08c7ff5e06f24d3fcc8f048`。
- `rl_exp/out/lizard2_b_joint_force_probe_20261021/rl_combined.json` SHA256 `165424229fcc50e4f834c244d33624ab0b06862965dbd09b30a2b24b1eaccfb1`。
- `rl_exp/out/lizard2_b_joint_force_probe_20261021/rl_knee_joint.json` SHA256 `e055ce5fc97025939052780ba5267f18f58d6df01649589292b033a79e2fc196`。
- `rl_exp/out/lizard2_joint_force_physics_20261021.log` SHA256 `93c0853e62a48e52c4e279af3dd4db49f3616c84befdedb808b2b9439ed757fb`。
- `rl_exp/out/lizard2_joint_force_preflight_20261021.log` SHA256 `bc5f48377c2b0496e06a022a8e75fb38d0ffe2be88403b15030fb2a843de0c38`。
- `rl_exp/out/lizard2_joint_force_offline_20261021.log` SHA256 `3141ddccde9060e45eef2d04ff1698a941dfa48ff76fd4b401dbd94341b4bf93`。
- 受控物理输出 source.py、progress_01/02 及原始样本保持，前序记录未覆盖。持久复读入口 `rl_exp/tools/diagnose/palm_joint_force_audit.py`；原始数据在本机，不承诺入仓。

```cmd
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp\tools\diagnose\palm_joint_force_audit.py --report rl_exp/out/lizard2_b_joint_force_probe_20261021/report.json --out rl_exp/out/lizard2_b_joint_force_probe_20261021/force_audit_replay.json
```

复读不起仿真，输出必须新建。物理复跑使用原左膝记录命令加 `--symmetric_knee_elbow_pd --joint_force_probe` 与新 out，受新预算约束；本轮仅执行上述一次两例。

## 未覆盖边界

不覆盖其它关节的同精度验证、额外负载、近水平等不同姿态、自由根/承地、硬件连续/峰值额定、热与电流限制或极限速度。步平均力矩不能排除子步内部瞬时尖峰或限幅；未以降低 cap/已知外力制造饱和正例，因此不称实际饱和阈值已标定。速度通道偏置和全姿态驱动边界未解决，不自动关闭 B/C/E/D 或写入正式训练配方。
