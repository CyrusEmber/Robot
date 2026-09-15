# v10 支撑诊断 summary（2026-09-14 18:48:26）

## Phase 1 站立闸（flat 列；fell=fell 判据见文件头）

脚列口径：feet_down=法向力>1N 的脚数（稳定段均值/最小值）；lift_frac=非四脚着地占比；air_frac=全脚离地占比；foot_z_min=逐脚最低世界 z（flat 地面 z=0，即离地最低点）；foot_load_frac=逐脚载荷占体重比（顺序见 foot_names）

承重列（2026-09-14 补）：`ΣF_body/mg`=**全 body** 法向力加总/体重——只加四只脚时缺的 ~10% 靠它判去处；`a_z_eq`=解释缺额所需的竖直加速度 [m/s²]，`Δv_z`=窗口端点速度差 [m/s]（|Δv_z| 远小于 a_z_eq×T 时缺额**不可能**是动量）；`非足top3`=逐 body平均载荷前三。注意 `max_belly_fz_n` 是基准阈值项，不是载荷量。

| case | max_tilt_deg | min_clearance | drift_m | ΣF_body/mg | a_z_eq | Δv_z | 非足top3 | max_belly_fz_n | feet_down | lift_frac | air_frac | foot_z_min | foot_load_frac | foot_names | fell |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| p1a_zero_action_5s | 5.2 | None | 0.076 | 1.0005 | -0.005 | 0.3965 | base_link=0.0N,chest_yaw=0.0N,tail1_yaw=0.0N | 0.0 | 3.85/0 | 0.056 | 0.028 | [0.074, 0.074, 0.07, 0.074] | [0.187, 0.274, 0.325, 0.215] | rr_foot,rl_foot,rf_foot,lf_foot | False |
| p1b_policy_still_10s | 17.8 | None | 0.307 | 0.9861 | 0.136 | -0.3244 | tail3_pitch=69.64N,base_link=0.0N,chest_yaw=0.0N | 0.0 | 2.84/0 | 1.0 | 0.018 | [0.08, 0.123, 0.104, 0.074] | [0.026, 0.008, 0.23, 0.624] | rr_foot,rl_foot,rf_foot,lf_foot | False |
