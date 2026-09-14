# v13 PLAN —— 换回 Miki 对称跟踪核（一个核闭三个账本盲区）

> 生成：2026-09-14。状态：**实施完成待训**（单变量消融，base = v10；验收门与判废线
> 预注册于 `NOTES.md`）。

## 目的/假设（≤3 行）

v10 判决暴露 EP 线性核三个账本盲区：超速饱和中性（+48…54% 而账本 1.47/1.5）、横向
投影不可见（~20° 蟹行）、零命令无停车梯度。假设：Miki 2022 对称核
`exp(−‖v_cmd−v_yaw‖²/0.25)`（全 2D 误差）一个式子闭合三洞的账本侧；停车目标首次
进账本（cmd=0 站立 = 满分）。**口径限定**：账本闭合 ≠ 行为必然跟准，验收量测判。

## 相对 v10 的 diff（单变量，obs/DR/地形/终止/课程零变更）

1. `lizard_params.yaml` = v10 全量拷贝 + `v13:` 段（`track_goal_vel.weight=1.5`、
   `sigma_sq=0.25` + 预注册判废线；v5 段留作 EP 核冻结档案）
2. `LizardRoughTeacherEnvCfg_V13(V10)`：`__post_init__` 里 EP 核 → None，挂
   `teacher_mdp.track_lin_vel_xy_miki`（yaw 帧、全 2D 误差、无 min_speed）
3. 注册 `Lizard-Rough-v13` / `Lizard-Rough-Play-v13`（runner
   `lizard_rough_teacher_v13`，独立 experiment_name）
4. 静态闸 `rl_exp/tools/verify/check_reward_v13.py`（miki 接线 / EP 移除 /
   V5+V10 冻结 / yaml 记录），挂进 `run_offline_checks.bat`

**偏差声明**：weight 保持 1.5（paper 0.75）——保跟踪天花板与罚项比例同 v10，纯核
形状单变量。

## 验收（同 NOTES 预注册）

1. 三洞量测：overshoot < 0.15 @0.3 档、|slip_y| < 0.05 m/s、零命令 |v| < 0.1 m/s
2. 不劣化：success_rate / terrain_levels ≥ v10 同期
3. 趴窝哨兵：feet_slide 不劣化、后脚 duty 不塌、belly ≈ 0（v3/v4 病历，判废线 = v10）
4. 观察项（非闸）：左右载荷对称性 / 静止期四脚着地

## 训练

```bat
python scripts\reinforcement_learning\rsl_rl\train.py --task Lizard-Rough-v13 --max_iterations 15000 --seed 42
```

log：`logs/rsl_rl/lizard_rough_teacher_v13/`

## 修订记录

| 日期 | 版本 | 变更 + 原因 + 依据 |
|---|---|---|
| 2026-09-14 | v13.0 | 初稿（用户拍板"换回 miki 的"；v10 判决 + DIAGNOSE 修正口径为依据；风险预注册 = v3/v4 趴窝病历，判废线 v10） |
