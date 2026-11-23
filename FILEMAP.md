# 文件地图

| 入口 | 用途 |
|---|---|
| `README.md` | 机体、实验、训练、评测四步用法 |
| `rl_exp/robots/lizard2_round_feet.py` | 圆足资产、动作关节顺序和默认 PD |
| `rl_exp/lizard2_round_feet/` | v7 使用的 USD、URDF 和网格 |
| `rl_exp/lizard2_v7.py` | 现役 v7 的环境与 PPO 配置 |
| `rl_exp/locomotion/` | 训练入口、v7 的 MDP、Run 留痕及 pytest |
| `ablation_harness/` | 协议、评测、地形和九宫格录像 |
| `rl_exp/tools/diagnose/` | 机体和行为的专项诊断 |
| `rl_exp/out/` | 本地 Run、评测与诊断产物 |
| `work/` | 简短交接和已有归档 |
| `acceptance/records/` | 重大实验决定与证据指针 |

旧 Gym 配方、退役版本、旧闸门和历史架构说明见 Git 标签 `archive/pre-refactor`。
