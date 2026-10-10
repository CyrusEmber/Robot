---
id: lizard2-s3-drive-load
title: lizard2 S3 执行：足部柔顺驱动与承重联调
scope: rl_exp/tasks, rl_exp/tools/diagnose, rl_exp/tools/verify, acceptance/records
status: open
landing: rl_exp/tasks/lizard2_recipe.py, rl_exp/tools/diagnose/stance_step_probe.py, rl_exp/tools/verify/check_actuator_budget.py
next: 取得 S2 已审行走姿态/轨迹后，按正文实施隔离驱动候选与承重对照；腕踝和趾根分别设计并实测，不整组降低 PD。趴姿仅挂账，当前不求解、不仿真，恢复须用户决定。完成后置 pending_review，请新上下文核对 R4/R5、真实驱动读回与完整周期动力学。
close_when: 新上下文核对已消费的驱动能力/联动方案、负载偏转回位、承载推进及新接触口径；诊断异常与失败关联、性能标定依据和复读有具名记录后交 S4/S5。未完成动力学不得以静力/声明关闭，未定性能阈值不造通过；趴姿仍挂账。
depends_on: lizard2-s2-motion-and-prone
evidence: acceptance/records/2026-10-10-lizard2-land-body-drive-overall-work, acceptance/records/2026-10-08-lizard2-joint-design-review-contract, acceptance/records/2026-10-09-lizard2-drive-readback-audit, acceptance/records/2026-10-09-lizard2-leg-joint-inertia-and-gain-caliber
---

## 直接执行

1. 消费 S0 能力调查、S1 联动方案和 S2 绑定周期，不把原生能力首次调查留到此步。核实实际驱动更新/读回层次；发现能力与方案不符即交 S0/S1 回修，不先生成另一套骨骼。
2. 在隔离诊断配置中实现已选腕踝/趾根候选，与同几何同工况线性基线比较偏转回位、承载/推进收益。力矩能力与刚度/阻尼分开，专用实现仅在已确认表达缺口时最小补充并留检查，不改共享旧 term 语义。
3. 代表姿态承重及完整周期先复核测量口径，分开关节变形、原点移动、真实接触点滑动和滚动/近似点切换；采用整体记录“联动设计修订”的口径对照。现有采样可读的迟滞/饱和/振铃只作诊断，不设独立准入门，造成安全或任务失败时才列具名失败因素。
4. 跑 S2 周期的诊断动力学，读取实际增益/力矩/速度设置与跟踪、载荷、滑移、滚动和近端代偿；旧 checkpoint 只作影响对照。结合新足部几何/驱动/分组标定性能与速度—载荷包线；readback不证明限值合理，阈值不得由失败读数反定。
5. 趴姿只挂账，不初始化、不求解、不仿真；恢复须用户决定，不通过关闭重力、冻结机体或取消全部驱动伪造放松。
6. 审几何、驱动与工况代价后向 S5 提交性能阈值和限速选项依据；比较前固定尺度与测量口径，最终协议阈值在 S5 批准。需改几何回 S1/S2，需改需求回 S0；收益未证时可拒绝或暂缓弹性分支，不为诊断齐全而扩测。

## 交付与边界

- 候选驱动配置/实现路径、运行绑定、原始采样与同条件对照、通过/失败和复读命令进 `acceptance/records/<日期>-lizard2-s3-drive-load.md`；记录存在后补 evidence。
- S4 可消费已审的行走驱动与周期，S5 消费已审参数和机制；趴姿挂账不阻碍行走交接，也不解除本项关闭前的范围决定。不用本项未冻结诊断配置替换已训 v3。
- 审核记录按整体记录“审核输入绑定约定”落地；本项只留已存在的记录指针。
- 不启动 PPO 训练，不增加游泳或趴姿策略任务。诊断若需例外接触初始化须显式隔离场景，不能全局放宽行走终止。
