# v1 —— teacher 首跑配方（DR 收窄版）

- 目的/假设: teacher Phase 1 首次实际训练。v0 未跑即被取代：全量 DR 对
  尚未学会走路的 26 关节蜥蜴门槛过高（家族 run flat 实证 10000 iters 才走、
  rough 15000 iters 趴窝），首跑先收窄扰动验证"特权 + 锁脊柱 + 轻扰动"
  能否出步态。特权 obs + 轻扰动仍趴 → 激励逃生舱坐实；走起来 → 门槛是
  扰动/形态，v2 再逐档加回 DR
- 参数: 与 v0 逐字相同，仅 domain_randomization 段全部收窄（无一归零）：
  friction [0.4,1.2]/[0.3,1.0] → [0.7,1.0]/[0.6,0.9]；
  mass_scale [0.87,1.15] → [0.95,1.05]；mass_scale_limbs [0.7,1.43] → [0.9,1.11]；
  com ±0.05/±0.02 → ±0.02/±0.01；stiffness/damping_scale [0.8,1.2] → [0.9,1.1]；
  joint_friction_add [0,0.05] → [0,0.01]；joint_armature_add [0,0.02] → [0,0.005]；
  external_force [-40,40] → [-15,15]；external_torque [-5,5] → [-2,2]；
  push_velocity ±1.5/±1.5/±0.3 → ±0.5/±0.5/±0.1。
  不变：inertia_scale、reset_height_range、friction_num_buckets、
  奖励/动作/命令/仿真参数（命令仍为论文值 [-1,1]/[-0.5,0.5]/[-1,1]）
- 相对上版: v0 仅 DR 段收窄，其余零改动（纯参数变更）
- 训练命令:
  ```bat
  python scripts\reinforcement_learning\rsl_rl\train.py --task Lizard-Rough-v1 --max_iterations 4000 --seed 42
  ```
- log 目录: logs/rsl_rl/lizard_rough_teacher/
- 验收线（按本机 flat 实证 10000 iters + 特权 2~3x 加速估）:
  ~1000 iters 内 feet_air_time 持续 >0、base 位移；~3000-5000 慢速命令成型。
  1000 iters reward 仍平 + feet_air_time≈0 = 判死刑信号（配方问题，非迭代数）
- 训练实况（2026-09-01 回填）: 实际 14000 iters（非本文件原写的 4000），
  `--max_iterations 14000 --seed 42`，run = `logs/rsl_rl/lizard_rough_teacher/2026-08-31_11-12-20`
  （08-31 11:12 启动 → 09-01 13:04 落 final `model_13999.pt`）。
  ckpt obs 266 → 确认 v1 配方（env.yaml 无 v2 增量 term）
- 逐迭代曲线: 已导出 `tb_scalars.csv`（406000 点 / 29 tags）。
  关键读数（iteration: value）: mean_reward -2.47→1.53(1k)→4.73(4k)→7.49(8k)→8.09(12k)→7.12(14k)；
  track_lin_vel_xy_exp 0.63(4k)→0.72(14k)；terrain_levels 0.32→0.63（仅训练诊断）
- eval 结果（2026-09-01，协议 Locomotion-Eval-v1，seed 123，task `Lizard-Rough-v1`，
  3 ckpt × 双模式，落盘 `ablation_harness\results\locomotion_eval_v1\`）:

  | tag | mode | success | fall | lin_mae | ang_mae | energy J/m | stop超调 | recovery mean | never_rec |
  |---|---|---|---|---|---|---|---|---|---|
  | （零动作基线） | nominal | 0.254 | 0.000 | 0.836 | 0.171 | 1219 | 0.002 | – | – |
  | v1_4k | nominal | 0.581 | 0.028 | 0.479 | 0.229 | 1569 | 0.041 | – | – |
  | v1_4k | robust | 0.511 | 0.278 | 2.244 | 0.276 | 1648 | 4.41 | 11.57 | 0.239 |
  | v1_8k | nominal | 0.593 | 0.278 | 5.157 | 0.362 | 2274 | 17.13 | – | – |
  | v1_8k | robust | 0.602 | 0.389 | 1.872 | 0.265 | 1432 | 5.46 | 7.06 | 0.125 |
  | v1_14k | nominal | 0.635 | 0.333 | 2.177 | 0.295 | 1591 | 7.28 | – | – |
  | v1_14k | robust | 0.610 | 0.417 | 1.958 | 0.275 | 1536 | 5.98 | 5.86 | 0.097 |

  逐地形 completion/fall（14k nominal）: flat .64/.50 slope5 .69/.50 slope10 .73/.12
  stairs10 .67/.38 stairs20 .55/.38 rough_a .71/.50 rough_b .77/.25
  gap20 .52/.38 **gap40 .10/.00（不跳大沟，站沟前）**
- 结论/下一步:
  1. **特权救活趴窝成立**（§4.6 对照判出）：零动作 success 0.254 → v1 0.58~0.64，
     1000 iters 内 reward 1.53、4000 已能全程走完套件。激励逃生舱（挂账 #7）
     不再是 Phase 1 阻塞项。
  2. **fall rate 随迭代上升**（nominal 0.028→0.278→0.333，robust 0.278→0.389→0.417），
     但 recovery 同步变好（11.6→7.1→5.9s，never_rec 0.24→0.10）：策略后期更"敢动"，
     奖励不罚摔 → 摔得起也爬得快。上限判定要盯 fall，不能只看 success。
  3. **lin_mae/stop 超调被摔倒 env 污染**（8k nominal lin_mae 5.16、stop 超调 17.1）：
     协议 valid 掩码只在 episode 终止处截断，摔倒后滑行的 env 仍计入均值——
     跨 run 比较时 MAE 需与 fall 一起读，单看会误判收敛趋势。
  4. gap_40cm 全线 completion ≈0.1、fall=0：不会起跳越沟，Phase 1 未达该难度。
  5. 复现：任务 id `Lizard-Rough-v1` 常驻注册（`LizardRoughTeacherEnvCfg_V1`，
     obs 266，spec 剥离 v2 增量 term），或 `git checkout v1` 整树快照。
     下一步 = 同协议跑 v2（obs 308）对照，判特权补全的净增益。
- 基础设施坑（评测台，非配方）: `eval.py` 缺 train.py 的
  `handle_deprecated_rsl_rl_cfg` 迁移，rsl-rl 5.4.2 拒绝 legacy `stochastic` 字段
  → checkpoint 路径直接 `TypeError`（08-31 冒烟是零动作策略，从未走过该路径）。
  已修 `ablation_harness\eval.py` `_prepare_env`。summary.csv 6 行 rev 从 c2d5d03
  变到 edba705，中间两提交为 skill/规则文档搬迁，测量代码未变，六行可互比。
