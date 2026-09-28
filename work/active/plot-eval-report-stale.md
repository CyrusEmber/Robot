---
id: plot-eval-report-stale
title: plot_eval 报告器与现行 eval.json 形状不符（盘上全崩，训练曲线段因此到不了）
scope: ablation_harness
status: open
landing: ablation_harness/plot_eval.py
next: ① 决定怎么读现行记录：`_load_runs` 取顶层 `mode`（字符串）与字符串 `checkpoint`，而 `results/**` 全是 `protocol: {...}` / `checkpoint: {...}` 形状 ⇒ `KeyError: 'mode'`（`plot_eval.py:65`）——要么改它对现行形状取数，要么明确标成"只读 legacy"并写进 `HARNESS.md` ② 读通后验证训练曲线段：v1 的 csv 已就位，`--report rl_exp\versions\lizard2\main\v1` 应出图而不是走"no tb_scalars.csv"警告 ③ 若判该报告器退役，指明谁接管它现在的两件事（趋势/地形图 + 训练曲线段），不留静默失效入口
close_when: 对 `ablation_harness/results/lizard2_flat_v2/v1` 加 `--report` 能生成 report.html 且训练曲线段出现（或该报告器被明确判废并写明接管者）；无论哪种，`HARNESS.md` 的格式/挂账节同步那条决定
evidence: acceptance/records/2026-09-28-lizard2-v1-training-curve
---

## 问题与本次范围

`plot_eval.py` 的 `--report` 是训练曲线唯一的仓内出口（它读版本目录的 `tb_scalars.csv`），但它读 eval.json
时崩在第一个字段上。本项只收"这个入口为什么读不动、怎么处置"；**不**改协议、**不**改 eval.json 的写侧、
**不**重定判据（记录格式的正式定义归 `ablation_harness/HARNESS.md`）。

## 当前状态

- 实测：`python ablation_harness\plot_eval.py --protocol lizard2_flat_v2 --group v1 --report rl_exp\versions\lizard2\main\v1`
  → `KeyError: 'mode'`（`plot_eval.py:65`）。扫过 `ablation_harness/results/**` 的全部 eval.json，没有一份带
  顶层 `mode` 或字符串 `checkpoint` ⇒ 这不是某个家族的 legacy 问题，是这个报告器对盘上全部记录都已失效。
- 后果：曲线入库后**没有仓内可视化出口**能自动读它（`plot_tb.py --csv` 仍可直读，已实测出图），
  "eval 报告自动读曲线"这条通路今天不能演示。

## 未覆盖边界

- 失效的原因（报告器没跟上格式，还是格式换了没同步读者）尚未定论；本项只记现象与处置方向。
- 报告器的图组（trend / terrains）是否仍被使用、是否有人消费 report.html，未核；若无人消费，判废比修更省。
- `results/**` 的历史 eval.json 是否也需要按现行格式甄别（legacy 三态读法），不在本项。
