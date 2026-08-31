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
- eval 结果: （训练后回填）ablation_harness results/locomotion_eval_v1/，tag=v1
- 逐迭代曲线: （训练后导出）`python lizard_exp\dump_tb.py --log_dir <run目录> --out lizard_exp\versions\v1\tb_scalars.csv`
- 结论/下一步: 未训练即被 v2 取代（2026-08-31，v2 = 本版参数 + 特权 obs
  论文对齐补全）。**复现：任务 id `Lizard-Rough-v1` 常驻注册**
  （`LizardRoughTeacherEnvCfg_V1`，obs 266，spec 剥离 v2 增量 term），
  或 `git checkout v1` 整树快照
