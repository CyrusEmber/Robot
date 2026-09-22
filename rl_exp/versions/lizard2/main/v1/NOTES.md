# main/v1 结果

> 骨架落位 2026-09-22，由 `rl_exp/tools/pipeline/declare_family.py` 生成（versioning.mdc §A 必含骨架：
> 设计的引用 / 本版重点变化 / 实际执行与偏离 / 结果回填 / 结论）。
> 配方与验收定义见 [PLAN.md](PLAN.md)。

## 设计的引用

目的与假设见 [PLAN.md](PLAN.md)（不复制判据）。开训前的状态：**未开训**——
`PLAN.md` 的三条硬前置（本线评测协议冻结、启动探针按 30 维动作/102 维观测/区间命令复测、落地姿态目视）
尚未完成，因此本文件暂只有骨架与已成立的离线事实。

已成立的离线事实（训练前就该有的，全部有记录）：

- 资产与家族落成：`acceptance/records/2026-09-22-lizard2-family-landing.md`（30 关节、逐位可证的资产差异、
  锁隔离、注册）
- 承重行程与动作覆盖：`acceptance/records/2026-09-22-lizard2-stride-at-load.md`（四腿髋 0.546–0.558 m、
  动作 30/30、obs 102 实测批准）
- obs 协议与实测关节序：`versions/obs_protocols.json` 的 `Lizard2-Flat-v1` / `-Play-v1`（协议
  `a25a8c39001b`）、`versions/joint_order_runtime.json` 的 `assets/lizard2/lizard2.usda`

## 本版重点变化（阅读提示，≤2 句）

换骨骼（四条腿根部各加一条竖直轴 `hip`，30 关节）并把命令从定点 0.5 打开到区间 0–2 m/s；
其余（平地、无课程、无 DR、7 项奖励、基座接触终止、PPO 超参）逐项照旧线 baseline v1 冻结值。
完整差异与逐项理由以 [diff.json](diff.json) 为准，本提示**不作完整性承诺**。

## 实际执行与偏离

未开训。实跑后必须写 run 目录路径 `logs/rsl_rl/lizard2_v1/<时间戳>`——同一 `experiment_name` 下会有
多次 run，缺时间戳指向的是目录、不是那一次。命令行 / 覆盖参数 / seed / checkpoint 的正文留在该目录的
`run_manifest.json` / `checkpoints.json`（记录本体机器本地、不进仓）⇒ 这里只给路径 + 复读命令。
偏离计划的地方照实写；run 记录不完整就写明缺什么、结果凭什么锚住。

## 结果回填

| 项 | 值 |
|---|---|
| run id | 未开训 |
| checkpoint | 未开训 |
| 评测报告 | 未开训（本线评测协议待冻结，见 PLAN「验收」硬前置 1） |
| 分类判定 | 未开训 |

## 结论

未开训，无结论。结论的边界届时照实写：几个 seed、几个 checkpoint、有无 DR、以及
`PLAN.md`「风险与挂账」第 1 条的归因边界（本版只到"新构型 + 本配方"，不能单独归因于骨骼修正）。
