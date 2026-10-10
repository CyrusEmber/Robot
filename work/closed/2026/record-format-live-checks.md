---
id: record-format-live-checks
title: 记录格式的剩余真跑段（HARNESS 挂账 #2 的未做半）
scope: ablation_harness, rl_exp/tools/runrecord
status: done
landing: ablation_harness/record.py, ablation_harness/eval.py, rl_exp/tools/runrecord/provenance.py
outcome: ① 身份判据从"包目录在 git 树里"改为安装来源（PEP 610）：本机 `rsl_rl_id()` 由 `source:28a37cecdd43`（借了外围树的 rev）变 `installed:5.4.2`，同次 run 的两个 rev 收敛为 rollout 前的一次采集；② 按用户 2026-10-10 拍板改成"两列分列且同源即记该事实、某侧缺失即判不完整"，真跑两对读数在证据里。副作用同批落地：组合键移动 ⇒ `lizard2/main` 黄金重基线十二条键、两处 `FROZEN` 摘要重记、`ACCEPTANCE.md` 登记一行；rsl_rl 未来"可重建"行由（假的）通过变未知 —— 判据归 `verified-rebuild-rating`。字段名债务（`*_declared` 落覆盖后值）另立 `work/active/eval-declared-columns-are-post-override.md`
evidence: acceptance/records/2026-10-10-record-format-live-checks
---

## 当前状态

2026-10-10 关闭（新上下文审核通过）。读数、勘误、独立审核、修复段与关闭审核唯一归
`acceptance/records/2026-10-10-record-format-live-checks.md`。

## 未覆盖边界

- ② 的"不等格"仍结构性不可达（真跑只能再证一次两列同值），字段名与值不符的债务归
  `work/active/eval-declared-columns-are-post-override.md`。
- pre-format 分支按用户此前决定不构造；资产 fail 路径（③）归
  `work/active/asset-fail-path-live-check.md`（blocked，等授权）。
- 身份只承诺"版本 + 记录里的安装来源"：同一版本的另一份 wheel 读作同一身份（天花板写在
  `provenance.rsl_rl_state` 的 docstring 里）；已存记录里的旧 `source:` 读数不改写。
- `livecheck` 组不进性能对账表；其它事项引用其记录，仍按各自判据审核。
