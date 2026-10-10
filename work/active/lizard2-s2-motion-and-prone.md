---
id: lizard2-s2-motion-and-prone
title: lizard2 S2 执行：完整迈步可达性（趴姿挂账）
scope: rl_exp/tools/verify, rl_exp/tools/diagnose, acceptance/records
status: open
landing: rl_exp/tools/verify/check_leg_reachability.py, rl_exp/tools/verify/check_self_collision.py
next: 取得 S1 已审联动候选、S0 设计约束及暂定工况后核验连续迈步；动力学性能阈值不冒称 S0 已定，按整体修订标定。趴姿仅挂账，当前不求解不仿真；失败回 S1/S0，不跳到奖励。完成后置 pending_review，请新上下文检查 R3/R4、原始样本与覆盖。
close_when: 新上下文核对同一候选的完整周期、有向掌面、限位和实际网格碰撞；结果与未覆盖域有具名记录。通过后交 S3；失败退回 in_progress 并交具名上游修复，用户要求变动置 blocked；静态展示或单次 IK 成功不足以关闭。趴姿挂账未获用户范围决定前不能关闭本项，不以本轮迈步核验宣称趴姿通过。
depends_on: lizard2-s1-body-candidate
evidence: acceptance/records/2026-10-10-lizard2-land-body-drive-overall-work, acceptance/records/2026-10-08-lizard2-joint-design-review-contract
---

## 直接执行

1. 绑定 S1 候选 DCC/URDF/USD 和 S0 目标，复核 `check_leg_reachability.py` 的数据口径能读当前掌跖段及末端片；新布局有不适用的硬编码时最小修复并留回归，不能继续套退役资产。
2. 按已确认几何设计约束和暂定工况建立静站至周期闭合的连续目标；候选比较前固定这些输入。记录整链角度/速度、骨段方向、相位、足端轨迹、法线和余量，不拼 IK 支路或靠机身补偿掩盖缺口。步幅与滑移性能阈值尚待新几何/驱动标定，不当已批准能力；目标需变动回 S0，不能为候选失败临时放宽。
3. 四种静态趴姿需求保留在整体记录，当前仅挂账，不求解姿态、不检查趴姿可达性、不启动仿真；恢复须用户决定。不将其计入本轮足部候选出口，不从几何贴地宣称稳定趴伏。
4. 使用 `rl_exp/tools/verify/check_self_collision.py` 的当前接口检查实际候选网格与需要的姿态/轨迹域；把缺失碰撞体、翻掌、异常内扣、反曲、穿透、连续性断点与速度超预算作为失败实例，原始姿态和输入绑定留存。
5. 比较多初值及搜索覆盖，区分“未找到解”和“证实不可表达”。失败需要改骨骼时回 S1，目标取舍回 S0；重新验证受影响目标，不放宽容差掩盖失败。

## 交付与边界

- 姿态和轨迹文件、检查命令、覆盖范围、逐阶段读数与失败实例进 `acceptance/records/<日期>-lizard2-s2-motion-and-prone.md`；机器本地产物只给实际路径与复读方法，不承诺入库。记录存在后补 evidence。
- S3 可消费已审的行走几何姿态/轨迹和速度/载荷工况；趴姿挂账不阻碍行走交接，也不解除本项关闭前的范围决定。未验证目标明确排除，不能悄悄删去用户需求。
- 审核记录按整体记录“审核输入绑定约定”落地；本项只留已存在的记录指针。
- 本项不跑策略训练、不设奖励权重，不全局取消腹部碰撞；几何通过仅允许进入承重动力学。
