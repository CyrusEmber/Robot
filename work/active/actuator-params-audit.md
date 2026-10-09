---
id: actuator-params-audit
title: 执行器参数（PD 增益与力矩上限）的出处、校核与判据
scope: rl_exp/tasks, rl_exp/versions/lizard2, rl_exp/lizard2_candidate, rl_exp/tools/verify, acceptance/records
status: open
landing: rl_exp/versions/lizard2/main/v3/main_params.yaml, rl_exp/tools/verify/check_dr_parity.py, rl_exp/tools/verify/check_actuator_budget.py, rl_exp/tools/verify/check_leg_reachability.py
next: ① 三层来源对拍读数（URDF `<limit>` 元数据 / USD 求解器属性 / 构建后逐关节值）落一份 record——能站住的只有"此配方覆盖了 effort ⇒ 被覆盖关节的 URDF effort 让位"与"旧 `velocity_limit` 字段未进求解器"，不写"URDF 限幅从不被消费"，也不写"只有 yaml 一处决定"。② 校核（已落地）：`check_dr_parity.py` 第 5 条断言"每个 URDF 关节被 yaml 组恰好覆盖一次"，漏配与重叠各一条破坏测试；不新增条数（`MAX_CHECKS` 棘轮已满）。③ **赢家对拍（已落地）**：覆盖唯一性只证归属、不证值进了求解器 ⇒ 逐关节读**引擎侧 readback**（`data.joint_effort_limits` / `joint_vel_limits` / `joint_stiffness` / `joint_damping`，来自 PhysX `get_dof_max_forces` / `get_dof_max_velocities` / `get_dof_stiffnesses` / `get_dof_dampings`，在 data-init 时 clone，`isaaclab_physx/.../articulation_data.py:1508-1537`）与各 actuator 声明对拍，落点 `check_actuator_budget.py --drive-audit`；v3 的读数与两条结论见 `acceptance/records/2026-10-09-lizard2-drive-readback-audit.md`。cfg 值只说明"要求了什么"，readback 才说明"拿到了什么"；readback 也不说明策略是否用到它（那是行为，不是驱动）。④ **静站层（已落地）**：`check_actuator_budget.py --static-only`——逐关节对自己的求解器侧限幅取 PD 估算占用，口径（复用 ⑫ 的逐关节限幅与估算式 + 落定/复位/掉地剔除 + 读数不叫"饱和"）写在 `run_static` 的 docstring；v3 的读数与三条结论见 `acceptance/records/2026-10-09-lizard2-static-load-demand.md`。静站只校核承重基线，不关闭目标速度带下的执行器能力问题。⑤ **增益口径（已落地，阈值仍缺）**：有效惯量 = 关节轴上的**反射惯量**（零位、下游链冻结、基座视为固定且差额未量化），频率侧口径 = 与**物理步 200 Hz / 控制周期 50 Hz** 比（不拿 Nyquist；执行器带宽无数据表 ⇒ 不给数字），`ζ` 只作局部单自由度读数、不判整机稳定；读数与三条结论见 `acceptance/records/2026-10-09-lizard2-leg-joint-inertia-and-gain-caliber.md`（其中一条：同一套 Kd/Kp=1/20 下 ζ 跨关节差 6.4 倍 ⇒ 要统一阻尼改的是逐关节 Kd）。**仍缺**：阈值依据（要 R4 的目标速度带）；构型只扫了 11 个"单关节到自身限位"的极值，多关节同时摆开与承重/接触未覆盖；本轮不判"增益过大"。⑥ 决策出口按改动面分两条：改 **yaml**（PD/上限）——未冻结走 `.codemaker/rules/versioning.mdc` §B 修订、已训走 §A；改 **URDF**（限位/effort 列）= 资产内容变更，资产锁只在首次冻结写一次 ⇒ §A。本轮只出候选与判据
close_when: 覆盖断言与破坏测试在看守、来源对拍与静站承重基线各有记录（已达成）；增益判据的有效惯量口径、动态工况与阈值依据定清并经用户评审，或明确不启用增益判据；数值是否改动的决策出口给出结论。未完部分另立具名活跃事项后关闭
depends_on: joint-limit-shape-and-range-pass
evidence: acceptance/records/2026-09-22-lizard2-actuator-capability, acceptance/records/2026-09-23-lizard2-v1-gait-skate, acceptance/records/2026-10-09-lizard2-drive-readback-audit, acceptance/records/2026-10-09-lizard2-static-load-demand, acceptance/records/2026-10-09-lizard2-leg-joint-inertia-and-gain-caliber
---

## 当前情况

执行器参数（`stiffness` / `damping` / `effort_limit`）的数值来自三处，读者要分清哪一层是哪一层：

- 本配方覆盖到的关节：`effort_limit` 由 yaml 的 `actuators:` 块决定（implicit actuator 把 cfg 值交给求解器，`actuator_pd.py:60-67`），URDF `<limit effort>` 在这一层让位——已对拍证实（30/30 关节的求解器持有值 = cfg 声明值），读数见 `evidence` 的 drive-readback 记录；
- URDF 逐关节自带 `effort` / `velocity`（`<limit>` 属性），与 cfg 组值不同；**未被任何组覆盖的关节会留着它**——这正是"覆盖唯一性要有断言"的理由；
- yaml 声明的 `velocity_limit` 被本 fork 丢弃 ⇒ 未进求解器（`actuator_pd.py:81-91`）；同一读数显示 URDF 自带的 `velocity` 也**没有**成为驱动上限（两处都不生效，驱动上是 PhysX 的"无上限"默认值），数值见该记录。

"生效 cfg" 不等于引擎实际属性：三者之间还隔着 USD 求解器属性与构建后的逐关节值，对拍归 `next` ③。

这套数值没有推导记录（无电机规格、无按机体质量与几何的力矩校核），唯一记录是"实测生效值是多少"。判"合理"需要力矩需求，而需求的靶子（目标速度带 R4）归 `joint-limit-shape-and-range-pass`。

## 边界

- 本项不改资产、不改配方、不动限位；只做读数、断言与判据。
- **数值差异本身不设闸**（差异以 readout 打印），闸只守**归属**——哪个组被声明为负责该关节、且只被一个组声明（覆盖唯一性）；那是 yaml 侧的说法，不叫"赢家定案"：赢家要引擎侧 readback 才算，见 `next` ③。判"两个数是否该相等"需要需求，需求还没定。
- **静站只校核承重基线**，不关闭目标速度带下的执行器能力问题；它是下限读数，不是能力验收。
- 增益随机化（执行器不确定性）不在 lizard2 的 DR 里；本项只记录这个缺口，不替它做决定。
