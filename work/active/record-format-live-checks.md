---
id: record-format-live-checks
title: 记录格式的剩余真跑段（HARNESS 挂账 #2 的未做半）
scope: ablation_harness
status: blocked
landing: ablation_harness/record.py, ablation_harness/eval.py
evidence: acceptance/records/2026-10-10-record-format-live-checks
next: 真跑段等窗口：① `--variant` 跑两次 —— base 换 ckpt ⇒ `substitutions` 落成已证类目；base 是只有 `eval.json` 的 pre-format 目录 ⇒ `comparison=unknown` 加该 reason；同一次真跑里核 `runtime.rsl_rl_id` 的写侧落值；② 同一批真跑读 `num_envs` / `num_envs_declared` 两列。前置机器条件：`lizard2_v3` 训练退出、GPU 空出（或用户另给窗口）—— 2026-10-10 用户定"先不跑，只写发现"，跑法与判据见证据记录
close_when: ① 同一 run 身份按训练记录的 `mode` 重建后两处取值一致 ⇒ 记"已核到行为"，不一致 ⇒ 记差异并指出是哪一侧的字段口径；② 声明与实际分列、不相等时两列都出现 ⇒ 成立，某侧缺失 ⇒ 报记录不完整。两条都写出观测即关
---

## 当前状态

离线可做的那半已核完（身份重建两处对照 / `baseline_evidence` 在真实记录与真实 pre-format 目录上的两个
分支 / `num_envs` 两列同源），读数、复读命令与判据归 `acceptance/records/2026-10-10-record-format-live-checks.md`
—— **真跑段仍未做**。资产 fail 路径已拆为 `work/active/asset-fail-path-live-check.md`（2026-10-10 用户定：
③ 单列，本项只关 ①②）。

## 未覆盖边界

真跑段整段未做 ⇒ **不得**据既有读数称"记录格式已全部真跑"。本项不含协议版本切换的对照
（见 `runtime-acceptance-v3`），也不改 `record.py` 的规则（记录格式的读侧/写侧语义归 `record.py`
与 `test_eval_record.py`）。
