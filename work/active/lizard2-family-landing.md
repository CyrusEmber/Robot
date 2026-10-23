---
id: lizard2-family-landing
title: lizard2 配方、动作接口与评测协议交付
scope: rl_exp/versions/lizard2, rl_exp/tasks, rl_exp/tools/pipeline, rl_exp/tools/verify, ablation_harness
status: in_progress
landing: rl_exp/versions/lizard2/main/main_params.yaml, rl_exp/tasks/lizard2_recipe.py, rl_exp/tools/pipeline/emit_diff_declaration.py, rl_exp/tools/verify/check_recipe_build.py
next: 执行者复用已审草案，落地正式候选配置并核训练接口。
close_when: 新上下文核验配置、采用、实际训练与策略评测交付；仅构建通过不关闭。
depends_on: lizard2-body-drive-candidate
evidence: acceptance/records/2026-10-23-lizard2-plan-inventory.md, acceptance/records/2026-10-23-lizard2-training-interface-plan.md, acceptance/records/2026-10-22-lizard2-rl-coordination-handoff.md, acceptance/records/2026-10-14-lizard2-palm-spatial-review-fixes.md, acceptance/records/2026-10-13-lizard2-body-drive-plan-review.md, acceptance/records/2026-10-10-lizard2-land-body-drive-overall-work, acceptance/records/2026-09-23-lizard2-v1-gait-skate, acceptance/records/2026-10-09-lizard2-limit-requirement-and-status-sync, acceptance/records/2026-10-09-lizard2-v3-pretrain-sanity, acceptance/records/2026-10-10-lizard2-v3-joint-velocity-limits
---

## 当前范围与交接

执行依据与变更边界取[训练优先修订](../../acceptance/records/2026-10-23-lizard2-training-priority-plan.md)。本项直接维护候选配置接入、正式采用、训练和策略评测；接口数值与映射取[训练接口方案](../../acceptance/records/2026-10-23-lizard2-training-interface-plan.md)。不设独立编号阶段或完整评测协议的开训关卡。

A/E 交骨架、几何及真实消费者，B/C 交具名工况下的默认驱动与通道，D 核同一配置的输入、驱动、动作、观测、接触采样与安全 reset。已有独立证据按身份和范围复用，只补实际变更或缺证；未核出的缺陷不因计划改写而通过。卸载、移重、平衡、躯尾协调、抬腿、步态及转向/恢复由 RL 学习，其性能在训练后评测。

`depends_on` 约束训练输入与安全集成，消费具名已审交付，不要求候选总项先关闭。`lizard2-contact-protocol` 维护新测量和完整评测协议；其三类动态标定、异常主承重分类及完整发布不阻塞本轮位置策略训练。若新增指标进入奖励、终止或合格判定，必须先交付对应测量验证，不得用未校准信号训练或判通过。静态趴姿仍归 `lizard2-prone-posture`（blocked），不作为本轮出口。

## 正式候选配置与训练接入

1. 消费候选 D 的输入/驱动/动作/安全 reset 审核与 B/C/E 的具名记录，核资产、代码、工况和实际驱动设置。配置接入可以直接准备，完整新接触协议未发布不阻止该动作；实际错轴、残留目标、漏采或驱动安全缺口按来源修复。部署端参考越限行为、硬限位与动作裁剪分别核对，不新增胸部世界水平门槛。
2. 按版本机制准备未冻结的下一版本 PLAN、参数与差异声明，绑定肩髋三轴、肘膝、腕踝及胸颈尾。逐角色落实策略可访问/锁定/门控及依据，RL 所需协调关节须有真实可达动作；不恢复指/趾根空通道，不暗中锁零。关节顺序、目标映射、scale/offset/clip、默认姿态、驱动及传感器逐项对照实际集合，复用已审草案，不改已发布 term 或已训 v3。
3. 在最终同一配置核实际 action manager 的逐列目标、缩放/偏置/裁剪、backend 零速度目标及实体响应，核非零观测、接触首子步/历史、完整及子集 reset 和已声明的终止边界。范围未变的证据复用；构建和名称一致不替代运行。实际采用的 effort/speed 设置须读回，不恢复已取消的边界试验。
4. 首轮沿用已核训练目标和必要的接触消费者，不因延后评测标定而静默删改奖励/终止。新滑移、滚动或异常主承重指标未经验证不启用；需要新增奖励时按版本纪律另交实现、测量依据和检查。奖励不保证几何禁区或全域精度。
5. 完成相关离线检查，由新上下文结合 D 一次核同一候选的真实配置和接口记录，避免把配置、协议和训练拆成反复互等的审核关卡。记录实际路径及可复读证据；红项修复后接续，不把手工步态表现列为输入检查。

## 正式采用与训练

1. 依据已核候选和用户采用决定，按版本规则完成正式资产声明、骨骼改名迁移、仍消费旧机体的冻结版本退休及新版本身份。`joint_order`、正则组、工具与 obs/action 文档随实际采用同步；不覆盖或解冻已训 v3，不刷新旧资产锁。资产管线消费 `asset-tree-per-family` 对此次采用的检查，不等待该项所有历史尾项关闭。
2. 复用同身份的默认驱动、静态承重安全、动作/观测、采样/reset 证据；只补正式落点变化影响的核验，以及地形预检、GUI 目视和相关仓库检查。取消的限速/限矩及对称复测不恢复，不要求先手工走路或抬腿。
3. 首轮训练预算与从头初始化决定复用[接口方案](../../acceptance/records/2026-10-23-lizard2-training-interface-plan.md#用户确定首轮训练预算)，不重复询问同一预算。展示实际工况、启动命令、学习目标及已有评测依据；尚未确定的关键采用/运行条件具名处理，不用预算确认代替输入核验，也不把只改计划写成已经开训。
4. 按版本机制冻结，通过启动前检查后执行已批准训练，绑定实际 run、manifest/checkpoint 与偏离。新策略从新接口初始化，不以旧 v3 checkpoint 续训代替新候选训练；工作树和版本锚点可复现。

## 训练后策略评测

1. 固定命令、窗口及已有可信报告项，评价实际 checkpoint 的速度/存活、卸载/移重、抬腿/步态、躯尾协调/拖尾、转向及恢复，交用户预览。学习性能不回交 D 要求手工动作先成功；趴姿训练和起卧过渡仍不新增。
2. 净空、摆幅、承重滑移、柔顺及异常主承重等目标继续保留。使用新增滑移/滚动分类或新承重判分前，交 `lizard2-contact-protocol` 完成相应样本、writer/reader、具名协议及审核；性能阈值在使用前经用户确认固定。未校准项写未判，不把静置样本外推动态能力，不从最终表现倒推阈值；更换尺须保留身份并同尺重评。
3. `report_only` 新清单、尾部与新增掌跖段分组、持续部分承重幅值标定及新协议发布仍由协议项维护；训练和该评测工具工作可并行，完整协议只约束使用其判分的结论。
4. 回填 NOTES 的实际 run/报告指针与一句判定；数值和结论归 acceptance/records。执行者按下文关闭条件交新上下文审核，失败与未判保留责任和去向，不因预算用完关闭。

## 关闭条件

- **审核者与输入**：新上下文对照上述配置、采用、训练与策略评测及真实证据；执行者完成后先置 pending_review。
- **配置与采用**：真实动作权限、驱动、观测、接触采样与 reset 集成已核，正式机体/改名/旧版本退休和版本锚点一致。仅草案构建或接口局部通过不等于采用或已训。
- **训练与评测**：实际执行已批准训练，按固定口径评价策略并供用户目视；新增指标已交相应验证，未启用或未验证的目标保持待验，完整策略验收不以未判冒充通过。原运动及躯尾目标不随取消独立阶段消失。
- **结果处理**：全部交付经审核，或用户明确不采用并记录未完动作去向，才关闭。可修缺口退 in_progress；只有用户能解除的条件缺失才 blocked。训练与协议未完动作分别继续在原事项，不为文档预算关闭或迁移。

## 接口与证据边界

- 部署端限位外参考与反曲禁区分别处理，历史撤回取 evidence；不以目标裁剪保证无碰撞或全域小幅精度。初始动作分布/硬限位/出生高度按已绑定候选核合理性，不外推旧 v3 读数。
- `feet_slide` / `foot_clearance` 保留奖励候选；先验证其实际测量，再按版本机制决定实现与权重，未加入首轮不构成该轮开训缺口。姿态监督仍须实际验收依据。
- 速度设置取当前候选配置并核实际写入；[取消决定](../../acceptance/records/2026-10-23-lizard2-plan-inventory.md)中的触边、跨关节、有/无限速及速度—载荷包线不恢复，未验范围不称通过。
- B/C 输入取[清单](../../acceptance/records/2026-10-23-lizard2-bc-handoff.md)和[审核](../../acceptance/records/2026-10-23-lizard2-bc-independent-review.md)；草案取[运行记录](../../acceptance/records/2026-10-23-lizard2-interface-runtime.md)及[复核](../../acceptance/records/2026-10-23-lizard2-interface-runtime-review.md)。接触测量取[原生样本](../../acceptance/records/2026-10-23-lizard2-contact-native.md)及其独立审核，原有限范围不变。
- 历史判决按原协议/机体解释；计划修订不修改原失败、不证明未测能力、不采用资产或启动训练。后续以同一候选实际配置与产物交付。
