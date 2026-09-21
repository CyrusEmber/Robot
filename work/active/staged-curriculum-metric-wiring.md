---
id: staged-curriculum-metric-wiring
title: staged 课程的 Curriculum/*/metric 恒 0（接线 bug，PLAN #9）
scope: rl_exp/tasks/staged_curriculum.py
status: open
landing: rl_exp/tasks/staged_curriculum.py, rl_exp/tasks/curriculum_env_cfg.py, rl_exp/tools/verify/test_staged_curriculum.py
next: 先复现再定位，定位到层再修：跑一条带 staged 课程的最小 run，取 `Curriculum/<term>/metric` 与同帧 `Metrics/success_rate` 对照。已读到的两个候选层（**是候选不是结论**，由这次复现判定）：term 只在"未到末级且依赖满足"时才返回 metric（末级那支与依赖未满足那支只返回 stage），以及 curriculum 计算与 command reset 的计算时序。修完要覆盖每一支并留反证，现有离线用例在 `test_staged_curriculum.py`
close_when: 执行者跑出这条 run 并读 `Curriculum/<term>/metric`：序列与同帧 `Metrics/success_rate` 的 EMA 一致、且末级与依赖未满足两支也取到值 ⇒ 关，反证用例一并留下；仍恒 0 ⇒ 写出实际接线路径与挡住的层，保持 open，修复另立实施项
---

## 当前状态

家族 staged 课程（`StagedCurriculumTerm`）的判据读数报不回来：日志里的 `Curriculum/<term>/metric` 恒 0。v3 的 c_k 课程因此**刻意不走 CurriculumTerm**（改纯函数推导 + 自定义 reward/event 读取）。本 bug 的修复仍挂账，影响面只限家族里走 staged 课程的版本。

## 未覆盖边界

本项不改 staged 课程的判据语义（阈值 / sustain / 依赖关系的规则归 `staged_curriculum.py` 的 docstring 与既有用例），只修"读数回得来"这一件事；c_k 那条路（纯函数推导）是否回填进 CurriculumTerm，不在本项，属方案变更。
