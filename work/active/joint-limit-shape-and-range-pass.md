---
id: joint-limit-shape-and-range-pass
title: lizard2 陆地骨骼、足部驱动与完整步态修复统筹
scope: acceptance/records, work/active
status: in_progress
landing: acceptance/records/2026-10-10-lizard2-land-body-drive-overall-work.md#阶段顺序与责任, acceptance/records/2026-10-08-lizard2-joint-design-review-contract.md#验收条件
next: 从 lizard2-s0-target-calibration 开始，按正文路由逐项接手；子项各自维护执行动作与审核状态，本项只协调依赖、需求变动和交接。子项失败回对应上游，证据改变后重审；配方与正式采用按 lizard2-family-landing 的 S5/S6 执行。当前拆分已落文档，尚未执行骨骼或驱动修复。
close_when: 新上下文对照需求记录、R1–R5 和 S0–S4 子项的真实审核证据汇总设计判定，用户确认机体与动作；执行者先置 pending_review。S5/S6 未完动作仍由具名交付事项维护，不以本项关闭宣称已采用或已训；任一需求或设计缺口未判定继续在办。
evidence: acceptance/records/2026-10-10-lizard2-land-body-drive-overall-work, acceptance/records/2026-10-08-lizard2-joint-design-review-contract
---

## 分步骤执行入口

| 顺序 | 接手文件 |
|---|---|
| S0 | `work/active/lizard2-s0-target-calibration.md` |
| S1 | `work/active/lizard2-s1-body-candidate.md` |
| S2 | `work/active/lizard2-s2-motion-and-prone.md` |
| S3 | `work/active/lizard2-s3-drive-load.md` |
| S4 | `work/active/lizard2-s4-trunk-tail.md` |
| S5/S6 | `work/active/lizard2-family-landing.md` 的两个执行节 |

子项唯一维护操作步骤、交付路径和完成条件，本项不留第二份。`open` 下游只是尚未开始，须先读取其 `depends_on` 和交付。前置关闭时，同一次变更把下游 `depends_on` 的活跃 id 换成已建立的交付记录路径，并更新统筹路由到关闭文件；不得提前指向不存在的证据或留下失效活跃依赖。

需求与范围唯一归 evidence；生物资料由 `work/active/large-monitor-skeleton-muscle-literature.md` 按需补证，正式资产管线由 `work/active/asset-tree-per-family.md` 在采用阶段核验。两者不是 S0 离线探索的全局阻塞。
