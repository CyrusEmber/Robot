---
id: lizard2-s4-trunk-tail
title: lizard2 S4 执行：躯干侧弯、拖尾与平衡对照
scope: rl_exp/tools/diagnose, rl_exp/tasks, acceptance/records
status: open
landing: rl_exp/tools/diagnose/gait_probe.py, rl_exp/tasks/lizard2_recipe.py
next: 取得 S3 可执行候选后，按正文做同速度、同接触条件的躯干/尾部行走协同对照；趴姿尾地接触仅挂账，恢复须用户决定。先用现有自由度，不以关节活动或相关性冒称稳定收益。完成后置 pending_review，请新上下文核对 R3/R5 和因果边界。
close_when: 新上下文核对同条件对照、尾部接触载荷/阻力、身体稳定与四足相位，用户确认动作外观；获准或明确拒绝方案有证据后交 S5。缺动力学或只有相关性记未判定，不关闭；机体或驱动改动回相应上游重验。
depends_on: lizard2-s3-drive-load
evidence: acceptance/records/2026-10-10-lizard2-land-body-drive-overall-work, acceptance/records/2026-10-08-lizard2-joint-design-review-contract, acceptance/records/2026-10-10-lizard2-v3-first-eval
---

## 直接执行

1. 绑定 S3 机体、驱动、可执行周期与 S0 工况。区分根机身 heading、胸部相对侧弯、颈部方向和尾部 yaw/pitch，先检查现有通道/驱动能否表达需求，不默认新增脊柱轴。
2. 在隔离诊断场景提出侧弯及尾摆的相位/幅度候选，与无协同基线同速度、同足部目标、同载荷比较；不改变多个无关参数后归因到尾巴。
3. 采集机身偏航/侧倾、侧向重心与速度、四足相位和载荷、胸尾运动、尾根/中/尖接触位置及法向/切向作用。量测稳定收益和拖曳代价，相关性和单纯角度幅度只作读数。
4. 检验行走允许拖尾与异常尾部主承重的边界；趴姿自然尾地接触暂缓，当前不执行，恢复须用户决定。不让尾巴拖住身体、头腹代替足部推进，或靠滑移维持速度。
5. 得出获准协同、无收益/代价过大而拒绝、或未判定的明确出口。机体改动交 S1/S2，驱动改动交 S3；用户需求取舍回 S0，不仅因样子好看就批准。

## 交付与边界

- 同条件对照、相位候选、尾部接触与稳定读数、预览、绑定/复读和用户选择进 `acceptance/records/<日期>-lizard2-s4-trunk-tail.md`，存在后补 evidence。
- S5 消费获准动作要求和允许接触域，评测应能分辨有用协同与异常承重；本项不发布协议、不写死奖励权重。
- 审核记录按整体记录“审核输入绑定约定”落地；本项只留已存在的记录指针。趴姿挂账未获用户范围决定前不得随行走交接关闭本项。
- 不启动训练、不加水动力；保留现有 v3 作为旧配方，诊断通过不等于新策略会自然学会协同。
