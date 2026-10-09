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
0.546，腿组最坏 0.198。见 `2026-10-09-lizard2-static-load-demand.md`。

### ③ 初始动作分布 vs 硬限位（本记录唯一新读数）

探索标准差取任务自己的 runner cfg（`actor.distribution_cfg.init_std = 1.0`），目标 = `scale × N(0,1)`，
默认目标为 0（本配方全 30 关节零默认角）。逐关节越界概率：

| 通道组 | 通道数 | scale | 硬限位 [rad] | 越界概率 |
|---|---|---|---|---|
| `hip` / `haa` | 8 | 0.50 | ±0.60 | **0.230** |
| spine pitch | 5 | 0.25 | ±0.50 | 0.0455 |
| `hfe` | 4 | 0.50 | ±1.20 | 0.0164 |
| spine yaw | 5 | 0.25 | ±0.60 | 0.0164 |

- **22/22 通道的 3σ 目标都在限位之外**（腿 1.5 rad vs 止档 0.6；spine pitch 0.75 vs 0.5）。
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

- **无 blocker 级问题**：接口、驱动值、静站占用三项都有读数且不构成问题；离线 48/48 绿；v3 的评测入口已就位。
- **两项待决，均在配方面**：③ 的 scale/clip（要不要裁、要不要加回限位惩罚）与 ④ 的出生高度。两者都
  不是"不修不能训"的量级，但都改物理 ⇒ 按 `versioning.mdc` 走版本，不在开训前顺手改。
- ③ 与 ④ **交互于同一现象**：新机体"开自碰撞时整机不推进"的机制未查明（
  `2026-10-09-lizard2-collision-margin-and-ankle-pass.md:53-61`），而落地冲击与早期目标越界恰好是
  该现象的两个候选输入。训练侧自碰撞关闭，不因此次读数受阻，但排查该现象时先把这两项当怀疑对象。

## 证据引用

- 本记录 ③ 的读数与复读命令；落点代码 `rl_exp/tools/verify/action_range_check.py`（离线，无仿真）。
- ① ② 与 ④ 的落定值：`acceptance/records/2026-10-09-lizard2-drive-readback-audit.md`、
  `acceptance/records/2026-10-09-lizard2-static-load-demand.md`、
  `acceptance/records/2026-10-09-lizard2-leg-joint-inertia-and-gain-caliber.md`。
- 集成状态与采用边界：`acceptance/records/2026-10-08-lizard2-v3-landing.md`；
  评测入口：`acceptance/records/2026-10-09-lizard2-v3-eval-entry-and-inert-velocity-field.md`。
- 用户 2026-10-09 指示：不跑 eval，只做训练前合理性检查。

## 未覆盖边界

- **初始分布不是策略行为**：训练后 actor 均值不再为 0，③ 不能外推到训练中/训练后。
- **估算不是夹断**：`Nm@stop` 是 `Kp·e − Kd·q̇` 的估算，不含求解器隐式项与接触冲量。
- **没有测"被驱动到接近限位"的工况**：③ 是抽样分布，不是贴限位占比；后者需带载荷的驱动读数。
- 单环境、单次、未做跨 seed；未跑 eval、未训练、未冻结/tag；未做 GUI 目视。
- ④ 的 0.19 m 是"声明值 vs 落定值"之差，未单独量落地冲击的持续时长与峰值接触力。
