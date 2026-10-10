---
id: runtime-acceptance-v3
title: 运行时验收的两条未完项（HARNESS 挂账 #1 的未做半）
scope: ablation_harness
status: pending_review
landing: ablation_harness/eval.py, ablation_harness/protocols/locomotion_eval_v3.yaml, ablation_harness/results
next: 审——**新上下文**（不带本次执行会话的历史）对着 `close_when` 与 `acceptance/records/2026-10-10-cross-protocol-suite-readings.md` 判三件：① 判据改写是否诚实（原"几何相同的列在 ±0.02 内"被实测证伪，改成"只在 mesh digest 相同的列上比"是治理还是自证）；② ② 的"有分布即成立"是否被"该列不判分"稀释成空判；③ 记录里的读数与四个 run 目录、`terrain/geometry.json` 是否自洽（不通过就地退回 `in_progress`，缺口只有用户能解则 `blocked`）。审核读数入 `acceptance/records/`，本项只留指针；审过即移进 `work/closed/2026/`、去掉本 `next`、补 `outcome`
close_when: 两条都跑完并观测：① 同一 ckpt 在 v2/v3 各一次（各臂另重跑一次作可复现性对照）—— 落在 ±0.02 内即记录并接受，超出则记差异清单并判断是哪一侧的口径问题；② 有 ckpt 的 run 完成后看 9 列 completion —— 有分布即成立。读数与判定进 `acceptance/records/`（数值只有一个家），本项只留指针。**本次执行中 ① 的判据被证伪并改写**，故按上一条 `next` 先审再关
---

## 当前状态

- **已做**：v3 零动作 smoke 已证 hook 活着（`captured == resets_in_rollout`、`early_terminations=0`，
  同时校正了计数口径：`dones` 含 `time_out`，末步全体超时 ⇒ 那两个数天然等于 env 总数）；
  ④a 起伏已证 —— 起伏在真实生成路径逐格测量并随运行归档，离线闸按归档自述的 suite+seed 重建后逐格比。
- **已做（本次）**：① 跨协议对照与 ② rough 两列分布都已真跑，读数、判据证伪与改写理由全在
  `acceptance/records/2026-10-10-cross-protocol-suite-readings.md`（本项不复述数字）。
- **待审**：见 `next`。执行者认为两条已完成，故置 `pending_review`。
- **遗留**：本次暴露出"几何未变的列也会随别的列改读数"（跨列耦合），机制未定，**另立**
  `work/active/eval-column-coupling.md`；它不阻塞本项关闭，但它是本次两条判据能成立的前提，审时须一并看。

## 为什么这几条不能靠零动作跑过关

零动作策略不产生"某列完成度"的信息：completion 全列接近 0 是**策略没动**，不是**地形分布**的性质。
把后者读成前者的结论，就是把"没测到"当成"测过了"。

## 未覆盖边界

- **对账对象只取本家族行**：`lizard/main`、`lizard/baseline`、`lizard/parkour` 在
  `rl_exp/versions/lines.json` 里均为 `retired`，退休 = 退出维护与复现承诺；其 task id 已随
  `work/closed/2026/retired-family-code-prune.md` 注销 ⇒ 那些 ckpt 跑不出 v3 行，也**不得与 v3 行同表**。
- **本项不定成绩**：`locomotion_eval_*` 的 9 列里只有 `flat` 对平地训练家族是成绩面，其余 8 列是 OOD 探针
  （列角色见 `ablation_harness/HARNESS.md`）。本项测的是协议与套件的行为，不是策略强弱。
- 本项不含 ④b 之外的地形几何工作（那已收，见 `work/closed/2026/`）；也不含记录格式的真跑段
  （另立 `record-format-live-checks`）。
