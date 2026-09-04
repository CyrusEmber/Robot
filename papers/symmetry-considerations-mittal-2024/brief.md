# Symmetry Considerations (Mittal 2024) — Brief

**Symmetry Considerations for Learning Task Symmetric Robot Policies** | ICRA 2024 | [arXiv:2403.04359](https://arxiv.org/abs/2403.04359) | ETH Zürich RSL（Mayank Mittal*, Nikita Rudin*, Victor Klemm, Arthur Allshire, Marco Hutter；实现进 leggedrobotics/rsl_rl）

> 对本仓的特殊地位：**Parkour in the Wild 专家训练引用的对称增广（论文 2.1 的 Mittal et al. 2024 即此篇）**；ANYmal Parkour S3 的实现是它的前身。

## 一句话概括

goal-conditioned 任务的对称性分两层（动作对称 vs 任务对称）；对称**数据增广**配合修正的 PPO 更新规则（镜像样本复用原样本 log-prob）完胜 mirror loss——更快收敛、更高 return、等效目标行为一致，真机对非完美对称硬件鲁棒。

## 要点

- **修正更新规则（Eq. 6，核心）**：增广样本 (L_g[s], K_g[a]) 的 PPO 概率比分母用**原样本的动作概率** π_θk(a|s)，不是镜像样本自身的 π_θk(K_g[a]|L_g[s])——后者对非完美对称策略可任意小 → 训练崩（Fig. 2）。直观：高回报动作 a@s 被强化时，等效动作 K_g[a]@L_g[s] 同步强化
- **前提**：状态概率比 p 项可忽略 = 策略近似对称——**小初始化权重 + 有界更新**时成立；大初始化权重下增广失效（Fig. 5），加小系数 mirror loss 可救对称性但救不回性能
- **aug > loss**：mirror loss 的梯度与 RL 目标竞争（w 大阻碍学习），增广的所有 transition 对齐同一 value function；两者叠加无增益
- **对称群**：ANYmal-Climb/Push 用 {I, reflect-x, reflect-y, 180° 旋转} 4 变体；Trifinger 用 120°/240° 旋转
- **Phase C 朝向课程**（climb 任务）：先固定朝向训练，成功后初始朝向随机化 yaw∈[−π,π]——**从头随机朝向会收敛到劣质侧向爬**；增广让 phase C 切换后几乎立即恢复（vanilla PPO 要重学且换行为）
- **硬件非对称鲁棒**：真机负载不均/执行器磨损下增广策略仍对称攀爬——方法鼓励对称但允许策略适配真实不对称

## 优点

- 理论动机干净（MDP 群对称 + on-policy 增广的修正推导）+ 四任务实证（cartpole/climb/push/trifinger）
- 对称性度量正确：等效目标的 return 差异（任务级），非 gait 对称性（动作级）
- 直接可用：实现开源在 leggedrobotics/rsl_rl，与本项目 rsl_rl 栈同源

## 缺点与局限

- 小初始化前提只有实验支撑无严格理论（作者自认 future work）
- 需要显式已知的对称变换（对 latent 表征如何增广未知）
- 网络架构路线（等变网络）被搁置——保证等变但约束死板、中性状态（静止站立）无法起步

## 方法对比（论文内）

- climb 任务：aug return 17.46 / 等效差异 0.124 vs vanilla 15.54 / 1.022 vs loss-w 更低
：vanilla 只用两条腿推物（其余腿走路），aug 四腿按就近分工——零手工 reward 涌现

## 结果

- 四任务全部：aug 收敛最快 + return 最高 + 对称差异最低（Table I）
- ANYmal-D 真机箱攀爬：vanilla 频繁原地转向（感知失败/失步），aug 无多余旋转、行为可预测

## 极简 Input / Output / 实现

- `Input:` 任务原生 obs（climb = proprio + 高程图 + 指令，282 维）
- `Output:` 任务原生动作（12 关节目标）
- `实现:` PPO + Isaac Gym；增广在 minibatch 级（obs/动作镜像变换 + log-prob 复用）

## 与当前 SOTA 的对比

- 已成 ETH RSL 系标准件：Parkour in the Wild（2025）专家训练默认引用；后续等变网络路线（MDP homomorphic networks 等）在 locomotion 实用性上仍处下风（中性状态问题）
- lizard 适配注意：**只有矢状面镜像（左右）一个非平凡变换**——neck（6 关节）与 rear+tail（4 关节）前后不对称，reflect-y 与 180° 旋转不适用 → 2× 增广（ANYmal 4×）
