---
id: phase2-obs-fidelity
title: Phase 2 输入侧两件：特权真值 term 的 event 缓存 + 三噪声模型移植
scope: rl_exp/tasks, rl_exp/versions/lizard
status: superseded
landing: rl_exp/tasks/teacher_mdp.py, rl_exp/versions/lizard/OBS.md
outcome: 两侧随退役线清理消失（特权真值 term 的宿主 `components.py`、三噪声模型的目标 `student_networks.py` 均已删除），Phase 2 的两件在仓内失去实现落点与开工前提 ⇒ 动作由清理项接管，`OBS.md` 的偏差句作为历史事实留在边界内。
superseded_by: retired-family-code-prune
evidence: rl_exp/versions/lizard/OBS.md
---

## 未覆盖边界

student 侧的蒸馏 runner 本身不在本项；obs 维度/布局的声明面归 `versions/obs_protocols.json`，本项不新增或删除 term。教师侧噪声已在用、student 侧还没有 Python 实现，是本项 ② 的起点。
