---
id: record-format-live-checks
title: 记录格式的剩余真跑段（HARNESS 挂账 #2 的未做半）
scope: ablation_harness, rl_exp/tools/runrecord
status: pending_review
landing: ablation_harness/record.py, ablation_harness/eval.py, rl_exp/tools/runrecord/provenance.py
evidence: acceptance/records/2026-10-10-record-format-live-checks
next: 待审（新上下文，不看执笔结论）。审什么：① 『修复』节的身份判读与落点是否一致（安装来源判据、`installed:5.4.2`、组合键移动后的锁重基线理由与两处 `FROZEN` 摘要）；② P2 守卫的例外表与自失效分支是否只覆盖修复前那两对、天花板是否写得准；③ `close_when` ② 按用户拍板改写后，"分列 + 同源事实"是否即算满足。落点与读数：该记录的『独立审核』与『修复』两节。
close_when: ① 同一 run 身份按安装来源重建后两处取值一致 ⇒ 记"已核到行为"，不一致 ⇒ 记差异并指出是哪一侧的字段口径；② 声明与实际两列分列、且两列同源于一处这一事实已写出 ⇒ 成立，某侧缺失 ⇒ 报记录不完整
---

## 当前状态

2026-10-10 审核后修复已落地：身份判据改按安装来源、同次 run 两 rev 收敛，连同逼出的配方锁重基线。
`close_when` ② 的口径按用户当日拍板改写（"两列同源、无法叉开"不再算未满足）；
`runtime.*_declared` 落覆盖后值的字段名问题**不改**，另立
`work/active/eval-declared-columns-are-post-override.md`。读数、复读命令、勘误与本次修复的唯一归属：
`acceptance/records/2026-10-10-record-format-live-checks.md`。

## 范围边界

- pre-format 分支按用户此前决定不构造；该分支的适用边界见证据记录，不作全部真跑承诺。
- 协议版本切换归 `work/closed/2026/runtime-acceptance-v3.md`；资产 fail 路径归
  `work/active/asset-fail-path-live-check.md`；rsl_rl 身份改变后"可重建"行的读法归
  `work/active/verified-rebuild-rating.md`。
- `livecheck` 组不进入性能对账表；其它事项若引用其记录，仍按各自判据审核。
