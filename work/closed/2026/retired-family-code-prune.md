---
id: retired-family-code-prune
title: 退休线（lizard main/parkour/baseline）代码、闸门与事项移出主路径
scope: rl_exp/tasks, rl_exp/tools/verify, work/active
status: done
landing: rl_exp/tools/verify/offline_suite.py, rl_exp/tasks/__init__.py, rl_exp/tasks/recipe.py
outcome: 按清单与 §8 补裁决执行完毕——38 个文件删除（13 模块 + 24 验证脚本 + freeze_parity.json）、旧线注册 44→6、离线套件 48→37 且 ALL_OFFLINE_CHECKS_PASSED (37/37)、台账 9 项关闭（7 superseded + 2 cancelled）+ 3 项改 scope；判词与逐条偏离见执行记录。A① 保留 teacher_mdp 所留下的死代码去向属新的挂账，须另立事项
close_when: 用户审过清单后——(a) 批准：按清单执行完毕，判据形状见清单 §验收条件，清单内事项按 cancelled/superseded 移入 `work/closed/2026/` ⇒ done；(b) 否决或改走"套件分层不删代码" ⇒ cancelled 并写理由，另立分层项；观测 = 清单记录 + 删除 commit + 离线全绿判词
evidence: acceptance/records/2026-10-09-repo-architecture-review, acceptance/records/2026-10-09-retired-family-prune-manifest, acceptance/records/2026-10-09-retired-family-prune-execution
---

## 当前状态

已关闭（`done`）：三条退休线的代码、注册、离线套件条目与在办事项已移出主路径，判词 = 执行记录里的
`ALL_OFFLINE_CHECKS_PASSED (37/37)`。执行前的候选名单、逐项判据、裁决与执行面核查全在清单记录，
落盘事实与偏离在执行记录（本项不复述）。

## 未覆盖边界

未真跑训练/仿真（只证"能注册、能构造、能过闸门"）；A① 保留的 `teacher_mdp` 旧线内核仍在主路径，
其去向须另立活跃事项；其余未处理面（诊断/验证工具的旧任务 id 默认值、skill 树里的失效入口、
一次性脚本 `_b3_remove_version_classes.py`）逐条列在执行记录「未覆盖边界」。
