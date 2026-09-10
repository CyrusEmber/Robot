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

## 结果回填

（待训）

## 结论

（待训）
