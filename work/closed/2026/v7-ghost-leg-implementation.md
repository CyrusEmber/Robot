---
id: v7-ghost-leg-implementation
title: v7 实施（ghost 断腿鲁棒性；方案 SSOT = v7/PLAN.md）
scope: rl_exp/versions/lizard/main/v7, rl_exp/tasks, ablation_harness
status: superseded
landing: rl_exp/versions/lizard/main/v7/PLAN.md, rl_exp/tasks/recipe.py, ablation_harness/suites.py
outcome: v7 是退役线 `lizard/main` 的版本，实施对象（env cfg、`Lizard-Rough-v7` 注册、断腿 DR 与 eval suite）随本迭代的代码清理删除，前置依赖（v8 已训）也随线消失 ⇒ 实施动作由清理项接管；方案文本仍在冻结的 `v7/PLAN.md`。
superseded_by: retired-family-code-prune
---

## 当前状态

v7 已拍板开（2026-09-08），方案与子类边界写在 `v7/PLAN.md`；工作树里 `main/v7/` 只有四件套骨架，没有 cfg、没有注册入口（`OBS.md` 的演进总表按"有历史目录、无注册入口"登记）。本项是它的排期与前置门，不是方案的第二个副本。

## 未覆盖边界

断腿后的奖励/终止语义细节、DR 参数取值，都以 `v7/PLAN.md` 为准；本项不接管 obs 契约的布局声明（那要过 `check_obs_protocol` 与声明面），也不含 v8 微调的训练结果判读（归该版本 NOTES 与 `ACCEPTANCE.md`）。
