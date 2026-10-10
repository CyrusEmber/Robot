---
id: harness-version-anchor-missing
title: harness 代码基线缺锚点：加模块那笔没声明版本，v1.10.0 一并补齐
scope: ablation_harness
status: pending_review
landing: ablation_harness/HARNESS.md
next: 由新上下文审（不带本次执笔会话的历史）：跑 `git ls-remote --tags origin` 看两个锚点是否都在 origin 上、各指向哪笔（本地只有 tag 不算锚点）；对着它读 `close_when`、`HARNESS.md` 的「代码基线」段、以及那段列的四份 `acceptance/records/` 记录，判编号是否够（v1.9.0 之后是否还有改测量语义的改动被漏编）。成立则关闭并把读数落一份 `acceptance/records/` 记录；tag 缺失或编号不够则退回 in_progress。
close_when: `git ls-remote --tags origin` 里同时有 `harness-v1.9.0` 与 `harness-v1.10.0`；前者指向 `0c3ec25`（主题以该版本号开头，即声明该版本的那笔），后者指向本次声明提交（主题同样以版本号开头）；`HARNESS.md` 的「代码基线」为 v1.10.0、再无敞口段、其中列的记录路径都存在。全部成立 ⇒ done；缺锚点、锚点指向的不是版本声明那笔、或「代码基线」与锚点对不上 ⇒ 退回 in_progress。
---

## 情况

`HARNESS.md` 的「代码基线」随本次声明写到 v1.10.0，两个锚点成对落：

- `harness-v1.9.0` → 提交 `0c3ec25`（主题 `harness-v1.9.0: declare the version, log the anchor it needs`）。
  它把基线从 v1.8.0 改到 v1.9.0 并写下版本纪律，但当时没打 tag —— 加 `video_matrix.py` 那笔 `9dcbf12`
  的主题是另一个家族的冻结，没有声明 harness 版本，所以 v1.9.0 从落地起就没有锚点。
- `harness-v1.10.0` → 本次声明提交。覆盖 v1.9.0 之后改测量语义的三笔（帧格式 2 与足端判据、定点场景驱动、
  帧格式 3 与四条步态形态报告项）加汇总侧身份拒表（记录格式节 ④）；逐笔的改动内容与升版理由在
  `HARNESS.md`「代码基线」段列的四份 `acceptance/records/` 记录里。

判据落在远端而不在本机：锚点的用途是别人能 checkout 出一份可复现的树。

## 未覆盖边界

- 只补编号与锚点，不重新评价 `video_matrix.py` 的实现（归 `work/closed/2026/video-matrix-gears.md`）。
- 不动 `harness-v1.8.0` 的锚点：已推的 tag 不改指不改名。
- 不建"代码基线 ↔ tag"的闸：`OFFLINE_CHECKS.md` §4 正暂缓新增声明一致类，且离线套件不能联网、
  弱于本项的远端判据。那一半另立 `work/active/harness-baseline-tag-gate.md`（blocked）。
- v1.9.0 之后另有两笔改动**未**列入本次编号，因为它们既不加模块也不改测量语义：评测启动的
  `--viz none` 取代已废弃的 `--headless`（`4ef9fb4`）、lizard 家族源码退休时的四处路径改写（`f1e6421`）。
  退休那笔的自身记录在 `work/closed/2026/`。
