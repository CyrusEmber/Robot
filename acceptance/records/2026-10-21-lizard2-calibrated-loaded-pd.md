# 逐关节标定增益后的全部受载单轴复验

## 适用范围

2026-10-21 用户要求“先提高pd值，使之都符合允许误差”，随后明确“不统一到80，按照差不多满足”。承接[左后膝 Kp=30 试验](2026-10-21-lizard2-left-knee-kp30.md)，只调整此前八个保持精度失败轴，其它 22 轴的 Kp/Kd 原样保留。全部 30 轴在同一套新候选 PD 下重新双向检查，包含此前分开测试的胸俯仰，不混用旧参数下的单轴通过结论。不创建子 agent，不修改冻结配方或正式采用状态。

## 验收条件

按每轴较大的双向保持误差 e，局部拟合 `k=Kp*e/(0.02-e)`，以 `Kp_min=k*(0.02/0.002-1)` 估算目标刚度，取 `ceil(1.05*Kp_min)`，只提高不降低；`Kd_new=Kd_old*sqrt(Kp_new/Kp_old)`。这是选择本轮候选的局部经验关系，5% 刚度余量不构成全 ROM 或任意载荷精度证明。名义 `sqrt(Kp/I)/(2π)` 为髋扭转约 2.1795 Hz、肩扭转约 2.1658 Hz、膝肘约 2.5461 Hz，阻尼沿用同一中立惯量近似；不把惯量对角或该频率当接触下精确模态。

沿用固定根 z=2 m、31 body 开重力、无支撑接触、armature=0、胸俯仰 cap=280 N·m，其它限位、cap/速度与过滤不变；保持原求解器迭代与外力更新设置。改变的八轴 cap 均为 180 N·m，`Kp*0.02` 为 1.24–1.30 N·m，仅为位置项尺度，不是总驱动力矩预算或实际余量证明。未核实的真实饱和与速度偏置问题继续保留。

单次物理进程，30 轴逐个 reset；每轴静置 5 s，正负各 0.02 rad、各 6 s 往返（2 s quintic 伸出、1 s 保持、2 s 返回、1 s 恢复），dt=0.005 s、速度目标为零，每轴 3400 步，共 102000 步，不扫描、不重试。各轴以自身本轮第 5 s 受载平衡角为增量基准：保持末段/返回末段 ≤0.002 rad、运动最大增量误差 ≤0.012 rad、其它轴增量 ≤0.01 rad、静置漂移 ≤0.002 rad；静差/全程绝对目标误差 ≤0.1 rad。绝对角度或目标误差 >0.35 rad、读回速度达到 cap 一半、接触 >1 N、非有限或 actor/FK 不一致即停；只允许单纯保持精度不达标时保存失败并继续覆盖，其它失败立即停止。没有放宽阈值。

## 结果

一次进程完成全部 30 轴、60 个方向、102000 步，`completed=true`、`selected_cases_completed=true`、`all_selected_cases_passed=true`、`calibrated_precision_verified`，物理进程退出 0。此前八个失败轴全部通过，其余轴复验也通过。

| 关节 | Kp N·m/rad | Kd N·m·s/rad | 双向最大保持误差 rad |
|---|---:|---:|---:|
| `rl_hip_twist_joint` | 48.92894181 → 62 | 8.04403948 → 9.05497230 | 0.00235791921616 → 0.00190574906766 |
| `rr_hip_twist_joint` | 48.92819942 → 62 | 8.04398389 → 9.05497843 | 0.00235794529319 → 0.00190576396883 |
| `rl_knee_joint` | 30.00000000 → 65 | 5.52068173 → 8.12622347 | 0.00372194822878 → 0.0019091707468 |
| `rr_knee_joint` | 20.15955046 → 65 | 4.52556690 → 8.12623253 | 0.00507773038 → 0.00190913698636 |
| `lf_shoulder_twist_joint` | 40.81870653 → 63 | 7.45298677 → 9.25914757 | 0.00280338663608 → 0.00191265761852 |
| `rf_shoulder_twist_joint` | 40.81796751 → 63 | 7.45291865 → 9.25914676 | 0.00280343599617 → 0.00191274423152 |
| `lf_elbow_joint` | 20.16010606 → 65 | 4.52562156 → 8.12621870 | 0.00506636917591 → 0.00190241726115 |
| `rf_elbow_joint` | 20.16025179 → 65 | 4.52563871 → 8.12622013 | 0.00506651073694 → 0.00190266964957 |

全体 30 轴最大保持误差 `0.00191274423152208 rad`（`rf_shoulder_twist_joint`，约 `0.109592°`），最大返回末段误差 `2.63769179582596e-05 rad`；两者均满足 0.002 rad。运动期间最大增量误差 `0.00571648572609714 rad`（`tail3_yaw_joint`），按原 0.012 rad 动态门限通过，不声称全程误差都小于 0.002 rad。其它轴最大增量 `0.00980962812900543 rad`。

最大静置漂移 `1.72294676303864e-08 rad`，最大静置静差 `0.0319021083414555 rad`，全程最大绝对目标误差 `0.0351091995835304 rad`；0.002 rad 仍是相对平衡角的增量保持/返回判据，不将绝对自重静差隐藏为零。接触最大 `0 N`；速度通道读数最大为配置限速的 `0.0702966153622`，只沿用原停止条件，不据此证明该通道准确。

执行者直接逐帧独立复算全部样本的目标时轴、backend float32 位置目标、零速度目标、正负实体运动方向、全部误差判词与停止条件。独立 XML/Rodrigues 与归一化 actor 四元数复建 150 份快照、各 31 body，最大矩阵分量差 `1.13651272777571e-06`，满足 1e-5。PD request 按采集类型重建差 `0 N·m`，仍仅是请求估计。逐项对比设计及回读，恰好八轴 Kp/Kd 变化，其它 22 轴及全部其它 readback 不变；tracking manifest 恢复 source 与八轴增益后同前次结构全等，输入/资产不变。

旧/新小幅、胸部、自重套件及本入口离线自检通过，错误批准摘要拒绝；移除新入口、统一到 80、误改额外轴、取消 Kd 配套四种破坏均由持久自检拒绝，恢复候选后通过。完整离线套件 `ALL_OFFLINE_CHECKS_PASSED (37/37 in 52.8s)`；台账/格式检查另以提交日志为准，不替代独立审核。

判定：本候选在本次固定根、自重、中立附近双向小幅测试下，全部实际关节的增量保持和返回精度达标，稳定方向与返回检查通过。更高增益带来的精度收益得到本轮行为验证；不外推任意姿态与载荷，不据此关闭 B/C/E/D。

## 证据引用

- 绑定输入及此前完整链见上轮记录；直接前序 report SHA256 `071689b93852e93829d300ae26ab2b1f8ec3758e9538df2717a6f03580569723`，惯量报告批准摘要 `f1f9951a5057e4f5431316be373b5e359fbd3f5f8d79d3c2978bda140f5d06fd`。新入口启动前复读原始全部逐轴样本、增益试验及左膝样本，不覆盖前序产物。
- 本轮源码提交 `859fee7fe69da6b7292843c94d0e705856977aeb`，实际 source SHA256 `1433161fc0e46537d28d5df94114e6a6a5fe495dc41c499909557131d4e587b1`；`rl_exp/out/palm_spatial_tracking_calibrated_HEAD.py.txt` 与已提交工具、物理产物 source.py 精确逐字节一致，不含共享文件 RF/视频 WIP。
- `rl_exp\out\lizard2_b_calibrated_20261021\report.json` SHA256 `c5500ee862043111f68b65d5e0c2a03a8a9d4154f143a8b38775fd3281def9dc`。
- `rl_exp\out\lizard2_b_calibrated_20261021\tracking_manifest.json` SHA256 `edfdf31455f901f2a09db5b2a193d9b6eba860366a6930a70ef0f4c5cf5d563a`。
- `rl_exp\out\lizard2_b_calibrated_20261021\audit.json` SHA256 `109d4791cabd9317496f010a5ca076643d610e5562c131759653aaff04cb4074`。
- `rl_exp\out\lizard2_b_calibrated_20261021.log` SHA256 `9c6be93e8eb7fafb9c280c08d07a5c930abc4ad91c25ba114c67545630f32b19`。
- `rl_exp\out\lizard2_b_calibrated_preflight_20261021.log` SHA256 `7df56e81129728b194dcc9b4035a92806e2e4c7ee0e2f8bbd86ed560a4cff32f`。
- `rl_exp\out\lizard2_b_calibrated_audit_20261021.log` SHA256 `31f6fe5fced97f96eb97f19cbebf9cb0c75d92ffbfd3822b940c3229590e7318`。
- `rl_exp\out\lizard2_b_calibrated_offline_20261021.log` SHA256 `e0d20c27965c1fa2e42566669c69ec54af0581ba11425bfa46f4af117cb15305`。
- 本机复读入口 `rl_exp/out/audit_calibrated_20261021.py`、前置检查 `rl_exp/out/check_precision_calibration.py` 及其破坏摘要日志留存；产物目录内逐轴原始 JSON、progress、source、manifest 和 audit 不覆盖、不删除。本机引用不承诺入仓。

持久自检/复跑入口（物理复跑需新目录及新预算；本轮没有追加执行）：

```cmd
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp\tools\diagnose\palm_spatial_tracking.py --headless --device cuda:0 --all_joints --self_weight_suite --calibrate_precision --resume_self_weight E:/Robot/rl_exp/out/lizard2_b_knee30_20261021/report.json --approved_resume_sha256 071689b93852e93829d300ae26ab2b1f8ec3758e9538df2717a6f03580569723 --approved_inertia_sha256 f1f9951a5057e4f5431316be373b5e359fbd3f5f8d79d3c2978bda140f5d06fd --inertia_report E:/Robot/rl_exp/out/lizard2_e_fresh_inertia_20261020/report.json --out E:/Robot/rl_exp/out/lizard2_b_calibrated_replay
```

离线自检去掉 `--headless --device cuda:0` 并加 `--self_check`，仍需不存在的新 out，不启动物理。

## 未覆盖边界

本轮未做六组主动组合、自由根、地面接触、额外负载、全限位或连续姿态保证，未测试真实力矩饱和/硬件能力；现有速度读数偏置及其 TGS 解释仍待验证。未把 Kd 与偏置速度估计当成实际输出力矩。正式默认驱动采用、有效边界、组合与集成仍按原在办事项接续；本记录是执行者直接复核，不冒称不带执笔历史的独立审核，不关闭未完事项。
