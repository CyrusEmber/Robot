---
id: lizard2-family-landing
title: lizard2 v1 步态验收缺口与 v2 配方决策
scope: rl_exp/versions/lizard2, rl_exp/tasks, rl_exp/tools/pipeline, rl_exp/tools/verify, ablation_harness
status: open
landing: rl_exp/versions/lizard2/main/main_params.yaml, rl_exp/tasks/lizard2_recipe.py, rl_exp/tools/pipeline/emit_diff_declaration.py, rl_exp/tools/verify/check_recipe_build.py
next: ① **动作接口边界：已收窄为"等 (c)"** —— 保留接口；(a)(b) 两问与 (b) 的"只是从一种饱和换成同一种饱和"都有读数（步态记录 ⑨/⑩），**(c) 部署端是否接受限位外位置参考不在本仓**，待它与后续验收证据再定是否约束参考。② **奖励变更归属**：`v1` 已训练并锚定，任何 reward/action 配方变更都进 `lizard2/main/v2` —— 而 **v2 已建、已训完（10000 迭代）并出判决**（`acceptance/records/2026-09-29-lizard2-v2-eval.md`）⇒ 在这之上的奖励变更须开 **v3**，不能按 v2 开训前修订处理；候选项已收敛为 `feet_slide` / `foot_clearance` 两项——**脚掌接触面积/形状项已排除**（记录 ⑪ 及其"四脚求和必然罚抬脚、饱和只修脚内不修脚间"的机理），前置是**统一承重门**（`foot_slip_v1` 的 `foot_fraction ≥ min_load` 与探针的 `net_z > 1 N` 不同源）。④⑤⑥⑦ 四条出口属**协议升级**：`lizard2_flat_v2.json` 已按 sha256 锚定，不能就地在它上面收窄 `report_only`（**同一条规则已在 2026-09-29 用过一次：报告项变更走新协议文件 v4**）。实测与撤回项见 `acceptance/records/2026-09-23-lizard2-v1-gait-skate.md`。**2026-09-29 起本项与他项的分工**：资产几何/需求（踝轴与行程）归 `pad-flat-requirement-and-ankle-axis` 与 `stride-axis-range-vs-speed`，本项只留配方与接口。
close_when: 动作边界和奖励方案决定落入 v2 的 PLAN、参数与差异声明；新步态协议使用已核验的三项行为量并完成阈值标定；v2 通过配方构建与冻结前检查，形成可复现的训练候选。训练结果另按 v2 NOTES 回填。
evidence: acceptance/records/2026-09-23-lizard2-v1-gait-skate, acceptance/records/2026-09-23-lizard2-v1-first-eval, acceptance/records/2026-09-22-lizard2-family-landing, acceptance/records/2026-09-22-family-landing-decoupled, acceptance/records/2026-09-22-lizard2-stride-at-load, acceptance/records/2026-09-22-lizard2-declarations-and-plan, acceptance/records/2026-09-22-lizard2-self-collision-sweep, acceptance/records/2026-09-22-lizard2-actuator-capability, acceptance/records/2026-09-22-lizard2-probe-observer-fixes
---

## 问题与本次范围

新家族 `lizard2` 已从旧资产落到"可建 env、能过资产/注册/锁三级闸门"。本项收**落成的尾与债**：
契约声明、差异论证、开训前检查。不含训练，不含旧家族的资产或锁。

## 评测协议交付

**新协议版本、报告清单与产品阈值归本项；采集、指标和执行机制归 `work/closed/2026/baseline-eval-pipeline-restructure.md`（2026-09-23 已关闭）。**
本项在机制可用后发布协议，不以机制总项关闭为前置；总项消费本节交付验收，不形成互等关闭的环。

- 消费足端采集和指标能力，在新协议定义并验收三项行为量：脚底相对地面的净空、足端相对机身的前后摆幅、承重地面接触点的切向速度。不得把足部刚体原点相对本次最低 z 的变化称为抬脚净空，也不得把足部刚体速度直接称为接触点滑移；接触点无法直接取得时，须记录采用的几何近似与有效样本。产品阈值和正常/异常标定样本进验收记录，再由新 reader 使用；奖励调整与重训另议。
- 收窄新协议的 `report_only`：明确移除 `dof_torque_frac_of_limit`，关节力矩留作专项采集；未实现的
  `foot_yaw_deg` 也不进入新清单。其余名称逐项对照实现；严格完整性由新 reader 强制，冻结旧协议不改写。
- 所有者确定摆动脚数量、脚底净空、前后摆幅与接触点滑移容限；定义、阈值依据和正常/异常对照样本只进验收记录，不在机制项再定一套。
- 补齐 `no_non_foot_carrier` 的持续部分承重标定样本，再决定对应门槛，不用现有异常读数直接定允许值。
- 在新协议声明固定命令序列、速度带、等待窗及覆盖要求，消费机制项的驱动与覆盖检查；新条件重新采集，
  不把旧随机重采样结果当成新场景证据。

本节出口：新协议与新 reader 绑定、报告清单全有实现、产品口径有依据、固定场景真跑可验；原判决仍按原协议可复读。**收窄 `report_only` 与把三项行为量写进 `criteria` 都需要新的协议版本**：`lizard2_flat_v2.json` 已由 `protocol_anchors.json` 按 sha256 锚定、四份报告带该 digest ⇒ 不得就地在它上面改；旧协议的 `why_*` 保持逐字节不变。

## 当前待决定

1. **动作接口边界**（范围已按证据收窄；读数与撤回见步态记录 ⑦ 第 6–8 条、⑨、⑩，本处不复述）：位置 PD 下更远的参考本身就是产生驱动力的手段 ⇒ **"参考越限"不等于"接口有缺陷"，也不等于该裁剪**。最小核查的三问里 **(a)(b) 已有读数，(b) 的"只是从一种饱和换成同一种饱和"已被排除**（⑩）；**第三问 (c) 未答且不在本仓**——部署端是否接受限位外参考（或自行裁剪/拒绝），训练必须匹配真正的部署行为。⇒ 待决定的是：按 (c) 的答案与后续验收证据再定是否约束参考；**在那之前保留接口**，验收侧仍按要求单列"参考超出范围的部分"。
2. **奖励变更归属**：`v1` 已训练并有结果锚点，依 `.codemaker/rules/versioning.mdc` §A/§B，修改 `feet_slide` / `foot_clearance` 属已训配方变更。v2 目录已建、已训完并出判决（见 `next` ② 的指针）⇒ **本轮变更须开 `lizard2/main/v3`**，不能按 v2 开训前修订处理。候选**收敛为这两项**：脚掌**接触面积/形状**项已排除——四脚求和必然惩罚正确抬脚、饱和只修脚内不修脚间、只评估承重脚仍留"把重量压到最平那只脚"的漏洞（判断与读数见步态记录 ⑪）。待决定的是这两项的实现、权重与 v2 验收；**前置**是统一承重门（`foot_slip_v1` 的 `foot_fraction ≥ min_load` 与探针的 `net_z > 1 N` 不同源，见该记录"未覆盖边界"）。v1 的奖励与结果保持可复读。

**lf（左前）异常已撤回**：不得再把一阶目标预测中的负净空解释为“目标要求入地”；摆动中段实测净空三档均高于 rf，符号翻转来自线性修正项。复核方法与撤回依据见步态记录 ⑧。后续读一阶预测须区分相位和瞬时修正量，不能把瞬时量当作姿态。

## 当前状态

2026-09-22 完成（细节见四条 `evidence` 记录，本处不复制数值）：

- **与任何历史家族解耦**：`declare_family.py` 的参照家族依赖整条删除；零漂移保护改为"目标家族之外的全部家族"
  逐字节比对且锁更新限定目标；通用闸门的检查项改由**声明**决定（资产契约只查 yaml 自己声明的键、只查 `active` 线；
  对拍对象搬进 `versions/freeze_parity.json`）。
- **新骨骼的运行时证据**：承重姿态下四腿髋的前后行程一致且远超旧构型；动作覆盖与 obs 宽度均有实测；
  `check_joint_layout.py` 改为按资产推导腿部关节/力臂并新增弦长断言。
- **声明与论证**：`EXPECTED_DIFFS` 等三处计数钉、obs 声明两任务 + 102 宽度按资产键实测批准（缺宽度/缺解析成静态红）、
  9 条 env + 43 条 agent 理由（再生成保留原文，值变化打 REVIEW 标记）。
- **探针的观测口径收口**（2026-09-22，评审后）：压头真的下发 + 头链用关节状态钉住、力/项值复位前同帧读、
  终止集合改为 yaml 点名 + 等号判、死条目（无碰撞网格的 yaw 连杆）单独清理并重钉 golden/lock、零动作出帧供目视；
  头守卫触发的**边界两半**已测（离地 18 帧静默 → 触地帧 1108.12 N 同帧触发），并由接触刚度（≈4×10⁶ N/m）
  得出该阈值是**接触检测器**而非力门限。读数与边界见 `evidence` 的 probe-observer-fixes 记录。
- **PLAN 写满**：硬前置 5 条、固定窗口、主轴 7 条判据（四个种类待新增）、非足承重两条判据、8 条风险与 4 条判废线；
  当前未决事项收敛为上列动作接口边界与奖励方案。**终止条件 2026-09-22 加一条**：`head_contact`（`chest_.*`/`neck_.*` > 1.0 N，框架
  `illegal_contact`，不加 dwell）——旧线 v1 就是被"压着脖子走"拖垮的（66% 的帧压在 10% 体重之上、却从未连续
  超过 0.22 s，dwell 型承重判据拦不住，接触判据可以）；连带重钉 golden/v1 锁、路径 64→65、计数钉 107→108。
  `v1` 已于 2026-09-22 开训（`--max_iterations 14000`，4096 envs，跑满）并于 2026-09-23 出首次判决
  （`model_13999`，256 envs/seed123：**pass 八条全过**）；锚点为 `lizard2-main-v1.6`。

## 未覆盖边界

判定口径**已写、已冻结、已出判决**（记录见 `2026-09-23-lizard2-v1-first-eval`），但判决是**开训之后**做的，
且那一轮改了尺子（两处缺陷 + 一处 GPU 专用 bug）；协议 `report_only` 的清单仍大于实际产物；
执行器能力曲线与自碰撞检查有读数（硬前置 4/5），但都是**估算 + 静态姿态**口径，不是承重动态；
理由写的是"这版为什么这样"，不是"数值对不对"；obs 宽度变化的活体重建只覆盖**声明过的键**；
行程是纯运动学读数。本轮离线套件全绿。
