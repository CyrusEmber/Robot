# 论文资料索引

> 由 paper-summarizer skill 维护。每篇论文一个同名文件夹：`brief.md` 必存，`detail.md` 可选（只存 brief 没有的可复现细节）。

## Locomotion

| 论文 | 一句话概括 | 要点 |
|---|---|---|
| [Learning robust perceptive locomotion](https://arxiv.org/abs/2201.08117) | 特权 teacher + 门控 belief 蒸馏，双模态感知鲁棒融合的四足野外控制器 | Science Robotics 2022；CPG 相位残差 + sigmoid 门控跳连；Etzel 徒步 / DARPA SubT 冠军默认控制器；后继：ANYmal Parkour 2024、SLR 去特权化 2024；brief+detail 双全 |
| [Extreme Parkour with Legged Robots](https://arxiv.org/abs/2309.14341) | 单目 depth→关节 端到端跑酷：双蒸馏让 policy 自选 heading，A1 跳 2× 身高、跨 2× 体长、倒立 | ICRA 2024；CMU；scandots 特权 + MTS yaw 门控蒸馏 + 边缘惩罚课程门控 + 延迟注入；3090 全程 <20h；brief+detail 双全 |

<!-- | [论文名](链接) | 一句话概括 | 要点 | -->

## Navigation / Driving

| 论文 | 一句话概括 | 要点 |
|---|---|---|
| [Learning by Cheating](https://arxiv.org/abs/1912.12294) | 特权 agent"作弊"训练 → 蒸馏纯视觉学生，CARLA 驾驶范式开山作 | CoRL 2019；CARLA 全任务 100% 成功率、NoCrash 新纪录；2026 LEAD/TFv6 修正：须控制 teacher-student 信息不对称 |

<!-- | [论文名](链接) | 一句话概括 | 要点 | -->

## 游戏 AI / 其他

<!-- | [论文名](链接) | 一句话概括 | 要点 | -->
