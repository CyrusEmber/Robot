---
id: staged-curriculum-metric-wiring
title: staged 课程的 Curriculum/*/metric 恒 0（接线 bug，PLAN #9）
scope: rl_exp/docs/pitfalls.md, rl_exp/versions/lizard/main/v3
status: superseded
landing: rl_exp/docs/pitfalls.md, rl_exp/versions/lizard/main/v3/PLAN.md
outcome: 故障模块 `staged_curriculum.py`、其消费的 cfg 与离线用例随退役线清理删除 ⇒ 本项失去可复现的对象与运行入口，剥离动作由清理项接管；该时序 bug 的机制与修法作为通用坑留在 `pitfalls.md` P002。
superseded_by: retired-family-code-prune
---

## 当前状态

家族 staged 课程（`StagedCurriculumTerm`）的判据读数报不回来：日志里的 `Curriculum/<term>/metric` 恒 0。v3 的 c_k 课程因此**刻意不走 CurriculumTerm**（改纯函数推导 + 自定义 reward/event 读取）。本 bug 的修复仍挂账，影响面只限家族里走 staged 课程的版本。

## 未覆盖边界

本项不改 staged 课程的判据语义（阈值 / sustain / 依赖关系的规则归 `staged_curriculum.py` 的 docstring 与既有用例），只修"读数回得来"这一件事；c_k 那条路（纯函数推导）是否回填进 CurriculumTerm，不在本项，属方案变更。
