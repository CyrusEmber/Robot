---
id: lizard2-s3-drive-load
title: lizard2 S3 执行：足部柔顺驱动与承重联调
scope: rl_exp/tasks, rl_exp/tools/diagnose, rl_exp/tools/verify, acceptance/records
status: open
landing: rl_exp/tasks/lizard2_recipe.py, rl_exp/tools/diagnose/stance_step_probe.py, rl_exp/tools/verify/check_actuator_budget.py
next: 取得 S2 已审姿态/轨迹后，按正文实施隔离驱动候选与承重对照；腕踝和趾根分别设计并实测，不整组降低 PD。完成后置 pending_review，请新上下文核对 R4/R5、真实驱动读回、稳态趴姿与完整周期动力学。
close_when: 新上下文核对驱动更新率、请求/实际口径、负载偏转回位、饱和振铃、推进滑移及趴姿稳态；参数方案和失败有具名记录，通过后交 S4/S5。未完成动力学不得以静力或线性 PD 声明关闭；需上游改动退回并重验受影响样本。
depends_on: lizard2-s2-motion-and-prone
evidence: acceptance/records/2026-10-10-lizard2-land-body-drive-overall-work, acceptance/records/2026-10-08-lizard2-joint-design-review-contract, acceptance/records/2026-10-09-lizard2-drive-readback-audit, acceptance/records/2026-10-09-lizard2-leg-joint-inertia-and-gain-caliber
---

## 直接执行

1. 消费 S2 绑定候选与 S0 工况，追踪现有执行器和物理子步接口；优先原生弹簧/阻尼和有效限速。先提交最小驱动实现方案，不能直接把采样显式 PD 当物理子步驱动或把硬限位当弹性。
2. 在隔离诊断配置/工具中分开腕踝与趾根；比较线性基线、腕踝主动柔顺参考和趾根被动弹性候选。参数放候选配置，力矩能力与刚度/阻尼分别调整；只在确需时写最小专用机制和可运行回归检查，不改共享旧 term 语义。
3. 对代表姿态做承重与单关节扫描，读取引擎实际增益/力矩和速度上限，量测偏转、回位、接触载荷、饱和与振铃。复用 `stance_step_probe.py` 和 `check_actuator_budget.py`，先核对候选布局和通道含义。
4. 跑 S2 完整周期的诊断性动力学，核对实际跟踪、推进方向、滑移、足部滚动及近端代偿；用 `gait_probe.py` 的可用接口采集，旧 checkpoint 只作影响对照，不当新机体成功依据。
5. 在独立静态场景初始化 S2 趴姿，核验腹部主要支撑、四足卸载/轻触、稳定低速与保持力矩；不通过关闭重力、冻结机体或取消全部驱动制造“放松”。
6. 与几何/碰撞约束一起审预算。需要改变掌段、轴或范围时交回 S1/S2；需要改变目标时交 S0。声明候选参数适用工况和不可外推范围。

## 交付与边界

- 候选驱动配置/实现路径、运行绑定、原始采样与同条件对照、通过/失败和复读命令进 `acceptance/records/<日期>-lizard2-s3-drive-load.md`；记录存在后补 evidence。
- S4 消费可执行驱动与周期，S5 消费已审参数和机制，不用本项未冻结诊断配置替换已训 v3。
- 不启动 PPO 训练，不增加游泳或趴姿策略任务。诊断若需例外接触初始化须显式隔离场景，不能全局放宽行走终止。
