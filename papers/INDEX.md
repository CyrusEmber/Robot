# 论文资料索引

> 由 paper-summarizer skill 维护。每篇论文一个同名文件夹：`brief.md` 必存，`detail.md` 可选（只存 brief 没有的可复现细节）。

## Locomotion

| 论文 | 一句话概括 | 要点 |
|---|---|---|
| [Learning robust perceptive locomotion](https://arxiv.org/abs/2201.08117) | 特权 teacher + 门控 belief 蒸馏，双模态感知鲁棒融合的四足野外控制器 | Science Robotics 2022；CPG 相位残差 + sigmoid 门控跳连；Etzel 徒步 / DARPA SubT 冠军默认控制器；后继：ANYmal Parkour 2024、SLR 去特权化 2024；brief+detail 双全 |
| [Extreme Parkour with Legged Robots](https://arxiv.org/abs/2309.14341) | 单目 depth→关节 端到端跑酷：双蒸馏让 policy 自选 heading，A1 跳 2× 身高、跨 2× 体长、倒立 | ICRA 2024；CMU；scandots 特权 + MTS yaw 门控蒸馏 + 边缘惩罚课程门控 + 延迟注入；3090 全程 <20h；brief+detail 双全 |
| [Parkour in the Wild](https://arxiv.org/abs/2505.11164) | 9 专家 DAgger 蒸馏成单 depth policy 再 RL 微调：ANYmal D 野外跑酷，支持加地形持续微调不掉点 | 2025 ETH RSL；蒸馏+微调胜过分层/VAE/纯 RL；critic 预训练防崩；真实 3D 扫描废墟进训练；brief+detail 双全 |
| [ANYmal Parkour](https://arxiv.org/abs/2306.14874) | 五技能专家+分层导航+3D 场景重建，ANYmal D 2m/s 过连续障碍——Parkour in the Wild 专家训练的真源（Table S2） | Science Robotics 2024；位置任务专家配方全公开；对齐增广 log-prob 复制；分层扩展性问题催生 Parkour in the Wild |
| [Advanced Skills (Rudin 2022a)](https://arxiv.org/abs/2209.12827) | 位置任务原始定义：时间稀疏 reward（末段 1s 逆平方）替代速度跟踪，跳沟/膝钩爬坑涌现，难度全面超速度跟踪 | IROS 2022；稳定性三件套（短 episode/大 batch/去 bootstrap）；单方向 artifact（ψ* 指令与对称增广的靶子） |
| [Symmetry Considerations (Mittal 2024)](https://arxiv.org/abs/2403.04359) | 对称数据增广 + log-prob 复用规则完胜 mirror loss：等效目标行为一致、收敛更快、真机非对称鲁棒 | ICRA 2024；实现开源 leggedrobotics/rsl_rl；小初始化前提；phase C 朝向课程 |
| [PARC](https://arxiv.org/abs/2505.04002) | 动捕扩产：扩散生成器造地形穿越动作 + RL tracker 物理校正回填数据集，14 分钟种子滚出跑酷控制器 | SIGGRAPH 2025；SFU+NVIDIA；blended denoising（CFG 式）；接触双向 reward；优先失败采样；生成器非实时（12s/0.5s）；brief+detail 双全 |

<!-- | [论文名](链接) | 一句话概括 | 要点 | -->

## Navigation / Driving

| 论文 | 一句话概括 | 要点 |
|---|---|---|
| [Learning by Cheating](https://arxiv.org/abs/1912.12294) | 特权 agent"作弊"训练 → 蒸馏纯视觉学生，CARLA 驾驶范式开山作 | CoRL 2019；CARLA 全任务 100% 成功率、NoCrash 新纪录；2026 LEAD/TFv6 修正：须控制 teacher-student 信息不对称 |

<!-- | [论文名](链接) | 一句话概括 | 要点 | -->

## 游戏 AI / 其他

<!-- | [论文名](链接) | 一句话概括 | 要点 | -->
