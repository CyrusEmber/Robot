---
id: lizard2-restored-limits-pd-validation
title: lizard2 恢复模型：限位与 PD 验证前提及标定
scope: rl_exp/blender, rl_exp/tools/diagnose, acceptance/records
status: in_progress
landing: rl_exp/blender/scripts/generate_urdf.py, rl_exp/blender/scripts/lizard2_stance_candidate.py, rl_exp/tools/diagnose/palm_motion_boundaries.py, rl_exp/tools/diagnose/palm_5b_targets.json, rl_exp/tools/diagnose/palm_motion_view.py, rl_exp/tools/diagnose/palm_spatial_inertia.py, rl_exp/tools/diagnose/palm_spatial_tracking.py, rl_exp/tools/diagnose/palm_spatial_standing.py
next: B 接肘膝升速记录核大摆幅/快轨迹边界、胸部余量与限速对照；不自动调 PD。
close_when: 新上下文按正文关闭条件审核实际落点与证据，合格后交机体总项 B/C/D；缺证不关闭。
evidence: acceptance/records/2026-10-22-lizard2-left-elbow-speed.md, acceptance/records/2026-10-22-lizard2-velocity-limits.md, acceptance/records/2026-10-22-lizard2-velocity-observation.md, acceptance/records/2026-10-19-lizard2-load-transfer-lift.md, acceptance/records/2026-10-19-lizard2-single-leg-lift.md, acceptance/records/2026-10-19-lizard2-a-geometry-replay.md, acceptance/records/2026-10-16-lizard2-support-schedule.md, acceptance/records/2026-10-16-lizard2-local-path-combined.md, acceptance/records/2026-10-16-lizard2-local-path-mirror.md, acceptance/records/2026-10-16-lizard2-local-path-quarters.md, acceptance/records/2026-10-16-lizard2-local-path-postprocess.md, acceptance/records/2026-10-15-lizard2-e-spatial-runtime-wiring.md, acceptance/records/2026-10-15-lizard2-palm-local-contact-repair.md, acceptance/records/2026-10-15-lizard2-palm-local-path-probe.md, acceptance/records/2026-10-15-lizard2-palm-phase-target-preparation.md, acceptance/records/2026-10-15-lizard2-palm-spatial-refined-boundaries.md, acceptance/records/2026-10-14-lizard2-palm-spatial-review-fixes.md, acceptance/records/2026-10-14-lizard2-palm-phase-constraint-correction.md, acceptance/records/2026-10-14-lizard2-5b-motion-boundaries.md, acceptance/records/2026-10-14-lizard2-a-priority-review.md, acceptance/records/2026-10-14-lizard2-restored-validation-handoff.md, acceptance/records/2026-10-13-lizard2-restored-limits-pd-open-issues.md, acceptance/records/2026-10-13-lizard2-hindlimb-restored.md
---

## 范围与交接

本项承接[总项](lizard2-body-drive-candidate.md)的恢复模型机械限位与全部关节默认 PD；整体结构、A/P2/P3 与 B/C/D 集成判据归总项。范围修订依据见[默认驱动与 RL 职责记录](../../acceptance/records/2026-10-19-lizard2-chest-standing-pd.md#用户定案默认关节驱动与强化学习职责)：保证关节正常驱动，移重、抬落、步态、转向/恢复和躯尾协调由 RL 学习，性能验收转交 [S6](lizard2-family-landing.md#s6-直接执行正式采用预检与训练验收)，不取消、不记为完成。本项完成不等于正式采用或完整步态验收。身份、读数和边界取 evidence；不把诊断导出或历史过滤对照当合格资产。

处理恢复原后肢尺寸、按 `work/active/lizard2-palm-spatial-reconfiguration.md` 重构肩髋的隔离候选；接收后重新绑定受影响的轴、动作列、惯量和连接碰撞，旧四轴读数只作对照。reward、冻结配方和正式资产保持不变；四掌共面是中立姿态要求。新参数进隔离配置，口径与拒错进实现/测试，测量结果进 `acceptance/records/`。结构决策及来源归重构事项；额外结构变更仍交总项 A。

## 执行顺序

先接收重构事项的实际候选并收口 1/2；5a 按已有几何证据及具名真实链缺口交 A，与 3/4 并行。按[用户最新定案](../../acceptance/records/2026-10-19-lizard2-a-delivery-plan.md#用户定案撤销手工步态交付前置)撤销手工步态回放、根平移、无滑移及完整动作周期交付前置；对应惯量、碰撞及真实接线前提成立后即可做 6 的默认驱动检查。5b 保留机械限位与几何禁区交付，运动性能由 S6 按实际 checkpoint 与接触协议验收，不要求复现手工 q(c) 目标。编号保留用于追溯，不表示必须串行完成 1–6。A 的几何结果无需等待本项关闭；正式导出与接口仍由原 A/E 接续，惯量、碰撞、机械限位与有效力矩/速度边界缺口继续在办，不称整个 A 已完成。

## 下一步

**当前几何交付**按[总项 A4](lizard2-body-drive-candidate.md#a4-交接)及[用户最新定案](../../acceptance/records/2026-10-19-lizard2-a-delivery-plan.md#用户定案撤销手工步态交付前置)执行，候选及具名缺口接[本轮回放记录](../../acceptance/records/2026-10-19-lizard2-contact-path-correction.md)。用户已确认当前回放，不据此推定另有外观批准或几何验收；不再等待手工步态、根平移、无滑移或动作周期交付。已有两腿、镜像、组合与支持相位证据按输入/行为变化复用，只补真实几何缺口；机械限位、正式导出/接口与受载驱动缺证按原 A/E 及 5b/6 在办，运动性能交 S6，不新增全 ROM 或连续域证明。

**B/C/E 接续**：步骤 3 的新正式导出输入固定基惯量依据取[当前两姿态复验](../../acceptance/records/2026-10-19-lizard2-spatial-inertia-repair.md#新正式导出输入的运行时惯量复验2026-10-20)，旧输入修正只按原身份复用，不混用新旧 USD 或将固定基对角当自由基/接触有效惯量；新输入全部关节逐轴工况取[当前小幅切片](../../acceptance/records/2026-10-19-lizard2-spatial-small-tracking.md#新导出输入全部关节小幅驱动复验2026-10-20)，全部关节切片仅为无重力工况；[胸俯仰自重](../../acceptance/records/2026-10-19-lizard2-spatial-small-tracking.md#胸俯仰自重280复验)按其预算/静差复用，不外推其它关节或正式采用；历史增益、固定基座组合及自由基座静站仍分别绑定[承重静站记录](../../acceptance/records/2026-10-19-lizard2-loaded-standing.md)的原输入，不自动升级为新目标通过。按[默认驱动与 RL 职责记录](../../acceptance/records/2026-10-19-lizard2-chest-standing-pd.md#用户定案默认关节驱动与强化学习职责)盘点腿部五角色、胸颈尾全部实际关节的小幅/组合与已知载荷保持/跟踪证据；复用[水平胸部左前腿记录](../../acceptance/records/2026-10-19-lizard2-level-leg-pd.md)的夹具、自重、运动增量与绝对静差边界，不外推其它关节、整机承重或默认 PD 定稿。历史抬落失败保留原义，不据此判单关节驱动不合格或原样重跑。沿用[PD 范围修订](../../acceptance/records/2026-10-19-lizard2-pd-scope-correction.md)，声明基座、重力、载荷与有限静差；胸部姿态只作观测，不要求水平，不自动追加移重、补偿控制器或增益扫描。安全 reset/站姿样本及实际驱动力通道缺口保留，区分请求估计与实际力矩；缺遥测不声称真实饱和已验证，也不把穷尽传感建设设为默认驱动前置。缺目标幅度、载荷/误差依据、频率/阻尼、力矩/速度预算、窗口或资源/停止预算时集中提请用户确认后才测试，不新增数值。步骤 4 的具名过滤及负例、E 的 baseline 实际写读链仍取 e-spatial-runtime-wiring 原边界；正式导出链与有效边界继续交付，退出传播局部回交其跨入口事项。时间映射、承重抬落/低速直行、转向/恢复与躯尾性能比较明确交 S6，不作为步骤 6 或训练接入前置。E/S5 另核逐角色真实 action 权限及固定/门控依据，需 RL 协调的关节必须可达；不自动改冻结配置，仅 S6 经授权新配方训练。不加 PD 压异常或扩大过滤，不重新从几何探索起步。

1. **固定输入与失败判定（执行者）**：先读 a-priority-review 的最新进展，再按 restored-validation-handoff 追溯原始问题；清点问题记录所用在办脚本、导出器改动、配置及本机产物，形成可复读的代码版本、输入绑定和不覆盖历史产物的命令。`palm_pd_probe.py`、`palm_asset_probe.py` 及相关导出片段须完成代码归属与版本落地。逐份比较报告代码/输入与最终版本，只重跑受行为变更影响或缺证的检查；不因日期或脚本哈希变化无差别重跑，也不混用不兼容版本。退出传播修复归 `work/active/exit-status-swallowed-by-app-close.md`，将该入口交其覆盖；本项验收真实成功/失败各一例，异常可见、退出状态正确，失败不得产生可误读为成功的报告。修复期间同时核对日志、报告身份与完成状态，不只看命令退出码。

2. **中立位置与坐标对照（执行者，先于动力学结论）**：明确 Blender 世界、URDF 根/link、USD 及运行时 actor/质心 frame 的转换；登记初始化、状态写入、缓存刷新和物理步时点。逐 body 输出位置与姿态残差，并用实际关节状态构造对应 FK；先检验明确的零位快照，再检验运动后快照，禁止把已运动状态与零位混比。分清检查错误、读取时序或导出/导入偏差，在责任层修复；误差预算按精度与转换链预先说明，不能按失败读数放宽。真实错 pivot/轴/读取状态负例须被拒绝，修复前失败、修复后通过；据此界定历史报告重跑范围。

3. **质量与惯量一致性（执行者，步骤 2 后）**：逐 link 核对质量、质心、惯量张量及其坐标系、单位和导入处理；在相同关节姿态与相同基座约束下比较同一定义的关节惯量，解释锁定下游投影与运行时质量矩阵读数差异。明确近似质量模型的适用范围，不能把改用运行时矩阵视为差异已解决。读回与预期对齐或差异机制被验证后，才用对应惯量选诊断阻尼；仍有未解释差异则停本步。

4. **连接区碰撞归属（执行者，步骤 2 后；可与步骤 3 分开处理）**：逐对确认原候选相交来自合法机构连接还是需要修复的网格干涉。对具名连接对记录树关系、几何理由与运行时过滤读回；实际过滤集合须与批准的具名连接集合严格相等，不能仅比较“生成列表”和其写入读回；补扫描额外连接对的拒错及真实跨腿接触反例。只排除有依据的连接对，保留跨腿与其它真实自碰撞。未过滤/具名过滤使用相同姿态、根高度和驱动做对照，尽可能用接触对证据归因，净力不足时保留未知；不能靠加大 PD 压住初始排斥。用应保留的真实非相邻碰撞作负例，确认没有误滤；明确哪些几何仍需回总项 A 修复。

5. **真实机构几何与机械限位**：

   **5a：真实链与实体几何交接**。按总项 A4 核具名候选的真实树、肩髋三轴与肘膝/腕踝的零位及非零运动、轴/pivot/符号、网格归属、连接与四肢镜像；完整 FK 与实际实体随动相互对照，不以仅脚板坐标或显示平移代替整条腿检查。优先复用已有四肢、组合及真实消费者证据，只补输入变化或真实缺证，不再求解手工步长、相位、抬脚净空、根前移或完整周期。

   **5b：机械限位与几何禁区**。机械范围须绑定真实轴、零位、符号和单位，在隔离配置维护并核导出；Blender 约束不当仿真限位。保留肘膝反曲、翻掌、穿地、连接错误和真实实体干涉检查，按已批准的代表姿态/有限采样复验受影响组合，仅排除有依据的连接对。已有路径只支持原工况，不作完整安全盒、解剖范围、全 ROM 或连续域证明；未解释的范围/干涉缺口留为具名未判并回 A，不能因删手工动作要求而消失。

   **证据与边界**：用户回放确认及手工步态前置撤销见[最新定案](../../acceptance/records/2026-10-19-lizard2-a-delivery-plan.md#用户定案撤销手工步态交付前置)。原相位、轨迹、回放、材料点残差与修正报告保留历史诊断用途；不再作为当前交付目标或无滑移保证，不新增滑动阈值，不要求 RL 复现 q(c)。复读工具继续可用，但不因工具存在重开手工步态开发。动作性能和真实承重滑移由 S6 的学习策略与接触协议评测，固定身体下能移动脚板不算走路。

   **具名交接**：A 交源件/URDF/网格/隔离 USD 身份、配置、真实几何证据及未解问题，E 接正式导出/运行时消费；步骤 6 按对应惯量、碰撞与接线前提独立检查全部关节默认驱动。几何预算或工程容差缺失先集中提请确认，不代填；正式导出、机械限位及真实碰撞缺口仍留在原事项。

6. **全部关节默认 PD：惯量初值与少量校准（对应 1–4 前提及实际接线成立后）**：

   **实际关节覆盖**：腿部五个角色及胸颈尾全部实际关节分别核对驱动、零位、符号和限位，twist 不继承旧 foot 或 abduct 的参数。逐轴小幅跟踪后做适度组合激励，在同一候选和固定初值下观察其它轴的响应、接触约束及力矩/速度边界；标量 PD 的初值不是动力学解耦证明。中间承载 link 的惯量近似、总量守恒与姿态依赖由步骤 3 给出，失稳或轴退化须定位后再继续。总项 B/C 定义交付范围，本步骤维护实际标定方法；不以 5a 手工周期、抬落或胸部水平为前置。

   **初值**：保持现有线性 implicit 驱动，先核运行时 drive type。力矩型旋转驱动取 `Kp=I_eff*(2πf)^2`、`Kd=2ζ*I_eff*(2πf)`；`f` 为 Hz，`ζ` 为阻尼比。惯量取步骤 3 已核的姿态/基座条件，登记 armature 是否已计入；锁定其它自由度的投影或质量矩阵对角只作近似，不能当自由浮基、接触下的精确惯量。左右同角色共用调参规则，按各自惯量计算。按小幅目标与已知载荷检查力矩预算依据、允许有限稳态误差和有效速度边界；初值不够保持/跟踪或请求估计触及预算时先回查载荷与设置，不盲目加 P，也不据估计宣称实际饱和。组别频率、阻尼、目标幅度/速度、载荷、误差/超调口径、窗口、资源/迭代预算与停止条件比较前提出依据并获用户确认，缺项不测试，不照搬旧诊断常数或新增数值；初值与既有无重力样本均不等于默认 PD 定稿。

   **最小受控检查**：同一套候选初值覆盖限位内逐关节小幅平滑跟踪、明确基座/重力/自重或已知载荷下的保持与跟踪、适度组合耦合检查；可用支持机身夹具隔离驱动，不能以无重力空载通过替代受载证据。允许预先声明的有限静差，检查无失控或持续振荡。固定物理步长、目标更新率、目标速度约定和重置状态，按已批准预算执行；安全 reset/站姿样本作集成检查，不要求胸部水平、手工单腿抬落或低速步行成功。读回 PD/限位/力矩/速度设置，分清请求估计与实际驱动力；缺可靠实测通道不称实际饱和已验证，保留未知与设置/预算依据，不追加穷尽传感项。失败先分辨限位、碰撞、载荷、边界与跟踪问题；只改对应关节组的一类参数并复验受影响检查，到预算上限带失败证据停，不作全关节网格扫描。

   **交付与后续**：逐关节覆盖、最小受载行为、组合响应、实际设置及适用边界交总项 B/C 与 D/S5，不先宣告默认 PD 最终合格。有效限速启用仍须原批准的触边激励和同条件有/无限速对照，否则明确不启用及其边界；实际 USD/执行器 cap 未知项不得消失。S5 核逐角色真实 action manager 目标、缩放/偏置与实体随动，声明固定或阶段门控，需协调关节必须可访问；不自动改冻结配置。原移重/抬落、物理时间映射、低速直行、转向/恢复及躯尾性能对照交 S6 的学习策略验收，不作为本项关闭或训练接入前置、不记为完成。机械限位、几何禁区和正式导出缺口仍由本项/A/E 完成；训练仅 S6 经用户授权的新配方执行，本项不授权训练或正式采用。

## 关闭条件

- **审核者与输入**：执行者完成后置 `pending_review`，next 点名新上下文审核者；其对照本项落点、绑定输入、原始报告及真实复读审查，不以执行者总结代替证据。新记录存在后与 evidence 指针同次提交。
- **可观察验收**：步骤 1–4 的失败机制已定位并有修复/解释及真实正反例；步骤 5 的机械限位、几何样本与禁区及步骤 6 全部实际关节的配置、运行时读回、小幅/组合与最小已知载荷行为可复读，PD、力矩/有效速度边界与未知项清楚。原几何/容差与资源预算保留，参数与检查口径有实现落点，无未解释的一致性差异被当作通过；有限静差须声明，无重力或源码证据不替代受载稳定性，缺遥测不称真实饱和已验证。不新增全 ROM、连续域证明或手工动作成功前置。
- **交付边界**：按默认驱动与 RL 职责记录向总项 A/B/C 交付具名候选与记录，向 D/S5 交付驱动工况、边界、安全 reset/站姿样本及真实动作权限缺口；原抬落/移重、时间映射/直行、转向/恢复及躯尾性能对照明确交 S6，不取消或记为完成，不阻断默认驱动交付。退出码事项只复用其机制与证据，不代替关闭该跨入口事项；正式采用与授权新配方训练仍走 S6。
- **结果处理**：独立审核通过才移至 `work/closed/2026/` 并补 outcome；可修缺口退 `in_progress`，只有用户能解除的前提才置 `blocked` 并具名说明。未完成动作不得为关闭本项而省略，证据改变后重审。
