---
id: floor-contact-attribution
title: 地面接触归属：谁在滑、谁在牵引、穿透容忍度
scope: rl_exp/tools/diagnose, rl_exp/assets
status: open
landing: rl_exp/tools/diagnose/diagnose_support.py, rl_exp/tools/diagnose/diag_metrics.py, ablation_harness/protocols/baseline_flat_v2.json
next: ① **已交付 2026-09-23（诊断侧）**：接触点切向速度 `v_com + ω × r` 落在 `diag_metrics.contact_point_velocity`，`r` 取最深网格顶点且已标 `ponytail:` 上限，配套 `mesh_lowest_point`（`mesh_min_z` 改为复用它）；口径以 **COM** 为参考点——框架 `body_lin_vel_w` 是 `body_com_lin_vel_w` 的别名，与 `body_pos_w` 混用会把 `ω × r` 算错。读数见 `acceptance/records/2026-09-23-lizard2-v1-gait-skate` 的 ⑤。余下：诊断器（`diagnose_support.py`）与验收器复用同一函数，不得各写一份；② 用带 `filter_prim_paths_expr` 的传感器（`force_matrix_w`）把**与地面的接触**和**自碰撞**分开——`net_forces_w` 是该 body 全部接触的合力，配方 `baseline_recipe.py:146` 未声明 filter 且不能加（会动冻结的 cfg 摘要）⇒ 在诊断器自建 cfg 里建；③ 用切向力**方向**区分"牵引"与"被拖着走"：颈 82–90 N 只说明它受力，不说明它在提供前向牵引；④ 穿透容忍度：先做受控对照（时间步 / 求解迭代 / 接触参数），再拍板；⑤ **已交付 2026-09-28（诊断侧）**：脚掌**贴地面积**与**姿态**——`diag_metrics.mesh_triangles` / `sole_area_m2` / `clip_area_below_z`（精确三角面裁剪）/ `ground_contact_area_m2`（带内与带下分开、下缘严格）/ `body_down_in_link`，驱动 `gait_probe.py` 的 `--sole_band_mm` / `--sole_eps_mm` 与 `sole_*` 读数。读数见同记录的 ⑪：每只脚只贴到自身上限的 0.3%–7.5%、翘 13–25° ⇒ "脚边承重"成立；新事实：`rl` 脚碰撞网格与另三只**不同形**（平板 vs 穹面，cap 0.119 vs 0.013 m²）——**⚠️ 已由同日资产修复改写：`rl` 修为 `rr` 的 y 镜像（cap 0.013352，与另三只同形），修复与"家族资产隔离"一起验收并归档在 `acceptance/records/2026-09-28-lizard2-foot-hull-and-asset-isolation.md`；⑪ 那条读数属**修前**状态，引用前先看记录 ⑫ 的"资产前提"节**。**这条不与②③④抢顺序，但它给的下一步是相关而不是因果**：把"占上限低"与已测的滑移/净空做同口径相关读数，再决定要不要把它变成奖励项；⑥ **已交付 2026-09-28（诊断侧）**：脚板关节**承重期用了多少力**——重构力矩 `Kp(q*−q) − Kd q̇` 的稳态中位/最大值、**逐关节按自身** `effort_limit` 归一的占比与饱和帧占比、承重期命令偏离零位幅度，落在 `gait_probe.py` 的 `*_foot_joint` 读数（口径自检含手算饱和例，已抓过一处逐关节上限被覆盖的真错）。读数见同记录 ⑫。**它证的是"机制真实存在且处于饱和工作点"，不是因果**：饱和最重的脚不是稳态滑移最坏的脚 ⇒ "降足部力量"与"固定脚板目标"两项试验的**判据形状**（脚选择性、大扰动且拿掉一个饱和执行器）写在 ⑫ 末节，做不做由这条链的下一次决定；本节不复制数值。
close_when: (a) 报告给出逐接触 body 的接触点切向速度、摩擦利用率与切向力方向，且结论与位移、逐脚 duty 自洽；(b) 穿透容忍度有一句明确决定，且该决定引用受控对照的读数——不得以"实测 5 mm"直接当作"允许 5 mm"。两项齐了才关
evidence: acceptance/records/2026-09-21-baseline-eval-measurement-contract.md, acceptance/records/2026-09-23-lizard2-v1-gait-skate.md
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
