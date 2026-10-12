---
id: lizard2-body-drive-candidate
title: lizard2 机体与驱动候选：蜥蜴骨段朝向、人手式足掌、骨骼改名
scope: rl_exp/blender, rl_exp/tools/pipeline, rl_exp/tools/verify, rl_exp/tools/diagnose, rl_exp/tasks, acceptance/records
status: in_progress
landing: rl_exp/blender/scripts/lizard2_stance_candidate.py, rl_exp/blender/scripts/generate_urdf.py, rl_exp/tools/diagnose/gait_probe.py, rl_exp/tools/diagnose/stance_step_probe.py, rl_exp/tools/diagnose/plot_joints.py, rl_exp/tools/verify/check_leg_reachability.py, rl_exp/tools/verify/check_self_collision.py, rl_exp/tools/verify/check_joint_layout.py, rl_exp/tools/verify/baseline_probe.py, rl_exp/tasks/joint_names.py, ablation_harness/baseline_metrics.py
next: 用户看无指爪掌外观及容差；连接方式已认可，未批准不扩四肢、不进 P3。
close_when: 新上下文按正文“关闭条件”核验 R1–R5 与 D 记录，用户确认外观和动作；未判定不关闭。
evidence: acceptance/records/2026-10-12-lizard2-claw-palm-shape.md, acceptance/records/2026-10-12-lizard2-palm-p2-sample.md, acceptance/records/2026-10-12-lizard2-palm-chain-p1.md, acceptance/records/2026-10-12-lizard2-drive-capability-and-name-inventory, acceptance/records/2026-10-10-lizard2-land-body-drive-overall-work, acceptance/records/2026-10-08-lizard2-joint-design-review-contract, acceptance/records/2026-10-08-lizard2-r1-numeric-reference-and-decision-drafts
---

本项取代 S0–S4 串联审核：各节仅自检，D 集成后一次审核。整体需求见整体记录；A 节用户拍板覆盖旧指/趾根约束。判据归 R1–R5/A，本项只留动作与交付顺序。

## 下一步

1. **按 A 探测链推进**：两肢无指爪掌见本项 claw-palm-shape 记录；用户看外观及位置/网格容差，再调整、扩四肢、隔离导出。连接方式已认可；诊断不当限位/物理批准，契约不当几何通过，正式资产不动。
2. **继续 E3 接线**：URDF → FK/碰撞、运行时、报告 reader、接触面（`diag_metrics.foot_ids`、`check_contact_ownership`、`obs_protocol_live`）与 `baseline_probe` 已接线并各有真跑读数与错配负例；当前改 Blender 构建入口与步态诊断。`diagnose_support.py` 归 `floor-contact-attribution`（该文件是它的 landing），E 只登记待接的四处行号，不代改。报告 **writer** 侧（`baseline_eval` 的关节列集合、`gait_probe` 报告字段）属评测协议面，先交 `lizard2-contact-protocol` 再动。E4 的运行时双命名对照做不了——运行时关节名还写在配方里（动作项/`joint_order`/默认位姿），改名须与采用同一次变更落地（归 S6），现在只验到"绑定被核对、错配被拒"。
3. **并行边界**：A 选 pivot/轴消费 B 的能力约束，按线性对照进行，不新建驱动机制；有效限速前置仍归 B。E 接线前，A 只核对旧名源几何，不让未接线工具测新名候选；C 可用现有机体开展。
4. **先解除资产前提**：`gait_probe` 的资产前提交 `floor-contact-attribution` 的 ⑤/⑪；不借 E 改资产或放宽断言。声明面边界与既有自检覆盖只取本项 2026-10-12 evidence。
5. **集成后一次审核**：A/B/C 自检就绪后执行 D，读数入同一具名记录；置 pending_review，next 点名新上下文审核者。已训 v3、采用资产与趴姿边界见本项“边界”。

## 关闭条件

- **审核者与输入**：新上下文对照 R1–R5、本项 D 节及其真实记录；用户确认候选外观与目标动作。
- **几何与命名**：蜥蜴骨段朝向正反例、前后肢映射与改名落地一致；按 A 核验腕/踝位于前臂/小腿末端、掌段从掌根延伸、骨架与模型连接一致及转动不脱节；同一候选完整周期覆盖有向掌面、限位与实际网格碰撞。
- **动力学与驱动**：承重动力学、真实驱动读回、躯干/尾部同条件对照有可复读证据；静力、声明或源码支持不当动力学通过。
- **结果处理**：通过后交 `lizard2-family-landing`；失败退 in_progress 并指明节，仅用户能给的缺口置 blocked。未判定不关闭。

## 目标：蜥蜴骨段朝向，不只是防内扣

用户目标（2026-10-10）：把肢体变成蜥蜴的骨骼姿态朝向，从而消除小腿内扣、更像巨蜥。判据为骨段方位而不是单个角度禁区：上臂/股骨外展并向后、肘/膝朝外、前臂/小腿近垂直落地、掌/跖朝前；内扣姿态作为反例保留。方位角、仰角、体高/骨长比例的量化与容差先于比较确定，复用 `check_leg_reachability.py`、`fit_gait_target.py` 的口径，不按现资产误差倒定。已被旧 A/B 比较拒绝的目标/机体组合不重跑，见 R1 草案 §15–§17；动物资料的访问受限、视频身份失败与足端可读量边界见同草案 §7–§10，不重试被拒访问、不靠猜关节点拼曲线（并不表示所有动物资料路线永久不可行）。机体读数前复读 `check_leg_reachability.py --self-check` 与整体记录“必须纠正的既有踝部分析”，工具通过不当设计通过；设计不变量（反曲/翻掌/穿透禁区）与测量精度在此确认，具体边界随候选几何复核。

## 骨骼改名（用户拍板：2026-10-10；足掌结构修订：2026-10-12）

前后肢分名，覆盖整体记录“沿用现有名称”的候选起点。当前目标链：肩/髋 → 上臂/股骨 → 肘/膝 → 前臂/胫段 → 腕/踝 → 掌/跖段（末端承重体）；本轮不建指/趾骨或指/趾根活动关节，结构要求见 A 节。

| 旧词根 | 前肢 | 后肢 |
|---|---|---|
| hip（竖直轴前后摆） | shoulder_swing | hip_swing |
| haa（外展升降） | shoulder_abduct | hip_abduct |
| hfe（肘/膝屈伸） | elbow | knee |
| kfe（腕/踝屈伸） | wrist | ankle |
| foot（旧末端活动轴） | 本轮不保留，不映射成指根关节 | 本轮不保留，不映射成趾根关节 |

腿前缀（lf/rf/rl/rr）、`_joint` 后缀与躯干/颈/尾名不变。掌/跖段作为腕/踝关节的子 link，随腕/踝词根命名并承担末端接触；不另设活动接触片。

- 改名走与 v8 同类的一次性迁移，不留旧名别名；候选（新名）与现行（旧名）并存期间，工具必须两边都可用，所以先做下面的“E. 名表单点化”。本次还改变链结构，不能把旧 `foot` 到 `finger/toe` 的改名样本直接当成目标候选。
- 候选在隔离路径生成；`joint_order`、正则组、工具、obs/action 文档在采用时同变更迁移。这是机体换代：采用时 lizard2 仍加载旧机体的冻结版本须同一次变更退休（`versioning.mdc` §A），归 `lizard2-family-landing` S6。

## E. 名表单点化（改名前置，与 B 能力约束构成第一波）

勘察、接线现状与逐切片读数见 `acceptance/records/2026-10-12-lizard2-drive-capability-and-name-inventory.md` 的**追加段落索引**（B 节 = 名表勘察，追加五 = 出口复核，追加六–十一 = 逐切片落地与读数）。下文是后续施工与判据，不把模块自检当消费者验证。

**A 节结构修订的接线影响**：现有 `split` / `PLANNED_ROOTS` 与指/趾根改名样本代表旧候选约定，不是当前无指/趾候选的名表。后续在既有入口数据中明确声明当前目标的真实角色与末端掌/跖 link；不得沿用 `finger/toe` 末端，或用旧链位次补出不存在的关节。已有双命名测试保留原含义，独立 `palm` 构建契约及 P1 消费者交接见本项 palm-chain-p1 记录；当前候选几何仍须独立通过 E/D 的真实消费者验证。

### E1. 变化向量、约束与路线

变化来自上文用户批准的前后肢分名：旧名机体与新名候选要同时可测，同一工具还要能同进程比较两者。链名、链端接触体、动作选择及报告读取随之变化；不是为了增加通用机器人框架。

- **就地代码问题**：复制词根、模块名被运行时列表遮蔽、按最后一个 `_` 拆词根、空匹配被当正常输出，分别在原消费者修复，不借机重构工具体系。
- **契约表达问题**：无机体上下文的全局旧名表不能表达双机体并存；只补入口绑定和内部传递，不扩张为资产注册系统。
- **落点与依赖**：名表仍在 `rl_exp/tasks/joint_names.py`，纯标准库；Blender 与离线工具绕过 `rl_exp/tasks/__init__.py` 导入，沿用名表模块说明中的直接文件导入先例。
- **范围**：既有 `rl_exp/versions/**` 的冻结 yaml/json、配方锁及历史协议/读数不改写。候选在隔离路径生成；正式声明、传感器/奖励配置、obs/action 协议与机体退休归 S6 采用，不用 E 提前采用机体。

| 路线 | 约束与收益 | 代价与取舍 |
|---|---|---|
| **入口绑定目标机体，普通数据沿调用链传递（采用）** | 复用工具现有任务/URDF/报告入口；同进程各持自己的绑定；不新增类、注册表或全局状态 | 需要把机体上下文传到真实取名处，遗漏不得靠默认值掩盖 |
| 入口绑定只读命名对象 | 同样支持并存，方法调用较短 | 新增对象层、方法面与生命周期；当前名称映射无需此层，不选 |

**用户拍板：2026-10-12**：显式的是“处理哪个机体”；工具入口绑定目标及其命名方案，内部传递。调用者不反复手选 `legacy/candidate`，方案身份不随候选采用而变；绑定与 URDF/运行时名称不符就报错，不猜测、不自动回退。

### E2. 绑定契约与接口边界

1. **在入口确定目标，命名约定与它同行**。最小普通数据形状为目标路径、声明来源、按 leg 的“角色 → 词根”映射和每 leg 的末端角色；不需要命名对象或注册表。稳定角色取本项已有链映射的角色键，前后肢实际词根来自同一名表；该映射不承诺两机体几何等价。方案可附稳定标识，但取名使用绑定的映射，不看全局开关或候选生命周期。旧入口显式提供共享词根映射，新候选入口显式提供前后肢映射；下游只拿已绑定数据。未声明约定的任意外部机体不得从关节名猜方案。
   **已落地**：`rl_exp/tasks/joint_names.py` 的 `NAMINGS`（`shared`/`split`，后者由 `PLANNED_ROOTS` 派生）+ `naming_for`/`naming_id`/`roots_of` 与按绑定的 `end_link`/`contact_body_patterns`/`is_contact_body`；各消费者按入口声明绑定并沿调用链传递（清单见 E3 接线现状）。路径与声明来源仍由各消费者的既有入口解析（任务级用 `obs_protocol.resolve_body`），名表只回答“词根”。
2. **复用路径解析，不另造寻址**。任务工具读取最终 cfg 的实际 `usd_path`，复用 `rl_exp/tasks/obs_protocol.py:363` 的 `resolve_body()`；无覆盖时可用 `body_for_task()`。`--usd`/`--urdf` 覆盖、`--compare` 第二机体须连同各自命名约定重新绑定，不继承当前家族或第一机体的约定。未能取得约定或 USD/URDF 对应依据则拒绝比较。不能仅按 family 选新旧，同一家族会有两种机体。
3. **声明只有入口一份**。Blender 在 `generate_urdf.py` 已有 `ROBOT_SPECS` 中随构建目标声明约定，候选骨架脚本消费同一目标；诊断入口随隔离配置声明约定，报告携带绑定来源。正式配方声明归 S6。E 不把命名参数塞进已冻结配方，不为路径另建全仓注册表。
4. **一套函数，两套数据**。纯名表函数接收绑定中的命名数据和 leg，派生链词根、具名 joint/link、链端接触体与匹配式；后缀/正则仍由已有 builder 生成。内部按链位置或已定义角色选关节，再取该 leg 的名字，不在每层选择新旧。关节名可含多个 `_`，用完整生成名映射到角色，或只剥已知 leg 前缀与 `_joint` 后缀，不用 `rpartition('_')` 识别词根。
5. **链结构不由名字杜撰**。链路径仍走实际 URDF 的父子关系，名表负责角色与接触端命名，不以固定关节数或元组位次替代真实树。旧 lizard 链缺少 lizard2 的根摆轴须继续可读；消费者用到某角色而机体未提供时，明确报告不适用或拒绝该检查，不造空数据。
6. **接触体与关节分开**。绑定提供每条腿的精确末端 link 名与其父 joint 名；模式优先由精确名生成，不扩大到任意 `.*_finger`/`.*_toe`。是否为末端按目标真实链声明：旧改名测试链中的掌/跖为中间段，当前 A 候选中的掌/跖为末端承重体，不按词根或旧链位置推断。运行时只选择正确集合，保留框架返回顺序，并与具名 leg 映射对照；不把名表顺序当 obs/action 索引。
7. **绑定先验真，再测量**。URDF 核对所需角色名、末端 link、对应父关节与链连通；运行时核对 robot、传感器及 action manager 的实际名称与映射。缺项、重名、跨前后肢错误、混合两套命名及空匹配都须带目标路径与差异拒绝；被诊断配置有意取消的动作通道不误报缺项，而按实际已声明通道核对。
8. **不改变既有公开符号语义**。旧常量/函数不全局翻转为新名，不删除或改签名；本轮双机体消费者显式走绑定数据。`PLANNED_ACTIVE` 不进入绑定或选名路径，E 与 S6 均不靠翻转它切换机体；模块内“采用即翻转 active”的既有说明随实现纠正，稳定映射不随采用改义。要移除旧公开接口先按 API 纪律另行弃用，不把旧名字解释成新名字，也不建立新候选的旧名别名。

### E3. 消费者迁移与交接范围

“导入了名表”不算接线，入口到取名、选择、输出的整条路径都要消费同一绑定。

| 消费链 | E 中要做的最小动作 | 验证落点 |
|---|---|---|
| Blender 候选 → URDF | `lizard2_stance_candidate.py` / `generate_urdf.py` 入口绑定构建目标，旧名源骨架与新名输出分别声明；关节/link/网格归属用角色映射生成，不抄词根 | Blender 真实读取骨架并调用导出消费者；源文件只读，输出临时隔离，不覆盖采用资产 |
| URDF → FK / 碰撞 | `check_leg_reachability.py`、`check_self_collision.py` 对每个输入独立绑定；替换链端、角色选取、限位查找旁路，保留树遍历与原有数值口径 | 同几何的新旧名 URDF 调用真实 `chain_joint_names` / `load_chain` / 现有碰撞姿态构造与检查 |
| 运行时 → 布局 / 站姿 / 步态诊断 | `check_joint_layout.py`、`stance_step_probe.py`、`gait_probe.py` 贯通最终目标、接触体、动作列与角色映射；模块采用 `leg_names` 别名，运行时列表不用模块名 | 两套隔离 cfg 真构建后调用实际诊断路径，读取机器人、传感器和动作通道；不用 py_compile 替代 |
| 接触诊断与在线协议核对 | `diag_metrics.py`、`diagnose_support.py`、`baseline_probe.py`、`check_contact_ownership.py`、`obs_protocol_live.py` 的后缀筛选改为消费绑定 | 新旧目标的末端集合、非末端排除与当前协议对表；正式传感器/奖励和协议声明仍交 S6 |
| 报告 → 图 / 评测 | `gait_probe.py` → `plot_joints.py`；`ablation_harness/baseline_metrics.py` / `baseline_eval.py` 从报告绑定和角色映射取值，不按当前机体重解释历史数据 | 同一 reader 顺次读取两套带绑定报告，不漏前后肢、不画空列；历史报告按原协议处理 |

历史报告没有新字段时保留原 reader 及其旧协议语义，不伪补“已核机体”证据；新绑定 reader 缺来源或名称冲突则拒绝。诊断量/列名若会变更评测语义，先核协议边界并交 `lizard2-contact-protocol`，E 不重写旧协议。

**接线现状**：URDF → FK/碰撞（`check_leg_reachability`、`check_self_collision`）、运行时（`check_joint_layout`、`stance_step_probe`）、报告 reader（`plot_joints`、`baseline_metrics`）、接触面（`diag_metrics.foot_ids`、`check_contact_ownership`、`obs_protocol_live`）与 `baseline_probe` 已按绑定接通，各有真跑读数与错配负例（`obs_protocol_live` 那条未验）；其余各行仍按旧名默认运行，未接线前不得指向新命名候选。

范围内残留硬编码逐点分成：要迁的名称选择、故意保留的旧协议/反例、几何或驱动假设。后两类不按字符串批量替换。实际漏点和延期站点只记验收记录；任何第一波必需消费者未接线，E 就不能交付。

### E4. 实施顺序、验收与第一波出口

1. **先绑定，再派生**：给名表最小入口数据与纯函数，保留原接口；接到一个 URDF 真实消费者后，才扩到 Blender、运行时和报告链。不增机器闸门，检查留在现有 self-check／测试入口。
2. **同几何双样本 + 负例**：同一份 URDF／报告／记录改名为另一套词（数值不动），经同一真实消费者读出同一组数；错配命名必须在消费前被拒。已按此法验过四个消费者，构造、命令与读数见 2026-10-12 记录追加六/七/九，本项不复述。
3. **真实解释器与接线**：标准 Python 验纯模块；Blender 验真实构建消费者；IsaacLab 用两套隔离目标验证运行时名称解析、传感器集合、动作列和至少一步诊断读回，不训练、不替换冻结配方。合成报告验证 reader 之外，至少消费一次真实诊断输出。新候选就绪后 A/D 再对其实际资产复验，改名样本不能替代候选。
4. **旧基线不退化**：先记录既有自检与相关离线套件的状态，再同条件复跑。既有红项按原记录及负责事项保留，不删断言、不借 E 改网格；受阻链留为未验，不算绿。仍受资产前提阻碍的必需运行时/报告验收不得以“旧红”豁免完成条件。
5. **证据与审核**：实施读数、复读命令、输入路径/绑定来源、实际消费者、负例结果与未验项追加到本项 evidence 的 2026-10-12 记录或后续具名记录；记录存在后才补指针。E 各步只自检，最终仍随 D 一次性由新上下文审核。

**第一波出口**：B 的线性对照与有效限速前置约束明确；E 的同一套入口绑定接口经实际消费者验证，显式服务旧机体和新名样本，运行时接线与报告读取有证据。名表内部自检、源码支持、编译通过不能单独满足 E。未跑 Blender/运行时、缺第二套目标或必需链受阻，留为未交付；不得以方案定稿宣告第一波完成。

**正式采用边界**：第一波证明双命名能力，不批准新候选几何/动力学，不完成 B 的承重对照，也不完成 S6。A/B/C 依本节接口推进；D 核对实际候选；S6 才迁正式配置/协议并退休旧机体版本。

**接触体名（当前要求：2026-10-12）**：当前无指/趾候选的末端承重 link 随腕/踝词根，前肢 `*_wrist`、后肢 `*_ankle`；对应掌/跖实体，不另建活动接触片。旧候选约定 `*_finger` / `*_toe` 只用于已有改名测试样本；现行旧机体与历史报告仍按各自绑定解释，不改写。运行时须核对目标的精确末端集合，不能把其它机器人的 `.*_foot` 当本仓默认，也不能按旧候选末端筛选当前候选。

## A. 机体候选（Blender：目的、探测链与验收）

写法复用 `rl_exp/tools/pipeline/declare_family.py` 的 `_plan_md()` 骨架（仅预览，不运行版本落位或锁更新）；方法见 `versioning.mdc` §A“复杂 PLAN 的探测链”。本节是隔离候选计划，不修订已训版本 PLAN；P1/P2 交接取具名记录，后续探测未执行。

### A1. 目的与结构约束

**用户拍板：2026-10-12**：采用类似人类腕—掌、踝—足的连接方式；“小腿根部”指小腿末端，不是膝侧。暂不建指/趾骨或指/趾根活动关节，掌/跖面直接承重；保留并重新定位腕/踝，不新增掌内关节或活动接触片，不强求旧关节数。“人手式”限定远端连接结构；蜥蜴式近端骨段朝向仍按上文目标，不改成直立人腿。

只回答：腕/踝移到前臂/小腿末端、掌段从掌根向前延伸后，能否在无指/趾根活动轴的情况下形成骨架—模型一致的承重候选？不预设答案是能，不用改名通过代替结构或物理通过。

- 腕/踝 pivot、前臂/小腿骨尾、掌/跖骨头与实际掌根共用连接点；掌骨尾朝远端延伸，实体掌段有长度与承重面。掌心、脚板中心或接触点不替代关节中心。
- 同改骨头 head/tail、关节标记、父子关系及网格归属：前臂/胫段止于腕/踝，掌/跖网格从掌根延伸并归腕/踝子 link。不能只移动显示骨线、改 pose 或平移旧脚板；碰撞体、质心和惯量随新网格复核，不沿用旧偏置。
- 前后肢分别镜像；轴与范围受 B 的线性驱动能力约束，不沿用旧轴或承诺渐硬弹性。E 须独立声明无指/趾候选角色与末端；同几何改名样本不代表此候选。

### A2. 关键假设 → 最小探测 → 停止条件

按 P1 → P2 → P3 → P4 推进；每一步仅做探测必需的最小修补，先证高风险前提，再批量制作或转换。各判据仅在本表定义，A3 与关闭条件引用；数值读数只进具名验收记录。

| 关键假设（可证伪） | 最小探测（输入/对照、入口与命令、观察判据） | 停止条件（失败/缺证时停哪一步、谁处理） |
|---|---|---|
| **P1：真实链能表达目标，不补回旧末端轴** | C0 复读旧基线；下方 P1 入口消费显式 `palm` 四角色及真实 Blender 父子树，旧 shared/split 不改义。判据与证据见 palm-chain-p1 记录。**声明一致，不证明几何**。 | 不将内存契约小样导出或采用；两肢几何探测见 P2 记录。 |
| **P2：骨架和网格在掌根连接，转动不脱节** | 一条前肢与一条后肢小样，对照修改前同腿；C1 补骨架叠加及肘/膝、腕/踝单关节转动，再扩四肢。共同坐标系量连接残差、掌骨方向、网格端点、镜像与运动连接残差；pivot 在掌根而非板中央。角度档、位置/镜像容差先按测量精度提出。**几何/运动行为**。 | 小样及诊断复读见 palm-p2-sample 记录；用户确认外观及位置/网格容差后再扩四肢。缺命令/批准、错位或脱节，停小样回 A；不转换、不放宽容差。 |
| **P3：导出保留同一连接，轴与真实网格不冲突** | P2 及用户外观确认后，C2 出隔离 URDF，核对后 C3 转独立 USD。C4 复用真实树/FK/碰撞，核对 DCC—URDF—USD 的树、pivot、轴、末端、网格及质心/惯量。旧链 + 主动腕踝为零号对照；同一批准目标覆盖支撑—摆动周期与限位，判据引用上文目标及 R1–R5，导出误差容差先获准。**结构一致 + 几何行为**。 | FK `--pose` 固定旧链维度，旧 self-check 含机体专属断言，碰撞有位次/链距离假设。执行者补真实角色、实际碰撞对与 C4 命令；不硬套旧参数/删断言。缺命令、绑定错、漂移或碰撞失败，停隔离导出回 E/A，不进 B/D。 |
| **P4：无指/趾轴的掌面承重能完成目标动作** | 交 B 的同几何线性对照、D 完整周期；目标、载荷、驱动、窗口相同，分记掌面接触、变形、滑移/滚动与推进。`stance_step_probe.py` 先接真实末端/动作通道；S5 比较前确认预算、幅度、窗口及性能判据。**动力学行为，FK/静力不能替代**。 | 缺新链隔离 cfg 与预算。执行者补原入口和精确命令，用户确认判据，接触口径交 `lizard2-contact-protocol`；缺证停 B/D 开跑前。失败回 A/B，不归因奖励、不自动加轴；额外自由度凭缺失能力请用户决策。 |

### A3. 探测入口与计划命令

从仓根运行；占位符替换为已核隔离路径，生成器会重建输出网格，禁止指向采用资产。C0 验旧工具；C1–C3 是已有接口，按 A2 前提执行，不代表新链已可验。C4/P4 未接线，不虚构命令。

**C0：旧工具基线（只读，不指定候选）**

```cmd
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp\tools\verify\check_leg_reachability.py --self-check
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp\tools\verify\check_leg_reachability.py --break-test
```

**P1：只读真实消费者契约（无候选资产输出）**

```cmd
"E:\SteamLibrary\steamapps\common\Blender\blender.exe" --background --factory-startup --python-exit-code 1 --python rl_exp\blender\scripts\lizard2_stance_candidate.py -- --contract_self_check
```

回归：末尾加 `--regression_without_fix`，预期非零；证据与边界见本项 palm-chain-p1 记录。

**C1：候选 Blender 入口（先完成 P1/P2 的最小修补）**

```cmd
"E:\SteamLibrary\steamapps\common\Blender\blender.exe" --background --python rl_exp\blender\scripts\lizard2_stance_candidate.py
```

输入 `rl_exp/blender/lizard_stance.blend`；上式是旧入口，固定输出采用候选路径，**不用于 P2**。P2 走同脚本显式 `--p2_sample --output_dir --diagnostic_angles`，命令、回归与边界见 palm-p2-sample 记录；禁止覆盖采用资产。

**C2：隔离 URDF 导出（先通过 P2）**

```cmd
"E:\SteamLibrary\steamapps\common\Blender\blender.exe" --background --python rl_exp\blender\scripts\generate_urdf.py -- --robot lizard2_candidate --blend "<已核候选.blend>" --out_dir "<隔离URDF目录>"
```

**C3：隔离 USD 转换（先完成 P3 的 URDF 检查）**

```cmd
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" rl_exp\tools\pipeline\convert_urdf.py --headless --robot lizard2 --urdf "<隔离URDF目录>\lizard2_candidate.urdf" --name <独立候选资产名>
```

`--robot lizard2` 仍读取该家族 dev yaml 的转换参数，不等于新链运行配置；必须核对驱动匹配。`--name` 决定 `rl_exp/assets/<独立候选资产名>/` 输出，禁止省略或与采用资产同名；清理仅限核实过的隔离输出。

**C4 与 P4：待接线的真实候选检查**

复用 `check_leg_reachability.py`、`check_self_collision.py`、`stance_step_probe.py`；执行者接真实角色/末端并核 CLI 后填 FK、碰撞对和隔离运行命令。不硬填旧五轴 pose/`split` 或未批准的默认 clearance/幅度；编译、help、名表自检不解除 A2 行为前提。

### A4. 验收与交接

P1–P3 成立、覆盖四肢镜像且用户确认外观和转动连接后才交 B/D；A 交付不等于 P4 动力学通过或允许采用。判据/失败出口引用 A2，记录和指针按 E4 第 6 条办理；正式采用边界仍按本项“边界”。

## B. 驱动（能力表先出，可与 A 同时）

1. 能力表已归 `acceptance/records/2026-10-12-lizard2-drive-capability-and-name-inventory.md` A 节（判词、源码坐标与未知项），本项只留它给的**约束**：位置→力矩通路按构造就是线性 PD，**渐硬/渐变的趾端恢复力今天不可表达**（要么新增 Python 执行器子类、但丢掉本线特意选的物理步长 implicit PD；要么走每子步外力、可达性未验证）⇒ A 选 pivot/轴时**按线性对照**进行，或先回来重划弹性这一节的范围。不新建驱动机制、不改配方。
2. A 给出候选后，在隔离诊断配置里验证重新定位的腕踝驱动与掌/跖承重，不再设置本轮已取消的指/趾根驱动。与同几何线性基线比较偏转回位、承载与推进；是否需要额外远端自由度，以目标动作无法表达的真实证据另行提出。读回与力矩能力分开，PD 请求量、估算与引擎实际量分开。
3. 速度上限按整体记录“联动设计修订”第 4 条：启用须有速度—载荷—跟踪/稳定包线和同条件有/无限速对照，否则明确不启用并写工况边界。**另有一笔前置的账**（具名缺口见 2026-10-12 记录的 A7 条，本项不复述）：implicit 执行器把配方设的 `velocity_limit` 静默作废，而 USD 关节 prim 是否自带限速未查 ⇒ "启不启用"这个问题本身还悬着；本轮不改配方。

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
