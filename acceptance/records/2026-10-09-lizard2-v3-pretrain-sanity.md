# lizard2 v3 训练前合理性检查（2026-10-09）

## 适用范围

只做训练前读数：**不训练、不跑 eval、不改配方与资产**。被读对象 `Lizard2-Flat-v3`（采用机体，
30 关节，22 动作通道）。本记录只补一件此前无读数的事：**初始动作分布相对各关节硬限位的位置**；
其余各条只引用同轮已有记录，不复述其数值。

## 验收条件

- 读数取自构建后的 cfg 与家族 `assets.json` 声明的 URDF（`family_urdf`），不是手抄表；
- 不设通过/失败：判"多少越界可接受"需要目标速度带（R4），该需求尚未声明；
- 引用处的口径归各自记录，本记录不派生新结论。

## 结果

### ① 接口与驱动（引用，已绿）

动作通道 22（12 腿 hip/haa/hfe + 10 spine；`kfe`/`foot` 无通道、PD 与默认零目标保留）。驱动侧读回：
30/30 关节的求解器持有 `stiffness`/`damping`/`effort_limit` 等于声明值；`velocity` 两处都不进引擎
（yaml 旧字段被 fork 丢弃、URDF 自带列未被消费，求解器持有 ~5.94e36）。见
`2026-10-09-lizard2-drive-readback-audit.md`。

### ② 静站承重（引用，已绿）

零动作、重力开：全部 30 关节 `pd_estimate_over_limit_frac = 0.000`，最坏 `tail1_pitch` 占自身限幅
0.546，腿组最坏 0.198。见 `2026-10-09-lizard2-static-load-demand.md`（该窗口是**超时开启**的微动窗口，
不是落定后读数：那边 ⑤）。

### ③ 初始动作分布 vs 硬限位（本记录唯一新读数）

探索标准差取任务自己的 runner cfg（`actor.distribution_cfg.init_std = 1.0`），目标 = `scale × N(0,1)`，
默认目标为 0（本配方全 30 关节零默认角）。逐关节越界概率：

| 通道组 | 通道数 | scale | 硬限位 [rad] | 越界概率 |
|---|---|---|---|---|
| `hip` / `haa` | 8 | 0.50 | ±0.60 | **0.230** |
| spine pitch | 5 | 0.25 | ±0.50 | 0.0455 |
| `hfe` | 4 | 0.50 | ±1.20 | 0.0164 |
| spine yaw | 5 | 0.25 | ±0.60 | 0.0164 |

- **22/22 通道的 3σ 目标都在各自限位之外**，逐组（止档必须按组写，腿不是同一个数）：`hip`/`haa`
  3σ = 1.5 rad vs ±0.60（2.5×）；`hfe` 1.5 vs ±1.20（1.25×）；spine yaw 0.75 vs ±0.60；spine pitch
  0.75 vs ±0.50。（`kfe`/`foot` 不在动作空间里——本配方的 `action.joints.legs` 只含 hip/haa/hfe。）
- 若该帧关节已坐在止档上，按 `Kp·(target − q) − Kd·q̇` 估算的 3σ 需求：hip/haa **720 N·m**（自身
  限幅 180）、`hfe` 240（180）、spine pitch 100（80）。**这是估算，不是求解器夹断**。同一张表打印
  `p_eff`＝"坐在止档上时 PD 估算需求超过该关节自身限幅"的抽样占比：hip/haa **9.89e-02**、spine pitch
  5.11e-03、`hfe` 4.37e-03、spine yaw 1.37e-03（3σ 越界本身仅 0.27%/通道）。
- 没有任何 `clip` 声明，`dof_pos_limits` 惩罚项在本配方被移除 ⇒ 早期抽样里"命令不可达"这件事
  既不裁、也不罚，只能通过动作的效果被学到。

```bat
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" rl_exp\tools\verify\action_range_check.py ^
  --task Lizard2-Flat-v3 --json "%TEMP%\action_range_lizard2_v3.json"
```
完成标记 `ACTION_RANGE_MEASURED`，退出码 0（测量，不是判决）。

### ④ 出生高度

声明 `robot.base_init_height = 1.1 m`；落定站高 **0.9082 m**（②的记录）⇒ 每回合带一次约 **0.19 m** 的
落地冲击（旧机体差距 0.16 m，家族基线已把它记为遗留项，`versions/lizard/baseline/v1/NOTES.md:54`）。

### 判定（训练前）

**这一节的边界（2026-10-09 评审后重写）**：本记录量的是**接口与初始化**四件事，它**不**构成"可以开训"的判定——
"无 blocker"要的是**安全运行域**整体验收，而那需要接触/碰撞、承重动态与训练侧行为，都不在本文。

- **各读数覆盖什么**：① 接口/声明面、② 驱动读回（求解器持有值 = 声明值）、④ 出生高度差、③ 初始动作分布对
  硬限位的越界率。四项都**没有**判到位的是：安全运行域、碰撞与接触行为、训练动力学。
- **两项待决，均在配方面**：③ 的 scale/clip（要不要裁、要不要加回限位惩罚）与 ④ 的出生高度。它们是**待决**，
  不是"可以留着训练"——"修不修都能训"这个结论本轮**没有**判据支撑，**收回**；要判它得先有安全运行域与
  训练侧的可接受性判据。
- ③ 与 ④ 与该现象的**关系未定**，不作为候选原因列出：新机体"开自碰撞时整机不推进"（
  `2026-10-09-lizard2-collision-margin-and-ankle-pass.md:53-61`）是**零动作**探针的读数，**随机动作探索不是它的
  输入**，所以 ③ 与它无关；④ 的出生高度差是否是它的输入，本轮**没有证据**（探针的出生条件未核对）。训练侧自碰撞
  关闭，不因此次读数受阻；排查该现象仍需另做输入核对。

## 证据引用

- 本记录 ③ 的读数与复读命令；落点代码 `rl_exp/tools/verify/action_range_check.py`（离线，无仿真）。
- ① ② 与 ④ 的落定值：`acceptance/records/2026-10-09-lizard2-drive-readback-audit.md`、
  `acceptance/records/2026-10-09-lizard2-static-load-demand.md`、
  `acceptance/records/2026-10-09-lizard2-leg-joint-inertia-and-gain-caliber.md`。
- 集成状态与采用边界：`acceptance/records/2026-10-08-lizard2-v3-landing.md`；
  评测入口：`acceptance/records/2026-10-09-lizard2-v3-eval-entry-and-inert-velocity-field.md`。
- 用户 2026-10-09 指示：不跑 eval，只做训练前合理性检查。

## 未覆盖边界

- **不构成"可以开训"的判定**：本记录只覆盖接口与初始化（① ② ③ ④）；**安全运行域**——接触与碰撞行为、承重
  动态、训练侧可接受性——都未验收，所以"无 blocker"这种结论不在本文能力范围内，"修不修都能训"同理。
- **初始分布不是策略行为**：训练后 actor 均值不再为 0，③ 不能外推到训练中/训练后。
- **估算不是夹断**：`Nm@stop` 是 `Kp·e − Kd·q̇` 的估算，不含求解器隐式项与接触冲量。
- **没有测"被驱动到接近限位"的工况**：③ 是抽样分布，不是贴限位占比；后者需带载荷的驱动读数。
- 单环境、单次、未做跨 seed；未跑 eval、未训练、未冻结/tag；未做 GUI 目视。
- **限位对称是当前资产的事实，不是这个工具的前提**：`Nm@stop` 与 `p_eff` 逐关节按**较近侧**止档算
  （`stop_readings`，`--self-check` 用手算的非对称例把它钉住）。本表 22 个通道的限位都对称，取哪一侧都一样；
  限位一旦改成非对称（`work/active/joint-limit-shape-and-range-pass.md`），这两个量会变，本表不适用。
- ④ 的 0.19 m 是"声明值 vs 落定值"之差，未单独量落地冲击的持续时长与峰值接触力。
