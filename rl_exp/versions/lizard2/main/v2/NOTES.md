# main/v2 结果

> 骨架落位 2026-09-28（versioning.mdc §A 必含骨架：设计的引用 / 本版重点变化 / 实际执行与偏离 /
> 结果回填 / 结论）。配方与验收定义见 [PLAN.md](PLAN.md)。

## 设计的引用

目的、假设与判据见 [PLAN.md](PLAN.md)（不复制）。本版由 v1 复制而来，唯一变化是脚板动作权限；
完整差异与逐项理由以 [diff.json](diff.json) 为准。

开训前的状态与前置：

- 建版与注册：`versions/lizard2/main/v2/` 六件 + `LIZARD2_RECIPES["v2"]` + 两个任务 id + `Lizard2V2PPORunnerCfg`；
  取证见 `acceptance/records/2026-09-28-lizard2-v2-startup-contract.md`。
- 观测协议（动作维度变化连带）：任务层 `dims_by_task`（同一协议同一资产、两个动作接口 ⇒ 两个宽度），
  既有批准不迁移；同记录。
- 启动契约探针：两个 v2 id 均 `BASELINE_PROBE_OK`（未声明关节无通道、**未命令关节目标恒等默认 0.000e+00 rad**、
  维度 = 声明集）；同记录。
- 两个任务 id 的 golden：配方锁重基线见 `acceptance/records/2026-09-28-lizard2-v2-cfg-lock-rebaseline.md`。

## 本版重点变化（阅读提示，≤2 句）

脚板四个关节交出动作通道（30 → 26 维），保留 v1 的增益、默认平放目标与上限；本轮读数是**只有实验臂**的
读数，无对照臂、单 seed，且实跑预算与 cfg 声明不一致（见"实际执行与偏离"）。

## 实际执行与偏离

- run：`logs/rsl_rl/lizard2_v2/2026-09-28_17-02-42`（命令行、覆盖参数与 checkpoint 明细在该目录的
  `run_manifest.json` / `checkpoints.json`；复读见记录）
- 偏离：
  1. **实跑 10000 迭代，cfg 声明 14000**（`Lizard2V2PPORunnerCfg.max_iterations`；run 的 `params/agent.yaml`
     与 manifest 记 10000，末档 `model_9999`）⇒ 覆盖来源未记进 argv，PLAN 里那条"两臂同预算"不靠 cfg 成立。
  2. seed 42 与 PLAN 一致；无其它 CLI 覆盖。
  3. 评测协议不是 PLAN 里预期的那份文件：现有 `lizard2_flat_v2.json` 钉 recipe v1，评估器拒判 v2
     ⇒ 新建 `ablation_harness/protocols/lizard2_flat_v3.json`（身份新、判据逐块相同，机器可查）并锚进
     `protocol_anchors.json`。

## 结果回填

| 项 | 值 |
|---|---|
| run id | `2026-09-28_17-02-42`（10000 迭代、4096 envs、seed 42） |
| checkpoint | `model_9999.pt`（该 run 目录的 `checkpoints.json` 里有 sha256） |
| 评测报告 | `ablation_harness/results/lizard2_flat_v3/v2/Lizard2-Flat-v2_9999_deterministic_seed123/eval.json`（协议 `lizard2_flat_v3.json`，reader `baseline-criteria-banded-settled-1`，256 envs / seed 123 / 20 s） |
| 对照臂 | **无**——本轮只评实验臂 |
| 训练读数 | 曲线落点 = 本目录 `tb_scalars.csv`（全量 `.full.csv` 留机器本地）；读法 `dump_tb.py` / `plot_tb.py`，巡检 `probe_run.py --exp lizard2_v2`；**收敛读数**归 `acceptance/records/2026-09-29-lizard2-v2-eval.md` |
| 分类判定 | 判决 **fail**（八条过六条，两条都倒在零命令带）；机制读数见同记录 ⇒ 见"结论" |

## 结论

- **能成立**：本版在冻结协议下 fail，且失败面收窄到零命令带的速度与漂移两条；相对带的跟踪与位移全过。
  去权限后脚板目标整个窗口恒为默认平放位、实际只被顶开 ≤0.249 rad ⇒ 无命令下 PD 仍把脚板钉住。
  脚板不再整段饱和（12 格中 11 格饱和帧占比 0.00）⇒ "拿掉一个饱和执行器导致步态变差"这条反向假设
  在本读数里没有证据。腿不吃紧（hip/hfe 稳态 p50 最高 0.43 倍上限）。
- **不成立**：把本轮的差异归因于"取消脚板权限"——没有对照臂，任何跨臂说法都不成立；"本版训满了"
  也不成立（曲线到 10000 仍在收紧）。
- **边界**：单 run / 单 seed / 单 checkpoint；探针 3 envs；力矩是重构值、饱和帧上按 clamp 推上界；
  脚碰撞 hull 换代发生在 v1 训练之后；预算 10000 vs 声明 14000。逐条见记录。
