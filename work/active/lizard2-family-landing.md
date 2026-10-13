---
id: lizard2-family-landing
title: lizard2 配方、动作接口与评测协议交付
scope: rl_exp/versions/lizard2, rl_exp/tasks, rl_exp/tools/pipeline, rl_exp/tools/verify, ablation_harness
status: open
landing: rl_exp/versions/lizard2/main/main_params.yaml, rl_exp/tasks/lizard2_recipe.py, rl_exp/tools/pipeline/emit_diff_declaration.py, rl_exp/tools/verify/check_recipe_build.py
next: 执行者先按 S5 阈值前置动作接收 B/C 标定并提请确认，回交 D；已审设计与协议齐备后做配方接入，S6 采用与开训另获用户确认。
close_when: 新上下文按正文“关闭条件”核验完整 S5/S6 或用户明确不采用的出口；仅 S5 构建通过不关闭。
depends_on: lizard2-body-drive-candidate, lizard2-contact-protocol
evidence: acceptance/records/2026-10-13-lizard2-body-drive-plan-review.md, acceptance/records/2026-10-10-lizard2-land-body-drive-overall-work, acceptance/records/2026-09-23-lizard2-v1-gait-skate, acceptance/records/2026-10-09-lizard2-limit-requirement-and-status-sync, acceptance/records/2026-10-09-lizard2-v3-pretrain-sanity, acceptance/records/2026-10-10-lizard2-v3-joint-velocity-limits
---

## 当前范围与交接

本项按下文 S5/S6 维护实际执行与交付，消费整体记录 `acceptance/records/2026-10-10-lizard2-land-body-drive-overall-work.md` 的需求与边界；交付配方、动作接口、驱动接入、新接触评测与训练候选。骨骼、驱动、完整周期与躯干/尾部由 `work/active/lizard2-body-drive-candidate.md` 交付，评测协议与样本标定由 `work/active/lizard2-contact-protocol.md` 交付，二者并行、各自一次审核。当前版本入口为 `rl_exp/versions/lizard2/PLAN.md`，本轮不建立或采用新版本。版本及资产采用消费 `.codemaker/rules/versioning.mdc` §A/§B。

拖尾与新增掌跖段承重须进入新协议的具名接触分组。静态趴姿归 `work/active/lizard2-prone-posture.md`（blocked），不在本项挂账、不计出口、不拆分 S5/S6；不新增趴姿任务。数值依据归 evidence，姿态与驱动方案尚未批准时不先写死奖励。

## S5 直接执行：配方与评测接入

`depends_on` 约束正式配方接入与本项完整交付；阈值前置动作只消费具名标定和测量口径，不要求上游已关闭或 D 已通过。修订依据见本项审核记录 F2/F4。

### 阈值前置动作（B/C 标定后、D 最终比较前）

1. 执行者接收 `lizard2-body-drive-candidate` B/C 的实际候选标定记录，以及 `lizard2-contact-protocol` 可复读的测量口径/样本。核对资产、代码、目标、载荷、驱动及工况身份；缺测量口径回协议项，缺标定回 B/C，不要求两项先关闭。首次标定的安全预算和设计不变量由候选项的“标定前置”负责，不等待本动作产出。
2. 根据标定与目标提出摆动脚数、净空、摆幅、滑移、柔顺等性能判据及比较的幅度、窗口、覆盖要求，用户确认后固定；确认记录进 `acceptance/records/<日期>-lizard2-comparison-criteria.md`，存在后补 evidence 并交 D。不能从最终比较是否通过倒推阈值；需改口径时回协议项形成具名修订，受影响比较重跑。
3. 本动作仅交付最终比较的判据，不批准机体、配方或 S6，不以标定宣告性能通过。D 按固定判据新跑比较并完成设计审核后，才进入下面的正式接入。

### 正式配方接入（上游设计与协议已审后）

1. 先核对 `lizard2-body-drive-candidate` D 与 `lizard2-contact-protocol` 的真实审核记录、阈值确认和同条件最终比较；未齐备只整理机制落点，不准备正式接入产物。核对部署端对限位外位置参考的实际行为，区分物理禁区与动作裁剪。
2. 按版本机制准备未冻结下一版本 PLAN/参数与差异声明，接入获准的实际腕/踝动作、掌/跖末端承重分组和必要的有效限速；无指/趾根活动轴，不创建其驱动或空动作组。动作通道、`joint_order`、默认位姿及传感器与实际关节/link 集合逐项对表；复用 E 已验的隔离目标绑定及现有注册/执行器机制，不改已发布 term 或 v3 参数。驱动与奖励数值归版本配置，理由和依据归对应记录。
3. 统一奖励和诊断的承重口径，消费阈值前置动作已固定且经 D 验证的判据。只在证据支持时采用最小奖励项，不把奖励当反曲/翻掌/碰撞的硬保证，不让 S6 失败后的调阈值倒改验收。
4. 采用 `lizard2-contact-protocol` 已审的具名新协议，绑定检查报告、writer/reader 与锚点，旧协议不改写；沿用比较前固定的阈值，S6 按同尺复验，失败不事后放宽，换尺须新协议和同尺重评。
5. 运行配方构建、注册/obs/action 对表、驱动单测及相关离线闸门；形成 S5 新记录并请新上下文审核候选接入和协议。全部产物能被复读后才允许进入 S6，S5 通过不关闭本项。

S5 交付为未冻结候选版本的实际路径、配置/协议/测试及 `acceptance/records/<日期>-lizard2-s5-recipe-eval.md`；记录存在后才加入 evidence。需要回改骨骼或目标时交 `lizard2-body-drive-candidate`，受影响证据重新审核。

## S6 直接执行：正式采用、预检与训练验收

1. 取得 S5 已审交付及用户正式机体采用决定，按 `.codemaker/rules/versioning.mdc` §A 完成资产采用、骨骼改名迁移（`joint_order`、正则组、工具、obs/action 文档同变更）、冻结版本退休及版本身份；不覆盖或解冻已训 v3，不刷新旧资产锁。正式管线核验交 `asset-tree-per-family`，不能以候选转换成功替代。
2. 跑当前版本的离线套件、驱动读回、行走静站承重检查、地形预检及 GUI 目视，绑定同一机体和配方。产物和判定写 S6 记录；红项先修复，不开训。
3. 向用户展示训练预算、工况、启动/评测命令与验收依据并确认。用户仅授权拆 work 不等于授权本步开训；预算或关键条件未批准置 blocked，保持可接手。
4. 按版本机制冻结并启动用户批准训练，记录实际 run、manifest/checkpoint 与偏离；检查工作树和启动协议，不能在缺锚状态假称可复现。
5. 固定具名新协议评测实际 checkpoint，分别检验速度/存活、行走形态、承重滑移与躯干拖尾；用户检查预览。不新增趴姿训练任务或起卧过渡。训练通过不自动代替姿势验收。
6. 回填 NOTES 的 run/报告指针与一句判定，所有数值结论进 `acceptance/records/<日期>-lizard2-s6-adoption-training.md`；执行者置 pending_review，新上下文按 close_when 审核。失败修复或明确拒绝，未完成动作不得以预算耗尽关闭。

## 关闭条件

- **审核者与输入**：执行者先置 pending_review；新上下文对照 S5/S6、已审上游交付和本项真实记录审核。
- **S5 交付**：阈值前置记录先于 D 最终比较，已审机体/驱动设计接入候选配方，新接触协议及标定落地，配置与协议产物可复读；仅阈值确认或配方构建通过不关闭。
- **S6 采用与验收**：正式机体采用、改名迁移、旧机体冻结版本退休及版本证据齐备；完成用户批准工况下的实际训练、固定协议评测与目视验收。旧 v3 判决不替代本项。
- **不采用出口**：用户明确不采用时记录理由与未完动作的去向，不把未验证说成通过。
- **结果处理**：完整交付经审核通过，或用户明确不采用，才关闭；可修缺口退 in_progress，预算未批准或用户设计决定缺失置 blocked。未完 S6 继续在办，不随 S5 关闭。

## 动作接口与奖励待办

- 部署端是否接受限位外位置参考仍待核对，由执行者整理实际部署行为或具名缺口；历史参考越限的诊断与撤回见步态记录，不能仅据参考越限决定裁剪。物理反曲禁区按 R4（`acceptance/records/2026-10-08-lizard2-joint-design-review-contract.md`）实施，不能用动作参考裁剪替代。
- 训练前合理性读数（2026-10-09）：初始动作分布对硬限位的越界率、以及 `robot.base_init_height` 与采用机体自然站高的差，都已量；两项都属配方改动（改则走 §B/§A），**当前不阻塞开训**。读数与判定归 `acceptance/records/2026-10-09-lizard2-v3-pretrain-sanity.md`（工具 `rl_exp/tools/verify/action_range_check.py`，离线无仿真）。
- `feet_slide` / `foot_clearance` 保留为奖励候选，先统一奖励与诊断的承重口径，再决定实现与权重。脚掌接触面积/形状项的排除依据、lf 异常撤回及历史因果边界见步态记录，不在本项复述读数。
- 姿态目标未验收时不直接新增角度监督；用户设计要求、量测结果与可训练目标的交接见整体记录及状态同步记录。
- 速度上限：先按整体记录“联动设计修订”消费 `lizard2-body-drive-candidate` 已审记录中的候选速度—载荷—跟踪/稳定包线与躯干/尾部结果，再选择明确不启用或有依据启用。旧 URDF 自报值、旧策略 p99 与 `check_actuator_budget.py --drive-audit` 均不能单独批准上限；启用须有限速/无限速同条件对照并核引擎采用，不启用须保留风险和工况边界。既有读数及生效字段机制只按 evidence 与 `check_dr_parity.py` 取用，不复制数值。

## 证据边界

历史判决按原协议与原机体解释，不自动外推到当前候选。最小运行自检、静态几何和执行器估算各有范围，不能替代完整周期、碰撞、承重动态或策略效果验证；已训旧版本的结果与当前版本的复现承诺按家族生命周期读取。

审核记录按整体记录“审核输入绑定约定”落地，本项只留已存在的记录指针。此次文档整改不执行 S5/S6，不读配方锁、不改未冻结新配方。
