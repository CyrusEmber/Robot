---
id: asset-fail-path-live-check
title: 资产 fail 路径的真跑核对（授权方式待定）
scope: ablation_harness/eval.py, ablation_harness/record.py, rl_exp/tools/runrecord/manifest.py
status: blocked
landing: ablation_harness/eval.py, rl_exp/tools/runrecord/manifest.py
next: 先定"怎么造一条能 fail 的资产"——授权方式由用户定（临时副本 / 冻结资产的一次性例外 / 改用合成摘要），定之前不动任何冻结资产、不开跑；授权到手后真跑一次走到 `assets.actual.verdict = fail`，核对记录里 declared 摘要、actual 的 changed 点名与 verdict 三处一致
close_when: 一次真跑落成 `assets.actual.verdict = fail` 且 declared 侧摘要与实际不符被点名 ⇒ 记成立；若 fail 分支无法在不越界的前提下触发，写明卡在哪一步冻结点，并把做法改为离线构造 + 记录它与真跑的差距 —— 两条都写出观测即关
---

## 当前状态

2026-10-10 从 `work/active/record-format-live-checks.md` 拆出（用户定：③ 单列，本项不再被 ①② 拖着）。
离线三态与 `manifest._verify_assets` 的既有测试覆盖该分支；真跑只落过 `pass`（v14 冻结锁）与
`unknown`（dev 配方无锁），读数归 `acceptance/records/2026-09-17-lizard-eval-record-and-terrain-map.md`。

## 待决项（不自行决定）

造 fail 需要一条"能 fail 的资产"：动已冻结资产越界。授权方式由**用户**定；在定之前本项不开跑，
也不许把离线的三态读数读成"fail 路径已真跑"。
