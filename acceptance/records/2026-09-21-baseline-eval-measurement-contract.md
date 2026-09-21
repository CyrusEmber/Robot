# baseline 固定窗口验收器：测量可信性与"谁在决定结论"

## 适用范围

本记录判定的是 **`lizard/baseline` 固定窗口验收器产出的数字是否可信**，以及由此暴露的
"验收口径 vs 开训前探针口径"两把尺子问题。

- 对象：`ablation_harness/baseline_frames.py`（新，采集契约）、`ablation_harness/baseline_metrics.py`
  （改写为纯判定）、`ablation_harness/baseline_eval.py`（只做仿真侧采集）、
  `rl_exp/tools/diagnose/diag_metrics.py`（补点云修复）、
  `rl_exp/tools/verify/test_baseline_contract.py`。
- 被验策略：`logs/rsl_rl/lizard_baseline_v1/2026-09-20_12-23-09/model_5850.pt`（首跑 5850/15000 iter），
  外加三份对照样本：零动作、`model_0.pt`（未训练）、`model_0.pt` + `--policy_mode sampled`（64 env）。
- 运行环境：真实 Kit、16 env（随机样本 64 env）、seed 123、`Lizard-Baseline-Flat-Play-v1`、
  协议 `baseline_flat_v2.json`（判定侧另用 `baseline_flat_v1.json` 复判同一记录）。
- **不外推**：不覆盖其他线、不覆盖训练侧、不覆盖阈值是否恰当（阈值见"未覆盖边界"）。

## 验收条件

1. 采集与判定分离：同一 rollout 落一份带单位、形状、轴标（哪个 body／哪只脚）的逐帧记录；
   判定是这份记录的纯函数，改协议复判**不得重跑物理**。
2. 结论三态：`invalid`（崩溃、缺测、非有限值、契约不满足 ⇒ 不得判策略好坏）/ `fail` / `pass`；
   门上的量**未测即无效**，不是通过。
3. 数值正确性可当场取证：多 env 不串、接触计数能累计、首个回合之后的帧不进任何门槛、
   必测值有限。
4. 量与诊断器独立读数一致（同一函数、同一参考系）。
5. 不得把观测到的读数直接写成允许阈值。

## 结果

**验收器已可信（条件 1–4）。** 20 秒窗口在真实 Kit 上跑完，进程正常退出，落盘
`eval.json` + `eval.frames.pt`（`ablation_harness/results/baseline_flat_v2/collector-check/`）。

| 量 | 本验收器（16 env，1000 帧） | 诊断器独立读数（上一轮，64 env） |
|---|---|---|
| 前向 MAE | **0.01976** m/s | 0.0199 m/s（v1 报告） |
| 位移 | **+9.459** m | +9.456 m（v1 报告） |
| 姿态最差 | **26.18°** | 26.2–26.7° |
| head/neck/tail 合力 | **87.2** N | 87.3 N |
| 非足网格最低 z | **−4.63 mm**（`neck_pitch`） | −5 mm |
| 逐脚 duty | **0.000 / 0.231 / 0.694 / 0.714** | 0.002 / 0.31–0.37 / 0.74 / 0.68 |

**修掉的六处度量缺陷**（全部实测，非读码推断）：

| 缺陷 | 实测 | 后果 |
|---|---|---|
| 载荷被所有 env 平均成 `(B,)` | 1-D 上 `.max(dim=1)` → `IndexError` | v2 协议下采集必炸、无报告 |
| 载荷 / 脚 duty 用 bool 相加 | `True + True` 仍是 `True` | duty 只可能 0 或 1 |
| 点云补 `+inf` 再旋转 | `mesh_min_z` 对较窄网格返回 **NaN** | 网格门槛 NaN ⇒ 判不明（验收器与诊断器共用该函数，故"诊断器跑得通"不能背书） |
| tilt 取**最大** cosine | 保留最正的一帧 | 报告的最差姿态朝错方向 |
| `mesh_min_z` 门槛无 `alive` 掩码 | 重生回合的帧进门 | 门槛读别的回合 |
| 未喂 tilt 时 `_require` 永不触发 | `tilt_violation` 恒有长度 | 门倾角而没采集时静默通过 |
| （外加）`feet_down_mean` | 老实现把逐帧脚数再除以有效帧数 | 实测 0.05，正确值 1.0 |

**"原生崩溃、无异常栈"不成立（重要更正）**：异常一直到达了 Python，吞掉它的是 `app.close()` ——
Kit 关闭时直接结束进程，解释器来不及打印栈。证据：把同一次 `run()` 包进显式 `except`，立刻得到完整
`RuntimeError: The size of tensor a (23) must match the size of tensor b (16) at non-singleton dimension 2`；
而 `-X faulthandler` 全程**没有原生栈**（不是段错误）。此前两次读到的"无异常栈"，是"没有把栈打出来"，
不是"没有异常"（前两次的异常是：载荷被平均成 1-D 后的 `IndexError`；判定侧 cuda/cpu 设备混用）。
**已修**：`main()` 在 `finally: app.close()` 之前先打印栈并 flush ⇒ 失败不再表现为静默退出。

**另补四项记录校验（评审提出，此前缺失）**：

| 校验 | 不满足时的行为 |
|---|---|
| `steps × step_dt` 必须等于协议窗口 | `invalid`：`the window is 20 steps x 0.04 s = 0.8 s, but the protocol declares 20 s` |
| `start_pos` 形状 `(N,3)`、`start_yaw` 形状 `(N,)`、两者有限 | `invalid`，逐项点名 |
| `body_weight_n` 存在且为正 | `invalid`（没有体重就换不出牛顿） |
| 逐帧命令落在协议声明的 box 内 | `invalid`：记录属于另一个协议 |

回归：`test_window_length_must_equal_the_protocol_window`、
`test_the_initial_state_is_checked_for_shape_and_finiteness`、
`test_a_record_is_refused_under_a_protocol_it_was_not_collected_for`。

**三态结论与离线复判可用（条件 1、2）**：同一份记录不重跑物理地判两遍协议——

| 协议 | 判定 | 说明 |
|---|---|---|
| `baseline_flat_v1` | `pass`（3/3） | v1 只读速度/位移/存活 ⇒ 拖颈蹭行照过 |
| `baseline_flat_v2` | `pass`（6/6） | **判的是 v1 策略**，与训练 v2 无关（见下） |

**归属必须写清**：这份报告的任务是 `Lizard-Baseline-Flat-Play-v1`、checkpoint 是
`lizard_baseline_v1/.../model_5850.pt` ⇒ 它说的只是"**v1 策略**在 v2 口径下通过"。它**不是**关于
训练 v2 的结论（v2 尚未开训），也不是 v2 协议能否胜任的结论——那份协议当时还判不了 v2
（入口拒绝 `params_version != "v1"`、采集要求命令恒为 0.5 m/s、判定只有绝对门槛）。
v2 口径已由 v3 取代，见 `2026-09-21-baseline-eval-v2-support-and-protocol-v3.md`。

其余真跑样本：零动作 = `smoke_only`（脚 duty 0.987–0.991、非足载荷 0 N、网格最低 +0.54 m ——
"正常样本"）；`model_0.pt` = `fail`；`model_0.pt`+sampled（64 env）= `fail`。
五份记录全部 `verdict ∈ {pass, fail, smoke_only}`，**没有一次 `invalid`**（即必测值全有限）。

**v2 判 pass 的原因（实测，不是猜测）**：`neck_pitch` 全窗时均法向力 **87.2 N**（体重 706.3 N 的
12.3%），**66.2%** 的帧超过 10% 体重阈值，但**最长连续超阈只有 0.22 s** ⇒ 败给 0.5 s 持续判据；
网格 −4.63 mm ⇒ 大于 −0.01 m 允许值。两个门槛都比**开训前探针**的口径更弱：

| 量 | 探针（开训前标准） | 验收 v2 | 本跑 |
|---|---|---|---|
| 非足承重 | 逐 body **全窗时均 > 1 N** ⇒ 红 | ≥10% 体重**连续** 0.5 s | 87.2 N ⇒ 探针红、v2 过 |
| 非足网格 | 逐帧 **> 0** | > −0.01 m | −4.63 mm ⇒ 探针红、v2 过 |

64 env 随机样本进一步说明允许值不是无害的：`neck_pitch` −7.7 mm、`tail3_pitch` −4.1 mm
仍判 `pass`。⇒ 这正是本轮起点说的"两套工具、两把尺子"。

**未采纳的建议（留待拍板）**：把验收门槛改读探针的原口径（`body_load_n` 时均 > 1 N；网格 > 0），
即"一把尺子"。支持证据两侧都有：正常样本（零动作）0 N / +0.54 m 通过；异常样本（拖颈策略）
87.2 N / −4.6 mm、随机策略 −7.7 mm 判红。**本记录不擅自改阈值**——阈值属协议内容，
`-0.01 m` 是上一轮按"求解器稳态穿插"校准出来的，正是条件 5 禁止的动作。

## 证据引用

- 代码：`ablation_harness/baseline_frames.py`（`COLUMNS` / `REQUIRED_META` / `BaselineFrames.add`）、
  `ablation_harness/baseline_metrics.py`（`judge` / `_contract_reasons` / `_data_reasons` / `_alive`）、
  `ablation_harness/baseline_eval.py`、`rl_exp/tools/diagnose/diag_metrics.py`（`pad_point_clouds`）。
- 回归：`rl_exp/tools/verify/test_baseline_contract.py`（逐 env 载荷、duty 累计、重生帧掩码、非有限即
  `invalid`、轴标不符即 `invalid`、未测即拒答、补点不动最小值、逐帧命令）——16 项 + acceptance metrics 5 项。
- 真跑记录：`ablation_harness/results/baseline_flat_v2/collector-check/eval.json`（+ `.frames.pt`，
  sha256 `0264ebde…`）、`.../collector-check-zero/eval.json`、`.../collector-check-untrained/eval.json`、
  `.../collector-check-sampled/eval.json`、`.../collector-check-random/eval.json`。
- 离线复判入口：`python -m ablation_harness.baseline_metrics <record> --protocol <协议>`。
- 离线套件：47/47 `ALL_OFFLINE_CHECKS_PASSED`。

## 未覆盖边界

- **没有一条真实"早终止"记录**：五个样本里每个 env 都活满 1000 帧（该 Play 任务的提前终止项是
  基座接触，这些策略都没触发）。因此"重生帧不进门槛"只有离线回归作证据；真跑只证到
  **终止帧替换**（最后一步 16/64 次复位被捕获，零动作位移 0.039 m 而非重生跳变）。
- **阈值是否恰当未判**：本记录只证明"测量可信、结论可复算"，`no_non_foot_carrier` 与
  `no_mesh_through_floor` 该用哪套口径（探针口径 or 现有口径）留给拍板；改口径后 v1 历史记录
  保持原义、不重打标签。
- 归因腿（接触点切向速度、地面与自碰分离、切向力方向）未做，见 `floor-contact-attribution`。
- 单资产、单线、单 seed；不覆盖训练侧口径与奖励。
