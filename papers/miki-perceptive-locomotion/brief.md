# Learning robust perceptive locomotion — Brief

**Learning robust perceptive locomotion for quadrupedal robots in the wild** | Science Robotics 2022 (Vol 7, Issue 62) | [arXiv:2201.08117](https://arxiv.org/abs/2201.08117)

## 一句话概括

特权 teacher（真值地形）PPO 训练 + 门控循环 belief 蒸馏出对感知故障鲁棒的视觉运动四足控制器——perceptive locomotion 里程碑。

## 要点

- 特权学习：teacher PPO 拿真值地形/摩擦/扰动；student 用 GRU belief encoder + sigmoid 逐维门控融合 proprio 历史与高度采样，BC + 重建双损失蒸馏，零样本真机部署
- 门控语义：外感受可靠时逐维直通（提前抬腿），不可靠时无缝退化盲走——无手工切换规则
- CPG 相位残差动作空间：名义足端轨迹 + 解析 IK + 残差
- 实战：Etzel 山 2.2km 徒步达人类推荐用时；DARPA SubT 冠军队默认控制器；多季节野外零摔
- 附录数据已全部核实（网络尺寸/reward 系数/PPO 超参/消融）

## 优点

- 双模态融合端到端学会"何时信感知"，不靠启发式——首个同时拿到外感受速度与本体鲁棒性的控制器
- 高程图作传感器抽象层：LiDAR / 深度相机互换零微调
- 真机验证密度极高（野外科目 + SubT 实战），工程可信度同级别最高

## 缺点与局限

- 不确定性仅隐式使用：悬崖/梅花桩等遮挡场景高程图无信息，policy 假设连续地面可能踩空（论文自述）
- 2.5D 高程图丢材质纹理；建图依赖未与策略联合训练的经典位姿估计模块（论文自述）
- 只会"正常行走"流形内的动作：窄洞拔腿、上高台等大机动不行（论文自述）
- student 上限被 teacher 行为覆盖限制（特权蒸馏通病）

## 方法对比（论文内）

- 对比 proprio-only 基线（Lee et al. 2020）：台阶 20cm 起基线前腿频繁卡住，本方法可靠过 30.5cm，>32cm 主动犹豫（学到物理极限）；障碍赛基线三处全卡需人工抬推，本方法顺滑通过
- 速度：平地 1.2 vs 0.6 m/s，转向 3 vs 0.6 rad/s（5×）
- 仿真量化：41×41 地形参数网格 × 300 trials，grid steps 与 stairs 成功率全线领先

## 结果

- 台阶 12–36.5cm 梯度试验：30.5cm 可靠通过（10 trials/档，5 秒内成功计过）
- Etzel 山：2.2km / 120m 爬升 / 38% 坡，登顶 31min（人类标牌 35min），全程 78min（徒步规划器 76min，评级 difficult），零摔
- DARPA SubT：4 台 ANYmal 三类赛道 1700m+ 零摔，冠军队默认控制器
- S9 消融：GRU gate 小噪声下动作差与重建误差全面最小（rough 地形动作差 0.690 vs no-gate 0.746）

## 极简 Input / Output / 实现

- `Input:` proprio（指令 3 + 姿态 3 + 机体速度 6 + 关节位置/速度 + 历史 + CPG 相位 13）+ 每脚 5 半径高度采样 52 点 × 4 脚 = 208 维
- `Output:` 每腿相位偏移 Δφ + 12 关节位置残差 Δq（CPG 名义轨迹 + IK + 残差），50Hz
- `实现:` RaiSim 多 ANYmal-C 并行（teacher 1000 / student 300 envs）+ 学习式执行器模型；PyTorch 自定义 PPO；GPU 高程图 20Hz；部署 2×Bpearl LiDAR 或 4×D435 零微调

## 与当前 SOTA 的对比

- teacher-student 特权蒸馏至今仍是 perceptive locomotion 主干范式，但本方法的三条边界均已被后继推进：
  1. **多技能+导航**：ANYmal Parkour（Hoeller et al., Science Robotics 2024, arXiv:2306.14874）分层导航 + walking/jumping/climbing/crouching 统一策略，地形能力（跳跃/攀爬/钻行）超出本方法"只会走路"的局限
  2. **去特权化**：SLR（CoRL 2024, arXiv:2406.04835）完全移除特权信息、纯 proprio 自学习 latent，在 4 个 benchmark 上超 Miki 2022 基线——直接挑战"必须特权蒸馏"假设
  3. **感知表示升级**：MGDP（2025）depth+height 对比学习解耦感知与动力学；2023–2024 起还有直接 depth→action 的 parkour 线（Robot Parkour Learning / Extreme Parkour，待核实具体引用），绕过 2.5D 高程图丢纹理问题
- 论文自述的两个未来方向（显式不确定性估计、端到端感知）已被后续部分兑现；"门控融合双模态 + 从历史估不可观测状态"的结构思想仍是当前工作的对照基线与常用组件
- 对比结论：本方法的价值已从"性能 SOTA"转为"范式基线"——结构可复用，指标已被超越
