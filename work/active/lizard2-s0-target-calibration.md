---
id: lizard2-s0-target-calibration
title: lizard2 S0 执行：需求标定与测量口径
scope: acceptance/records, rl_exp/tools/verify, rl_exp/tools/diagnose
status: open
landing: rl_exp/tools/verify/check_leg_reachability.py, acceptance/records/2026-10-10-lizard2-land-body-drive-overall-work.md#验收条件
next: 执行者直接按正文开始：复核当前机体关节映射与 FK 中心索引，复用现有资料形成行走及静态趴姿正反例、坐标与容差提案；量测和用户确认归本阶段新记录，不等用户指定 kfe/foot。完成后置 pending_review，请新上下文核对 R1/R2 和原始样本。
close_when: 新上下文核对映射、复读检查、正反例、数值来源与用户确认的容差；具名审核归 acceptance/records，通过后关闭并交 S1。不通过退回 in_progress，只有用户能决定的缺口置 blocked；不得以文档齐全代替标定。
evidence: acceptance/records/2026-10-10-lizard2-land-body-drive-overall-work, acceptance/records/2026-10-08-lizard2-joint-design-review-contract, acceptance/records/2026-10-08-lizard2-r1-numeric-reference-and-decision-drafts
---

## 直接执行

1. 按需读取 evidence 的 R1/R2、整体需求与静态趴姿节，复用已有参考及用户决定；不重新询问已经确定的腹部承重、前后舒展、背面向上或足部职责授权。
2. 从 `rl_exp/lizard2_candidate/lizard2_candidate.urdf` 核对四腿的实际关节中心、局部轴、左右符号、掌跖与末端片职责。复读整体记录的踝部勘误；运行 `python rl_exp/tools/verify/check_leg_reachability.py --self-check`，确认工具通过不被误称设计通过。
3. 整理行走支撑/蹬离/摆动/落脚与静态趴姿的正反例样本，注明坐标、机体朝向、相位、载荷条件和来源。静态组合取整体记录定义，不在本项复制需求表。
4. 提出可执行的目标姿态、接触条件、低/中/高速度工况、法线角/穿透/反曲余量/滑移等容差及稳态窗口。区分动物证据与工程假设；缺失数据不填零，不能用当前错误姿态反定容差。仅尚未确认的取舍交用户拍板。
5. 为后续筛查列出“同样本、同阈值、不同候选”的检查入口和失败记录方式。复用已有工具，只有发现真实仪器缺陷才最小修复并留下回归检查；本项不生成新机体。

## 交付与边界

- 新阶段记录落 `acceptance/records/<日期>-lizard2-s0-target-calibration.md`：样本/参考指针、关节映射、标定提案与用户答复、复读命令、代码及资产绑定、失败与缺口。创建后才加入本项 evidence；数值不抄入 work。
- S1 输入为该记录的已审目标和允许的探索边界；缺生物参数可标注工程候选，不阻止探索，但未确认容差不得判通过。
- 本项不改已训 v3、配方锁、资产锁或冻结协议；不训练。执行解释器由 `ablation_harness/host_paths.py --check` 确认。
