---
id: harness-version-anchor-missing
title: harness 代码基线锚点与语义覆盖核对
scope: ablation_harness
status: done
landing: ablation_harness/HARNESS.md
outcome: 历史快照与现行锚点分别验收，逐笔覆盖及耦合对照经独立审核通过；范围见证据。
evidence: acceptance/records/2026-10-28-harness-version-anchor-final-review.md, acceptance/records/2026-10-28-harness-version-anchor-declaration-repair.md, acceptance/records/2026-10-28-harness-version-anchor-coverage-review.md, acceptance/records/2026-10-28-harness-version-anchor-coverage-repair.md, acceptance/records/2026-10-28-harness-version-anchor-independent-review.md, acceptance/records/2026-10-10-harness-baseline-coverage-fill.md, acceptance/records/2026-10-10-harness-version-anchor-review.md, acceptance/records/2026-10-10-harness-coverage-per-commit-review.md
---

## 当前状态

按用户选择分别验收历史与现行锚点；独立审核、逐笔覆盖及边界见 `evidence`。

## 未覆盖边界

- 只处理编号、锚点与覆盖声明，不重新评价 `video_matrix.py` 的实现（归 `work/closed/2026/video-matrix-gears.md`）。
- 已推的 tag 不改指不改名；本次不作新编号裁决。
- 代码基线与本地 tag 的配对闸归 `work/closed/2026/harness-baseline-tag-gate.md`；本项的锚点判据在远端，两者不等价。
