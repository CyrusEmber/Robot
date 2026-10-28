# lizard2 路线入口

> 更新：2026-10-28。main/v6.1 在腹部触地重开基础上开放转向指令，修订采用 `lizard2-main-v6.1` 并保留原标签；本轮只交付配置与验证，不启动新训练。正文唯一归 [main/v6/PLAN.md](main/v6/PLAN.md)，验证归 [转向记录](../../../acceptance/records/2026-10-28-lizard2-v6-yaw-command.md)。已训 v5/v4 保留原配方与结果身份，资产采用证据仍取 [配置记录](../../../acceptance/records/2026-10-23-lizard2-v4-configuration.md)。

家族事实与版本史见 [FAMILY.md](FAMILY.md)。当前训练交付由 [lizard2-family-landing](../../../work/active/lizard2-family-landing.md)承接，资产及默认驱动来源见 [候选事项](../../../work/active/lizard2-body-drive-candidate.md)，统筹路由取 [joint-limit-shape-and-range-pass](../../../work/active/joint-limit-shape-and-range-pass.md)。

按[训练优先修订](../../../acceptance/records/2026-10-23-lizard2-training-priority-plan.md)，接续正式配置的必要集成/预检与已批训练；完整动态接触标定和独立 S5/S6 阶段不作开训前置。限速边界试验已取消，决定见[计划盘点](../../../acceptance/records/2026-10-23-lizard2-plan-inventory.md)。接口及预算取[接口方案](../../../acceptance/records/2026-10-23-lizard2-training-interface-plan.md)，不重复询问。平衡、卸载、抬腿、步态和躯尾协调由 RL 学习；新增指标进入奖励、终止或合格判定前交[接触协议项](../../../work/active/lizard2-contact-protocol.md)核对应测量。

main/v3 已随机体换代退休，已训历史保留在 [main/v3/PLAN.md](main/v3/PLAN.md) 和 [main/v3/NOTES.md](main/v3/NOTES.md)，不改旧配方或续训旧 checkpoint。趴姿与其过渡不加入本轮。
