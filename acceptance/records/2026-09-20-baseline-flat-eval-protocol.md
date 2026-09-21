# baseline 平地线：v1 验收口径漏判"拖颈行走"，v2 协议与共用量表

## 适用范围

本记录判定的是 **`lizard/baseline` 线固定窗口验收的判据是否足以区分"走"与"爬到目的地"**，
以及由此新增的协议 v2 与开训前/验收共用量表。

- 对象：`ablation_harness/protocols/baseline_flat_v1.json`（旧）、`..._v2.json`（新）、
  `ablation_harness/baseline_eval.py`、`ablation_harness/baseline_metrics.py`、
  `rl_exp/tools/diagnose/diag_metrics.py`、`rl_exp/tools/verify/baseline_probe.py`。
- 被验策略：`logs/rsl_rl/lizard_baseline_v1/2026-09-20_12-23-09/model_5850.pt`（首跑 5850/15000 iter）。
- **不外推**：不覆盖其他线、不覆盖相机/视觉观测、不覆盖会飞的姿态判据；v2 阈值只按仓库已有先例取值。

## 验收条件

1. 判据必须能**独立分辨**该策略的行为，而不是靠"速度对了"推断：同一 rollout 上，前向速度与位移
   可以全对，同时机器人用脖子承重、后脚不走。
2. 同一物理量在**开训前探针**与**固定窗口验收**必须由**同一函数**测量（量纲/参考系/阈值来源一致），
   否则"开训前钉的标准"在验收时会被更弱的口径替代。
3. 门槛阈值**不得新发明**：只用仓库已钉过的判据（几何 fall；非足承重 > 10% 体重持续 > 0.5 s；
   碰撞网格最低世界 z > 0）。
4. 未测的量不得算作通过（未知 ≠ 通过），缺测量必须报错。
5. 旧协议与其历史记录**保持原义**，不重打标签、不混表。

## 结果

**旧口径漏判成立。** 同一策略、同一 seed（64 env、确定性、20 s 首回合）：

| 口径 | 结果 | 说明 |
|---|---|---|
| v1 三门槛 | `pass`（`forward_mae_mps` 0.0199 / 位移 +9.456 m / 存活 1.000） | 速度与位移确实达标 |
| 姿态与承重（诊断器实测） | 躯干前倾 26.2–26.7°；`neck_pitch` 承重 82.2 N（行驶）/ 90.3 N（零命令）= **体重的 11.6% / 12.8%**（体重 706.3 N），满足 >10% 判据的时间占比 47.6%；网格最低世界 z **−0.005 m** | 头颈蹭地承重 |
| 腿的使用（同一实测） | 逐脚 duty **0.002** / 0.31–0.37 / 0.74 / 0.68；零命令段 `lift_frac` **1.0**（全程未四脚同时着地） | 后脚几乎不走，前肢+颈拖 |

⇒ v1 的三条门槛**全对**，机器人却是"拖颈蹭行"。`head_tail_contact_force_n`（87.3 N）当时已在报告里，
但它是 head/neck/tail **合力**、无网格 z、且只是 `report_only`，没有形成判据。

**新口径（v2）** 在原三门槛上增加：几何 fall（tilt ≤ 40°、持续 0.5 s，沿用 `metrics.fall_flags` 语义）、
非足承重（≥10% 体重持续 ≥0.5 s）、非足碰撞网格最低 z 不得低于 −0.01 m；脚 duty / 脚载荷份额 / `feet_down` 作诊断。
量表与探针共用 `diag_metrics`（`tilt_cos` / `body_load_n` / `foot_ids` / `mesh_min_z` / `MESH_CHECK_BODIES`）。

**两处度量修正（2026-09-21 实测，同一跑重测）**

| 量 | 修正前（我写的） | 修正后（实测） | 原因 |
|---|---|---|---|
| 颈承重 | "82–94 N ≈ 体重 47–49%" | **82.2–90.3 N = 体重 11.6–12.8%** | `neck_frac = 0.476` 是"满足 >10% 判据的**时间占比**"，不是载荷占体重比；我把它当成了载荷比 |
| 入地深度 | "−0.052 m（入地 5 cm）" | **−0.005 m** | 原值来自 **AABB 角点**：link 系里角点与最低顶点同高，但机身一旋转角点就不再是形体上的点，世界系可低于任何真实顶点 ⇒ 约 10 倍上界。碰撞体是 `convexHull`，真值须用**网格顶点**（`diag_metrics.mesh_vertices`） |

**穿透为什么"能"发生（同一实测的配置事实）**：逐 shape 实时摩擦静/动均为 **1.0**、恢复 0.0，地面材质
同为 1.0 且 `combine=multiply` ⇒ 有效 µ ≈ 1.0（**不是无摩擦**）；`rest_offset = 0.0`、shape
`contact_offset` 实测 **3.5–14.7 mm** ⇒ 接触只在这个距离内生成，求解器以有限速度去穿透，持续下压的
接触会停在**几毫米的稳态穿插**上（实测 5 mm）。因此 v2 的几何门槛写成"不得比求解器允许的更深"，
而不是 "> 0"——后者连正常行走的脚都过不了。

**离线回归（已过，含反证）**：v1 协议下过、v2 协议下必须红的"拖颈窗口"；单帧尖峰不算违反（持续性过滤）；
缺测量必须拒答；v1 协议路径行为不变。开训前探针在同一资产上 `BASELINE_PROBE_OK`，非足网格最低 z
+0.497…+0.973 m、非足载荷 0 N ⇒ 同一把尺子训练前会红、训练后（策略改变承重路径时）也会红。

**待办**：v2 真跑尚未产出报告（该次运行在写盘前被中断，日志止于环境构建、无异常栈）——见"未覆盖边界"。

## 证据引用

- 协议与代码：`ablation_harness/protocols/baseline_flat_v2.json`、
  `ablation_harness/baseline_metrics.py`（`BaselineWindow`）、`ablation_harness/baseline_eval.py`、
  `rl_exp/tools/diagnose/diag_metrics.py`、`rl_exp/tools/verify/baseline_probe.py`。
- 回归：`rl_exp/tools/verify/test_baseline_contract.py`（`test_v2_catches_what_v1_passed`、
  `test_v2_sustain_filter_and_unmeasured_refusal`、`test_v2_refuses_a_gate_it_could_not_measure`）。
- 原始读数：v1 报告 `ablation_harness/results/baseline_flat_v1/v1/Lizard-Baseline-Flat-v1_5850_deterministic_seed123_rev2a07c88/eval.json`；
  姿态/承重读数 `rl_exp/tools/diagnose/out/baseline_v1_headcheck`（`--phases 1,2 --speeds 0.5`）。
- 前置缺陷（yaw 索引）：`rl_exp/versions/lizard/baseline/v1/NOTES.md` §验收工具缺陷。

## 未覆盖边界

- **v2 真跑未产出报告**：这是当前最大的缺口——上面"v1 漏判"的结论来自 v1 报告 + 诊断器读数两处，
  而"v2 会把该策略判 fail"目前只有**离线反证**（合成窗口）与诊断量作支撑，尚无仿真内生成的 v2 报告。
- 阈值不是本记录证明出来的：tilt 40°、非足 10%/0.5 s、网格 z>0 都取自仓库先例，其**适用性**（尤其
  40° 对"低头但不倒"的姿态是否过宽）本轮未标定——26.7° 的拖颈姿态就是**不会**触发 tilt 门槛的例子。
- 脚 duty / `feet_down` / 脚载荷份额**只是诊断**，未设门槛：阈值的先例只覆盖"四脚 > 1 N"的站立口径，
  步态口径没有先例，故按"未钉过就不设门槛"处理。
- 单 seed、单 checkpoint、单次 64-env 首回合；无 DR、无扰动、无地形变化。
- 同一缺陷类在 `rl_exp/tasks/parkour_mdp.py` 的副本**未改**（属该线记录含义问题，已记家族挂账）。
