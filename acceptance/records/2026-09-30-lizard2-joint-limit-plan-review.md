# lizard2 限位方案评审与映射勘误（2026-09-30）

## 适用范围

核对当前腿链工具与 `2026-09-30-lizard2-leg-to-anatomy-mapping.md`，记录本轮几何反例与方案取舍。仅改文档；没有改资产、工具、限位或训练配方。当前推进方案唯一正文在 `work/active/joint-limit-shape-and-range-pass.md`。

## 验收条件

- 当前几何自检与设计验收分开；前者通过不能替代仿生或承载验证。
- 反例从 URDF 与现网格直接复算，给出姿态、坐标约定与复读代码。
- 不从局部运动能力推出四足支撑成立，不从常用轨迹极值推出硬限位。
- 目标定结构、结构定候选范围；新增轴与对话临时角度都不能未经验证成为定案。

## 结果

### 几何复算

`check_leg_reachability.py --self-check` 本轮 exit 0；只确认当前几何关系与钉住的事实，未做新的仿真对齐。

1. **hip 不是唯一影响足端前后位置的轴。** lf 姿态 `(hip, haa, hfe, kfe, foot) = (0.4, 0.2, 0.6, -0.3, 0.0)` rad 在现区间内。base 系前后方向导数如下，单位 m/rad：

   | 轴 | dp_x/dq |
   |---|---:|
   | hip | -0.058184 |
   | haa | +0.294109 |
   | hfe | +0.156314 |
   | kfe | +0.049968 |
   | foot | 0.000000 |

   这是反驳“唯一轴/各姿态力臂最大”的实例，不说明其他轴能独立替代 hip 的方位控制。

2. **姿态公式符号。** lf 只令 haa 为 +0.3 rad 时，FK 旋转矩阵 `R[1][2] = +0.295520`；标准右手 `Rx(+0.3)` 为 -0.295520。三铰链沿 −X，完整姿态应写 `Rz(hip) Rx(-σ) Ry(foot)`。
3. **翻掌被无方向倾角折叠。** 令 `σ = π + atan2(ny, -nz)`，lf 姿态为 `(0, 0.6, 1.2, σ-1.8, 0)` rad，所有角都在现限位内。`fold_tilt()` 返回 0°，`pad_state()['tilt_deg']` 返回 180°。这说明当前前者不能直接验掌面朝下；并不证明该姿态避碰、触地或能承重，也不单凭此例判定整个限位盒不可用。

### 本轮方案取舍

用户指出目标是巨蜥式动作，现限制与动作表达“像狗”。据此优先用可测的骨段姿态与接触轨迹定义仿生目标；视觉判断不是结构证据。后肢股骨长轴旋转进入优先结构候选，前肢肩部另映射；尚未批准采用、未取得目标三维序列或冻结容差。

对话曾建议 hfe 伸展端取 ±0.90 rad 作为临时实验候选。该表随后撤回“巨蜥推荐限位”的定位：其余沿用旧值不等于合理；本轮不采用任何数值。下一步先比较结构表达，再验证连续轨迹、反推常用范围/硬边界并做动力学。

掌面平放、小腿竖直与 σ 近零不再默认作为巨蜥目标；接触要求按目标、阶段、机体姿态与地形明示。奖励、动作目标约束、终止与物理硬约束的保证不能互换；轨迹通过不能证明整盒安全。

机体换代复用已落地的退休与冻结锁机制：采用时新路径/新版本，同变更退休旧机体冻结消费者；不刷新旧锁。该机制事实与边界见 `2026-09-30-body-swap-and-lock-freeze.md`，本记录不复述其验收读数。

## 证据引用

- 资产：`rl_exp/versions/lizard2/lizard2.urdf` 与 `rl_exp/versions/lizard2/meshes/collision/`。
- 实现：`rl_exp/tools/verify/check_leg_reachability.py` 的 `joint_effect`、`fold_tilt_cos`、`fold_tilt`、`pad_state`。当前 `--urdf` 与 `_pad_mesh` 尚未统一绑定候选身体，不能用新 URDF 搭旧网格宣称新机体通过。
- 自检：在仓根运行 `E:/IsaacLab/env_isaaclab/Scripts/python.exe rl_exp/tools/verify/check_leg_reachability.py --self-check`。
- 内联复算：用上述解释器的 `-B -c` 运行下列代码（本机 isaaclab.bat 为空，因此直接用环境解释器；此代码只读）：

```python
import math
from rl_exp.tools.verify import check_leg_reachability as k

chain = k.load_chain(k.DEFAULT_URDF, "lf")
n = k.pad_normal_in_link(k.DEFAULT_URDF, "lf")
vertices = k.pad_vertices("lf")
q = [0.4, 0.2, 0.6, -0.3, 0.0]
for i, name in enumerate(k.CHAIN):
    print(name, k.joint_effect(chain, q, i, n, vertices)[0][0])
rotation = k.foot_pose(chain, [0.0, 0.3, 0.0, 0.0, 0.0])[1]
print("FK R[1][2]", rotation[1][2], "Rx(+sigma)", -math.sin(0.3))
sigma = math.pi + math.atan2(n[1], -n[2])
q = [0.0, 0.6, 1.2, sigma - 1.8, 0.0]
print("in box", all(j["limits"][0] <= a <= j["limits"][1]
                    for j, a in zip(chain, q)))
print("fold_tilt", k.fold_tilt(n, sigma, 0.0))
print("directed tilt", k.pad_state(chain, q, n, vertices, 0.9)["tilt_deg"])
```

- 生物角定义：[Clemente 2011](https://doi.org/10.1242/jeb.059345) 区分股骨前后摆动、内收和股骨—胫骨平面旋转；其来源与体型边界见 ROM evidence。本轮未取得成年大型个体的完整三维序列。
- 动作功能：[Clemente 2013 摘要](https://pubmed.ncbi.nlm.nih.gov/23868836/) 支持股骨旋转等运动与步幅相关，不提供本机器人硬限位，也不单独证明本任务必须增加自由度。

## 未覆盖边界

- 反例为 lf 离线几何，不是步态分布、实际碰撞或动力学验证；其他腿的代表姿态作用量未完成。
- 现有几何自检主要按水平机体；带机体姿态的世界系接触验收尚待实现。
- 掌面正反口径、候选资产绑定与通用新轴 FK 尚未修复；本轮仅把它们列为候选验证前置。
- 未构建新增旋转轴机体、未完成前肢映射或 A/B 拟合、未确定最终逐轴范围、未训练或评测。
