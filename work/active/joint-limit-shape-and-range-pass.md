---
id: joint-limit-shape-and-range-pass
title: lizard2 陆地骨骼与默认关节驱动交付统筹
scope: acceptance/records, work/active
status: open
landing: acceptance/records/2026-10-10-lizard2-land-body-drive-overall-work.md#验收条件, acceptance/records/2026-10-08-lizard2-joint-design-review-contract.md#验收条件
next: 执行者并行推进候选与协议；D 审输入/驱动/动作/安全 reset 集成，S5 据 B/C 与测量样本定策略判据并接入；S6 另获采用与开训授权，趴姿仍 blocked。
close_when: 新上下文对照需求记录、R1–R5、用户定案和两条并行子项的真实审核证据汇总设计判定，用户确认机体外观与几何样本；执行者先置 pending_review。lizard2-family-landing 的采用与训练未完动作仍由该项维护，不以本项关闭宣称已采用或已训；任一需求或设计缺口未判定继续在办。
evidence: acceptance/records/2026-10-19-lizard2-chest-standing-pd.md, acceptance/records/2026-10-13-lizard2-body-drive-plan-review.md, acceptance/records/2026-10-10-lizard2-land-body-drive-overall-work, acceptance/records/2026-10-08-lizard2-joint-design-review-contract
---

## 路由

| 项 | 接手文件 | 关系 |
|---|---|---|
| 机体与驱动候选（当前候选 PLAN 正文） | `work/active/lizard2-body-drive-candidate.md` | A/E 几何与真实消费者、B 声明载荷下默认 implicit PD 正确/稳定驱动和真实 effort/speed 限制、C 通道与默认驱动并行；各自前置成立后交 D 做输入/驱动/动作/安全 reset 集成审核，不验手工步态或躯尾协调性能 |
| 接触评测协议 | `work/active/lizard2-contact-protocol.md` | 并行，测量口径与样本供 B/C，writer 契约与真实报告回交 E；不等候选关闭或采用，不以样本要求手工步态通过 |
| 训练策略性能阈值（S5 前置） | `work/active/lizard2-family-landing.md` | 消费 B 默认驱动条件、C 通道及协议测量样本，用户确认后在 S6 策略评测前固定；不依赖上游关闭，不回交 D 证明手工运动性能 |
| 配方接入、采用与训练（S5/S6） | `work/active/lizard2-family-landing.md` | 正式接入及完整交付依赖 D 集成与协议已审交付；S5 逐角色定策略可访问/锁定/门控，S6 另获采用/开训确认，冻结及真实运行时约束验证后训练并评测学习策略 |
| 静态趴姿 | `work/active/lizard2-prone-posture.md` | blocked，等用户 |

本表是阶段路由的唯一活家，各项 `depends_on` 表示完整交付依赖，不阻止表中明确允许的中间交付。S5 阈值前置和正式接入共属原事项，不新建待办；子项唯一维护操作步骤、交付路径和完成条件。前置关闭时，同次变更把下游活跃依赖换成已建立的交付记录，不提前指向不存在的证据或留下失效活跃依赖。

当前执行按[用户定案](../../acceptance/records/2026-10-19-lizard2-chest-standing-pd.md#用户定案默认关节驱动与强化学习职责)；卸载、移重、躯尾协调、抬腿、步态及转向/恢复动态交 `work/active/lizard2-family-landing.md` S6 学习策略评测，不删除待验目标，也不作为 S5/D/训练前手工运动成功条件。几何采样只作诊断；未完几何、碰撞、导出、接触 cap 有效性和声明载荷下驱动安全任务仍在各原责任项，不以无重力运动或格式检查替代，不新增胸部水平门槛。

需求与完整结论归 evidence。生物资料由 `work/active/large-monitor-skeleton-muscle-literature.md` 按需补证，正式资产管线由 `work/active/asset-tree-per-family.md` 在采用阶段核验；两者不是候选离线探索的全局阻塞。`rl_exp/versions/lizard2/PLAN.md` 只作入口，已冻结已训 v3 不改，本次文档同步不授权采用、冻结或开训。
