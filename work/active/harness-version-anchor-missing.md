---
id: harness-version-anchor-missing
title: harness 代码基线锚点与语义覆盖核对
scope: ablation_harness
status: pending_review
landing: ablation_harness/HARNESS.md
next: 由新上下文审（不带本次执笔会话的历史）：跑 `git ls-remote --tags origin` 核两枚 tag 的指向；逐笔比 `HARNESS.md`「代码基线」段的覆盖声明与 `git log 0c3ec25..925d997 -- ablation_harness`（判分语义、整腿扩列是否都在声明里，且不与 `diff.json`/实现落点矛盾）；读 `evidence` 两份记录、"代码基线"段列的各记录是否存在，并**自己复跑一次耦合对照**（证据记录里那段代码）确认读数对得上。
close_when: ① `git ls-remote --tags origin` 里同时有 `harness-v1.9.0` 与 `harness-v1.10.0`，前者指向 `0c3ec25`、后者指向 `925d997`，两笔主题都以对应版本号开头；② `HARNESS.md` 的「代码基线」为 v1.10.0、无敞口段、所列记录路径都存在；③ v1.9.0 之后改测量语义的改动逐笔出现在覆盖声明里（旧基线起的每一笔要么被点名、要么写明为何不计入），且声明不与实现落点矛盾；④ 审核者在**新上下文**里跑出与 `evidence` 一致的耦合对照读数。①②③④ 全成立 ⇒ done（关闭时把读数落一份 `acceptance/records/` 记录）；缺锚点、锚点指向不是版本声明那笔、覆盖声明与实现或记录对不上、或读重复现不出 ⇒ 退回 `in_progress`。
evidence: acceptance/records/2026-10-10-harness-version-anchor-review.md, acceptance/records/2026-10-10-harness-baseline-coverage-fill.md
---

## 情况

覆盖声明的缺口与补齐落点写在 `evidence` 两份记录里，代码基线的权威声明在 `ablation_harness/HARNESS.md`「代码基线」段。本项复述与修订历史都不在这里。

## 未覆盖边界

- 只处理编号、锚点与覆盖声明，不重新评价 `video_matrix.py` 的实现（归 `work/closed/2026/video-matrix-gears.md`）。
- 已推的 tag 不改指不改名；本次不作新编号裁决。
- 代码基线与本地 tag 的配对闸归 `work/active/harness-baseline-tag-gate.md`；本项的锚点判据在远端，两者不等价。
