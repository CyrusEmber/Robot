---
id: teacher-literal-parity-gate
title: 补闸门：教师快照的资产派生字面量要有可验证关系（矩阵定位的缺口）
scope: rl_exp/tools/verify, rl_exp/tasks, rl_exp/versions/freeze_parity.json
status: open
landing: rl_exp/tools/verify/check_dr_parity.py, rl_exp/versions/freeze_parity.json, rl_exp/tasks/teacher_env_cfg.py
next: 先**由用户拍板**形态（三选一）：① **声明式** —— 每个冻结字面量旁声明它所依据的资产事实（体尺 / 足底尺寸 / 运动范围的来源），闸门断言该声明仍与它命名的资产一致（把 ⑤ 的形状扩到 `tasks/*.py` 里的字面量）；② **派生式** —— 资产派生量从资产或参数导出而非手抄，并把"冻结的是当时的资产事实、不是那串数字"写清；③ **对照式** —— 断言教师字面量与家族侧构造结果一致，**默认不选**：教师是 *frozen* 对照，与家族相等不是不变式（除非把比对面收窄到"资产事实"那一层）。形态定后：把矩阵四例做成夹具（C3 / C4 必须由静默变红，C1 / C2 保持现状），并复跑 `rl_exp\tools\verify\run_offline_checks.bat`
close_when: 闸门落地且两侧夹具齐（"教师侧资产派生字面量被改 ⇒ 红"与"家族侧有意调参 ⇒ 不误红"）、离线套件全绿 ⇒ 关。读数与缺口定义见 `acceptance/records/2026-09-22-teacher-snapshot-parity-matrix.md`（本项不复述）
depends_on: teacher-snapshot-asset-sync
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
