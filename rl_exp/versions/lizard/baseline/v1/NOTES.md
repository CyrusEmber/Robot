# baseline/v1 结果

> 骨架（versioning.mdc §A）：目的 / 假设 / 相对上版 diff / 训练命令 / 结果回填 / 结论。
> 配方与验收定义见 [PLAN.md](PLAN.md)；线路线见 [../PLAN.md](../PLAN.md)。

## 目的

回答一个问题：这副机器人能否在平地、固定 0.5 m/s 前向指令下，从随机策略学到**持续
稳定**的行走？

## 假设

1. 若能学会，跟踪误差与固定窗口前向位移会同步改善，而不是只有奖励上升（奖励可以靠
   站着不动刷，位移不能）。
2. 平地 + 零 DR + 零课程下，任何失败都只能归因到三种之一：配方太朴素、机器人动力学
   限制、或实现缺陷（启动探针只排除已覆盖的故障，不能整体排除第三种）。多 seed 失败也
   不能区分共享的优化障碍与资产限制；结论必须限定到配方、预算和证据范围。

## 相对上版 diff

**无上游母本**（`base.json` 为 `null`）：本线是从框架基类 `LocomotionVelocityRoughEnvCfg`
直接重写的全新配方，不与任何既有版本做逐项 diff。相对"既有粗糙地形线"的方向性差异：

- 地形：粗糙 → **平面**；移除 `height_scanner` 与 `height_scan` obs
- 观测：381 维三组 → **90 维单组 proprio**；脚环 208 与特权 83 全去
- 网络：`SplitEncoderModel` 三编码器 + 归一化 → **普通 MLP**，归一化关闭
- 命令：连续 `x∈[0,3]` + `heading_command` + 速度课程 → **固定点 `(0.5, 0, 0)`** +
  `heading_command=False` + `rel_standing_envs=0`
- 课程：地形课程 + 阶段速度课程 + c_k 时钟 → **全无**
- DR：10 项（含 2 项非 c_k 门控的 interval 扰动）→ **全关**
- 奖励：15 槽位 → **7 项**
- 终止：`time_out` + `roll_over` → `time_out` + **`base_contact`**
- 资产 / PD / 动作拆分 / sim 时序：**冻结为既有线的实际生效值，不改**
- PPO：paper S1（三编码器调参）→ 框架 velocity 任务默认平地配方，独立 `experiment_name`

## 开训前实测（2026-09-18，v1.1 修复之后）

`baseline_probe.py --task Lizard-Baseline-Flat-v1 --steps 250`（零动作、16 env、5 s；这一段测
**资产与 PD**，不是策略）：

| 量 | 实测 | 读法 |
|---|---|---|
| base z | 均值 0.9384 / 最低 0.9114（出生 1.1000 m） | 站得住。**但出生点比自然站高高 16 cm** ⇒ 每个回合先自由落体落地 |
| tilt | 均值 1.62° / 最大 1.71° | 直立，无倾倒趋势 |
| 承重 body（>1 N） | 四脚：rf 225.6 / rl 194.2 / lf 156.3 / rr 143.4 N | 腹、头链、尾三节**零载荷**：不趴地、不拿尾巴当第五支撑 |
| ΣF/(m·g) | 1.0186（仅四脚） | 承重闭环成立（+2% 为落地残余） |
| 关节 | 逐关节 mean\|qd\| 最大 0.152 rad/s（kfe 系）；无不动关节、无零力矩关节 | PD 全通道在线 |
| 终止 | 250 步内 fall 0 / time_out 0 | 零动作下不摔 |

**结论**：零动作站立成立，四脚承重闭环、无趴地 ⇒ 开训前"资产/PD 闸"过。

**同时钉住 P2-4 的那条口子**：同一 rollout 的逐项奖励为 `track_lin_vel_xy_miki +0.5706`、
`track_ang_vel_z_exp +0.4975`，合计 **+1.068/步（扣惩罚前）**。所以"不动"不是零收益，训练若收敛
到站桩，这两项会一直发钱——后续判"学不会"必须用位移与跟踪误差，不能只看奖励是否上升。

**遗留（不在本版变量里，属资产/平台决策）**：`baseline_params.yaml` 的
`robot.base_init_height: 1.1` 与自然站高 0.938 差 16 cm，每个回合带一次落地冲击，前 ~0.3 s 的
观测里混着落地暂态。要不要对齐站高由资产线决定。

**动作接口与逐关节激励**（`check_joint_layout.py --task Lizard-Baseline-Flat-Play-v1`，单关节注入
目标 0.3 rad、其余归零、40 步收敛）：

| 检查项 | 实测 | 判读 |
|---|---|---|
| 动作索引/顺序 | 2 个 term：`joint_pos_legs` 16 维 scale 0.5 + `joint_pos_spine` 10 维 scale 0.25，合计 **26** | 与 `baseline_params.yaml` 的 `action` 段一致 |
| 方向（符号） | 10 个探测关节的 `achieved` **全为正** = 与指令同号 | 无反向通道 |
| 限位 | 无一 CLAMPED；achieved 全在软限位内（腿 ±0.47…1.52、脊柱 ±0.47…0.57） | 0.3 rad 目标不触限位 |
| 幅值（achieved/target） | 自由链 84–100%（neck_yaw 100、tail3_pitch 97、neck_pitch 93、hfe 90/84、kfe 81）；承力链短：chest_pitch 49、haa 29、**踝 foot 2%** | PD 通道全部在线；踝/髋/胸在站姿下顶着地面反力，达不到目标——物理预期，不是死通道 |
| 端点位移 | 仅自由链可读（tail1_yaw 侧扫 −0.232 m）；腿/头链 0–30 mm | **端点落在承力路径上**（踝被踩住、头被腿撑）⇒ 站姿下不能靠端点位移判方向，改读 `achieved/target`（已写进工具注释） |

**结论**：动作接口（索引/尺度/方向/限位）核实通过，无死通道、无反号。腿/头链的幅值短缺是载荷
问题而非接线问题。**遗留**：踝关节在站姿下只有 2% 行程——摆动相可用即可，但若步态需要踝主动承重
发力，这一条要在资产线单独看。

## 最终验证（2026-09-20）：工具冒烟，**不是**训练验收

**这一节证明的是工具与接线按声明工作，以及"随机策略不会被判成通过"；它不包含任何训练
checkpoint，因此不能替代训练验收。**训练结果仍见下方"结果回填"表（**待**）。

**探针重跑（真实 Kit，两个模式都跑）**

| 运行 | 结果 |
|---|---|
| `baseline_probe.py --task Lizard-Baseline-Flat-v1 --headless` | rc 0，**26 项检查全 ok**；含本轮新增的三项真实检查：`events/actual-joint-reset`（读实际关节位置/速度与默认值比，不是读声明）、`events/live-materials-uniform`（读 live 逐 shape 摩擦/恢复系数）、`terminations/contact-and-timeout-behavior`（把接触历史与回合时钟**注进活的管理器**再还原） |
| 同上 `--random-actions` | rc 0，26 项全 ok；`mean\|a\| 0.4998` / `mean\|da\| 0.6679` / commanded dims **26/26**；60 步内 fall 0、time_out 0 |

接触注入的目标由 `baseline_runtime.termination_errors` 按 `sensor.body_names.index("base_link")`
**独立于配置**选取——若 `base_contact` 被错绑到脚，注进 `base_link` 就不会触发，探针报错而不是
跟着配置一起错（反例：`test_baseline_contract.py::test_termination_injection_is_independent_of_wiring`
把 term 绑到脚即红）。它验证**接线与阈值**，不替代物理跌倒试验。

**复位契约重跑**：`reset_check.py --task Lizard-Baseline-Flat-v1 --headless` → rc 0，A–D 八条断言
全 ok（激励 8/8 env、worst |dq| 0.3986 rad、suppressed respawns **0**；子集复位 env [0,1] 后，
**未被命名的 env 逐位未变**）。先激励再复位，是为了不让"初始姿态本来就对"把空验证伪装成通过。

**固定窗口评测入口（三份报告分开落盘，互不覆盖）**

| 报告 | `policy_mode` | 判定 |
|---|---|---|
| 零动作（无 checkpoint） | `zero_action` | `smoke_only` |
| 随机 checkpoint / 确定性 | `deterministic` | `fail` |
| 随机 checkpoint / 采样 | `sampled` | `fail` |

三个都**没有被误判为训练通过**；确定性/采样分文件（`--output` 已存在即拒绝写）是"采样只多一个
分布抽样、不得与确定性混表"的落点。

**证据的边界（照实写）**：这三跑的首回合**都活满 1000 步**（`first_episode_frame_fraction 1.0`），
所以"首回合失败后不累计重生位移"这条**没有被真实跑触发**——真实证据只到"随机策略三项门槛全不过"。
该条只有**离线反例**证过：`test_baseline_contract.py::test_fixed_window` 在第 3 步注入失败，之后每步
喂 1000 m 的假重生位移，位移仍为 2 m（= 3 × 0.5）。要真实触发它，需要一个会摔的 checkpoint。

**离线套件**：`run_offline_checks.bat` **46/46** 通过；`--confirm-cost` quiet 合计 **140s**（如实记在
`rl_exp\tools\verify\OFFLINE_CHECKS.md`，常量 175s 本轮不动）。

## 验收工具缺陷（2026-09-20 发现并修复，属本版范围）

**症状**：`baseline_eval.py` 首次接真实 checkpoint（`model_5850.pt`）时判 `fail`，但三条门槛里
**只有位移轴红**，且是 `−9.456 m`；同一份报告里 `forward_mae_mps = 0.0199`（速度误差极小）、
64/64 env 位移整齐同为 −9.45、`yaw_offset_abs_rad` **恰好 0.0**。位移与速度在同一帧里互斥。

**根因**：`baseline_eval.py:91` 用 `2 * atan2(q[:, 3], q[:, 0])` 取 yaw——那是 **(w, x, y, z)** 读法。
本仓 IsaacLab 的四元数是 **(x, y, z, w)**（`isaaclab/utils/math.py:577/601/651` 明文；`main/v10/DIAGNOSE.md`
也钉过），`yaw_quat` 输出 `x = y = 0` ⇒ `atan2(w, 0)` 恒 π/2 ⇒ **yaw 恒 π**。后果两条：

1. `distance = delta·(cos π, sin π) = −Δx_world`：报出的"前向位移"**不再是初始朝向轴**，与初始朝向
   无关，本配方下等价于"必须往世界 −x 走"——门槛要求被反过来了。
2. `yaw_offset_abs_rad` 恒 0（两侧都是同一个坏值），**该诊断没有信息量**，不能用它推断 yaw 没变。

速度轴走的是 `quat_apply_inverse(yaw_quat(q), v_w)`（库路径，自洽），**未受影响**。

**为什么 46 项离线检查没抓住**：`test_baseline_contract.py::test_fixed_window` 自己造 `yaw` **标量**
喂进 `BaselineWindow`，从不经过 quat→yaw 那一行；此前真实路径只用随机/零动作 checkpoint 跑过，
位移都是 ~0，符号翻转不可见。这正是本文档上一节自己写下的"证据边界"。

**修法**（单一真相，不新增模块）：`baseline_metrics.py` 的投影不动；`baseline_eval.py` 的 yaw 改由
**库**给出（`euler_xyz_from_quat(quat)[2]`，与 `yaw_quat` 同一公式，和奖励核同一帧定义），并把该调用
提成模块级 `yaw_of()` 供离线测试走同一接缝。回归两条：
`test_eval_forward_axis_is_the_training_frame`（投影必须等于奖励核的算子、且俯仰不影响 yaw）、
`test_eval_scores_equal_relative_motion_equally`（同相对运动、不同朝向，必须同分），
另加源码守卫 `test_no_hand_rolled_quat_yaw`（除白名单外，禁止手写 quaternion→yaw）。三条**修前全红**
（`yaw_of` 恒 π），修后全绿；整离线套件 **46/46**，quiet **165s**（文档常量 175s 不动）。

**同 ckpt 同 seed 重跑对照**（`..._reframe/eval.json`）：位移 `−9.456 → +9.456 m`，
`forward_mae_mps` 与 `first_episode_timeout_fraction` **逐位不变** ⇒ 缺陷只影响位移轴 + yaw 诊断。
修法与回归随后提交为 `2a07c88`，并打 tag `lizard-baseline-v1`（**补打**：开训前该打的锚点当时缺失，
`check_version_docs` 一直在报；锚点钉在"冻结配方 + 已修验收工具"的那个提交上）。

**作废报告**：`ablation_harness/results/baseline_flat_v1/v1/Lizard-Baseline-Flat-v1_5850_deterministic_seed123_void_wxyz_bug/eval.json`
（目录名已标 `void`）是本次缺陷的产物（`fail`），**不得**作为验收记录引用；有效记录见下节。

**跨线发现（不属本版范围，未改）**：`rl_exp/tasks/parkour_mdp.py:28 _yaw_from_quat` 是同一类错误——
docstring 写 `(x, y, z, w)`，算的是 `(w, x, y, z)` 分支。数值实测：真 yaw `[0, π/2, π]` → 它返回
`[π, π, π]`（恒 π，与转向无关）。该函数被 `PositionCommand` 用了 4 处（目标采样 `abs_dir = base_yaw + rel_dir`
与 `heading_err`），parkour 线有训练 run（`logs/rsl_rl/lizard_parkour_climb_v1`），故其记录的含义可能受影响。
已在守卫的白名单里**显式登记为已知坏**（不掩盖），处理方式留 parkour 线自己定。

## 训练命令

```bat
python scripts\reinforcement_learning\rsl_rl\train.py --task Lizard-Baseline-Flat-v1 --num_envs 4096
```

开训前：`check_cfg_lock.py --update --line lizard/baseline --reason "..."` 建本线 golden，
并打 tag `lizard-baseline-v1`。工作树必须干净（脏树开训被 `run_manifest.begin` 硬拒）。

## 结果回填（首跑，2026-09-20）

| 项 | 值 |
|---|---|
| run id | `lizard_baseline_v1/2026-09-20_12-23-09` |
| checkpoint | `model_5850.pt`（sha256 `b6e67533…`），15000 iter 计划中取于 **5850/15000（38.6%）** |
| 评测报告 | `ablation_harness/results/baseline_flat_v1/v1/Lizard-Baseline-Flat-v1_5850_deterministic_seed123_rev2a07c88/eval.json`（64 env，确定性，seed 123，20 s 首回合） |
| provenance | `code.repository.rev = 2a07c881bc0b`（修复提交）、`dirty = True`、`untracked_count = 1`。脏的两项都**不在配方代码里**：报告自身写下的未跟踪结果目录，以及另一处并行会话在改的 `WORK_PLAN.md`（非本次改动）。`ablation_harness/baseline_eval.py` 与 `rl_exp/tasks/baseline_mdp.py` 在提交点与工作树逐位一致 ⇒ 记录可用 `git checkout 2a07c88` 复原 |
| 跟踪误差（`mean\|v_x − 0.5\|`） | **0.0199 m/s**（门槛 < 0.15 ✓） |
| 固定窗口前向位移 | **+9.456 m**（门槛 > 8 ✓；64/64 env 存活满窗） |
| 存活率（`time_out` 占比） | **1.000**（门槛 > 0.9 ✓；`base_contact` 终止 0 次） |
| 侧向 / yaw 误差 | 0.0217 m/s / 0.194 rad（诊断，非门槛） |
| 分类判定 | 三项全过 ⇒ `pass` |

**训练期读数（过程监控，不作为验收）**：`error_vel_xy` 0.509 → 0.220(100) → 0.126(499) → 0.105(999)
→ 0.080(1999) → 0.0755(4999) → 0.0758(5789)；`mean_episode_length` 满 1000、`time_out` 1.000、
`base_contact` 0.000；`Policy/mean_std` 0.999 → 0.031。**lr 自 ~2000 iter 起触底 1e-5（adaptive KL），
此后曲线全平**（窗口 1000 的 Δ 在 ±0.1%）⇒ 后 9200 iter 预计空转，是否提前停训由使用者定。

训练期 `error_vel_xy`(0.0758) 与固定窗口 `forward_mae_mps`(0.0199) 的差**不是矛盾**：前者含随机动作
采样（`mean_std` 0.031）、全场次与复位后各回合；后者是确定性策略的**首回合**。两者口径不同，各自
服务的目的不同（过程监控 vs 冻结协议）。

## 结论

**回答本版的问题：能。** 平地 + 固定 `(0.5, 0, 0)`、零课程、零 DR 下，随机策略起训到 5850 iter，
在冻结协议的三条硬门槛上**全过**（跟踪 0.0199 m/s、前向位移 +9.456 m、存活 1.000），且位移与
速度互相独立地佐证"确实在往前走"，不是站桩刷分（`track_lin_vel_xy_miki` 1.488/1.5 对应
`exp(-e²/0.25) ⇒ e≈0.09`，与速度误差一致）。

**结论的边界（照实写）**：单 seed、单 checkpoint、单次 64-env 首回合、无 DR / 无扰动；本版**不**回答
速度泛化、鲁棒性、地形适应性——那些是后续轮次要逐项加回的变量（见 `../PLAN.md`）。
`baseline/v1` 的"工具链"部分在开训前已完成（探针两模式、复位契约、固定窗口入口、离线套件）；
本轮补上的是**首跑 + 一次验收工具缺陷的修复**，缺陷与回归见上节。

**遗留**：① `robot.base_init_height: 1.1` 与自然站高 0.938 差 16 cm（每回合一次落地冲击，属资产线决策）；
② 踝关节站姿下仅 2% 行程（若步态需踝主动承重，需资产线单独看）；③ parkour 线同款 yaw 缺陷（已登记，未改）。

