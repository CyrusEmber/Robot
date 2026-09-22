---
id: teacher-snapshot-asset-sync
title: 资产换代时同步 teacher 快照文件（PLAN #8；同步仍人工）
scope: rl_exp/tasks, rl_exp/tools/verify
status: open
landing: rl_exp/tools/verify/check_dr_parity.py, acceptance/records/2026-09-22-teacher-snapshot-parity-matrix.md, rl_exp/tasks/teacher_env_cfg.py
next: ① 缺口已由反向验证矩阵定位（读数见 `acceptance/records/2026-09-22-teacher-snapshot-parity-matrix.md`）：教师侧**资产派生字面量**在 ④⑤⑥ 三条上全静默，cfg_lock 只报"cfg 变了"、不验两侧同步 ⇒ **补闸门另立** `work/active/teacher-literal-parity-gate.md`，本项不承接该实施动作；② 待那条闸门落地后，**由用户拍板**哪些同步动作保留人工纪律（名单与口径届时登记，不在本项预先列出）
close_when: 补闸门项关闭（静默类缺口变红、且家族侧有意调参不误红）后，用户给出"哪些同步动作保留人工纪律"的裁决并登记 ⇒ 关；裁决若是"全部机器化"，本项以"无余下人工动作"收口。观测 = 该裁决能在实现或文档里被读到，且本项不再持有未落地的动作
---

## 当前状态

teacher 快照（`teacher_env_cfg.py`）与家族侧（`lizard_env_cfg.py`）是**手抄冻结**关系：资产换代时两侧要一起改，
机器只负责"报警"（④机器人块 / ⑤usda 结构契约 / ⑥asset_lock）。**同步动作仍是人工**，这是本项的余下部分；
覆盖到什么程度原未验证，2026-09-22 用反向验证矩阵做完（独立 worktree、逐例"改一处 → 跑闸 → 还原"，主树零改动）。

结果：**存在一类教师侧改动，④⑤⑥ 三条全静默**；cfg_lock 虽补位，但只报"cfg 变了"、不验两侧同步 ⇒
不能把"三个反例被拦住"读成"覆盖完整"。逐例读数与机制归
`acceptance/records/2026-09-22-teacher-snapshot-parity-matrix.md`（本项不复述），缺口与补闸门动作落在
`work/active/teacher-literal-parity-gate.md`。

## 未覆盖边界

本项不改 teacher 的快照纪律（零家族 import 是冻结纪律），也不接管版本目录四件套的机械迁移——那由换代 commit
自己完成。**旧冻结版本不因新家族换代而改写**：矩阵的变异只存在于一次性 worktree 副本里，已随其删除。
