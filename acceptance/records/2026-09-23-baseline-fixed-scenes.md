# baseline 定点场景：命令由评测器驱动，覆盖率可读（2026-09-23）

## 适用范围

`ablation_harness/components/command_player.py`（按 env 的场景分配与命令块）、
`ablation_harness/baseline_eval.py`（读协议 `scenes`、冻结重采样、逐步注入、条件入帧 meta）、
`ablation_harness/baseline_metrics.py`（同表核对 + 逐场景有效帧）。
只回答"命令是不是评测器按协议给的、每个声明的带是否真被测量"，不回答阈值与协议版本（归家族项）。

## 验收条件

1. 注入落到**每个 env 各自**的命令上，而不是把一条命令广播给全部 env。
2. 环境自身的重采样不得覆盖评测命令，且该条件随记录保存。
3. 每个声明的场景都要有有效帧；空带与"帧数很少"要能分辨。
4. 同一 rollout 的采集条件、格式身份与判据能在报告里对上。

## 结果

两次真跑（`Lizard2-Flat-Play-v1` + 冻结 `lizard2_flat_v2.json` **加上** `scenes` 块 + `model_13999.pt`，
16 envs、seed 123、20 s = 1000 帧），协议文件是临时副本（冻结文件未改）。

- **按带对齐的场景**（`0.05 / 0.5 / 1.5 / 2.5` m/s）：`verdict = pass`，八条闸门全过；
  逐场景有效帧 **4000 / 4000 / 4000 / 4000**（4 envs × 1000 帧）；
  逐带跟踪误差 0.0112 / 0.0405 / 0.0095 / 0.0059 m/s，位移比 0.008 / 0.968 / 1.008 / 1.002。
- **未对齐的场景**（`0 / 1 / 2 / 3` m/s）：`verdict = fail`，判据点名 **`0.1-1mps measured nothing`**；
  四个场景本身各 4000 帧 ⇒ 这不是策略读不到，而是**场景集与协议声明的带不匹配**。
  两次的差别只在这一处 ⇒ 该读数可归因。
- **注入落到每个 env**：`_scene_reasons` 用"记录里该 env 每帧发出的命令"对"分配的场景"，
  两次真跑皆 `invalid_reasons = []`；把广播式注入（同一条命令给全部 env）做进反例后该检查红。
- **条件随记录保存**：帧 meta 的 `scenes` = 声明、逐 env 分配（16 项）、`resampling_frozen: true`、seed；
  报告侧 `diagnostics.scene_valid_frames` 给出逐场景有效帧。
- 冻结重采样沿用 `dr_controller.apply_eval_mode` 的同一组设置（`heading_command`、`rel_standing_envs`、
  `rel_heading_envs`、`resampling_time_range = 1e9`），只在协议声明 `scenes` 时施加。

## 证据引用

- 报告与帧记录：`%TEMP%\baseline_eval_p0_probe\scenes\`（未对齐）与 `scenes_bands\`（对齐）各一份
  `eval.json` + `eval.frames.pt`；`*.pt` 不入库，本地可复判。
- 临时协议：同目录 `scenes_v2.json`、`scenes_bands.json`（由冻结 v2 复制加 `scenes` 块，报告里带其摘要）。
- 真跑命令：`<isaaclab python> ablation_harness\baseline_eval.py --headless --task Lizard2-Flat-Play-v1
  --protocol <上述临时协议> --checkpoint E:\IsaacLab\logs\rsl_rl\lizard2_v1\2026-09-22_19-26-50\model_13999.pt
  --num_envs 16 --seed 123 --output <...>\eval.json`
- 离线回归：`rl_exp/tools/verify/test_baseline_contract.py` 的六条场景测试（覆盖/去相关/逐 env 命令块/
  缺分配/空带/命令不一致/逐场景帧数）。

## 未覆盖边界

1. 场景是**常量命令**：一条按时间变化的场景序列需要扩 `CommandPlayer`，本轮未做（没有协议声明它）。
2. 未做 256-env 与"重采样 vs 定点"的对照读数；本记录不声称定点场景比训练分布更优或更差。
3. 策略在固定 3 m/s 下能否长时间保持，本轮只有 16 env 的读数，不构成对策略的结论。
4. 采集条件只进帧 meta：帧记录不是 `record.json`，它没有另一处能放这组条件。
