# Parkour in the Wild — Detail

只写 brief 没有的可复现细节。元数据、优缺点、结果数字、SOTA 对比见 brief.md。

## 方法详解

### 训练管线（三阶段）

**Stage 1 — 专家 RL（9 个，各自独立训练）**

- 训练流程沿用 Hoeller et al. 2023（ANYmal Parkour）的 locomotion module；任务描述用 Rudin et al. 2022a 的 position-based 形式；数据增强用 Mittal et al. 2024 的对称性增广。
- 9 技能/地形：Walk、Climb、Climb down、Jump、Tables（即 crouch 钻桌）、Rock pile（碎石堆）、Low wall（跳低墙）、Beams（窄梁）、Stepping stones（梅花桩）。前 5 个来自 ANYmal Parkour，后 4 个新增（低墙跳越、梅花桩、窄梁、巨石堆攀爬）。
- 每个专家需专门 curriculum、reward 调参与训练流程；例如 Low wall 策略用 Climb 策略权重初始化。调参一次性成本，训完冻结复用。
- 专家感知：高程图（特权、近完美）——精细局部 1×2m @ 0.1m 分辨率 + 粗略全局 3×6m @ 0.5m 分辨率，另加 1 ray/30° 的 lidar 式水平扫描（分辨悬挑障碍）。

**Stage 2 — DAgger 在线蒸馏**

- 仿真环境合并全部 9 种专家地形，按 Rudin et al. 2022b 的海量并行设置，按地形给每台机器人指定对应专家。
- 每步同时查询学生与指定专家；**学生的动作（加零均值高斯 action noise）送进仿真**，收集 (o_student, a_expert) 对；然后监督训练最小化 Σ(π_student(o) − a_expert)²。
- Action noise 双重作用：防止过拟合小部分轨迹 + 预适应 RL 微调期的探索噪声（微调稳定性的关键之一）。
- 学生感知模态与专家不同：专家看高程图，学生只看 4 路深度图（2 前 2 后），必须靠记忆推断视野外/被遮挡的障碍部分。

**Stage 3 — RL 微调**

- 地形 = 9 专家地形 + Parkour line（箱/沟/桌/梯/坡混合，同 ANYmal Parkour）+ **15 个真实世界 SAR 训练设施废墟的 3D 扫描地形**。
- 稳定性三件套（论文明确列出）：
  1. foundation policy 对 action noise 的最大性能与鲁棒性（蒸馏期加噪 + 降低 RL policy 分布初始标准差）；
  2. 保守的 RL 超参；
  3. **critic 预训练**——RL 初始阶段冻结 policy 权重，超参按 critic 训练效率调优，critic 收敛后才开始更新 policy。
- 微调期 reward 见下表；无专家监督。

### 观测空间（Table 3）

| 通道 | 专家 | 学生 | 微调 critic |
|---|---|---|---|
| 基座线速度 v_b、角速度 ω_b（基座系） | × | × | × |
| 基座系重力向量 g_b | × | × | × |
| 关节位置 q、关节速度 q̇ | × | × | × |
| 指令：目标位置 r*、目标朝向 ψ*、剩余时间 t* | × | × | × |
| 高程图 Em 2×1m（精细） | × | | × |
| 高程图 Em 6×3m（粗略） | × | | × |
| Lidar 式水平扫描（1 ray/30°） | × | | × |
| 4× 深度图 I | | × | × |

- proporio 还含上一步动作（正文 "previous action"）。
- critic 为特权 critic：高程图 + lidar + 深度图全见（Table 3 排版解读）。
- 到达判定 S_L = 1(‖r_xy − r*_xy‖ < 0.25 m) · 1(‖ψ − ψ*‖ < 0.5)。

### 动作空间

- 与专家完全一致：12 关节位置目标 q*（由 action rate 惩罚项作用对象 q*_t 证实）；ANYmal D。
- 部署：机载 CPU 50Hz。

### Reward（RL 微调期，Table 2 全量）

| 项 | 表达式 | 权重 |
|---|---|---|
| Track position | 1_{t*<1}(1 − 0.5‖r_xy − r*_xy‖) | 10 |
| Track heading | 1_{t*<1}(1 − 0.5‖ψ − ψ*‖) | 5 |
| Joint velocity | ‖q̇‖² | −1e-3 |
| Torque | ‖τ‖² | −1e-5 |
| Joint vel. limit | Σ₁² max(\|q̇_i\| − q̇_lim, 0) | −1 |
| Torque limit | Σ₁² max(\|τ_i\| − τ_lim, 0) | −0.2 |
| Base acc. | ‖v̇‖² + 0.02‖ω̇‖² | −1e-3 |
| Feet acc. | Σ₄ ‖v̇_f‖ | −2e-3 |
| Action rate | ‖q*_t − q*_{t−1}‖² | −1e-2 |
| Feet force | Σ₄ max(‖F_f‖ − 700, 0)² | −1e-5 |
| Don't wait | 1(‖v_b‖ < 0.2) | −1 |
| Stand at target | S_L ‖q − q_d‖ | −0.5 |
| Collision | 1_{knee/shank collision} | −1 |
| Termination | 1_{α>135°} + 1_{q̇ > q̇_lim} | −2e3 |

- α 为基座 z 轴与重力夹角；F_f 足底接触力（700 N 阈值）；q_d 默认关节位置。任务项只管"到点 + 朝向"，Don't wait 反磨蹭。
- 专家训练期 reward 未给出（各自专门调参，论文只说 specialized）。

### 深度图噪声模型（sim-to-real 核心，Section 2.4）

仿真图先以 48×32 低分辨率渲染，然后 5 步退化：

1. **Clip**：深度 > 2m 截到 2m；< 0.15m（太近）视为空（同样设为 2m）。
2. **Edge noise**：对深度梯度做阈值找边缘；边缘邻域像素随机置空或与邻像素交换（模拟 stereo-matching 边缘失配）。
3. **Holes**：用缓变 Perlin noise 阈值化出 patch 置为最大深度——时间上连贯的空洞（模拟表面反光/材质失配）。
4. **Blind spot**：删掉最左 1–5 列（模拟近距离 stereo 盲区）。
5. **Gaussian blur**：整图模糊，抹细节、进一步拉近 sim-real 分布。

真实图处理：同样 clip → 降采样到 48×32 → 裁剪 → 与仿真相同的高斯模糊。

### 网络结构（Figure 3）

- 每路深度图独立过 CNN：3 个 conv + max-pool 层 → 2 个全连接层，输出 64 维特征（conv 通道数未给，待核实）。
- 4×64 特征拼接 proprio → 2 层 LSTM（hidden 尺寸未给）。
- LSTM 输出再拼接 proprio + 指令 → 3 层全连接 MLP（ELU）→ 动作。
- 消融：去掉 LSTM 的 MLP 版在高程图观测下蒸馏损失同样低；**深度图观测下 MLP 版蒸馏误差显著更高——记忆机制是 depth 输入的必要条件**（部分地形信息只在接近阶段出现过，如薄墙 vs 箱子爬上去前不可分辨）。

### Curriculum

- 专家阶段：每技能专门 curriculum（细节未给）。
- 微调阶段：未见显式课程；地形难度以"最大训练难度的 90%"评估，暗示难度参数化存在，具体课程策略未描述。
- 相机延迟：训练期对每路相机随机化延迟 → 部署无需任何同步机制，直接用最新一帧。

## 实现与部署细节

- 仿真：Isaac Gym（Rudin et al. 2022b 海量并行框架；正文未点名 RL 算法，推测 PPO，待核实）。训练并行 env 数未给出。
- 蒸馏评估/技能对比实验：1000 台机器人、100 个随机地形、难度 50–100% 最大训练难度，报 mean/mode。
- 硬件：标准 ANYmal D，4/6 深度相机（RealSense D435i，2 前 2 后），不用 lidar 与任何外部传感；机载 CPU 50Hz 控制循环；深度图 15Hz 供 policy（相机内部 60Hz ROS 推送）。
- 真机部署场景：SAR 训练设施废墟堆（未见过地形）、室内混合障碍。抗性演示：高草、光照变化、反光面、直射阳光（感知退化）；碎石/泥地湿滑、滚石、不稳定废墟（物理扰动）；钢筋、裂缝（卡脚陷阱）。

## 实验与泛化过程

- 主表（Table 4，1000 rollouts @ 90% 难度）关键数：
  - 蒸馏后 π_D：专家地形 73.0–99.3（平均较专家 −10.4%）；新地形几乎全挂（Parkour line 5.8、扫描 11.9/14.9、Gap-climb 10.2、Down-stones 11.3）。
  - 微调后 π_RL：专家地形全 ≥96.5（平均较对应专家 +3.1%，8→99.9）；Parkour line 98.5、扫描训练 99.1；**未见地形**：扫描测试 94.9、摆石 93.2、Gap-climb 82.0、Down-stones 54.4。
  - 二次微调 π_RL*（加 Down-stones）：Down-stones 54.4→92.4，其余地形基本不变（Walk 99.8、Scanned test 93.9 等）。
- 反复微调实验（Figure 5）：Down-stones 上 from-scratch 学不出解；从蒸馏策略起步可达非平凡性能；从已微调策略起步更快且终点更高；**混合全部旧地形训练（新地形仅 3% 样本）比只训新地形更好**——地形多样性本身重要。
- 技能组合对比（Figure 6）：蒸馏+微调 > VAE latent > 分层切换 ≈ 纯 RL（分层与纯 RL 均塌缩到地形子集；分层 5→9 专家后高层弃用部分专家；VAE 优势在 from-scratch 探索，劣势在 decoder 没见过的动作）。
- Active perception（Figure 8）：Climb 专家贴箱停下省力矩；蒸馏学生继承此行为导致伸手时看不到箱顶；微调后学会**停远一点 + 倾斜机身**让箱顶进入深度相机 FOV，跨训练 run 与障碍形状一致出现。
- 诊断性观察：接近箱子后站几秒再前进会撞箱（LSTM 隐状态在静止时被稀释，近场 clip 掉的箱体信息丢失）→ 长期记忆不足，作者提 Transformer 方向。

## 对游戏开发的启示

（解读）三阶段管线与游戏角色控制器多技能整合直接同构：

- **"专家冻结 → 蒸馏 → 微调"替代"分层技能状态机"**：游戏里对应"多个专精 controller（motion matching clip 集 / 专用 policy）→ 蒸馏成单 policy → 在混合关卡内容上微调"。本文数据说明硬切换（分层）在技能数上去后不可维护，软融合（蒸馏）才行——对"技能越多越想上分层"的直觉是反例。
- **持续加内容不灾难性遗忘**：加新关卡段→继续微调、新内容只占 3% 样本、保留旧地形混合训练——可直接搬到"角色动作包持续更新"流程。critic 预训练预热是防微调崩溃的廉价技巧。
- **蒸馏期注入 action noise**：既是正则又是 RL 微调的预热，游戏侧对应"对 teacher 动作加扰动再学"，提高学生鲁棒性。
- **Active perception 涌现**：policy 为改善自身感知而改变身体行为——对"角色为了看清而调整姿态"这类表现层行为，RL 微调可零成本涌现，不必手写。
- **不该照搬**：深度图噪声模型、相机延迟随机化、sim-to-real 细节为真机专用；游戏感知无 sim-real gap。reward 表可作游戏 RL locomotion 模板（任务项极简 + 大量正则，termination 大罚）。
- 对本项目 IsaacLab 训练管线（teacher-student / multi-expert 消融）而言，"蒸馏只是初始化、RL 微调才是完成态"+"critic 预训练"+"混合旧地形防遗忘"三条可直接进训练配方。
