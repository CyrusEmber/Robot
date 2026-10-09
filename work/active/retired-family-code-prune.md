---
id: retired-family-code-prune
title: 退休线（lizard main/parkour/baseline）代码、闸门与事项移出主路径
scope: rl_exp/tasks, rl_exp/tools/verify, work/active
status: open
landing: rl_exp/tools/verify/offline_suite.py, rl_exp/tasks/__init__.py, rl_exp/tasks/recipe.py
next: 清单已落盘（`acceptance/records/2026-10-09-retired-family-prune-manifest.md`，六项裁决已收该记录 §5）；待用户批准即按 §6 顺序执行 —— 先打 tag `lizard-final`，再在同一提交内建新删旧（拆 `recipe.py` 旧线引用 + 删 17 个模块 + 清三条声明面 + 删 12 条套件条目）
close_when: 用户审过清单后——(a) 批准：打 tag `lizard-final`，按清单删除并拆 `recipe.py` 等共用件的旧线 import，`run_offline_checks.bat` 全绿、lizard2 v3 任务能注册与构造，清单内事项按 cancelled/superseded 移入 `work/closed/2026/` ⇒ done；(b) 否决或改走"套件分层不删代码" ⇒ cancelled 并写理由，另立分层项；观测 = 清单记录 + 删除 commit + 离线全绿判词
evidence: acceptance/records/2026-10-09-repo-architecture-review, acceptance/records/2026-10-09-retired-family-prune-manifest
---

## 当前状态

lizard 整家族与 parkour / baseline 线已在 `rl_exp/versions/lines.json` 退休（"退出维护与复现承诺"），
但代码、注册、离线套件条目与若干活跃事项仍在主路径，每次 pre-commit 都在为退休线付维护成本。
规模与候选名单见评审记录（本项不复述）。

已知前提：

- lizard2 任务模块不 import 旧线模块；但共用件 `rl_exp/tasks/recipe.py` 反向 import 了旧线，删除前必须先拆。
- `test_resume_state` 等看守的续训状态层被 `work/active/dr-widening-policy.md` 列为 lizard2 未来依赖，不能按名字一刀切。
- 旧 checkpoint 的可加载性在删除后只能靠 checkout tag 取回；ckpt 载荷含生成类名（见 `FILEMAP.md` 不直观布局节）。

## 未覆盖边界

不改任何已冻结版本目录（`rl_exp/versions/lizard/**` 的文档、yaml、lock 原样保留），不改退休记录，
不删 `acceptance/records/` 与 `ablation_harness/results/` 下的历史数据。不处理 lizard2 自身的冗余。
