# 已标定 PD 的六组受载组合复验与力矩通道核对

## 适用范围

2026-10-21 用户同意继续核定下一步。承接[全部单轴标定复验](2026-10-21-lizard2-calibrated-loaded-pd.md)，固定同一套 30 轴 PD，检查四肢各五轴、颈部两轴及尾部六轴的六组双向组合；不再加增益、不新建补偿环或手工步态，不创建子 agent。

## 验收条件

全部 Kp/Kd、armature、求解器、cap/速度/机械限位、过滤、重置与输入均沿用上轮；固定根 z=2 m、全部 31 body 开重力、无支撑接触。每组各命令轴同时取相同方向 ±0.02 rad，其它轴目标为零；每组 reset 后静置 5 s，正/负各 6 s（2 s quintic 伸出、1 s 保持、2 s 返回、1 s 恢复），dt=0.005 s、零速度目标。单次物理进程，最多 6×3400=20400 步；不重试、不追加激励或增益。

沿用各组自身 5 s 自重平衡角作为增量基准，保持末段和返回末段 ≤0.002 rad、运动最大增量误差 ≤0.012 rad、其它轴增量 ≤0.01 rad；静置漂移 ≤0.002 rad，静差/绝对目标误差 ≤0.1 rad。绝对角度或目标误差 >0.35 rad、读回速度达到 cap 一半、接触 >1 N、非有限或 actor/FK 不符即停；只有单纯保持精度未达允许记录失败后继续其它组，其它失败立即停。未放宽上轮阈值，未要求整机走路。

## 结果

一次进程完整完成 6 组、12 个方向、20400 步，`completed=true`、`selected_cases_completed=true`、`all_selected_cases_passed=false`、`calibrated_combinations_completed_precision_unmet`。物理退出码 1 真实保留精度失败，不是异常中断；未重跑或再调参。

| 组合 | 最大保持误差所在轴 | 最大保持误差 rad | 最大返回误差 rad | 判定 |
|---|---|---:|---:|---|
| `lf_combined` | `lf_elbow_joint` | 0.00375613475218 | 1.90669670701e-05 | 仅保持精度未达 |
| `rf_combined` | `rf_elbow_joint` | 0.00373764520511 | 3.59555706382e-05 | 仅保持精度未达 |
| `rl_combined` | `rl_knee_joint` | 0.00382227681577 | 1.79877824849e-05 | 仅保持精度未达 |
| `rr_combined` | `rr_knee_joint` | 0.00381330049597 | 3.58794713975e-05 | 仅保持精度未达 |
| `neck_combined` | `neck_yaw_joint` | 9.10838733657e-05 | 2.15276510167e-05 | 通过 |
| `tail_combined` | `tail3_yaw_joint` | 0.00158181505278 | 0.000642955303192 | 通过 |

四肢仅各自肘/膝保持误差超线，其余主动轴保持/返回及六组原停止条件均通过。全局最大运动增量误差 `0.0081430614595592 rad`、最大返回末段误差 `0.000642955303192139 rad`、其它轴最大增量 `5.49908727407455e-05 rad`，各自满足原动态/返回/其它轴判据。最大接触 `0 N`，速度读数最大为配置 cap 的 `0.0702966153622`；这仍不是速度通道准确性的独立证明。

执行者对全部原始帧独立重算时间、组合命令列、backend float32 位置目标与零速度目标、正负方向、全部误差和判词，均与报告一致。30 份 actor 快照×31 body 的独立 XML/Rodrigues/FK 最大矩阵分量差 `1.06367778091032e-06`，满足 1e-5。请求估算重建差 `0 N·m`。设计与全部 readback 逐项等同上轮；manifest 只 source 路径变化，恢复后与上轮结构全等。审计 `passed=true` 仅表示这些真实失败结果可复算，不是组合物理通过。

### 保持误差的局部解释

从 URDF 质量/COM 和实际末段姿态计算重力势能，以中心差分独立求各命令轴重力矩，再与各组受载平衡角比较。四个超标肘/膝的 `Δ重力矩/Kp` 与实测带符号增量误差之差最大 `7.23030285091448e-06 rad`；同姿态改变差分步长交叉检查保留在原始分析里。相邻关节同时转动使膝肘负载变化增大，能解释本次几乎加倍的保持误差；不是新的方向错误或已证实的力矩上限不足。

该解释只适用于本轮实际样本和保持段。其它主动轴中简化关系最大残差 `0.000190762502467612 rad`（尾部），不冒称所有动态误差均由静态重力模型精确解释；不将势能差分等同求解器实际驱动力矩，也不把局部拟合当全姿态保证。

### 力矩通道仍有边界

已对照当前安装源码：`ImplicitActuator.compute` 给出近似 PD；articulation 的 PhysX/Newton 适配路径在源码中调用 `sync_torque_telemetry`，implicit DOF 的 computed/applied 值由局部 PD shadow 及限幅生成。因此 `computed_torque`/`applied_torque` 不能用来宣称已经实测 solver drive torque。底层 Tensor API 有 `get_dof_actuation_forces`、`get_dof_projected_joint_forces` 和 `get_link_incoming_joint_force`，其中后两者文档为传入关节力及运动轴投影；尚未通过运行对照证明可分离驱动、约束/限位与其它分量，本轮没有将其写作真实电机输出。

本轮完成了通道语义核对，没有额外启动饱和压力试验或改执行器模型。真实驱动力矩/饱和、有效余量与自由根接触集成仍在办；不能以估计值小于 cap 宣布上限足够。

入口及原套件自检通过；错误批准、移除组合入口、遗漏尾组、误选左前腿命令通道均被拒绝。源码只增加有界六组合入口，原误差口径与目标轨迹不变。完整离线套件 `ALL_OFFLINE_CHECKS_PASSED (37/37 in 42.4s)`，台账与源码提交钩子通过；最终日志 `rl_exp/out/lizard2_b_combinations_offline_final_20261021.log` SHA256 `c96ac84df9770b7e25f1eb707fe6922fa2fb3709adcbb0dbaf1795ac502db1f0`；第一次闸门因并行工作使活跃文档预算超额而停止，未把该失败算作通过。只去除本轮两份活跃事项中正文已有明确链接的重复前言证据项，保留所有动作与正文，不关闭、取消或归档事项。

判定：原单轴全通过仍成立；当前 PD 在本轮颈/尾组合通过，四肢组合受载保持精度未达。默认驱动候选的组合精度尚未全通过，继续按具名膝肘误差校准，不能宣布 B/C/D 正式完成。

## 证据引用

- 七份日志与两个临时 Git index 已另存本机归档，原路径当前保留；归档身份、恢复及消费者缺口见 `acceptance/records/2026-10-28-diagnostic-combinations-archive.md`。
- 直接前序 report SHA256 `c5500ee862043111f68b65d5e0c2a03a8a9d4154f143a8b38775fd3281def9dc`；新入口在启动前重新复读全部 30 轴及前序完整链，不覆盖旧数据。
- 本轮实际源码 SHA256 `76140c6b4d5fde72e207f69df7b0208a071e9d6f16b10050117dff9c8991b7be`；`rl_exp/out/palm_spatial_tracking_combinations_HEAD.py.txt` 与物理产物 source.py 字节一致，源码提交 `745976777fde50bf9e1911da944317d4ea18e357`；不含共享文件 RF/视频等 WIP。
- `rl_exp/out/lizard2_b_combinations_20261021/report.json` SHA256 `903ec4dcf17ba4c6bd7c7f2e4e4e1a68ed0794cf0c17f18356554574b386de82`。
- `rl_exp/out/lizard2_b_combinations_20261021/tracking_manifest.json` SHA256 `90aa3cc9e7d206341405d7606f655d6a916026c8fbac3dfc0e7f145430d84018`。
- `rl_exp/out/lizard2_b_combinations_20261021/audit.json` SHA256 `22bb1c67ee3b258ebf83a24383fb26decb5f9f148dd1d56a681252180965201b`。
- `rl_exp/out/lizard2_b_combinations_20261021/per_joint_analysis.json` SHA256 `b74a8474302b2121ee074f27b2d5f53f5f1961d6c29764a7d74bbd778b8f74fd`。
- `rl_exp/out/lizard2_b_combinations_20261021/force_channel_review.json` SHA256 `8a65c48ac9d53f86f8a21167a7255f5b15a03270237329e1cdd36af38d01dbe1`。
- `rl_exp/out/lizard2_b_combinations_20261021.log` SHA256 `72762d4ba1f84c387e04168500a4fa23b02f6efcf3f20d41cabf0ae8a32b7a80`。
- `rl_exp/out/lizard2_b_combinations_preflight_20261021.log` SHA256 `d335ff7e1a311d106b6d25a464554e9622258bf55ed03c574eac4dca973bdf15`。
- 本机复读 `rl_exp/out/audit_combinations_20261021.py`、逐轴负载分析 `rl_exp/out/explain_calibrated_combinations.py`、前置拒错 `rl_exp/out/check_calibrated_combinations.py` 及对应日志保留。前序审计脚本已由并行清理归档到 `rl_exp/out/archive/diagnostic-development/tracking-scratch-20261021.zip`，本轮准备器按 manifest/blob 摘要读取其历史字节，不在仓根恢复脚本。当前六组合审计独立适配多命令列，不修改其它会话的新单轴审计工具。
- 当前安装环境的四份力矩接口源码摘要在 `force_channel_review.json`；本机原件引用不承诺入仓，不只凭接口名认定物理含义。

持久复跑入口（物理复跑需新预算和新 out；本轮没有追加执行）：

```cmd
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp\tools\diagnose\palm_spatial_tracking.py --headless --device cuda:0 --all_joints --self_weight_suite --calibrated_combinations --resume_self_weight E:/Robot/rl_exp/out/lizard2_b_calibrated_20261021/report.json --approved_resume_sha256 c5500ee862043111f68b65d5e0c2a03a8a9d4154f143a8b38775fd3281def9dc --approved_inertia_sha256 f1f9951a5057e4f5431316be373b5e359fbd3f5f8d79d3c2978bda140f5d06fd --inertia_report E:/Robot/rl_exp/out/lizard2_e_fresh_inertia_20261020/report.json --out E:/Robot/rl_exp/out/lizard2_b_combinations_replay
```

离线自检去掉 `--headless --device cuda:0` 并加 `--self_check`，仍需新 out，不启动物理。

## 未覆盖边界

六组只覆盖中立附近、同方向小幅组合，不是所有联合角度、异相动作、全 ROM 或连续姿态证明。未验证自由根、承地支撑、额外负载、实际饱和、硬件能力或速度偏置因果解释。正式采用、安全 reset 与训练前集成按原专项继续；本记录为执行者直接复核，不冒充新上下文关闭审核，不关闭 B/C/E/D，不自动加 PD 或补偿器。
