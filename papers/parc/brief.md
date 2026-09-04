# PARC — Brief

**PARC: Physics-based Augmentation with Reinforcement Learning for Character Controllers** | SIGGRAPH 2025 Conference Papers（2025-08，Vancouver） | [arXiv:2505.04002](https://arxiv.org/abs/2505.04002) | SFU + NVIDIA（Michael Xu, Yi Shi, KangKang Yin, Xue Bin Peng）；代码/数据/生成数据全开源（github.com/mshoe/PARC）

## 一句话概括

动捕稀缺下的地形穿越技能扩产：运动生成器（扩散模型，地形+方向条件）造合成动作 → 物理跟踪控制器（DeepMimic 式 RL）在仿真里校正伪影 → 校正后的动作回填数据集继续训生成器——自消费自校正循环，14 分钟种子数据滚出跑酷控制器。

## 要点

- **双模型互喂数据的迭代循环**：生成器负责"想得出"（新地形新技能），tracker 负责"做得到"（物理可行性过滤 + 接触标签自动标注）；各阶段模型从上一阶段热启动（continual）
- **Blended denoising（CFG 式）**：小数据下生成器过拟合前两帧 → 无视地形；推理时混合"有/无历史帧"两种条件输出（s=0.65），平衡时序平滑与地形合规——无历史帧分支靠 15% attention mask 训出来
- **接触**：匹配参考接触给分、多余接触扣分——自然接触构型的关键（只跟踪姿态不跟踪接触 = 学出怪姿势爬墙）
- **优先失败采样**：按 clip 失败率加权采参考（下限 0.01 防灾难遗忘）——难动作不被早停饿死
- **物理校正是循环的命根**：无校正消融的高 jerk 帧率 18.7%（有校正 2.7%），且出现空中变向等物理不可能动作

## 优点

- 对症"高敏捷地形穿越动捕贵且少"的真痛点；产物喂任何下游（motion matching、learned MM、动画资产）
- 全链路开源（含生成数据集与可视化/编辑工具，Polyscope）
- 量化扎实：100 个 OOD 生成算法（Random Walk）测试地形 × 3200 动作的四指标跨迭代曲线 + 无校正/s 消融两版

## 缺点与局限

- **生成器非实时**：0.5s 动作 12s 生成（A6000）——论文自述不满足游戏/机器人闭环规划
- 全管线 3 迭代 ≈ 1 个月单卡——离线资产管线成本
- 程序化地形（2.5D 盒子网格）缺真实场景多样性；不自然行为未完全消除（自述需更好过滤）
- tracker 依赖参考轨迹在环（DeepMimic 系通病），runtime 复杂度高于纯 policy 方案

## 方法对比（论文内）

- 跨迭代（生成器）：FWD 1.908→0.596 m、地形穿透 2093→179.6、高 jerk 帧率 10.7%→2.7%
- 跨迭代（tracker）：成功率 27%→68%、关节跟踪误差 0.083→0.052 m
- 无物理校正 vs 有：高 jerk 帧 18.7% vs 2.7%，且出现空中变向类不可能动作
- blended denoising s 消融：s=0 平滑但穿墙（TPL 40796），s=1 地形好但抖（%HJF 54.8），0.65 平衡
- vs Gillman 2024（自消费循环）：对方用**冻结预训练** tracker 当校正器，PARC 把 tracker 训进循环并扩展到地形穿越域

## 结果

- 涌现新技能组合：跳沟接抓檐、连跳-挂檐-落下-手抓第二檐、爬下-跑离台-落地
- 种子数据 14m07s（vault/爬/跳/跑/台阶 + UE5 Game Animation Sample 节选），地形手工重建、接触手工标注；先做 50 变体/clip 的空间扩产，PARC 再滚 3 迭代（前两轮 ~1000 动作/轮 Random Boxes 地形，后两轮 2000/轮 100×100 手工地形切片）
- 长程演示：A\* 路径（跳跃边 + 墙体遮挡检查）+ 生成器自回归 + tracker 执行

## 极简 Input / Output / 实现

- `Input:` 生成器 = 局部高程图 31×31@0.4m + 目标方向 +（可选）前两帧；tracker = proprio（root 位姿/关节/接触标签）+ 局部高程图 + 参考未来帧
- `Output:` 生成器 = 0.5s 动作序列（15 帧：root 位姿/旋转 + 关节旋转/位置 + 接触标签）；tracker = 各关节 PD 目标姿态，30Hz（物理 120Hz）
- `实现:` 扩散（MDM 式 transformer encoder，DDIM stride 5）+ PPO/GAE Isaac Gym；策略 3FC 2048/1024/512；单 A6000 一个月

## 与当前 SOTA 的对比

- 定位在动效/游戏侧地形穿越线（ANYmal Parkour、Parkour in the Wild——专家 RL 无动作数据，动作自然性不保）是同一问题的两条路线；PARC 证明"小数据 + 物理校正"能到动画级质量
- 上游：DReCon（运动匹配规划器 + 物理跟踪）的双层结构被沿用，生成器从 motion matching 换成扩散；PhysDiff 用物理投影做采样级校正，PARC 用整个 RL tracker 做序列级校正（更强也更贵）
- 后续方向（论文自述 + 领域趋势）：实时化（蒸馏/小步数采样）、真实场景（非程序化地形）、不自然行为过滤；contact label reward 与优先失败采样已被 MaskedMimic 等物理控制线吸收为常规件
