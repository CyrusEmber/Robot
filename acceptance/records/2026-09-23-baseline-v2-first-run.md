# baseline v2 首跑：按协议 v3 判定（2026-09-23）

## 适用范围

`lizard/baseline` 线 v2 配方**首次**以冻结协议判定：`Lizard-Baseline-Flat-Play-v2` +
`ablation_harness/protocols/baseline_flat_v3.json` + `lizard_baseline_v2/2026-09-21_17-41-12/model_9999.pt`。
只回答"v3 协议判 v2 配方，结论是什么、判据有没有区分度"，**不**回答阈值数值是否最优、不回答步态质量、
不回答训练侧奖励与终止实现（归 `baseline-v2-recipe`）、不含开训启动闸门（归 `work/active/eval-protocol-before-training.md`）。

## 验收条件

1. 报告 `verdict ∈ {pass, fail}`（不是 `smoke_only`、不是 `invalid`）。
2. 两条相对门槛（跟踪、位移）与接触轴各有"能过"与"能红"两侧证据。
3. 回填 `versions/lizard/baseline/v2/NOTES.md`，并更正 `v1/NOTES.md` 结论的**口径**（不改写其原义）。

## 结果

**真跑**（16 env、seed 123、确定性、20 s 首回合；无 checkpoint 之外的覆盖参数）：

```bat
E:\IsaacLab\env_isaaclab\Scripts\python.exe ablation_harness\baseline_eval.py --headless ^
  --task Lizard-Baseline-Flat-Play-v2 --protocol ablation_harness\protocols\baseline_flat_v3.json ^
  --checkpoint E:\IsaacLab\logs\rsl_rl\lizard_baseline_v2\2026-09-21_17-41-12\model_9999.pt ^
  --num_envs 16 --seed 123 ^
  --output ablation_harness\results\baseline_flat_v3\v2-trained-9999-rerun\eval.json
```

`verdict: pass`、`invalid_reasons: []`、判分器 `legacy-baseline-threshold-keys-1`（`origin: legacy`）、
报告 `timestamp 2026-09-23T17:02:21+08:00`、`code.repository.rev = d92edc72938c`（`dirty = true`，
工作树含另一会话未提交的 `baseline_eval.py`/`baseline_frames.py`/`baseline_metrics.py` 与本报告自身）。

| 轴 | 读数 | 门槛 | 判 |
|---|---|---|---|
| 跟踪（归一 MAE） | `forward_mae_norm` 0.04451 | `< 0.2` | 过 |
| 位移 / 期望 | `displacement_frac` 0.97105（40.559 / 41.762 m） | `> 0.8` | 过 |
| 存活（`time_out` 占比） | `first_episode_timeout_fraction` 1.000 | `> 0.9` | 过 |
| 姿态 | `tilt_max_deg` 13.60 | `< 40°` 持 0.5 s | 过 |
| 非足接触 | `non_foot_contact_load_n_max` 0.0 N | `> 1 N` 即红 | 过（绿） |

诊断：`command_mps_mean` 2.0881（落在协议声明的 1–3 box 内，逐帧记录）、`lateral_speed_abs_mps` 0.0263、
`yaw_offset_abs_rad` 0.0639、`non_foot_mesh_min_z_m` +0.342。

**与磁盘上同名报告逐项相同**：`results/baseline_flat_v3/v2-trained-9999/eval.json`（2026-09-22T11:22，
旧采集器）与本次（新采集器，帧格式 2 含足端四列）在 `metrics`／`gates`／`verdict` 上**逐位一致**
（如 `displacement_frac` 两次都是 0.9710497856140137）。两份都保留：旧份是同一 rollout 在旧采集器下的读数，
本次是**当前采集器下可引用的一份**。同 checkout 的独立判定也复现过同一个 `pass`
（`acceptance/records/2026-09-23-baseline-frames-format-2-foot-reading.md` 的"同一 rollout 结论不变"）。

**区分度（两侧证据）**

| 样本 | `forward_mae_norm` | `displacement_frac` | 结论 |
|---|---|---|---|
| 零动作、同一命令 box（`results/baseline_flat_v3/v2-recipe-smoke/eval.json`） | 0.99888 | 0.00095 | 两条相对门槛**都红**；`verdict: smoke_only`（无 checkpoint ⇒ 明确不是策略结论） |
| 随机 checkpoint（`results/baseline_flat_v2/collector-check-random/eval.json`，v2 协议口径） | — | — | `verdict: fail`，跟踪与位移两条红 |
| **本记录**（训练 9999 iter） | 0.04451 | 0.97105 | 两条相对门槛都绿 |

接触轴：绿侧 = 本记录 0 N；红侧 = 合成回归 `test_v3_keeps_the_two_samples_apart`（把 87.2 N 放进一份
v3 形状的记录）。v1 那份拖颈记录**不能在 v3 下复判**——它的命令恒 0.5 m/s，落在 v3 的 1–3 m/s box 之外 ⇒
判定器返 `invalid`（`test_a_record_is_refused_under_a_protocol_it_was_not_collected_for`），**其原义不变**。

**两处声明在本次真跑的配置快照里成立**（不是探针复测）：报告自带的 `env_cfg.actions` 只有
`joint_pos_legs`（`.*_haa_joint`／`.*_hfe_joint`／`.*_kfe_joint`）与 `joint_pos_spine`
（`chest_.*`／`neck_.*`／`tail[0-9]_.*`）两项 ⇒ **22 维动作、脚关节无动作权**。
`baseline_probe.py` 的 v2 接口复测（命令落区间并逐 env 采样、22 维、脚关节无动作权三条断言）**未做**。

**照实写的两处缺口**

1. 存活与姿态两条门槛在**本线的真跑样本里只有绿侧**：两个随机/零动作样本都是 `tilt 33.74° / 13.60°`（< 40°）、
   存活满窗。红侧本轮补在**判据级**：`test_baseline_contract.py::test_v3_the_two_axes_no_sample_ever_exercised_can_still_fail`
   （永不复位 ⇒ 存活红；压过 `cos 40°` 持 0.6 s ⇒ 姿态红）。**补之前**这两个 gate 在本仓没有一条断言
   （grep `["gates"]["attitude"]` / `["gates"]["survival"]` 无 `False` 比较）⇒ "只有绿侧"既是样本的事实，也是测试的事实。
2. 训练侧记录**半截**（`manifest --verify` ⇒ 3 条 BLOCKING）：`pre_make` 与 `ready_to_learn` 两处记录都失败于
   `AttributeError: 'NoneType' object has no attribute 'strip'`，`stages` 只有 `env_constructed`，
   六项声明全是 `declared None`（`num_envs` 4096 / `seed` 42 / `params_version` v2 等）。
   ⇒ **checkpoint 没有 repo rev 与配方摘要的锚**，本记录只锚定评测侧。该失败消息与
   `acceptance/records/2026-09-23-git-output-encoding.md` 复现的**同一形状**，但成因未在本记录内判定；
   训练侧记录归 `work/active/baseline-pre-make-record-check.md`。

## 证据引用

- 报告与帧记录：`ablation_harness/results/baseline_flat_v3/v2-trained-9999-rerun/eval.json`
  （+ 同目录 `eval.frames.pt`，`*.pt` 不入库、本地可复判）；离线复判命令
  `python -m ablation_harness.baseline_metrics <record> --protocol ablation_harness\protocols\baseline_flat_v3.json`。
- checkpoint：`lizard_baseline_v2/2026-09-21_17-41-12/model_9999.pt`，
  `sha256:3aa910f7cd3d1ddfbfeef00a00e01842d052d4ef6388104c7121ad4ecdbbc7c7`（1777269 B）。
- 对照读数：`results/baseline_flat_v3/v2-recipe-smoke/eval.json`（零动作）、
  `results/baseline_flat_v2/collector-check-random/eval.json`（随机 ckpt）、
  `results/baseline_flat_v1/v1/Lizard-Baseline-Flat-v1_5850_deterministic_seed123_rev2a07c88/eval.json`（v1 口径）。
- 协议：`ablation_harness/protocols/baseline_flat_v3.json`（本次报告记录的 `protocol_digest` 为 `sha256:a288b898…`）。
- 判定器与回归：`ablation_harness/baseline_metrics.py`、`rl_exp/tools/verify/test_baseline_contract.py`。

## 未覆盖边界

1. **单 seed、单 checkpoint、单次 16-env 首回合**；`pass` 的含义只到"不倒、方向对、位移对、无头链触地"，
   不含步态质量（`foot_slip_mps` 等只作诊断，本协议没有一条判据读它们）。
2. 阈值 0.2 / 0.8 / 1 N / 0.766 的来源与选取理由在协议文件的 `why_v3`，本记录只验证**区分度**，不验证取值最优。
3. 评测时的 `dirty = true`：脏项是另一会话在改的三个 `ablation_harness` 文件与本报告目录；`rev = d92edc7`
   可用 `git checkout d92edc7` 复原，但**那三个文件在提交点与工作树不一致**，所以本次复现锚在采集器上弱于
   v1 那次（v1 记录里逐位核过同名文件）。
4. 不覆盖训练侧（奖励/终止实现、记录半截的成因）、不覆盖启动闸门、不覆盖 `lizard2` 家族与其它线。
