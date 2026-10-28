# lizard2 main/v5 运行记录

## 设计与差异

目的、假设与验收取 [PLAN.md](PLAN.md)。本版以头部持续触地替换旧胸颈瞬时净接触终止；解冻修订关闭指定腿部接触惩罚。完整差异与逐项理由取 [diff.json](diff.json)。

当前修订另关闭全部物理自碰撞；设置与验证取 [本轮记录](../../../../../acceptance/records/2026-10-26-lizard2-v5-self-collision-off.md)。

## 实际执行与偏离

已完成的训练 run 为 `logs/rsl_rl/lizard2_v5/2026-10-26_16-35-11`，最终 checkpoint 为该目录 `model_5999.pt`。命令、seed 与实际配置以 run 内 `run_manifest.json` / `params` 为准。只读复读：从 IsaacLab 根运行 `python -B E:/Robot/rl_exp/tools/trainlog/probe_run.py --exp lizard2_v5`。

原配置、回归与隔离测量取 [验收记录](../../../../../acceptance/records/2026-10-26-lizard2-v5-head-ground-dwell.md)；当前策略的胸腹承地失败对照取 [腹部重开记录](../../../../../acceptance/records/2026-10-28-lizard2-v6-belly-reset.md)。

训练前的解冻与奖励修订历史取 [奖励修订记录](../../../../../acceptance/records/2026-10-26-lizard2-v5-leg-contact-penalty.md)；原记录只覆盖其当时配置，后续自碰撞修订取上文对应记录。

## 结果回填

本机九宫格位于 `ablation_harness/videos/v5_20261028_5999/plane_overview.mp4`，原片及条件取同目录 `matrix.json`；失败模式与对照读数唯一归腹部重开记录。

## 结论

训练已完成，胸腹承地退化姿态由 v6 接续修正终止覆盖；v5 checkpoint 始终按本版原配方解释。
