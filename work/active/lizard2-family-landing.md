---
id: lizard2-family-landing
title: lizard2 配方、动作接口与评测协议交付
scope: rl_exp/versions/lizard2, rl_exp/tasks, rl_exp/tools/pipeline, rl_exp/tools/verify, ablation_harness
status: open
landing: rl_exp/versions/lizard2/main/main_params.yaml, rl_exp/tasks/lizard2_recipe.py, rl_exp/tools/pipeline/emit_diff_declaration.py, rl_exp/tools/verify/check_recipe_build.py
next: ① **评测入口已真跑验证**（2026-10-10）：`model_5999.pt` 在 `ablation_harness/protocols/lizard2_flat_v5.json` 下判决 pass、八闸全过、`invalid_reasons` 空、离线可从帧记录重导出；身份副本协议 + 锚点条目 + 三臂同尺用例见证据中的入口记录。读数与边界（6000 迭代短窗 ⇒ 只证入口可用与这一份判决，不证收敛）归 `acceptance/records/2026-10-10-lizard2-v3-first-eval.md`。② 消费 joint-limit-shape-and-range-pass 的设计决定；核对部署端对限位外位置参考的处理，形成动作接口提案。③ 统一奖励与诊断的承重口径后评审滑移/净空奖励：**低命令段站着有分这件事只是假设**（核是双侧惩罚）。分桶读数**已取**（归 `acceptance/records/2026-10-10-lizard2-v3-band-buckets.md`）：零命令带无非足接触、承重脚滑移 p90 随命令从 0.030 升到 3.235 m/s；**奖励侧那半仍缺**（帧里没有奖励项，逐带奖励分要另跑），采用与否待拍板。④ 速度上限读数**已出**（归 `acceptance/records/2026-10-10-lizard2-v3-joint-velocity-limits.md`，含同日勘误）：求解器持有 5.94e36 = 无限速，PLAY 窗**帧均**口径 **9/20** 腿关节 p99 越 URDF 限、最坏 **1.53×**（瞬时口径 11/20、2.66×，高出的部分来自 `kfe`/`foot` 子帧振铃），脊柱 2/10（最坏 1.66×）；是否启用有效限速待拍板（无限速臂对照 ⇒ 只能说会裁掉多少，不能说裁完会怎样）；"声明了但不生效的字段"已折进 `check_configclass_fields.py` 的 `INERT_VELOCITY_LIMITS`（改值/加 sim 上限即红，见 evidence 末条）。当前采用与剩余缺口见 acceptance/records/2026-10-09-lizard2-limit-requirement-and-status-sync.md，版本处理沿用 versioning.mdc，不再把已接入的 v3 当作待建版本
close_when: 动作接口与奖励决定落入对应版本的 PLAN、参数和差异声明，或明确不采用；新协议与 reader 绑定、报告清单有实现、阈值及固定场景经标定；对应训练候选完成构建和冻结前检查，结果有具名记录。未完设计由父事项承接，不以现有 v3 最小自检替代完整验收
evidence: acceptance/records/2026-09-23-lizard2-v1-gait-skate, acceptance/records/2026-09-29-lizard2-v2-eval, acceptance/records/2026-10-08-lizard2-v3-landing, acceptance/records/2026-10-09-lizard2-limit-requirement-and-status-sync, acceptance/records/2026-10-09-lizard2-v3-eval-entry-and-inert-velocity-field, acceptance/records/2026-10-09-lizard2-v3-pretrain-sanity, acceptance/records/2026-10-10-lizard2-v3-first-eval, acceptance/records/2026-10-10-lizard2-v3-band-buckets, acceptance/records/2026-10-10-lizard2-v3-joint-velocity-limits, acceptance/records/2026-10-10-lizard2-carrier-dwell-calibration
---

## 当前范围与交接

本项交付配方、动作接口与评测协议；参考动作、资产几何、接触要求、限位与命令窗口设计由 `work/active/joint-limit-shape-and-range-pass.md` 承接。当前版本设计入口为 `rl_exp/versions/lizard2/PLAN.md`，正式接入与验证结果只引用 evidence。版本修订、换体与锁处理消费 `.codemaker/rules/versioning.mdc` §A/§B，不另定版本规则。

## 动作接口与奖励待办

- 部署端是否接受限位外位置参考仍待核对，由 Codex 整理实际部署行为或具名缺口；历史参考越限的诊断与撤回见步态记录，不能仅据参考越限决定裁剪。物理反曲禁区按父事项 landing 的 R4 实施，不能用动作参考裁剪替代。
- 训练前合理性读数（2026-10-09）：初始动作分布对硬限位的越界率、以及 `robot.base_init_height` 与采用机体自然站高的差，都已量；两项都属配方改动（改则走 §B/§A），**当前不阻塞开训**。读数与判定归 `acceptance/records/2026-10-09-lizard2-v3-pretrain-sanity.md`（工具 `rl_exp/tools/verify/action_range_check.py`，离线无仿真）。
- `feet_slide` / `foot_clearance` 保留为奖励候选，先统一奖励与诊断的承重口径，再决定实现与权重。脚掌接触面积/形状项的排除依据、lf 异常撤回及历史因果边界见步态记录，不在本项复述读数。
- 姿态目标未验收时不直接新增角度监督；用户设计要求、量测结果与可训练目标的交接见父事项及状态同步记录。
- 速度上限：yaml 里 implicit actuator 的旧 `velocity_limit` 字段不进引擎（v1/v2/v3 同款继承，读数边界见 v3 落地记录的未覆盖边界）。先出"PLAY 窗 `joint_vel` 对 URDF 自带速度上限"的读数，再决定要不要启用有效限速（**是否启用**是本项的决策）；"yaml 声明的字段必须与引擎采用的一致"那半条连同断言落点 = `rl_exp/tools/verify/check_dr_parity.py` 第 5 条（覆盖唯一性 + urdf 列 readout；原事项已于 2026-10-09 关闭，见 `work/closed/2026/actuator-params-audit.md`），不在这里留第二份。

## 评测协议交付

产品协议、报告清单与阈值归本项；采集、指标和执行机制归 `work/closed/2026/baseline-eval-pipeline-restructure.md`。机制可用后发布协议，不形成互等关闭。

- 新协议覆盖脚底相对地面的净空、足端相对机身的前后摆幅、承重地面接触点切向速度；逐项绑定实现。几何近似与有效样本必须可追溯，不用刚体原点净空或刚体线速度替代足底/接触点量。
- 整理 `report_only` 实现清单，移除 `dof_torque_frac_of_limit`（关节力矩留专项采集），未实现的 `foot_yaw_deg` 不进入新清单。清单收窄或新增验收 criteria 走新协议文件，冻结旧协议和报告摘要保持不变。
- 由用户确认摆动脚数量、净空、摆幅与滑移容限；Codex 提交定义、阈值依据及正常/异常标定样本，结果唯一进验收记录。**容限决策的输入已备（2026-10-10）**：摆动脚数与净空/摆幅/滑移的逐带分布归 `acceptance/records/2026-10-10-lizard2-v3-band-buckets.md`（滑移 p90 0.030→3.235 m/s 随命令单调升、净空 p05 0.8–1.9 mm），容限值本身仍待拍板。
- `no_non_foot_carrier` 的"持续部分承重"档：2026-10-10 用同机体未训练塌陷样本补了一档，但它是**高幅值/短时长**（连续越限最长 6 帧、dwell 25 帧）⇒ 只钉住**时长轴**，**档位轴仍缺**，不能拿它冒充；补法（浅压 + 保持 ≥1 s 且落帧）见 `acceptance/records/2026-10-10-lizard2-carrier-dwell-calibration.md`。门槛仍为协议现值。
- 新协议声明固定命令序列、速度带、等待窗与覆盖要求，并按新场景采集，不将历史随机场景读数当作新证据。
- v3 的身份副本协议**已交付**（判据逐字段同 v4，只换 `recipe`/版本与身份说明）；三处登记点＝文件本身、`protocol_anchors.json`（覆盖由 `protocols/` 目录推出 ⇒ 放进目录即被闸门要求，改表＝人工批准，理由必填）、`test_baseline_contract.py` 的 lizard2 臂表（现三条；`report_only` 显式豁免，其余键不同即红）。**入口已真跑验证（2026-10-10）**：判决 pass、八闸全过、离线可从帧记录重导出，读数归 `acceptance/records/2026-10-10-lizard2-v3-first-eval.md`；协议号与配方号是两个命名空间，别互推。

## 证据边界

历史判决按原协议与原机体解释，不自动外推到当前候选。最小运行自检、静态几何和执行器估算各有范围，不能替代完整周期、碰撞、承重动态或策略效果验证；已训旧版本的结果与当前版本的复现承诺按家族生命周期读取。
