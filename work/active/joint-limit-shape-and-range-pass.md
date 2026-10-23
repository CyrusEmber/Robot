---
id: joint-limit-shape-and-range-pass
title: lizard2 陆地骨骼与默认关节驱动交付统筹
scope: acceptance/records, work/active
status: open
landing: acceptance/records/2026-10-10-lizard2-land-body-drive-overall-work.md#验收条件, acceptance/records/2026-10-08-lizard2-joint-design-review-contract.md#验收条件
next: 执行者优先接真实训练配置，D 核必要接口与安全；完整动态接触评测另行维护，趴姿仍 blocked。
close_when: 新上下文对照需求记录、R1–R5、用户定案和两条并行子项的真实审核证据汇总设计判定，用户确认机体外观与几何样本；执行者先置 pending_review。lizard2-family-landing 的采用与训练未完动作仍由该项维护，不以本项关闭宣称已采用或已训；任一需求或设计缺口未判定继续在办。
evidence: acceptance/records/2026-10-19-lizard2-chest-standing-pd.md, acceptance/records/2026-10-13-lizard2-body-drive-plan-review.md, acceptance/records/2026-10-10-lizard2-land-body-drive-overall-work, acceptance/records/2026-10-08-lizard2-joint-design-review-contract
---

## 路由

| 项 | 接手文件 | 关系 |
|---|---|---|
| 机体与驱动候选（当前候选 PLAN 正文） | `work/active/lizard2-body-drive-candidate.md` | A/E 几何与真实消费者、B 声明载荷下默认 implicit PD 正确/稳定驱动和真实 effort/speed 限制、C 通道与默认驱动并行；各自前置成立后交 D 做输入/驱动/动作/安全 reset 集成审核，不验手工步态或躯尾协调性能 |
| 接触评测协议 | `work/active/lizard2-contact-protocol.md` | 维护三类动态样本、承重分类与报告契约；新增指标使用前核验，不阻塞当前首轮训练，不要求手工步态通过 |
| 训练策略性能判据 | `work/active/lizard2-family-landing.md` | 固定本轮工况与已有可信报告项；新增指标在使用前完成测量验证和阈值确认，未校准项未判，不从策略表现倒推标准 |
| 配方接入、采用与训练 | `work/active/lizard2-family-landing.md` | 直接接入已审草案，D/E 核真实动作/观测/接触采样/reset 与实际驱动设置；正式采用、版本锚点与已批预算按真实交付接续，完整新评测协议不作开训依赖 |
| 静态趴姿 | `work/active/lizard2-prone-posture.md` | blocked，等用户 |

本表是路由唯一活家，执行按[训练优先修订](../../acceptance/records/2026-10-23-lizard2-training-priority-plan.md)；配置、训练和评测仍在原事项，不另建编号关卡。`depends_on` 不将完整动态评测偷挂回开训。前置关闭时，下游换成已建立的真实记录，不引用不存在的交付。

默认驱动与 RL 职责取[用户定案](../../acceptance/records/2026-10-19-lizard2-chest-standing-pd.md#用户定案默认关节驱动与强化学习职责)；卸载、移重、躯尾协调、抬腿、步态及转向/恢复动态交训练后策略评测，不删除待验目标，也不作训练前手工运动成功条件。实际几何、碰撞、导出与受载驱动安全缺口仍由原责任项处理，不以无重力或格式检查替代，不新增胸部水平门槛。

需求与完整结论归 evidence。生物资料由 `work/active/large-monitor-skeleton-muscle-literature.md` 按需补证，正式资产管线由 `work/active/asset-tree-per-family.md` 在采用阶段核验；两者不是候选离线探索的全局阻塞。`rl_exp/versions/lizard2/PLAN.md` 只作入口，已冻结已训 v3 不改，本次文档同步不授权采用、冻结或开训。
