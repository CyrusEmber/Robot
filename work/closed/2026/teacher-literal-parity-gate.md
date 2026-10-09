---
id: teacher-literal-parity-gate
title: 补闸门：教师快照的资产派生字面量要有可验证关系（矩阵定位的缺口）
scope: rl_exp/tools/verify, rl_exp/tasks
status: superseded
landing: rl_exp/tools/verify/check_dr_parity.py
outcome: 本闸门的两侧对象随退役线清理消失——教师快照 `teacher_env_cfg.py` 已删除，其唯一主体 `freeze_parity.json` 也随同删除，静默缺口无处可补 ⇒ 补闸门动作由清理项接管，矩阵读数仍归 evidence。
superseded_by: retired-family-code-prune
evidence: acceptance/records/2026-09-22-teacher-snapshot-parity-matrix
---

## 问题与本次范围

矩阵实测出一类**教师侧**改动在 ④⑤⑥ 上全静默（读数与逐例证据归
`acceptance/records/2026-09-22-teacher-snapshot-parity-matrix.md`，本条不复述）。本项只做一件事：
把这一类缺口纳入闸门。

**为什么不是"照着 ④ 再写一条"**：④ 比的是**两个文件之间**的行集合；本条缺的是"**教师侧字面量与它据以取值的
资产事实**之间"的关系，对象不是家族文件。照抄 ④ 去比家族侧会把"教师必须与家族不同"（21 条已审查单侧差异、
v3–v15 的 recipe delta）一并判红，等于取消冻结纪律。故形态必须显式选一个，且"有意调参不误红"是验收的一半。

## 未覆盖边界

本项不改 `freeze_parity.json` 已登记的 subject 语义，也不动既有的 21 条 `wiring_allowlist`；矩阵只覆盖单侧变异与
一条版本、一个尺寸参数 ⇒ 缺口总量未知，本项以"这一类变更会红"为验收，不以"穷举全部资产派生量"为验收。
