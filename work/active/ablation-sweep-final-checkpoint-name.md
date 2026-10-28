---
id: ablation-sweep-final-checkpoint-name
title: 调度器的"训练已完成"凭据（model_{max_iterations}.pt）与训练器收尾保存命名差一
scope: ablation_harness/run_ablation.py, ablation_harness/specs
status: in_progress
landing: ablation_harness/run_ablation.py
next: 执行者用全新 tag 与独立组补跑新训到评测，保留原始 spec、完整命令和终局日志，再交无执行历史的新上下文审核。
close_when: 一条**不复用旧 checkpoint** 的 spec 能走完 train → eval：判据 = `[ABLATION] sweep done, failures=0` 且对应 `results/<协议>/<组>/<run_id>/eval.json` 落盘；或用户明示"spec 只走复用路径"，则判据改为 docstring 写明该前提、检查与之一致。两条路都得落一份 `acceptance/records/` 记录。缺 checkpoint 时报失败是当前行为，不算通过
evidence: acceptance/records/2026-10-10-isaac-root-parameterisation.md
---

## 当前状态

代码已修复，独立审核发现原探针缺少可复核的终局日志；真实新训、零失败终局与原组 eval 须在同一次执行中补证。审核结果见 evidence 的「checkpoint 完成凭据独立审核」节。

## 未覆盖边界

- 只动调度器对"训练已完成"的判定，不动 `save_interval` 语义，也不动 spec 的字段含义
  （`eval_checkpoints` 仍按训练器自己的命名给下标）。
- 不评价 `--summarize` / `--by-terrain` 两态（它们不调 `_isaac_root()`，与本项无关）。
- 训练器侧（`rsl_rl` fork 的收尾保存命名）是机器本地安装的事实，本项不改、也不假设它会变。
