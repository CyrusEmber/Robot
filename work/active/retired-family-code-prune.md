---
id: retired-family-code-prune
title: 退休线（lizard main/parkour/baseline）代码、闸门与事项移出主路径
scope: rl_exp/tasks, rl_exp/tools/verify, work/active
status: open
landing: rl_exp/tools/verify/offline_suite.py, rl_exp/tasks/__init__.py, rl_exp/tasks/recipe.py
next: 按清单 §6 执行；三项补裁决见清单 §8，决策阻塞已解除。用户本轮只授权回填，尚未执行代码清理；后续实施先打 tag `lizard-final`，计数与顺序以清单 §7/§6 为准
close_when: 用户审过清单后——(a) 批准：按清单执行完毕，判据形状见清单 §验收条件，清单内事项按 cancelled/superseded 移入 `work/closed/2026/` ⇒ done；(b) 否决或改走"套件分层不删代码" ⇒ cancelled 并写理由，另立分层项；观测 = 清单记录 + 删除 commit + 离线全绿判词
evidence: acceptance/records/2026-10-09-repo-architecture-review, acceptance/records/2026-10-09-retired-family-prune-manifest
---

## 当前状态

lizard 家族与 parkour / baseline 线已在 `rl_exp/versions/lines.json` 退休（"退出维护与复现承诺"），
但代码、注册、离线套件条目与若干活跃事项仍在主路径 —— 每次 pre-commit 都在为退休线付维护成本。
候选名单、逐项判据、规模、执行顺序与前置耦合全在清单记录（本项不复述）；三项补裁决归清单 §8，决策已落定、实施未开始。本轮只回填文档，不执行清理。

## 未覆盖边界

不处理 lizard2 自身的冗余。删除面的边界（冻结版本目录 / 退休记录 / 历史数据）与未被本清单覆盖的
引用面，见清单 §适用范围「不动的边界」与 §未覆盖边界。
