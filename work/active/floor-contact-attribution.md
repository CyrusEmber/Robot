---
id: floor-contact-attribution
title: 地面接触归属：谁在滑、谁在牵引、穿透容忍度
scope: rl_exp/tools/diagnose, rl_exp/tools/verify, rl_exp/assets, rl_exp/versions/lizard2/main
status: in_progress
landing: rl_exp/versions/lizard2/main/main_params.yaml, rl_exp/tools/verify/check_recipe_build.py, rl_exp/tools/diagnose/diagnose_support.py, rl_exp/tools/diagnose/diag_metrics.py, ablation_harness/protocols/baseline_flat_v2.json
next: E 核旧对象回交边界；接触执行者接续地面力、速度与穿透对照。
close_when: 新上下文按正文关闭条件审核接触测量、穿透容忍度与旧对象回交；缺口保留在办。
evidence: acceptance/records/2026-10-22-lizard2-dev-contact-selection.md, acceptance/records/2026-10-22-lizard2-e-legacy-contact.md, acceptance/records/2026-10-22-lizard2-e-legacy-exit.md, acceptance/records/2026-10-13-lizard2-body-drive-plan-review.md, acceptance/records/2026-09-21-baseline-eval-measurement-contract.md, acceptance/records/2026-09-23-lizard2-v1-gait-skate.md
---

## 当前范围

区分谁在滑、谁在牵引、允许多少穿透。接触点速度、最低网格点、接触面积和脚板关节负载的既有方法与结果取本项 evidence；实现口径归 `diag_metrics.py`，不在本项复制读数。

旧 shared cap 校准及同几何 shared/split 处罚选择以[原对象回交](../../acceptance/records/2026-10-22-lizard2-e-legacy-contact.md)为入口；历史资产修复边界另取 `acceptance/records/2026-09-28-lizard2-foot-hull-and-asset-isolation.md`。隔离配置不能当作冻结配方已修改，当前 palm_spatial 正例不能替换旧对象证明。

## 下一步

1. E 对照原对象回交与出口表核定 cap 校准身份、原失败、实际入口、collider/处罚集合及具名地面过滤证据；确认所需消费者使用记录绑定的隔离配置，仍按 E/D 流程独立审核。
2. 后续正式版本采用时承接[开发选择修正](../../acceptance/records/2026-10-22-lizard2-dev-contact-selection.md)，按版本规则接入，不把开发构建当作正式任务已迁移；如需证明非足端处罚实际触发，再安排同资产、同配方边界下的受控接触，不把足端载荷外推该能力。
3. 诊断器与验收器复用 `diag_metrics.contact_point_velocity` / `mesh_lowest_point`，不各写一份。接触点切向速度以 COM 为参考，区分 body 原点与 COM；最低顶点近似及点切换限制继续声明。
4. 在诊断自建 cfg 中采过滤力，区分地面接触与自碰撞；不能只用 `net_forces_w` 推断接触对象，不改冻结配方摘要来补传感器过滤。
5. 用切向力方向区分牵引与被拖动，按逐 body 接触速度、位移和逐脚 duty 交叉核验；法向力或摩擦预算占比不能单独证明牵引/滑动。
6. 做时间步、求解迭代与接触参数的受控对照，再明确穿透容忍度。`contact_offset` 不是允许穿透深度，观测到穿透也不自动形成许可。
7. 在 cap 资产前提核实后，按同一口径关联贴地面积/姿态、滑移和净空；再决定是否进入奖励，不把相关读数当作因果。
8. 保留脚板关节负载、逐关节 effort 上限归一及饱和帧诊断；足部选择性扰动与移除饱和执行器的试验是否执行，由本链依据既有证据中的判据形状决定，不自动取消或转成 E 的手工步态门槛。

## 关闭条件

由新上下文核对本项 close_when、实际输入与记录：报告须给出逐接触 body 的接触点切向速度、摩擦利用率及切向力方向，并与位移/逐脚 duty 自洽；穿透容忍度须有引用受控对照的明确决定。旧对象前提和 E 回交按上述动作落实；未完动作保留在办，不以新候选接线或格式通过代替审核。

## 未覆盖边界

资产改造、URDF/USD 或接触参数变更由资产线负责，本项提供问题与证据；脚板被动移动边界仍取 `baseline-v2-recipe` 的资产不动假设。摩擦组合由框架基座声明，本项不更改。手工卸载、移重、步态协调或恢复不构成 E/D 的前置门槛，学习策略评测归训练后策略评测。
