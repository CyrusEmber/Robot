# Parkour in the Wild — Brief

**Parkour in the Wild: Learning a General and Extensible Agile Locomotion Policy Using Multi-expert Distillation and RL Fine-tuning** | 2025（arXiv 预印本；搜索结果称被 RSS 2025 接收，arXiv 页无 comments 标注，待核实） | [arXiv:2505.11164](https://arxiv.org/abs/2505.11164) | ETH Zürich RSL + NVIDIA Switzerland（Nikita Rudin, Junzhe He, Joshua Aurand, Marco Hutter）

> 链接勘误：搜索结果常把 `robot-parkour.github.io` 挂到本文——该主页实为 Robot Parkour Learning（Zhuang et al., CoRL 2023），另一篇论文。本文项目页在 ETH RSL（待核实具体 URL）。

## 一句话概括

9 个地形专家策略 → DAgger 蒸馏成单个 depth 驱动 foundation policy → 在含真实 3D 扫描废墟的混合地形上 RL 微调——单策略在 ANYmal D 上完成野外跑酷，且支持"加地形→继续微调"的持续扩展。

## 要点

- **三阶段管线**：专家 RL（elevation map 特权感知）→ DAgger 在线蒸馏（学生只看 4 路 48×32 深度图）→ RL 微调（9 旧地形 + Parkour line + 15 个真实 SAR 设施 3D 扫描地形）
- **蒸馏 + 微调的组合方式胜过分层切换与 VAE latent**：分层方法从 5 技能扩到 9 技能就学不会用全部专家；VAE from-scratch 探索快但新地形不如蒸馏；纯 RL from-scratch 直接塌缩到任务子集
- **微调稳定性三件套**：蒸馏期注入 action noise（预适应 RL 探索）+ 保守超参 + 先冻结 policy 只训 critic 的预热阶段
- **可扩展性验证**：对最难的 Down-stones 地形反复微调，成功率 54.4% → 92.4%，旧技能不掉点；且混合全部旧地形（新地形仅占 3% 样本）比只训新地形效果更好
- **Active perception 涌现**：微调后 policy 学会离障碍更远停下、倾斜机身让深度相机看到箱顶——专家没有的行为

## 优点

- 首个演示"蒸馏 foundation policy + 反复 RL 微调"可持续加技能而不灾难性遗忘的腿足 locomotion 管线
- 微调后单策略平均成功率超过各专家 +3.1%（蒸馏后是 −10.4%），证明 RL 微调能修复蒸馏损失而非仅保持
- 深度图直驱（跳过高程图/状态估计依赖），配合 5 步噪声模型（边缘噪声/Perlin 空洞/盲区列/模糊）完成 sim-to-real，真机 SAR 废墟、湿滑碎石、高草、反光、直射阳光下通过
- 系统性对比三种技能组合范式（分层/VAE/蒸馏+微调），结论对后续选型有直接参考价值
- 消融证明：depth 输入下 LSTM 记忆必需（MLP 版蒸馏误差下不去）；elevation map 输入下 MLP 就够

## 缺点与局限

- 蒸馏问题是 ill-posed：不同专家在相似状态给不同动作，且专家-学生感知模态不同（高程图 vs 深度图），精度地形（Beams/Stepping stones）蒸馏后掉点最大（论文自述）
- 微调阶段调参量仍大：9 专家各用不同 reward/termination，微调需统一 setup，"省了从头训但依旧可观"（论文自述）
- 落脚精度不足：踩空后快速恢复而非直接选对落点；爬/跳过度用膝，电机磨损加快（论文自述）
- LSTM 无长期记忆：站几秒后近场裁剪范围内看过的箱子信息被稀释，再走会撞上；作者建议 Transformer（论文自述）
- OOD 仍会失败：组合技能地形 Down-stones 首轮微调仅 54.4%，"相对简单的场景也可能失败"（论文自述）
- 微调用 RL 算法未在正文点名（沿其 Isaac Gym 并行框架，推测 PPO，待核实）；训练并行规模、conv 通道数等实现细节未给

## 方法对比（论文内）

- **vs 分层切换（ANYmal Parkour 方式）**：高层硬切换专家，5→9 技能后高层 policy 弃用部分专家导致对应地形必挂；Gap-climb 需两技能混合运动，硬切换原理上做不到
- **vs VAE latent 技能编码**：from-scratch 时 VAE 探索效率最高（latent 动作空间优势）；但预训练+新地形上蒸馏+RL 微调更强——VAE decoder 只见过专家动作，新地形要的新动作生成不了
- **vs 纯 RL from-scratch**：任务数增多时塌缩到子集、学出跨任务的次优折中解、reward/curriculum 调参不可维护
- **vs 各自专家**：蒸馏后平均 −10.4%；微调后平均 +3.1%，Low wall 84.8% → 99.9%
- **蒸馏后 vs 专家（Walk 地形反超）**：99.3 vs 94.6——蒸馏自发产生跨技能知识复用

## 结果

- 微调策略 π_RL 成功率（1000 rollouts，90% 最大难度）：9 专家地形全部 ≥96.5%，Parkour line 98.5%，扫描地形（训练）99.1%
- **零样本泛化**：未见扫描地形 94.9%、人工摆石 93.2%、Gap-climb 82.0%；Down-stones 54.4% → 二次微调 92.4% 且旧地形不掉点
- 真机 ANYmal D：SAR 训练场废墟堆、室内外未见过地形，动态攀爬/跳跃；抗高草、光照变化、反光、直射阳光、湿滑碎石泥地、滚石、钢筋裂缝卡脚
- 部署：4/6 深度相机、无 lidar/外部传感、机载 CPU 50Hz、深度图 15Hz

## 极简 Input / Output / 实现

- `Input:` proprio（基座线/角速度、关节位置/速度、上一步动作、基座系重力）+ 指令（目标位置 r*、朝向 ψ*、剩余时间 t*）+ 4× 48×32 深度图（2 前 2 后）
- `Output:` 12 关节位置目标（与专家一致），机载 CPU 50Hz
- `实现:` 专家 RL（elevation map 特权）→ DAgger 在线蒸馏（MSE + action noise）→ RL 微调（PPO？待核实；Rudin 2022b Isaac Gym 并行框架；critic 预训练预热）；ANYmal D 真机

## 与当前 SOTA 的对比

- ANYmal Parkour（Hoeller et al., Science Robotics 2024）**：本文直接证伪其分层切换路线的可扩展性（9 技能即失效），改走蒸馏+微调；但 ANYmal Parkour 的导航/全局规划层本文没有——本文是 locomotion policy，不做长程导航
- **与 Robot Parkour Learning（Zhuang et al., CoRL 2023 Oral）/ Extreme Parkour（Cheng et al., ICRA 2024）**：同为"多技能蒸馏成单视觉策略"，但两者技能数少（4–5）且不展示新地形泛化；本文证明该范式配上 RL 微调才能扩展到 9+15 地形并涌现新行为。Extreme Parkour 的 scandots/双蒸馏已是后续 parkour 线标配，本文把"蒸馏只当初始化、RL 微调才是完成态"这一认知立起来
- **机制被后续吸收**：蒸馏后 RL 微调、critic 预训练防崩、训练期相机延迟随机化免部署同步——已成 sim-to-real 视觉 locomotion 常规配方。RLDG（arXiv:2412.09858, UC Berkeley, 2024-12，~65 引用）在操作任务上独立验证同一路线（专家 RL 产数据蒸馏进 generalist，弥合泛化-精度差距），说明"distill specialists → RL-FT generalist"是跨领域的通用配方而非四足特例
- **SOTA 视角盲点**：① 单策略容量与技能数的天花板未量化——论文自己预期"更多专门地形加入后性能会降"；② 深度端到端 vs 模块化感知的取舍（难归因、难分模块调优）在更 demanding 的精度任务上仍无定论；③ OOD 组合地形（Down-stones）首轮 54.4% 说明技能插值能力靠微调而非结构保证；④ 2025–2026 有 MoE 条件计算、Mamba 视觉骨干等新架构探索（搜索结果提及，具体论文未核实，不列）——LSTM 记忆瓶颈是公认弱点
- **结论**：仍是"多技能合成为单一可扩展控制器"这条线的当前参照系（2026 年引用约 48–53，搜索核实）；对做技能合成/持续扩展的人是必读方法论，对只做单一技能极限性能的人不是
