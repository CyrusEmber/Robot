# main/v1 结果

> 骨架落位 2026-09-22，由 `rl_exp/tools/pipeline/declare_family.py` 生成（versioning.mdc §A 必含骨架：
> 设计的引用 / 本版重点变化 / 实际执行与偏离 / 结果回填 / 结论）。
> 配方与验收定义见 [PLAN.md](PLAN.md)。

## 设计的引用

目的与假设见 [PLAN.md](PLAN.md)（不复制判据）。开训前状态：三条硬前置里**启动探针与落地目视已完成**、
**评测协议已冻结**，但 PLAN 要求的"协议缺失/摘要不符 ⇒ 拒绝开训"**启动闸门仍未建**（形态归
`work/active/eval-protocol-before-training.md`）——2026-09-22 的开训是在该闸门缺失下按所有者决定启动的。

已成立的离线事实（训练前就该有的，全部有记录）：

- 资产与家族落成：`acceptance/records/2026-09-22-lizard2-family-landing.md`（30 关节、逐位可证的资产差异、
  锁隔离、注册）
- 承重行程与动作覆盖：`acceptance/records/2026-09-22-lizard2-stride-at-load.md`（四腿髋 0.546–0.558 m、
  动作 30/30、obs 102 实测批准）
- obs 协议与实测关节序：`versions/obs_protocols.json` 的 `Lizard2-Flat-v1` / `-Play-v1`（协议
  `a25a8c39001b`）、`versions/joint_order_runtime.json` 的 `assets/lizard2/lizard2.usda`
- 评测协议冻结：`acceptance/records/2026-09-22-lizard2-eval-protocol-freeze.md`（v1），判决后的修订见 v2

## 本版重点变化（阅读提示，≤2 句）

换骨骼（四条腿根部各加一条竖直轴 `hip`，30 关节）并把命令从定点 0.5 打开到区间 0–2 m/s；
其余（平地、无课程、无 DR、7 项奖励、基座接触终止、PPO 超参）逐项照旧线 baseline v1 冻结值。
完整差异与逐项理由以 [diff.json](diff.json) 为准，本提示**不作完整性承诺**。

## 实际执行与偏离

- run：`logs/rsl_rl/lizard2_v1/2026-09-22_19-26-50`（4096 envs、seed 42、`--max_iterations 14000`、
  `save_interval 50`）。命令行与覆盖参数留在该目录的 `run_manifest.json` / `checkpoints.json`
  （记录本体机器本地、不进仓）⇒ 这里只给路径 + 复读命令。
- **偏离 1（记账）**：`max_iterations` 实跑 **14000**，而本线 runner cfg（`Lizard2PPORunnerCfg`，逐项照
  baseline v2）声明 10000 ⇒ 本 run 的迭代预算不是配方声明的那个数。
- **偏离 2（启动记录不完整）**：该 run 的 `run_manifest.json` T0 `declaration` **为空**，`after_env`
  因此报 5 条 `declared None != actual`（`num_envs` 4096、`sim_dt` 0.005、`control_dt` 0.02、`seed` 42、
  `params_version v1`）；查旧线 `lizard_baseline_v2` 的 run 同样如此 ⇒ 本机所有 run 的既有状态、
  非本次启动特有，但**该 run 的声明面因此不可读**。
- **偏离 3（判据交付不完整）**：PLAN 验收节的步态判据要求 `min_lift_m`（离地高度），交付的两种 K
  **没有实现该项**；`report_only` 另声明了无人计算的 `foot_slip_mps`/`foot_yaw_deg`/
  `dof_torque_frac_of_limit` **3 项**（2026-09-23 更正：初版写"等 6 项"，其中 `foot_duty`/
  `foot_load_fraction`/`feet_down_mean` 其实已算）。见"结论"与
  `acceptance/records/2026-09-23-lizard2-v1-gait-skate.md`。
- 评测在训练**之后**做（协议先冻结、判决后修订一次），过程与两处尺子缺陷见
  `acceptance/records/2026-09-23-lizard2-v1-first-eval.md`。

## 结果回填

| 项 | 值 |
|---|---|
| run id | `logs/rsl_rl/lizard2_v1/2026-09-22_19-26-50`（14000/14000、4096 envs、seed 42；`manifest --verify` 的缺口见"实际执行与偏离"偏离 2） |
| checkpoint | `model_13999.pt`（sha256 与全量参数见该 run 目录的 `checkpoints.json`） |
| 评测报告 | `ablation_harness/results/lizard2_flat_v2/v1/Lizard2-Flat-v1_13999_deterministic_seed123/eval.json`（**pass**，八条全过）；无 settle 读者的 v1 判决与被取代的中间报告在同根目录下并列保存 |
| 训练读数 | 见 run 目录的 tfevents（巡检入口 `rl_exp/tools/trainlog/probe_run.py --exp lizard2_v1`）；数值的书面家见下"结论"引用的两份记录 |
| 分类判定 | **未定**：判据侧 `pass`，步态实测**不合格**（v2 探针同 run 补测：摆动贴地 + 承重接触点滑移；成因已分开为"低速是目标层命令的、高速是执行器跟踪、lf 目标要求入地"）⇒ 按"能力基线"记账，**不按"会走路"记账**（判定依据见两份记录） |

## 结论

- **能成立**：新构型在平地 0–3 m/s 区间上不倒、不趴、不把非足部位当支撑、方向与位移对。
- **不成立**：**步态质量不合格**。目视症状（踮脚、不迈腿、不抬腿）成立；同日的 v2 探针把四个量在同一次
  run 里补测，并按一阶正运动学把**目标角映射成脚底高度**，成因因此分开：**低速档的贴地是目标层命令的**
  （摆动最高帧的目标净空只有毫米级），**高速档的剩余差是执行器跟踪**（再按"目标是否可达"分解，见记录 ⑦），
  且高速档的**关节目标系统性越限**、其来源是**动作接口无界**（策略头无输出激活 + `clip_actions: null` +
  动作项无 `clip`）；"没发动作"与"执行器是低速主因"都不成立。**lf（左前）那条异常已降级为待验证**
  （左右关节目标是镜像的，符号翻转来自预测的转动项，见记录 ⑦ 第 8 条）。可确认的两侧缺口：奖励侧删了
  `feet_slide`/`foot_clearance`（旧线预注册的取舍，现已到期），判据侧把 PLAN 验收要求的 `min_lift_m`
  丢了 ⇒ 八条判据没有一条能看见它。**数值、更正明细与仍未答的问题（策略为何学到这个目标，属奖励侧）
  不复述，见 `acceptance/records/2026-09-23-lizard2-v1-gait-skate.md`**；判决侧的另一半见
  `acceptance/records/2026-09-23-lizard2-v1-first-eval.md`。
- **边界**：1 个 seed、1 颗检查点、无 DR、无课程；`pass` 与"垫着滑"同出一份 20 s 窗口，故本版只能归因到
  "新构型 + 本配方"，不能把步态问题归因于骨骼修正。
