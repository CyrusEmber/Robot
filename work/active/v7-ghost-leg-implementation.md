---
id: v7-ghost-leg-implementation
title: v7 实施（ghost 断腿鲁棒性；方案 SSOT = v7/PLAN.md）
scope: rl_exp/versions/lizard/main/v7, rl_exp/tasks, ablation_harness
status: open
landing: rl_exp/versions/lizard/main/v7/PLAN.md, rl_exp/tasks/recipe.py, ablation_harness/suites.py
next: 按 `v7/PLAN.md` 清单实施（本项只管排期与前置门，方案正文不复述）：V7 env cfg + 任务注册 `Lizard-Rough-v7`、broken_leg DR 事件、`damage_flags` 4 维进 actor obs、断腿 hfe/kfe 接触罚豁免（走 V7 子类、不改旧类）、broken-leg eval suite、v8 ckpt 微调入口。**前置依赖：v8 已训**（未满足不许冻结/开训）。obs 维度变化属契约变更 ⇒ 走 `versions/obs_protocols.json` 声明面，不改旧版本的声明
close_when: 执行者实施完并观察两条：① `check_cfg_lock` / `check_obs_protocol` / `check_dr_parity` 三条离线闸全绿，且 v7 声明面与实构 cfg 一致；② broken-leg suite 能起来并出一条**真分数**（不是零动作 run）。两条都成立即关；任一红或 suite 起不来 ⇒ 记缺口并保持 open。读数归 `ACCEPTANCE.md`，不进本项
---

## 当前状态

v7 已拍板开（2026-09-08），方案与子类边界写在 `v7/PLAN.md`；工作树里 `main/v7/` 只有四件套骨架，没有 cfg、没有注册入口（`OBS.md` 的演进总表按"有历史目录、无注册入口"登记）。本项是它的排期与前置门，不是方案的第二个副本。

## 未覆盖边界

断腿后的奖励/终止语义细节、DR 参数取值，都以 `v7/PLAN.md` 为准；本项不接管 obs 契约的布局声明（那要过 `check_obs_protocol` 与声明面），也不含 v8 微调的训练结果判读（归该版本 NOTES 与 `ACCEPTANCE.md`）。
