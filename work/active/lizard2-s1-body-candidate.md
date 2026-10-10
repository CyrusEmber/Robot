---
id: lizard2-s1-body-candidate
title: lizard2 S1 执行：腕踝、掌跖段与趾根骨骼候选
scope: rl_exp/blender, rl_exp/tools/pipeline, rl_exp/tools/verify, acceptance/records
status: open
landing: rl_exp/blender/lizard2_stance_candidate.py, rl_exp/blender/generate_urdf.py
next: 本轮暂停资产执行、先改计划；恢复时先取得 S0 具名驱动能力输入，再联动选择“连续骨段＋小接触端”的轴/pivot与驱动方案，不等 S3 才发现表达缺口。正式验收还需已审设计约束；趴姿只挂账，不动已训 v3。
close_when: 新上下文核对 S0 已审约束及具名驱动能力输入、联动方案、DCC/URDF/USD 绑定、轴/镜像、连接/碰撞/惯量，用户确认候选外观；记录落 acceptance/records 后交 S2。声明能力不当承重真跑，几何通过不替代 S3 动力学；未判定不关闭。
depends_on: lizard2-s0-target-calibration
evidence: acceptance/records/2026-10-10-lizard2-land-body-drive-overall-work, acceptance/records/2026-10-08-lizard2-joint-design-review-contract
---

## 直接执行

1. 先消费 S0 具名驱动能力表和整体记录“联动设计修订”，结合已审约束提出骨骼/驱动同一候选。能力表尚缺时仅可核对现几何，不定 pivot/轴或承诺渐硬弹性；不等待 S3 承重证据，不制造循环依赖。
2. 按可实现恢复力与更新接口联动选择腕踝、掌跖段、趾根轴和小接触端，在隔离 DCC 路径探索。前后肢分别镜像，核对骨头/网格归属；不能先定非线性曲线再回找平台实现，线性对照或暂缓分支须明示。
3. 第一候选保留关节数。先读 `acceptance/records/2026-10-08-lizard2-r1-numeric-reference-and-decision-drafts.md` §15–§17 的增轴及长度扫判决，不重复相同目标宽带比较；重开仅限新小腿内扣/足部布局结构反例，或用户恢复趴姿后的新反例，且须说明旧条件不适用。旧机体读数不证明新机体可达，非一次 IK 失败就增轴。重开前由执行者在本阶段记录登记结构反例及旧条件不适用的理由，新上下文审核该判断；涉及目标变动仍交用户确认。
4. 修掌段几何/惯量后导出视觉/碰撞和 URDF，用 `convert_urdf.py` 实际接口转隔离 USD，核对路径、关节/刚体与 DCC—URDF—USD 一致；不覆盖 `rl_exp/lizard2_candidate/` 或刷新正式锁。
5. 提交局部几何和行走默认姿态的多视角及正负转动检查，记录驱动可表达与仍待承重验证的边界；趴姿不求解、不仿真，不计本轮出口。用户看外观不等于柔顺或推进通过。

## 交付与边界

- DCC/URDF/网格/USD 的隔离路径、联动驱动方案及所消费能力记录统一进 `acceptance/records/<日期>-lizard2-s1-body-candidate.md`，连同几何检查、预览和复读；存在后补 evidence，不预填骨骼结果。
- S2 只消费已审的绑定候选。局部探索记录不替代 S0 通过或 S1 正式验收；用户改外观或资产变动后，受影响检查须重做，不能沿用旧候选审核。
- 审核记录按整体记录“审核输入绑定约定”落地；本项仅留已存在的记录指针。
- 正式采用、旧版本退休和新配方归 S5/S6；本项不训练、不调正式增益、不修改已训 v3。趴姿恢复须用户决定。
