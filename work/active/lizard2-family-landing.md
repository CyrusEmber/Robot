---
id: lizard2-family-landing
title: lizard2 配方、动作接口与评测协议交付
scope: rl_exp/versions/lizard2, rl_exp/tasks, rl_exp/tools/pipeline, rl_exp/tools/verify, ablation_harness
status: open
landing: rl_exp/versions/lizard2/main/main_params.yaml, rl_exp/tasks/lizard2_recipe.py, rl_exp/tools/pipeline/emit_diff_declaration.py, rl_exp/tools/verify/check_recipe_build.py
next: 消费 joint-limit-shape-and-range-pass 的整体记录 S5–S6：设计批准后交付腕踝动作与驱动、必要最小奖励、有效限速和下一版本接入；新评测区分足部承重、允许尾部接触与禁止腹/头等异常承重，补固定场景及阈值标定。已有 v3 入口、分桶、限速和载荷对照只按 evidence 取用，不把旧判决当新步态验收；承重口径与部署端参考处理继续核对。本轮只同步 work，不改配方、协议或启动训练。
close_when: 获准设计的动作、驱动、奖励、限速和版本决定进入 PLAN、参数与差异声明，或逐项明确不采用；新接触协议与 reader 绑定、阈值和固定场景有标定证据，训练候选完成构建及冻结前检查。执行者置 pending_review，新上下文对照 S5–S6、落点和原始证据审核；用户确认选择及训练工况。未完设计留父事项，不以旧 v3 判决或最小自检关闭。
evidence: acceptance/records/2026-10-10-lizard2-land-body-drive-overall-work, acceptance/records/2026-09-23-lizard2-v1-gait-skate, acceptance/records/2026-09-29-lizard2-v2-eval, acceptance/records/2026-10-08-lizard2-v3-landing, acceptance/records/2026-10-09-lizard2-limit-requirement-and-status-sync, acceptance/records/2026-10-09-lizard2-v3-eval-entry-and-inert-velocity-field, acceptance/records/2026-10-09-lizard2-v3-pretrain-sanity, acceptance/records/2026-10-10-lizard2-v3-first-eval, acceptance/records/2026-10-10-lizard2-v3-band-buckets, acceptance/records/2026-10-10-lizard2-v3-joint-velocity-limits, acceptance/records/2026-10-10-lizard2-carrier-dwell-calibration
---

## 当前范围与交接

本项消费整体记录 `acceptance/records/2026-10-10-lizard2-land-body-drive-overall-work.md` 的 S5–S6，交付配方、动作接口、驱动接入、新接触评测与训练候选；参考动作、骨骼、完整周期与驱动验证由 `work/active/joint-limit-shape-and-range-pass.md` 统筹。当前版本入口为 `rl_exp/versions/lizard2/PLAN.md`，本轮不建立或采用新版本。版本及资产采用消费 `.codemaker/rules/versioning.mdc` §A/§B。

拖尾与新增掌跖段承重须进入新协议的具名接触分组；允许尾触地不等于放行腹部、头部或异常非足承重。数值依据归 evidence，姿态与驱动方案尚未批准时不先写死奖励。

## 动作接口与奖励待办

- 部署端是否接受限位外位置参考仍待核对，由执行者整理实际部署行为或具名缺口；历史参考越限的诊断与撤回见步态记录，不能仅据参考越限决定裁剪。物理反曲禁区按父事项 landing 的 R4 实施，不能用动作参考裁剪替代。
- 训练前合理性读数（2026-10-09）：初始动作分布对硬限位的越界率、以及 `robot.base_init_height` 与采用机体自然站高的差，都已量；两项都属配方改动（改则走 §B/§A），**当前不阻塞开训**。读数与判定归 `acceptance/records/2026-10-09-lizard2-v3-pretrain-sanity.md`（工具 `rl_exp/tools/verify/action_range_check.py`，离线无仿真）。
- `feet_slide` / `foot_clearance` 保留为奖励候选，先统一奖励与诊断的承重口径，再决定实现与权重。脚掌接触面积/形状项的排除依据、lf 异常撤回及历史因果边界见步态记录，不在本项复述读数。
- 姿态目标未验收时不直接新增角度监督；用户设计要求、量测结果与可训练目标的交接见父事项及状态同步记录。
- 速度上限：yaml 里 implicit actuator 的旧 `velocity_limit` 字段不进引擎（v1/v2/v3 同款继承，读数边界见 v3 落地记录的未覆盖边界）。先出"PLAY 窗 `joint_vel` 对 URDF 自带速度上限"的读数，再决定要不要启用有效限速（**是否启用**是本项的决策）；"yaml 声明的字段必须与引擎采用的一致"那半条连同断言落点 = `rl_exp/tools/verify/check_dr_parity.py` 第 5 条（覆盖唯一性 + urdf 列 readout；原事项已于 2026-10-09 关闭，见 `work/closed/2026/actuator-params-audit.md`），不在这里留第二份。

## 评测协议交付

产品协议、报告清单与阈值归本项；采集、指标和执行机制归 `work/closed/2026/baseline-eval-pipeline-restructure.md`。机制可用后发布协议，不形成互等关闭。

- 新协议覆盖脚底相对地面的净空、足端相对机身的前后摆幅、承重地面接触点切向速度；逐项绑定实现。几何近似与有效样本必须可追溯，不用刚体原点净空或刚体线速度替代足底/接触点量。
- 整理 `report_only` 实现清单，移除 `dof_torque_frac_of_limit`（关节力矩留专项采集），未实现的 `foot_yaw_deg` 不进入新清单。清单收窄或新增验收 criteria 走新协议文件，冻结旧协议和报告摘要保持不变。
- 由用户确认摆动脚数量、净空、摆幅与滑移容限；执行者提交定义、阈值依据及正常/异常标定样本，结果唯一进验收记录。逐带分布输入见 `acceptance/records/2026-10-10-lizard2-v3-band-buckets.md`，不在本项复述读数；容限仍须按新目标和工况确定。
- `no_non_foot_carrier` 的持续部分承重档仍须补齐幅值标定；既有样本、复读方法和缺口见 `acceptance/records/2026-10-10-lizard2-carrier-dwell-calibration.md`。新协议须分别标定允许尾触地与异常载荷，不能直接沿用旧分组。
- 新协议声明固定命令序列、速度带、等待窗与覆盖要求，并按新场景采集，不将历史随机场景读数当作新证据。
- v3 入口与协议身份交付只按 `acceptance/records/2026-10-10-lizard2-v3-first-eval.md` 和 evidence 中的入口记录取用；本轮新增接触及步态目标须另交新协议、锚点与用例，不能据旧入口可用或旧判决替代。协议号与配方号独立，不互推。

## 证据边界

历史判决按原协议与原机体解释，不自动外推到当前候选。最小运行自检、静态几何和执行器估算各有范围，不能替代完整周期、碰撞、承重动态或策略效果验证；已训旧版本的结果与当前版本的复现承诺按家族生命周期读取。
