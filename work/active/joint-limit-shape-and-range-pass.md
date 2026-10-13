---
id: joint-limit-shape-and-range-pass
title: lizard2 陆地骨骼、足部驱动与完整步态修复统筹
scope: acceptance/records, work/active
status: open
landing: acceptance/records/2026-10-10-lizard2-land-body-drive-overall-work.md#验收条件, acceptance/records/2026-10-08-lizard2-joint-design-review-contract.md#验收条件
next: 执行者按路由并行推进机体与协议；B/C 标定交 S5 阈值前置动作后做 D，设计与协议已审后再做配方接入/S6；趴姿仍 blocked。
close_when: 新上下文对照需求记录、R1–R5 和两条并行子项的真实审核证据汇总设计判定，用户确认机体与动作；执行者先置 pending_review。lizard2-family-landing 的采用与训练未完动作仍由该项维护，不以本项关闭宣称已采用或已训；任一需求或设计缺口未判定继续在办。
evidence: acceptance/records/2026-10-13-lizard2-body-drive-plan-review.md, acceptance/records/2026-10-10-lizard2-land-body-drive-overall-work, acceptance/records/2026-10-08-lizard2-joint-design-review-contract
---

## 路由

| 项 | 接手文件 | 关系 |
|---|---|---|
| 机体与驱动候选 | `work/active/lizard2-body-drive-candidate.md` | A/E 与 B 能力调查、C 通道探测并行；各自前置成立后 B/C 标定，取得 S5 阈值确认再做 D，D 后一次审核 |
| 接触评测协议 | `work/active/lizard2-contact-protocol.md` | 并行，测量口径供 B/C，writer 契约与真实报告回交 E；不等候选关闭或采用 |
| 性能阈值（S5 前置） | `work/active/lizard2-family-landing.md` | 消费具名 B/C 标定与接触口径，用户确认后回交 D；不依赖上游已审或关闭 |
| 配方接入、采用与训练（S5/S6） | `work/active/lizard2-family-landing.md` | 正式接入及完整交付依赖机体与协议的已审交付；S6 另获用户采用/开训确认 |
| 静态趴姿 | `work/active/lizard2-prone-posture.md` | blocked，等用户 |

本表是阶段路由的唯一活家，各项 `depends_on` 表示完整交付的依赖，不阻止表中明确允许的中间交付。S5 阈值前置和正式接入共属原事项，不新建待办；子项唯一维护操作步骤、交付路径和完成条件，本项不留第二份。前置关闭时，同一次变更把下游 `depends_on` 的活跃 id 换成已建立的交付记录路径，不得提前指向不存在的证据或留下失效活跃依赖。

需求与范围唯一归 evidence；生物资料由 `work/active/large-monitor-skeleton-muscle-literature.md` 按需补证，正式资产管线由 `work/active/asset-tree-per-family.md` 在采用阶段核验。两者不是候选离线探索的全局阻塞。
