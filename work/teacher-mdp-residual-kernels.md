---
id: teacher-mdp-residual-kernels
title: teacher_mdp 保留段的死代码去向（清理项 A① 的挂账）
scope: rl_exp/tasks
status: open
landing: rl_exp/tasks/teacher_mdp.py, rl_exp/tasks/curriculum_state.py
next: 用户裁决去向——① 抽出：把 `curriculum_state` 依赖的三个符号搬进独立模块，再整删 `teacher_mdp`；② 就地切：保留三个符号所在类、删旧线奖励与终止内核，代价是要先给出可切分边界并证明切完仍绿；③ 保留现状并改归属：把该文件重述为"续训状态层的现有实现"，不再自称旧线
close_when: 选定的改法落地，或将保留理由记录在模块说明中；默认 pytest 和显式点名的 test_joint_sir.py、test_terrain_geometry.py 通过，并核对 curriculum_state 的续训导入路径。
evidence: acceptance/records/2026-10-09-retired-family-prune-manifest, acceptance/records/2026-10-09-retired-family-prune-execution
---

## 当前状态

三条退休线的代码已移出主路径（`work/closed/2026/retired-family-code-prune.md`，`ALL_OFFLINE_CHECKS_PASSED 37/37`），
但裁决 A① 保留了 `rl_exp/tasks/teacher_mdp.py`：`curriculum_state.py:93-97` 从它取
`JointSIRTerrainCurriculum` / `SpawnWeightSIRTerrainCurriculum` / `ck_value`，而续训状态层是 lizard2
未来接 DR 时的依赖（`dr-widening-policy`（已删除：现役实验无 DR，接 DR 须对新实验另立事项））。保留的代价是本项存在的理由：旧线的奖励与
终止内核仍留在主路径，修改这部分时需验证仍在用的导入与离线专项。

`test_joint_sir.py` 检查 SIR 机制。`test_terrain_geometry.py` 覆盖保留的 `terrain_preflight` 和地形再生路径。旧课程和旧续训测试按归档版本复跑。

## 未覆盖边界

本项不裁 lizard2 何时接 DR（那是 `dr-widening-policy` 的事）；不动 `versions/lizard/**` 的冻结 yaml
（保留的 SIR 检查仍把它们当契约读）；不重写冻结版本的 NOTES/PLAN。
