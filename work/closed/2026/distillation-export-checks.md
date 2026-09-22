---
id: distillation-export-checks
title: Step 3.4 蒸馏与导出校验（**已取消**：当前不做蒸馏）
scope: rl_exp/tasks, rl_exp/tools/runrecord
status: cancelled
landing: rl_exp/tasks/teacher_networks.py, rl_exp/tasks/student_networks.py
outcome: 用户 2026-09-22 裁决**取消**——当前不做蒸馏，Step 3.4 的两件校验（①导出前协议校验 ②蒸馏数据 manifest 与分片哈希）随之不作要求，两件**从未执行**（无读数：P05/P06/P07 保持"未执行/未知"，不得读成通过）。登记源 ARCH_PLAN 的 Step 3.4 行已标注取消。若日后重启蒸馏，从本项恢复：核对时已查清三条前置事实——(a) ① 的真前置是 **export runtime** 而非 Phase 2 排期（P05/P06 判的是导出件与原件逐元素一致，随机权重即可，不需要 teacher checkpoint 或数据）；本机 torch 2.10 在、`onnxruntime` **未装** ⇒ ONNX 半条当前按 P05 只能记未知；(b) P06 的"循环模型 128 步 + reset mask"针对的是**学生 GRU**（`student_networks.py` 2×50、hidden `[2,N,50]`），教师是 split-encoder MLP ⇒ 教师侧 P06 记"不适用"，而学生侧**尚无导出面**（无 `as_jit`/`as_onnx`），要验 P06 先得做那个面；(c) 命名敞口（冻结 yaml 与 UE 侧写 `joint_pos_rel`、代码 term 名是 `joint_pos`）决定导出件吃哪一列 ⇒ 属 P05 的样本对齐语义，重启时先把它定成判据。
---

## 问题与本次范围

Step 3.4（`ARCH_PLAN.md`）把"导出前协议校验"与"蒸馏数据 manifest/分片哈希"登记为待做，配套判据是 P05/P06/P07。
本项是那条登记，`blocked` 挡在排期决定上。2026-09-22 用户裁决取消。

## 为什么取消而不是继续挂账

登记项的价值是"别把未执行读成通过"；既然**整个蒸馏方向当前不做**，继续挂一条 `blocked` 只会让在办清单里多一个永不动的动作。
取消的语义（本仓口径）：**没做完的动作随之不作要求**，而不是"已复核"——P05/P06/P07 仍是"未执行/未知"。

## 未覆盖边界

`obs_layout` 那条命名敞口属 **UE 侧契约**，本项只登记、不修（它仍写在 `ARCH_PLAN.md` 的 Step 3.4 行里）；
导出契约的其它面（快照外置、`--variant` 声明）归 `work/active/record-variant-and-snapshot-specs.md`，本项不动。
