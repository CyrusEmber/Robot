---
id: lizard2-family-landing
title: lizard2 配方、动作接口与评测协议交付
scope: rl_exp/versions/lizard2, rl_exp/tasks, rl_exp/tools/pipeline, rl_exp/tools/verify, ablation_harness
status: in_progress
landing: rl_exp/versions/lizard2/main/main_params.yaml, rl_exp/tasks/lizard2_recipe.py, rl_exp/tools/pipeline/emit_diff_declaration.py, rl_exp/tools/verify/check_recipe_build.py
next: S5 按 RL 分工接通道与协议样本定策略判据；正式接入、采用与开训按正文执行。
close_when: 新上下文按正文“关闭条件”核验完整 S5/S6 或用户明确不采用的出口；仅 S5 构建通过不关闭。
depends_on: lizard2-body-drive-candidate, lizard2-contact-protocol
evidence: acceptance/records/2026-10-22-lizard2-rl-coordination-handoff.md, acceptance/records/2026-10-14-lizard2-palm-spatial-review-fixes.md, acceptance/records/2026-10-13-lizard2-body-drive-plan-review.md, acceptance/records/2026-10-10-lizard2-land-body-drive-overall-work, acceptance/records/2026-09-23-lizard2-v1-gait-skate, acceptance/records/2026-10-09-lizard2-limit-requirement-and-status-sync, acceptance/records/2026-10-09-lizard2-v3-pretrain-sanity, acceptance/records/2026-10-10-lizard2-v3-joint-velocity-limits
---

## 当前范围与交接

本项按下文 S5/S6 维护实际执行与交付，消费整体记录 `acceptance/records/2026-10-10-lizard2-land-body-drive-overall-work.md` 的需求与边界。当前职责按[用户定案](../../acceptance/records/2026-10-19-lizard2-chest-standing-pd.md#用户定案默认关节驱动与强化学习职责)执行。候选 PLAN 正文为 `work/active/lizard2-body-drive-candidate.md`；`rl_exp/versions/lizard2/PLAN.md` 只作路由，本轮不改该入口或已冻结、已训的 v3 PLAN，不建立或采用新版本。

骨骼/几何、默认 implicit PD 驱动与通道由候选项 A/B/C/E 交付；D 核训练前输入、驱动、真实动作映射和安全 reset。协议与测量样本由 `work/active/lizard2-contact-protocol.md` 交付，各自审核。卸载、移重、平衡、躯尾协调、抬腿和步态由 RL 学习，运动性能（含转向/恢复动态）归本项 S6；按[抬腿归属更正](../../acceptance/records/2026-10-22-lizard2-current-lift.md#用户更正抬腿检查归属)，该手工诊断不作策略验收或驱动缺陷判据，不要求 S5/D/开训前手工动作成功。

拖尾与新增掌跖段承重须进入新协议的具名接触分组。静态趴姿归 `work/active/lizard2-prone-posture.md`（blocked），不在本项挂账、不计出口、不拆分 S5/S6；不新增趴姿任务。数值依据归 evidence，驱动方案尚未批准时不先写死奖励。版本及资产采用消费 `.codemaker/rules/versioning.mdc` §A/§B。

## S5 直接执行：配方与评测接入

`depends_on` 约束正式配方接入与本项完整交付；阈值前置动作只消费具名默认驱动条件、通道和测量样本，不要求上游已关闭或 D 已通过。

### 阈值前置动作（B 默认驱动条件、C 通道与协议样本可用后）

1. 接收候选项 B 在声明载荷/工况下的默认 implicit PD 正确驱动、稳定跟踪及真实 effort/speed 限制条件，C 的通道与默认驱动交付，以及协议项可复读的测量口径/样本。核对资产、代码、目标、载荷、驱动及工况身份；缺测量口径回协议项，缺驱动条件或通道回 B/C，不要求两项先关闭。候选项负责首次测试的安全预算与设计不变量。
2. 据上述输入与训练目标提出摆动脚数、净空、摆幅、滑移、柔顺、躯尾协调、转向及恢复等学习策略性能判据，明确幅度、窗口、覆盖与安全停止要求，在 S6 评测前取得用户确认并固定。确认记录进 `acceptance/records/<日期>-lizard2-comparison-criteria.md`，存在后补 evidence。协议修订交协议项，受影响策略按同尺重评；不能从最终策略表现倒推阈值。
3. 本动作只定义训练后的策略性能判据，不批准机体、配方或 S6，不以标定样本宣告性能通过。无需先证明手工步态、卸载/移重、抬腿或躯尾协调；不把性能判据回交 D 要求手工比较。D 仍独立审核训练前集成与安全边界。

### 正式配方接入（上游集成与协议已审后）

1. 核对候选项 D 的输入/驱动/动作/安全 reset 集成审核与协议项的真实审核记录、阈值确认；未齐备只整理机制落点，不准备正式接入产物。D 必须消费 B 在声明载荷下的默认驱动证据与 E 真实消费者证据，不能以无重力运动或格式检查替代。核对部署端对限位外位置参考的实际行为，区分物理禁区与动作裁剪；不新增胸部世界水平门槛。
2. 按版本机制准备未冻结下一版本 PLAN/参数与差异声明，接入获准的肩髋三轴、肘膝与腕踝动作、掌/跖末端承重分组和必要的有效限速；无指/趾根活动轴，不创建其驱动或空动作组。五个腿部角色及躯干/颈/尾逐角色明确策略可访问、锁定或阶段门控及依据；twist 不套旧 foot 通道。诊断可控不自动批准全部开放，正式开放须实际配方变更；RL 所需协调关节不能默认为零目标锁定，锁定/门控须明确可学性限制与开放阶段，未获准不代填决策。动作通道、`joint_order`、默认位姿及传感器与实际 joint/link 集合逐项对表；复用 E 已验隔离绑定及现有注册/执行器机制，不改已发布 term 或 v3 参数。逐角色向真实 action manager 注入，核缩放、偏置、裁剪、顺序、目标、状态及对应实体运动，固定/门控角色同样验保持或阶段切换；同关节数/网络宽度不证明动作语义一致。驱动和奖励数值归版本配置，理由和依据归记录。
3. 统一奖励和诊断的承重口径，消费前置动作已固定的学习策略判据，不要求经 D 手工运动验证。只在证据支持时采用最小奖励项，不把奖励当反曲/翻掌/碰撞的硬保证，不让 S6 失败后的调阈值倒改验收。
4. 采用已审具名新协议，绑定检查报告、writer/reader 与锚点，旧协议不改写；S6 按固定判据评测，失败不事后放宽，换尺须新协议和同尺重评。
5. 运行配方构建、注册/obs/action 对表、驱动单测、真实运行时限制与安全 reset 核验及相关离线闸门；形成 S5 新记录并请新上下文审核候选接入和协议。全部产物能被复读后才允许进入 S6，S5 通过不关闭本项。

S5 交付为未冻结候选版本实际路径、配置/协议/测试及 `acceptance/records/<日期>-lizard2-s5-recipe-eval.md`；记录存在后才加入 evidence。骨骼、碰撞、默认驱动或映射缺陷回候选项，受影响证据重新审核；学习协调性能不回流为 D 手工步态前置。

## S6 直接执行：正式采用、预检与训练验收

1. 取得 S5 已审交付及用户正式机体采用决定，按版本规则 §A 完成资产采用、骨骼改名迁移（`joint_order`、正则组、工具、obs/action 文档同变更）、冻结版本退休及版本身份；不覆盖或解冻已训 v3，不刷新旧资产锁。正式管线核验交 `asset-tree-per-family`，不能以候选转换成功替代。
2. 跑当前版本离线套件、声明载荷下默认驱动读回/稳定跟踪、安全 reset 与静态承重安全检查、地形预检及 GUI 目视，绑定同一机体和配方。核实运行时 effort/speed 上限及真实动作映射，不以静态声明或无重力运动替代；不是行走或协调性能预验收。产物与判定写 S6 记录；红项先修复，不开训。
3. 向用户展示训练预算、工况、启动/评测命令与验收依据并确认。用户仅授权同步 work 不等于授权开训；预算或关键条件未批准置 blocked，保持可接手。
4. 按版本机制冻结并启动用户批准训练，记录实际 run、manifest/checkpoint 与偏离；检查工作树和启动协议，不能在缺锚状态假称可复现。采用、授权、冻结与已验证运行时约束均须先于开训。
5. 固定具名新协议评测实际 checkpoint：速度/存活、卸载/移重、抬腿与步态、承重滑移、躯尾协调/拖尾、转向与恢复动态均归学习策略性能验收；用户检查预览。几何样本或通道注入不代替策略表现，不要求训练前手工控制器先通过这些动作。不新增趴姿训练或起卧过渡；训练通过不自动代替姿势验收。
6. 回填 NOTES 的 run/报告指针与一句判定，数值结论进 `acceptance/records/<日期>-lizard2-s6-adoption-training.md`；执行者置 pending_review，新上下文审核。失败修复或明确拒绝，未完成动作不得以预算耗尽关闭。

## 关闭条件

- **审核者与输入**：执行者先置 pending_review；新上下文对照 S5/S6、已审上游交付及真实记录审核。
- **S5 交付**：训练策略判据在 S6 评测前固定，已审默认驱动/动作/安全 reset 集成接入候选配方；逐角色策略可访问/锁定/门控决策落地，新接触协议及测量样本可复读。仅阈值确认或配方构建通过不关闭，不要求 D 手工步态比较。
- **S6 采用与验收**：正式机体采用、改名迁移、旧机体冻结版本退休及版本证据齐备；完成用户批准工况下实际训练、固定协议学习策略评测与目视验收。旧 v3 判决不替代本项。
- **不采用出口**：用户明确不采用时记录理由与未完动作去向，不把未验证说成通过。
- **结果处理**：完整交付经审核通过，或用户明确不采用，才关闭；可修缺口退 in_progress，预算未批准或用户决定缺失置 blocked。未完 S6 继续在办，不随 S5 关闭。

## 动作接口与奖励待办

- 部署端是否接受限位外位置参考仍待核对；历史参考越限诊断与撤回见步态记录，不仅据参考越限决定裁剪。物理反曲禁区按 R4（`acceptance/records/2026-10-08-lizard2-joint-design-review-contract.md`）实施，不能用动作参考裁剪替代。
- 初始动作分布与硬限位、初始化高度与自然站高的配方合理性复核沿用 `rl_exp/tools/verify/action_range_check.py`；历史读数及判定仅见 `acceptance/records/2026-10-09-lizard2-v3-pretrain-sanity.md`，不外推当前候选可开训。改配方走版本规则。
- `feet_slide` / `foot_clearance` 保留奖励候选，先统一承重口径再定实现与权重。脚掌接触面积/形状项排除依据、lf 异常撤回与历史因果边界见步态记录。
- 姿态目标未验收时不直接新增角度监督；设计要求、量测与可训练目标交接见整体记录及用户定案指针。
- 速度上限消费 B 声明载荷下默认 implicit PD 的跟踪/稳定包线与真实 effort/speed 约束；明确有依据启用或明确不启用及风险/工况边界，未决须回 B，不把自动启用当默认要求。不以旧 URDF 自报值、旧策略分位数或 `check_actuator_budget.py --drive-audit` 单独批准上限；启用须同条件对照并核引擎采用，字段机制按 evidence 与 `check_dr_parity.py` 取用。不启用诊断不冒称有限速能力。

## 证据边界

历史判决按原协议与机体解释，不自动外推当前候选。最小运行自检、静态几何、运动采样与执行器估算均有范围，不能替代碰撞、声明载荷下驱动稳定性或学习策略效果验证；几何样本只作诊断，不新增手工完整步态门槛。已训旧版本复现承诺按家族生命周期读取。

审核记录按整体记录“审核输入绑定约定”落地，只留已有记录指针。本轮通道复读只整理接入机制，不构成正式 S5/S6 交付或可开训结论。
