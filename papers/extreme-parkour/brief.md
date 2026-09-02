# Extreme Parkour with Legged Robots — Brief

**Extreme Parkour with Legged Robots** | ICRA 2024 | [arXiv:2309.14341](https://arxiv.org/abs/2309.14341) | CMU（Xuxin Cheng*, Kexin Shi*, Ananye Agarwal, Deepak Pathak）

> 注意：常被记错的 arXiv ID 2306.14882 是 Spectre 安全论文（Citadel），本论文正确 ID 为 2309.14341。

## 一句话概括

低成本 A1 + 单目前置深度相机，端到端 depth→关节 神经网络完成极端跑酷（2× 身高跳、2× 体长跨、37° 斜坡、倒立行走）——核心是 scandots 特权 teacher 加"连 heading 一起蒸馏"的双蒸馏。

## 要点

- **双蒸馏（dual distillation）**：Phase 1 用 waypoints 给特权 heading + scandots 地形做 RL；Phase 2 从 depth 同时蒸馏地形编码与 heading 预测——部署时 policy 自己决定转向，人工摇杆跟不上斜坡连跳所需的瞬时 yaw 变化
- **统一 inner-product reward**：世界系 waypoint 方向速度跟踪 + 边缘 5cm clearance 惩罚 + 风格项（倒立）——一套 reward 涌现跳/跨/倒立，无需按障碍逐个设计
- **MTS（mixture of teacher & student）**：蒸馏时 yaw 观测在预测值与 oracle 间按误差门控混合，防止分布漂移毁掉 DAgger 标签
- **延迟注入课程**：8k iters 后才开启 action delay；真机 depth 固定 0.08s 延迟防抖
- **低成本极限数字**：A1（身高 26cm / 体长 40cm）高跳 0.5m、跨 0.8m、爬 24–26cm 台阶与路缘；单张 3090 全程 <20h

## 优点

- 概念极简可复用：scandots 作为跨地形几何的通用特权表征 + 一套 reward，不依赖"障碍类型/宽度/距离"这类抽象特权（对比同期的 Robot Parkour Learning）
- 首个单网络 depth→motor 完成极端跑酷：同期 ANYmal Parkour 仍用高程图 + 分层导航
- 蒸馏消融干净：预测 yaw 的 MTS 方案（MXD 0.92）几乎追平 oracle（0.94），直接观测预测 yaw（Both 0.12）或不给 yaw（Mask 0.05）都崩

## 缺点与局限

- 感知视野窄：单目前置深度、far clip 2m、10Hz——只能"冲向看得见的障碍"，无侧后方感知、无全局导航（读者视角）
- 训练/评估地形全是 parkour 系五类（ramp/hurdle/flat/step/gap 各 0.2），无常规 rough 地形混合，真实世界多样性泛化存疑
- 边缘惩罚与任务表现有权衡：NoClear 仿真 MXD 反而 0.99（Ours 0.98），说明 clearance 惩罚是拿一点通过率换真机稳定
- 蒸馏依赖 DAgger，深度相机外观鲁棒性（光照/材质/透明物）论文讨论少
- yaw 观测门控阈值 0.6 rad 等超参对场景的敏感度未做消融

## 方法对比（论文内）

- 仿真障碍赛（256 robots / 30s）：Ours MXD 0.98±0.09 vs NoInner（base 系速度跟踪）0.75——NoInner 在 step 地形 0.14（撞-弹回-重试，绕不过去）；NoClear 0.99 但 MEV 0.08（贴边不稳）；Noisy（模拟建图）0.82 且方差大
- 真机蒸馏消融 MXD：Ours 0.92±0.19 ≈ Oracle 0.94；Both 0.12、Mask 0.05——yaw 预测必须混合 oracle 才能收敛
- 真机成功率（5 trials × 每地形每难度）：最难档比 NoDir（人工摇杆给向）与 NoClear 高 20–80%；NoDir 在斜坡连跳（需瞬时变向）上必挂

## 结果

- 高跳 0.5m（2× hip 高 26cm）、跳远跨 0.8m（2× 前后足距）、37° 斜坡、倒立行走（草地/软地形，无视觉倒立下楼梯）
- 台阶至 24cm 高/30cm 宽，路缘 26cm（项目页）
- 仿真 MXD 总分 0.98±0.09 / MEV 0.03；真机 MXD 0.92±0.19 / MEV 0.09
- 训练：Isaac Gym，base 10–15k iters（8–10h）+ 蒸馏 5–10k iters（5–10h），单张 3090 合计 <20h

## 极简 Input / Output / 实现

- `Input:` proprio 53 维（含 10 帧历史 × 53）+ scandots 132（teacher）/ 87×58 depth（student，buffer 2 帧）+ priv_latent 29 + priv_explicit 9
- `Output:` 12 关节位置目标（action_scale 0.25 × action + default stance），50Hz
- `实现:` PPO + ROA（rsl_rl fork / Isaac Gym Preview3，6144 envs）→ Phase 2 DAgger + MTS；Jetson NX 机载（depth 10Hz + policy 50Hz，UDP）

## 与当前 SOTA 的对比

- **数字与覆盖面已被超越**：ANYmal Parkour（Hoeller et al., Science Robotics 2024）统一策略 + 高层导航，walk/jump/climb/crouch 多技能在 2m/s 下组合；SoloParkour（Chane-Sane et al., CoRL 2024, arXiv:2409.13678）用 constrained RL 把"边缘/坠崖安全"写进训练目标（替代本方法事后 penalty），Solo-12 全机载部署；PIE（arXiv:2408.13740, 2024）implicit-explicit 双层学习改泛化
- **被吸收沿用的机制**：depth→action 端到端、scandots 类特权几何蒸馏、waypoint heading 自蒸馏、延迟注入课程——已成为后续 parkour 线标配骨架；同组把该配方扩展到人形（Humanoid Parkour Learning, Zhuang et al., CoRL 2024, PMLR v270）
- **暴露盲点**：单目短视野局部反应式跑酷缺全局规划（ANYmal Parkour 用分层导航补）；统一 reward 的技能覆盖受地形分布设计上限（Parkour in the Wild, arXiv:2505.11164, 2025 改多专家蒸馏扩规模；LocoMamba 2025 换 Mamba 视觉骨干）
- **结论**：价值已从"性能 SOTA"转为"低成本端到端 parkour 配方基线"——结构与工程 trick（延迟注入、MTS、边缘惩罚）比数字更长寿
