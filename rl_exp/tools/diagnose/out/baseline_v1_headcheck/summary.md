# v10 支撑诊断 summary（2026-09-20 17:52:59）

## Phase 1 站立闸（flat 列；fell=fell 判据见文件头）

脚列口径：feet_down=法向力>1N 的脚数（稳定段均值/最小值）；lift_frac=非四脚着地占比；air_frac=全脚离地占比；foot_z_min=逐脚最低世界 z（flat 地面 z=0，即离地最低点）；foot_load_frac=逐脚载荷占体重比（顺序见 foot_names）

承重列（2026-09-14 补）：`ΣF_body/mg`=**全 body** 法向力加总/体重——只加四只脚时缺的 ~10% 靠它判去处；`a_z_eq`=解释缺额所需的竖直加速度 [m/s²]，`Δv_z`=窗口端点速度差 [m/s]（|Δv_z| 远小于 a_z_eq×T 时缺额**不可能**是动量）；`非足top3`=逐 body平均载荷前三，括号内 `z`=body 原点世界 z、`mesh`=**碰撞网格最低世界 z**（地面 z=0，只有 mesh≈0 才是真撑地；原点 z 会被网格自身偏置骗——tail3_pitch 的网格最低点在其原点**上方** 0.103 m）。注意 `max_belly_fz_n` 是基准阈值项，不是载荷量。

| case | max_tilt_deg | min_clearance | drift_m | ΣF_body/mg | a_z_eq | Δv_z | 非足top3 | max_belly_fz_n | feet_down | lift_frac | air_frac | foot_z_min | foot_load_frac | foot_names | fell |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| p1a_zero_action_5s | 1.7 | None | 0.039 | 1.0153 | -0.15 | 0.0158 | base_link=0.0N(z=0.94,mesh=0.546),chest_yaw=0.0N(z=0.94,mesh=None),tail1_yaw=0.0N(z=0.91,mesh=None) | 0.0 | 3.8/0 | 0.056 | 0.04 | [0.073, 0.072, 0.071, 0.074] | [0.213, 0.259, 0.315, 0.228] | rr_foot,rl_foot,rf_foot,lf_foot | False |
| p1b_policy_still_10s | 26.7 | None | 4.509 | 0.968 | 0.314 | 0.1084 | neck_pitch=90.29N(z=0.281,mesh=-0.052),base_link=0.0N(z=1.041,mesh=0.536),chest_yaw=0.0N(z=1.041,mesh=None) | 0.0 | 1.8/0 | 1.0 | 0.1 | [0.188, 0.078, 0.104, 0.2] | [0.0, 0.054, 0.459, 0.328] | rr_foot,rl_foot,rf_foot,lf_foot | False |

## Phase 2 平地直行（flat 列；first_event: neck_load=先低头承重 / feet_lift=先失稳）

移动列口径（**验收列与奖励核同帧**）：fwd_yaw=vel_yaw_x 均值 = 前向速度验收量（yaw 帧，俯仰/侧倾不污染）；fwd_b=体坐标前向均值，**诊断用**（俯仰把重力分量折进 x 轴 → 会误报欠速，不能当验收）；overshoot_frac=fwd_yaw/命令−1（**签名量**；v10 EP 核把超速 clamp 成满分，v13 Miki 核双向罚）；overshoot_abs=|同名量|（v13.1 验收闸——签名量在完全不动时=−1 也能过关）；fwd_mae=逐帧 mean|vel_yaw_x−cmd|（报告用，不设闸：均值达标而快慢交替靠它暴露）；fwd_std=速度抖动（yaw 帧）；drift_x/drift_y=世界位移、v_world=世界速度均值（横向漂移判据）；**slip_abs=mean|vel_yaw_y| = 侧滑验收量**（逐帧取绝对值，左右摆动不能互相抵消）；slip_y=签名均值（只作方向诊断）；yaw_drift/turn_rate=库算 yaw 的漂移与角速度=机身转向；crab=体坐标 atan2(lat,fwd)（slip 与 turn 的合量）；foot_duty/foot_load_frac 顺序见 foot_names

| case | cmd | fwd_yaw | overshoot | overshoot_abs | fwd_mae | fwd_std | fwd_b | slip_y | slip_abs | yaw_drift | turn_rate | drift_x | drift_y | crab | v_world | tilt_max | feet<2 | foot_duty | foot_load_frac | ΣF_body/mg | 非足top3 | neck_frac | belly_frac | ledger |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| p2_flat_v0.5_r0 | 0.5 | 0.468 | -0.064 | 0.064 | 0.055 | 0.075 | 0.45 | -0.008 | 0.036 | 4.63 | 0.16 | -6.6° | 0.468 | 26.2 | 0.292 | [0.002, 0.372, 0.744, 0.682] | [0.002, 0.071, 0.425, 0.31] | 0.9241 | neck_pitch=82.18N(mesh=-0.053),base_link=0.0N(mesh=0.545),chest_yaw=0.0N(mesh=None) | 0.476 | 0.0 | {"5": 1.455, "6": 0.0} |
| p2_flat_v0.5_r1 | 0.5 | 0.468 | -0.063 | 0.063 | 0.052 | 0.072 | 0.451 | -0.01 | 0.036 | 4.65 | 0.14 | -6.8° | 0.468 | 26.2 | 0.288 | [0.002, 0.354, 0.742, 0.698] | [0.0, 0.066, 0.434, 0.305] | 0.929 | neck_pitch=87.39N(mesh=-0.052),base_link=0.0N(mesh=0.549),chest_yaw=0.0N(mesh=None) | 0.482 | 0.0 | {"5": 1.458, "6": 0.0} |
| p2_flat_v0.5_r2 | 0.5 | 0.467 | -0.067 | 0.067 | 0.063 | 0.086 | 0.448 | -0.012 | 0.038 | 4.63 | 0.18 | -7.1° | 0.466 | 26.3 | 0.3 | [0.002, 0.312, 0.742, 0.698] | [0.001, 0.061, 0.465, 0.319] | 0.9789 | neck_pitch=94.2N(mesh=-0.054),base_link=0.0N(mesh=0.55),chest_yaw=0.0N(mesh=None) | 0.486 | 0.0 | {"5": 1.443, "6": 0.0} |
