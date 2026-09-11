# v10 支撑诊断 summary（2026-09-11 18:48:42）

## Phase 1 站立闸（flat 列；fell=fell 判据见文件头）

脚列口径：feet_down=法向力>1N 的脚数（稳定段均值/最小值）；lift_frac=非四脚着地占比；air_frac=全脚离地占比；foot_z_min=逐脚最低世界 z（flat 地面 z=0，即离地最低点）；foot_load_frac=逐脚载荷占体重比（顺序见 foot_names）

| case | max_tilt_deg | min_clearance | drift_m | max_belly_fz_n | feet_down | lift_frac | air_frac | foot_z_min | foot_load_frac | foot_names | fell |
|---|---|---|---|---|---|---|---|---|---|---|---|
| p1a_zero_action_5s | 6.0 | None | 0.076 | 0.0 | 3.85/0 | 0.056 | 0.028 | [0.074, 0.074, 0.07, 0.074] | [0.154, 0.226, 0.268, 0.177] | rr_foot,rl_foot,rf_foot,lf_foot | False |
| p1b_policy_still_10s | 17.8 | None | 0.307 | 0.0 | 2.84/0 | 1.0 | 0.018 | [0.08, 0.123, 0.104, 0.074] | [0.021, 0.006, 0.19, 0.515] | rr_foot,rl_foot,rf_foot,lf_foot | False |
