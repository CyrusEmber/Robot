# Advanced Skills (Rudin 2022a) — Brief

**Advanced Skills by Learning Locomotion and Local Navigation End-to-End** | IROS 2022 | [arXiv:2209.12827](https://arxiv.org/abs/2209.12827) | ETH Zürich RSL（Nikita Rudin, David Hoeller, Marko Bjelonic, Marco Hutter）

> 对本仓的特殊地位：**Parkour in the Wild 位置任务的原始定义**（论文 2.1 引用的 Rudin et al. 2022a 即此篇）；ANYmal Parkour 的 Table S2 是它的演化版。

## 一句话概括

把局部导航+locomotion 端到端化：不跟踪速度指令，只要求在给定时间内到达目标位置——任务 reward 只在 episode 末段（T_r=1s）激活的**时间稀疏**形式，释放全部解空间，涌现三相位步态/跳沟/膝钩爬坑/绕障，难度全面超速度跟踪基线（gap 1.2m vs 0.15m）。

## 要点

- **任务形式**（原始版）：指令 = 基座系目标位置（3D）+ 剩余时间；episode T=6s，任务 reward 仅在最后 T_r=1s 激活：r_task = (1/T_r)·1/(1+‖x_b−x\*_b‖²)（逆平方，非 ANYmal S2 的线性 1−0.5‖·‖）
- **T_r 的意义**：必须长到逼 policy 在目标处稳定停下，否则学到"最后一刻扑向目标"（真机无 episode reset 会摔）
- **探索偏置 r_bias** = cos⟨v_b, x\*−x⟩——即 ANYmal S2 的 Move in direction；**原文自动退火**（r_task 达最大值 50% 后移除），不约束最终解
- **Stalling 罚**：−1 当 ‖v‖<0.1 m/s 且距目标>0.5m——**距离门控**（ANYmal S2 的 Don't wait 是其无门控演化）
- **训练稳定性三件套**（时间稀疏 reward 的代价，critic 难预测、换 seed 就崩）：①批加倍（4096 env × 48 steps = 200k 样本/迭代）②**episode 缩短 20s→6s** ③**去掉 value bootstrapping**（任务时限已知且是 actor/critic 输入，有限视界无需 bootstrap）
- **目标采样**：极坐标均匀，半径 1–5m，目标高 z=+0.5m，无效目标（坑/高障碍内）重采样；成功判据 0.5m
- **已知 artifact**：policy 只学一个行走方向（每次训练随机固定，转头代替侧走/倒走）——ANYmal 加 ψ\* 朝向指令 + Mittal 对称增广都是对着这个打的

## 优点

- 任务定义范式转变的干净论证：层级化 reward（先解任务，再自由优化动作质量），任务与正则解耦，调参不需妥协
- 对比实验完整（速度跟踪/连续位置/末段位置三任务同地形），难度表量化（Table I）
- 能耗更低 + 步态自然（无 air-time/clearance reward 需求），真机部署含伪速度控制（固定目标 3m 前方 + 恒定时间值 = 摇杆速度控制）

## 缺点与局限

- 训练不稳定敏感（论文自述，靠三件套压制）
- 单方向行走 artifact（局部最优极强）
- 依赖状态估计与感知模块（跳/爬场景不适配，爬坑部署需动捕）

## 方法对比（论文内）

- vs 速度跟踪（95% 成功率最大难度）：stairs 0.4 vs 0.2m、slope 48° vs 35°、gap 1.2 vs 0.15m、pit 0.95 vs 0.1m、障碍 0.85 vs 0.35m
- vs 连续位置跟踪（r_task 每步给）：全面次优 + 障碍地形完全失败（"越快越好"偏置 = bang-bang 系）
- 能耗（Στ²/距离）：低速域显著优于速度跟踪（trot 约束税），高速域收敛

## 结果

- 2000 iters ≈ 1h 训练；真机：0.6m gap 跳跃、0.55m 箱攀爬（膝钩）、楼梯高速、绕障
- 三相位不对称步态（后腿-中对角-前腿），斜向运动（运动学/电机布置的最优方向）

## 极简 Input / Output / 实现

- `Input:` proprio（q, q̇, v_b, ω_b, 上步动作）+ 指令（基座系 3D 目标 + 剩余时间）+ 地形采样；观测加传感器级噪声
- `Output:` 12 关节位置目标（PD 跟踪）
- `实现:` PPO + Isaac Gym 4096 envs（Learning-to-walk-in-minutes 框架）；执行器网络 + 速度相关力矩限幅

## 与当前 SOTA 的对比

- 任务定义被 ANYmal Parkour（S2 线性化 + ψ\* 朝向指令 + 恒定 direction 项）和 Parkour in the Wild（继承 S2）沿用——**位置任务范式本身仍是这条线的标准**
- 单方向 artifact 的两条修复线：ψ\* 指令（ANYmal）+ 对称增广（Mittal 2024，实测 climb 任务 return 17.46 vs 15.54、等效目标差异 0.124 vs 1.022）
- 稳定性三件套（短 episode/大 batch/去 bootstrap）是该任务形式的标配前提，后续论文默认继承不再显式讨论
