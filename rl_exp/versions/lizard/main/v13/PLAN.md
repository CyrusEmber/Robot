# v13 PLAN —— 换回 Miki 对称跟踪核（一个核闭三个账本盲区）

> 生成：2026-09-14。状态：**实施完成待训**（单变量消融，base = v10；验收门与判废线
> 预注册于 `NOTES.md`，v13.1 开训前修正两处口径）。

## 目的/假设（≤3 行）

v10 判决暴露 EP 线性核三个账本盲区：超速饱和中性（+48…54% 而账本 1.47/1.5）、横向
投影不可见（~20° 蟹行）、零命令无停车梯度。假设：Miki 2022 对称核
`exp(−‖v_cmd−v_yaw‖²/0.25)`（全 2D 误差）一个式子闭合三洞的账本侧；停车目标首次
进账本（cmd=0 站立 = 满分）。**口径限定**：账本闭合 ≠ 行为必然跟准（旧核只是**放过**
了超速误差，不是超速的必要条件），验收量测判。

## 相对 v10 的 diff（单变量，obs/DR/地形/终止/课程零变更）

1. `lizard_params.yaml` = v10 全量拷贝 + `v13:` 段（`track_goal_vel.weight=1.5`、
   `sigma_sq=0.25` + 预注册判废线；v5 段留作 EP 核冻结档案）
2. `LizardRoughTeacherEnvCfg_V13(V10)`：`__post_init__` 里 EP 核 → None，挂
   `teacher_mdp.track_lin_vel_xy_miki`（yaw 帧、全 2D 误差、无 min_speed）
3. 注册 `Lizard-Rough-v13` / `Lizard-Rough-Play-v13`（runner
   `lizard_rough_teacher_v13`，独立 experiment_name）
4. 静态闸 `rl_exp/tools/verify/check_reward_v13.py`（miki 接线 / EP 移除 /
   V5+V10 冻结 / yaml 记录 / v13.1 静止值表），挂进 `run_offline_checks.bat`

**偏差声明**：weight 保持 1.5（paper 0.75）——保跟踪天花板与罚项比例同 v10，纯核
形状单变量。

## 验收（同 NOTES 预注册；v13.1 开训前三处修正）

1. 三洞量测（**与奖励核同帧**）：前向 = `vel_yaw_x`（yaw 帧；体坐标只作诊断），
   `abs(mean(vel_yaw_x)/v_cmd − 1) < 0.15` @0.3 档（原签名量把「完全不动」记成 −1 也
   放行）+ **报告逐帧** `fwd_mae_mps = mean|vel_yaw_x − v_cmd|`（不设闸，防快慢交替被
   均值抵消）；侧滑闸 `mean(|vel_yaw_y|) < 0.05 m/s`（签名均值会被左右摆动抵消）；
   零命令 `|v| < 0.1 m/s`。闸 `test_acceptance_metrics.py`
2. 不劣化 = **固定场景性能**：Locomotion-Eval-v1 nominal seed 123（`lizard_suite_v1`，
   含 stairs_10·20cm / rough / gap）上 v13 对比 v10 ckpt 同期的 `lin_mae_mps`
   （全局+逐地形）/ `terrain_completion_mean` / `success_rate` / `fall_rate` /
   `stop_overshoot_mps`，+ diagnose Phase 2 速度误差与位移、Phase 3 单级台阶通过率。
   **不用** `Curriculum/terrain_levels`（课程状态 ≠ 能力）
3. 趴窝判据（**非单项**）：`feet_slide` 变差只记观察项（从静止变真走，滑动代价本可
   上升）；判废回滚 v10 = 速度误差不达标 **且** 进度/位移回退 **且**（后脚 duty 塌向 0
   或 belly 持续受力）
4. **第一轮判读问题**：侧向漂移与超速是否下降，且未退化成欠速/不动（不加四脚着地 /
   belly 新罚项，保单变量）
5. 观察项（非闸）：左右载荷对称性 / 静止期四脚着地

## 训练

```bat
python scripts\reinforcement_learning\rsl_rl\train.py --task Lizard-Rough-v13 --max_iterations 15000 --seed 42
```

log：`logs/rsl_rl/lizard_rough_teacher_v13/`

## 修订记录

| 日期 | 版本 | 变更 + 原因 + 依据 |
|---|---|---|
| 2026-09-14 | v13.0 | 初稿（用户拍板"换回 miki 的"；v10 判决 + DIAGNOSE 修正口径为依据；风险预注册 = v3/v4 趴窝病历，判废线 v10） |
| 2026-09-14 | v13.1 | 开训前验收修正（用户 review；代码/配方零变更，只改验收与表述）：① 速度误差改 **abs 双向** + 逐时刻 `fwd_mae_mps` 报告（签名量在完全不动时 = −1 也能过闸；均值达标而快慢交替不可见）；② 「不劣化」改**固定场景性能**（eval v1 套件 + diagnose Phase 2/3），弃 `terrain_levels`（课程状态非能力）；③ `feet_slide` 单项降为观察项，判废改**组合判据**（速度误差 + 进度/位移 + 趴窝形态）；④ 表述修正：旧核 clamp 是「放过」超速误差而非其必要条件，反塌缩包保留 ≠ 不复发（静止时 belly/slide 罚项 ≈0，0.3 档静止→满分最大增益仅 0.453） |
| 2026-09-14 | v13.2 | 验收量测**换帧 + 侧滑改 abs**（用户 review；代码/配方零变更）：前向一律 `vel_yaw_x`（= 奖励核同帧；体坐标 `fwd_b` 在 45° 俯仰下假阴 −29%，实测见 `test_acceptance_metrics.py`）、侧滑闸改 `mean(|vel_yaw_y|)`（原签名均值把左右交替侧滑抵消成 ~0）、逐帧 MAE 保留；新增纯函数模块 `diag_metrics.py` + 离线闸 `test_acceptance_metrics.py`（5 例：核满分/超速/欠速/侧滑降分、yaw 不变性、混俯仰不误报欠速、交替侧滑必判不通过）。harness `lin_mae_mps` 仍体坐标 → 记待办（改需 `Locomotion-Eval-v2` + 重跑 v10 基线） |
