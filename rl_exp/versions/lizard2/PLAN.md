# lizard2 路线入口

> 更新：2026-10-10。当前实施版本：main/v3，已冻结（tag `lizard2-main-v3`）、训练已跑满（6000/6000），
> 首判与曲线读数归 `acceptance/records/2026-10-10-lizard2-v3-first-eval.md` 与 `2026-10-10-lizard2-v3-training-curve.md`。

已训 v3 的设计正文唯一归 [main/v3/PLAN.md](main/v3/PLAN.md)（v3.4，用户拍板启动训练与冻结）。
实现与验证证据归 `acceptance/records/2026-10-08-lizard2-v3-landing.md`；运行回填见 [main/v3/NOTES.md](main/v3/NOTES.md)。
家族事实与版本史见 [FAMILY.md](FAMILY.md)。后续几何/限位/动作周期由 `work/active/joint-limit-shape-and-range-pass.md` 承接，交付入口为 `work/active/lizard2-family-landing.md`。

当前隔离候选的计划正文为 [lizard2-body-drive-candidate](../../../work/active/lizard2-body-drive-candidate.md) 的 E、A–D 节；交接顺序取[统筹路由](../../../work/active/joint-limit-shape-and-range-pass.md)，接收方为[训练接入与评测](../../../work/active/lizard2-family-landing.md)及[接触评测工具](../../../work/active/lizard2-contact-protocol.md)。按[训练优先修订](../../../acceptance/records/2026-10-23-lizard2-training-priority-plan.md)直接推进正式候选配置，完整动态接触标定不作首轮开训前置；必要接口安全、版本与采用检查仍保留。本入口不变更已训 v3 或建立新版本。

2026-10-13 候选修订：按用户最新决定恢复放大前的后肢与后掌尺寸，保留四掌共面的中立站姿；实施与边界见 [A 节计划](../../../work/active/lizard2-body-drive-candidate.md)及[恢复记录](../../../acceptance/records/2026-10-13-lizard2-hindlimb-restored.md)。

2026-10-23 路由修订：按[训练优先修订](../../../acceptance/records/2026-10-23-lizard2-training-priority-plan.md)移除独立阶段和完整动态接触评测前置；当前执行正文见[训练接入](../../../work/active/lizard2-family-landing.md)。取消限速决定与原盘点保留在[计划盘点](../../../acceptance/records/2026-10-23-lizard2-plan-inventory.md)，接口取值与已批预算见[接口方案](../../../acceptance/records/2026-10-23-lizard2-training-interface-plan.md)。本次仅改计划，不采用资产或启动训练。
