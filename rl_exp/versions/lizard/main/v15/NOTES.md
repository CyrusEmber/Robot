# v15 NOTES —— joint SIR 地形课程（参数格 combo × 速度桶），base = v14

> **已取消（2026-09-22）**：用户因机体设计缺陷退役整个 lizard 家族，本提案未冻结、未实施、未训练。以下设计与命令保留为历史，不再是开训安排；证据边界见 `acceptance/records/2026-09-22-lizard-family-retirement.md`。

- 目的/假设: v5 行 SIR 只调难度行、类型维度不可调（v14 的 `terrain_levels` 全程
  3.7–5.3 微动、eval 侧 gap_40cm completion 0.109 vs 其余 0.78–0.91）。v15 假设：
  把**类型内部**的参数档做成课程轴（每 combo 一个单值 sub-terrain）+ 命令按速度桶取样，
  课程即可把流量从过不去的组合上挪开，并给出可判读的课程信号。
  **类型份额固定、不跨类型**（v15.3 起不再承诺"自动转移类型流量"）。
- 相对 v14 的 diff: ① terrain_generator → `build_param_grid_terrain_cfg`
  （58 combos / 4×120）② commands → `ParticleVelocityCommand`（buckets 0.5…3.0 + jitter 0.1）
  ③ curriculum → `terrain_levels=None` + `joint_sir` ④ yaml 加 `v15` 段。
  obs / action / 奖励 / 终止 / DR / 资产**逐字段零差异**。方案 SSOT = `v15\PLAN.md`。
- 训练命令:
  `python scripts\reinforcement_learning\rsl_rl\train.py --task Lizard-Rough-v15 --max_iterations 15000 --seed 42`

## 预注册闸（判读口径，冻结前定稿）

1. **不劣化**：Locomotion-Eval-v2 `nominal` seed 123 vs v14 同条件 —— `lin_mae_mps` /
   `success_rate` / `fall_rate` / `terrain_completion_mean` 四项并列报告；
   **禁止只报 fall**（v14 教训：`fall_rate` 在难 suite 上连 flat 都饱和到 1.0）。
   命令口径已变（离散步点 vs 连续 U(0,3)），与 v5–v14 的跟踪数字**不得同表**。
2. **课程活性**：`Curriculum/joint_sir/tr_mean` 进带 [0.5,0.9] 且有爬升或 `particle_entropy`
   下降 = 课程在工作；`frontier_max_v` 现为 **verified 量**（已结算 + 估计 ≥ band 下限的桶，
   见 PLAN「处置」）⇒ 可读作能力前沿的**候选**，但必须并列样本量；`sampled_max_v` 才是冷启动即
   3.0 的那个量，**不得当能力**。`tr_mean < 0.05` 且 `entropy` 不降 = 全失败态
   （权重全零 → 当前粒子群内均匀 → 局部游走，**不会自己下探**）→ 人工介入。
3. **v15.3 评分口径（必须先于读数确认）**：`Tr` 分母 = **固定观察窗口 `W`**，不是实际存活步数
   ⇒ 提前失败按未达标计入剩余帧；逐帧标签 = **yaw 帧**跟踪误差 `‖vel_yaw_xy − cmd_xy‖ ≤
   track_tol_mps`（实际含 jitter 的指令），不是 `v_pr > 0.2`；出被分配 combo 列块的帧记未达标
   （`W` 与掩蔽方案见 PLAN「评分修正」/「待拍板 1」）。**未经此口径读数一律不进结论**。
4. **短局/翻覆交互**：`W` 固定后短局不再自动提分（分母不再缩短），但翻覆仍改变剩余帧构成
   ⇒ 结论必须并列 `completion` 与逐地形 `fall_rate`，并回答"是否存在短局命中带内却持续吃流量
   的组合"（v15 继承 v14 roll_over 闸，本项必测）。
5. **首跑声明**：joint SIR 从未真训（v11 仅 6-iter 冒烟、v12 无 run）→ v11/v12
   **不作基线**，本版结果不与它们对表。
6. **并行迁移约束**（运行期红线）：开训前打 tag；进程不得重启/续训；
   训练结束前不得 `cfg_lock --update`。违反任一条，本次 run 的"可重建"声明作废。

## 结果回填

（未训练）

## 结论

（训练后补）
