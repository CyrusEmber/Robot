# lizard2 5b：转向、几何恢复与膝肘边界（2026-10-14）

## 适用范围

针对恢复后肢尺寸的隔离 palm 候选，承接 `work/active/lizard2-restored-limits-pd-validation.md` 步骤 5b。用户于本轮确认先做建议的几何诊断。正式资产、冻结配方、PD 与训练不变；本记录不是无执笔历史的关闭审核。

入口为 `rl_exp/tools/diagnose/palm_motion_boundaries.py`，参数唯一归同目录 `palm_5b_targets.json`，可视化归 `palm_motion_view.py`。本机输出在 `rl_exp/out/lizard2_palm_motion_5b_20261014/`；产物未入仓，不承诺其他机器可直接打开。

## 验收条件

用户确认的工程工况：沿用 5a 步长 0.20 m、抬脚 0.05 m、周期 1 s、支撑占比 0.6；根转向角速度 ±0.20 rad/s；根横移/升降 ±0.02 m、侧倾/俯仰 ±3°，用 2 s 平滑往返中立。恢复期间四掌世界目标保持固定；转向用显式 SE(2) 根运动和每段支撑内固定的世界落足点。世界原点取中立根位置，掌底平面约 z=-0.603 m。

位置残差 ≤0.1 mm、世界掌面倾斜 ≤2°、URDF 限位余量 ≥0.02 rad、关节速度 ≤URDF 限速的 50%、帧间变化 ≤0.05 rad、周期接缝 ≤1e-6 rad。非排除对间隙 ≥5 mm；每周期 400 帧，恢复 801 帧，组合碰撞检查所有轨迹帧及接缝。所有碰撞承载 link 对均纳入，排除直接关节连接对及既有批准六对；排除区域的局部机械干涉另列未覆盖。

膝肘扫描每个上下文 81 个角度，覆盖 URDF [-1.2, 1.2] rad；上下文取中立与各工况实际最大关节偏移范数帧，不合成各关节极值。5 mm 失败转折加密至 1e-4 rad；这不是实体相交位置或连续域安全性的精度声明。伸直与完全折叠角由本候选实际肢段向量和轴计算，不借用采用机体的固定事实。

## 结果

### 工况

全量运动学为 `run2/`，完成标记为 true，退出 1 对应明确目标失败。最终碰撞检测重放输出为 `final/`，几何读数复用原轨迹并绑定源报告及 CSV 哈希；旧 `run1/` 被主动中止，无完成报告，不作为最终结果。

| 工况 | 判定 | 关键读数 |
|---|---|---|
| 直行、左右转向 | 离散几何通过 | 最大位置残差约 8e-12 m 以内，掌面倾斜约 1e-6° |
| 横移 ±0.02 m、升降 ±0.02 m | 离散几何通过 | 位置及掌面均达标 |
| 侧倾 ±3° | 离散几何通过 | 最大位置残差 1.96e-8 m，掌面倾斜约 1.1049° |
| 俯仰 +3° / -3° | 失败，均为掌面倾斜 | 最大倾斜 2.8824° / 2.8701°，位置仍达标 |

九个通过工况中的最小关节限位余量为 0.15593 rad，最大有限差分关节速度为 3.36222 rad/s。139 个非排除 link 对全部轨迹帧满足 5 mm 条件；最小保守 AABB 间隙下界为 7.594 mm，不把该下界写成精确网格距离。固定世界落足目标的实际位置误差随位置残差达标；这是运动学支撑约束，不是承重滑移测量。

俯仰峰值另经 `pitch_final/` 的每腿、每符号 32 个随机初值复核：位置达标的最小掌面倾斜仍为 2.7404–2.8824°。这降低了局部初值误判的可能，但不是全局不可达证明。失败只否定本工况、此配置与所用求解方法，不直接判缺轴或允许事后放宽 2°。

### 伸直、折叠与实体干涉

| 关节 | 几何伸直角 [rad] | 完全折叠角 [rad] | URDF [-1.2, 1.2] rad 中的观察 |
|---|---:|---:|---|
| lf/rf elbow | -1.399013 | +1.742580 | 两个共线端均在限位外；正向折叠先出现腕与上臂干涉 |
| rl knee | -1.399141 | +1.742451 | 两个共线端均在限位外；本次切片未发现非排除对干涉 |
| rr knee | -1.399139 | +1.742453 | 同上 |

肘部中立上下文的 5 mm 余量失败边界位于 [1.141230, 1.141289] rad。不同实际组合上下文，前肢边界约在 1.12869–1.18570 rad 之间。具名对为 `lf_shoulder_abduct ↔ lf_wrist`、`rf_shoulder_abduct ↔ rf_wrist`。中立扫描 q=1.17 与 1.20 rad 均有三角表面相交，非仅 AABB 或凸包重叠；前一中立粗采样 q=1.14 rad 未相交。因此实体相交开始只定位在该采样区间，不能把 5 mm 精细转折误称精确接触角。

URDF 对称限位不等于全范围无干涉。通过工况的肘/膝包络分别约 [-0.2727, 0.2222] / [-0.2114, 0.3490] rad；全 16 个关节精确包络在报告 `sampled_envelope_rad`。包络仅取通过工况，不包含失败俯仰样本；各维极值的任意组合没有验证。机械硬限位只读隔离 URDF 声明，尚未新增或采用物理停止；策略范围与阶段约束不在本轮定稿。

### 方法缺陷与正反例

- 首版恢复求解器以位置和精确掌面法线同权优化，侧倾 +3° 的 lf 位置残差为 0.002351291 m。按照既定 0.1 mm / 2° 容差归一化权重后，同一输入得到 1.96e-8 m / 1.1049°；修复前快照复读确认旧入口超位置阈值。改的是求解目标权重，验收阈值不变。
- 表面检查包含顶点/面、边/边距离、边穿面和封闭体包含。十字交叉薄盒没有内含顶点，仍必须被拒；关闭边穿面读法后自检红。平行分离面、斜边最近距离、完全包含有手算对照。
- OBJ 顶点精确焊接，删除重复索引三角与重复面，再检查闭合边次数和一致绕序。胸和颈各有两个封闭连通部件，其他碰撞网格单部件；包含检查逐部件取代表点。回退到只检查首顶点时，第二部件完全包含反例以 `AssertionError: second component containment` 失败；修复后通过。最终重放只重验碰撞及相关边界，不重算未受影响的运动学。
- 首轮离线套件 36 项通过，源码快照的 `.py` 副本触发 `check_record_bindings.py`；快照改存 `.py.txt` 后该项通过。诊断快照不作为第二份生产实现，最终代码保留此写法。工作账本、语法及提交钩子另验；闸门通过不等于几何目标全部通过。
- 重放入口原先继承源报告的汇总状态和包络；新增碰撞失败时可能留下错误的通过状态。以保存的 `replay_regression/source/` 夹具注入 `lf_wrist ↔ rl_ankle` 相交，修复前输出仍为 PASS 且保留 `j` 包络，修复后为失败且包络为空。该入口现从重放后的场景派生状态和包络，拒绝非有限轨迹。对本次 `final/report.json` 重新派生，数值与判定一致；未重跑未受影响的几何或碰撞。
- 最终离线套件 `ALL_OFFLINE_CHECKS_PASSED (37/37 in 59.1s, jobs=4)`；工作账本 `WORK_DOCS_OK (87 item file(s))`、源码语法和正例自检通过。最终重放的全部场景、膝肘边界与包络逐项等于原报告。四组侧/俯视动画及 `residuals.png` 已生成；误差图经查看确认显示俯仰超限。

## 证据引用

输入：`rl_exp/out/lizard2_palm_pd_restored_20261013/lizard2_palm_diagnostic.urdf`，SHA256 `ec247886a6512e8cc70ba86261970eed8f205e92de98a70eba1dc577f3ce7cc2`。配置 SHA256 `0d264781ff420737d9df49ac966a1f222ad14119e66c0e539a126b2133084294`。各运行 `launch_identity.json` / `report.json.identity` 绑定 URDF、全部实际碰撞网格、诊断入口、FK、关节名、binding 和配置；`.py.txt` 源码快照留在同次输出 `source_snapshot/`。结束前复核源码与输入哈希未变。

全量轨迹的运行脚本 SHA256 为 `0f8759377c6d49e7bdd6ebeb25fc20095868a3c9ff123abe277823623864433d`；后续改动为文本快照后缀、保留俯仰多初值入口及多部件碰撞检测/重放入口，未修改目标与运动学求解。最终碰撞证据归 `final/report.json`，来源及原轨迹身份保留在 `trajectory_source`。动画从保存的 CSV 和同一 URDF 生成，不从动画反推判定。

最终碰撞运行入口 SHA256 为 `5b5659a4f70e0705ccc63d5b9e6cd54583ae14f4322592aec729878448b97f32`。提交前入口 SHA256 为 `917c074144587248213c1981871196b6b5dffb963cf0a40e0068c1981e7f7ce3`；两者之后的差异仅为上述重放汇总派生与非有限轨迹拒绝，碰撞算法、扫描与目标未变。俯仰复核和原运动学各保留自己的身份，不拼成同一源码版本。

代码与配置已落入 `cf8ddb1`（`feat: probe palm turning and recovery boundaries`），提交钩子的冻结契约、版本文档、工作账本和观测协议检查均通过。本记录与专项 evidence 指针同次提交，事项仍为 in_progress。

复读命令（PowerShell；输出目录换成不存在的新目录，禁止覆盖）：

```powershell
& 'E:/IsaacLab/env_isaaclab/Scripts/python.exe' rl_exp/tools/diagnose/palm_motion_boundaries.py --urdf rl_exp/out/lizard2_palm_pd_restored_20261013/lizard2_palm_diagnostic.urdf --output_dir rl_exp/out/lizard2_palm_motion_5b_20261014/reproduce_full
& 'E:/IsaacLab/env_isaaclab/Scripts/python.exe' rl_exp/tools/diagnose/palm_motion_boundaries.py --urdf rl_exp/out/lizard2_palm_pd_restored_20261013/lizard2_palm_diagnostic.urdf --output_dir rl_exp/out/lizard2_palm_motion_5b_20261014/reproduce_collision --collision_replay rl_exp/out/lizard2_palm_motion_5b_20261014/run2
& 'E:/IsaacLab/env_isaaclab/Scripts/python.exe' rl_exp/tools/diagnose/palm_motion_boundaries.py --urdf rl_exp/out/lizard2_palm_pd_restored_20261013/lizard2_palm_diagnostic.urdf --output_dir rl_exp/out/lizard2_palm_motion_5b_20261014/reproduce_pitch --pitch_multistart
& 'E:/IsaacLab/env_isaaclab/Scripts/python.exe' rl_exp/tools/diagnose/palm_motion_boundaries.py --self_check
& 'E:/IsaacLab/env_isaaclab/Scripts/python.exe' rl_exp/tools/diagnose/palm_motion_boundaries.py --self_check --break_crossing
& 'E:/IsaacLab/env_isaaclab/Scripts/python.exe' -c "import sys; sys.path.insert(0,'rl_exp/tools/diagnose'); import palm_motion_boundaries as m; import numpy as np; m.component_representatives=lambda v,f:np.array([0]); m.self_check()"
& 'E:/IsaacLab/env_isaaclab/Scripts/python.exe' rl_exp/tools/diagnose/palm_motion_view.py --report_dir rl_exp/out/lizard2_palm_motion_5b_20261014/final
```

完整诊断与俯仰复核退出 1 是已记录的目标失败；破坏自检退出 1 是预期反例。中断、异常或半成品目录没有 `completed: true` 的汇总，不能作为合格报告。通过场景也只是 `PASS_SAMPLED_GEOMETRY_ONLY`。

## 未覆盖边界

未测承重、受推动态恢复、跟踪误差、PD、实际力矩/限速、摩擦或稳定性；最终策略范围仍依赖步骤 6。本轮不闭项、不正式采用。

关节域只扫描具名切片；不证明所有组合或帧间连续域。没有单独扩大腕/踝范围、证明直接连接区只在枢轴合法重叠，或排除绕过采样的细小接触区。间隙工具检查导出的三角表面，不等于 USD/PhysX 实际碰撞形状；运行时需另证。共用 FK 的系统误差仍依赖先前坐标链证据。

交 A：复核俯仰目标、掌面容许区间与结构可表达性，处理肘部折叠干涉；未经目标修订或结构证据，不扩大机械限位或放宽已确认判据。交 B：资产前提收口后按步骤 6 运行同轨迹，取得跟踪与恢复余量，才确定策略目标及阶段范围。
