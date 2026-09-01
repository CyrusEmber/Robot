# Learning robust perceptive locomotion — 论文笔记示例

> 勘误记录（本次调研修正的四处初版错误）：
> 1. 初版误写训练仿真器为 Isaac Gym，实为 **RaiSim**；
> 2. 初版把 attentional gate 描述成 query-key softmax attention，实为 **sigmoid 逐维门控跳连**，无 QK 结构；
> 3. 初版"DAgger 式采样"当论文术语用，论文原文仅"roll out student policy 生成样本"并引 Ross et al. / Czarnecki et al.，"DAgger" 是解读标签；
> 4. 初版部分补充材料内容（reward 系数、观测维度表、网络尺寸、S9 消融变体名）凭记忆复述，现统一标注「待核实」。

## 一、12 点结构化字段表

| 字段 | 内容 |
|---|---|
| 链接 | https://arxiv.org/abs/2201.08117 |
| 论文名 | Learning robust perceptive locomotion for quadrupedal robots in the wild |
| 年份 | 2022（Science Robotics, Vol 7, Issue 62） |
| 方向 | Perceptive Locomotion（感知融合运动） |
| 核心问题 | 外感受（视觉/激光）在雪、植被、反光、遮挡下不可靠，如何与本体感知鲁棒融合而非退化成盲走 |
| 核心方法 | teacher-student 特权学习：teacher PPO 拿特权观测训练；student 用 GRU belief encoder + attentional 门控融合 proprio 历史与高度采样，行为克隆 + 重建双损失蒸馏 |
| Input | Proprio（机体速度、姿态、关节位置/速度历史、动作历史、每腿相位）+ Velocity Command + 每脚 5 个半径的高度采样（52 点/脚 × 4 脚 = 208 维） |
| Output | 每腿相位偏移 Δφ + 12 关节位置残差 Δq（CPG 名义轨迹 + 解析 IK + 残差，50Hz） |
| Policy | Teacher-student 两阶段；RaiSim 仿真；teacher PPO（特权观测）→ student 蒸馏（BC + 重建），零样本部署 |
| Perception | Proprioception + Exteroception（高程图采样）双模态，attentional gate 逐维门控外感受通量 |
| 能力 | 雪地/植被/废墟/地下多季节零摔；台阶 30.5cm 可靠（任意方向任意朝向，无需专用模式）；平地 1.2 m/s、转向 3 rad/s（基线 5×）；Etzel 山 2.2km 徒步达人类推荐用时；DARPA SubT 冠军队默认控制器 |
| Game Friendly | 中——CPG 相位残差动作空间与特权蒸馏管线可直接借鉴，噪声鲁棒融合动机游戏不存在 |
| 我的结论 | 借鉴 CPG 相位残差动作空间与特权蒸馏管线；游戏感知免费，噪声融合层不需要，物理随机化+课程退火可平移到物理角色训练 |

## 二、详细总结

### 1. 背景与动机

外感受对快速运动至关重要——落地前看到地形才能提前调步态。但雪/植被在视觉上像不可踩障碍或因反光缺失；光照、灰尘、透明表面毁深度感知；高程图还依赖位姿估计，打滑带来漂移；树枝/悬挑物被 2.5D 高程图误表示成高障碍。此前最鲁棒方案只用 proprioception，代价是"用脚试地形"，速度受限（Lee et al. 2020 基线：平地 0.6 m/s，台阶 20cm 卡前腿）。目标：双模态鲁棒融合——感知好时快而优雅，感知坏时无缝退化盲走，全程无手工切换规则。

### 2. 方法详解

**训练管线（三阶段）**
1. **Teacher RL**：PPO 训 Gaussian 策略，随机地形 + 随机扰动 + 随机目标速度（机体坐标系 \(v_x, v_y, w\)）；特权观测 = 无噪地形测量、地面摩擦、所加扰动。
2. **Student 蒸馏**：同环境，但高度采样过噪声模型 \(o^{student}_t=(o^p_t, n(o^e_t))\)；belief encoder（GRU + 门控）+ 动作 MLP（复用 teacher 主干权重初始化）；双损失 = 行为克隆 \(\mathcal{L}_{bc}\)（同状态同指令下 student/teacher 动作平方距离）+ 0.5·重建损失 \(\mathcal{L}_{re}\)（无噪高度采样与特权信息 vs 从 belief 重建值）；训练样本由 student 自己 rollout 生成（引 Ross et al. / Czarnecki et al.，思想同 DAgger——解读标注）；GRU 用 TBPTT。
3. **零样本部署**：真机不微调。

**观测空间（通道级主文核实；逐维维度表待核实）**
- Proprio（师生共用）：机体速度、姿态、关节位置与速度历史、动作历史、每腿相位
- Extero：每脚周围 5 个半径的高度采样（开源实现 52 点/脚 × 4 脚 = 208 维）
- 特权（仅 teacher）：接触状态、接触力、接触法线、摩擦系数、大腿/小腿接触、机体外力外力矩、摆动时长

**动作空间（CPG 式结构化，主文核实）**
每腿维护相位变量 \(\phi_l\)，按相位定义名义足端轨迹（stepping motion），经逆运动学得各关节名义目标 \(q_i(\phi_l)\)；policy 输出每腿相位差 \(\Delta\phi_l\) 与"residual joint position target" \(\Delta q_i\)（论文原词），\(q^{target} = IK(\mathbf{p}(\phi_l+\Delta\phi_l)) + \Delta q_i\)。动作语义 = 调节奏 + 微调姿态，不是裸关节位置。

**Belief encoder（核心贡献）**

POMDP 两条不可观测链路：外感受噪声大时地形不可观测；特权状态无传感器直接测。需从观测序列在线估计：

\[
\begin{aligned}
l^e_t &= g_e(\tilde{o}^e_t) & &\text{噪声外感受特征（复用 teacher 的 } g_e\text{）}\\
b'_t,\ h_{t+1} &= \mathrm{GRU}(o^p_t,\ l^e_t,\ h_t) & &\text{中间 belief}\\
\alpha &= \sigma(g_a(b'_t)) & &\text{注意力向量（逐维 0~1）}\\
b_t &= g_b(b'_t) + l^e_t \odot \alpha & &\text{belief = GRU 通路 + 门控外感受跳连}
\end{aligned}
\]

- **门控语义（解读）**：\(l^e_t\) 同时进 GRU 与跳连；门决定多少**原始**外感受绕过循环积分直通 belief。可靠时 \(\alpha\to1\) 外感受直通（看到台阶提前抬腿）；不可靠时 \(\alpha\to0\)，belief 退化为 GRU 从 proprio 历史攒出的估计（盲走）。快慢双通路。灵感论文自述来自 gated RNN 与多模态信息融合。
- **Decoder 同款门**：belief decoder 用同一门结构从 \(b_t\) 重建无噪高度采样与特权信息，仅训练期使用（算重建 loss）+ belief 可视化内省。
- **蒸馏目标**：belief state 匹配 teacher 特征向量 \((l^e_t, l^{priv}_t)\)——"encodes all locomotion-relevant information"。
- **结构尺寸**：GRU 2 层 × 50 隐单元、重建权重 0.5、TBPTT、噪声课程 epoch 1→100 升满（开源实现默认参数证实）；teacher 各编码器尺寸待核实。

**噪声与随机化（主文核实）**
- 物理随机化：机体/腿部质量、初始关节位置与速度、初始机体姿态与速度、躯干外力外力矩、足底摩擦偶尔调低（打滑）
- 终止条件：躯干触地、大倾角、超关节力矩
- **高度采样噪声模型**：参数 \(z\in\mathbb{R}^{8\times4}\)（每腿 8 个噪声分量）；两类噪声——扫描点横向偏移 + 高度值扰动，各高斯采样；三种作用域——每扫描点/每脚（每步重采样）、每 episode（常量）；三档工况每 episode 头部或中途按 **60% / 30% / 10%** 抽取：nominal（正常建图）/ large offset（位姿漂移与可变形地形）/ large noise（遮挡与感知完全失效）；地形分格加偏移模拟植被/深雪地块突变；\(z\) 幅度随训练线性增大（课程）

**Reward（通道级主文核实；系数表待核实）**
- 指令跟踪：\(r_{command}=1.0\)（若 \(\bm{v}_{des}\cdot\bm{v}>|\bm{v}_{des}|\)，超速给满不罚），否则 \(\exp(-(\bm{v}_{des}\cdot\bm{v}-|\bm{v}_{des}|)^2)\)；yaw 指令同式
- 惩罚：正交速度分量、roll/pitch/yaw 机体角速度
- Shaping：机体姿态、关节力矩、关节速度、关节加速度、足底打滑、小腿与膝盖碰撞

**Curriculum**
- 地形课程：粒子滤波自适应更新地形参数，保持"难而可解"
- 扰动/权重课程：\(c_{k+1}=(c_k)^d,\ 0<d<1\)，扰动幅度与部分惩罚项（关节速度、关节加速度、姿态、打滑、大小腿接触）乘以单调趋近 1 的因子

### 3. 实现与部署细节

- 仿真：RaiSim，多台 ANYmal-C 并行，集成学习式执行器模型弥合 sim-to-real；地形为参数化高度图 + 四种楼梯（standard/open/ledged/random），楼梯用盒子拼装——高度图楼梯边缘不垂直，policy 会钻仿真空子导致迁移差。
- 框架 PyTorch；PPO 超参与并行环境数见补充材料（待核实）。
- 部署 ANYmal C：2×Robosense Bpearl dome LiDAR 或 4×Intel RealSense D435，换传感器零微调（高程图作传感器抽象层）；GPU 高程图管线 20Hz（Kalman 式更新 + 漂移补偿 + ray casting）；policy 50Hz，从最新高程图采样高度，无图区域填随机值。

### 4. 实验与泛化结果

- 台阶：proprio 基线 20cm 起前腿频繁卡住；本方法可靠过 30.5cm（10 次试验/档，5 秒内成功计过），提前抬腿前倾送后腿；>32cm 主动犹豫——学到超出自身物理极限。楼梯任意方向任意朝向原生通过（Spot 需专用模式），雪盖楼梯零失败。
- 障碍赛（20cm 平台、17cm/29cm 楼梯、20cm 方块堆）：本方法顺滑通过；基线三处全卡，需人工抬推。
- 速度：平地 1.2 m/s vs 基线 0.6（前进/横移）；转向 3 rad/s vs 0.6（5×）。
- Etzel 山 2.2km 环线、爬升 120m、坡度至 38%：登顶 31 分钟（官方人类标牌 35 分钟），全程 78 分钟（徒步规划器推荐 76 分钟，评级"困难"），零摔，仅停机修鞋与换电池。
- DARPA SubT：Cerberus 队默认控制器，冠军；4 台 ANYmal 在 tunnel/urban/cave 三类赛道探索 1700m+，零摔。
- Belief 行为（可视化）：踩上泡沫障碍后 belief 下修地形估计且离地后保留（循环记忆）；透明亚克力接触后上修改步态；蒙住传感器收纯噪声，磕碰修正估计后照样上下楼；滑面识别低摩擦（decoder 可解出摩擦系数）加快步频，位姿漂移毁图期间退回 proprio，图稳后切回。

### 5. 局限与风险（论文自述）

- 不确定性仅隐式使用：悬崖/梅花桩前高程图被遮挡，policy 假设连续地面可能踩空；显式不确定性估计（如用脚探地）是未来工作
- 高程图中间表示丢失材质纹理信息；建图依赖经典位姿估计模块，未与策略联合训练
- 不会大幅异常动作：从窄洞拔腿、爬高台等超出正常行走的机动

### 6. 对游戏开发的启示

- **CPG 相位残差动作空间**：名义轨迹 + IK + 残差，与游戏动画管线（foot trajectory + IK + 程序化修正）同构，比裸关节位置输出好落地。
- **特权蒸馏管线**：仿真特权状态训 teacher → 观测蒸馏 student，物理角色训练标准配方；比直接在 partial-observable 下 PPO 稳。
- **门控跳连技巧**：多输入源可靠性不一时逐维开关直通量，训练时对该源加 dropout 即学会开关——可用于多传感器/预测器/玩家输入融合。
- **"从历史估不可观测状态"**：游戏对应网络同步延迟下的状态预测、玩家意图估计、物理角色接触/摩擦估计——同一结构换个不可观测量。
- **不该照搬**：LiDAR/高程图建图与外感受噪声模型整套是为真机传感器不可靠设计的，游戏感知免费，纯冗余。

### 附：待核实清单（凭记忆，补充材料 S1/S3/S5-S9，本次未抓到原文）

- 观测逐维维度表（S5, Table S3）
- teacher 编码器与主干尺寸（S6）：extero 编码器 {80,60}→96 维、特权编码器 {64,32}→24 维、主干 {256,160,128}；belief 120 维
- reward 各项系数（S7）
- S9 消融四变体名（GRU gate / GRU no gate / MLP gate / MLP no gate）；主文仅确认 S9 存在门结构有效性评估
- PPO 超参与并行环境数（S1/S3）：teacher 1000 环境、student 300、lr 5e-4 衰减、γ 0.996、GAE λ 0.95、clip 0.2、熵系数 0.005
- 高度采样每圈点数 {6,8,10,12,16} 与半径 {0.08,0.16,0.26,0.36,0.48} m（S8；与开源实现 52 点/脚一致）
- 噪声模型离群值分量（S8）
