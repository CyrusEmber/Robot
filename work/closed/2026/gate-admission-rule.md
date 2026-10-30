---
id: gate-admission-rule
title: 闸门准入判据：新闸门须绑一次真实缺陷，并区分"声明一致"与"行为成立"
scope: rl_exp/tools/verify, AGENTS.md
status: done
landing: AGENTS.md, rl_exp/tools/verify/OFFLINE_CHECKS.md
close_when: 独立审核者核对规则落点与用户选定的既有闸门扩展证据
outcome: 规则落点与既有闸门扩展经独立重审通过；首个新增条目尚未观察。
depends_on: rl_exp/tools/verify/offline_suite.py
evidence: acceptance/records/2026-10-09-repo-architecture-review, acceptance/records/2026-10-30-gate-admission-rule-evidence, acceptance/records/2026-10-30-gate-admission-rule-independent-review
---

## 当前状态

判据正文归机制；用户选择观察已有闸门扩展，独立审核通过，证据见 `evidence`。该扩展不是新增套件条目。

## 关闭条件

- 独立审核者从规则落点、提交 `3420339` 的实际差异与证据出发，核对真实来源缺陷、类别及破坏测试；辨别替身测试和真实行为的证明边界。
- 通过则关闭；证据不足退回补证。准入判定仍由人工审核，不改规则或将声明一致当作行为证据。

## 未覆盖边界

- 原条件的首条新增套件项尚未观察到；用户同意不再把该观察作为本事项关闭条件，未来新增项仍按现行准入规则审查。
- 不回溯存量条目的来源，不改 `.codemaker/rules/versioning.mdc`；准入无机器看守。命中史统计由 `work/active/gate-hit-history.md` 跟进。
