# lizard2 v3 训练曲线读数：任务级 2k 定型、质量层到 6000 仍在动（2026-10-10）

## 适用范围

`logs/rsl_rl/lizard2_v3/2026-10-10_10-14-50`（6000/6000、4096 envs、seed 42）的**训练过程读数**：
千迭代分块均值、各量退出平台带的最早分块、终止项分块均值。**不覆盖**策略判决（归
`acceptance/records/2026-10-10-lizard2-v3-first-eval.md`），也不判"步态好或坏"；也不做 v2→v3 归因
（机体与动作接口同时变）。

本记录补的是 v3 版本目录里此前无家的那半：`dump_tb.py` 的入库步骤（`v3/tb_scalars.csv`）与 run 目录
回填在训练收尾后执行，读数由此有唯一落点。

## 验收条件

1. 读数必须来自 run 自己的记录（tfevents → csv），不是"看起来像"。
2. 说"收敛"必须分层回答：任务级（走完/存活）、质量（跟踪）、策略收紧（熵/方差）。
3. 分块宽度与平台带必须写在读数里，不能让读者猜阈值。
4. 单 run 就是单 run：不得据此声称 seed 稳定性。
5. 预算 6000 是用户声明的**短窗**（`v3/PLAN.md`：读新机体的短窗，不是训练候选）⇒ 任何读数只能称
   "截至 6000 步"，不许称收敛 / 修复。

## 结果

条件：`tb_scalars.full.csv`（该 run 全部 25 个 scalar tag × 6000 迭代，机器本地），分块 = 1000 迭代；
"平台带" = **从该分块起，其后所有分块都留在尾块 ±band 内**的最早分块（band 取 2% / 5% / 10%，
是读数口径不是判据）。

| tag | 尾块均值 | 分块均值（0 / 1k / 2k / 3k / 4k / 5k） | 2% / 5% / 10% 平台带 |
|---|---|---|---|
| `Train/mean_reward` | 27.59 | 0.340 / 10.6 / 25.25 / 26.59 / 27.27 / 27.59 | 4k / 3k / 2k |
| `Train/mean_episode_length` | 999.4 | 65.7 / 558.1 / 999.6 / 999.7 / 999.7 / 999.4 | 2k / 2k / 2k |
| `Metrics/success_rate` | 1.000 | 0.395 / 0.714 / 1.000 / 1.000 / 1.000 / 1.000 | 2k / 2k / 2k |
| `Metrics/base_velocity/error_vel_xy` | 0.0999 | 1.006 / 0.613 / 0.1140 / 0.1081 / 0.1038 / 0.09986 | 5k / 4k / 3k |
| `Loss/entropy` | −8.737 | −3.981 / 1.566 / −6.555 / −8.069 / −8.694 / −8.737 | 4k / 4k / 3k |
| `Policy/mean_std` | 0.2019 | 0.2759 / 0.3182 / 0.2217 / 0.2067 / 0.2014 / 0.2019 | 4k / 3k / 2k |
| `Episode_Reward/track_lin_vel_xy_miki` | 1.426 | 0.043 / 0.740 / 1.407 / 1.416 / 1.421 / 1.426 | 2k / 2k / 2k |

终止项（`Episode_Termination/*`，分块均值）：

| tag | 0 块 | 1k 块 | 2k 块 | 尾块 | 读法 |
|---|---|---|---|---|---|
| `time_out` | 0.024 | 0.493 | 0.999 | 0.999 | 走完一整段的占比在 2k 到位 |
| `head_contact` | **0.963** | 0.507 | 0.00093 | 0.00089 | 失败模式**首现于第 0 块**（<1000 it 主导），2k 后近零 |
| `base_contact` | 5.6e−07 | 0 | 0 | 0 | 全程几乎未触发 |

**最后千迭代买到的**（同一 run 内，不是两次 run）：`mean_reward` 27.27 → 27.59（+1.2%）、
`error_vel_xy` 0.1038 → 0.09986（−3.8%）、`entropy` −8.694 → −8.737、`mean_std` 0.2014 → 0.2019
（**微升**）。

## 判定

1. **任务级收敛在 2000 迭代**：episode 长度顶到 1000 步上限、`time_out` 0.999、`success_rate` 1.0、
   `base_contact` ≈ 0 ⇒ "会不会走完"在 2k 定型。
2. **质量层没有平台期**：`error_vel_xy` 的 2% 带落在 5k（即最后一个分块才进带）、熵的 2% 带落在 4k；
   而 `mean_std` 尾块比上一块**微升**，不是"收紧到平台"。⇒ **"6000 已收敛"不成立**；本 run 结束时
   策略仍在动。与预算声明一致（短窗），也只是短窗。
3. **失败模式有明确首现点**：`head_contact` 第 0 块占 0.963，2k 块降到 0.00093 ⇒ 早期是"砸头"主导，
   2k 后转偶发。数值与 v1（1k 块 0.0080）同方向，但**跨机体不可比**，此处只作形状描述。
4. **不能据此说 seed 稳定性**：n=1，无第二个 run 可比，run-to-run 散度无处可测。

## 证据引用

```bat
:: 全量曲线（机器本地、不入库）
E:\IsaacLab\env_isaaclab\Scripts\python.exe rl_exp\tools\trainlog\dump_tb.py ^
  --log_dir "E:\IsaacLab\logs\rsl_rl\lizard2_v3\2026-10-10_10-14-50" ^
  --out rl_exp\versions\lizard2\main\v3\tb_scalars.full.csv        :: 150000 点

:: 入库抽样
E:\IsaacLab\env_isaaclab\Scripts\python.exe rl_exp\tools\trainlog\dump_tb.py ^
  --csv_in rl_exp\versions\lizard2\main\v3\tb_scalars.full.csv ^
  --out rl_exp\versions\lizard2\main\v3\tb_scalars.csv --max_points 150   :: 3775 点 = 25 tags × 151

:: 曲线图（可再生 viz，不入库）
E:\IsaacLab\env_isaaclab\Scripts\python.exe rl_exp\tools\trainlog\plot_tb.py ^
  --csv rl_exp\versions\lizard2\main\v3\tb_scalars.csv --out_dir rl_exp\versions\lizard2\main\v3\plots
```

`dump_tb.py` 需要 TensorBoard ⇒ 用 IsaacLab 的 venv 解释器，系统 python 会 `ModuleNotFoundError`（实测）。
抽样器自测：`python rl_exp\tools\verify\test_dump_tb_sampling.py`（`DUMP_TB_SAMPLING_OK`）。

## 未覆盖边界

1. **单 run / 单 seed**：上面任何"改进了多少"都不能与 seed 噪声相比。
2. **分块均值口径是本记录选的**（1000 迭代 / 2%–5%–10% band）：换宽度会得到不同的"退出平台"分块，
   换宽度必须重新陈述，不能只换数字。
3. **`head_contact` 的首现精度只到分块**（第 0 块内）；要精确到迭代需重读全量 csv。
4. **曲线不含步态量**：滑移、承重分配、离地高度都不在 tfevents 里（首判里的 `foot_slip_mps` 来自评测，
   不在本记录）。
5. **入库是抽样**：`tb_scalars.csv` 为 150 点/tag，逐迭代细节以机器本地 `.full.csv` 为准。
6. **短窗**：6000 迭代是用户声明的预算，本记录的任何判定**不适用于**"这条线可用/收敛"的结论。
