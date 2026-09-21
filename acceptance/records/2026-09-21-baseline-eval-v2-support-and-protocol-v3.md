# 验收器对训练 v2 的支持与协议 v3（相对门槛 / 接触轴 / 命令 box）

## 适用范围

本记录判定的是 **`lizard/baseline` 固定窗口验收器能否验收本线的 v2 配方**，以及为此冻结的
协议 `baseline_flat_v3.json` 的口径。

- 对象：`ablation_harness/protocols/baseline_flat_v3.json`（新）、`ablation_harness/baseline_eval.py`
  （`--protocol` 入参、recipe 绑定、命令 box 校验）、`ablation_harness/baseline_metrics.py`
  （相对门槛、接触轴、命令 box 与窗口长度校验）、`rl_exp/tools/verify/test_baseline_contract.py`。
- 真跑：`Lizard-Baseline-Flat-Play-v2` + `--protocol baseline_flat_v3.json`，16 env、seed 123、
  **零动作**（无 checkpoint）⇒ 只是一次**管路验证**，不是 v2 的性能结论。
- 起因（前一份报告的事实更正）：`ablation_harness/results/baseline_flat_v2/collector-check/eval.json`
  的任务是 `...-Play-v1`、checkpoint 是 `lizard_baseline_v1/.../model_5850.pt` ⇒ 那份 "pass" 判的是
  **v1 策略**；而当时验收器根本判不了 v2。
- **不外推**：不覆盖其他线、不覆盖奖励、不覆盖阈值是否最优。

## 验收条件

1. 入口按**协议声明的 `recipe_version`** 绑定配方：v1/v2 协议声明缺省 `v1`，v3 声明 `v2`；
   不匹配即拒，报错同时点名协议与 task。
2. 命令按协议声明的**box**采集与校验（v1/v2 的定点是退化 box），逐帧记录实际下发命令；
   记录里的命令越界 ⇒ `invalid`（记录属于别的协议），不是判分。
3. v2 计划书里那两条**相对**门槛落地：跟踪用逐帧 `|v_fwd − v_cmd| / v_cmd` 的窗口均值，
   位移用 `实际位移 / Σ(v_cmd·dt)`，分母恒为完整 20 s。
4. 头链轴与训练终止**同判据**：非足 body 任一帧竖直反力 > 1 N 即红；非足网格最低 z 降为诊断。
5. 阈值**不由"把旧样本判红"反推**：v1 拖颈记录是**异常回归样本**，零动作是**正常样本**，
   两侧只用来验证判据的区分度，不参与取值。

## 结果

**条件 1–4 已成立，条件 5 已按此执行。**

| 项 | 实测 |
|---|---|
| v2 配方被接受 | 同一命令跑通：动作 **22 维**、终止项 3 条（含 `head_load_contact`）、奖励 7 项 |
| 命令是区间 | 记录里 `command_mps_mean` **2.088**（落在 1–3 内，逐帧记录） |
| 相对位移分母 | `expected_displacement_m` **41.76**（≈2.09 m/s × 20 s） |
| 相对门槛按预期判红 | 零动作策略：`forward_mae_norm` **0.999**、`displacement_frac` **0.0009** ⇒ 两条相对门槛都不过 |
| 接触轴 | 零动作：非足接触 **0 N**、网格最低 **+0.54 m** ⇒ 绿 |
| 结论 | `verdict: "smoke_only"`（无 checkpoint ⇒ 明确不是策略结论），`eval.json` + `eval.frames.pt` 落盘 |

**协议 v3 的三条轴**：相对跟踪（`forward_mae_norm_lt: 0.2`）、相对位移（`displacement_frac_gt: 0.8`）、
接触（`non_foot_contact_load_n_gt: 1.0`，与训练终止/`base_contact` 同值）；姿态沿用仓库先例
（tilt 40°/0.5 s）；存活 > 0.9；非足网格与逐脚量只报告。两条相对门槛的形态与 v2 `PLAN.md`
§验收 的表述一致（阈值本身仍是"本版新定、待首跑验证区分度"）。

**一个必须说清的后果**：v1 那份拖颈记录**不能在 v3 下复判**——它是恒定 0.5 m/s 采的，落在 v3 的
1–3 m/s box 之外，判定器会返回 `invalid`（`test_a_record_is_refused_under_a_protocol_it_was_not_collected_for`
就是这个行为）。所以"接触轴能把拖颈样本判红"这条回归是**合成记录**（把 87.2 N 放进一份 v3 形状的记录，
见 `test_v3_keeps_the_two_samples_apart`），而 v1 记录本身仍只在 v1/v2 口径下有判定——它的原义不变。

## 证据引用

- 协议：`ablation_harness/protocols/baseline_flat_v3.json`（`command` box、`recipe_version`、两条相对门槛、
  接触轴、`why_v3` 逐条写下来源与反例）。
- 代码：`baseline_metrics.command_box` / `_command_reasons` / `_contract_reasons` / `judge`（相对与接触分支）、
  `baseline_eval.run`（`--protocol`、recipe 绑定、box 校验）、`baseline_eval.main`（失败先打印栈再关 app）。
- 回归（新增 6 条，均在 `test_baseline_contract.py`，离线套件 `[22]` 内）：
  `test_window_length_must_equal_the_protocol_window`、
  `test_the_initial_state_is_checked_for_shape_and_finiteness`、
  `test_a_record_is_refused_under_a_protocol_it_was_not_collected_for`、
  `test_v3_normalized_tracking_scores_the_band_not_one_number`、
  `test_v3_displacement_is_measured_against_the_distance_asked_for`、
  `test_v3_head_chain_contact_is_the_training_termination_criterion`、
  `test_v3_keeps_the_two_samples_apart`。
- 真跑：`ablation_harness/results/baseline_flat_v3/v2-recipe-smoke/eval.json`（+ `.frames.pt`）。
- 套件：47/47 `ALL_OFFLINE_CHECKS_PASSED`。

## 未覆盖边界

- **没有 v2 的性能结论**：v2 未开训，零动作跑只证明管路通。首跑后用 v3 出报告并回填
  `versions/lizard/baseline/v2/NOTES.md`，届时才谈"是否学会"。
- **阈值仍待首跑验证区分度**：`0.2 / 0.8 / 1 N / 0.766` 里前两个是本版新定、无仓库先例；本记录只证明
  判据能被执行、能被拒绝、能给出三态结论，不证明它们的数值选得对。
- **开训前闸门未接**：本记录没有让"协议不存在或摘要不符 ⇒ 拒绝开训"生效，那归
  `work/active/eval-protocol-before-training.md`；在该闸门接通前，v3 的冻结只是文件层面的事实。
- 单 seed、单资产；不覆盖训练侧奖励与终止的实现细节（那是 `baseline-v2-recipe` 的范围）。
