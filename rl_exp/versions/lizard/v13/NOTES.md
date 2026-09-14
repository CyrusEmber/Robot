# v13 NOTES —— 换回 Miki 对称跟踪核（一个核闭三个账本盲区）

- 修订历史：v13.0（2026-09-14，单变量：跟踪核换形）。

- 目的/假设: v10 判决（`v10\NOTES.md` + `DIAGNOSE.md`）暴露 EP 线性核
  `track_lin_vel_xy_lin`（v5，Cheng et al. 2023 Eq.2）的三个账本盲区：
  ① **超速饱和中性**——`clamp(proj, max=speed_c)`，快了不扣分（实测 cmd 0.3 跑
  0.445，+48…54%，账本 1.47/1.5）；② **横向不进分子**——`proj` 只取命令轴投影，
  横向速度不受约束（实测恒定 ~19–21° 蟹行、世界横移 2.4–6.2 m/10 s）；③ **零命令
  无停车梯度**——cmd=0 时 `proj≡0`，站与不站同分（实测零命令 10 s 漂 0.31 m 不停）。
  口径限定（DIAGNOSE 修订后）：①是超速的**必要条件而非充分条件**——本版闭合的是
  **账本盲区**，策略是否收敛到"跟准"由验收量测判，不预设。
  v13 假设：换回 Miki et al. 2022 对称核 `r = exp(−‖v_cmd − v_yaw‖²/0.25)`
  （全 2D 误差、yaw 帧），一个核同时闭合三洞的账本侧；且 **cmd=0 站立拿满分** =
  停车目标首次进账本。
- 相对 v10 的变更（**单变量**，obs/DR/地形/终止/课程零变更）:
  - `versions/lizard/v13/lizard_params.yaml` = v10 全量拷贝 + `v13:` 段（v1–v10
    段保留作冻结记录；v5 段的 `track_goal_vel` 留作 EP 核冻结档案）
  - `LizardRoughTeacherEnvCfg_V13(V10)`: `params_version="v13"`，
    `__post_init__` 里 `rewards.track_lin_vel_xy_lin = None` 并挂
    `teacher_mdp.track_lin_vel_xy_miki`（weight/sigma_sq 读 v13 段）
  - 注册 `Lizard-Rough-v13` / `Lizard-Rough-Play-v13`（runner
    `lizard_rough_teacher_v13`）
  - 静态闸: `rl_exp/tools/verify/check_reward_v13.py`（无 sim：V13 miki 接线 +
    EP 核移除 + V5/V10 冻结不动 + yaml 记录）
- **偏差声明（F（belly −0.5 / r_slip −0.03 / torque 等）的相对权重逐字节同 v10，这是
  纯核形状单变量消融的前提；代价是不复刻论文超参比，判读时记住这点。
- 已知风险（预注册，判废线 = v10）: v3/v4 病历——旧 exp 核让站立白嫖残值，收敛到
  脚垫蹭行最优。不复发理由：v5 反塌缩包其余件全保留（r_fc 符号修正、r_slip ×10、
  belly −0.5 连续受力罚）。**复发判据**（任一触发即判废回滚 v10）：
  `Episode_Reward/feet_slide` 劣于 v10 同期、后脚占空比塌向 0、低速档 success_rate
  回退、`belly_contact_force` 持续 >0 且 tracking 高。
- 验收（预注册，全部用 diagnose_support 修正后口径——真实体重 706.3 N、xyzw lib
  旋转、全 50 Hz 接触）:
  1. 三洞量测闭合（ckpt 接管，Phase 1/2 重跑）: 0.3 m/s 档 `overshoot < 0.15`；
     `|slip_y| < 0.05 m/s`；零命令 `|v| < 0.1 m/s`
  2. 不劣化: `Metrics/success_rate` 与 `Curriculum/terrain_levels` 不低于 v10
     同期（判读节点同 v10：~15000 iter 或中途 ~2000 iter 快判）
  3. 趴窝哨兵: feet_slide 账本不劣化、四脚 duty 不塌、belly ≈ 0
  4. 观察项（非闸）: 载荷左右对称性（lf/rf 比）与静止期四脚着地是否改善——
     v10 的三脚站/左前 62% 是否随停车梯度消失
- 训练命令:
  ```bat
  python scripts\reinforcement_learning\rsl_rl\train.py --task Lizard-Rough-v13 --max_iterations 15000 --seed 42
  ```
- log 目录: logs/rsl_rl/lizard_rough_teacher_v13/
- 结果回填: （训练后补：三洞量测表 / success_rate 与 terrain_levels 对 v10 /
  趴窝哨兵读数 / 结论）
- 结论: （一句话，训练后补）
