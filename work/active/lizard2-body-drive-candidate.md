---
id: lizard2-body-drive-candidate
title: lizard2 机体与默认关节驱动候选：肩髋三轴、足掌连接与躯尾通道
scope: rl_exp/blender, rl_exp/tools/pipeline, rl_exp/tools/verify, rl_exp/tools/diagnose, rl_exp/tasks, acceptance/records
status: in_progress
landing: rl_exp/blender/scripts/lizard2_specimen_proportions.py, rl_exp/blender/scripts/lizard2_stance_candidate.py, rl_exp/blender/scripts/generate_urdf.py, rl_exp/tools/diagnose/gait_probe.py, rl_exp/tools/diagnose/stance_step_probe.py, rl_exp/tools/diagnose/plot_joints.py, rl_exp/tools/verify/check_leg_reachability.py, rl_exp/tools/verify/check_self_collision.py, rl_exp/tools/verify/check_joint_layout.py, rl_exp/tools/verify/baseline_probe.py, rl_exp/tasks/joint_names.py, ablation_harness/baseline_metrics.py
next: B/C 接受载逐轴证据，补组合与有效边界；E 补其余消费者，缺证局部补齐，不手工调步态。
close_when: 新上下文按正文修订范围核验 R1–R5 与 D 记录，保留几何/预算约束，用户确认外观/几何样本；策略动作性能交 S6，缺证不关闭。
evidence: acceptance/records/2026-10-19-lizard2-pd-scope-correction.md, acceptance/records/2026-10-19-lizard2-load-transfer-lift.md, acceptance/records/2026-10-19-lizard2-single-leg-lift.md, acceptance/records/2026-10-21-lizard2-left-knee-absolute-pd.md, acceptance/records/2026-10-19-lizard2-spatial-inertia-repair.md, acceptance/records/2026-10-19-lizard2-contact-path-correction.md, acceptance/records/2026-10-19-lizard2-a-geometry-replay.md, acceptance/records/2026-10-16-lizard2-support-schedule.md, acceptance/records/2026-10-16-lizard2-candidate-doc-organization.md, acceptance/records/2026-10-14-lizard2-palm-spatial-review-fixes.md, acceptance/records/2026-10-14-lizard2-palm-spatial-design-decision.md, acceptance/records/2026-10-14-lizard2-a-priority-review.md, acceptance/records/2026-10-13-lizard2-restored-limits-pd-open-issues.md, acceptance/records/2026-10-13-lizard2-a-implementation-plan-review.md, acceptance/records/2026-10-13-lizard2-body-drive-plan-review.md, acceptance/records/2026-10-13-lizard2-natural-ground-tail.md, acceptance/records/2026-10-13-lizard2-lowered-body-vertical-shanks.md, acceptance/records/2026-10-12-lizard2-four-palms-lowered.md, acceptance/records/2026-10-12-lizard2-claw-palm-shape.md, acceptance/records/2026-10-12-lizard2-palm-p2-sample.md, acceptance/records/2026-10-12-lizard2-palm-chain-p1.md, acceptance/records/2026-10-08-lizard2-r1-numeric-reference-and-decision-drafts
---

本项统筹隔离候选的机体、全部关节默认驱动、真实接线与训练前集成交付。用户定案及对前序动作前置的修订见[默认驱动与 RL 职责记录](../../acceptance/records/2026-10-19-lizard2-chest-standing-pd.md#用户定案默认关节驱动与强化学习职责)；整体结构需求及“审核输入绑定约定”见 [整体记录](../../acceptance/records/2026-10-10-lizard2-land-body-drive-overall-work.md)，R1–R5 的轴系、几何禁区和驱动预算约束见 [设计审核契约](../../acceptance/records/2026-10-08-lizard2-joint-design-review-contract.md)。各节自检，D 集成后一次独立审核；专项分段交付不以其关闭为前提。移重、支撑分配、躯尾协调、抬腿与步态由 RL 学习，其性能验收转交 S6，不作为本项驱动交付前置。

## 下一步

1. **B/C 执行者**按[默认驱动与 RL 职责记录](../../acceptance/records/2026-10-19-lizard2-chest-standing-pd.md#用户定案默认关节驱动与强化学习职责)和限位 PD 专项步骤 6，按真实关节盘点默认 PD、限位、力矩/有效速度边界、逐轴/组合及已知载荷保持/跟踪证据；腿、胸颈和尾部均不得漏项。复用[小幅跟踪](../../acceptance/records/2026-10-19-lizard2-spatial-small-tracking.md)、[自重夹具](../../acceptance/records/2026-10-19-lizard2-level-leg-pd.md)与[静站](../../acceptance/records/2026-10-19-lizard2-loaded-standing.md)的原工况边界，只补真实变化或缺证。胸部允许自然倾角，不新增补偿控制器或增益扫描；手工抬落失败保留原义，不据此判单关节驱动不合格，也不再要求先手工走起来。A 的真实几何/碰撞缺口继续局部交付；正式 URDF 导出切片取 A4 的验收指针，USD/运行时交 E，动作周期样本不变为 RL 必须复现的轨迹。
2. **E 执行者**按 [接线专项 E5](lizard2-candidate-wiring.md#e5-当前剩余工作与-a-并行交接) 补实际消费链；baseline reset/采集异常交限位 PD 专项 3/4，旧资产 cap/contact ownership 前提交 `work/active/floor-contact-attribution.md` ⑤/⑪。A 与 E 按输入变化交接并复验。
3. **B/C/E 执行者**交默认驱动证据、躯尾通道和实际 action manager 权限，D 核同一候选的训练前集成与安全 reset；[S5 判据前置](lizard2-family-landing.md)按协议样本固定训练后策略性能判据，不要求手工运动先成功。移重、支撑分配、抬落、低速直行、完整步态、转向/恢复及躯尾协同性能明确交 S6，不记为已完成。

## A–E 当前执行关系

字母表示职责，不表示串行；实施细节按下表唯一落点维护。

| 职责 | 实施正文与交付 | 前置与回交 |
|---|---|---|
| A 机体 | 重构专项维护轴系、构型与真实随动；限位 PD 专项 1–5 维护资产诊断、机械限位与几何样本；本项 A4 维护当前几何交付出口 | 接 E 最小绑定及 B 能力约束；交真实机构几何、具名候选及未解问题，既有回放仅作诊断，P4 由 B/C/D 核默认驱动与集成安全，动作性能交 S6 |
| B 驱动 | 本项 B 定义能力与交付，限位 PD 专项 6 维护标定方法 | 能力约束先出；标定等 A 几何、E 实际接线及惯量/碰撞前提 |
| C 躯尾 | 本项 C 维护胸颈尾默认驱动、坐标与测量通道；协同策略归 S6 | 同一候选按 B 的受控驱动口径验证，不手工设计载荷转移 |
| D 集成 | 本项 D 与关闭条件维护训练前输入、驱动、动作与安全 reset 审核 | A/E 出口及 B/C 默认驱动证据齐备；失败回责任节，不要求手工步态通过 |
| E 接线 | [接线专项](lizard2-candidate-wiring.md) 维护命名、导出、FK、运行时、动作/观测和报告消费 | 最小绑定先供 A；真实新候选逐层验证，完整出口交 D |

记录分别绑定实际资产与配置；旧四轴或同几何改名证据不外推到新构型。未接线工具不得测新名候选，也不能等 D 才首次核新链运行接线。

## 目标与当前结构要求

- **蜥蜴骨段朝向**：前肢上臂外展向后、后肢股骨外展向前，肘/膝朝外，下段近垂直落地、掌/跖朝前；保留内扣反例，不仅验单角度禁区。方位角、仰角、体高/骨长比例、测量精度和容差在比较前确认，复用 `check_leg_reachability.py`、`fit_gait_target.py` 口径，不按现资产误差倒定。反曲、翻掌和穿透禁区随候选复核。
- **骨架与掌根**：肩/髋三个共中心串联轴接肘/膝、腕/踝；轴序、长轴方向、镜像及网格归属归重构专项。无指/趾骨、指/趾根活动关节或活动接触片；“人手式”仅限定远端连接，近端仍取蜥蜴朝向。腕/踝 pivot、下段骨尾、掌骨头与实体掌根共点，掌骨尾向远端延伸，掌体有长度与承重面；掌心/接触点不得替代关节中心。
- **实体一致性**：同步调整 head/tail、关节标记、父子关系与网格归属，下段止于腕/踝、掌体归其子 link。不能只改显示骨、pose 或平移脚板；碰撞体、质心/惯量随网格复核。前后肢分别镜像，轴与范围消费 B 的线性能力，不沿用旧轴或承诺渐硬弹性。
- **中立外形**：降低离地体高而不压薄机身，下段竖直，落掌 XY 可随可达性调整；前肢尺度保持，后肢骨长/后掌按恢复要求。四掌底共用固定水平地面，仅约束中立站姿；掌体接近腕/踝球底并核掌根过渡。体高、颈尾与近端前后朝向保持；尾根连接、逐段下落，远端自然贴地且有沿轴支持跨度，不做尾尖单点悬空休息。新候选外观仍待用户确认，尾部外形不授权 ROM/物理/导出或采用。
- **依据与边界**：几何输入取 [后肢恢复记录](../../acceptance/records/2026-10-13-lizard2-hindlimb-restored.md)，体高/尾部及各次几何修订依据见 evidence；旧视觉认可不延伸到新姿态或物理。R1 草案 §15–§17 的旧组合拒绝不替代新构型验证，不重复无变化测试；资料访问和可读量边界见其 §7–§10，不重试被拒访问、不猜关节点拼曲线。机体读数前核整体记录“必须纠正的既有踝部分析”及 A3 自检，工具通过不当设计通过。

## E. 接线与命名交付

完整正文归 [接线专项](lizard2-candidate-wiring.md)：骨骼改名表、E1 路线、E2 绑定契约、E3 消费者清单、E4 验证/分段出口及 E5 当前动作均在那里维护。当前目标为 `palm_spatial`，旧 shared/split/palm 保留原义；E 最小绑定先供 A，实际新候选完整链交 D。

## A. 机体候选

### A1. 结构与实施入口

结构约束取上文“目标与当前结构要求”；三轴方案、源件身份、生成器和随动检查归重构专项。候选在隔离路径生成，记录与历史决定只取 evidence。核三个近端轴、肘膝及腕踝的真实整链运动、连接与几何禁区，不用改名通过或仅脚板显示移动替代真实机构检查；不以手工步态、相位或无滑移求解作为 A 交付。

### A2. 探测顺序与停止条件

| 阶段 | 必须验证及实施落点 | 失败/缺证时 |
|---|---|---|
| P1 真实链 | 重构专项核实际树、三个方向运动与实体随动；新轴沿上段长轴，旧命名语义保留，不补回旧末端轴 | 漏轴、错轴、未重绑网格或旧位次被接受，回重构专项；旧契约不算新构型通过 |
| P2 连接与随动 | 同一三轴候选四肢镜像，近端逐轴/组合及肘膝、腕踝转动；共同坐标系核连接残差、掌骨方向、网格端点、掌底/球底、运动连接残差及下段与掌表面交叉 | 用户确认新外观与工程容差；错位/脱节或缺证停 P2 回 A，不放宽容差。旧两肢样本不覆盖当前四肢，诊断件不当正式交付或 ROM |
| P3 导出与几何 | 限位 PD 专项 1–4 核 DCC→URDF→USD 的树、pivot、轴、末端、网格、质心/惯量及写前拒错；旧链+主动腕踝作零号对照。按 5a 复用四肢零位/非零真实树、完整 FK、实体连接/随动及网格碰撞证据，只补受影响几何缺口；原周期样本仅作诊断，导出误差容差先获准 | 缺目标/命令、绑定错、漂移或碰撞失败回 E/A，停止受影响交付；真实输入/惯量/碰撞不可信不进对应 B/D 检查，只读 contract 不解除前置。手工周期求解不阻塞已具前提的默认驱动检查；剩余惯量/碰撞前提在对应 P4 检查前完成，不阻塞已具前提的离线几何 |
| P4 默认驱动与集成安全（B/C/D 接续） | 核真实关节/动作通道；B/C 交逐轴小幅与适度组合、明确基座/自重或已知载荷下的保持/跟踪，D 核同一候选读回及安全 reset/站姿样本；完整周期与推进性能交 S6 | 缺隔离 cfg、命令、载荷/误差依据、安全预算或接触口径停对应检查并提请用户确认。失败回 A/B/C/E，不归因奖励或自动加轴；额外自由度需用户决策，FK/静力不替代受载行为证据。P4 不要求手工抬落/步行成功，不作为 A4 几何交付的完成条件 |

### A3. 探测入口

从仓根运行，复用已绑定证据，仅重验变更或缺证部分。C0 旧工具基线：

```cmd
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp\tools\verify\check_leg_reachability.py --self-check
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp\tools\verify\check_leg_reachability.py --break-test
```

旧 P1 四轴契约回归：`"E:\SteamLibrary\steamapps\common\Blender\blender.exe" --background --factory-startup --python-exit-code 1 --python rl_exp\blender\scripts\lizard2_stance_candidate.py -- --contract_self_check`，追加 `--regression_without_fix` 应非零；范围见 palm-chain-p1 记录。

C1/C2/C3 按重构专项核 `lizard2_palm_spatial_candidate.py`、`palm_spatial_probe.py` 与接线专项实际导出目标；`lizard2_specimen_proportions.py --restore_source_lengths` / `--check_only` 仅复读尺寸恢复上游。保存重开 Blender 核父子树/网格随动，确认参数、输入身份和独立输出目录后才写交付命令；生成器会重建网格，禁止指向采用资产或调用旧无参数写入入口。

旧四轴对照为 `generate_urdf.py --robot lizard2_palm_diagnostic` 与 `palm_pd_probe.py`，限制取 a-priority-review/restored-validation-handoff 记录；`lizard2_palm_contract` 仅作旧契约回归。五轴输入不得喂旧四轴入口，旧 shared 五轴及家族 dev 驱动参数不直接套用。源件、导出或转换设置变化才重建对应产物，使用新路径，不覆盖历史。

C4 的 `local_path_check.py`、`local_path_view.py` 及既有路径/回放保留为历史几何复读工具；A4 不再要求更新手工周期、根运动或无滑移解。真实轴系、实体随动、限位/碰撞缺口按专项 5a/5b 局部检查，不以末端显示移动替代整链证据。P4 另核默认驱动与集成安全。

### A4. 交接

当前按[用户最新定案](../../acceptance/records/2026-10-19-lizard2-a-delivery-plan.md#用户定案撤销手工步态交付前置)只交真实机构几何候选及具名缺口，不要求手工步态回放、根前移或无滑移轨迹。已有回放与轨迹留作诊断证据，不再开发步长、相位或周期，不要求 RL 复现。用户回放确认的边界与阶段交付判定只取该记录，不推定另有外观或正式采用批准。

1. **核真实几何**：复用 P1–P3 已绑定的树、轴、pivot、实体连接/随动、镜像及限位/碰撞证据，只补真实变更或缺证；不能只移动脚板显示或只看末端坐标代替整条腿和实体检查。保留错轴、脱节、翻掌、反曲、穿地和真实干涉判据；不将脚板能动解释为整机能走。
2. **交具名候选给 E/B/C**：绑定源候选、URDF/网格/隔离 USD 身份、配置、真实几何检查与已生成回放的记录指针；轨迹/根偏移仅标历史诊断参考，不作为后续控制目标。正式 URDF 导出接口、写前拒错及独立切片审核取[导出验收](../../acceptance/records/2026-10-19-lizard2-a-delivery-plan.md#正式导出与写前拒错切片验收)。E/B 接[新输入验收](../../acceptance/records/2026-10-15-lizard2-e-spatial-runtime-wiring.md#追加新正式导出身份接入隔离-usd-与真实消费者2026-10-20)的实测 manifest，新输入固定基惯量与独立在线布局取[前置验收](../../acceptance/records/2026-10-15-lizard2-e-spatial-runtime-wiring.md#追加新输入运行时惯量与独立在线观测前置2026-10-20)，继续补后端实体响应及剩余消费者，不混用原检查点身份；B 接全部关节默认 PD/有效力矩速度边界，C 接胸颈尾驱动与通道，各自前提按对应输入核验，不等手工运动成功。
3. **区分阶段交接与事项关闭**：正式 URDF 导出切片依上述验收交 E；全部机械范围、动力学、完整 E/USD runtime 和总项 D 独立审核不据此完成。真实几何缺口仍回 A，受新导出影响的消费复验交 E；不因局部交付或撤销动作要求自动关闭任何事项。

**检查边界**：保留错轴/错 pivot、连接错误、限位、翻掌、穿地和自碰撞的既有判据；已绑定证据按输入与行为变化判断是否重验，无变化则引用。不得为交付扩大采样范围、另加全区间数学证明、全 ROM 扫描或新闸门；新缺陷先定位，再做能复现该缺陷的最小检查，仓库提交闸门照常执行。

机械限位及几何禁区仍由限位 PD 专项 5b 维护，默认驱动由其步骤 6 维护；惯量和运行时缺口由该专项 3/4 及 E 维护，P4 默认驱动与安全集成归 B/C/D。原时间映射、承重直行、转向/恢复与躯尾比较交 [S6](lizard2-family-landing.md#s6-直接执行正式采用预检与训练验收) 的策略性能验收，不记为完成。A4 是阶段交付，A、专项及总项的其余未完动作继续在办；关闭按修订范围独立审核，依据见默认驱动与 RL 职责记录。证据手续按接线专项 E4 第 5 条办理。

## B. 驱动（能力表先出，可与 A 同时）

**标定前置（B/C 共用）**：候选的 A/P3 几何与实际隔离运行接线成立后，执行者提出目标、载荷、驱动能力、幅度、窗口、步数/资源预算及停止条件，用户确认工程取值；先按 R5 静力筛查，再做受控动力学标定。设计不变量及已批准几何容差仍约束标定，缺测量通道先交接触协议项处理。标定只交付测量及工况边界，不先判最终性能通过；它不依赖 S5 完整交付或本项关闭。C 可先用现有机体核通道，受机体变化影响的标定须用实际候选重做后交 S5。

1. 能力表已归 `acceptance/records/2026-10-12-lizard2-drive-capability-and-name-inventory.md` A 节（判词、源码坐标与未知项），本项只留它给的**约束**：位置→力矩通路按构造就是线性 PD，**渐硬/渐变的趾端恢复力今天不可表达**（要么新增 Python 执行器子类、但丢掉本线特意选的物理步长 implicit PD；要么走每子步外力、可达性未验证）⇒ A 选 pivot/轴时**按线性对照**进行，或先回来重划弹性这一节的范围。不新建驱动机制、不改配方。
2. 标定前置成立后，按专项步骤 6 的唯一方法，以已核惯量生成稳定的默认 PD，覆盖全部实际关节而不只腿部。先验目标与实体运动，再做小幅跟踪/组合及明确基座、重力、载荷下的保持/跟踪检查，允许已声明的有限自重静差；四足静站只作集成安全样本，不要求胸部水平、手工单腿抬落或承重直行通过。PD 不是无动力的被动关节，固定零目标也会产生保持力矩，但不能代替策略协调目标。新输入全部关节小幅后端目标与 actor 行为取[当前切片](../../acceptance/records/2026-10-19-lizard2-spatial-small-tracking.md#新导出输入全部关节小幅驱动复验2026-10-20)，[胸俯仰自重试验](../../acceptance/records/2026-10-19-lizard2-spatial-small-tracking.md#胸俯仰自重280复验)只按其实际预算/静差复用，不据此正式采用力矩值；逐轴受载按 evidence 复用；组合和有效边界仍缺证。初值、配置、读回与行为证据分开交 D/S5，不恢复指/趾根驱动、不盲扫增益、不添加步态或补偿控制器。
3. 速度上限按整体记录“联动设计修订”第 4 条：启用须有速度—载荷—跟踪/稳定包线和同条件有/无限速对照，否则明确不启用并写工况边界。**另有一笔前置的账**（具名缺口见 2026-10-12 记录的 A7 条，本项不复述）：implicit 执行器把配方设的 `velocity_limit` 静默作废，而 USD 关节 prim 是否自带限速未查 ⇒ "启不启用"这个问题本身还悬着；本轮不改配方。

4. **五角色驱动与近端耦合**：swing、abduct、twist、elbow/knee、wrist/ankle 分别绑定真实关节，核零位、符号、硬限位、驱动目标、力矩与速度设置；不复制旧 foot 或 abduct 的 PD 给 twist。中间承载 link 的质量/惯量近似及整条链守恒由重构与专项步骤 3 核验。按专项步骤 6 由各姿态有效惯量取初值，逐轴跟踪再组合激励，检查其它轴被带动、奇异邻域、限位/饱和和接触下的稳定性；三个标量目标可独立设置不意味着动力学解耦。全部五角色先在隔离诊断中可控可读，胸颈尾全部实际关节按 C 补齐同口径覆盖；策略动作集合与冻结版本迁移仍归 S5/S6。

## C. 胸颈尾默认驱动与测量通道

1. 区分根机身 heading、胸部侧弯、颈方向、尾 yaw/pitch 与肩髋 twist；躯干转向不能被记成腿的长轴旋转。以实际 URDF 树与运行时关节集合为准，在交付记录逐项对表胸颈尾关节的默认目标、坐标、真实驱动及动作/观测列，不默认新增脊柱轴；旧机体只作具名通道对照。
2. 在同一候选上按 B/专项步骤 6 的受控载荷与保持/跟踪口径补胸颈尾缺证，记录耦合、静差和有效力矩/速度边界。胸部世界姿态只作观测，不要求固定水平；不手工增加移重、尾部随动或姿态补偿来证明驱动合格。测量通道和稳定默认驱动交 D/S5，已训策略才用于协同性能判断。
3. 行走允许自然拖尾，异常主承重、头腹推进和真实滑移仍由接触协议与 S6 的策略验收检查。原躯干侧弯、尾部运动及组合协同的性能对照转交 [S6](lizard2-family-landing.md#s6-直接执行正式采用预检与训练验收)，不取消、不记为完成，不作为本项关闭前置。

## D. 训练前集成与审核（A/E 输入、B/C 默认驱动证据齐备后）

1. **绑定集成对象**：核 A 的骨架/网格、URDF/USD、E 的真实角色/动作/观测/接触映射、B/C 的默认 PD/限位/力矩/有效速度边界来自同一具名候选。旧命名、旧四轴或改名样本不拼接为新构型通过，声明一致不替代真实驱动行为。D 按已批准的受载工况对默认驱动给出合格、拒绝或具名未判；缺预算/判据不得视为通过。有效限速须明确为已启用、明确不启用或未决并注明依据；未决回 B，不以缺实际力矩遥测为由忽略限速设置缺口。
2. 复读逐关节、组合与已知载荷证据，核安全 reset、重力/基座/碰撞及实际设置；发现 NaN、异常接触、持续振荡、错轴/错列或已知载荷下的保持/跟踪缺口，按来源回 A/E/B/C。保持原局部安全判据，不用手工抬腿或步行成败判断单关节驱动能力，不再以胸部水平阻断交付。
3. E/S5 逐角色声明策略可访问、固定或阶段门控及依据；需 RL 学习协调的关节必须有可达的实际动作通道，固定零位或 scale=0 不称可学习。核真实 action manager 目标、缩放、偏置、状态与实体随动；本次文档修订不自动开放冻结动作或修改配方。原完整周期、抬落、低速直行、转向/恢复及躯尾协同的动态性能交 S6 学习策略验收；几何与禁区检查继续由 A/专项维护，不以有限采样证明全安全域。
4. 记录进 `acceptance/records/<日期>-lizard2-body-drive-candidate.md`，绑定候选、代码、B/C 驱动工况及 E 真接线和接触口径；存在后补 evidence。D 自检后交新上下文独立审核，合格交 S5 正式接入；S5 提前确定策略评测判据，S6 采用/开训另获用户确认，D 不批准或保证训练后的动作性能。

## 关闭条件

- **审核者与输入**：新上下文按[默认驱动与 RL 职责记录](../../acceptance/records/2026-10-19-lizard2-chest-standing-pd.md#用户定案默认关节驱动与强化学习职责)核验 R1–R5、本项 D 节及其真实记录；原轴系、几何禁区、容差与驱动/资源预算保留，用户确认候选外观与几何样本。原手工动作及躯尾性能对照前置修订为 S6 策略验收，不据此宣告 R1–R5 全部通过。
- **几何与命名**：蜥蜴骨段朝向正反例、前后肢映射与改名落地一致；按 A 核验肩髋三轴共中心、长轴旋转及实体随动，并核验腕/踝位于前臂/小腿末端、掌段从掌根延伸、骨架与模型连接一致及转动不脱节；同一候选按已确认有限采样覆盖有向掌面、机械限位与实际网格碰撞。固定机身周期证据保留原几何用途，不新增全 ROM 或连续域证明作为驱动前置。
- **动力学与驱动**：腿部五角色及胸颈尾全部实际关节的默认驱动读回、小幅/适度组合与明确基座、自重或已知载荷的保持/跟踪可复读，允许已声明有限静差，无失控或持续振荡；安全 reset/站姿样本不要求胸部水平或手工抬落成功。缺预算/误差/窗口依据先提请用户确认，缺实际力矩通道不称真实饱和已验证；预算依据与最小受载行为证据不能被静力、声明、源码或无重力跟踪替代，也不要求穷尽传感工程。E/S5 核逐角色真实动作权限与固定/门控说明，需协调关节可达；运动及躯尾同条件性能比较交 S6，仅经授权新配方训练。
- **结果处理**：通过后交 `lizard2-family-landing`；失败退 in_progress 并指明节，仅用户能给的缺口置 blocked。未判定不关闭。

## 边界

不训练、不调正式增益、不改已训 v3、不读写配方锁正文、不新增机器闸门；旧 checkpoint 只作影响诊断。静态趴姿归 `lizard2-prone-posture`，游泳不在本轮。
