---
id: parkour-yaw-reinterpretation
title: parkour 线 yaw 取角缺陷：其记录是否重解释（待拍板）
scope: rl_exp/tasks, rl_exp/versions/lizard/parkour
status: blocked
landing: rl_exp/tasks/parkour_mdp.py, rl_exp/versions/lizard/parkour/v1/PLAN.md
next: **待决（用户拍板）**：`parkour_mdp.py` 的 `_yaw_from_quat` docstring 写 `(x, y, z, w)` 而算的是 `(w, x, y, z)` 分支 ⇒ 对 xyzw 输入恒约等于 pi，`PositionCommand` 有 4 处建在它上面（目标采样与 `heading_err`）；该线已退休但**有训练 run** ⇒ 记录按"未重跑即不可比"处理。裁决三选一：保留现状（判不可比）/ 重解释记录（重跑或加注）/ 判废。修法与 baseline 侧同一处方（`euler_xyz_from_quat(quat)[2]`，口径见 `baseline/v1/NOTES.md`），该方法已由离线守卫白名单显式登记为已知坏（不静默）；改代码属实施，不在本项
close_when: 用户给出裁决后：保留现状 ⇒ 执行者把"未重跑不可比"写进该线记录/方案、并在白名单条目旁记下理由 ⇒ 关；重解释 ⇒ 另立实施项（重跑或加注），本项在该实施项验收通过后关。观测 = 该线记录与 `baseline/v1/NOTES.md` 的口径不再互相矛盾，且白名单条目旁的"已知坏"理由仍在
---

## 未覆盖边界

缺陷本身已核实、4 处调用点全在这条退休线自己的命令项里，主线不受影响；卡住的不是修法，而是这条线历史记录的含义要不要改（改 = 重解释已入库读数；不改 = 记录继续带一个恒为 pi 的取角）。
