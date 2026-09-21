---
id: floor-contact-attribution
title: 地面接触归属：谁在滑、谁在牵引、穿透容忍度
scope: rl_exp/tools/diagnose, rl_exp/assets
status: open
landing: rl_exp/tools/diagnose/diagnose_support.py, rl_exp/tools/diagnose/diag_metrics.py, ablation_harness/protocols/baseline_flat_v2.json
next: ① 滑动判据换成**接触点**相对地面的切向速度（`v_body + ω × r`，body 原点速度不够——纯转动时原点为零而接触点在滑），`r` 暂取最深网格顶点并标 `ponytail:` 记上限；② 用带 `filter_prim_paths_expr` 的传感器（`force_matrix_w`）把**与地面的接触**和**自碰撞**分开——`net_forces_w` 是该 body 全部接触的合力，配方 `baseline_recipe.py:146` 未声明 filter 且不能加（会动冻结的 cfg 摘要）⇒ 在诊断器自建 cfg 里建；③ 用切向力**方向**区分"牵引"与"被拖着走"：颈 82–90 N 只说明它受力，不说明它在提供前向牵引；④ 穿透容忍度：先做受控对照（时间步 / 求解迭代 / 接触参数），再拍板
close_when: (a) 报告给出逐接触 body 的接触点切向速度、摩擦利用率与切向力方向，且结论与位移、逐脚 duty 自洽；(b) 穿透容忍度有一句明确决定，且该决定引用受控对照的读数——不得以"实测 5 mm"直接当作"允许 5 mm"。两项齐了才关
evidence: acceptance/records/2026-09-21-baseline-eval-measurement-contract.md
---

## 问题与本次范围

"头在地上划、而且确实穿插"拆成三个可分别回答的问题：**谁在滑**、**谁在牵引**、**穿透多少算允许**。

1. `|F_tang| / F_normal` **单独回答不了"谁在滑"**：它给的是摩擦预算用了多少，不是有没有相对滑动。
   滑动的定义要靠接触点切向速度；刚体原点速度不够（纯转动时原点为零、接触点在滑），需含 `ω × r`。
2. 受力方向有别：颈承重 82–90 N ≠ 颈在提供前向牵引，它也可能只是被拖着走（产生阻力）。
   三维合力已有（`net_forces_w[..., :3]`，此前只读了 z），切向分量与方向今天就能算。
3. 接触对象要分清：`net_forces_w` 汇的是该 body 的**全部**接触（含自碰撞），不区分地面。
4. `contact_offset` **不是允许穿透深度**：它控制提前生成接触的距离，由它推不出"5 mm 穿插合理"，
   也不能默认可通过调小它改善穿透。已实测的 5 mm 是求解器在有限速度下的稳态穿插，是**观测值**，
   不是验收依据；容忍度需要受控对照（时间步 / 求解迭代 / 接触参数）才能拍板。

摩擦本身已有实测（逐 shape 静/动 1.0、地面 1.0、`combine=multiply` ⇒ µ ≈ 1.0），"无摩擦滑行"不成立；
待答的是摩擦**姿态**（牵引还是刮擦）。

## 未覆盖边界

不覆盖资产改造（改 URDF/USD 或接触参数属资产线，本项只把问题与证据递过去）；不覆盖脚板被动移动
（见 `baseline-v2-recipe` 的资产不动假设）；µ 的组合方式由框架基座声明，本项不能改。
