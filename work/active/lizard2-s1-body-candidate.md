---
id: lizard2-s1-body-candidate
title: lizard2 S1 执行：腕踝、掌跖段与趾根骨骼候选
scope: rl_exp/blender, rl_exp/tools/pipeline, rl_exp/tools/verify, acceptance/records
status: open
landing: rl_exp/blender/lizard2_stance_candidate.py, rl_exp/blender/generate_urdf.py
next: 先取得 S0 的已审目标与探索边界，再按正文在隔离 DCC/资产路径生成骨骼和碰撞候选；脚板位置、腕踝及趾根轴由执行者提出，不等用户给关节设计。完成后置 pending_review，请新上下文核对 R2 与资产链、用户检查多视角候选。
close_when: 新上下文核对 S0 输入、DCC/URDF/USD 同一机体、关节职责、轴/镜像、连接、碰撞和惯量，用户确认候选外观；审核记录落 acceptance/records，通过后关闭并交 S2。此处只审工程候选，不以外观批准替代周期或承重通过。
depends_on: lizard2-s0-target-calibration
evidence: acceptance/records/2026-10-10-lizard2-land-body-drive-overall-work, acceptance/records/2026-10-08-lizard2-joint-design-review-contract
---

## 直接执行

1. 读取 S0 交付和整体记录“联动设计起点”，确认输入机体及可修改范围。先展示本次候选改动方案；复用 `rl_exp/blender/lizard2_stance_candidate.py`、`rl_exp/blender/generate_urdf.py` 的现有约定，不复制整套导出工具。
2. 从当前站姿 DCC 另存隔离候选，按实际局部轴调整腕踝、掌跖段、趾根 pivot 与末端接触片；前后肢分别映射并由一侧镜像。检查骨头移动后网格归属和世界变换，不手改正式 URDF 冒充 DCC 修复。
3. 保留现有关节数作为第一候选，修正掌段几何与惯量缺口；导出视觉/碰撞网格和 URDF。只有可复读结构缺口才比较最小新增旋转轴，并按 R2 留下预算与代价。
4. 用 `rl_exp/tools/pipeline/convert_urdf.py` 的真实参数接口把候选转换到隔离 USD，核对相对网格路径、关节/刚体数量、末端碰撞和 DCC—URDF—USD 姿态一致。候选路径不得覆盖 `rl_exp/lizard2_candidate/` 或刷新正式锁。
5. 提交前后/左右/俯视预览及逐关节正负转动检查，覆盖行走默认姿态和趴姿可调整方向；记录尚未证明的范围并请用户看候选。不在此宣称趴姿、蹬地或柔顺已成立。

## 交付与边界

- DCC、URDF、网格、USD 的实际隔离路径与摘要统一进 `acceptance/records/<日期>-lizard2-s1-body-candidate.md`，连同变更动机、镜像/姿态检查、预览指针和复读命令；文件存在后再写 evidence。
- S2 只消费这份绑定候选。用户改外观或资产变动后，受影响检查须重做，不能沿用旧候选审核。
- 正式采用、旧版本退休和新配方归 S5/S6；本项不训练、不调正式增益、不修改已训 v3。
