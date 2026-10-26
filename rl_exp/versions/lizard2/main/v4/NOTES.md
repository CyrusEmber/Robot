# lizard2 main/v4 运行记录

## 设计与差异

目的、假设和验收见 [PLAN.md](PLAN.md)。本版将已审 palm 草案落实到正式资产、全部位置动作与子步接触/reset 配置；PPO 与奖励核继承母本。完整差异与逐项理由以 [diff.json](diff.json) 为准。

## 实际执行与偏离

本次查看的 run 为 `logs/rsl_rl/lizard2_v4/2026-10-26_11-16-58/`，checkpoint 为 `model_5999.pt`；命令与实际工况以该 run 的 `run_manifest.json` / `checkpoints.json` 为准。原文“尚未启动训练”已不符合本机已有 run，现修正为实际指针。配置交付仍取 [配置验收记录](../../../../../acceptance/records/2026-10-23-lizard2-v4-configuration.md)。

## 结果回填

本次录像、训练读数与自碰撞归因假设取 [训练现象记录](../../../../../acceptance/records/2026-10-26-lizard2-v4-self-collision-hypothesis.md)；统计复读使用 `rl_exp/tools/trainlog/probe_run.py --run <上述 run 目录> --window 200`。

## 结论

低头及姿态不稳现象已记录，自碰撞影响属于待验证假设，未认定根因或策略验收通过。
