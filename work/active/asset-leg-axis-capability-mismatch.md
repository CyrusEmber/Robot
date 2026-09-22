---
id: asset-leg-axis-capability-mismatch
title: 名义 stride 轴装在股骨远端（膝部偏航扫板，非髋前伸）
scope: rl_exp/blender, rl_exp/tools/verify, rl_exp/versions/lizard
status: open
landing: rl_exp/versions/lizard/FAMILY.md, rl_exp/tools/verify/check_joint_layout.py, rl_exp/docs/pitfalls.md, rl_exp/blender/generate_urdf.py, rl_exp/blender/build_rig.py
next: ① 核对四腿碰撞形状、胫骨实际所属 body、以及 `undesired_contacts` 实际选中的 body（URDF 侧已查；USD 侧碰撞形状与运行时接触归属未验）；② 查 v5.6 整机 Rz(−90°) 的提交意图与 v5 首跑位移读数，判当年那次错配被认成朝向还是能力轴
close_when: (b) 分支已发生（组合扫描给出足够行程 ⇒ 能力结论已撤回，记录只留较窄事实）；(c) 换代已决定并落成 —— 决定、分项评估与余项都在 `work/active/lizard2-family-landing.md`。剩余：① 碰撞归属在 USD 侧与运行时各有结论。
depends_on: baseline-v2-recipe
evidence: acceptance/records/2026-09-21-lizard-leg-axis-kinematics
---

## 问题与本次范围

腿链能推的方向与任务命令轴相差 90°：观测与实测见 `evidence` 那条记录，事实落点见 `FAMILY.md`
§机械链与轴向实测与 `docs/pitfalls.md` P009。要固定的是机制——流程检查必须**同时**覆盖轴的位置、轴的
方向、驱动的几何、以及工作姿态下的运动；现在只有"轴的方向"有表，另三者无人校验，缺陷才活到今天。
不含训练配方改动，也不代替 v2 验收侧的工作。

## 当前状态

记录已落；组合扫描已做（`check_joint_layout.py` 的组合段，自带自检：中格必须复现刚量到的稳态），其结论已按
(b) 分支回写记录与 `FAMILY.md`。**换代已执行**：按 §A 越级条款落成**新家族 `lizard2`**（不是旧家族的 v3），
在办余项见 `lizard2-family-landing`。本项剩下：USD 侧碰撞形状与运行时接触归属、v5.6 提交意图。

## 未覆盖边界

不含 v2 的奖励/终止/验收口径（归 `baseline-v2-recipe` 与评测侧）；结论边界见记录，此处不重复。
