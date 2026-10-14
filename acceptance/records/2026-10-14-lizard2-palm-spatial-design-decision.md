# lizard2 肩髋三轴构型决策与方案修订

## 适用范围

本记录仅登记本次对话的构型选择与方案更新，关联 `work/active/lizard2-palm-spatial-reconfiguration.md`、机体总项及限位 PD 专项。不是候选资产验收、动力学结论或关闭审核。

## 验收条件

当前计划应一致表达用户选择的三个肩／髋转轴，保留远端掌链和自然接触相位要求；明确轴系、网格归属、旧消费者兼容风险及验证交接。不得把既有隔离试作、未完成回归或历史平掌失败当作新构型已经通过。

## 结果

用户拍板：2026-10-14。本次对话先明确希望近端具有上下抬落、左右摆动、长轴旋转；讨论受控球关节后，用户选择“就按照三个关节来吧，然后更新你的方案”。据此采用三个共中心串联 revolute 的肩／髋表达，接肘／膝与腕／踝单轴，每腿合计五个转动自由度。该决定不意味着串联轴与球关节在所有姿态、限位和驱动下完全等价，也不固定最终 ROM、PD、力矩或速度。

本轮仅更新方案：新重构事项明确 swing → abduct → twist → elbow/knee → wrist/ankle 的实施与验证路线；机体总项替换四角色当前目标并路由至新事项；限位 PD 专项接收新候选后复核受影响证据，保留所有未完动作。旧 `palm` 四轴和 `shared/split` 五轴各自保留原含义。

前轮讨论被用户暂停前已经写出名表增量、两个试作脚本及本机隔离候选；这些仍属于未完成实现。本次不继续运行其几何、Blender 或仿真验证，不提交这些代码或资产，不认定任何此前试作报告为已验收结果。

历史固定参考点、全程平掌俯仰测试仅可用于新旧机构能力对照；此次新增近端旋转来自用户明确的运动要求。共面仅中立，拨动／滚动按真实接触相位验证，沿用 `2026-10-14-lizard2-palm-phase-constraint-correction.md` 的修订。

用户随后明确要求先增加办事项总篇幅上限，不把所有构型说明搬入决策记录。本轮据此将总字节上限由 120000 调整为 150000；完整构型与实施约束留在重构事项，延续的几何要求留在总项 A1。本记录只登记决策、修订及验证边界。

文档验证：`python -B rl_exp/tools/verify/check_work_docs.py --self-test` 通过既有事项、记录、引用与脚手架反例检查，真实事项检查通过。预算自测仍能拒绝超额样本；本轮只提高总量阈值，没有关闭、归档或删去未完事项。`git diff --check` 通过。这些检查不证明新构型可行。

恢复正文后，活跃事项共 27 项、125187/150000 字节。提交前的 `check_suite_banners`、`framework_pin_check --strict --self-test`、`check_dr_parity --strict`、`check_version_docs`、`check_work_docs --self-test` 和 `check_obs_protocol --live` 均通过；框架检查提示 IsaacLab 工作树有既存未提交修改，版本检查提示历史版本缺 tag。本轮没有据此认定候选运动或物理通过。

## 证据引用

- 决策来源：当前对话中用户对三个串联关节实现方式的明确选择。
- 方案唯一落点：`work/active/lizard2-palm-spatial-reconfiguration.md`。
- 总项接线及后续：`work/active/lizard2-body-drive-candidate.md` A/P1–P3 与 E/D。
- 限位、惯量、PD 及承重：`work/active/lizard2-restored-limits-pd-validation.md`。
- 接触相位边界：`acceptance/records/2026-10-14-lizard2-palm-phase-constraint-correction.md`。

## 未覆盖边界

未完成实际构型、动作包络、碰撞、USD／运行时、质量惯量和驱动验证；未进行独立关闭审核，事项保持在办。原有正式资产与训练配方未采用本候选。文件格式检查仅验证文档结构，不证明方案的行为可行性。
