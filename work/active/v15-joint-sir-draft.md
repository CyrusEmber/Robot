---
id: v15-joint-sir-draft
title: v15 起草：joint SIR 课程代码件、前置门与 4 项待拍板
scope: rl_exp/versions/lizard/main/v15, rl_exp/tasks
status: open
landing: rl_exp/versions/lizard/main/v15/PLAN.md, rl_exp/tasks/param_grid_terrain.py, rl_exp/tasks/teacher_mdp.py
next: 代码件按 `v15/PLAN.md` 实施（本项只管排期、前置门与待拍板项，方案正文不复述）。**前置门三条**：① 该课程线从未真训（v11 只有冒烟、v12 无 run）⇒ v11/v12 不作基线；② 本版在老框架训练而项目并行迁新框架 ⇒ 开训前必须打 tag、训练进程不得重启或续训、训练结束前不得 `cfg_lock --update`；③ 迁移后必须保留旧任务 id 映射才能评 v15 ckpt。**待拍板 4 项（不得夹在装配里顺手做，由用户拍板）**：yaw 帧标签 / 固定窗口 `W` / `anchor_combo` / `curriculum_state` v2→v3——尤其"共享课程类是否改变历史版本语义"
close_when: 代码件实施完、4 项待拍板各有裁决并记进 `v15/PLAN.md` 后，执行者观察两条：① 离线闸全绿，且 v15 与 v14 的零差异被闸门证（obs / 动作 / 奖励 / 终止 / DR / 资产）；② v11/v12 golden 重生成后的处置（偏差声明或 v15 专用变体）已写进方案。两条成立即关；任一未定 ⇒ 保持 open，且不进入开训准备
---

## 未覆盖边界

课程判读量口径（`tr_mean` / `particle_entropy`，`frontier_max_v` 不作能力进度）与 v15 命令口径变化（不得与 v5–v14 同表）写在 `v15/PLAN.md` 与 `ACCEPTANCE.md`，本条不复述；训练结果判读归该版本 NOTES。方案 SSOT 是 `v15/PLAN.md`，本项与它冲突时以后者为准。
