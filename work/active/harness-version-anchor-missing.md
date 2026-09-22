---
id: harness-version-anchor-missing
title: harness v1.9.0 没有锚点：加模块那笔没有声明版本
scope: ablation_harness
status: open
landing: ablation_harness/HARNESS.md
next: 补一次版本声明并打锚点 —— 声明提交按仓规写成 `harness-v1.9.0: ...`，随后 `git tag harness-v1.9.0 <该提交>` 且 `git push origin harness-v1.9.0`（tag 用轻量形态，先例取 `lizard2-main-v1.5`；原先例的裸标签 `lizard2-main-v1` 已于 2026-09-22 删除，因为它指的那笔提交里配方还没出现——名字与状态对不上）。锚点该指"记录该版本的那笔"，而不是随机某一笔。
close_when: `git ls-remote --tags origin` 里出现 `harness-v1.9.0`，且它指向的那笔提交的主题是这次版本声明；`HARNESS.md` 的「代码基线」与之一致
---

## 情况

`HARNESS.md` 的「代码基线」已写到 v1.9.0（v1.8.0 的判据身份化/套件锁/同表条件面，加 `video_matrix.py`），
但**只有 v1.8.0 打了 `harness-v1.8.0` 锚点**：加 `video_matrix.py` 那笔提交 `9dcbf12` 的主题是另一个
家族的冻结，没有声明 harness 版本，因此 v1.9.0 这一刻没有锚点可 checkout。

按 `HARNESS.md` 的版本纪律，往 `ablation_harness/` 加模块是 minor 新增、应同时落"版本声明 + tag"；
这一件只补那两样，不改任何测量语义。

## 未覆盖边界

只补锚点，不重新评价 `video_matrix.py` 的实现（归 `work/closed/2026/video-matrix-gears.md` 那条链）；
也不动 v1.8.0 的锚点（已推的 tag 不改指不改名）。
