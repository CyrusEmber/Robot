---
id: baseline-v3-new-skeleton
title: baseline v3 —— 新骨骼（髋前伸轴落位）+ v1 配方（去掉 v2 三项约束）
scope: rl_exp/blender, rl_exp/tasks, rl_exp/versions/lizard/baseline, rl_exp/tools/verify
status: superseded
superseded_by: lizard2-family-landing
landing: rl_exp/blender/generate_urdf.py, rl_exp/blender/build_rig.py, rl_exp/tasks/baseline_recipe.py, rl_exp/versions/lizard/baseline, rl_exp/tools/verify/check_joint_layout.py, rl_exp/versions/lizard/FAMILY.md
outcome: 换代已按用户决定执行，但落点不是 baseline 线的 v3，而是**新家族 lizard2** —— 给每条腿加一条髋枢轴关节属于"机器人构型变更"，按 `.codemaker/rules/versioning.mdc` §A 的越级条款必须换家族，不能作为 vN+1 塞进现有家族。该家族已落到"可建 env + 过资产/注册/锁三级闸门"（离线套件 45/47），余项与其三项分项评估（关节功能 / 动作维数 / 旧策略兼容）都由 `lizard2-family-landing` 承接，证据见 `acceptance/records/2026-09-22-lizard2-family-landing.md`。
---

## 问题与本次范围

本项记录的决定是：**换代骨骼 + 用 v1 配方**（新骨骼跑旧配方，去掉 v2 的命令区间以外的约束按 v1 原样）。
它已兑现，落点与理由见 `outcome`；本项不再持有任何未完成动作。

## 当前状态

已关闭（superseded）。现行工作在 `lizard2-family-landing`；换代的测量依据记在
`acceptance/records/2026-09-21-lizard-leg-axis-kinematics.md`。

## 未覆盖边界

本项不含新家族的落成细节与余项（归 `lizard2-family-landing`），也不含旧家族的资产/锁维护（必须零漂移）。
