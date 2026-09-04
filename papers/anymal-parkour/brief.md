# ANYmal Parkour — Brief

**ANYmal Parkour: Learning Agile Navigation for Quadrupedal Robots** | 2023 arXiv / Science Robotics 2024 | [arXiv:2306.14874](https://arxiv.org/abs/2306.14874) | ETH Zürich RSL（David Hoeller*, Nikita Rudin*, Dhionis Sako, Marco Hutter）

> 对本仓的特殊地位：**Parkour in the Wild 的专家训练真源**——其补充材料 Table S2 就是专家 reward 表，正文 IV-B2 是专家训练配置。

## 一句话概括

五技能 locomotion 专家（walk/jump/climb up/climb down/crouch，位置任务）+ 高层导航 policy（选技能+发中间指令）+ 3D 场景重建感知模块，三模块各自仿真训练、真机部署，ANYmal D 以 2 m/s 过连续障碍。

## 要点

- **专家 = 位置任务 (r\*, ψ\*, t\*) + Table S2 reward + 对称增广**；技能间共享 obs/action 空间，reward/termination 各有 flavor
- **Table S2 关键结构**：跟踪项带 𝟙_{t\*<1} 末秒门控 + **Move in direction cos⟨v_b, r\*−r⟩（approach 稠密激励）** + Stumble（横向足力>2×垂直）+ 终止罚（base 碰撞 + 足力>1500N，−200）——与 Parkour in the Wild 微调表（Table 2）相差这三项 + 终止罚形式
- **地形配比**：Walk = 60% stairs + 20% slopes + 20% random obstacles；专精技能 = 80% 对应障碍 + 20% random rough
- **Per-skill 定制**：climb down 加足部冲击终止（防跳下伤机）；climb up 降 base/knee 碰撞罚（允许用膝）；jump/crouch 各有障碍参数课程
- **对称增广（S3）**：transition 镜像扩样 + 原动作 log-prob 复制到镜像变体（解决 Abdolhosseini 2019 复制法的 off-policy 收敛问题）

## 优点

- 完整可复现配方在正文+补充材料（S1 表格化 obs/reward/action，S2/S3 实现细节），是 parkour 类工作的配方基准
- 涌现行为有记录：climb down 膝钩挂边、jump 三腿起跳一腿伸出、跨技能能力复用（jump 技能原地转向最快被导航利用）
- 手工轨迹对比（Table I）：导航 policy 胜人工放点 96–98% vs 61–95%，证明高层不是摆设

## 缺点与局限

- 八个网络分别调参、模块间耦合（感知 latent 换了导航要重训）——作者自述训练耗时、扩展性存疑（正是 Parkour in the Wild 要解决的）
- 导航收敛难，需专门课程，否则卡在大障碍前
- 场景限于 pallet-box 障碍排列（3 种场景类型），复杂场景泛化未验证

## 方法对比（论文内）

- vs 手工轨迹放点（1000 rollouts）：98.2/96.3/97.6% vs 95.3/60.9/75.3%——精细控制场景人工放点崩
- 高层 action space 消融（S6）：去 heading 掉 3–9%（窄道多次原地转场景），去 timer 掉 2–7%（长赛道需变速）

## 结果

- 真机 ANYmal D 55kg：2 m/s 跨连续障碍，爬 1.15m 箱（导航自动改道）、0.9m 平台（电机满扭矩）、0.8m 窄箱精确落点（比训练箱小一半 OOD）
- 专家各自地形 90% 训练难度内成功率 ≥90%（Fig. 4F）
- 训练：Isaac Gym 4096 agents，感知数据 Warp CUDA 核（~1.4 亿射线/步），感知训练 45GB 显存

## 极简 Input / Output / 实现

- `Input:` 专家 = proprio（v_b/ω_b/g_b/q/q̇）+ (r\*,t\*,ψ\*) + h 2m×1m 高程图（训练期加扰：点噪声+全图平移≤7.5cm）；导航 = 全局目标 + 感知 latent
- `Output:` 专家 = 关节位置命令 50Hz；导航 = (技能选择 categorical + r\*/t\*/ψ\* Gaussian) 5Hz 混合输出
- `实现:` PPO（导航版改造 hybrid actor）；Isaac Gym 4096 envs

## 与当前 SOTA 的对比

- **被 Parkour in the Wild（2025）直接超越**：其自证分层技能切换在 5→9 技能扩展时失效（高层弃用部分专家），改多专家蒸馏+RL 微调；但 Parkour in the Wild 不含导航/全局规划层——长程导航仍归本作的分层方案
- 专家配方（Table S2 + 位置任务 + 对称增广）被 Parkour in the Wild 全盘继承为 stage 1——本论文作为"专家怎么训"的真源价值不变
- 感知模块（多分辨率体素重建）在后续被深度图直驱路线（Parkour in the Wild 学生）部分替代；长时序遮挡记忆的重建思路仍被沿用
- 对称增广的正式化版本：Mittal et al. ICRA 2024（arXiv:2403.04359），实现进 leggedrobotics/rsl_rl
