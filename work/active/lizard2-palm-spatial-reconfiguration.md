---
id: lizard2-palm-spatial-reconfiguration
title: 肩髋三轴掌链候选与缺失运动能力修复
scope: rl_exp/blender/scripts, rl_exp/tools/diagnose, rl_exp/tasks/joint_names.py
status: in_progress
landing: rl_exp/blender/scripts, rl_exp/tools/diagnose
next: 执行者按镜像记录提出接缝处理及四肢组合的相位、根运动与预算；运行时与 A/E 交接继续。
close_when: 新上下文核验实际候选、行为证据与交接；有缺口不关闭。
evidence: acceptance/records/2026-10-16-lizard2-local-path-mirror.md, acceptance/records/2026-10-16-lizard2-local-path-quarters.md, acceptance/records/2026-10-16-lizard2-local-path-postprocess.md, acceptance/records/2026-10-15-lizard2-palm-local-contact-repair.md, acceptance/records/2026-10-15-lizard2-palm-local-path-probe.md, acceptance/records/2026-10-15-lizard2-palm-phase-target-preparation.md, acceptance/records/2026-10-15-lizard2-palm-spatial-refined-boundaries.md, acceptance/records/2026-10-15-lizard2-palm-spatial-static-slices.md, acceptance/records/2026-10-14-lizard2-palm-spatial-review-fixes.md, acceptance/records/2026-10-14-lizard2-palm-spatial-trial-checkpoint.md, acceptance/records/2026-10-14-lizard2-palm-spatial-design-decision.md
---

## 当前范围

当前目标为肩／髋三个共中心串联轴，接肘／膝和腕／踝；无指／趾活动轴。隔离试作检查点、复读入口及验证边界归 trial-checkpoint 记录；当前继续补完整动作、碰撞拒错和运行时验证。总项 A/E 接收候选，正式采用仍走 D/S6。

按总项“A–E 当前执行关系”分段交付：最小绑定和真实树先支撑 A 的运动学，实际候选再交 E 扩到运行时和报告链；不以本项关闭作为总项几何推进的前提。限位、承重 PD 及躯尾标定由专项与总项 B/C 承接，最终集成仍归 D。

采样与证明范围按 `acceptance/records/2026-10-16-lizard2-local-path-quarters.md` 的“用户确认的验证范围”执行；关闭审核按同一范围，不另加连续域证明前置。另两腿局部镜像的覆盖与未完边界取 evidence 的镜像记录，当前继续接缝及四肢组合；单腿镜像不替代组合验证。

## 构型与实现方案


| 链顺序 | 前肢词根 | 后肢词根 | 位置与功能 |
|---|---|---|---|
| 1 | shoulder_swing | hip_swing | 肩／髋中心；中立姿态下沿局部竖直方向，控制水平摆向 |
| 2 | shoulder_abduct | hip_abduct | 与第一个轴共中心；横向轴控制上臂／大腿抬落 |
| 3 | shoulder_twist | hip_twist | 与前两个轴共中心；轴线沿肩到肘／髋到膝，随前两个轴运动 |
| 4 | elbow | knee | 肘／膝中心；下段屈伸 |
| 5 | wrist | ankle | 下段末端与掌根共点；掌段屈伸、拨动 |

- **轴系与姿态**：明确父子顺序、零位、局部坐标和正方向，不能把“竖直”当成整个动作中固定的世界方向。新增轴不制造一段有长度的虚构骨段；前后肢分别定义中立朝向与范围，左右镜像按实际轴推导符号，不默认全部同号。
- **骨架与实体**：上臂／大腿实体及肘／膝子链归扭转轴下游；中间承载 link 仅用于串联关节表达。保持当前中立体高、骨长、掌形、颈尾与落掌位置作为初始对照；若运动证据要求改变几何，回总项 A 明确修改。同步审查网格归属、关节连接、质量／质心／惯量，不能只增加名字或只转显示骨。
- **数值与驱动**：沿用单轴驱动体系，三个方向独立给目标；其组合仍受几何和动力学耦合。中间 link 的质量与惯量须说明近似及总量守恒，不把试作的拆分方案当已验物理。诊断角度、力矩和速度不直接升级为解剖范围或策略限位；实际标定归限位 PD 专项。检查目标包络内的轴退化、奇异姿态与连续性，串联三轴和球关节不宣称在任意姿态、限位及驱动下完全等价。
- **命名与消费**：新候选显式绑定 `palm_spatial`；`palm` 保持原四轴对照含义，`shared`／`split` 保持原语义。逐一检查骨树、导出、FK、动作列、观测、接触体和报告读取；肘／膝从链第三位移到第四位，禁止沿用旧位次或硬编码四元素数组。末端仍是 wrist／ankle。
- **接触目标**：共面只要求中立站姿；行走允许拨动、滚动及接触边变化。固定落点平掌俯仰仅作新旧机构的可选能力对照，不代表自然步态必须全程平掌，也不作为本次需求来源。

## 下一步

1. 审查 `rl_exp/blender/scripts/lizard2_palm_spatial_candidate.py`、`rl_exp/tools/diagnose/palm_spatial_probe.py` 与名表增量；绑定源 blend、URDF、轴／限位、代码及网格哈希，使用新隔离输出目录。旧 shared/split/palm 作为兼容对照，新目标显式绑定 palm_spatial。
2. 一前一后再四肢核验共中心、长轴方向、真实随动与镜像。纯扭转时肘／膝中心不漂移，下段和掌转出腿平面；新轴置零复现旧运动。保存重开 Blender 后对照独立 FK；错轴、错 pivot、未重绑网格必须拒绝，锁轴对照须失去对应能力。
3. 按 `rl_exp/docs/leg_geometry_reuse.md` 先选择可复用读点与证据，只补新增轴影响的非零上下文和耦合切片；未适配的旧位次扫描不得消费新链。按正文构型约束检查组合动作、奇异性、轨迹连续与限位余量；按接触相位验证迈步、转向、回正及反曲／翻掌／穿地／自碰撞。先按限位 PD 专项步骤 5 收口逐相位目标和获准工程取值，再实现五轴求解与独立 FK 对照；旧四轴求解器不得测新候选。历史平掌样本只作对照，局部满秩或离散通过不证明完整安全域。
4. 扩展实际导出与运行时消费者，核对树、轴、质量惯量、动作／观测列和接触体；逐轴与组合运动实测虚拟承载 link 稳定性、驱动耦合。将受影响的坐标、惯量、连接碰撞和动作映射交 `work/active/lizard2-restored-limits-pd-validation.md` 重验；其完整周期、承重、PD 与最终范围保持在办。
5. 结果进验收记录并同步指针；候选修复和交接齐备后置 pending_review，交不带执笔历史的新上下文审核。

## 关闭条件

- 审核实际源／候选、消费者和复读证据；不得以试作存在、声明一致或执行者总结代替验证。
- 骨架与实体运动、镜像及旧运动保留成立；真实失败对照和错误输入被拒绝，具名动作范围的连续性、碰撞及运行时轴／状态有证据。
- 向总项 A/E 交带身份的候选，向限位 PD 专项交明确重验范围；未完动作不得随关闭消失，正式采用和训练不在本项授权内。
- 通过审核后关闭；可修缺口退 in_progress，仅用户能解除的缺口置 blocked。
