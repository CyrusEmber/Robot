# lizard2 v1 评测协议冻结（硬前置 1，2026-09-22）

## 适用范围

- 落点：`ablation_harness/protocols/lizard2_flat_v1.json`（新协议）、`ablation_harness/baseline_metrics.py`
  （新增四个 kind + 闸门 + judge 绑定 + 未决 gate 判否）、`ablation_harness/judge_semantics.json`
  （新 judge id 的冻结块）、`rl_exp/tools/verify/test_baseline_contract.py`（fixture + 5 条行为单测 + 13 条反例）。
- **不覆盖**：开训前置里的**启动闸门**（"协议不存在或摘要不符 ⇒ 拒绝开训"）未建，见末节；
  也不覆盖 `baseline_eval.py` 的"固定评测命令覆盖"（本协议的逐带判据隐含要求它，见末节）。

## 验收条件

1. 协议不许借旧线：命令区间、判据种类、阈值、逐帧实际下发命令，全部写在本文件里。
2. 四个新种类**各自带反例**（仓规：非平凡逻辑要留一条能挂掉的检查），且新语义挂到**新 judge id**。
3. 判据声明必须**全被判决**：声明的 gate 若没有任何 `decide` 调用，不许算过。
4. 逐带全过才算过（含零命令带），且报告每带帧数与读数。
5. 阈值不得贴着历史故障值选；`non_foot_carrier_v1` 的 `fraction`/`sustain_s` 定死并给标定依据。

## 结果

**协议**：`Lizard2-Flat-v1` v1，`judge: baseline-criteria-banded-1`，命令箱 `lin_vel_x [0,3]`、
`resample_s 10`、`episode_length_s 20`、plane。八条轴：`tracking_banded_v1`、`displacement_banded_v1`、
`survival_v1`、`sustained_tilt_v1`、`non_foot_contact_v1`、`non_foot_carrier_v1`、`non_foot_load_sum_v1`、
`gait_swing_v1`。带为 `[[0,0.1],[0.1,1.0],[1.0,2.0],[2.0,3.0]]`——**零命令带是声明出来的带**，不是特例；
每带 `[lo,hi)`、最高带闭在上界，于是"命令恰好等于声明上界"不会掉出所有带；掉出的帧算**声明漏洞**并判否。

**四个新 kind 的语义**（都进 `CRITERION_KINDS`，各带 `columns`，闸门读没测过的列会被既有契约拒）：

- `tracking_banded_v1 {threshold 0.25, floor_mps 0.5, zero_band_mps 0.1, zero_abs_mps 0.15, bands}`：
  带内读 `mean |v_fwd−v_cmd| / max(v_cmd, floor_mps)`；零命令带读 `max |v_fwd|`，只在 `alive` 帧上；
  **失败后帧在相对带里记 1.0**（提前停下继续被计）。空带 = 没测到 = 不是过。
- `displacement_banded_v1 {threshold 0.8, zero_band_mps 0.1, zero_abs_m 0.3, bands}`：**先按带求和再相除**；
  分子只算 `alive` 帧的逐帧前向增量（不是位置差，复位跳变进不来），**分母含失败后帧的命令**。
- `non_foot_load_sum_v1 {fraction_sum 0.08, sustain_s 0.5}`：逐帧把全部非足 body 竖直载荷**求和**再判持续。
- `gait_swing_v1 {min_swing_feet 2, min_air_time_s 0.1, min_landing_load 0.05, band_mps 0.5}`：
  摆动 = 该脚连续不承重；要满足时长 **且** 落地帧恢复承重；只在被要求移动的帧上判，**只在被要求移动的 env 上判**
  （命令为 0 的 env 不算步态失败），整窗没让任何 env 移动则判否（没测到 ≠ 过）。

**两处与 PLAN 正文的偏离**（都在此明写，不藏在代码里）：

1. **`min_lift_m` 去掉**。PLAN 表里写了它，但记录里**没有足端高度列**（只有 `foot_contact`/`foot_fraction`），
   而"闸门不许读没测过的量"是本模块反复出现的规则 ⇒ 要么加记录列（改采集器），要么去掉该参数。
   本版去掉；要离地高度须先给记录加列。落地恢复承重那条改由 `min_landing_load` 承担。
2. **`min_swing_feet 2` 是本次会话填的数**，PLAN 说它是"产品验收要求，由所有者冻结"。**待你确认**：
   记录里的 4 只脚，2 只 = 半数（小跑式有腾空期）。改成别的数只需改协议文件 + 重钉该 id 的摘要（kind 不变）。

**两个阈值的标定依据**（PLAN 要求：不得贴着历史故障值，须给正常/异常样本）：

- `no_non_foot_carrier.fraction = 0.05`、`sustain_s = 0.5`：正常样本 = 启动探针的零动作 40 步（非足载荷
  **0.00 N**，载荷全在四足）；异常样本 = 压头实验（下巴承 1108 N > 1 倍体重 ⇒ 分数 > 1.0）；
  退役线实测故障量级 11.6–12.8% 体重。0.05 取在"正常 ≈ 0"与"故障 0.116"之间、**不贴故障值**。
  **缺口**：缺"持续部分承重"这一档样本（介于 0 与 1.0 之间），未测。
- `no_non_foot_load_sum.fraction_sum = 0.08`：设计理由而非拟合——单部位门槛 0.05 之下，两个 0.04 的部位
  合计 0.08 ⇒ 正好落在总量门槛上被判否，而单部位判据看不见它们（反例 `load_sum_two_bodies_under_the_fraction_still_fail`）。

**顺手修掉的洞（重要）**：`_score` 里 `passed = {}` 起手 + `verdict = all(passed.values())` ⇒
**协议声明了但没有任何 `decide` 调用的 gate 对判决完全不可见**（`gait`、`no_non_foot_load_sum` 一开就中招）。
改为 `passed` 从 `plan` 起手（未决 = `None`），收尾发现未决即判 `invalid` 并说明。
另外 `_score`/`_data_reasons` 里两处 `tracking[1]["normalized"]`/`displacement[...]["normalized"]` 是按旧 kind 的
参数集写的，新 kind 没有该参数 ⇒ 已按 kind 收窄（否则一带带 kind 就 KeyError）。

## 证据引用

- 反例与冻结：`test_baseline_contract.py`（`BASELINE_CONTRACT_OK`，13 条新 case + 5 条行为单测）；
  `judge_semantics.json` 的 `baseline-criteria-banded-1` 块（`kinds_sha256` b1e9046f…、`frozen_sha256` 15484281…）。
- 摘要重算：`python rl_exp\tools\verify\test_baseline_contract.py --print-frozen`。
- 离线套件：`ALL_OFFLINE_CHECKS_PASSED (47/47)`。
- 落点：PLAN 硬前置 1、`work/active/lizard2-family-landing.md`。

## 未覆盖边界

- **启动闸门未建**：PLAN 硬前置 1 还要求"协议不存在或摘要不符 ⇒ 拒绝开训"，该闸门**今天不存在**
  （`manifest.begin` 的拒绝集只有 lifecycle 与脏树）。形态与落点写在
  `work/active/eval-protocol-before-training.md`（它把 `manifest.begin` 列为落点），本记录不重复设计。
  ⇒ 在此之前，"协议被冻结"靠**离线契约测试 + 评审**保证，而不是靠开训闸门。
- **固定评测命令覆盖未做**：逐带判据要求每个带在 `alive` 帧上被覆盖到，而 `baseline_eval.py` 现在用的是
  环境自己的 10 s 重采样 —— 单个 env 的 20 s 窗可能只落到一两个带。4096 env 一起看，各带覆盖率高，
  但**零命令带（< 0.1 m/s）依赖采样**；要稳，评测器需按固定基命令序列下命令。属 PLAN「固定窗口」那段
  列出的后续动作，本记录只把依赖写清。
- **`fraction` 的第三档标定样本（持续部分承重）未测**，见上。
- 旧线的四个协议与既有 id 未被本改动触碰（`baseline-criteria-1` 的 `kinds_sha256` 与 `frozen_sha256` 均不变，
  因为冻结按 id **列出的** kind 子集哈希，加 kind 不动它）。
