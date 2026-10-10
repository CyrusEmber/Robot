---
id: lizard2-body-drive-candidate
title: lizard2 机体与驱动候选：蜥蜴骨段朝向、人手式足掌、骨骼改名
scope: rl_exp/blender, rl_exp/tools/pipeline, rl_exp/tools/verify, rl_exp/tools/diagnose, rl_exp/tasks, acceptance/records
status: open
landing: rl_exp/blender/lizard2_stance_candidate.py, rl_exp/blender/generate_urdf.py, rl_exp/tools/diagnose/gait_probe.py
next: E 名表单点化先做（改名前置，与 B 能力表同时）；A/B/C 三节无先后依赖，可同时开始，A 的 Blender 改造用新名表；B 的能力表先出（小，供 A 选 pivot/轴），C 沿用现有机体不等 A。全部节自检完成后做 D 集成，一份记录，置 pending_review，请新上下文一次性审核。不动已训 v3，不覆盖 rl_exp/lizard2_candidate/，趴姿不在本项。
close_when: 新上下文对照 R1–R5 与本项 D 节记录审核：蜥蜴骨段朝向正反例、前后肢映射与改名落地一致、同一候选的完整周期（有向掌面、限位、实际网格碰撞）、承重动力学与真实驱动读回、躯干/尾部同条件对照；你确认候选外观与目标动作。通过后交 lizard2-family-landing；失败退回 in_progress 并指明节，只有用户能给的缺口置 blocked。静力/声明/源码支持不当动力学通过；未判定不关闭。
evidence: acceptance/records/2026-10-10-lizard2-land-body-drive-overall-work, acceptance/records/2026-10-08-lizard2-joint-design-review-contract, acceptance/records/2026-10-08-lizard2-r1-numeric-reference-and-decision-drafts
---

本项取代按 S0–S4 串联、逐级审核的安排：各节自检只用机器闸门与可复读检查，不置 `pending_review`；只在 D 集成后审核一次。需求与范围唯一归整体记录，判据归 R1–R5，本项只留动作、交付与顺序。

## 目标：蜥蜴骨段朝向，不只是防内扣

用户目标（2026-10-10）：把肢体变成蜥蜴的骨骼姿态朝向，从而消除小腿内扣、更像巨蜥。判据为骨段方位而不是单个角度禁区：上臂/股骨外展并向后、肘/膝朝外、前臂/小腿近垂直落地、掌/跖朝前；内扣姿态作为反例保留。方位角、仰角、体高/骨长比例的量化与容差先于比较确定，复用 `check_leg_reachability.py`、`fit_gait_target.py` 的口径，不按现资产误差倒定。已被旧 A/B 比较拒绝的目标/机体组合不重跑，见 R1 草案 §15–§17；动物资料的访问受限、视频身份失败与足端可读量边界见同草案 §7–§10，不重试被拒访问、不靠猜关节点拼曲线（并不表示所有动物资料路线永久不可行）。机体读数前复读 `check_leg_reachability.py --self-check` 与整体记录“必须纠正的既有踝部分析”，工具通过不当设计通过；设计不变量（反曲/翻掌/穿透禁区）与测量精度在此确认，具体边界随候选几何复核。

## 骨骼改名（用户拍板：2026-10-10）

前后肢分名，覆盖整体记录“沿用现有名称”的候选起点。链：肩带 → 上臂/股骨 → 肘/膝 → 前臂/胫段 → 腕/踝 → 掌/跖段 → 指/趾根 → 末端接触片。

| 旧词根 | 前肢 | 后肢 |
|---|---|---|
| hip（竖直轴前后摆） | shoulder_swing | hip_swing |
| haa（外展升降） | shoulder_abduct | hip_abduct |
| hfe（肘/膝屈伸） | elbow | knee |
| kfe（腕/踝屈伸） | wrist | ankle |
| foot（指/趾根） | finger | toe |

腿前缀（lf/rf/rl/rr）、`_joint` 后缀与躯干/颈/尾名不变。新增掌跖段与接触片的 link 名由执行者随名表一并提出，不另造命名体系。

- 改名走与 v8 同类的一次性迁移，不留旧名别名；候选（新名）与现行（旧名）并存期间，工具必须两边都可用，所以先做下面的“E. 名表单点化”。
- 候选在隔离路径生成；`joint_order`、正则组、工具、obs/action 文档在采用时同变更迁移。这是机体换代：采用时 lizard2 仍加载旧机体的冻结版本须同一次变更退休（`versioning.mdc` §A），归 `lizard2-family-landing` S6。

## E. 名表单点化（改名前置，先做，与 B 能力表同时）

2026-10-10 实测（grep `rl_exp`、`ablation_harness` 的 `.py`，未含 yaml/json/md）：词根硬编码散在约 25 个文件，且同一份词根表被各自抄写至少 7 份（`check_joint_layout.py`/`check_self_collision.py`/`gait_probe.py` 的 `_LEG_TOKENS`、`check_leg_reachability.py` 的 `CHAIN`、`plot_joints.py` 的 `JOINTS`、`baseline_metrics.py`/`baseline_eval.py` 的 `_LEG_TOKENS`）。分布：

- Blender：`build_rig.py`、`fix_bones.py`、`generate_urdf.py`、`lizard2_stance_candidate.py`。`rename_flip_v8.py`、`rotate_rig.py`、`tools/pipeline/migrate_joint_names_v8.py`、`tools/archive/patch_stance.py` 为历史一次性脚本，不改。
- 任务：`tasks/lizard2_env_cfg.py`（驱动分组正则）、`tasks/teacher_mdp.py`（`.*_foot` 接触体）。
- 诊断：`debug_pose.py`、`diag_metrics.py`、`diagnose_support.py`、`gait_probe.py`、`plot_joints.py`、`stance_step_probe.py`。
- 校验：`baseline_probe.py`、`check_actuator_budget.py`、`check_contact_ownership.py`、`check_dr_parity.py`（自测样例）、`check_joint_layout.py`、`check_leg_reachability.py`、`check_self_collision.py`、`fit_gait_target.py`、`obs_protocol_live.py`、`test_baseline_contract.py`。
- 评测：`ablation_harness/baseline_eval.py`、`baseline_metrics.py`；协议 JSON 里的接触体名、yaml 的 `joint_order` 与正则组、OBS 等文档另行 grep。

动作：

1. 新建一个纯标准库的名表模块（Blender 的 Python 与 IsaacLab 解释器都能导入）；落点先查 `rl_exp/tools` 下现有共享模块的惯例，不另立体系。内容是：腿前后分组、关节词根按前/后肢的新旧对应、链顺序。各工具改为读它，删除各自抄写的词根表。
2. 工具读取名表时按所面对的机体（新/旧）取名，不靠字符串猜；旧名机体上全部现有自测与闸门必须保持绿，新名只在候选上启用。
3. 这是改名前置，不是独立交付：不单独审核，随 D 一起审；但完成后须有一条最小自检——用新、旧两套名分别通过链顺序与前后肢分组。

**接触体名（用户拍板：2026-10-10）：跟新词根。** 现状：`lf_foot_joint` 是关节，它的子 link `lf_foot` 是末端接触体，两者同名，传感器、`.*_foot` 正则、协议 JSON、各诊断都按这个 link 名找脚。本仓约定 link 与其父关节同词根，故末端接触 link 随关节改为前肢 `*_finger`、后肢 `*_toe`，不另设例外。Isaac Lab 框架本身不固定名字（ANYmal 用 `.*FOOT`，Unitree/Spot 用 `.*_foot`，人形用 `*toe*`/`*ankle*`，奖励与传感器均取 `body_names` 参数），所以无框架默认可依，只改本仓。代价：
- 前后肢接触 link 名不同，凡按脚找接触体处不再用单一 `.*_foot`，改读名表给出的接触体集合（前肢 finger、后肢 toe）；这是名表模块必须提供的接口之一。
- 传感器配置、奖励、诊断、协议 JSON 的接触体名随名表同变更迁移；旧协议与历史评测读数按旧机体解释，不改写。
- 新增掌跖段的 link 名由执行者随名表提出，须与上述约定一致（掌/跖段随腕/踝关节词根）。

## A. 机体候选（Blender，可立即开始）

1. 在隔离的 `lizard2_stance_candidate.py` / `generate_urdf.py` 路径里改骨架：蜥蜴朝向的肩/髋、肘/膝、腕/踝，掌跖段为连续骨段，指/趾根 pivot 放在掌跖段远端，接触端是小接触片；先沿用关节数，不先增轴。
2. 选 pivot/轴及弹性方案前取 B 的能力表（能力表出之前只核对现几何，不定轴、不承诺渐硬弹性）；前后肢分别镜像，核对骨头/网格归属、碰撞体与惯量。
3. 导出 URDF，用 `convert_urdf.py` 实际接口转隔离 USD；核对 DCC—URDF—USD 的关节树、名称与新名表一致。预览多视角；零号对照：现有链 + 主动腕踝，用以判断新掌跖段是否值得。

## B. 驱动（能力表先出，可与 A 同时）

1. 调查当前 fork 的原生弹簧、限位、执行器、物理子步接口，出一页具名能力表：可表达恢复力、更新频率、力矩/限速入口、依据（源码/文档/运行）与未知项。线性 implicit PD 不冒称非线性弹性；缺渐硬实现则保留线性对照或暂缓弹性分支。复用现有实现，不新建驱动机制。
2. A 给出候选后，在隔离诊断配置里实现腕踝与趾根驱动（分组，不整组降低 PD），与同几何线性基线比较偏转回位、承载与推进。读回与力矩能力分开，PD 请求量、估算与引擎实际量分开。
3. 速度上限按整体记录“联动设计修订”第 4 条：启用须有速度—载荷—跟踪/稳定包线和同条件有/无限速对照，否则明确不启用并写工况边界。

## C. 躯干侧弯与拖尾（沿用现有机体，可立即开始）

1. 区分根机身 heading、胸部侧弯、颈方向、尾 yaw/pitch；先用现有通道表达，不默认新增脊柱轴。
2. 同速度、同足部目标、同载荷下与无协同基线比较；每次只变一类参数。记录机身偏航/侧倾、侧向重心与速度、四足相位和载荷、尾根/中/尖接触位置与法向/切向作用。
3. 行走期允许拖尾，不允许尾巴拖住身体、头腹代替足部推进，或靠滑移维持速度。出口：获准协同、拒绝、或未判定；机体变化后受影响项在 D 重验。

## D. 集成与审核（A、B、C 就绪后）

1. 同一候选跑完整支撑—摆动周期的几何与实际网格碰撞（`check_leg_reachability.py`、`check_self_collision.py`，新布局有硬编码时最小修复并留回归），再跑承重动力学：关节变形、原点移动、真实接触点滑动与滚动分开记（口径见整体记录“联动设计修订”第 2 条，样本对拍归 `lizard2-contact-protocol`）。
2. 失败修复在对应节内迭代；几何失败回 A，不放宽容差，不直接归因奖励；目标变动须用户确认。
3. 记录进 `acceptance/records/<日期>-lizard2-body-drive-candidate.md`，按“审核输入绑定约定”列明消费的上游输入；存在后补 evidence。性能阈值（步幅、滑移、柔顺）只给标定依据，最终由 `lizard2-family-landing` S5 在比较前经用户确认并固定。

## 边界

不训练、不调正式增益、不改已训 v3、不读写配方锁正文、不新增机器闸门；旧 checkpoint 只作影响诊断。静态趴姿归 `lizard2-prone-posture`，游泳不在本轮。
