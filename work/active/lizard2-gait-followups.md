---
id: lizard2-gait-followups
title: 步态补测遗留：动作接口无界、奖励载体
scope: rl_exp/tools/diagnose, rl_exp/versions/lizard2
status: open
landing: rl_exp/versions/lizard2/main/v1/main_params.yaml, rl_exp/tasks/lizard2_env_cfg.py, rl_exp/versions/lizard2/main/v1/PLAN.md
next: ① **动作接口无界的处置**（待所有者拍板）：实测高速档关节目标系统性越限，来源是接口本身——策略头最后一层无输出激活、agent cfg `clip_actions: null`（train/play 皆然）、`JointPositionActionCfg` 无 `clip`（`rl_exp/tasks/lizard2_env_cfg.py:102-107`）⇒ 名义 0.5 rad 不是区间，而关节限位 hip ±0.60 / hfe ±1.20 比它更宽（读数见步态记录 ⑦ 第 6、7 条）。三条可选：策略头加有界激活 / runner 开 `clip_actions` / 动作项加 `clip`——训练语义改动，与 ② 同一批决定。② **奖励侧载体**：加回 `feet_slide`/`foot_clearance` 是记录 ⑥ 点明的"仍未答"，但 `rl_exp/versions/lizard2/main/` 下只有 `v1`，没有承接版本 ⇒ 先定载体（新 v2 配方还是 v1 的修订），再谈参数。
close_when: ① 三条做法里定一条（含"本版不动接口"这一选）并留一次读数说明越界是否消失；② 载体定下且改动落在该版本参数上。两件齐即具备关闭条件；任一件被明示不做须写下理由并移出本项——留着不说等于没关。lf 那条已在 2026-09-23 撤回（步态记录 ⑧），不再挂在本项。
depends_on: floor-contact-attribution
evidence: acceptance/records/2026-09-23-lizard2-v1-gait-skate.md, acceptance/records/2026-09-23-lizard2-leg-chains-not-mirrored.md, acceptance/records/2026-09-23-gait-probe-exit-status.md
---

## 来源与范围

六件都出自 2026-09-23 的步态补测（记录见 evidence）：读数已闭环，但这六件动作当时没做，且此前只存在于会话里。

不重开 ⑤⑥ 的读数裁定（已入记录）；不改冻结协议，协议侧缺项（`min_lift_m`、`foot_slip_mps`）归
`lizard2-family-landing` 与 `baseline-eval-pipeline-restructure`；不管探针以外的入口退出码，归
`exit-status-swallowed-by-app-close`。

## 未覆盖边界

不覆盖奖励的重新设计（本项只问"载体在哪"）；不覆盖诊断器集成（归 `floor-contact-attribution`）；
不覆盖 0–0.1 m/s 档与足端姿态（`foot_yaw_deg` 仍未算，属新观测，需要时另立）。
