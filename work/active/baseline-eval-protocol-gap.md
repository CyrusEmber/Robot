---
id: baseline-eval-protocol-gap
title: 固定窗口验收口径漏判"拖颈蹭行"（v2 判 pass，口径待拍板）
scope: ablation_harness, rl_exp/tools/verify
status: in_progress
landing: ablation_harness/protocols/baseline_flat_v2.json, ablation_harness/baseline_metrics.py, rl_exp/tools/diagnose/diag_metrics.py, rl_exp/tools/verify/baseline_probe.py, rl_exp/versions/lizard/baseline/v1/NOTES.md
next: ① 拍板口径：把验收门槛改读**探针原口径**（逐 body 全窗时均 > 1 N 即红；非足网格逐帧 > 0），还是保留现有（≥10% 体重连续 0.5 s、> −0.01 m）——两侧证据已在验收记录里（正常样本 0 N/+0.54 m 通过；异常样本 87.2 N/−4.6 mm、随机策略 −7.7 mm 判红）；② 按拍板结果改协议并**重判同一份 `eval.frames.pt`**（不重跑物理）；③ 据此改判 `rl_exp/versions/lizard/baseline/v1/NOTES.md` 的结论与结果表，并把旧报告标为被取代（保留原义）
close_when: 执行者观察到 v2（或其后继协议）报告把该策略判 fail，且失败项指向非足承重与网格入地；同时 v1 三条门槛仍全对（用同一份记录复判即可）。**判 pass 不算关闭**：那说明口径或采集有误，先修口径，不得放宽门槛
depends_on: eval-protocol-before-training
evidence: acceptance/records/2026-09-21-baseline-eval-measurement-contract.md
---

## 问题与本次范围

v1 只读前向速度与存活，于是"用脖子蹭地承重、后脚几乎不落地"的策略三条门槛全过。v2 增加了姿态、
非足承重、网格入地三条判据，并把量提到 `diag_metrics` 供探针与验收器共用。**不改奖励、不重训、不改资产。**

## 当前状态

仿真内报告已产出（`ablation_harness/results/baseline_flat_v2/collector-check/`），结论是
**v2 判 pass**——按本项 `close_when` 的规则，这不是关闭条件，而是"口径有误"的证据。原因已量化：
`neck_pitch` 全窗时均 87.2 N（体重 12.3%）、66.2% 的帧超 10% 体重，但**最长连续超阈 0.22 s**，
败给 0.5 s 持续判据；网格 −4.63 mm 在 −0.01 m 允许值之内。这两条门槛均**弱于开训前探针的口径**
（探针：任一非足 body 时均 > 1 N 即红；网格逐帧 > 0）——探针口径下本策略两侧都红。
采集侧已被独立复核（同一记录对 v1/v2 两协议复判、量与诊断器一致），所以现在缺的是**拍板**，不是数据。

## 未覆盖边界

阈值本身要有独立依据与正常／异常样本验证（本项只把两侧样本摆出来，不自行改阈值）；
脚 duty 等仍只作诊断；单 seed、单资产。v1 及其历史记录保持原义，不与 v2 混表。
