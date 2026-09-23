---
id: baseline-eval-protocol-gap
title: 验收侧对训练 v2 的支持与口径（协议 v3）
scope: ablation_harness, rl_exp/tools/verify, rl_exp/versions/lizard/baseline
status: in_progress
landing: ablation_harness/protocols/baseline_flat_v3.json, ablation_harness/baseline_eval.py, ablation_harness/baseline_metrics.py, rl_exp/versions/lizard/baseline/v2/PLAN.md, rl_exp/versions/lizard/baseline/v1/NOTES.md
next: ① v2 首跑后按 v3 出报告（`--task ...-Play-v2 --protocol baseline_flat_v3.json`），确认 `verdict` 属于 `pass`/`fail` 且两条相对门槛与接触轴各有区分度（不是全绿也不是全红）；② 据此回填 `baseline/v2/NOTES.md` 并改判 `baseline/v1/NOTES.md` 的结论与结果表（v1 记录保持原义、不重打标签）；③ 若 0.2 / 0.8 这两个本版新定阈值在首跑上无区分度 ⇒ 回到"独立依据 + 正常/异常样本"再定，不得按首跑结果平移
close_when: 执行者观察到 v2 首跑的报告：`verdict ∈ {pass, fail}`，每条门槛都有"能过"与"能红"两侧证据，并已回填 v2 NOTES、改判 v1 NOTES 的旧结论。仅"能跑出报告"不结项；"把旧 v1 拖颈样本判红"**也不是**结项条件——它是异常回归样本，不设定阈值
evidence: acceptance/records/2026-09-21-baseline-eval-v2-support-and-protocol-v3.md
---

## 问题与本次范围

v1 只读前向速度与存活 ⇒ 拖颈蹭行的策略三条门槛全过；v2 协议补了姿态/承重/网格三条，却**判不了它要判的那版**：
入口拒绝 `params_version != "v1"`、采集要求命令恒为 0.5 m/s、判定只有绝对门槛与固定 8 m 位移。于是
"v2 协议判 v1 策略"看起来像结论，其实是两件无关的事拼在一起（事实更正见验收记录）。

本项把验收侧补齐到能判训练 v2：协议按 `recipe_version` 绑定配方、命令按 box 采集与校验（逐帧记录实际
下发命令）、跟踪与位移改**相对口径**、头链轴改成与**训练终止同判据**的接触判据、非足网格降为诊断。
阈值只许来自"仓库先例 + 本版新定 + 两侧样本验证"，**不许由"让某个旧样本变红"反推**。

## 当前状态

协议 `baseline_flat_v3.json`、`--protocol` 入参与 recipe 绑定、命令 box 采集/校验、两条相对门槛、接触轴与
网格降级均已落地并通过闸门（离线套件 47/47；本轮新增 7 条回归）。真跑已证明**管路通**：
`Lizard-Baseline-Flat-Play-v2`（零动作）跑完，22 维动作、命令区间采样（均值 2.088）、期望位移 41.76 m、
两条相对门槛按预期判红、接触轴绿、`verdict = smoke_only`、报告与记录落盘 ⇒ **但这不是 v2 的性能结论**。

v1 那份记录不能在 v3 下复判（命令 0.5 落在 1–3 box 之外 ⇒ `invalid`）：接触轴的回归是合成记录，v1 记录
本身仍只在 v1/v2 口径下有判定。当前缺的是 v2 首跑，见 `next`。

## 未覆盖边界

不覆盖奖励与训练侧终止实现（归 `baseline-v2-recipe`）；不覆盖启动闸门（归 `eval-protocol-before-training`）；
脚 duty 等仍只作诊断；单资产、单 seed。
