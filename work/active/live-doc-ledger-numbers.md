---
id: live-doc-ledger-numbers
title: 活文档里的旧台账编号（4 处协议注释 + 4 个事项标题 + 2 处指针核认）
scope: ablation_harness, work/active, ARCH_PLAN.md
status: open
landing: ablation_harness/HARNESS.md, ARCH_PLAN.md, work/active/headless-flag-deprecation.md, work/active/record-format-live-checks.md, work/active/runtime-acceptance-v3.md
next: ① 4 个活跃事项标题去掉「（HARNESS 挂账 #N）」：`HARNESS.md` 的 #1–#6 行已随迁移收成指针，编号在活链上解析不到；来源由 `acceptance/records/2026-09-20-harness-migration.md` 的表记着 ⇒ 标题只留当前状态，来源记录指针放进正文。② 4 处协议注释统一**不改**，判据写在本项：`locomotion_eval_v1.yaml:53` / `v2:63` / `v3:64` / `v4:83` 的 latency「挂账 #6」与 `v3:8` 的「#18 ①」都在"落库即冻结，只读"的契约文件里（v4 头部逐字如此），注释同样是字节；`ablation_harness/protocol_anchors.json` 只钉两份 JSON ⇒ 改注释不破闸门、破的是纪律，不为它开例外；要在协议内留活指针，唯一正路是下一版协议带上它（#6 的目标 = `work/active/deployment-delay-injection-dr.md`，blocked）。③ 核认 `ARCH_PLAN.md:47`、`HARNESS.md:10` 两处已带事项路径的指针，记一笔即完。
close_when: 4 个标题里不再有活链上解析不到的编号；4 处协议注释各有处置（`next` ② 的"不改"也算处置，理由在本项）；两处指针核认已记。历史类（`rl_exp/versions/**`、`acceptance/records/`、`work/closed/`、`rl_exp/fork_patches/`、`verify_logs`）不计入判据 —— 理由同 `work/closed/2026/stale-doc-pointers-in-code.md` 的冻结与证据表，本项不改写历史。
---

## 现状（2026-09-23 复核）

全仓 `PLAN.md #N` / `挂账 #N` 命中 **68 行**，按"它是什么"分三类：

| 类 | 命中 | 处置 |
|---|---|---|
| 历史类：版本目录 `PLAN/NOTES`、`acceptance/records/`、`work/closed/`、fork patch 存档、`verify_logs` 真日志 | ~55 行 | 不改（本项与关闭项同一套排除理由，按"它是什么"而非扩展名） |
| 已带事项路径：`HARNESS.md:10`（→ `isaac-root-parameterisation`）、`ARCH_PLAN.md:47`（→ `verified-rebuild-rating`） | 2 行 | 算已处置，只需核认 |
| **活且解析不到** | 4 处协议注释 + 3 个事项标题 | 本项 |

原第 4 个标题（`diagnostic-run-gate`，挂账 #5）已于 2026-09-23 关入 `work/closed/2026/`：按本项自己的判据
它转入历史类，标题里的编号不再要求改。

## 为什么不并进代码侧那次

代码侧那次（`7f2144f`）的判据是"原引用片段 = 身份"的白名单，逐处改指事项或机制。文档侧不同：编号本身不是错误 ——
`versions/lizard/PLAN.md` §5 的「原行 → 新事项」表仍在，`HARNESS.md` 的 #1–#6 行已收成指针 —— 问题只是
**在活链上解析不到**。所以动作是"删编号 / 写下不改的判据"，不是"改指文件"，判据也只能逐处点名（历史类量大，
"片段匹配 0 处"这种判据在文档侧不成立）。

## 未覆盖边界

- 版本目录、记录与 `work/closed/` 里的同类编号按历史处理，不在本项；要动须另立。
- 协议注释的处置是"不改"：若 owner 要协议内有活指针，只能随下一版协议（`locomotion_eval_vN+1.yaml`）带上。
- 本项不碰任何协议语义字段，不动 golden、不改闸门口径。
