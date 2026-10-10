---
id: lizard2-s0-target-calibration
title: lizard2 S0 执行：需求标定与测量口径
scope: acceptance/records, rl_exp/tools/verify, rl_exp/tools/diagnose
status: open
landing: rl_exp/tools/verify/check_leg_reachability.py, acceptance/records/2026-10-10-lizard2-land-body-drive-overall-work.md#验收条件
next: 先按正文调查驱动可实现性并消费已有参考失败与工程模板，再复核关节映射、行走正反例和设计约束；能力调查成为 S1 选骨骼/驱动方案的具名输入。趴姿仅挂账；未定性能阈值不阻碍获准局部探索，不当正式通过。完成后置 pending_review，请新上下文核对 R1/R2 和原始样本。
close_when: 新上下文核对具名驱动能力输入、映射、复读检查、正反例及已确认设计约束，区分未定性能阈值与动物证据；审核归 acceptance/records 后交 S1。不通过退回 in_progress，只有用户能决定的缺口置 blocked；源码/声明支持不当运行能力验证。
evidence: acceptance/records/2026-10-10-lizard2-land-body-drive-overall-work, acceptance/records/2026-10-08-lizard2-joint-design-review-contract, acceptance/records/2026-10-08-lizard2-r1-numeric-reference-and-decision-drafts
---

## 直接执行

1. 按需读取 evidence 的 R1/R2、整体记录“联动设计修订”和草案 §7–§10、§15–§17。先消费已知访问受限、视频身份失败、可读足端与工程模板边界，不重走被拒访问或猜骨点路线，也不泛化为所有动物资料永久不可行。已定需求不重问，趴姿保持挂账。
2. 调查当前 fork 的原生弹簧/限位/执行器和物理子步接口，形成一页具名能力表：可表达恢复力、更新频率、力矩/限速入口、源码或运行依据、未知与最小替代。S1 选择 pivot/轴及弹性方案前消费此表；能力调查不等待 S3 承重真跑，未验证层次明示，不能预承诺渐硬曲线。复用现有实现，不在本项建驱动机制。
3. 从 `rl_exp/lizard2_candidate/lizard2_candidate.urdf` 核对四腿实际中心、局部轴、左右符号和掌跖/末端片职责；复读踝部勘误及 `check_leg_reachability.py --self-check`，工具通过不当设计通过。整理行走正反例的坐标、相位、工况和来源。
4. 确认设计不变量与测量精度：反曲/翻掌禁区、穿透约束、局部参照及正反例；具体边界随候选几何核对。速度工况、步幅/滑移和柔顺性能仅提暂定口径，按整体修订由 S3/S4 标定、S5 比较前确认，不在 S0 冒称已确认能力阈值。
5. 列出同样本同阈值的检查入口和失败记录方式。只有真实仪器缺陷才最小修复并留回归；本项不生成新机体，不新增闸门。

## 交付与边界

- 新阶段记录落 `acceptance/records/<日期>-lizard2-s0-target-calibration.md`：具名驱动能力表、参考指针、映射、设计约束与用户答复、暂定性能口径、复读命令及代码/资产绑定；创建后才加入 evidence，不抄读数进 work。
- S1 先消费具名能力表和设计探索边界，再联动选骨骼/驱动；承重可行性仍待 S3。局部探索不冒称正式通过，S0 不承担尚无新几何/驱动的性能阈值批准。
- 审核记录按整体记录“审核输入绑定约定”落地；本项仅保留已存在的记录指针，不复制输入摘要。
- 本项不改已训 v3、配方锁、资产锁或冻结协议；不训练。执行解释器由 `ablation_harness/host_paths.py --check` 确认。
