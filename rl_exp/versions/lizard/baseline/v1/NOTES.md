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

## 训练命令

```bat
python scripts\reinforcement_learning\rsl_rl\train.py --task Lizard-Baseline-Flat-v1 --num_envs 4096
```

开训前：`check_cfg_lock.py --update --line lizard/baseline --reason "..."` 建本线 golden，
并打 tag `lizard-baseline-v1`。工作树必须干净（脏树开训被 `run_manifest.begin` 硬拒）。

## 结果回填

（待第一跑：`rl_exp\tools\trainlog\dump_tb.py` 导曲线 → 固定窗口验收 → 本表回填）

| 项 | 值 |
|---|---|
| run id | 待 |
| 训练量 | 待 |
| 跟踪误差（`mean|v_x − 0.5|`） | 待 |
| 固定窗口前向位移 | 待 |
| 存活率（`time_out` 占比） | 待 |
| 侧向 / yaw 误差 | 待 |

## 结论

（待训练结果。2026-09-20 已完成的只是**开训前工具链**：探针（两模式）、复位契约、固定窗口评测
入口、离线套件 46/46 —— 全是"工具与接线按声明工作 + 随机策略不会判成通过"的冒烟，**不含训练
checkpoint**，因此**不构成**对"这副机器人能否学会持续行走"的回答。该问题仍待第一跑回填。）
