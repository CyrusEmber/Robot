---
id: distillation-export-checks
title: Step 3.4 蒸馏与导出校验（登记项，非排期承诺）
scope: rl_exp/tasks, rl_exp/tools/runrecord
status: blocked
landing: rl_exp/tasks/teacher_networks.py, rl_exp/tasks/student_networks.py
next: **登记项，本轮不执行**：① 导出前协议校验（`teacher_networks.py` 的 flat 与分段两条路径、ONNX/JIT 导出路径）；② 蒸馏数据 manifest 与分片哈希（Phase 2 建）。在本轮一切验收里 P05/P06/P07 标"未执行"，**不得**读成通过。**挡在排期**：由 Phase 2 的排期人（用户）决定何时做；**已知敞口**：冻结 yaml 的 `obs_layout` 写 `joint_pos_rel` 而代码 term 是 `joint_pos`，它是 UE 侧契约，本轮不动导出
close_when: 用户给出排期后，执行者跑 ①② 并观察：① flat 与分段两条路径各出一次明确的导出前协议判定（通过 / 不过各有判词）；② manifest 与分片摘要能独立重算并与 manifest 一致 ⇒ 两条成立即关；任一条未跑 ⇒ 保持 blocked 并写明仍挡在排期。读数归 `ACCEPTANCE.md`，不进本项
---

## 当前状态

Step 3.4 的两件校验被**登记**而非排期：导出前协议校验与蒸馏数据 manifest/分片哈希都还没做，本轮交付里它们的位置是"未执行"标记，不是通过项。

## 为什么它是 blocked 而不是 open

它不是"已知要做、只差动手"：连"本轮做不做"都还没定，挡的是一个**排期决定**（Phase 2 的排期人 = 用户）。写成 open 会让人以为随时可以开工，进而把"未执行"读成"已复核"。

## 未覆盖边界

`obs_layout` 那条敞口（冻结 yaml 与代码 term 不同形）属 UE 侧契约，本项只登记、不修；导出契约的其它面（快照外置、`--variant` 声明）归 `record-variant-and-snapshot-specs`。
