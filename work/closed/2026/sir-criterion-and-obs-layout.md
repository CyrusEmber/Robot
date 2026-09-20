---
id: sir-criterion-and-obs-layout
title: SIR 课程判据 v6 候选 + obs_layout 同步（PLAN 挂账 #15/#10，已结案）
scope: rl_exp/tasks, rl_exp/versions/lizard/main/v3
status: done
landing: rl_exp/tasks/components.py, rl_exp/versions/lizard/main/v11/main_params.yaml, rl_exp/tools/verify/test_joint_sir.py, rl_exp/versions/lizard/OBS.md, rl_exp/tasks/obs_protocol.py
outcome: 判据候选 a（逐步 Tr，贴论文 Eq.2/3/7）**由 v11 的联合粒子 SIR 落地**；v5 时代的二值代理判据冻结不改。obs_layout 随 v3 装配同步到三组（90/208/83）——组级 SSOT 归 `OBS.md`，代码侧由 `check_obs_layout.py` 看守。
evidence: rl_exp/versions/lizard/ACCEPTANCE.md, rl_exp/versions/lizard/main/v11/PLAN.md
---

## 问题与本次范围

两条"口径"挂账：SIR 课程用什么量判读（候选 a 逐步 Tr / 候选 b v5.4 进度分制），
以及 v3 三组 obs 的 yaml 注记与组级 SSOT。

## 未覆盖边界

候选 b（v5.4 进度分制，代码保全在 git `3ef2aa0`）**未采用、未删除**：留着当备选，不属本项。
判读量本身的语义（`frontier_max_v` 冷启动即满值、不能当能力进度）归 v15 的课程评审。
