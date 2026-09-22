---
id: dr-widening-policy
title: lizard2 加回 DR 时的放宽轴 + 续训状态层与多 GPU 边界（原 PLAN #11 余两项，已改挂本家族）
scope: rl_exp/tasks/lizard2_recipe.py, rl_exp/versions/lizard2, rl_exp/tasks/curriculum_state.py
status: blocked
landing: rl_exp/versions/lizard2/main/v1/PLAN.md, rl_exp/tasks/lizard2_recipe.py, rl_exp/tasks/curriculum_state.py
next: 两条待用户裁决：① DR 放宽轴取哪一种 —— 沿用旧线 c_k（iteration 的纯函数；但本线配方自包含、不 import `teacher_mdp.py`，要用得先决定"抄一份"还是"放宽契约"）/ 另立一套（按成功率，代价见正文）/ **不接课程**（DR 固定在全范围）；② 续训状态层何时接 —— 本线 v1 声明 `REQUIRES_CURRICULUM_STATE=False`（无课程无 DR），接 DR 的那一版才需要 `clock` 载荷。多 GPU 维持"只从 rank 0 写、非 0 rank 硬拒绝并记录"这一已声明边界，要支持就另立件
close_when: ① 用户给出放宽口径（含"不接课程"这一选）后，口径落进实现（元素/参数或机制），并复跑相关离线用例全绿；② 接 DR 的那一版把 `REQUIRES_CURRICULUM_STATE` 声明为真并验收 `clock` 载荷（counter + c_k 指纹），或用户明示本线不接状态层 ⇒ 两条都有落点即关。观测 = 口径能在实现里被读到，"多 GPU 支持"要么是已声明边界要么已拆成独立活跃项
---

## 为什么这条挂在 lizard2 而不是 lizard

本家族以 `lizard2/main/v1` 起步，v1 是**无 DR、无课程**的能力基线（配方表与风险节在
`rl_exp/versions/lizard2/main/v1/PLAN.md`），且本线配方**自包含**：不 import 任何其它线的 cfg/mdp，
也就不 import 那个仍在被改的 `teacher_mdp.py`。旧线的"放宽轴 = c_k"因此**既不是本线的现状，
也不是本线能直接继承的机制**，只能作设计参照。本项不向 lizard 侧提任何要求，也不动它的冻结版本。

## 参照：旧线的 c_k（三个性质才是本线选轴时要复用的判据）

`c_k = c0 ** (decay ** iteration)`（`iteration = common_step_counter // steps_per_iteration`）把六个 DR 事件的
范围按 `anchor + (range - anchor) * c_k` 从近零推向 yaml 全范围；续训时 counter 与 c_k 指纹进 `clock` 载荷，
课程**连续**、不重烧。它的性质：

- **纯 iteration 函数** ⇒ 同配方两次 run 落在同一 DR 范围，可复现、可对账（这正是"按成功率放宽"打掉的东西）。
- **不覆盖全部 DR** ⇒ reset 随机化、高度噪声、摩擦 dip 都不挂它；说"放宽 DR"必须先说覆盖哪几个事件。
- **同时缩放惩罚项** ⇒ 冻它会连奖励价格一起冻；"二阶段放宽 DR"等于同时改奖励经济学。

机制与读数归 `rl_exp/tasks/teacher_mdp.py` 与 `rl_exp/versions/lizard/REWARDS.md`，本条不复述。

## 为什么它是 blocked 而不是 open

① 的下一步是一次**政策选择**（放宽轴与口径），不是工程动作；② 取决于本线哪一版真的接了 DR ——
现在没有那一版（v1 的 DR 是逐项置 None 的，见上）。没有这两条，它就是"什么时候做都行"的假待办。

## 未覆盖边界

本项不裁"lizard2 哪一版加 DR"（那是版本计划的事），也不动 `lines.json` 的行状态 —— `lizard/main`
已随家族退役，决定见 `acceptance/records/2026-09-22-lizard-family-retirement.md`。旧线 13 份冻结 `main_params.yaml`
里那句已过时的 `resume is not reconstructed` 按"冻结记录不改"保留，不在本项处理范围。
