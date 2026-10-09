---
id: gate-admission-rule
title: 闸门准入判据：新闸门须绑一次真实缺陷，并区分"声明一致"与"行为成立"
scope: rl_exp/tools/verify, AGENTS.md
status: blocked
landing: AGENTS.md, rl_exp/tools/verify/OFFLINE_CHECKS.md
next: 观测首条新增套件项是否按判据登记来源缺陷与类别（本身无动作；解除者 = 下一次加检查的人）
close_when: 用户裁决——(a) 采纳：`AGENTS.md` 与 `OFFLINE_CHECKS.md` 能读到准入判据，且此后第一条新增套件项按它填写了来源缺陷 ⇒ done；(b) 否决 ⇒ cancelled 写理由；观测 = 规则文本 + 首个按判据入套件的 commit
depends_on: rl_exp/tools/verify/offline_suite.py
evidence: acceptance/records/2026-10-09-repo-architecture-review
---

## 当前状态

判据已采纳（用户拍板 2026-10-09），正文归机制：规则句在 `AGENTS.md`，准入字段与暂缓条件在
`OFFLINE_CHECKS.md` §4，看守空缺在 §6。本事项只剩观测——首条按判据登记的套件条目。

## 未覆盖边界

不回溯审存量条目的准入来源（多数缺陷史只在 git log 里）；准入无机器看守（`OFFLINE_CHECKS.md` §6），
判定与腐化都靠 review；不改 `.codemaker/rules/versioning.mdc` 的既有闸门条款。是否值得做"命中史"统计未定。
