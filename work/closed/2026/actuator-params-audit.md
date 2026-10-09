---
id: actuator-params-audit
title: 执行器参数（PD 增益与力矩上限）的出处、校核与判据
scope: rl_exp/tasks, rl_exp/versions/lizard2, rl_exp/lizard2_candidate, rl_exp/tools/verify, acceptance/records
status: done
landing: rl_exp/versions/lizard2/main/v3/main_params.yaml, rl_exp/tools/verify/check_dr_parity.py, rl_exp/tools/verify/check_actuator_budget.py, rl_exp/tools/verify/check_leg_reachability.py
close_when: 覆盖断言与破坏测试在看守，来源对拍、静站承重基线与增益口径各有记录（均已达成）；**只剩阈值依据**一项（依赖 `joint-limit-shape-and-range-pass` 的目标速度带 R4）——它被满足，或经用户明确接受"阈值随 R4 落地时再回填"即可关闭；承重/接触已声明范围外（见「边界」）。未完部分另立具名活跃事项
outcome: 四件读数全部落地且可复读：② 覆盖唯一性断言折进 `check_dr_parity.py` 第 5 条（漏配/重叠各一条破坏测试，不新增条数）；③ 引擎侧驱动 readback 对拍（30/30 关节的求解器持有值 = cfg 声明值，readback 源在 `isaaclab_physx/.../articulation_data.py:1508-1537`）；④ 静站承重基线（六条结论，含落定判据与统计量）；⑤ 增益口径（14 个声明构型、反射惯量 + 局部 ω_n/ζ，含三处口径更正）。⑥ 决策出口（改 yaml §B/§A、改 URDF §A）已写明。**唯一未完的动作**是"增益是否过大"的**阈值依据**——它要目标速度带（R4），已作为**下游动作**挂在 `joint-limit-shape-and-range-pass`；承重/接触构型经用户 2026-10-09 明确为**范围外**（要另做 sim 侧变体，触发条件写在「边界」）。原 `next` 不保留：其余各条已转成记录与断言
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
- **范围外：承重/接触下的构型**（2026-10-09 定，用户确认）：本项的惯量口径是**离线、无接触**的关节链读数，按定义不含接触约束（`reflected_inertia` 没有接触力这个输入）。"承重下惯量够不够"要另做一套 **sim 侧变体**（接触力 + 惯量耦合），那是另一个事项，不是本项欠的读数；触发条件 = 有人要拿这条读数判承重。
- 增益随机化（执行器不确定性）不在 lizard2 的 DR 里；本项只记录这个缺口，不替它做决定。
