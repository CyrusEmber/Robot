# Parkour v1 — NOTES

> 骨架（versioning.mdc §A）：目的 / 假设 / 相对上版 diff / 训练命令 / 结果回填 / 结论。
> 本版为支线首版，无上版——"相对上版 diff" 记相对家族主线 v5 的关系。

## 目的

在 lizard 上复现 Parkour in the Wild 核心范式：跑/爬/跳三专家（位置任务，
特权高程感知）→ DAgger 蒸馏成深度感知学生 → RL 微调恢复并超越专家。
切片验证管线，不含 9 技能全量与扫描地形。

## 假设

- H-A：位置任务 (r\*,ψ\*,t\*) + 防趴窝三件套可在 lizard 上稳定训练（M2 首专家验证）
- H-B：lizard 跑跳物理可行（M1.5 probe 裁决；不可行则双专家管线）
- H-C：蒸馏掉点 −10% 量级、RL 微调恢复到专家 ±5%（论文对标）
- H-D：height_scanner 特权可承载专家训练（论文 elevation map 映射）

## 相对上版 diff（vs 家族主线 v5）

- 命令：velocity → 位置任务（新 command term + S_L 判定）
- reward：v5 反划脚包 → 论文 Table 2 移植（正则数值论文初值）
- 感知：教师特权沿用，学生侧引入深度图路线（Q2 终裁前不实施）
- 训练范式：单 teacher → 多专家 + 蒸馏 + 微调三阶段
- 共用：机体/assets/DR 框架/eval harness/SplitEncoderModel/StagedCurriculumTerm

## 训练命令

```bat
python scripts\reinforcement_learning\rsl_rl\train.py --task Lizard-Parkour-Climb-v1 --max_iterations 4000 --seed 42
:: 回放
python scripts\reinforcement_learning\rsl_rl\play.py --task Lizard-Parkour-Climb-Play-v1
```

（M2 启动前需先接地形课程 term，见 PLAN §4——当前无课程，spawn 恒在最易行。）

## 结果回填

### M1 任务基建（2026-09-04，冒烟绿）

- `parkour_mdp.py`：PositionCommand（t\* 预算=重采样计时器，到达即重采样，
  地形格内夹紧）+ Table 2 全部 reward/termination 函数
- `parkour_env_cfg.py`：ParkourClimbEnvCfg（teacher 快照纪律，只继承框架基类；
  楼梯上+下同专家，v3.4 定标 0.55m 台阶；DR 全量接线）
- 任务注册 `Lizard-Parkour-Climb-v1`（+Play），runner `lizard_parkour_climb_v1`
- 冒烟（parkour_smoke.py，2 env × 20 步）：OBS (2, 278) 有限，布局
  3+3+3+26+26+26+187+4；位置命令 t\* 采样+倒计时正常，Δr 基座系，
  metrics（position_error/heading_error/success/last_outcome）全活；
  16 reward + 4 termination 项无字段错
- 离线闸门 10/10 绿（含框架 pin / DR parity / obs layout）

**实现偏差（M1 新增，相对 paper）**：
1. Torque 项用 PD 模型重构（τ = K(q\*−q) − D q̇，K/D 含 DR 真值）——implicit
   执行器下 `applied_torque` 恒零，论文力矩惩罚无源可读
2. Base acc 用 `body_com_acc_w`（fork 无 `root_lin_acc_b`）
3. 专家 proprio 无噪声（paper 专家=特权教师；噪声在 M4 学生侧引入）

**顺手发现（家族级，未处理）**：stock `mdp.joint_torques_l2` 读
`applied_torque`，对 implicit 执行器恒零——**teacher v1–v5 的 torque 惩罚
一直是死项**（框架 `applied_torque_limits` docstring 自述仅支持 explicit）。
不属本线修复范围（teacher term 红线），建议主线 reward 重开版处理。

## 结论

（待结果）
