---
id: lizard2-family-landing
title: lizard2 配方、动作接口与评测协议交付
scope: rl_exp/versions/lizard2, rl_exp/tasks, rl_exp/tools/pipeline, rl_exp/tools/verify, ablation_harness
status: open
landing: rl_exp/versions/lizard2/main/main_params.yaml, rl_exp/tasks/lizard2_recipe.py, rl_exp/tools/pipeline/emit_diff_declaration.py, rl_exp/tools/verify/check_recipe_build.py
next: 消费 joint-limit-shape-and-range-pass 的设计决定；核对部署端对限位外位置参考的处理，形成动作接口提案；统一奖励与诊断的承重口径后评审滑移/净空奖励；交付新评测协议、实现清单与阈值标定。当前采用与剩余缺口见 acceptance/records/2026-10-09-lizard2-limit-requirement-and-status-sync.md，版本处理沿用 versioning.mdc，不再把已接入的 v3 当作待建版本
close_when: 动作接口与奖励决定落入对应版本的 PLAN、参数和差异声明，或明确不采用；新协议与 reader 绑定、报告清单有实现、阈值及固定场景经标定；对应训练候选完成构建和冻结前检查，结果有具名记录。未完设计由父事项承接，不以现有 v3 最小自检替代完整验收
evidence: acceptance/records/2026-09-23-lizard2-v1-gait-skate, acceptance/records/2026-09-29-lizard2-v2-eval, acceptance/records/2026-10-08-lizard2-v3-landing, acceptance/records/2026-10-09-lizard2-limit-requirement-and-status-sync
---

## 当前范围与交接

本项交付配方、动作接口与评测协议；参考动作、资产几何、接触要求、限位与命令窗口设计由 `work/active/joint-limit-shape-and-range-pass.md` 承接。当前版本设计入口为 `rl_exp/versions/lizard2/PLAN.md`，正式接入与验证结果只引用 evidence。版本修订、换体与锁处理消费 `.codemaker/rules/versioning.mdc` §A/§B，不另定版本规则。

## 动作接口与奖励待办

- 部署端是否接受限位外位置参考仍待核对，由 Codex 整理实际部署行为或具名缺口；历史参考越限的诊断与撤回见步态记录，不能仅据参考越限决定裁剪。物理反曲禁区按父事项 landing 的 R4 实施，不能用动作参考裁剪替代。
- `feet_slide` / `foot_clearance` 保留为奖励候选，先统一奖励与诊断的承重口径，再决定实现与权重。脚掌接触面积/形状项的排除依据、lf 异常撤回及历史因果边界见步态记录，不在本项复述读数。
- 姿态目标未验收时不直接新增角度监督；用户设计要求、量测结果与可训练目标的交接见父事项及状态同步记录。

## 评测协议交付

产品协议、报告清单与阈值归本项；采集、指标和执行机制归 `work/closed/2026/baseline-eval-pipeline-restructure.md`。机制可用后发布协议，不形成互等关闭。

- 新协议覆盖脚底相对地面的净空、足端相对机身的前后摆幅、承重地面接触点切向速度；逐项绑定实现。几何近似与有效样本必须可追溯，不用刚体原点净空或刚体线速度替代足底/接触点量。
- 整理 `report_only` 实现清单，移除 `dof_torque_frac_of_limit`（关节力矩留专项采集），未实现的 `foot_yaw_deg` 不进入新清单。清单收窄或新增验收 criteria 走新协议文件，冻结旧协议和报告摘要保持不变。
- 由用户确认摆动脚数量、净空、摆幅与滑移容限；Codex 提交定义、阈值依据及正常/异常标定样本，结果唯一进验收记录。
- 补齐 `no_non_foot_carrier` 的持续部分承重标定，再决定门槛；新协议声明固定命令序列、速度带、等待窗与覆盖要求，并按新场景采集，不将历史随机场景读数当作新证据。

## 证据边界

历史判决按原协议与原机体解释，不自动外推到当前候选。最小运行自检、静态几何和执行器估算各有范围，不能替代完整周期、碰撞、承重动态或策略效果验证；已训旧版本的结果与当前版本的复现承诺按家族生命周期读取。
