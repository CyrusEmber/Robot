---
id: baseline-eval-protocol-gap
title: 验收侧对训练 v2 的支持与口径（协议 v3）
scope: ablation_harness, rl_exp/tools/verify, rl_exp/versions/lizard/baseline
status: done
landing: ablation_harness/protocols/baseline_flat_v3.json, ablation_harness/baseline_eval.py, ablation_harness/baseline_metrics.py, rl_exp/versions/lizard/baseline/v2/PLAN.md, rl_exp/versions/lizard/baseline/v2/NOTES.md, rl_exp/versions/lizard/baseline/v1/NOTES.md, rl_exp/tools/verify/test_baseline_contract.py
close_when: 执行者观察到 v2 首跑的报告：`verdict ∈ {pass, fail}`，每条门槛都有"能过"与"能红"两侧证据，并已回填 v2 NOTES、改判 v1 NOTES 的旧结论。仅"能跑出报告"不结项；"把旧 v1 拖颈样本判红"**也不是**结项条件——它是异常回归样本，不设定阈值
evidence: acceptance/records/2026-09-21-baseline-eval-v2-support-and-protocol-v3, acceptance/records/2026-09-23-baseline-v2-first-run
outcome: v2 首跑按 v3 判定：`verdict: pass`、五轴全过（16 env、seed 123、确定性），报告落 `results/baseline_flat_v3/v2-trained-9999-rerun/`，与磁盘上 2026-09-22 同一 rollout 的旧采集器报告**逐位相同**。区分度：两条相对门槛有**样本级**两侧证据（同一命令 box 的零动作两条都红、随机 ckpt 判 `fail`、训练 9999 iter 两条都绿），接触轴绿侧真跑取到、红侧是合成回归；**存活与姿态在真跑样本里只有绿侧**，本轮把红侧补在判据级（`test_baseline_contract.py::test_v3_the_two_axes_no_sample_ever_exercised_can_still_fail`；补之前这两条 gate 全仓没有一条断言）。已回填 `baseline/v2/NOTES.md`（结果表按"路径 + 复读命令 + 一句判定"）并在 `baseline/v1/NOTES.md` 补口径声明：v1 的"能"只属 v1 协议，v3 下那份记录 `invalid`，不改其原义。**未做**：`baseline_probe.py` 的 v2 接口复测（三条新断言）没跑，归 `baseline-v2-recipe`；v2 训练侧记录半截（checkpoint 无 rev 锚），归 `baseline-pre-make-record-check`。
---

## 问题与本次范围

v1 只读前向速度与存活 ⇒ 拖颈蹭行的策略三条门槛全过；v2 协议补了姿态/承重/网格三条，却**判不了它要判的那版**：
入口拒绝 `params_version != "v1"`、采集要求命令恒为 0.5 m/s、判定只有绝对门槛与固定 8 m 位移。于是
"v2 协议判 v1 策略"看起来像结论，其实是两件无关的事拼在一起（事实更正见验收记录）。

本项把验收侧补齐到能判训练 v2：协议按 `recipe_version` 绑定配方、命令按 box 采集与校验（逐帧记录实际
下发命令）、跟踪与位移改**相对口径**、头链轴改成与**训练终止同判据**的接触判据、非足网格降为诊断。
阈值只许来自"仓库先例 + 本版新定 + 两侧样本验证"，**不许由"让某个旧样本变红"反推**。

## 当前状态（关闭时）

协议 `baseline_flat_v3.json`、`--protocol` 入参与 recipe 绑定、命令 box 采集/校验、两条相对门槛、接触轴与
网格降级均已落地并通过闸门。真跑两阶段：先零动作证明**管路通**（`smoke_only`），再训练 9999 iter 的
checkpoint **首跑判定**（`pass`；逐轴读数、两侧样本与两处缺口见
`acceptance/records/2026-09-23-baseline-v2-first-run.md`）。

v1 那份记录不能在 v3 下复判（命令 0.5 落在 1–3 box 之外 ⇒ `invalid`）：接触轴的回归是合成记录，v1 记录
本身仍只在 v1/v2 口径下有判定，其原义不变，已在 `baseline/v1/NOTES.md` 写明。

## 未覆盖边界

不覆盖奖励与训练侧终止实现（归 `baseline-v2-recipe`）；不覆盖启动闸门（归 `eval-protocol-before-training`）；
脚 duty 等仍只作诊断；单资产、单 seed。**存活/姿态的红侧只有判据级**（真跑样本两条都是绿）；
0.2 / 0.8 两个本版新定阈值的**取值**是否最优不在本项判据内（本项只验证区分度）。
