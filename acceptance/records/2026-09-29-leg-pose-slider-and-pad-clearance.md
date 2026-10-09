# 摆姿器落地，与"名义机身高度下零位四掌不共面"这一读数（2026-09-29）

## 适用范围

- 本次新增两件**仪器**：`rl_exp/tools/diagnose/pose_slider.py`（交互摆姿，固定机身/无重力/无接触）与
  `rl_exp/tools/verify/check_leg_reachability.py` 的读数面（`chain_frames` / `pad_state` / `joint_effect` /
  垫网格顶点与三角面）。
- 被读对象：`versions/lizard2/lizard2.urdf`（四腿各 5 关节）与家族声明树内的
  `versions/lizard2/meshes/collision/*_foot_collision.obj`。
- 本次给的是仪器本身与它产出的**第一批读数**；**不含**可达性扫描（A/B/C 三段，归本记录服务的在办事项 ①）。
  一切读数都是运动学的：机身固定且水平、无重力、无接触，因而不含承重、平衡、行走。

## 验收条件

1. 口径必须由**手算事实**看守，不接受"再跑一遍同一段矩阵乘"。已落进 `--self-check` 的有五条：
   零位垫原点 = 各关节 origin 之和；绕竖直髋轴转 1/4 圈 = 绕髋轴转该点；**竖直髋轴不改变倾角**
   （`|d(tilt)/dq| < 1e-9`）；抬机身 h 即抬每个垫顶点 h；`|dp/dq|` = 该关节轴到垫原点的垂距（力臂）。
2. **仪器不得复制数学**：滑块侧只做呈现，FK、倾角、离地高度、导数全部在 stdlib 的
   `check_leg_reachability.py` 里，两个消费者（今后含扫描）共用一份。
3. 无头可跑：`--self-check` 必须在主机 python（无 matplotlib）与 `env_isaaclab` python 下都绿；
   GUI 路径另做一次"建图 + 回调 + 存读"的冒烟（`out/` 同类的一次性脚本，不入仓）。

## 结果

### ① 口径自检（`python rl_exp\tools\verify\check_leg_reachability.py --self-check`）

| 腿 | 垫法线（foot 系） | 偏离 link 的 −z | 零位倾角 | hip 力臂 | 最低顶点（base 0.900 m） |
|---|---|---|---|---|---|
| lf | (0.0000, +0.0254, −0.9997) | 1.45° | 1.45° | 0.4679 m | −0.0177 m |
| rf | (0.0001, −0.0254, −0.9997) | 1.45° | 1.45° | 0.4680 m | −0.0178 m |
| rl | (0.0000, +0.0254, −0.9997) | 1.45° | 1.45° | 0.4513 m | −0.0275 m |
| rr | (−0.0000, −0.0254, −0.9997) | 1.45° | 1.45° | 0.4679 m | −0.0177 m |

**1.45° 与 `2026-09-29-lizard2-pad-leveling-unreachable` ① 的 1.45° 相同**（后者从仿真侧的同一批网格拟合）
⇒ 离线口径与仿真侧同源，不是另一套几何。力臂与 `2026-09-22-lizard2-stride-at-load` 的髋 arm 0.490–0.494 m
不同口径（那是"脚掌中心垂距"，这里是"轴到垫原点"），两者不可互换引用。

### ② 名义机身高度下，URDF 零位四掌不共面

`base_z = 0.912 m`（`2026-09-22-lizard2-stride-at-load` 的零动作落定高度）下，零位四腿读数
（摆姿器 `reset` 后的同一屏）：最低顶点 lf **−0.0057** / rf **−0.0058** / rl **−0.0155** / rr **−0.0057** m
（四腿都记为"入地"），四腿倾角同为 1.45°。

⇒ **`rl` 比另三只低 9.8 mm**：四掌共面不是零位，而是一个要在（机身高度 × 关节角）里解出来的姿态 ——
这正是在办事项 ①A 的第一问。**本记录不判"是不是缺陷"**：网格与关节原点是两笔账
（`2026-09-23-lizard2-leg-chains-not-mirrored`），且共面与否要先有容差需求（① ②）。

### ③ 摆姿器的读数面（已跑通的例）

末次触碰的关节会给出：**轴在 base 系**、`|dp/dq|`（垫原点每弧度走多远）、垫绕哪条轴转多少（`dn/dq`）、
以及 `d(tilt)/dq`。冒烟里按到的两例：

| 操作 | 读数 |
|---|---|
| `lf hip +0.55 rad`（机身 1.05 m） | 垫原点自零位移动 (−0.245, −0.069) m，最低顶点 +0.1323 m，倾角 1.45°（髋是竖轴 ⇒ 不动倾角） |
| `rl foot +0.90 rad`（越限、范围已在内存里放宽） | 垫绕 [−0.62 0.00 +0.78] 以 1.000 rad/rad 转、`d(tilt)/dq ≈ +57.3 deg/rad`、倾角 51.58°，并被标注 `OUT OF RANGE: foot +0.90 > [−0.50,+0.50]` |

第二行的 57.3 deg/rad 是**构造性**的（零位附近倾角≈0，倾角是"有向偏差的绝对值"）⇒ 不能读成
"踝关节能纠 57°/rad"；换到承重姿态（板倾 40–50°）后这个导数才是有意义的那一个，而这正是
`2026-09-29-lizard2-pad-leveling-unreachable` ③ 量的情形。

## 判定

1. **仪器成立**：五条手算事实 + 与仿真侧 1.45° 的对齐 ⇒ FK、垫网格、倾角、离地四个量的口径可复算，
   且 `--self-check` 在两个解释器下都绿（主机 python 无 matplotlib 也能跑）。
2. **第一批几何事实**：名义机身高度下，URDF 零位无法四掌共面着地（`rl` 低 9.8 mm）。它把 ①A 从
   "能不能"推进到"在哪个高度/角度组合下"，但**没有**回答 ①A。
3. **本仪器不能判的**：承重、平衡、稳定行走（无重力无接触）；"腿收得很怪"是判据不是读数 ——
   手摆只能找到点，曲线归 ① 的扫描。扫描侧不再重复数学：`pad_state`（倾角/离地）与 `joint_effect`
   （含 `d(tilt)/dq`）就是它要用的那两个函数。
4. 与既有读数的关系：③ 的"踝在其行程内只买得到 1–3°"现在是**离线可复现**的读数面，
   但那条结论的权威副本仍是 `2026-09-29-lizard2-pad-leveling-unreachable`（逐帧实测），本记录不替代它。

## 证据引用

- 工具（入仓）：`rl_exp/tools/diagnose/pose_slider.py`、
  `rl_exp/tools/verify/check_leg_reachability.py`；文件路由见 `FILEMAP.md` 两行。
- 复读（**必须从仓根 `<REPO>` 发起**；`rl_exp` 不复制进 IsaacLab 根，见 `README.md` 摆位节）：
  `cd /d <REPO>` 后 `python rl_exp\tools\verify\check_leg_reachability.py --self-check`、
  `<ROOT>\env_isaaclab\Scripts\python.exe rl_exp\tools\diagnose\pose_slider.py`（GUI）；
  任意 cwd 用模块式 `<ROOT>\env_isaaclab\Scripts\python.exe -m rl_exp.tools.diagnose.pose_slider`；
  加 `--self-check` 则无界面。
- 冒烟（机器本地、不入仓；**2026-10-09 已删，见文末勘误**）：`rl_exp/tools/diagnose/_tmp_pose_slider_smoke.py` —— Agg 建图 + 21 滑块 +
  3 按钮 + 越限标注 + 存/读/复位往返 + TkAgg 画布构建（`FigureCanvasTkAgg`）。
- 相关读数：`2026-09-29-lizard2-pad-leveling-unreachable`（踝轴与行程的逐帧读数）、
  `2026-09-22-lizard2-stride-at-load`（机身高度与髋 arm）、
  `2026-09-28-lizard2-foot-hull-and-asset-isolation`（usda 内联点 ↔ `.obj`，最差 0.244 mm）。
- 在办事项：`work/active/pad-flat-requirement-and-ankle-axis.md` ①。

## 未覆盖边界

1. **机身固定且水平**：倾角读的是"垫法线与机体 −z"，机体一有俯仰该读数即失真（工具里没有俯仰自由度）。
2. 碰撞几何取自家族声明树里的 `.obj`；它与 usda 内联点的一致性由资产记录承担（最差 0.244 mm），本记录不重测。
3. 垫法线是**拟合值**（最低 2 mm 带）⇒ ±2° 以内的比较不作数。
4. 自碰撞、限位外的真实可行性、执行器能力都不在；GUI 的**鼠标交互本身**只有人眼验证过（建图、回调、
   存读、TkAgg 画布是自动跑过的）。
5. 零位读数只对这一个 URDF 有效；资产换代后 `--self-check` 会因 rpy 守卫或网格面数变化而报出。

## 勘误（2026-10-09，仓根 `_tmp_*` 清仓）

本文提到的冒烟脚本 `rl_exp/tools/diagnose/_tmp_pose_slider_smoke.py` **未入仓，已于 2026-10-09 随 64 个
`_tmp_*` 删除**（原委见 `2026-10-09-repo-architecture-review.md` 的善后节与
`rl_exp/tools/verify/OFFLINE_CHECKS.md` §6）⇒ 那条"冒烟"路径作废。**本记录的两支工具都在仓内**
（`pose_slider.py` / `check_leg_reachability.py`），复读不受影响，只需把冒烟那一项换成它们各自的
`--self-check`（无界面，任意 python），读数与判据不变。缺失的只是"GUI 建图 + 21 滑块 + 三按钮"那条
端到端冒烟，要恢复得按本节判据重写并落到 `rl_exp/tools/diagnose/`（别再造一次性脚本）。
