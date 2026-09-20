---
id: lifecycle-hard-refusal-and-policy-reversals
title: 缺课程状态硬拒真跑臂 + 两条策略反转（PLAN 挂账 #23/#25，已结案）
scope: rl_exp/tasks, rl_exp/tools/runrecord
status: done
landing: rl_exp/tools/verify/lifecycle_entry_run.py, rl_exp/tools/runrecord/lifecycle.py, rl_exp/tools/verify/recipe_lifecycle.py
outcome: ① 入口侧真跑两臂：剥掉课程状态的 ckpt `--resume` **exit 2 硬拒**且文案点名缺状态；同一 ckpt 加 `--drop_curriculum_state` **exit 0 放行**并记显式降级。期间发现并修掉"参数网格主线真跑全灭"（P005）。② 两条**有意反转**落进契约：退休线放行开关撤销（`judge()` 只看状态 ⇒ 退休线一律拒新训与续训）；manifest 不可用即硬拒（`ImportError` 分支从 WARN 改 `[FATAL] … refusing to launch unrecorded`）——即"记录绝不阻断训练"被有意反转。
evidence: rl_exp/versions/lizard/ACCEPTANCE.md, rl_exp/docs/pitfalls.md
---

## 问题与本次范围

两条都是"离线断言不足、必须真进程证据"的类：缺状态的硬拒要证据来自真进程的退出码而不是单测；
策略反转要同时改契约文字与补丁，并清掉旧口径的每一处残留。

## 未覆盖边界

其余 `lifecycle` 档位的入口侧真跑不在本项；`ACCEPTANCE.md` 按"追加不改写"补记，历史行不改。
