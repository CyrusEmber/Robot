---
id: gate-hit-history
title: 离线闸门命中史统计
scope: rl_exp/tools/verify
status: done
landing: rl_exp/tools/verify/OFFLINE_CHECKS.md
close_when: 独立审核者复核统计口径、样本和证据，确认结论及边界。
outcome: 固定基线命中调查经独立重审通过，未知不作零命中或退役依据。
depends_on: rl_exp/tools/verify/offline_suite.py
evidence: acceptance/records/2026-10-30-gate-hit-history, acceptance/records/2026-10-30-gate-hit-history-review, acceptance/records/2026-10-30-gate-hit-history-second-review, acceptance/records/2026-10-30-gate-hit-history-final-review
---

## 当前范围

历史调查经独立重审通过；调查、历次审核及局限见 `evidence`。

## 关闭条件

- 独立审核者对照套件、所选历史范围及原始证据抽查统计；定义、方法和复读入口清楚。
- 区分真实问题、人工注入反例及未知；记录缺失和结论的适用边界，不以未观察到命中作为删除依据。
- 若需后续持续统计或治理动作，另立活跃事项；通过审核后关闭，可修缺口退 `in_progress`，仅用户能解决的缺口置 `blocked`。
