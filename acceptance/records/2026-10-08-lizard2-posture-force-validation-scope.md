# 巨蜥参考姿态与发力验证的工作范围（2026-10-08）

## 适用范围

把默认站姿、训练重置状态及姿态相关发力验证接入现有 `joint-limit-shape-and-range-pass`。本文记录方案补充的依据和验收边界，不提供已量测的参考角度、关节限位、动物肌肉输出曲线或机器人载荷结果。

## 验收条件

- 主项 next、执行阶段和 close_when 同时承接默认姿态与分阶段发力验证，不另立重复事项。
- 参考站姿、建模零位和行走相位重置分别定义，修改默认角对动作偏置的影响有检查落点。
- 几何可达、静力可承载与动态可执行分开判定；执行器能力和接触条件参与结构/范围取舍。
- 现有生物及执行器证据只按其覆盖范围使用，估算、上界与实测不混用。
- 文档与仓库提交前检查通过，不改资产、配方、冻结锁或检查闸门。

## 结果

### 接入位置

主项①增加默认站姿与相位重置的数值交付、几何/承载验证及动作偏置核查；⑤增加姿态—接触阶段的载荷与执行记录、候选公平对比、力矩测量有效性核查。next 包含这些动作，close_when (j)(k) 收其验收。配方变更仍由 `lizard2-family-landing` 承接。

### 方案依据与限制

- 当前 `main_params.yaml` 的 `default_joint_pos` 全零，注释将零位描述为自然站姿；`lizard2_recipe.py` 将它用于初始关节状态，并启用默认动作偏置。该注释不是巨蜥姿态验证。默认角调整会影响动作参考中心，不能仅作显示姿态修改。
- 一般肌肉力学表明产力受长度和收缩速度影响，肌肉到关节的力臂影响力矩；巨蜥肌肉架构记录可作功能参照，尚无本机器人的逐角度可交付能力曲线。生物肌肉性质不直接转换为电机参数。
- 接触力对关节的力矩贡献依赖姿态下的雅可比。完整机器人仍须计入重力、惯性、浮动机体平衡、多足接触及摩擦；不能将单腿静力关系求逆后宣布整机推进能力。近奇异姿态下的形式机械优势也不代表无限可用力。
- 同一关节在摆动期与支撑期受到不同约束；评估使用整链姿态和接触状态。身体侧弯与新增轴既可能改变动作表达，也可能改变载荷分配，其具体收益待同条件验证。
- 已有执行器记录区分隐式 PD 估算与实测，并报告其 `applied_torque` 通道局限。后续先复核当前候选和框架的测量含义，再采用有效通道或明确标注的估算；不得把零值当作无负载。

最大风险是挑选外观合适、数学可达的姿态，却让执行器长期饱和或足端滑移。验证需覆盖默认支撑及完整周期，记录载荷假设、实际能力与跟踪/接触结果；失败后允许回改姿态、结构、驱动或工况，不自动归因为训练不足。

本轮文档验证：`framework_pin_check.py --strict --self-test`、`check_dr_parity.py --strict`、`check_version_docs.py`、`check_work_docs.py`、`check_obs_layout.py` 与 `git diff --check` 通过；既有框架工作树、历史 tag 和日期证据旧路径提示不属本轮修复范围。这些检查验证仓库一致性，不代表上述发力验证已完成。

## 证据引用

- 工作入口：`work/active/joint-limit-shape-and-range-pass.md`；配方交付：`work/active/lizard2-family-landing.md`。
- 当前配置与构建：`rl_exp/versions/lizard2/main/main_params.yaml` 的 default_joint_pos/action、`rl_exp/tasks/lizard2_recipe.py` 的初始状态与 lizard2_actions。
- 数值参考缺口：`acceptance/records/2026-10-08-lizard2-reference-motion-v0.md`。
- 生物资料及样本边界：`acceptance/records/2026-09-29-large-monitor-skeleton-muscle-review.md`；一般肌肉力学：[Skeletal muscle design to meet functional demands](https://pmc.ncbi.nlm.nih.gov/articles/PMC3130443/)。
- 姿态与力矩关系：[Modern Robotics — Statics of Open Chains](https://modernrobotics.northwestern.edu/nu-gm-book-resource/5-2-statics-of-open-chains/)。
- 当前执行器测量边界：`acceptance/records/2026-09-22-lizard2-actuator-capability.md`；腿链作用量缺口：`acceptance/records/2026-09-30-lizard2-leg-to-anatomy-mapping.md`。

## 未覆盖边界

本轮仅接入待办和验收，没有完成定量影像分析、站姿拟合、力矩采集、仿真或新结构比较。没有决定采用新增轴，也没有决定初始角或限位数值。未实施参考周期训练重置；它作为需评估的方案保留，不意味着已选定训练算法。
