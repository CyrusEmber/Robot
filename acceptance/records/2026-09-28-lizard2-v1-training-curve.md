# lizard2 v1 训练曲线读数：任务级 1–2k 定型，曲线到 14000 仍未平台化（2026-09-28）

## 适用范围

`logs/rsl_rl/lizard2_v1/2026-09-22_19-26-50`（14000/14000、4096 envs、seed 42）的**训练过程读数**：
千迭代分块均值、各量退出平台带的最早分块、终止项首现。**不覆盖**策略评测（那是判决侧，见 v1 `NOTES.md`
引用的两份记录），也不判"步态好或坏"。

本记录补的是一件此前**无家**的数据：v1 的"训练读数"行只指向 tfevents 与巡检入口，而 `dump_tb.py` 的
入库步骤（`versions/<line>/<vN>/tb_scalars.csv`）当时没有执行，所以收敛类的数字只活在引用它的散文里。
入库已补：同目录 `tb_scalars.csv`（150 点/tag）已就位，`ablation_harness/plot_eval.py --report` 会自动读它。
本记录的数字取自**全量** csv（`tb_scalars.full.csv`，350000 点，机器本地），分块均值由该 csv 按 1000 迭代
分块求均值得到。

## 验收条件

1. 读数必须来自 run 自己的记录（tfevents → csv），不是"看起来像"。
2. 说"收敛"必须给三层分开的答案：任务级（存活/走完）、质量（跟踪）、策略收紧（熵/方差）。
3. 分块宽度与平台带必须写在读数里，不能让读者猜阈值。
4. 单 run 就是单 run：不得据此声称 seed 稳定性。

## 结果

条件：`tb_scalars.full.csv`（= 该 run 的全部 25 个 scalar tag × 14000 迭代），分块 = 1000 迭代；"平台带"
= **从该分块起，其后所有分块都留在尾块 ±band 内**的最早分块（band 取 2% / 5% / 10%，是读数口径不是判据）。

| tag | 尾块均值 | 分块均值（0 / 1k / 2k / … / 13k） | 2% / 5% / 10% 平台带 |
|---|---|---|---|
| `Train/mean_reward` | 32.43 | 7.29 / 25.8 / 28.9 / 30.2 / 30.9 / 31.2 / 31.4 / 31.7 / 31.7 / 31.9 / 32.1 / 32.2 / 32.3 / 32.4 | 9000 / 4000 / 3000 |
| `Train/mean_episode_length` | 999.9 | 412 / 997 / 999 → 上限 1000 | 1000 / 1000 / 1000 |
| `Metrics/success_rate` | 1.000 | 0.609 / 1.000 / 1.000 … | 1000 / 1000 / 1000 |
| `Metrics/base_velocity/error_vel_xy` | 0.0801 | 0.654 / 0.125 / 0.106 / 0.0978 / 0.0928 / 0.0908 / 0.0888 / 0.0858 / 0.0857 / 0.0848 / 0.0824 / 0.0813 / 0.0803 / 0.0801 | 11000 / 10000 / 7000 |
| `Loss/entropy` | −10.24 | 3.13 / −1.76 / −5.11 / −7.02 / −7.97 / −8.29 / −8.41 / −9.04 / −8.90 / −9.16 / −9.73 / −9.91 / −9.94 / −10.24 | 13000 / 11000 / 10000 |
| `Policy/mean_std` | 0.2065 | 0.348 / 0.277 / 0.246 / 0.230 / 0.222 / 0.220 / 0.219 / 0.214 / 0.216 / 0.214 / 0.210 / 0.209 / 0.209 / 0.207 | 10000 / 7000 / 4000 |
| `Episode_Reward/track_lin_vel_xy_miki` | 1.449 | 0.517 / 1.390 / 1.418 / 1.428 / 1.435 / 1.437 / 1.439 / 1.443 / 1.443 / 1.444 / 1.446 / 1.447 / 1.448 / 1.449 | 3000 / 1000 / 1000 |

终止项（`Episode_Termination/*`，分块均值）：

| tag | 0 块 | 1k 块 | 尾块 | 读法 |
|---|---|---|---|---|
| `time_out` | 0.328 | 0.992 | 0.9999 | 走完一整段的占比在 1k 就到位 |
| `head_contact` | **0.668** | 0.0080 | 8.98e−05 | 失败模式**首现于第 0 块**（<1000 it 就在砸头），1k 后残余 |
| `base_contact` | 0 | 0 | 0 | 全程未触发 |

**10000 与 14000 两点的差额**（同一 run 内，不是两次 run）：`mean_reward` 32.09 → 32.43（+1.1%）、
`error_vel_xy` 0.0824 → 0.0801（−2.8%）、`mean_std` 0.2099 → 0.2065。即**后 4000 迭代买 1–3% 的跟踪改善**。

## 判定

1. **任务级收敛在 1000–2000 迭代**：episode 长度顶到 1000 步上限、`time_out` 0.99、`success_rate` 1.0、
   `base_contact` 恒 0。按这三条，"会不会走完"在 1–2k 就定型。
2. **质量层没有平台期**：`error_vel_xy` 的 2% 带落在 11000、熵的 2% 带落在 13000、`mean_std` 单调下降，
   千迭代增量从 +0.64（3k→4k）衰减到 +0.12（12k→13k）但**从未归零**。⇒ 本 run 到 14000 时策略仍在收紧，
   "14000 已收敛"不成立；预算差（10000 vs 14000）因此不是中性的，只是幅度只有 1–3%。
3. **失败模式有明确首现点**：`head_contact` 在第 0 块占 0.67，1k 块降到 0.008 ⇒ 早期是"砸头"主导，
   1k 后转为偶发。这条是 v2 那条曲线（`head_contact` 在 1k 仍为 1.0）的对照基线。
4. **不能据此说 seed 稳定性**：n=1；`logs/rsl_rl/lizard2_v1/2026-09-23_17-31-26` 只有 `run_manifest.json`、
   无曲线，run-to-run 散度无处可测。

## 证据引用

- 全量曲线（机器本地、不入库）：`logs/rsl_rl/lizard2_v1/2026-09-22_19-26-50` 的 tfevents →
  `python rl_exp\tools\trainlog\dump_tb.py --log_dir <run> --out rl_exp\versions\lizard2\main\v1\tb_scalars.full.csv`
- 入库抽样（已提交）：`python rl_exp\tools\trainlog\dump_tb.py --csv_in rl_exp\versions\lizard2\main\v1\tb_scalars.full.csv --out rl_exp\versions\lizard2\main\v1\tb_scalars.csv --max_points 150`
  （3750 点 = 25 tags × 150；抽样只为入库体积，首尾点保留，分块趋势不变）
- 曲线图（已跑通）：`python rl_exp\tools\trainlog\plot_tb.py --csv rl_exp\versions\lizard2\main\v1\tb_scalars.csv --out_dir rl_exp\versions\lizard2\main\v1\plots`
  （5 张 png，`plots/` 为可再生 viz、不入库）
- **报告侧还没通**（本记录实测，独立缺口）：`python ablation_harness\plot_eval.py --protocol lizard2_flat_v2 --group v1 --report rl_exp\versions\lizard2\main\v1`
  在读 eval.json 时就崩 `KeyError: 'mode'`（`plot_eval.py:65`）—— 它期望顶层 `mode` 与字符串 `checkpoint`，
  而 `ablation_harness/results/**` 里**没有一份** eval.json 有这两个形状（全是 `protocol: {...}` /
  `checkpoint: {...}`）⇒ 该报告器对盘上全部记录都已失效，训练曲线那一段因此到不了。
  这条属评测台自己的缺口（SSOT = `ablation_harness/HARNESS.md`），不在本记录里修，已立项并已收：
  `work/closed/2026/plot-eval-report-stale.md`（`plot_eval.py` 现在按 `report_format` 分派两种读法，
  lizard2 的记录能出 `report.html`）。
- 抽样器自测：`python rl_exp\tools\verify\test_dump_tb_sampling.py`（`DUMP_TB_SAMPLING_OK`）

## 未覆盖边界

1. **单 run**：无 run-to-run 散度 ⇒ 上面任何"改进了多少"都不能与 seed 噪声相比。
2. **分块均值口径是本记录选的**（1000 迭代 / 2%–5%–10% band）：换宽度会得到不同的"退出平台"分块，
   换宽度后必须重新陈述，不能只换数字。
3. **`head_contact` 的首现迭代精度只到分块**（第 0 块内），要精确到迭代需重读全量 csv。
4. **曲线不含步态量**：滑移、承重分配、离地高度都不在 tfevents 里，本记录不涉步态判决。
5. **入库是抽样**：`tb_scalars.csv` 为 150 点/tag，逐迭代细节以机器本地 `.full.csv` 为准。
6. **报告侧当时未通**（现已修，见"证据引用"）：`plot_eval.py --report` 当时对盘上所有记录都崩
   （`KeyError: 'mode'`）⇒ "eval 报告自动读这张 csv"在写作本记录时还不能演示；csv 的落点与消费约定成立，
   消费方已按 lizard2 的记录形状修通并关项。
