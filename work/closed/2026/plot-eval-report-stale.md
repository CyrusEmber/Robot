---
id: plot-eval-report-stale
title: plot_eval 报告器与现行 eval.json 形状不符（盘上全崩，训练曲线段因此到不了）
scope: ablation_harness
status: done
landing: ablation_harness/plot_eval.py
outcome: 按"修，但只修 lizard2 这一代记录"处置：`_load_runs` 改为按 `report_format == "baseline-eval-2"` 分派两种读法（`_new_run` / `_legacy_run`），新形状的图=**逐记录判据栅格**（`_gates`，绿=过/红=FAIL）与**读数表**（`_record_rows`，identity + verdict + 标量 metrics），legacy 的 trend/terrains 两图保持原样、只在其记录形状出现时才画；HTML 里写明"这份记录没有 nominal/robust 划分与逐地形网格，故不画那两张图"，不再静默。实测：`python ablation_harness\plot_eval.py --protocol lizard2_flat_v2 --group v1 --report rl_exp\versions\lizard2\main\v1` → `report.html`（208 KB，2 runs），含 5 张训练曲线 + 判据栅格 + 读数表，**不再出现 "no tb_scalars.csv" 警告**（csv 已入库）。另加 `plot_eval.py --self-test`（14 条手写 fixture，两种形状各一条）——legacy 分支盘上已无记录可跑，这是它唯一的活处；同一笔把 `__main__` 从裸 `main()` 改成 `sys.exit(main())`，否则自检失败也返回 0。未核：报告器图组是否有人消费（见"未覆盖边界"）。
evidence: acceptance/records/2026-09-28-lizard2-v1-training-curve
---

## 当前状态

已收。原缺口（`_load_runs` 取顶层 `mode`/字符串 `checkpoint`，对盘上全部记录崩 `KeyError: 'mode'`）消除：
两种形状各走各的适配器，新形状不再执行 legacy 的取数路径。lizard2 v1 的版本目录现在有可打开的
`report.html`（训练曲线 + 判据 + 读数表），"曲线入库后没有仓内出口"这条随之关闭。

## 未覆盖边界

- **只覆盖 lizard2 这一代（`baseline-eval-2`）与 legacy 两形状**：第三种记录形状出现时要再加适配器并配 fixture，
  本项不预造。
- **`--self-test` 未登记进 `rl_exp\tools\verify\offline_suite.py`**：fixture 现在只能手动跑，
  legacy 分支因此仍不被 CI 看守。要不要登记是 owner 判定（登记要动套件形状闸门）。
- **报告器是否有人消费未核**：图组（gates / trend / terrains）与 report.html 的读者仍未查证；
  若无人消费，判废比继续维护更省 —— 本项按"修"处理是因为命令此前直接崩，不是因为有读者证据。
- **不改 eval.json 的写侧与判据**：本条只动读侧与呈现；记录格式定义仍归 `ablation_harness/HARNESS.md`。
- **未回填历史 protocol 目录**：`results/**` 里其它协议的记录仍是 legacy 形状，报告器能读，但没有为它们跑过。
