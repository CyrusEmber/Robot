# baseline/v1 方案（全量式，新线）

> 无上游母本 ⇒ 按 versioning.mdc §A 分线条款用**全量式 PLAN**。
> 结果见 [NOTES.md](NOTES.md)；线路线（后续轮次如何逐项加回变量）见 [../PLAN.md](../PLAN.md)。
> 第一轮只回答一个问题，**不预留任何第二臂**。

## 目的与假设

平地 + 固定 0.5 m/s 前向 + 零课程 + 零 DR，从随机策略起训，看能否得到持续稳定行走。
假设与判据见 NOTES.md；本文件定义**配方本身**。

## 五项前提校正（本轮明确写死，避免把别线的机制混进来）

1. **观测切换不是"免费的一行 A/B"**：90 维 ↔ 381 维牵动扫描器、特权观测、网络输入、
   归一化与 checkpoint 兼容性。第一轮**只实现 proprio 路径**，不实现、不为第二臂预留
   复杂度；若将来要三组观测，那是**另一份配方、另起一版、各自从头训**。
2. **"无课程" ≠ "关 DR"**：既有线里五项 DR 的强度依赖 c_k（实现上耦合），但两者概念
   独立。可选组合有"无课程 + 固定强度 DR"，本轮选的是**无课程 + 无 DR**。因此
   **逐个事件显式置 None**，不是删掉 `init_ck` 后吃函数缺省；两项 `interval` 扰动
   （外力/推力）不受 c_k 门控，必须单独关。
3. **固定命令要同时关两个改写开关**：`heading_command=False`、`rel_standing_envs=0`。
   否则配置写着 `v_x=0.5`，运行时命令仍可能被改写（`heading_command` 会把 `ang_vel_z`
   按 heading 误差重写；`rel_standing_envs>0` 会把该比例 env 的命令清零，白拿跟踪奖励）。
   **启动探针直接读下发后的 command tensor**，不信配置。
4. **删项理由要准确**：`head_load_penalty` 的删除是**简化选择**，不能说"belly 已覆盖头部
   承重"——两者测的不是同一个量（头部链竖向反力 vs 基座合力），不等价。`ang_vel_xy_l2`/
   `dof_acc_l2` 的删除与 c_k 无关，是**主动减少约束**（首轮少几个可归因项）。
5. **动作尺度不作硬验收**：撤掉 `mean(|action|) ∈ [0.05,0.4]` 这类门槛——动作值依赖关节
   尺度、默认姿态与步态，"均值大"不等于抖动、"均值小"不等于不动，26 个关节也不必全部
   充分运动。改为**诊断项**（见验收节）。

## 配方

| 项 | 值 | 依据 |
|---|---|---|
| 地形 | `plane`，`terrain_generator=None`，无 `height_scanner` | 平地是问题本身；扫描器在平面上扫的是常数 |
| 命令 | **固定点** `(0.5, 0, 0)`；`heading_command=False`；`rel_standing_envs=0` | 0.5 m/s ≈ 0.25 体长/s（躯干约 2 m）；固定点让速度课程失去对象 |
| 观测 | 单组 `policy` = 7 项 proprio，**90 维**（3+3+3+3+26+26+26）；`height_scan=None`；`enable_corruption=False` | 复用框架 velocity 任务的 proprio 组定义，逐维与既有线 proprio 相同；观测噪声也是随机化，显式关 |
| 网络 | MLP `[256,128,128]` elu，单组，`obs_normalization=False` | 归一化统计是训练状态，本线不从任何地方继承状态 |
| 奖励 | **7 项**（下表） | 满值口径见下 |
| 终止 | `time_out` + `base_contact`（`base_link`，threshold 1.0） | 平地躺下 = 基座接触 ⇒ 直接终止；"存活"因此有定义，"趴着前滑"直接判负而非慢慢罚 |
| 课程 | 全无：`terrain_levels` 置 None；阶段速度/地形课程属别线代码，本线不存在 | 见前提校正 2 |
| DR | **全关**：`physics_material`/`add_base_mass`/`base_com`/`base_external_force_torque`/`push_robot`/`reset_robot_joints` 六项置 None；`reset_base` 保留但 `pose_range`/`velocity_range` 逐轴归零 | 显式逐项关闭；`reset_base` 是把机器人放下来所必需，但它自带的姿态/速度随机也必须归零 |
| 资产 / PD / 动作接口 / sim | 冻结为既有线实际生效值：usda 共享、PD `800/40`·`200/12`·`400/20`、动作两组 `legs 0.5`（haa/hfe/kfe/foot）+ `spine 0.25`（chest/neck/tail）、`dt 0.005`×`decimation 4`（50 Hz）、`episode 20 s` | 这些是平台接口，不是本轮变量；改它们就无法回答"这副机器人"的问题 |
| PPO | 框架 velocity 平地配方：`num_steps 24`、`max_iter 3000`、`save 50`、5 epochs、4 minibatch、lr `1e-3` adaptive(`desired_kl 0.01`)、`gamma 0.99`、`lam 0.95`、`entropy 0.005`、`clip 0.2`、`max_grad_norm 1.0`；`experiment_name=lizard_baseline_v1` | 不用 paper S1（那是 4096 env + 381 维三编码器的调参）；独立日志目录 |

### 奖励 7 项

| term | 权重 | 说明 |
|---|---|---|
| `track_lin_vel_xy_miki` | `1.5` | yaw 对齐重力系下的全 2D 误差核 `exp(-‖v_cmd−v_yaw‖²/0.25)`：超速、横移、停车都掉分。**实现**在本线自己的 `baseline_mdp.py`（原实现在共享可变文件 `teacher_mdp.py`），漂移由测试抓 |
| `track_ang_vel_z_exp` | `0.5` | `ang_vel_z` 命令为 0 ⇒ 实际是"保持不转" |
| `lin_vel_z_l2` | `-2.0` | 禁竖直速度 |
| `action_rate_l2` | `-0.01` | 动作平滑 |
| `dof_torques_l2` | `-1e-5` | 省力 |
| `undesired_contacts` | `-1.0` | `.*_hfe`/`.*_kfe` 触地（大腿/小腿），threshold 1.0 |
| `belly_contact_force` | `-0.5` | 基座净接触力连续罚，`force_scale=706 N`（72 kg × 9.81）；无死区，擦一下便宜、压上去贵 |

置 None 的槽位（**逐个点名**，不靠"忘了的就没有"）：`track_lin_vel_xy_exp`（被 miki 核
替换）、`ang_vel_xy_l2`、`dof_acc_l2`、`feet_air_time`、`flat_orientation_l2`、
`dof_pos_limits`。

## 明确不做

地形与地形课程 · 高度扫描与脚环 · 特权观测与蒸馏 · 阶段速度课程与桶命令 · c_k 时钟 ·
任何域随机化与外力/推力 · `head_load_penalty` · `feet_slide`/`foot_clearance` ·
`RollOverTerm`（属共享可变文件；平地用基座接触终止即可）· 三编码器与 obs 归一化 ·
多 seed 并行 · 第二臂观测。

## 验收

**固定窗口**：每个 env 固定评测 20 s；**失败后不得重建 env 续算位移**，**不得只截取失败
前的帧**；确定性策略（`-Play`）与训练采样策略**分开报告**。

主轴（三条同时成立才算通过）：

| 轴 | 口径 | 阈值 |
|---|---|---|
| 跟踪 | 逐时刻 `mean|v_x − 0.5|`（abs 双向） | `< 0.15 m/s` |
| 位移 | 固定 20 s 内前向净位移 | `> 8 m`（**注意**：10 m 是"指令距离"，不是实际位移上界） |
| 存活 | `time_out` 占比 | `> 0.9` |

补充报告项（不作通过门槛）：**侧向误差**与 **yaw 误差**（只沿 x 达标不算通过）。

诊断项（**不给通过门槛**，只作判断依据）：

- 动作：`mean` / `p95` / `max` / 相邻步差分（抖动看均值）
- 关节：位置、速度、力矩，以及**限位占比**
- 长期输出异常的关节清单

## 风险与挂账（预注册）

1. **满值惩罚从第一步起用**：本线无 c_k，所有惩罚项一开始就是满值（既有线是随课程
   渐进）。若首跑"几乎不动"，**先读探针打印的各项实际量级与动作/关节响应**，再判断是否
   罚重了——不要仅凭现象就改权重。
2. **无 DR ⇒ 策略不可直接部署**。本线产物是**能力基线**，不是最终策略；鲁棒性是本线
   后续轮次要"逐项加回"的变量之一（见 ../PLAN.md）。
3. **删掉 `feet_slide`/`foot_clearance`** 可能重现拖脚/划脚；这是首轮主动接受的取舍。
4. **动作接口保留两组**：若将来发现两组拆分本身是学习障碍，那是一个**独立变量**，需单开
   一版，不在本版悄悄改。
5. **非 c_k 门控的 interval 扰动**在既有线里一直开（外力 4–8 s、推力 3–6 s）。本版关掉，
   因此与既有线的对比差异里包含这一项。

## 启动探针（先跑，再训）

`rl_exp\tools\verify\baseline_probe.py --task Lizard-Baseline-Flat-v1`：起少量 env，断言
**实际生效值**而非配置值：

- 命令：逐步读 `command_manager.get_term("base_velocity").command`，全 env 恒为
  `(0.5, 0, 0)`，且无 env 被"站立"掩码清零、`ang_vel_z` 未被 heading 重写
- 事件：7 个 DR 事件全为 None；跨 env 比对基座质量/地面摩擦一致（无随机化残留）
- 观测：组名与维数（`policy=90`）、有限性
- 奖励：短 rollout 内**逐项量级**（均值/极值），供风险 1 判断
- 终止：`base_contact`/`time_out` 均在场

探针全绿后才开训。**先 1 个 seed 跑通**，用于查明显故障；跑通后再加种子验证重复性。

## 修订记录

| 日期 | 版本 | 变更 + 原因 + 依据 |
|---|---|---|
| 2026-09-16 | v1 | 初稿。首跑定案：平地/无扫描器；固定 `0.5,0,0` 且关 heading 与 standing；90 维 proprio + 普通 MLP；课程与 DR 全部显式关闭；七项奖励（删项理由按用户 2026-09-16 校正）；资产与控制接口冻结既有生效值；PPO 用平地配方；验收改为固定窗口 + 动作尺度降级为诊断。依据：用户 2026-09-16 六条校正 + golden 实际生效值核查 |
