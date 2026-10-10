---
id: lizard2-s2-motion-and-prone
title: lizard2 S2 执行：完整迈步与四种静态趴姿可达性
scope: rl_exp/tools/verify, rl_exp/tools/diagnose, acceptance/records
status: open
landing: rl_exp/tools/verify/check_leg_reachability.py, rl_exp/tools/verify/check_self_collision.py
next: 取得 S1 已审候选和 S0 工况/容差后，按正文核验连续迈步与整体记录定义的静态趴姿；失败先反馈 S1 或 S0，不跳到调奖励。完成后置 pending_review，请新上下文检查 R3/R4、完整样本及失败覆盖。
close_when: 新上下文核对同一候选的完整周期、趴姿覆盖、有向掌面、限位和实际网格碰撞；结果与未覆盖域有具名记录。通过后交 S3；失败退回 in_progress 并交具名上游修复，用户要求变动置 blocked；静态展示或单次 IK 成功不足以关闭。
depends_on: lizard2-s1-body-candidate
evidence: acceptance/records/2026-10-10-lizard2-land-body-drive-overall-work, acceptance/records/2026-10-08-lizard2-joint-design-review-contract
---

## 直接执行

1. 绑定 S1 候选 DCC/URDF/USD 和 S0 目标，复核 `check_leg_reachability.py` 的数据口径能读当前掌跖段及末端片；新布局有不适用的硬编码时最小修复并留回归，不能继续套退役资产。
2. 按已确认工况建立静站、支撑前/中/后、蹬离、屈腿回收、落脚和周期闭合的连续目标。记录整链角度/速度、骨段方向、相位、末端轨迹、接触面法线和限位余量；不拼接不同 IK 支路或靠机身补偿掩盖结构缺口。
3. 在固定头尾朝向下求整体记录定义的四种静态趴姿，保存可重载的姿态文件；读取掌跖段与末端片的有向法线，分别检查腹地接触和四腿地面/自碰撞。腹部承重的动力学暂归 S3，本项不能从几何贴地直接宣称稳定趴伏。
4. 使用 `rl_exp/tools/verify/check_self_collision.py` 的当前接口检查实际候选网格与需要的姿态/轨迹域；把缺失碰撞体、翻掌、异常内扣、反曲、穿透、连续性断点与速度超预算作为失败实例，原始姿态和输入绑定留存。
5. 比较多初值及搜索覆盖，区分“未找到解”和“证实不可表达”。失败需要改骨骼时回 S1，目标取舍回 S0；重新验证受影响目标，不放宽容差掩盖失败。

## 交付与边界

- 姿态和轨迹文件、检查命令、覆盖范围、逐阶段读数与失败实例进 `acceptance/records/<日期>-lizard2-s2-motion-and-prone.md`；机器本地产物只给实际路径与复读方法，不承诺入库。记录存在后补 evidence。
- S3 输入为已审的几何可行姿态/轨迹和速度/载荷工况，未验证目标明确排除，不能悄悄删去用户需求。
- 本项不跑策略训练、不设奖励权重，不全局取消腹部碰撞；几何通过仅允许进入承重动力学。
