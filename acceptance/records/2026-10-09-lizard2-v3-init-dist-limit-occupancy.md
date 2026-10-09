# lizard2 v3 初始动作分布下的贴限位占比（2026-10-09）

## 适用范围

问的是：**actor 自己的初始分布（t=0）把关节压到止档上的频率**。这是
`work/active/joint-limit-shape-and-range-pass.md` 里"控制余量改按**同工况贴限位占比**判"那条判据的
**训练前可用版本** —— 训练前没有 checkpoint，`gait_probe.py` 那套跑不了，所以驱动源换成分布本身。
不改资产/配方/限位、不训练、不冻结/tag。

被读对象：`Lizard2-Flat-v3`（train 任务，DR 开），16 envs，1000 个站点帧/dwell。

## 验收条件

- **驱动源** = `σ·N(0,1)` 逐通道，`σ` 从 runner cfg 读（`actor.distribution_cfg.init_std` = 1.0，
  与 `action_range_check.py` 同一个叶子）；目标由 **env 自己的动作项**变成位置目标，回读
  `data.joint_pos_target`，不从 yaml 重算。
- **样本保持 `dwell` 个控制帧后重抽**：真 policy 是时间相关的，dwell 是这个读数的敏感参数，
  所以给 1 / 4 / 20 帧（0.02 / 0.08 / 0.40 s）三档，而不是一个任意值。
- **贴限位** = `min(|q − low|, |high − q|) < 0.01 rad`，取 **solver 侧硬限位** `data.joint_pos_limits`
  （与 `gait_probe.py:629` 同一表达式）。软限位与硬限位在本资产**全部 30 关节上都不同**，报告里同时
  打印这一事实，读的是硬限位——求解器真正顶住关节的那道。
- **`pressed`** = 贴限位 **且** 目标仍在限位之外：把"被命令压住"和"路过蹭一下"分开。
- **只统计站点帧**：复位帧、以及机体低于该 env 出生半高的帧丢掉；`episodes_ended` /
  `frames_dropped_below_half_spawn` 与每档的**独立样本数**（帧数/dwell）一并打印——hold 住的样本让
  相邻帧相关，**方差由独立样本数封顶，不由帧数**。
- **不判"该不该改"**：选出口（改 scale / 改量程 / 写成口径前提）归父事项 D3。

## 结果

1000 站点帧/dwell，pooled over 16 envs，`σ` = 1.0，seed 0（采样路径固定 ⇒ 可复读）。

| dwell [帧 / s] | 独立样本 | 任一腿通道贴限位 | 任一脊柱通道贴限位 | 单关节最坏 | 单关节最坏的 `pressed` |
|---|---|---|---|---|---|
| 1 / 0.02 | ~1008 | **0.024** | 0.178 | `lf_haa` 0.007 | 0.003 |
| 4 / 0.08 | ~250 | **0.354** | 0.222 | `rl_haa` 0.076 | 0.051 |
| 20 / 0.40 | ~50 | **0.743** | 0.410 | `rr_haa` 0.260 | 0.238 |

逐关节（只列有读数的，按 `at_stop_frac` 降）：

- **dwell 1**：`chest_pitch` 0.155（pressed 0.005）、`tail1_pitch` 0.034、`lf_haa` 0.007（0.003）、
  `rf_haa` 0.005（0.004）、`rl_haa` 0.004（0.001）、`rr_hip` 0.003（0.002）、`rr_haa` 0.002（0.000）、
  `lf_hip` 0.002（0.002）、`tail1_yaw` 0.001、`rl_hip` 0.001（0.001）、`rf_hip` 0.001（0.000）；
  `hfe` 四关节全 **0.000**。
- **dwell 4**：`chest_pitch` 0.139（0.002）、`rl_haa` 0.076（0.051）、`rf_haa` 0.071（0.044）、
  `rl_hip` 0.069（0.066）、`tail1_pitch` 0.067（0.000）、`rr_haa` 0.058（0.036）、`lf_hip` 0.049（0.046）、
  `rr_hip` 0.043（0.041）、`rf_hip` 0.040（0.038）、`lf_haa` 0.030（0.017），其余 ≤0.011。
- **dwell 20**：`rr_haa` 0.260（0.238，平均连续 11.35 帧）、`rl_hip` 0.221（0.205，17.00）、
  `rl_haa` 0.206（0.190，17.17）、`rf_haa` 0.148（0.121，8.22）、`chest_pitch` 0.137（0.011，9.79）、
  `lf_hip` 0.135（0.135，12.27）、`tail1_pitch` 0.118（0.067）、`lf_haa` 0.114（0.062）、
  `rr_hip` 0.090（0.090）、`rf_hip` 0.090（0.079）、`neck_pitch` 0.059（0.047）、`rl_hfe` 0.058（0.050）、
  `tail2_pitch` 0.057、`chest_yaw` 0.042、`tail3_pitch` 0.040，其余 ≤0.015。

**可读出的结论（只此五条）**：

1. **命令侧与 dwell 无关，且与离线表对上**：8 个 `hip`/`haa` 通道的 `target_outside_frac` 在三档下
   分别是 0.227 / 0.218 / 0.222（逐通道 0.13–0.38），与 `action_range_check.py` 离线算的 `p_out`
   **0.230** 一致。两个工具量的是同一个分布，这里没有"仿真里的分布变了"这回事——**这条是两边的交叉校验**。
2. **物理侧几乎完全由 dwell 决定**：单关节贴限位 0.7% → 8% → 13–26%，"任一腿通道贴限位" 2.4% →
   35% → 74%。20 ms 之内关节**来不及**走到止档（`dwell 1` 全表 ≤0.007）；到了 0.4 s，命中的正是
   `hip`/`haa`。⇒ 拿哪一个 dwell 当"真相"直接决定结论，所以这个读数**不带 dwell 就没有意义**。
3. **贴住的时候几乎都是"被命令压住"**：`pressed`/`at_stop` 在 `hip`/`haa` 上多为 0.7–1.0
   （dwell 20：`rr_haa` 0.238/0.260、`rf_hip` 0.079/0.090、`lf_hip` 0.135/0.135），不是蹭一下。
4. **`chest_pitch` 的高占比不是同一件事**：它三档都 ~0.14 贴 ±0.5，但 `pressed` 只有 0.002–0.011
   ⇒ 脊柱是**被重力/姿态压在止档上**（这条链带质量），不是被命令压住。四腿 `hfe` 反向：命令越界
   0.8–3.5% 却几乎从不贴限位（≤0.058）——**意图不可达 ≠ 关节真的到得了**（它要走上 ≥1.2 rad）。
5. **与旧机体的训练读数同量级，但不可混读**：2026-09-22 那次是**训练后 policy**在 2.8 m/s 档读到
   `lf_hip` 贴 +0.600 的 26.6%（见 `acceptance/records/2026-09-22-lizard2-stride-at-load.md`）；本记录
   20 帧档单关节最高 26.0%（`rr_haa`）。⇒ **初始分布已经花和训练后步态一样多的时间在髋止档上**。
   但同一套 `±0.6` + `legs_scale 0.5` 在旧机体上是训得动的，所以这是**家族既有性质**，不是 v3 回归，
   也不构成"训不了"的依据；两份读数的驱动源、机体、窗口都不同，**只作量级对照**。

**这份读数支持什么、不支持什么**：它支持"`hip`/`haa` 在初始分布下就长期停在止档，且停住时驱动仍在
往里推"。它**不能**在两条出口间选：改 `legs_scale` 只改探索铺多宽（可达集不变），改量程才改可达集，
而"腿到底需要多大行程"要 R4 的目标速度带。出口选择归父事项 D3，本记录只出读数。

## 复读命令与结果

解释器 `E:\IsaacLab\env_isaaclab\Scripts\python.exe`（本机 `paths.yaml`），从 `E:\Robot` 执行：

```bat
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" rl_exp\tools\verify\check_actuator_budget.py ^
  --task Lizard2-Flat-v3 --init-dist --json "%TEMP%\init_dist_lizard2_v3.json"
```

`INIT_DIST_MEASURED`，退出码 0（测量，不是判决）。三个 dwell 各 64 步、3.5–3.9 s（**16–18 steps/s**），
共 ~11 s 测量 + 一次 app 启动。可用 `--init-dwells` / `--init-frames` / `--init-envs` / `--init-band`
/ `--init-sigma` 改口径。本机报告落在 `%TEMP%\init_dist_lizard2_v3.json`（**机器本地，不进仓**）。

**成本这条要记**：本层第一版用 1 env、预算 = 帧数 × 20（20000 步上限）⇒ 按实测 16 steps/s，单个 dwell
要 **20 分钟以上**，三个 dwell 一个多小时。改成 16 envs（一步出 16 帧）+ 预算 ×4 后，同一读数 **20 步**。
教训是通用的：**单环境步进速率就是 ~15 steps/s，读数成本按"步数"算，帧/步才是杠杆**——把帧数当成本
估计会算错两个数量级。

## 证据引用

- 判据的来处（"控制余量按同工况贴限位占比判"）：`work/active/joint-limit-shape-and-range-pass.md`。
- 命令侧的离线表与同一把 `p_out`：`acceptance/records/2026-10-09-lizard2-v3-pretrain-sanity.md`
  （③），工具 `rl_exp/tools/verify/action_range_check.py`。
- 旧机体训练后 policy 的同名读数（量级对照）：`acceptance/records/2026-09-22-lizard2-stride-at-load.md`。
- 贴限位表达式的另一处实现（policy 驱动、需 checkpoint）与它只读 `hip`/`hfe`/`foot` 的事实：
  `rl_exp/tools/diagnose/gait_probe.py`。
- 落点代码：`rl_exp/tools/verify/check_actuator_budget.py`（`init_sigma` / `run_init_dist` / `--init-dist`）。

## 未覆盖边界

- **无 policy、无 checkpoint**：这是 t=0 分布；且 `σ` 在 rsl_rl 里是**可学参数**
  （`GaussianDistribution.std_param`，`learn_std=True`）⇒ 训练中会移动，本记录是"初始瞬态"的读数，
  不能外推到训练中/训练后。
- **与 26.6% 那条不同量**：那份是训练后 policy、2.8 m/s 档、256 envs / 20 s 的读数；驱动源、机体、
  窗口都不同，只可作量级对照。
- **dwell 是外生的**：真 policy 的动作相关时间**没有测过**，0.02–0.40 s 覆盖的是一段假设区间；本记录
  给的是三档的敏感度，不是"正确的那一档"。
- **归因不完全可分**：随机姿态由重力与接触共同决定，贴限位里混着这两种贡献；`pressed` 列能
  分开"被命令压住"的那部分，但"没被命令却被压住"这一类的**成因未查**（要接触力读数，本轮没有）。
- **半高过滤抓不住低头栽**：`dropped` 三档都是 0，而 dwell 4/20 各有 **3 次 episode 结束**——终止
  （`base_contact`/`head_contact`）可以在机体仍高于出生半高时发生，所以窗口里可能含少量栽倒帧；
  `episodes_ended` 打印出来就是为了让这件事可见。未做"接触建立时刻"作为站点判据。
- **单 seed、单任务、DR 开而未逐项剥离**；未跑 `Lizard2-Flat-Play-v3`（PLAY）；20 帧档只有 ~50 个独立
  样本，逐关节小数的方差大（报告里已打印该数）。
- **只有 22 个被命令通道**：`kfe`/`foot` 无动作通道（目标钉在零位姿态），它们出现在报告里但不属本问题。
- **不构成"该改 scale / 该改量程"的判定**，也不构成"可以开训"的判定；未做限位侧的接触力读数
  （求解器是否夹断不在本文）。
