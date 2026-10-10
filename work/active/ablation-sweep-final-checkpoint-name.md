---
id: ablation-sweep-final-checkpoint-name
title: 调度器的"训练已完成"凭据（model_{max_iterations}.pt）与训练器收尾保存命名差一
scope: ablation_harness/run_ablation.py, ablation_harness/specs
status: open
landing: ablation_harness/run_ablation.py
next: 先定口径再改：① `_run_train` 与 `_sweep` 那处同一检查判定"这一步训练已完成"的凭据该是什么——现在要的是 `model_{max_iterations}.pt`，而训练器收尾保存的名字是 `model_{max_iterations-1}.pt`；② 另一条路是把既有约定（spec 的 `max_iterations` 当"复用已有 checkpoint 的下标"，训练只在它缺失时发生）写进 `run_ablation.py` 的 docstring，让检查与那句话一致。两处同源一次改完，再按 `close_when` 真跑一条不能复用的 spec
close_when: 一条**不复用旧 checkpoint** 的 spec 能走完 train → eval：判据 = `[ABLATION] sweep done, failures=0` 且对应 `results/<协议>/<组>/<run_id>/eval.json` 落盘；或用户明示"spec 只走复用路径"，则判据改为 docstring 写明该前提、检查与之一致。两条路都得落一份 `acceptance/records/` 记录。缺 checkpoint 时报失败是当前行为，不算通过
evidence: acceptance/records/2026-10-10-isaac-root-parameterisation.md
---

## 当前状态

发现现场 = G3 收尾事项（`isaac-root-parameterisation`）的真跑探针，读数与复现命令在其记录里。
本项的判据、口径取舍与修法都还没动：现状是**任何需要真训的 spec 都过不了这一步**，只有"checkpoint 已存在"的
跳过路径能走通 —— 后者是历史用法，所以缺陷一直没露头。

## 未覆盖边界

- 只动调度器对"训练已完成"的判定，不动 `save_interval` 语义，也不动 spec 的字段含义
  （`eval_checkpoints` 仍按训练器自己的命名给下标）。
- 不评价 `--summarize` / `--by-terrain` 两态（它们不调 `_isaac_root()`，与本项无关）。
- 训练器侧（`rsl_rl` fork 的收尾保存命名）是机器本地安装的事实，本项不改、也不假设它会变。
