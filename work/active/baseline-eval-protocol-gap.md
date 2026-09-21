---
id: baseline-eval-protocol-gap
title: 固定窗口验收口径漏判"拖颈蹭行"
scope: ablation_harness, rl_exp/tools/verify
status: in_progress
landing: ablation_harness/protocols/baseline_flat_v2.json, ablation_harness/baseline_metrics.py, ablation_harness/baseline_eval.py, rl_exp/tools/diagnose/diag_metrics.py, rl_exp/tools/verify/baseline_probe.py, rl_exp/tools/verify/test_baseline_contract.py
next: ① 重跑 v2 固定窗口（同 ckpt/seed/64 env → `ablation_harness/results/baseline_flat_v2/`），确认判 fail 且失败项指向非足承重与网格入地（**被 `baseline-eval-native-crash` 挡住**）；② 据此改判 `rl_exp/versions/lizard/baseline/v1/NOTES.md` 的结论与结果表，并把该跑的旧报告标为被取代（保留原义）；③ 跑整离线套件确认无红
close_when: 执行者观察 v2 报告——三条 v1 门槛仍全对，而 `no_non_foot_carrier` 与 `no_mesh_through_floor` 为 false ⇒ 结论改为"该策略未学会行走（拖颈蹭行）"，本项关闭。若 v2 反而判 pass（承重未超阈）⇒ 说明阈值或采集有误，保持 open 并先修采集，不得放宽门槛
depends_on: eval-protocol-before-training
evidence: acceptance/records/2026-09-20-baseline-flat-eval-protocol.md
---

## 问题与本次范围

v1 只读前向速度与存活，于是"用脖子蹭地承重、后脚几乎不落地"的策略三条门槛全过。本项修**判据与量表**：
v2 协议增加几何 fall、非足承重、网格入地；这些量提到 `diag_metrics` 让开训前探针与验收器读同一份函数。
**不改奖励、不重训、不改资产**。两处读数口径已在 2026-09-21 修正（颈载荷 11.6–12.8% 而非 47–49%；
入地深度取顶点 −0.005 m 而非角点 −0.052 m），修正表见验收记录。

## 当前状态

协议 v2、量表、验收器采集、探针改写、离线回归均已落地并通过。差的是**仿真内生成的 v2 报告**——
采集路径原生崩溃，见 `baseline-eval-native-crash`。

## 未覆盖边界

阈值全部取自仓库先例或本版新定（几何门槛 `≥ −0.01 m` 是**按求解器稳态穿插校准**的，不是"零穿透"）；
脚 duty 等只作诊断；单 seed、单 ckpt。v1 及其历史记录保持原义，不与 v2 混表。
