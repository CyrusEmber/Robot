# v11 —— 联合粒子地形课程（Lee 2020 复刻 + 联合粒子扩展）

- 修订历史：v11.0（2026-09-10，件 1–5 落地）；v11.1（2026-09-10，审查四修，
  见 `PLAN.md` 修订记录）。

- 目的/假设: v10 之上解决三件事——① **对角线问题**：stock `TerrainGenerator`
  单难度标量把类型所有参数同步插值（stairs step_width 恒 0.7），呈弓形）；②
  **速度盲维**：v5 起 lin_vel_x (0,3) 与课程无关，"同地形不同速度"不可表达；
  ③ **测量口径**：v5.5 二值终局代理回论文逐步 Tr（家族挂账 #15 候选 a 落地）。
  假设：联合粒子 (参数格 cell, 速度桶) 的 SIR 把流量集中到 Tr∈[0.5,0.9] 薄壳，
  壳的多模态得到充分训练。方案 SSOT = `PLAN.md`（12 节 + 修订记录）。
- 相对 v10 的变更（结构级，reward/obs/动作/DR 零变更）:
  - `versions/lizard/v11/lizard_params.yaml` = v10 全量拷贝 + `v11:` 段
    （terrain_grid 难度等级表 58 combos / velocity_buckets ×6 / terrain_curriculum
    课程旋钮 / velocity_command Eq.2 阈值+抖动）
  - `rl_exp/tasks/param_grid_terrain.py`（新）: 参数组合网格构建器——每 combo
    一个 sub-terrain（单值 range，难度插值 no-op），名称编码 `<type>|<lvl>...`
  - `rl_exp/tasks/teacher_mdp.py` v11 段（add-only，v5 SpawnWeightSIR 冻结）:
    `ParticleVelocityCommand`（Eq.2 逐步标签累加 + 桶命令 + (0,3) 回落）+
    `JointSIRTerrainCurriculum`（Eq.7 权重 / 单轴游走 / replay / 带空方向分流
    兜底 / frontier_max_v·particle_entropy·tr_mean 三键）+ `JOINT_SIR_TERM` 常量
  - `rl_exp/tasks/teacher_env_cfg.py`: `LizardRoughTeacherEnvCfg_V11(V10)` +
    `_V11_PLAY`（terrain 换 param-grid 生成器 + joint_sir 接线 + 命令项替换）
  - 注册 `Lizard-Rough-v11` / `Lizard-Rough-Play-v11`（runner
    `lizard_rough_teacher_v11`）
  - 验证链: `test_joint_sir.py` **10/10**（含 v11.1 跨块累积回归）+
    `check_obs_layout.py` v11 断言 + `run_offline_checks.bat` [11/11] +
    `teacher_smoke_v11.py`（PLAY 段已验：obs 381 三组/命令回落/spine 0.25；
    TRAIN 段留开训前补跑——用户拍板 2026-09-10 不起 sim）
  - **v11.1 审查四修**（同日，用户拍板"顶档降 0.45，别的也修"）:
    ① stairs 顶档 0.55→0.45 等距重切 [0.08,0.17,0.27,0.36,0.45]（动力学
    演算：腿力矩/功率全过 ~106 N·m vs 180 限，卡躯干几何——0.55 = 站高
    0.94 的 59%，腹面借越无余量；0.42/0.55 无任何 run 实证）② `_resample_all`
    结算式清零（P0：原每块无条件清零，.1 类 6.15 eps/粒子/块贴 n_traj_min
    饥饿线，低流量 pair 权重永久均匀 = 课程静默死）③ `JOINT_SIR_TERM`
    常量化（三处同源防改名静默回退）+ `desired >= 0.0` 哨兵（0.0 桶不再被吞）
    ④ PLAN 勘误（档位表对齐 yaml 实值 / §2.2 预算 4096 env 实测回填 /
    终止步偏差声明 / 冷启动声明改实际实现）+ 修订记录节
- 已知上限/偏差（详见 PLAN §9/§11）:
  - 终止步无 done 特判，按实际速度记 ν（论文"终止记 0"未逐式复刻；v10 后
    仅 time_out，影响≈0）
  - 冷启动 = 全最易 combo + v 桶 0.5–3.0 轮转（无近平地/低速偏置——原 PLAN
    声明未实现，v11.1 勘误）
  - stairs 顶两档 0.36/0.45 仍超历史任何训练/评测实证范围（terrain_levels
    贴地、eval 套件止于 0.20）——preflight 重点目视
  - per-type 粒子数旋钮不存在（particles_per_type 全局单值）；低比例类型
    靠 v11.1 跨块累积覆盖
- 版本纪律: 开训门 = v10 判决（`../v10/NOTES.md` 验收 1–5）；v10 判废则
  重SpawnWeightSIR（v5–v10）零改动，test_v5_terrain_sir
  9/9 回归绿。
- 训练命令（开训门后）:
  ```bat
  python scripts\reinforcement_learning\rsl_rl\train.py --task Lizard-Rough-v11 --max_iterations 15000 --seed 42
  ```
- log 目录: logs/rsl_rl/lizard_rough_teacher_v11/
- 验收（预注册，~2000 iter 节点判读，详表见 PLAN §8）:
  1. `Curriculum/joint_sir/frontier_max_v` 爬升（课程活性）
  2. `particle_entropy` 不塌 0（多模态健康）
  3. `tr_mean` 落 [0.5, 0.9] 附近
  4. 离对角 cell episode 占比 > 20%（对角线问题直接量化）
  5. eval v1 旧套件 completion 不低于 v10 同期（能力不回退）
- 结果回填: （训练后补：三键曲线读数 / 离对角占比实测 / eval 跑分表 / 结论）
- 结论: （一句话，训练后补）
