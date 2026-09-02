# Extreme Parkour with Legged Robots — Detail

> 本文件只含 brief.md 没有的可复现细节。数据来源：arXiv HTML 全文（2309.14341v1）、官方仓库 `chengxuxin/extreme-parkour` README 与配置代码（`legged_robot_config.py` / `a1_parkour_config.py` / `legged_robot.py`），逐项核实，无凭记忆项。
> 代码与论文的对应关系：论文 reward 公式 = `_reward_tracking_goal_vel` / `_reward_feet_edge` 等；延迟注入 = `delay_update_global_steps`（8k iters 后开启）。

## 方法详解

### 训练管线（两阶段，ROA 在线适配贯穿）

1. **Phase 1 — Scandots RL（base policy）**
   - 输入：proprioception + scandots（特权地形点）+ oracle heading（waypoints 计算）+ 风格开关 W + v_cmd
   - 算法：PPO（rsl_rl fork），特权的 priv_latent（质量/摩擦/电机强度）直接进观测，同时用 ROA 训 estimator 从观测历史回归这些环境参数（蒸馏后替换特权输入）
   - 奖励见下节；地形课程见下节
   - 6144 envs，10–15k iters（3090 上 8–10h）
2. **Phase 2 — 蒸馏方向与外感受（distillation policy）**
   - 外感受：用 convnet-GRU 管线（RMA 式结构）替换 scandots 输入，输入 depth（87×58，buffer 2 帧），**DAgger** 监督：teacher 动作作标签，student 自己的动作 step 环境（防漂移）
   - actor 用 Phase 1 权重初始化，depth 编码器从头训练
   - heading：额外网络头从 depth 预测 yaw；直接把预测 yaw 给 student 会分布漂移毁掉动作标签，故用 **MTS**：`obs_θ = θ_pred if |θ_pred − d̂_w| < 0.6 rad else d̂_w`（0.6 rad 为代码/论文一致的门控阈值）
   - DAgger 更新频率 20 iters；priv 回归损失调度 [0, 0.1, 2000, 3000]（2000 iters 起加、3000 到满 0.1）
   - 5–10k iters（3090 上 5–10h）
3. **部署**：Jetson NX 同时跑 depth 编码（10Hz）与 base policy（50Hz），UDP 通信；零微调

### 观测空间（代码逐通道核实，num_observations = 753）

| 组 | 通道 | 维度 |
|---|---|---|
| proprio 当前帧（53） | base_ang_vel × 0.25 | 3 |
| | roll / pitch（imu） | 2 |
| | [0, Δyaw, Δnext_yaw]（Δ 每 5 policy 步更新一次） | 3 |
| | [0, 0, v_cmd]（前两路恒零，仅留结构） | 3 |
| | [env_class≠17, env_class==17] 地形类 one-hot 旗标 | 2 |
| | dof_pos − default（×1.0） | 12 |
| | dof_vel × 0.05 | 12 |
| | 上一帧 action | 12 |
| | 足端接触（contact_filt − 0.5） | 4 |
| scandots（132） | 高度采样 `clip(root_z − 0.3 − measured_heights, −1, 1)`，x 12 点 × y 11 点（前方 1.2m × 侧向 1.5m 网格，×5.0 scale） | 132 |
| priv_explicit（9） | base_lin_vel × 2.0 + 两组恒零 3 维（占位） | 9 |
| priv_latent（29） | mass + com（4）+ friction（1）+ motor_strength−1（12×2 前后腿组） | 29 |
| 历史 | proprio 10 帧（yaw 通道在历史中置零） | 10×53 |

- env_class 17：特定 parkour 地形类（gap/step 一族，具体索引→地形名映射待核实）——姿态正则只对该类启用（见 reward）
- student 时 scandots 132 维被 depth 编码器输出（512 维 GRU 隐态管线）替换

### 深度相机配置（config 核实）

- 原始 106×60 → resize 87×58；horizontal FOV 87°；near/far clip 0–2m；buffer 2 帧
- 安装位 [0.27, 0, 0.03]，俯仰角 ±5° 随机
- update_interval 5（50Hz policy 下 depth 每 5 步更新 = 10Hz）；真机固定 0.08s 延迟、proprio 0.016s
- 训练期相机地形网格：192 envs 开相机，terrain 10 行 × 20 列，水平 scale 0.1（粗于 scandots 的 0.05）

### 动作空间

- 12 关节位置目标：`q_target = 0.25 × action + default stance`，clip ±1.2
- default stance（a1_parkour_config）：hip ±0.1、thigh 0.8（前）/1.0（后）、calf −1.5
- PD：stiffness 40 N·m/rad，damping 1 N·m·s/rad；decimation 4 × dt 0.005 → 50Hz

### Reward（代码逐项核实，scale 值）

| 项 | scale | 说明 |
|---|---|---|
| tracking_goal_vel | +1.5 | `min(⟨d̂_w, v⟩, v_cmd) / v_cmd`——世界系 waypoint 方向（论文 Eq.2），防"绕开障碍骗奖励" |
| tracking_yaw | +0.5 | `exp(−\|target_yaw − yaw\|)` |
| lin_vel_z | −1.0 | env_class 17（跳/跨类）全额，其余 ×0.5 |
| ang_vel_xy | −0.05 | |
| orientation | −1.0 | **只在 env_class 17 启用**，其余地形放开俯仰自由度 |
| dof_acc | −2.5e-7 | |
| collision | −10.0 | thigh/calf/base 接触力 > 0.1N 计 1 |
| action_rate | −0.1 | |
| delta_torques | −1e-7 | |
| torques | −1e-5 | |
| hip_pos | −0.5 | |
| dof_error | −0.04 | |
| feet_stumble | −1.0 | 足端水平接触力 > 4× 垂直力（踢到立面） |
| feet_edge | −1.0 | 足端接触点落在边缘 mask（5cm 内）且接触；**仅 terrain_levels > 3 后生效**（课程门控） |

- `only_positive_rewards = True`；tracking_sigma 0.2；soft_torque_limit 0.4
- 风格项（论文 Eq.4，倒立）：`W·[0.5·⟨v̂_fwd, ĉ⟩ + 0.5]²`，ĉ = [0,0,−1]，W 训练时 {0,1} 均匀采样、部署时遥控开关——该训练配置对应 repo 中倒立分支（无外感受版本）
- 正则项继承 Legs as Manipulator（Cheng et al., ICRA 2023）

### 噪声与随机化（config 核实）

- **观测噪声整体关闭**（`add_noise = False`，noise_scales 定义了但未启用）——鲁棒性改由"蒸馏 + 延迟注入 + 物理随机化"承担，这是与 Miki 2022 路线的本质分工
- 物理：摩擦 [0.6, 2.0]；附加质量 [0, 3] kg；质心偏移 [−0.2, 0.2] m；电机强度 [0.8, 1.2]
- 推扰：每 8s 一次，最大 0.5 m/s
- 延迟：`action_delay` 缓冲 8 帧，`delay_update_global_steps = 24×8000` → 8k iters 后开启随机 action delay（README：`--delay` 即训练/游玩时启用）
- 初始状态：默认关闭位置/速度/偏航随机（`randomize_* = False`），rand_yaw 1.2 / pitch 1.6 / y 0.5 为可用范围

### 网络结构（config 核实）

- scan（scandots）编码器 MLP [128, 64, 32]；actor/critic MLP [512, 256, 128]，ELU
- priv 编码器 [64, 20]（ROA estimator：hidden [128, 64]，lr 1e-4）
- depth 编码器：CNN → 512 hidden + GRU（buffer 2 帧），lr 1e-3
- PPO：lr 2e-4 adaptive（KL 目标 0.01）、γ 0.99、λ 0.95、clip 0.2、entropy 0.01、5 epochs、4 minibatches、24 steps/env/iter

### Terrain 与课程

- trimesh，水平 scale 0.05m / 垂直 0.005m；edge_width_thresh 0.05m（feet_edge mask 同源）
- 地形分布：parkour / parkour_hurdle / parkour_flat / parkour_step / parkour_gap 各 0.2（纯 parkour 系，无 rough 混合）
- 10 行（难度级）× 40 列；terrain_length 18m × width 4m
- 课程：通过半程以上升级；若走过的距离 < 0.5 × v_cmd·T 则降级；feet_edge 惩罚在 level 3 之后才启用（先学会通过、再学贴边安全）
- waypoints：每地形预布（论文 Fig.3 红点），waypoint_delta 0.7m，接近阈值 0.2m 换下一目标，未来目标观测 2 个（Δnext_yaw）

## 实现与部署细节

- 仿真 Isaac Gym Preview3/4（Preview4 无碍），rsl_rl fork（`extreme-park_rl`），legged_gym 框架
- 部署全机载：Jetson NX，depth 编码 10Hz + policy 50Hz 双进程 UDP；D435 位于头部
- 真机 latency 工程化：处理时间不足 0.08s 时主动补齐到 0.08s（防抖动比低延迟更重要）；proprio 固定 0.016s
- 倒立策略训练时无外感受（proprio-only），部署可无视觉倒立下楼梯

## 实验与泛化过程

- 仿真量化：4 类地形各拼一条递增难度障碍赛道，256 robots 同时刷 30s，报 MXD（平均 x 位移）与 MEV（平均踩边次数）——Ours MXD 0.98 / MEV 0.03 全面最优（NoInner 在 step 地形 MXD 0.14：无世界系 waypoint reward 时学会绕行，遇台阶绕不过去只能撞墙重试）
- 真机：每地形每难度 5 trials；最难档成功率比 NoDir / NoClear 高 20–80%（Fig.7 未给绝对数值）
- 涌现行为：高跳（0.5m 健身块）的助跑-对齐-后腿蹬伸-前腿拉拽-收腿-落定全流程无脚本；长跳（0.8m）同理；倒立可在软草地与缓坡上行走
- OOD 表现（项目页）：未见过的楼梯/路缘先卡住，靠涌现的"攀爬上拽"行为最终通过

## 对游戏开发的启示

- **heading 自蒸馏（MTS）**：把"人工指令 + 自动选路"统一进一个网络——游戏 NPC 对应"玩家粗指令 + NPC 自己补局部最优方向"，混合 oracle 门控防蒸馏漂移的技巧直接可用
- **世界系 waypoint 方向 reward**：防"绕开障碍骗奖励"——游戏训练物理角色时同样该用路径方向内积而非机体系速度指令
- **延迟注入课程**：先学理想控制、后期随机化延迟，对网络同步/帧率抖动下的角色控制训练是现成配方
- **feet_edge 课程门控惩罚**：先保通过率、再收紧安全边界，两难指标的通用调法
- **观测噪声关闭 + 蒸馏管鲁棒**：与 Miki 路线（噪声全开）二选一时，低感知保真度的游戏场景更适合本篇配方
- **不该照搬**：87° FOV / 2m far clip 的感知配置绑定真机深度相机；10Hz 视觉 + 50Hz 控制的异频融合在游戏里可简化；纯 parkour 系地形分布无法支撑通用移动能力
