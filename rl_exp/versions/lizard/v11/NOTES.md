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
- 首跑实证（2026-09-11，resume smoke，非开训；TRAIN 段由此首次起仿真）:
  - **4096 env（默认）stock 2\*\*26 接触栈溢出 → obs NaN 崩溃**（日志 635–644 行，
    `collisionStackSize` 需 ≥67.2M 字节）：与 v4 NOTES 第 2 条预警同源——接触
    密度问题，不是栈容量问题；按家族纪律**未再抬栈**（v4 PLAN：溢出复发 → 修
    接触几何）。**结论：v11 按现行地形网格不能以默认 4096 env 开训**，开训前
    必须先处理接触几何（或由用户拍板接受 2\*\*28 症状修补）
  - **512 env 干净**：60 iter / 165 s，无溢出无 NaN（接触对数量随 env 数缩放，
    stock 2\*\*26 余量 ~8×）。该 env 数是 smoke 专用选择，**不构成配方改动**
  - 真续训四证（同一 checkpoint `model_50.pt`：counter=1224）:

    | 场景 | 命令 | 实证 |
    |---|---|---|
    | 全新 | `--num_envs 512 --max_iterations 60` | save hook 生效：`model_0/50/59` 带 counter = 24/1224/1440（= it×24）|
    | 真续训 | `--resume --checkpoint model_50.pt --max_iterations 20` | 报告 `counter=1224 c_k=0.5631 lr=4.9745e-4`、`next_eval_step=1440`（首个块边界 > counter）、半块 `n=11`、`particle_entropy=0.8325 frontier_max_v=2.938`；首存 counter=1248 |
    | 权重模式 | `--resume --weights_only` | 明示丢弃课程状态；首存 `counter=24`（冷时钟）——与真续训的 1248 成数值对照 |
    | 老式无状态 ckpt + `--resume` | 同上（把 checkpoint 的 `infos` 剥空） | `train.py:226` RuntimeError **硬中断**，训练前退出，提示 `--weights_only` |

  - 判读：真续训的 c_k 连续（0.2 → 0.5631，未回热）、粒子分布/半块证据/评估时刻
    全带过来；权重模式同一 checkpoint 却从 c_k=0.2 冷起——两模式可用数值区分。
    机制与限制（不存 RNG、非逐位复现、c_k-only 版本仍回热）见
    `../v12/NOTES.md`「续训」+ `rl_exp/tasks/curriculum_state.py`
- 验收（预注册，~2000 iter 节点判读，详表见 PLAN §8）:
  1. `Curriculum/joint_sir/frontier_max_v` 爬升（课程活性）
  2. `particle_entropy` 不塌 0（多模态健康）
  3. `tr_mean` 落 [0.5, 0.9] 附近
  4. 离对角 cell episode 占比 > 20%（对角线问题直接量化）
  5. eval v1 旧套件 completion 不低于 v10 同期（能力不回退）
- 结果回填: （训练后补：三键曲线读数 / 离对角占比实测 / eval 跑分表 / 结论）
- 结论: （一句话，训练后补）
