# v0 —— 首版冻结（lizard 训练系统第一代配方）

- 目的/假设: teacher Phase 1 基线（Miki 两阶段，特权 actor + 基线奖励），
  回答"特权 obs 能否单独救趴窝"（PLAN.md §4.6 对照实验）
- 参数: 与 lizard_params.yaml 2026-08-28 状态一致（72kg、DR 全套、
  mass_scale_limbs [0.7,1.43]、基线奖励回滚态）
- 相对上版: 无（首版）
- 训练命令:
  ```bat
  python scripts\reinforcement_learning\rsl_rl\train.py --task Lizard-Rough-v0 --max_iterations 4000 --seed 42
  ```
- log 目录: logs/rsl_rl/lizard_rough_teacher/
- eval 结果: 未训练——首跑前决定收窄 DR 降低门槛，配方被 v1 取代存档
- 逐迭代曲线: 无（未训练）
- 结论/下一步: 已被 v1 取代（2026-08-31）。全量 DR 保留作对照基准，
  teacher 走稳后按 v2 逐档加回。任务 id `Lizard-Rough-v0` 已注销，
  现行 teacher 任务为 `Lizard-Rough-v1`（读 versions/lizard/v1）
