---
id: teacher-v1-first-run
title: teacher 环境快照重写 + smoke 解包 bug + v1 首跑验收（PLAN 挂账 #1/#2/#3，已结案）
scope: rl_exp/tasks, rl_exp/versions/lizard/main/v1
status: done
landing: rl_exp/tasks/teacher_env_cfg.py, rl_exp/tools/verify/teacher_smoke.py, rl_exp/versions/lizard/main/v1/NOTES.md
outcome: teacher env 去掉 lizard 中间层继承、独立成快照；teacher_smoke 的 gym 5 元组解包 bug 修掉；v1 首跑 14000 iters 并出对照结论——**特权 obs 救活趴窝**（零动作 success 0.254 → v1 0.635），遗留 fall 随迭代上升（0.03→0.33）、`gap_40cm` 不跳。
evidence: rl_exp/versions/lizard/ACCEPTANCE.md, rl_exp/versions/lizard/main/v1/NOTES.md
---

## 问题与本次范围

建档期的三件基础工作：teacher 侧继承链、冒烟脚本可跑性、第一版能否出分。前两件是"能不能跑"，
第三件是"跑出来说明什么"——对照结论改变了后续杠杆方向（改走 v3 论文口径）。

## 未覆盖边界

`fall` 随迭代上升与 `gap_40cm` 不跳两条**未归因**：它们进的是 v3+ 的路线讨论（PLAN §2/§3），
不在本项。v1 的原地复现已整体退役（资产换代），旧 ckpt 只在旧资产上有意义。
