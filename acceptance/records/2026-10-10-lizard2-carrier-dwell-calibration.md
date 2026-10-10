# 非足承载门槛的第三档标定：真实塌陷样本把"时长轴"钉住，档位轴仍缺（2026-10-10）

## 适用范围

`work/active/lizard2-family-landing.md` 评测协议那节要的缺口：`no_non_foot_carrier` 的**"持续部分承重"档
标定样本**（`acceptance/records/2026-09-22-lizard2-eval-protocol-freeze.md:51-52` 记为"缺介于 0 与 1.0
之间的样本，未测"）。

本轮用一份**真实的、同一机体同一采集器**的 rollout 去补：同配方未训练策略（v3 作废那次 run 的
`model_0.pt`）× PLAY 任务机器人塌陷、非足部位真实受力。它给出的是**时长轴**的证据，
不是档位轴；结论只能到"这个样本说了什么"，不改协议、不改阈值。

## 验收条件

1. 样本必须**真实**（真 rollout，不是合成帧），且与首判同机体、同采集器、同协议；
2. 判据口径用判分器的**自己的函数**（`baseline_metrics._sustained`、`alive`），不另写 dwell 语义；
3. 读数必须写明样本量、alive 帧、体重量纲（`fraction` 是"受伤部位竖直载荷 / 体重"）；
4. 一次样本不是标定全集：缺的那一档若未补上，必须**明写成缺**，不许用别的档代替。

## 结果

### ① 样本与条件

| 项 | 值 |
|---|---|
| 策略 | `E:\IsaacLab\logs\rsl_rl\lizard2_v3\2026-10-10_10-09-15\model_0.pt`（v3 作废 run 的唯一样本；**未训练**），`--policy_mode sampled` |
| 任务 / 协议 | `Lizard2-Flat-Play-v3` / `ablation_harness/protocols/lizard2_flat_v5.json` |
| 规模 | 256 envs、seed 123、1000 帧 × 0.02 s = 20 s、27 个非足部位、体重 **708.3 N** |
| 存活 | alive 188926 / 256000 env-帧；**127/256** env 提前终止（未训练策略会塌） |
| 落点 | `%TEMP%\carrier_calib_v3\eval.json` + `eval.frames.pt`（**机器本地**，不进仓） |

这份样本**故意不写进 `ablation_harness/results/<协议>/`**：它不是候选行，进campaign 表会污染对账。

### ② 载荷分布（alive 帧）

| 读法 | 值 |
|---|---|
| 逐帧 `fraction` | p50 **0.0000**、p90 **0.0000**、p99 **0.0000**、max **11.8728** |
| 逐 env 最坏帧 | p50 **0.7470**、p90 **3.0471**、max **11.8728** |
| 曾承重（>0.01）的部位 | `neck_pitch`、`rf_haa`、`tail2_pitch`、`rf_hfe`、`tail3_pitch` |
| `load_sum` 最大值 | 11.8728 |

即：**每个 env 在某一帧都狠狠压过非足部位（中位数 0.75 倍体重）**，但那是**冲击**——
逐帧分位的 p90/p99 仍是 0。塌陷的读数是"砸下去"，不是"扛着"。

### ③ 判分器口径下的持续判定（`(fraction ≥ t).any(bodies)` 持续 ≥ 0.5 s）

| t | 越限帧数 | 判否的 env |
|---|---|---|
| 0.03 | 3365 | **0/256** |
| 0.05（现阈值） | 3088 | **0/256** |
| 0.08 | 2639 | **0/256** |
| 0.10 | 2362 | **0/256** |
| 0.20 | 1293 | **0/256** |

单 env 的连续越限时长（t=0.05）：中位 **2 帧**、最长 **6 帧**（0.12 s）——dwell 是 0.5 s = **25 帧**，
差 **4 倍以上**。`load_sum` 判据同样 0/256。

### ④ 结论

1. **时长轴被钉住**：连"未训练策略塌陷砸地"这种最粗的工况，非足载荷也**持续不到 0.5 s**。
   ⇒ `sustain_s = 0.5` 有一大截余量，它把"冲击"与"扛着"分开这件事在这份样本上成立。
2. **档位轴仍缺那一档**：本样本是**高幅值 / 短时长**，不是"持续部分承重"（5–10% 体重扛 ≥0.5 s）。
   缺口**没有被这次补上**，不能拿它冒充。现有三点仍只是：
   健康 = 首判 0.0（`acceptance/records/2026-10-10-lizard2-v3-first-eval.md`）、
   极端异常 = 压头 1108 N > 1 倍体重（协议冻结记录）、退役线故障量级 11.6–12.8% 体重。
3. **补那一档最便宜的路径**（本记录不去做）：用启动探针的 `--head-press` 机制**浅压 + 保持 ≥1 s**
   （`--press-depth` 取小值），并且要**落帧记录**才能用判分器自己的 dwell 语义判——探针现在只打印
   力与终止，不留可判帧。另一条是等一条真的"拖地爬"策略（退役线出现过 11.6–12.8% 那种）。

## 证据引用

**这份读数的输入与读法**（判分器口径，脚本一次性、未入库；样本帧只在那台机器上）：

- 输入：`%TEMP%\carrier_calib_v3\eval.frames.pt`；
- `alive` = `baseline_metrics._alive(terminated, timeout)`；
  持续 = `baseline_metrics._sustained((non_foot_fraction >= t).any(dim=bodies) & alive, dt, 0.5)`；
  逐帧分位与"最长连续越限"按上式的布尔矩阵逐 env 数。
- `load_sum` = `(non_foot_fraction * alive).sum(dim=bodies)`，同一 dwell。

采集命令（本机，可重跑；输出落 `%TEMP%`）：

```bat
E:\IsaacLab\env_isaaclab\Scripts\python.exe ablation_harness\baseline_eval.py --viz none ^
  --task Lizard2-Flat-Play-v3 --protocol ablation_harness\protocols\lizard2_flat_v5.json ^
  --checkpoint E:\IsaacLab\logs\rsl_rl\lizard2_v3\2026-10-10_10-09-15\model_0.pt ^
  --policy_mode sampled --num_envs 256 --seed 123 ^
  --output "%TEMP%\carrier_calib_v3\eval.json"
```

- 门槛的原始标定与缺口：`acceptance/records/2026-09-22-lizard2-eval-protocol-freeze.md`（第 47–52 行）。
- 健康样本：`acceptance/records/2026-10-10-lizard2-v3-first-eval.md`（四带非足 fraction 全 0）。
- 判分器语义：`ablation_harness/baseline_metrics.py::_gate_non_foot_carrier_v1`（先跨部位 `any`、再判 dwell）。

## 未覆盖边界

1. **未训练策略不是"拖地爬"**：它给的是冲击载荷；真拖地工况可能给出持续部分承重，本样本没有覆盖。
2. **单次采样、单 seed**；`fraction` 用体重 708.3 N 归一，体重取自同一帧记录。
3. **探针不留可判帧**：`baseline_probe.py --head-press` 的力读数无法直接套判分器语义（它的帧不进
   `baseline_frames`），所以第 ④.3 条那条路径需要先解决"落帧"，本记录只指出它。
4. **本记录不改任何阈值**：`fraction = 0.05` / `sustain_s = 0.5` 保持协议现值；
   档位样本补齐后再决定是另一件事（协议升版）。
