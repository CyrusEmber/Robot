# 腿链 FK 口径修补：有向朝面、机体姿态、候选链（2026-09-30）

## 适用范围

把 `rl_exp/tools/verify/check_leg_reachability.py` 的读数口径修到能承担"结构候选对比"：掌面朝向分有向/无向、
机体姿态进世界系读数、候选机体与网格绑定、FK 载得进候选新增关节。只改**离线工具与它的自检**；未改任何
URDF/USD/网格/限位/配方，未训练、未评测，未构造任何采用候选。目标姿态序列与容差仍缺（见
`work/active/joint-limit-shape-and-range-pass.md` ①），本记录不提供它们。

## 验收条件

- 反例能**使验收失败**：旧口径下的翻掌实例必须被拒，且"把口径改回错的"必须让自检变红。
- 读数归属同一机体：链与网格不得取自两棵树。
- 读数在世界系：机体 roll/pitch 不得被当成不存在。
- 结论只覆盖**离线几何**；不冒称目标动作、碰撞、动力学或整盒安全。

## 结果

### ① 口径修补（四项）

| 项 | 旧口径 | 现口径 | 落点 |
|---|---|---|---|
| 掌面朝向 | `fold_tilt` 取 `abs`，翻掌读成 0°；无验收函数 | `fold_tilt` 仍为**无向**折腿量（不能作验收）；新增 `faces_down(facing_cos, tol)` 与 `pad_state()['facing_cos']`（有向：+1 朝下 / −1 朝上） | `check_leg_reachability.py` 的 `faces_down` / `pad_state` |
| 机体姿态 | 假设机体水平（`base_link` 的 −z 即世界向下） | `pad_state(..., base_rpy)`：法线与顶点都过机体姿态；`tilt_deg` = 到世界下方向的有向夹角（0 朝下 / 180 朝上） | 同上 |
| 机体绑定 | `_pad_mesh` 硬编码 `versions/lizard2/meshes/collision` | `pad_mesh(urdf, leg)` 读 URDF 自己 `<leg>_foot` 的 `collision` 网格，相对 URDF 所在目录解析；URDF 离开自己的网格树则**报错退出** | 同上（复用 `check_joint_layout.py` 的既有读法） |
| 候选链 | 固定五关节名表，非零 `rpy` 直接拒绝 | `chain_joint_names` 自 `<leg>_foot` 沿 URDF 树向上遍历（到首个不带 `<leg>_` 前缀的父 link 停），`load_chain` 按树读；关节 `rpy` 按 URDF 次序参与合成 | 同上 |

另加 `hinge_vs_body_z(chain, angles, index)`：铰链轴在 base 系与机体 z 的夹角。**90° = 该关节的运动平面
不可能离开"包含机体 z 的平面"**——这正是映射记录里那条结构不变式的可测形式。

### ② 读数（本次运行）

自检命令：`python rl_exp\tools\verify\check_leg_reachability.py --self-check`，exit 0。

| 腿 | 零位掌面法线 | 法线离 link −z | 零位 facing | 零位最低顶点 | 髋力臂 | haa/hfe/kfe 轴 vs 机体 z |
|---|---|---:|---:|---:|---:|---|
| lf | (+0.0000, +0.0254, −0.9997) | 1.45° | +1.000 | −0.0177 m | 0.4679 m | 90.0000/90.0000/90.0000 |
| rf | (+0.0001, −0.0254, −0.9997) | 1.45° | +1.000 | −0.0178 m | 0.4680 m | 90.0000/90.0000/90.0000 |
| rl | (+0.0000, +0.0254, −0.9997) | 1.45° | +1.000 | −0.0275 m | 0.4513 m | 90.0000/90.0000/90.0000 |
| rr | (−0.0000, −0.0254, −0.9997) | 1.45° | +1.000 | −0.0177 m | 0.4679 m | 90.0000/90.0000/90.0000 |

**翻掌反例（review 记录里那条，四腿都在限位内）**：`σ = π + atan2(n_y, −n_z)`，`q = (0, 0.6, 1.2, σ−1.8, 0)`。
`fold_tilt` 读 0.00–0.01°（无向），`facing_cos` 读 **−1.000** ⇒ `faces_down(..., 10°)` 与 `fold_tilt_cos`
两条路径**都拒**。"平放"与"翻面平放"从此不再是同一个读数。

**候选链（合成夹具，lf，插入一条绕股骨的旋转）**：树遍历得 6 关节链（`hip, haa, fem, hfe, kfe, foot`），
零位与现腿链逐位一致（<1e-9）；`fem = 0.5 rad` 时垫原点移动 **0.1959 m**；下游 `hfe` 的轴离开 90° 达
**23.6°**（读作 66.4°）。现资产三铰链在全行程恒 90.0000°。

**`--compare` 自一致性**：同一 URDF 与自身对比，两行逐字段相同（243 poses、垫 span x 1.115 / y 1.310 /
z 1.107 m、facing −0.973..+1.000、108 翻面、3/243 落在 10° 容差内、铰链最小 90.0000°）；
`rl` 对合成候选的同一张表（3 值/关节，机体 z 0.9 m，容差 10°）与上表逐字段相同，候选的**额外关节单独报**：
`fem` 自身轴静置时离机体 z 55.4°，单独扫 −0.60..+0.60 把最差铰链（`hfe`）压到 62.3083°。

### ③ 反证（`--break-test`）

`python rl_exp\tools\verify\check_leg_reachability.py --break-test` → `BREAK_TEST_OK (5 perturbation(s), every one caught)`：

| 扰动 | 触发的断言 |
|---|---|
| `faces_down` 取绝对值（旧口径） | `a pad on its back was accepted` |
| 关节 `rpy` 当零处理 | 机体 roll 的手算恒等（facing 0.8851/0.9831） |
| `pad_state` 丢掉 `base_rpy` | 同上 |
| 链取自资产五关节名表而非树 | 候选链零位与现腿链不等 |
| URDF 离开自己的网格树 | `pad_mesh` 报错退出（拒绝借用他机体网格） |

## 证据引用

- 工具（入仓）：`rl_exp/tools/verify/check_leg_reachability.py`（本次新增 `chain_joint_names` / `pad_mesh` /
  `faces_down` / `hinge_vs_body_z` / `break_test`；`pad_state` 增 `base_rpy` 与 `facing_cos`；`_matrix` 增 `rpy`）。
- 消费者同步：`rl_exp/tools/diagnose/pose_slider.py`（`pad_vertices`/`pad_faces` 改带 URDF）+ 其读数加 facing；
  该脚本 `--self-check` 本次通过（FK 自检 + clamp + JSON 往返）。
- 触发本轮的事实与前一轮反例：`acceptance/records/2026-09-30-lizard2-joint-limit-plan-review.md`（第 3 条翻掌）、
  `acceptance/records/2026-09-30-lizard2-leg-to-anatomy-mapping.md`（结构表达限制）。
- 复读命令：
  `python rl_exp\tools\verify\check_leg_reachability.py --self-check`、
  `--break-test`、
  `--compare <候选>.urdf --leg rl --samples 3 --tol 10`。
- 文件路由：`FILEMAP.md` 的 `check_leg_reachability.py` 行（本轮同步）。

## 未覆盖边界

- **候选链是合成夹具**：由资产自身 XML 插入一条绕股骨的旋转得到（夹具进自检、不进仓），不是设计资产、
  不是采用候选；它证明的是"FK 载得进候选新增关节"，不是"该轴值得加"。
- **`--compare` 只读结构**：同一机体姿态/高度/容差下的可达性与平面关系；不校验两机体的骨长是否相同、
  不含碰撞与动力学、不含目标序列。可达集更大不是结论。
- **网格绑定的包含性断言是后备闸**：本资产上旧硬编码树与 URDF 自己那棵树重合，故"重新硬编码回去"不会
  触发它；真正会响的是"URDF 离开网格树"（报错退出）。
- **记录格式仍无姿态列**：`--frames <baseline-frames-3>` 那条路径照旧假设机体水平（`fold_reading` 未改），
  所以"机体带 roll/pitch 而掌面水平于世界"的旧说法在这条读数上仍无法验证。
- **本工具不在 `run_offline_checks.bat` 的检查表内**（该表是显式清单 + 数量棘轮），本轮的自我验证靠
  `--self-check` / `--break-test` 手动跑 + 本记录，不靠套件。
- 未做仿真侧 FK 逐位核对（需 Isaac），未做四腿连续轨迹、碰撞、限位余量或动力学；未改任何资产与配方。
