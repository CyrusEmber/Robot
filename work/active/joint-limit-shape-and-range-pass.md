---
id: joint-limit-shape-and-range-pass
title: lizard2 陆地骨骼、足部驱动与完整步态修复统筹
scope: acceptance/records, work/active
status: open
landing: acceptance/records/2026-10-10-lizard2-land-body-drive-overall-work.md#验收条件, acceptance/records/2026-10-08-lizard2-joint-design-review-contract.md#验收条件
next: 并行推进 lizard2-body-drive-candidate（Blender 机体、改名、驱动、躯干/尾部）与 lizard2-contact-protocol（接触评测协议），各自完成后一次审核；二者通过后 lizard2-family-landing 做 S5/S6。趴姿归 lizard2-prone-posture（blocked）。本项只汇总设计判定，不重复子项的操作步骤。
close_when: 新上下文对照需求记录、R1–R5 和两条并行子项的真实审核证据汇总设计判定，用户确认机体与动作；执行者先置 pending_review。lizard2-family-landing 的采用与训练未完动作仍由该项维护，不以本项关闭宣称已采用或已训；任一需求或设计缺口未判定继续在办。
evidence: acceptance/records/2026-10-10-lizard2-land-body-drive-overall-work, acceptance/records/2026-10-08-lizard2-joint-design-review-contract
---

## 路由

| 项 | 接手文件 | 关系 |
|---|---|---|
| 机体与驱动候选 | `work/active/lizard2-body-drive-candidate.md` | 并行，内部 A/B/C 同时开始，D 集成后一次审核 |
| 接触评测协议 | `work/active/lizard2-contact-protocol.md` | 并行，不等机体 |
| 配方、采用与训练（S5/S6） | `work/active/lizard2-family-landing.md` | 依赖上两项的已审交付 |
| 静态趴姿 | `work/active/lizard2-prone-posture.md` | blocked，等用户 |

本表是阶段路由的唯一活家，依赖关系的机器可读真身是各项 `depends_on`。子项唯一维护操作步骤、交付路径和完成条件，本项不留第二份；前置关闭时，同一次变更把下游 `depends_on` 的活跃 id 换成已建立的交付记录路径，不得提前指向不存在的证据或留下失效活跃依赖。

需求与范围唯一归 evidence；生物资料由 `work/active/large-monitor-skeleton-muscle-literature.md` 按需补证，正式资产管线由 `work/active/asset-tree-per-family.md` 在采用阶段核验。两者不是候选离线探索的全局阻塞。
