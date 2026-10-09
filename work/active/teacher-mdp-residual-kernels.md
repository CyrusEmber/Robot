---
id: teacher-mdp-residual-kernels
title: teacher_mdp 保留段的死代码去向（清理项 A① 的挂账）
scope: rl_exp/tasks
status: open
landing: rl_exp/tasks/teacher_mdp.py, rl_exp/tasks/curriculum_state.py
next: 用户裁决去向——① 抽出：把 `curriculum_state` 依赖的三个符号搬进独立模块，再整删 `teacher_mdp`；② 就地切：保留三个符号所在类、删旧线奖励与终止内核，代价是要先给出可切分边界并证明切完仍绿；③ 保留现状并改归属：把该文件重述为"续训状态层的现有实现"，不再自称旧线
close_when: 三种之一落进实现且 `run_offline_checks.bat` 全绿，或用户明示"保留现状"并把归属写进该文件 docstring ⇒ done；观测 = `teacher_mdp.py` 的 docstring/切片 + 全套离线判词
evidence: acceptance/records/2026-10-09-retired-family-prune-manifest, acceptance/records/2026-10-09-retired-family-prune-execution
---

## 当前状态

三条退休线的代码已移出主路径（`work/closed/2026/retired-family-code-prune.md`，`ALL_OFFLINE_CHECKS_PASSED 37/37`），
但裁决 A① 保留了 `rl_exp/tasks/teacher_mdp.py`：`curriculum_state.py:93-97` 从它取
`JointSIRTerrainCurriculum` / `SpawnWeightSIRTerrainCurriculum` / `ck_value`，而续训状态层是 lizard2
未来接 DR 时的依赖（`work/active/dr-widening-policy.md`）。保留的代价是本项存在的理由：旧线的奖励与
终止内核仍留在主路径，每次 pre-commit 仍为它们付 import 与维护成本 —— 本次省下的是改动风险，不是长期成本。

保留期内它是活的：套件里 `test_joint_sir` / `test_v5_terrain_sir` / `test_resume_state` 与
`terrain_preflight`（经 `param_grid_terrain`）都还在跑它的 SIR 机制。

## 未覆盖边界

本项不裁 lizard2 何时接 DR（那是 `dr-widening-policy` 的事）；不动 `versions/lizard/**` 的冻结 yaml
（保留的 SIR 检查仍把它们当契约读）；不重写冻结版本的 NOTES/PLAN。
