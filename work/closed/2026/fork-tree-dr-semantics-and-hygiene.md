---
id: fork-tree-dr-semantics-and-hygiene
title: fork 树 DR 语义钉住 + 树内杂物定性（PLAN 挂账 #19/#20，已结案）
scope: rl_exp/tools/verify
status: done
landing: rl_exp/tools/verify/framework_pin_check.py, rl_exp/fork_patches/local_tree_extras.patch, hooks/pre-commit
outcome: ① fork 树的未提交 DR 改动（`interval` 模式与 interval 节拍）会静默改实验——改为 AST 按赋值目标名取 keyword 值钉住（不用全文件 regex），配 `--self-test` 5 fixtures；**关键限制已实测**：只改树时现有整文件比对就会红，新断言的价值只在"树与 patch 同时改且仍一致"时显现；hook 触发面补 `.patch` 与 `hooks/`。② `isaaclab.bat` 被清空是 `local_tree_extras.patch` 的刻意目标（不是故障，仅在 patch 头补注记）；树根 0 字节未跟踪 `python` 已删，验收口径 = status 恰好少一行且其余条目逐项不变。
evidence: rl_exp/versions/lizard/ACCEPTANCE.md
---

## 问题与本次范围

fork 树带着未提交改动，任何新 run 的 DR 都由它决定——"改树等于改实验"而闸门原先看不见。
另一件是树内杂物的定性（刻意置空 vs 故障、可删 vs 不可动）。

## 未覆盖边界

`local_tree_extras.patch` 里那三处本地改动（`isaaclab.bat` + `anymal_c_env.py` + `velocity_env_cfg.py`）
本身**保留**；归档与隔离重建的取材口径归 `PLAN` #18 / `rebuild.py`，不在本项。
