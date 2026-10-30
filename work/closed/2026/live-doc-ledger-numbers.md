---
id: live-doc-ledger-numbers
title: 活文档里的旧台账编号
scope: ablation_harness, work/active, ARCH_PLAN.md
status: done
landing: ablation_harness/HARNESS.md, ARCH_PLAN.md, ablation_harness/protocols
outcome: 独立审核通过，详情见 evidence；冻结协议未修改。
close_when: 独立审核活跃标题无失效编号、指定冻结协议注释已有处置且两处指针真实可解析；失败退回修复。
evidence: acceptance/records/2026-10-30-live-doc-ledger-numbers.md, acceptance/records/2026-10-30-live-doc-ledger-numbers-review.md
---

## 当前状态

执行与独立审核结果见 evidence。

## 关闭条件

- 新上下文核对 `work/active/` 中事项标题、指定协议注释及冻结声明，确认处置与当前实际文件一致。
- 核对 `ARCH_PLAN.md`、`ablation_harness/HARNESS.md` 的事项路径和目标，确认 evidence 未将历史状态当成当前状态。
- 审核通过后归档；可修缺口退 `in_progress`，只有用户能解除的缺口置 `blocked`。

## 边界

版本目录、验收记录及 `work/closed/` 是历史类，不改写；冻结协议内的新指针只能随新协议版本处理。本项不改协议语义、黄金基线或闸门。
