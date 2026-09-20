---
id: diagnostic-run-gate
title: 诊断 run 与 campaign 表之间没有闸门（HARNESS 挂账 #5）
scope: ablation_harness
status: open
landing: ablation_harness/run_ablation.py#summarize
next: 二选一落成机制（不许停在人工约定）——(a) `--summarize` 按 `policy.kind` 分组或给行加 kind 标注；或 (b) 非 smoke 组出现 `policy.kind != "checkpoint"` 的行时拒绝并报错。选定后在 `run_ablation.py` 写成断言，并留一条反证
close_when: 执行者跑一次"零动作 run + 真分数 run 同目录树"的 `--summarize`，观察 `summary.csv`：方案 (a) 成立 = 零动作行带 kind 标注或落进专属分组；方案 (b) 成立 = 非 smoke 组出现零动作行时 summarize 报错并以非零码退出。任一观测成立即关；两者都不成立就把实际输出记入本项并保持 open
---

## 问题与本次范围

`--group` 只决定落盘目录，**不校验 run 的身份**：诊断 run（`policy.kind=zero_action` / `smoke_only`）
与真分数行会混进同一张表。本轮靠"把 smoke 进 `--group smoke` 目录"规避，那是**人工命名约定**，
不是机制——下一个人照样会把诊断 run 写进正式组。

## 为什么现在不关

两个候选做法都还没实施，且都能被离线反证；没有实施就没有可观测的判据，写了关闭条件也只是措辞。

## 未覆盖边界

本项只管"表里混身份"，不管诊断 run 本身的数值是否正确。另：`results/locomotion_eval_v3/smoke/` 里
completion 列在这条跑上没有信息量，**不得**被后人当作 v3 上的性能引用（该提醒归 `HARNESS.md`）。
