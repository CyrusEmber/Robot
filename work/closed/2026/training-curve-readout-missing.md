---
id: training-curve-readout-missing
title: 训练曲线读数无家：入库步骤可被跳过，收敛读数没人收
scope: rl_exp/tools/trainlog, rl_exp/tools/pipeline, rl_exp/versions/lizard2, .codemaker/rules/versioning.mdc, acceptance/records
status: done
landing: rl_exp/tools/pipeline/declare_family.py, .codemaker/rules/versioning.mdc, rl_exp/tools/trainlog/dump_tb.py
outcome: 已收"读数无家"这一件：v1 曲线入库 `versions/lizard2/main/v1/tb_scalars.csv`（抽样 150 点/tag，全量 `.full.csv` 留机器本地）+ 收敛读数落 `acceptance/records/2026-09-28-lizard2-v1-training-curve.md`（分块均值、平台带、`head_contact` 首现分块、n=1 边界）+ `versioning.mdc` §A 第 4 步写明入库落点与"收敛读数归 `acceptance/records/`" + v1/v2 NOTES 的"训练读数"行改为落点 + 读法 + 记录路径 + `declare_family.py` 的 NOTES 骨架新增"训练曲线"行（新版本默认带槽位）。**不含追溯回填**：§A 只要求处理中的版本做导出，历史上未入库的版本不是本项欠账，日后若某版要复查收敛，按同一落点补即可。过程中另查出 `plot_eval --report` 对盘上全部记录崩（`KeyError: 'mode'`），独立立项 `plot-eval-report-stale`
evidence: acceptance/records/2026-09-28-lizard2-v1-training-curve
---

## 当前状态

已收。判据（"读数有家且读法能跑通"）在 v1 上兑现：`dump_tb.py` 入库 → `plot_tb.py --csv` 出图（实测 5 张
png）→ 收敛读数在记录里带口径与边界；规则侧落点可被磁盘验证（§A 第 4 步的命令可跑）。

顺带的观察（**不是**本项的欠账）：`git grep -l "logs/rsl_rl" -- "rl_exp/versions/**/NOTES.md"` 有 20 处提到 run，
其中有入库 csv 的 4 处。仓里没有"每条 run 都要入库"的要求，故不据此派活；仅记录这个规模，供日后判断
"某版要不要补"时参考。

## 未覆盖边界

- **不主张追溯义务**：本项钉的是"处理中的版本如何处理"（落点 + 槽位 + 规则），不回溯历史版本。
- **不证明任何一次 run 的 tfevents 还在**：落点与槽位存在 ≠ 曲线可取。
- **收敛读数的口径是一次读数声明**（分块 1000 迭代 / band 2%–5%–10%），不是判据；换口径要重新陈述。
- **单 run**：n=1，run-to-run 散度无处可测，读数不能与 seed 噪声相比。
- **入库是抽样**：仓内 csv 不保证逐迭代细节，全量留机器本地；抽样器行为由 `test_dump_tb_sampling.py` 看守。
