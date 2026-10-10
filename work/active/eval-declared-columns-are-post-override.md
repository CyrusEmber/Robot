---
id: eval-declared-columns-are-post-override
title: runtime.*_declared 两列落的是 harness 覆盖后的值，不是配方声明值
scope: ablation_harness
status: open
landing: ablation_harness/eval.py, ablation_harness/record.py
evidence: acceptance/records/2026-10-10-record-format-live-checks
next: 用户拍板口径，三选一：① 改名（如 `*_requested`），承认它记的是 harness 交给 `gym.make` 的值；② 让"声明"取配方被覆盖前的原值（在 `_prepare_env` 覆盖前抓，真跑即可观测到与实际不等）；③ 只把这条边界写进记录、字段名照旧。拍板前不动代码。
close_when: 口径落成实现或写明边界，且该字段的读法只有一处（字段名本身或记录），不再靠读者推断
---

## 当前状态

2026-10-10 独立审核发现并留在交付面（`acceptance/records/2026-10-10-record-format-live-checks.md` 的
『独立审核』与『修复 · 本次未做』两节）：`runtime.num_envs_declared` / `runtime.device_declared` 读的是
`eval.py` 覆盖过的同一个 cfg 对象（`ablation_harness/eval.py:394`、`:398-399`），
字段名承诺的"配方声明值"从未被写下来。本项只做这一件事；记录格式的其余判读与 ② 的口径归
`work/closed/2026/record-format-live-checks.md`（2026-10-10 关闭）。
