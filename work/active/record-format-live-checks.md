---
id: record-format-live-checks
title: 记录格式的剩余真跑段（HARNESS 挂账 #2 的未做半）
scope: ablation_harness, rl_exp/tools/runrecord
status: in_progress
landing: ablation_harness/record.py, ablation_harness/eval.py, rl_exp/tools/runrecord/provenance.py
evidence: acceptance/records/2026-10-10-record-format-live-checks
next: 执行者修复 provenance.rsl_rl_state 的安装来源判定并补回归验证；复核 eval.py 两处 rev 采集及记录边界，按证据记录的“独立审核”节修订证据。用户决定验收②是否接受仅核分列，未决定前不改 close_when、不关闭。完成后重新置 pending_review，由新上下文对照 close_when、落点与更新后的证据重审。
close_when: ① 同一 run 身份按训练记录的 `mode` 重建后两处取值一致 ⇒ 记"已核到行为"，不一致 ⇒ 记差异并指出是哪一侧的字段口径；② 声明与实际分列、不相等时两列都出现 ⇒ 成立，某侧缺失 ⇒ 报记录不完整。两条都写出观测即关
---

## 当前状态

2026-10-10 用户选择退回 `in_progress`，本项未关闭；未完成动作见 `next`。
审核读数、结论、勘误与复读命令唯一归
`acceptance/records/2026-10-10-record-format-live-checks.md` 的“独立审核”节。

## 范围边界

- 保留用户此前不构造 pre-format 分支的决定；适用边界见证据记录，不作全部真跑承诺。
- 协议版本切换归 `work/closed/2026/runtime-acceptance-v3.md`；资产 fail 路径归
  `work/active/asset-fail-path-live-check.md`。
- `livecheck` 组不进入性能对账表；其它事项若引用其记录，仍按各自判据审核。
