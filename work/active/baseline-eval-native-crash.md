---
id: baseline-eval-native-crash
title: 固定窗口验收器在仿真内原生崩溃（第一帧被消费之后）
scope: ablation_harness, rl_exp/tools/verify
status: open
landing: ablation_harness/baseline_eval.py, ablation_harness/baseline_metrics.py
next: ① 把 `window.add(...)` 换成空操作、只跑 `wrapper.step`，分开"两帧 step"与"一帧 add"；② 若落在收集器，逐项喂（先 `pos/yaw/velocity_yaw`，再加 tilt、载荷、网格）找触发项；③ 反向验证：同一批字段走 `diagnose_support` 的录像路径（它跑得通）确认量本身没问题；④ 修好，或把累加路径换成跑得通的那套
close_when: 执行者跑完整 20 s 窗口——进程正常退出且落盘 `eval.json`，`verdict`/`gates`/`diagnostics` 齐全（v1 与 v2 协议各一次）。修不动则保持 open，并记录"改用诊断器录像路径"的决定与代价（固定窗口将不再由单一工具产出）
depends_on: baseline-eval-protocol-gap
evidence: acceptance/records/2026-09-20-baseline-flat-eval-protocol.md
---

## 问题与本次范围

带新采集的固定窗口跑在仿真内原生崩溃：无异常栈、进程退出、报告不落盘。已定位：`snapshot()` 八个字段
连续两次调用全过（打点法 `1 q` → `8 feet`），死在**第一帧被 `window.add` 消费之后**；同一批量在
`diagnose_support.py` 里跑得通（本轮的物理结论就是它给的）⇒ 问题在验收器的采集/累加路径，不是量不可测。
影响：`baseline_flat_v2` 下无有效报告，"v2 会判 fail"仍只有离线反证 + 诊断器读数支撑。

## 未覆盖边界

只解决"固定窗口能产出报告"，不回答 v2 应否判 fail（归 `baseline-eval-protocol-gap`）；不覆盖 v1 历史报告
（更早实现产出，与本项无关）。
