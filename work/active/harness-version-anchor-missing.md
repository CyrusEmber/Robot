---
id: harness-version-anchor-missing
title: harness 代码基线锚点与语义覆盖核对
scope: ablation_harness
status: pending_review
landing: ablation_harness/HARNESS.md
next: 缺口已在本笔补齐（`acceptance/records/2026-10-10-harness-baseline-coverage-fill.md` ① 表加 `d60bd3f` 行、③ 表加两笔协议副本行、① 末段协议写全家族名）。由**新上下文只审 ③ 的残项**：拿 `git log --name-only 0c3ec25..925d997 -- ablation_harness` 对照 ①②③ 三张表，核 span 内每一笔测量语义改动都被点名或有排除理由，且 ① 末段改名后不与 `lizard2_flat_v1..v5` 的 `judge`/`criteria` 冲突；①②④ 已由 `2026-10-10-harness-coverage-per-commit-review.md` 通过，不重跑锚点与耦合对照。
close_when: ① `git ls-remote --tags origin` 里同时有 `harness-v1.9.0` 与 `harness-v1.10.0`，前者指向 `0c3ec25`、后者指向 `925d997`，两笔主题都以对应版本号开头；② `HARNESS.md` 的「代码基线」为 v1.10.0、无敞口段、所列记录路径都存在；③ v1.9.0 之后改测量语义的改动逐笔出现在覆盖声明里（旧基线起的每一笔要么被点名、要么写明为何不计入），且声明不与实现落点矛盾；④ 审核者在**新上下文**里跑出与 `evidence` 一致的耦合对照读数。①②③④ 全成立 ⇒ done（关闭时把读数落一份 `acceptance/records/` 记录）；缺锚点、锚点指向不是版本声明那笔、覆盖声明与实现或记录对不上、或读重复现不出 ⇒ 退回 `in_progress`。
evidence: acceptance/records/2026-10-10-harness-baseline-coverage-fill.md, acceptance/records/2026-10-10-harness-version-anchor-review.md, acceptance/records/2026-10-10-harness-coverage-per-commit-review.md
---

## 情况

覆盖声明的缺口与补齐落点写在 `evidence` 两份记录里，代码基线的权威声明在 `ablation_harness/HARNESS.md`「代码基线」段。本项复述与修订历史都不在这里。

## 未覆盖边界

- 只处理编号、锚点与覆盖声明，不重新评价 `video_matrix.py` 的实现（归 `work/closed/2026/video-matrix-gears.md`）。
- 已推的 tag 不改指不改名；本次不作新编号裁决。
- 代码基线与本地 tag 的配对闸归 `work/active/harness-baseline-tag-gate.md`；本项的锚点判据在远端，两者不等价。
