---
id: harness-version-anchor-missing
title: harness 代码基线锚点与语义覆盖核对
scope: ablation_harness
status: in_progress
landing: ablation_harness/HARNESS.md
next: 执行者按审核记录「结果」②③补齐代码基线的语义覆盖声明与后续变更证据，不改已推 tag、不改写历史记录；修后置 pending_review，由新上下文复核远端锚点与覆盖说明。
close_when: `git ls-remote --tags origin` 里同时有 `harness-v1.9.0` 与 `harness-v1.10.0`；前者指向 `0c3ec25`（主题以该版本号开头，即声明该版本的那笔），后者指向本次声明提交（主题同样以版本号开头）；`HARNESS.md` 的「代码基线」为 v1.10.0、再无敞口段、其中列的记录路径都存在。全部成立 ⇒ done；缺锚点、锚点指向的不是版本声明那笔、或「代码基线」与锚点对不上 ⇒ 退回 in_progress。
evidence: acceptance/records/2026-10-10-harness-version-anchor-review.md
---

## 情况

覆盖声明与后续变更证据待修订，缺口及复读方法见 `evidence`；代码基线的权威声明仍在 `ablation_harness/HARNESS.md`「代码基线」段，事项不复制版本跨度摘要。

## 未覆盖边界

- 只处理编号、锚点与覆盖声明，不重新评价 `video_matrix.py` 的实现（归 `work/closed/2026/video-matrix-gears.md`）。
- 已推的 tag 不改指不改名；本次不作新编号裁决。
- 代码基线与本地 tag 的配对闸归 `work/active/harness-baseline-tag-gate.md`；本项的锚点判据在远端，两者不等价。
