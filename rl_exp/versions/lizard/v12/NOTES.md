# v12 NOTES — Miki S8 复位/观测鲁棒性包

> 方案与决策见 [PLAN.md](PLAN.md)；本文件只回填训练事实。骨架按
> versioning.mdc §A（目的/假设/diff/命令/结果/结论）。

## 目的

补齐对照 Miki et al. 2022 S8 审计的三处缺口（关节初始随机、摩擦偶发
调低、高度环噪声——teacher 侧，无蒸馏），并把基座 reset 范围搬进 yaml；
r_slip 回 −0.003。

## 假设

1. 噪声+复位随机不会压死 joint SIR 课程（v11 未训，v12 首跑即合训）。
2. ±0.2 rad 腿部初始偏置 + 软限位 clamp 足够温和，不产生地形穿插出生。
3. σ 档位（0.15/0.05/0.02 m）在 0.10–0.35 m 地形幅度尺度下可学。

## 相对上版 diff（v11 → v12）

- 代码：`teacher_mdp.py` v12 段（sample_ring_noise / NoisyFootRing /
  FootFrictionDipTerm）；`teacher_env_cfg.py` V12(+PLAY)；注册
  Lizard-Rough-v12；runner v12；DR 名单两侧 +2；三处校验器扩展；
  test_v12_noise.py。
- yaml：v12 段（reset_randomization / height_noise）+ v5.r_slip.weight
  → −0.003。其余逐字同 v11。
- obs 契约不变：90/208/83 = 381（extero func 换实现，名/序/维度不动）。

## 训练命令

```bash
python scripts\reinforcement_learning\rsl_rl\train.py --task Lizard-Rough-v12
```

experiment：`lizard_rough_teacher_v12`。开训前：地形预检 + smoke。

### 续训（2026-09-11 起）

`--resume` = 真续训：课程状态随 checkpoint 存取（`rl_exp/tasks/curriculum_state.py`）
——joint SIR 的粒子/权重/跨块计数器/回放池/`env_pair`/`desired_vel` +
`common_step_counter`（c_k 时钟）。恢复点在 wrapper 首次 reset **之前**，所以第一个
episode 就落在恢复后的粒子与 c_k 上（不是先冷跑一段）。

- 旧语义（只加载权重、c_k 回热、SIR 冷启动）需显式 `--resume --weights_only`
- joint SIR 任务对**无课程状态的老 checkpoint** 用 `--resume` 会**硬中断**并提示该 flag
  （静默降级正是要消灭的失败模式；该功能落地前产出的 checkpoint 属于此列）
- 指纹不符（yaml 改过地形网格 / 速度桶 / 任务身份）同样硬中断，不冒险误读 pair 索引
- 不做逐位复现：不存 RNG，恢复后首块粒子重抽样序列不同，但分布/统计/时钟连续
- 接线落在家族 runbook 入口 `scripts\reinforcement_learning\rsl_rl\train.py`（wrapper 前
  apply + runner 构造后 save hook 两行）。若将来迁到统一入口 `train_rsl_rl.py`，这两行必须
  一并搬过去，否则续训会静默退回冷启动

判读：恢复后再跑 ≥200 iters，`Curriculum/joint_sir/*` 与 reward 曲线在边界不得有台阶；
对照实验 = 同一 ckpt 加 `--weights_only` 冷启动，两条曲线应能明显区分。

## 结果回填

（待训）

## 结论

（待训）
