# baseline/v2 结果

> 骨架（versioning.mdc §A）：目的 / 假设 / 相对上版 diff / 训练命令 / 结果回填 / 结论。
> 配方与验收定义见 [PLAN.md](PLAN.md)；线路线见 [../PLAN.md](../PLAN.md)。上版结论见 [../v1/NOTES.md](../v1/NOTES.md)。

## 目的

同线第二版：只加三个变量——命令窗口 `1.0–3.0 m/s`（框架 10 s 重采样）、脚板关节失去动作权限
（动作 26 → 22 维）、头链触地终止（`chest_.*`/`neck_.*` 竖直反力 > 1 N 即终止，dwell 0）。假设与判据见 PLAN.md。

## 假设

1. 若 v1 的失败主要是"捷径不被计价"，堵掉脚板捷径 + 打开速度窗口后，失败应表现为**够不到 3 m/s**
   或**姿态/触地再次越界**，而不是"完全不动"。
2. 若换成"够不到"，则说明瓶颈在动力学/资产而不是奖励口径——那属于资产线，不是本线再加变量能回答的。

## 相对上版 diff

逐项见 PLAN.md 的 diff 表。一句话：命令从定点变区间、动作组去掉 `.*_foot_joint`，**其余逐项照 v1**。
配方元素列表与 v1 相同，差异全部落在 `baseline_params.yaml`。

## 开训前实测

**未做**（本版 2026-09-21 开训，早于本次 2026-09-23 回填；`baseline-v2-recipe` 的 `close_when` 要求"跳过就写明"）：
`baseline_probe.py` 的 v2 接口复测——命令落在区间且逐 env 采样、动作 22 维、脚关节无动作权——没有探针读数。
旁证只有两条快照级证据：配方 `action` 段的声明，以及首跑报告自带的 `env_cfg.actions`
（两项 `joint_pos_legs`／`joint_pos_spine`、合计 22 维、无 `.*_foot_joint`），见首跑记录。
**验收协议冻结在前**：`baseline_flat_v3.json` 在开训前入库，**闸门**（无协议即拒绝开训）后补，见 PLAN.md §验收。

## 训练命令

**计划**

```bat
python scripts\reinforcement_learning\rsl_rl\train.py --task Lizard-Baseline-Flat-v2 --num_envs 4096
```

**实跑**：`logs/rsl_rl/lizard_baseline_v2/2026-09-21_17-41-12`（相对 IsaacLab 根，根由 `paths.yaml` 解析）。
同名 run 有两个（`17-28-13`、`17-41-12`）⇒ 只写实验名指向的是目录、不是那一次。

**这一次的记录是半截的，照实写**：`manifest --verify` 报 3 条 BLOCKING —— `pre_make`／`ready_to_learn`
两处记录都失败于 `AttributeError: 'NoneType' object has no attribute 'strip'`，`stages` 只到 `env_constructed`，
六项声明全为 `declared None`（实跑值 `num_envs` 4096 / `seed` 42 / `params_version` v2）。
⇒ **checkpoint 没有 repo rev 与配方摘要的锚**，本版结果的复现锚只到评测侧报告自带的那行 provenance。
训练侧记录归 `work/active/baseline-pre-make-record-check.md`；成因未判定。

## 结果回填

读数只有一个家：`acceptance/records/2026-09-23-baseline-v2-first-run.md`（含逐轴读数、两侧区分度与缺口）。

| 项 | 值 |
|---|---|
| run 目录 | `logs/rsl_rl/lizard_baseline_v2/2026-09-21_17-41-12`（记录半截，见上节） |
| checkpoint | `model_9999.pt`（本机该目录） |
| 评测报告 | `ablation_harness/results/baseline_flat_v3/v2-trained-9999-rerun/eval.json`（16 env、seed 123、确定性、20 s 首回合） |
| 复读命令 | `python -m ablation_harness.baseline_metrics <报告同目录记录> --protocol ablation_harness\protocols\baseline_flat_v3.json` |
| 判定 | `verdict: pass`：跟踪、位移、存活、姿态、非足接触五轴全过（逐轴读数与两侧样本见记录） |
| 训练期曲线 | 同目录 `tb_scalars.csv`（抽样入库） |

**作废/并存的一份**：`results/baseline_flat_v3/v2-trained-9999/eval.json`（2026-09-22 旧采集器）是同一 rollout
的早期读数，与本次逐位相同，保留不改写；引用以本次为准。

## 结论

**回答本版的问题：能。** 命令区间 `1.0–3.0 m/s`、去脚板动作权、头链触地终止三条变量下，训练 9999 iter
的策略在冻结协议 v3 的**五条门槛上全过**，且两条相对门槛（跟踪、位移）有两侧证据——同一命令 box 的零动作
样本两条都红，随机 checkpoint 判 `fail`，本策略两条都绿。头链触地轴 0 N：**不是** v1 那种拖颈蹭行。

**结论的边界（照实写）**：单 seed、单 checkpoint、单次 16-env 首回合；`pass` 只到"不倒、方向对、位移对、
无头链触地"，**不证明会走路**（脚滑/离地等只作诊断）；训练侧记录半截 ⇒ 结果只锚在评测侧；
存活与姿态两条门槛在本线样本里只有绿侧。
