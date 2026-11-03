---
id: lizard2-two-axis-feet
title: lizard2 脚掌双自由度机体
scope: rl_exp/lizard2_palm_spatial, rl_exp/tools/diagnose, rl_exp/versions/lizard2
status: superseded
superseded_by: lizard2-round-feet
outcome: 按用户指令由圆足方案替代；独立审核通过，已有文件及未完动作已交接，不代表旧机体能力验收通过。
landing: rl_exp/tools/diagnose/lizard2_two_axis_candidate.py, rl_exp/versions/lizard2
close_when: 新上下文按正文“关闭条件”核验替代关闭；不声称双轴机体已采用。
evidence: acceptance/records/2026-10-29-lizard2-two-axis-candidate.md, acceptance/records/2026-10-29-lizard2-two-axis-support-sweep.md, acceptance/records/2026-10-29-lizard2-foot-design-review.md, acceptance/records/2026-10-30-lizard2-foot-control-tiprise-review.md, acceptance/records/2026-10-30-lizard2-foot-control-first-trials.md, acceptance/records/2026-10-30-lizard2-round-feet-plan-review.md, acceptance/records/2026-10-30-lizard2-foot-plan-closure-review.md
---

## 当前范围

用户要求关闭旧脚板方案，本项已由圆足事项替代关闭；双轴未完动作转由 `work/active/lizard2-round-feet.md` 的交接节维护，以下清单仅保留旧实施背景。双轴首轮记录、原腕偏差、路径、接触观测、惯量和驱动缺口没有变为通过；双轴候选未采用为正式机体或训练配方。依据见 `acceptance/records/2026-10-30-lizard2-round-feet-plan-review.md`。

## 下一步

1. 执行者绑定保留输入和允许改动，核实脚掌坐标、俯仰/侧翻定义、左右正方向及组合范围；核本次限位、地面接触及实际加载的自碰撞开关与过滤，避免把正交单轴当全域解耦。当前自碰撞关闭时，内部网格相交只记录模型限制，不阻塞有限受载 PD 诊断，不要求先改碰撞形状；地面穿透、异常承重和失稳仍须检查。若自碰撞开启或设置不明，先核实有效碰撞冲突，不用加刚度掩盖；局部诊断不等待全运动域验收。
2. 按 `lizard2-foot-design-tradeoffs` 的限位与 PD 顺序恢复受载保持、正负响应及观测核验；原腕反向偏差、路径失配和接触观测缺口仍待处理。踮脚只有明确需要该能力时才继续，不作为圆足或双轴采用的默认硬门槛；既有失败不改写。各轴不预设高增益或强制同增益，不混改后单独归因；同外部条件不等于同足载。缺可靠力矩读回可筛选当前模型候选增益，不核定正式驱动、饱和或硬件余量。质量惯量及 USD/URDF/Blender 一致性仍须核对，诊断试值不作正式参数。
3. 在声明使用范围的碰撞、惯量和受载前置满足后，创建独立版本及命名、动作、观测和评测接线；只有命令链确有顶限位问题时才评估目标余量或限位奖励，不要求必加奖励。纯关节限位项不等待接触协议，消费接触信号的奖励或判分须先完成对应标定。旧 checkpoint 不作新接口兼容替代，策略性能和训练启动按对应事项另行确认。
4. 完成相关证据及仓库闸门后置 pending_review，交不带执笔历史的新上下文审核；尚未正式核定的能力不因文档修订视为通过。

## 关闭条件

- **审核者与输入**：无执笔历史的新上下文核对用户关闭指令、圆足交接节、原候选与记录。
- **可观察验收**：双轴的几何、惯量、控制、限位、观测与正式版本接线缺口均保留在办归属；旧试值及失败不改写为正式验收。
- **交付与边界**：按 superseded 交给 lizard2-round-feet，不按 done 宣布双轴完成；更新仍活跃的交接指针，保留历史记录。
- **结果处理**：审核通过后移入 work/closed/2026，保留 id、去掉 next、补 outcome/superseded_by；失败退 in_progress。
