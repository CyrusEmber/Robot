---
id: diagnostic-run-gate
title: 诊断 run 与 campaign 表之间没有闸门（HARNESS 挂账 #5）
scope: ablation_harness
status: done
landing: ablation_harness/run_ablation.py#summarize
close_when: 执行者跑一次"零动作 run + 真分数 run 同目录树"的 `--summarize`，观察 `summary.csv`：方案 (a) 成立 = 零动作行带 kind 标注或落进专属分组；方案 (b) 成立 = 非 smoke 组出现零动作行时 summarize 报错并以非零码退出。任一观测成立即关；两者都不成立就把实际输出记入本项并保持 open
evidence: acceptance/records/2026-09-23-diagnostic-row-identity-gate.md
outcome: 关闭于 2026-09-23，落法取 (b)：`_identity_report` 读每行 `record.json` 的 `policy.kind`，非 `smoke` 表里出现非 `checkpoint` 行即点名并非零退出；缺 `policy.kind` 的老记录记 `uncertified` 而不拒（否则历史表全变不可读）。观测：`--protocol locomotion_eval_v4` 点名根表那行 `zero_action` 且退出码 1、`--protocol locomotion_eval_v2` 点名 `dev` 组那行（总 3，其余是既有条件冲突）、`--protocol locomotion_eval_v3` 的 smoke 组放行且退出 0；反证在 `test_eval_record.py`（四例：非 smoke 拒 / smoke 放行 / checkpoint 放行 / 缺 kind 只报不可认证）。顺带读出的事实：`locomotion_eval_v4` 目前**没有任何真分数行**，它根表唯一那行是零动作诊断行，读数与 v3 smoke 同值。规则已写进 `HARNESS.md` 记录格式节 ④。
---

## 问题与本次范围

`--group` 只决定落盘目录，**不校验 run 的身份**：诊断 run（`policy.kind=zero_action` / `smoke_only`）
与真分数行会混进同一张表。本轮靠"把 smoke 进 `--group smoke` 目录"规避，那是**人工命名约定**，
不是机制——下一个人照样会把诊断 run 写进正式组。

## 关闭方式

落法 (b)，读数与反证见 `outcome` 与 `evidence`。`smoke` 组反方向（混进 `checkpoint` 行）没有闸门，
仍靠纪律——这条边界写在记录里，不在这里重复。

## 未覆盖边界

本项只管"表里混身份"，不管诊断 run 本身的数值是否正确。另：`results/locomotion_eval_v3/smoke/` 里
completion 列在这条跑上没有信息量，**不得**被后人当作 v3 上的性能引用（该提醒归 `HARNESS.md`）。
