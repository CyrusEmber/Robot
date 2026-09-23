---
id: asset-leg-axis-capability-mismatch
title: 名义 stride 轴装在股骨远端（膝部偏航扫板，非髋前伸）
scope: rl_exp/blender, rl_exp/tools/verify, rl_exp/versions/lizard
status: done
landing: rl_exp/versions/lizard/FAMILY.md, rl_exp/tools/verify/check_joint_layout.py, rl_exp/docs/pitfalls.md, rl_exp/blender/generate_urdf.py, rl_exp/blender/build_rig.py, rl_exp/tools/verify/check_contact_ownership.py
close_when: (b) 分支已发生（组合扫描给出足够行程 ⇒ 能力结论已撤回，记录只留较窄事实）；(c) 换代已决定并落成 —— 决定、分项评估与余项都在 `work/active/lizard2-family-landing.md`。剩余：① 碰撞归属在 USD 侧与运行时各有结论。
depends_on: baseline-v2-recipe
evidence: acceptance/records/2026-09-21-lizard-leg-axis-kinematics, acceptance/records/2026-09-23-leg-collision-authorship
outcome: 关闭于 2026-09-23，两项余数各有结论。① 碰撞归属两侧都已读（见 evidence 第二条）：USD 侧与 URDF 侧逐 body bbox 一致、approximation 全为 convexHull；胫骨几何所属 `*_hfe`、股骨挂在 `*_haa` 且不在罚项名单内（v1 PLAN 写作"大腿/小腿"）；`.*_kfe` 两代资产都没有碰撞体 ⇒ 罚项名单一半是恒 0 死条目；运行时稳态站立只有四脚承重（旧线 643/949/1077/3778 N），漏罚那条在站姿下不触发。**新家族的碰撞归属与旧资产逐比特相同**：换骨骼没有动碰撞作者身份，改与不改归资产线。② v5.6 的提交意图仓内已有答案（`rl_exp/blender/rotate_rig.py:1-7`：修的是 "URDF long axis was Y while the velocity task commands/reward assume base +X is forward"）⇒ 当年被认成**朝向**问题，不是能力轴问题；当时的位移读数属退役线历史，未复读。③ 机制落成：`check_joint_layout.py` 覆盖轴位（力臂）/ 轴向（FK 极性）/ 四腿全覆盖（`leg_probes` 按资产推导）/ 承重姿态组合扫描；`check_contact_ownership.py` 补第四件——碰撞体归属与罚项可见性，自带三条断言（死条目 / 接触体无人罚 / 空测量）。
---

## 问题与本次范围

腿链能推的方向与任务命令轴相差 90°：观测与实测见 `evidence` 那条记录，事实落点见 `FAMILY.md`
§机械链与轴向实测与 `docs/pitfalls.md` P009。要固定的是机制——流程检查必须**同时**覆盖轴的位置、轴的
方向、驱动的几何、以及工作姿态下的运动；现在只有"轴的方向"有表，另三者无人校验，缺陷才活到今天。
不含训练配方改动，也不代替 v2 验收侧的工作。

## 当前状态

记录已落；组合扫描已做（`check_joint_layout.py` 的组合段，自带自检：中格必须复现刚量到的稳态），其结论已按
(b) 分支回写记录与 `FAMILY.md`。**换代已执行**：按 §A 越级条款落成**新家族 `lizard2`**（不是旧家族的 v3），
在办余项见 `lizard2-family-landing`。本项的两项余数 2026-09-23 各有结论，见 `outcome`。

## 未覆盖边界

不含 v2 的奖励/终止/验收口径（归 `baseline-v2-recipe` 与评测侧）；结论边界见记录，此处不重复。
