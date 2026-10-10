---
id: runtime-acceptance-v3
title: 运行时验收的跨协议判定与证据勘误（HARNESS 挂账 #1）
scope: ablation_harness
status: done
landing: ablation_harness/eval.py, ablation_harness/protocols/locomotion_eval_v3.yaml, ablation_harness/results
close_when: 两条都跑完并观测：① 同一 ckpt 在 v2/v3 各一次（各臂另重跑一次作可复现性对照）—— 落在 ±0.02 内即记录并接受，超出则记差异清单并判断是哪一侧的口径问题；② 有 ckpt 的 run 完成后看 9 列 completion —— 有分布即成立。读数与判定进 acceptance/records，本项只留指针
evidence: acceptance/records/2026-10-10-cross-protocol-suite-readings.md, acceptance/records/2026-10-10-runtime-acceptance-v3-review.md
outcome: 关闭于 2026-10-10，走**用户拍板**的"降级判据"路线 —— 这是关闭范围变更，不是复审通过：独立审核判退回后，用户对"只有用户能解"的那一半直接裁决，① 的原 ±0.02 判据作废（摘要相同的列仍超差，且各臂重跑逐字相同 ⇒ 它是"几何相同即同读数"的假设，不是噪声带），该条改为"跨协议读数只作测量差异诊断，不得作策略排名，也不得作旧行仍可比的依据"；② 按原范围成立（有 ckpt 的 run 九列 completion 非零且取值各异；记录只到逐列 env 均值，未证逐 env 分布）。读数、超差清单、勘误与复读命令归两条记录，本项不复述
---

## 当前状态

已收。两条都真跑过（同一 ckpt 跨 v2/v3、各臂另重跑一次），独立审核判**退回**，其后由用户拍板把 ① 降级为口径诊断并以变更后的范围关闭；审核的具体判定、证据边界与本次处置只在那条审核记录里。

## 未覆盖边界

- **对账对象只取本家族行**：`lizard/main`、`lizard/baseline`、`lizard/parkour` 在 `rl_exp/versions/lines.json` 里均为 `retired`，
  退休 = 退出维护与复现承诺；其 task id 已随 `work/closed/2026/retired-family-code-prune.md` 注销 ⇒ 那些 ckpt 跑不出 v3 行，也**不得与 v3 行同表**。
- **本项不定成绩**：`locomotion_eval_*` 的 9 列里只有 `flat` 对平地训练家族是成绩面，其余 8 列是 OOD 探针
  （列角色见 `ablation_harness/HARNESS.md`）。本项测的是协议与套件的行为，不是策略强弱。
- **跨列耦合机制不在本项**：本项只观测到"改套件会污染摘要未变的列"，机制候选与单变量探针归 `work/active/eval-column-coupling.md`。
- 本项不含 ④b 之外的地形几何工作（已收，见 `work/closed/2026/`），也不含记录格式的真跑段（当时另立事项 `record-format-live-checks`，2026-10-10 关闭 ⇒ 现于 `work/closed/2026/record-format-live-checks.md`）。
