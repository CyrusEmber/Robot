---
id: v5-terrain-eyeball-question
title: v5 开训前 GUI 目视与 preflight 难度的矛盾（已由 SIR 地形课程回应）
scope: rl_exp/versions/lizard/main/v5, rl_exp/tasks/param_grid_terrain.py
status: done
landing: rl_exp/tasks/param_grid_terrain.py, rl_exp/tasks/teacher_mdp.py, rl_exp/versions/lizard/main/v5/PLAN.md
outcome: 矛盾已归因、并由地形课程直接回应：PLAY 非课程模式按 `U(0,1)` 采样难度 ⇒ 目视 tile 大概率落在低难度，而训练侧按行爬坡 + 出生 level 0，前期平缓属设计内；v5.3 起由 SIR 地形课程按真实成败在固定网格上再分配流量 ⇒ `Curriculum/terrain_levels` 的判读语义反转（带内集中或爬升 = 课程在起作用）。**标准 re-check 触发保留**：只有长期贴地不动才需复核碎石参数
evidence: rl_exp/versions/lizard/main/v5/NOTES.md
---

## 标准 re-check 触发（保留）

判据不是"看一眼 tile 像不像碎石堆"，而是课程读数：`Curriculum/terrain_levels` 长期贴地不动 ⇒ 才回到碎石参数本身复核（是否过不去、是否退化）。带内集中或爬升都算课程在起作用，不构成复检理由。

## 未覆盖边界

本项只回答"目视 tile 与 preflight 数字为何矛盾、由谁回应"，不含 v5 的配方变更（归 `main/v5/PLAN.md`）与碎石参数的取值范围（归地形生成器与 `main_params.yaml`）。
