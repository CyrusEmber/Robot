---
id: baseline-eval-protocol-gap
title: baseline 固定窗口验收口径漏判"拖颈行走"（协议 v2 + 开训前/验收共用量表）
scope: ablation_harness, rl_exp/tools/diagnose, rl_exp/tools/verify, rl_exp/versions/lizard/baseline
status: in_progress
landing: ablation_harness/protocols/baseline_flat_v2.json, ablation_harness/baseline_metrics.py, ablation_harness/baseline_eval.py, rl_exp/tools/diagnose/diag_metrics.py, rl_exp/tools/verify/baseline_probe.py, rl_exp/tools/verify/test_baseline_contract.py
next: ① 重跑 v2 固定窗口（同一 ckpt / seed / 64 env，输出到 `ablation_harness/results/baseline_flat_v2/`），确认它判 fail 且失败项指向非足承重与网格入地（上次运行写盘前被中断，需先确认能产出报告）；② 按结果改判 `rl_exp/versions/lizard/baseline/v1/NOTES.md` 的结论与结果表，并把 v1 报告标为被取代（保留原义，不重打标签）；③ 跑整离线套件（当前 47 项 + 本项新增回归）确认无红
close_when: 执行者做完 ①② 后观察 v2 报告：三条 v1 门槛仍全对、且 `no_non_foot_carrier` 与 `no_mesh_through_floor` 为 false ⇒ 结论改为"该策略未学会行走（拖颈蹭行）"，本项关闭，证据指向 `acceptance/records/2026-09-20-baseline-flat-eval-protocol.md`；若 v2 反而判 pass（例如承重未超阈值）⇒ 说明阈值或采集有误，本项保持 open 并先修采集，不得放宽门槛
depends_on: eval-protocol-before-training
evidence: acceptance/records/2026-09-20-baseline-flat-eval-protocol.md
---

## 问题与本次范围

v1 协议只读前向速度与存活，于是"用脖子承重、后脚几乎不落地"的蹭行策略三条门槛全过（原始读数见证据记录）。
本项修的是**判据与量表**：v2 协议增加几何 fall、非足承重、碰撞网格入地，并把这些量提到
`diag_metrics` 让开训前探针与验收器读同一份函数。**不改奖励、不重训、不改资产**——策略行为是否划算
由后续轮次决定，本项只保证"验收不会再漏掉它"。

## 当前状态

协议 v2、量表、验收器采集、探针改写、离线回归均已落地并通过；开训前探针在同一资产上仍全 ok。
差的是**仿真内生成的 v2 报告**与据此的结论改判。

## 未覆盖边界

阈值全部取自仓库先例，未做适用性标定（tilt 40° 对"低头不倒"的姿态偏宽）；脚 duty / `feet_down` /
脚载荷份额只作诊断不设门槛（步态口径无先例）；单 seed、单 ckpt。协议 v1 及其历史记录保持原义，
不与 v2 混表。
