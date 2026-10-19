---
id: lizard2-body-drive-candidate
title: lizard2 机体与驱动候选：肩髋三轴、足掌连接与躯尾协同
scope: rl_exp/blender, rl_exp/tools/pipeline, rl_exp/tools/verify, rl_exp/tools/diagnose, rl_exp/tasks, acceptance/records
status: in_progress
landing: rl_exp/blender/scripts/lizard2_specimen_proportions.py, rl_exp/blender/scripts/lizard2_stance_candidate.py, rl_exp/blender/scripts/generate_urdf.py, rl_exp/tools/diagnose/gait_probe.py, rl_exp/tools/diagnose/stance_step_probe.py, rl_exp/tools/diagnose/plot_joints.py, rl_exp/tools/verify/check_leg_reachability.py, rl_exp/tools/verify/check_self_collision.py, rl_exp/tools/verify/check_joint_layout.py, rl_exp/tools/verify/baseline_probe.py, rl_exp/tasks/joint_names.py, ablation_harness/baseline_metrics.py
next: B/C 按移重抬落记录修承重胸姿态与足尾载荷目标，再测左前腿抬落；E 继续正式导出与消费者出口。
close_when: 新上下文按正文“关闭条件”核验 R1–R5 与 D 记录，用户确认外观和动作；未判定不关闭。
evidence: acceptance/records/2026-10-19-lizard2-load-transfer-lift.md, acceptance/records/2026-10-19-lizard2-single-leg-lift.md, acceptance/records/2026-10-19-lizard2-loaded-standing.md, acceptance/records/2026-10-19-lizard2-spatial-small-tracking.md, acceptance/records/2026-10-19-lizard2-spatial-inertia-repair.md, acceptance/records/2026-10-19-lizard2-contact-path-correction.md, acceptance/records/2026-10-19-lizard2-a-geometry-replay.md, acceptance/records/2026-10-19-lizard2-a-delivery-plan.md, acceptance/records/2026-10-16-lizard2-support-schedule.md, acceptance/records/2026-10-16-lizard2-candidate-doc-organization.md, acceptance/records/2026-10-15-lizard2-e-spatial-runtime-wiring.md, acceptance/records/2026-10-14-lizard2-palm-spatial-review-fixes.md, acceptance/records/2026-10-14-lizard2-palm-spatial-design-decision.md, acceptance/records/2026-10-14-lizard2-a-priority-review.md, acceptance/records/2026-10-13-lizard2-restored-limits-pd-open-issues.md, acceptance/records/2026-10-13-lizard2-hindlimb-restored.md, acceptance/records/2026-10-13-lizard2-a-implementation-plan-review.md, acceptance/records/2026-10-13-lizard2-body-drive-plan-review.md, acceptance/records/2026-10-13-lizard2-natural-ground-tail.md, acceptance/records/2026-10-13-lizard2-lowered-body-vertical-shanks.md, acceptance/records/2026-10-12-lizard2-four-palms-lowered.md, acceptance/records/2026-10-12-lizard2-claw-palm-shape.md, acceptance/records/2026-10-12-lizard2-palm-p2-sample.md, acceptance/records/2026-10-12-lizard2-palm-chain-p1.md, acceptance/records/2026-10-12-lizard2-drive-capability-and-name-inventory, acceptance/records/2026-10-10-lizard2-land-body-drive-overall-work, acceptance/records/2026-10-08-lizard2-joint-design-review-contract, acceptance/records/2026-10-08-lizard2-r1-numeric-reference-and-decision-drafts
---

本项统筹隔离候选的机体、驱动、躯尾协同与集成验收。整体需求及“审核输入绑定约定”见 [整体记录](../../acceptance/records/2026-10-10-lizard2-land-body-drive-overall-work.md)，R1–R5 见 [设计审核契约](../../acceptance/records/2026-10-08-lizard2-joint-design-review-contract.md)。各节自检，D 集成后一次独立审核；专项分段交付不以其关闭为前提。

## 下一步

1. **B 执行者**按[移重抬落记录](../../acceptance/records/2026-10-19-lizard2-load-transfer-lift.md)修承重胸姿态与三足/尾部载荷分配，固定下一次局部轨迹、窗口、预算及停止条件后再测左前腿抬落；保留[承重静站记录](../../acceptance/records/2026-10-19-lizard2-loaded-standing.md)的合格基线及瞬态请求、实测通道边界。沿用[接触边修正记录](../../acceptance/records/2026-10-19-lizard2-contact-path-correction.md)的几何交付，不继续盲扫增益；抬落成立后再接新轨迹时间映射与低速直行。E 复用静站记录的组合与实体读回边界，继续自身出口。A 阶段出口仍按 [A4](#a4-交接)，最终外观/动作确认不记为已完成，只重验变更或缺证。
2. **E 执行者**按 [接线专项 E5](lizard2-candidate-wiring.md#e5-当前剩余工作与-a-并行交接) 补实际消费链；baseline reset/采集异常交限位 PD 专项 3/4，旧资产 cap/contact ownership 前提交 `work/active/floor-contact-attribution.md` ⑤/⑪。A 与 E 按输入变化交接并复验。
3. **B/C 执行者**先分别核驱动能力约束、协同测量通道；满足 B 的标定前置后形成记录，交 [S5 阈值前置动作](lizard2-family-landing.md)。用户固定阈值后，D 才做最终比较。

## A–E 当前执行关系

字母表示职责，不表示串行；实施细节按下表唯一落点维护。

| 职责 | 实施正文与交付 | 前置与回交 |
|---|---|---|
| A 机体 | 重构专项维护轴系、构型与真实随动；限位 PD 专项 1–5 维护资产诊断与相位周期；本项 A4 维护当前几何交付出口 | 接 E 最小绑定及 B 能力约束；交四肢回放、机身前移检查和具名候选，P4 由 B/C/D 接续 |
| B 驱动 | 本项 B 定义能力与交付，限位 PD 专项 6 维护标定方法 | 能力约束先出；标定等 A 几何、E 实际接线及惯量/碰撞前提 |
| C 躯尾 | 本项 C 维护根运动、躯干、四肢与拖尾协同 | 旧机体只核通道；实际候选用 B 可用驱动做无协同对照 |
| D 集成 | 本项 D 与关闭条件维护最终比较和独立审核 | A/E 出口、B/C 标定及 S5 固定阈值齐备；失败回责任节 |
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

结构约束取上文“目标与当前结构要求”；三轴方案、源件身份、生成器和随动检查归重构专项。候选在隔离路径生成，记录与历史决定只取 evidence。先验证能否表达摆动、抬落、沿上段长轴旋转及相位动作，不预设可行，不用改名通过替代结构或物理通过。

### A2. 探测顺序与停止条件

| 阶段 | 必须验证及实施落点 | 失败/缺证时 |
|---|---|---|
| P1 真实链 | 重构专项核实际树、三个方向运动与实体随动；新轴沿上段长轴，旧命名语义保留，不补回旧末端轴 | 漏轴、错轴、未重绑网格或旧位次被接受，回重构专项；旧契约不算新构型通过 |
| P2 连接与随动 | 同一三轴候选四肢镜像，近端逐轴/组合及肘膝、腕踝转动；共同坐标系核连接残差、掌骨方向、网格端点、掌底/球底、运动连接残差及下段与掌表面交叉 | 用户确认新外观与工程容差；错位/脱节或缺证停 P2 回 A，不放宽容差。旧两肢样本不覆盖当前四肢，诊断件不当正式交付或 ROM |
| P3 导出与几何 | 限位 PD 专项 1–4 核 DCC→URDF→USD 的树、pivot、轴、末端、网格、质心/惯量及写前拒错；旧链+主动腕踝作零号对照。坐标/网格可信后按 5a 先两腿再四肢周期，复用真实树/FK/实际网格碰撞，导出误差容差先获准 | 缺目标/命令、绑定错、漂移或碰撞失败回 E/A，不进 B/D；只读 contract 不解除前置。剩余惯量/碰撞前提在 P4 前完成，不阻塞已具前提的离线几何 |
| P4 承重动作（B/C/D 接续） | `stance_step_probe.py` 接真实末端/动作通道；B/C 先标定、S5 固定性能阈值、D 同目标/载荷/驱动/窗口比较完整周期；分记掌面接触、变形、滑移/滚动和推进 | 缺隔离 cfg、命令、安全预算或接触口径停标定；缺阈值停 D。失败回 A/B，不归因奖励或自动加轴；额外自由度需用户决策，FK/静力不替代动力学。P4 不作为 A4 几何交付的完成条件 |

### A3. 探测入口

从仓根运行，复用已绑定证据，仅重验变更或缺证部分。C0 旧工具基线：

```cmd
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp\tools\verify\check_leg_reachability.py --self-check
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp\tools\verify\check_leg_reachability.py --break-test
```

旧 P1 四轴契约回归：`"E:\SteamLibrary\steamapps\common\Blender\blender.exe" --background --factory-startup --python-exit-code 1 --python rl_exp\blender\scripts\lizard2_stance_candidate.py -- --contract_self_check`，追加 `--regression_without_fix` 应非零；范围见 palm-chain-p1 记录。

C1/C2/C3 按重构专项核 `lizard2_palm_spatial_candidate.py`、`palm_spatial_probe.py` 与接线专项实际导出目标；`lizard2_specimen_proportions.py --restore_source_lengths` / `--check_only` 仅复读尺寸恢复上游。保存重开 Blender 核父子树/网格随动，确认参数、输入身份和独立输出目录后才写交付命令；生成器会重建网格，禁止指向采用资产或调用旧无参数写入入口。

旧四轴对照为 `generate_urdf.py --robot lizard2_palm_diagnostic` 与 `palm_pd_probe.py`，限制取 a-priority-review/restored-validation-handoff 记录；`lizard2_palm_contract` 仅作旧契约回归。五轴输入不得喂旧四轴入口，旧 shared 五轴及家族 dev 驱动参数不直接套用。源件、导出或转换设置变化才重建对应产物，使用新路径，不覆盖历史。

C4 按 A4 复用 `local_path_check.py` 的支持相位报告及 `local_path_view.py` 的四肢回放、根运动前提读数，推进限位 PD 专项 5a。先核已有产物身份再交付；仅当目标动作确有缺口才补求解能力，小角度快照/单轴扫描不代替周期。P4 另验动力学。

### A4. 交接

当前按以下顺序交付，重构与限位 PD 专项引用这里，不再各起一套推进顺序：

1. **先交四肢动作回放**：A 用同一支持相位报告交侧视、俯视动画及复读入口，标出接地、离地及实际节点处理方式。先核对并复用已有组合动画与分析产物，向用户展示当前动作；播放节奏不作为物理周期，不等待承重或完整 PD。
2. **再补机身前移与滑动检查**：A 按限位 PD 专项 5a，用同一四肢路径提出并应用明确的根运动，检查世界系地面间隙、支撑相位及同一材料接触点的位移，区分滑动与接触点切换。现有前提分析先复用；根运动与轨迹须同时自洽，不能只平移画面。沿用已确认的有限采样、容差与预算口径，新增工程取值按专项集中提出；失败只修受影响相位或几何，并重验其依赖。
3. **交几何候选给 E/B/C**：P1–P3 中与几何交付有关的输入、坐标、四肢镜像和连接证据齐备，用户确认外观/动作后，A 交候选身份、轨迹、配置、动画、检查记录及具名缺口。E 接实际导出/运行时消费，B 接有效限速、时间映射和承重 PD，C 接躯尾协同；B/C 开始标定仍须满足各自前置。几何交付单独记录，不等待 P4、转向/恢复或专项关闭。

**检查边界**：保留错轴/错 pivot、连接错误、限位、翻掌、穿地和自碰撞的既有判据；已绑定证据按输入与行为变化判断是否重验，无变化则引用。不得为交付扩大采样范围、另加全区间数学证明、全 ROM 扫描或新闸门；新缺陷先定位，再做能复现该缺陷的最小检查，仓库提交闸门照常执行。

转向/恢复与最终动作范围仍由限位 PD 专项 5b/6 维护；惯量和运行时缺口由该专项 3/4 及 E 维护，P4 和最终比较仍归 B/C/D。A4 是阶段交付，A、专项及总项的未完动作继续在办；关闭仍走原独立审核。证据手续按接线专项 E4 第 5 条办理。

## B. 驱动（能力表先出，可与 A 同时）

**标定前置（B/C 共用）**：候选的 A/P3 几何与实际隔离运行接线成立后，执行者提出目标、载荷、驱动能力、幅度、窗口、步数/资源预算及停止条件，用户确认工程取值；先按 R5 静力筛查，再做受控动力学标定。设计不变量及已批准几何容差仍约束标定，缺测量通道先交接触协议项处理。标定只交付测量及工况边界，不先判最终性能通过；它不依赖 S5 完整交付或本项关闭。C 可先用现有机体核通道，受机体变化影响的标定须用实际候选重做后交 S5。

1. 能力表已归 `acceptance/records/2026-10-12-lizard2-drive-capability-and-name-inventory.md` A 节（判词、源码坐标与未知项），本项只留它给的**约束**：位置→力矩通路按构造就是线性 PD，**渐硬/渐变的趾端恢复力今天不可表达**（要么新增 Python 执行器子类、但丢掉本线特意选的物理步长 implicit PD；要么走每子步外力、可达性未验证）⇒ A 选 pivot/轴时**按线性对照**进行，或先回来重划弹性这一节的范围。不新建驱动机制、不改配方。
2. 标定前置成立后，按专项步骤 6 的唯一方法，以核对的惯量生成一套 PD 初值，经小幅跟踪、四足静站、单腿抬落校准，再做同几何承重直行；不恢复已取消的指/趾根驱动，不以增益扫描替代动作能力验证。初值、配置、读回和实际行为分开记录，交 S5 阈值前置动作；新增 twist 的驱动要求按第 4 条落实，其它结构变更凭目标动作缺失另议。
3. 速度上限按整体记录“联动设计修订”第 4 条：启用须有速度—载荷—跟踪/稳定包线和同条件有/无限速对照，否则明确不启用并写工况边界。**另有一笔前置的账**（具名缺口见 2026-10-12 记录的 A7 条，本项不复述）：implicit 执行器把配方设的 `velocity_limit` 静默作废，而 USD 关节 prim 是否自带限速未查 ⇒ "启不启用"这个问题本身还悬着；本轮不改配方。

4. **五角色驱动与近端耦合**：swing、abduct、twist、elbow/knee、wrist/ankle 分别绑定真实关节，核零位、符号、硬限位、驱动目标、力矩与速度设置；不复制旧 foot 或 abduct 的 PD 给 twist。中间承载 link 的质量/惯量近似及整条链守恒由重构与专项步骤 3 核验。按专项步骤 6 由各姿态有效惯量取初值，逐轴跟踪再组合激励，检查其它轴被带动、奇异邻域、限位/饱和和接触下的稳定性；三个标量目标可独立设置不意味着动力学解耦。全部五角色先在隔离诊断中可控可读，策略动作集合与冻结版本迁移仍归 S5/S6。

## C. 躯干侧弯与拖尾（先核通道，再在新候选上标定）

1. 区分根机身 heading、胸部侧弯、颈方向、尾 yaw/pitch 与肩髋 twist；躯干转向不能被记成腿的长轴旋转。先用现有通道核测量，不默认新增脊柱轴；旧机体仅作通道对照，其协同参数与表现不能直接作为新候选证据。
2. A/E 与 B 的标定前提成立后，在同一 palm_spatial 候选、同一套 PD/限位上，以同速度目标、同足部任务、同载荷与无协同基线比较；按预设顺序分别加入躯干侧弯、尾部运动及组合协同，每次只变一类参数。足部任务按接触相位表达，允许滚动/拨动，不锁死全程平掌，也不借协同比较改变肩髋构型。记录机身偏航/侧倾、侧向重心与速度、四足相位和载荷、尾根/中/尖接触位置与法向/切向作用。
3. 行走期允许拖尾，不允许尾巴拖住身体、头腹代替足部推进，或靠滑移维持速度。C 先给协同标定及适用工况，最终获准、拒绝或未判定归 D 的固定判据比较；机体变化后受影响项重新标定和验证。

## D. 集成与审核（A/E 前置、B/C 标定与 S5 阈值输入齐备后）

1. **先绑定集成对象**：核对 A 的源骨架/网格与 URDF/USD、E 的 palm_spatial 角色/动作/观测/接触映射、B 的 PD/限位/力矩/速度及 C 的协同配置来自同一具名候选；旧 shared 五轴、四轴 palm 或改名样本的通过不能拼接成新构型通过。重构事项的候选交付不代替本项 D 审核。
2. 先取得 `lizard2-family-landing` S5 阈值前置动作给出的用户确认记录，以及接触协议项可复读的测量口径与样本；不要求 S5 配方接入或 S6 已完成。按事先固定的目标、载荷、驱动、窗口和性能判据，对同一候选跑完整支撑—摆动周期的几何与实际网格碰撞（`check_leg_reachability.py`、`check_self_collision.py`），再跑承重动力学。关节变形、原点移动、真实接触点滑动与滚动分开记；标定与最终比较记录分开，既有标定不能事后套阈值充当最终通过。
3. 比较覆盖四肢完整周期，以及专项 5b 的转向、恢复与组合碰撞；复核三轴奇异邻域、跟踪/限位余量、掌面相位和躯尾协同，前后肢分别验证。失败按来源回 A（构型/几何）、E（绑定/索引/接触读取）、B（驱动/限位）或 C（协同），不放宽容差，不直接归因奖励；目标变动须用户确认。
4. 记录进 `acceptance/records/<日期>-lizard2-body-drive-candidate.md`，按“审核输入绑定约定”绑定候选、代码、B/C 标定、S5 阈值确认和接触口径；存在后补 evidence。输入改变则重新确认受影响判据并重跑对应比较，不用失败读数倒改阈值。D 自检完成后一次性交新上下文审核；通过才交 S5 正式配方接入。

## 关闭条件

- **审核者与输入**：新上下文对照 R1–R5、本项 D 节及其真实记录；用户确认候选外观与目标动作。
- **几何与命名**：蜥蜴骨段朝向正反例、前后肢映射与改名落地一致；按 A 核验肩髋三轴共中心、长轴旋转及实体随动，并核验腕/踝位于前臂/小腿末端、掌段从掌根延伸、骨架与模型连接一致及转动不脱节；同一候选完整周期覆盖有向掌面、限位与实际网格碰撞。
- **动力学与驱动**：承重动力学、真实驱动读回、躯干/尾部同条件对照有可复读证据；静力、声明或源码支持不当动力学通过。
- **结果处理**：通过后交 `lizard2-family-landing`；失败退 in_progress 并指明节，仅用户能给的缺口置 blocked。未判定不关闭。

## 边界

不训练、不调正式增益、不改已训 v3、不读写配方锁正文、不新增机器闸门；旧 checkpoint 只作影响诊断。静态趴姿归 `lizard2-prone-posture`，游泳不在本轮。
