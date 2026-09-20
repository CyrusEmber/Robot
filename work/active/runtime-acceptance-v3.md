---
id: runtime-acceptance-v3
title: 运行时验收的三条未完项（HARNESS 挂账 #1 的未做半）
scope: ablation_harness
status: open
landing: ablation_harness/eval.py, ablation_harness/protocols/locomotion_eval_v3.yaml, ablation_harness/results
next: 三条都在 v3 协议下做（v2 已冻结封存，**v2 行不得与 v3 行混表**）：① 同一 checkpoint 跨协议对照 —— 预期 fall_rate 单调、其余指标在 ±0.02 内；② 基线（v13/v10 的 ckpt）在 v3 下重跑，v3 行才有对账对象；③ rough 两列的 completion 分布 —— 需要一条**有 ckpt 的 run**，零动作跑上这 9 列没有信息量
close_when: 执行者跑完三条并观察：① 同一 ckpt 在 v2/v3 各一次 —— 落在 ±0.02 内即记录并接受，超出则记差异清单并判断是哪一侧的口径问题；② 基线与新行同表 —— 有可对账行即成立；③ 有 ckpt 的 run 完成后看 9 列 completion —— 有分布即成立。三条各自的观测结果写进本项；若 ③ 仍只有零动作 run，明确标"证据不足"而不是下结论
---

## 当前状态

- **已做**：v3 零动作 smoke 已证 hook 活着（`captured == resets_in_rollout`、`early_terminations=0`，
  同时校正了计数口径：`dones` 含 `time_out`，末步全体超时 ⇒ 那两个数天然等于 env 总数）；
  ④a 起伏已证 —— 起伏在真实生成路径逐格测量并随运行归档，离线闸按归档自述的 suite+seed 重建后逐格比。
- **未做**：跨协议对照、基线重跑、rough 两列 completion 分布（见 `next`）。

## 为什么这几条不能靠零动作跑过关

零动作策略不产生"某列完成度"的信息：completion 全列接近 0 是**策略没动**，不是**地形分布**的性质。
把后者读成前者的结论，就是把"没测到"当成"测过了"。

## 未覆盖边界

本项不含 ④b 之外的地形几何工作（那已收，见 `work/closed/2026/`）；也不含记录格式的真跑段
（另立 `record-format-live-checks`）。
