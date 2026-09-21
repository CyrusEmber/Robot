---
id: dr-widening-policy
title: DR 放宽策略未定案 + 多 GPU 续训不在保证范围（PLAN #11 余两项）
scope: rl_exp/tasks/curriculum_state.py, rl_exp/versions/lizard
status: blocked
landing: rl_exp/tasks/curriculum_state.py, rl_exp/versions/lizard/FAMILY.md
next: ① **待决（用户拍板）**：DR 放宽策略 —— 续训二阶段要不要放宽 DR 范围、按什么轴放宽（成功率 / iteration / 不放宽），决定后写成规则并接进续训状态层；② 多 GPU 续训**不在保证范围**（状态只从 rank 0 写，非 0 rank 明确拒绝并记录）—— 这是已声明的边界、不是待办；若用户改为要求支持，本项拆件并把多 GPU 那件单列
close_when: ① 用户给出放宽口径（含"不放宽"这一选）后，执行者把它落成规则并复跑续训相关离线用例（含 `test_resume_state.py`）全绿 ⇒ 关；② 若用户要求支持多 GPU 续训，本项只关 ①、多 GPU 拆成新活跃项。观测 = 规则能在续训状态层被读到，离线用例里不再有"未覆盖"空槽
---

## 当前状态

续训状态层本身已经落地（注册表 + 命名 slot、载荷 v2、c_k 与 term 解耦、`--drop_curriculum_state` 正名、`REQUIRES_CURRICULUM_STATE` 硬失败），机制与验收的正文分别在 `FAMILY.md` / `FILEMAP.md` 与 `ACCEPTANCE.md` 的续训节——**本条不复述**。剩下的只有挂账行点名的两项：DR 放宽策略未定案，以及多 GPU 续训不在保证范围。

## 为什么它是 blocked 而不是 open

① 的下一步是一次**政策选择**（放宽轴与口径），不是工程动作；没有它就是"什么时候做都行"的假待办。② 是已知边界声明，只有在用户改口径要求支持时才变成工作。
