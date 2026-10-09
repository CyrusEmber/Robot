# lizard2 驱动读回对拍：声明值 vs 求解器持有值（2026-10-09）

## 适用范围

本轮只做一件事：把 `work/closed/2026/actuator-params-audit.md` 当时列的第 ③ 项落成读数——**逐关节**回答"yaml/cfg 声明的
增益与上限，有没有成为求解器持有的值"。不改资产、不改配方、不动限位、不训练；结论不改任何数值。

被读对象：`Lizard2-Flat-Play-v3`（采用机体 `rl_exp/lizard2_candidate/lizard2_candidate.urdf`，30 关节，单环境）。

## 验收条件

- 读数取自**引擎侧 readback**，不是 cfg 自述：`ArticulationData.joint_stiffness` / `joint_damping` /
  `joint_effort_limits` / `joint_vel_limits`，在 data buffer 建立时从 PhysX view clone
  （`get_dof_stiffnesses` / `get_dof_dampings` / `get_dof_max_forces` / `get_dof_max_velocities`，
  `isaaclab_physx/isaaclab_physx/assets/articulation/articulation_data.py:1508-1537`），发生在 articulation
  把 actuator cfg 交给求解器**之后**。
- 逐关节比，不按组比：组 cfg 只说明"要求了什么"。
- `asked = None`（本 fork 丢弃该字段）**不算不一致**，但必须被报出来（否则每次运行都"红"而失去意义）。
- 不据此声称策略行为或力矩饱和。

## 结果

任务 `Lizard2-Flat-Play-v3`，30 关节全部被某个 actuator 组认领（无遗漏）；`stiffness` / `damping` /
`effort_limit` 三项**逐关节与声明完全一致**（容差 1e-6）：

| 组 | 关节数 | `stiffness` asked→held | `damping` | `effort_limit` | `velocity_limit` |
|---|---|---|---|---|---|
| legs | 16 | 800 → 800 | 40 → 40 | 180 → 180 | asked=none → **5.939047009418473e+36** |
| feet | 4 | 200 → 200 | 12 → 12 | 70 → 70 | asked=none → **5.939047009418473e+36** |
| spine | 10 | 400 → 400 | 20 → 20 | 80 → 80 | asked=none → **5.939047009418473e+36** |

两条结论，都是**读数**不再是推断：

1. **effort 的赢家是 cfg，覆盖到的关节一个不剩**：30/30 关节的求解器持有值等于 cfg 声明值（120/150/30 若生效，
   这里会显示 URDF 的那一列）。⇒ 在覆盖完整的前提下，URDF 的 `effort` 列确实不进驱动；但这条只在"覆盖完整"时成立，
   不是"URDF 从不被消费"。
2. **velocity 两处都没进引擎**：yaml 声明的 10/6/4 被 fork 丢弃（`actuator_pd.py:81-91`），URDF 自带的 8/6/4 也
   没有成为驱动上限——求解器持有的是 **5.939047009418473e+36**（PhysX 的"无上限"默认值），30 个关节一致。
   本 fork 自己的告警原文即此意："Previously, although this value was specified, it was not getting used by
   implicit actuators. Since this parameter affects the simulation behavior, we continue to not use it."
   旁证：同一场景初始化打印的 joint info 表里 Velocity Limits 也是 `5.9e+36`、Effort Limits 为 `80/180/70`，
   与 readback 一致。

## 复读命令与结果

解释器 `E:\IsaacLab\env_isaaclab\Scripts\python.exe`（本机 `paths.yaml`），从 `E:\Robot` 执行：

```bat
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" rl_exp\tools\verify\check_actuator_budget.py ^
  --drive-audit --task Lizard2-Flat-Play-v3 --json "%TEMP%\drive_audit_lizard2_v3.json"
```

本机该次报告落在 `C:\Users\yanke03\AppData\Local\Temp\drive_audit_lizard2_v3.json`（**机器本地，不进仓**）。
完成标记 `DRIVE_AUDIT_MEASURED`，退出码 0（这是测量，不是判决）。

## 证据引用

- 事项与判据：`work/closed/2026/actuator-params-audit.md`。
- 生效限幅与响应曲线的首测：`acceptance/records/2026-09-22-lizard2-actuator-capability.md`。
- 承重期逐关节饱和占用与"被裁剪拿走多少驱动"的口径：`acceptance/records/2026-09-23-lizard2-v1-gait-skate.md`（⑨–⑫）。
- 落点代码：`rl_exp/tools/verify/check_actuator_budget.py`（`run_drive_audit` / `--drive-audit`）。
- yaml 侧归属闸（覆盖唯一性）：`rl_exp/tools/verify/check_dr_parity.py` 第 5 条（同日的 `--strict --self-test` 通过）。

## 未覆盖边界

- **readback 是 data-init 快照**：之后由 DR 写增益（`write_joint_stiffness_to_sim_index`）不会刷新它。lizard2 当前
  没有增益随机化，所以这里等于运行时值；有随机化的线要另判。
- **只跑了 v3**：lizard2 的 dev 与旧线未跑；结果不能外推到别的任务或家族。
- **readback ≠ 行为**：它说驱动的参数是什么，不说策略是否用到、也不说力矩是否被夹断；层 1/2 的 `pd_tau` 仍是估算。
- **数值差异是否"应该相等"仍无判据**：`effort` 列在 URDF 与 cfg 之间不一致（120/150/30 vs 180/180/70）是不是问题，
  取决于目标速度带（R4）带来的力矩需求，本轮不判。
- 单环境、`num_envs=1`；多环境下的 per-env 差异未覆盖。
