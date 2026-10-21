# 新输入受载逐轴续测

## 适用范围

2026-10-21 用户要求“继续接下来17个”。本轮仅执行前次停点之后的 17 个逐轴双向自重工况，不重测原已完成 12 项，不运行四腿、颈、尾六组合。沿用[原套件与恢复依据](2026-10-19-lizard2-spatial-small-tracking.md#其它关节双向自重与组合验证)及[稳定性与精度口径](2026-10-21-lizard2-loaded-precision-interpretation.md)，不调 PD、不改原阈值、不自动重试、不正式采用或训练，不创建子 agent。

## 验收条件

固定根 z=2 m、31 body 开重力、无额外夹具或地面支撑；同一新输入、`_gravity_design` 初值、armature=0；胸俯仰 effort cap=280 N·m，其它 cap、速度、范围和碰撞过滤不变。每项正常 reset，零目标静置 5 s，正向 0.02 rad 6 s 往返、负向 0.02 rad 6 s 往返；每方向 2 s quintic 伸出、1 s 保持、2 s 返回、1 s 恢复。dt=0.005 s，backend 速度目标为零；每项 3400 步，本轮上限 57800 步。

保持原逐方向判据：最大运动增量误差 ≤0.012 rad，保持/返回末 0.2 s ≤0.002 rad，其它轴运动增量 ≤0.01 rad；静置漂移 ≤0.002 rad、静差及全程绝对目标误差 ≤0.1 rad。仅保持精度未达允许留失败记录后继续，不将失败改成通过；返回、最大跟踪误差、其它轴或静置条件失败仍停。绝对角度/目标误差 >0.35 rad、速度达到读回限速一半、接触 >1 N、非有限状态或 actor/FK 不一致仍立即停。

`--continue_self_weight_axes` 要求批准的前次 report 摘要；启动前复核原写文件异常恢复链、全部 12 项原样本与判词、输入/源码/manifest，确认 11 项通过及最后一项仅保持精度未达。按原顺序只选余下 17 单轴，六组合列为 deferred；报告区分本次所选项和历史失败，不冒称完整 35 项套件通过。

## 结果

唯一物理进程完成全部 17 项、57800 步，无重试；`completed=true`、`selected_cases_completed=true`，状态 `self_weight_axes_completed_precision_unmet`。本轮 **10 项通过原判据、7 项仅保持精度未达**；退出码 1 保留严格精度失败，不是中途异常。历史左后髋 twist 原失败保留，未重测；合并此前样本后，其它 29 关节双向逐轴均已覆盖，21 项通过、8 项保持精度未达。胸俯仰仍单独复用原自重切片，六组合尚未执行。

| 工况 | 正向保持误差 rad | 负向保持误差 rad | 返回误差上界 rad | 原判词 |
|---|---:|---:|---:|---|
| `rr_hip_twist_joint` | 0.002760169078 | 0.002765924186 | 2.713873982e-06 | 保持精度未达 |
| `neck_pitch_joint` | 1.471631229e-05 | 2.646371722e-06 | 1.11758709e-08 | 通过 |
| `lf_shoulder_abduct_joint` | 0.0002668429911 | 0.0002551455796 | 7.823109627e-08 | 通过 |
| `rf_shoulder_abduct_joint` | 0.0002666287869 | 0.0002549565211 | 7.264316082e-08 | 通过 |
| `tail2_pitch_joint` | 7.104452699e-05 | 8.330911398e-05 | 4.731118679e-07 | 通过 |
| `rl_knee_joint` | 0.005798637383 | 0.005797629226 | 2.607703209e-07 | 保持精度未达 |
| `rr_knee_joint` | 0.005798581969 | 0.005797691159 | 2.607703209e-07 | 保持精度未达 |
| `lf_shoulder_twist_joint` | 0.003271744102 | 0.003267743024 | 3.082677722e-06 | 保持精度未达 |
| `rf_shoulder_twist_joint` | 0.003267914271 | 0.003271896839 | 3.091990948e-06 | 保持精度未达 |
| `tail3_yaw_joint` | 0.0007331147604 | 0.0007320474647 | 1.892005093e-05 | 通过 |
| `rl_ankle_joint` | 4.554025829e-05 | 3.36426124e-05 | 1.862645149e-09 | 通过 |
| `rr_ankle_joint` | 4.554212093e-05 | 3.363329917e-05 | 0 | 通过 |
| `lf_elbow_joint` | 0.005783873126 | 0.005786771402 | 6.444752216e-07 | 保持精度未达 |
| `rf_elbow_joint` | 0.005784280114 | 0.005787032172 | 7.227063179e-07 | 保持精度未达 |
| `tail3_pitch_joint` | 6.240092218e-05 | 7.414489985e-05 | 2.402812243e-07 | 通过 |
| `lf_wrist_joint` | 1.290857792e-05 | 2.48965621e-05 | 3.725290298e-09 | 通过 |
| `rf_wrist_joint` | 1.281917095e-05 | 2.47438252e-05 | 2.048909664e-08 | 通过 |

本轮最大保持误差 0.00579863738269 rad（约 0.332°，约为 0.02 rad 幅度的 29.0%）；不能将全部未达项笼统当成此前约 0.158° 的同一偏差。全过程运动增量误差最大 0.00683979817124 rad，返回末段最大 1.8920050934e-05 rad，其它轴运动增量最大 0.00576526485384 rad；均在各自原界内。

执行者直接复读全部 57800 帧：时轴、双向 quintic 目标、30 通道 backend 位置目标的 float32 表示与零速度目标、全部误差及判词逐值一致；17 轴正负保持时的实际增量均同命令方向，返回条件均满足。q/v/目标/接触全部 finite，绝对角度、绝对误差、速度和接触停止界均未触发。最大接触力 0 N；最大速度占读回限速的 7.02966%（停止界为 50%，不等于有效限速触边验证）。以 XML origin RPY、独立 Rodrigues 及归一化 actor 四元数轴角转换重建实际姿态 FK，不调用采集 FK；85 份快照共 31 body，最大矩阵分量差 1.12126471659e-06，小于 1e-5。

新旧 design、settings、全部 backend 读回与输入完全一致；tracking manifest 仅 source 路径变化，消除该路径后与前次结构全等。PD request 依采集类型精确重建，差为零；它仍是请求估计，不是求解器实际力矩或饱和证据。首次离线重建把 float64 目标误降为 float32，等值断言失败；按采集运算类型修正后全帧一致，未修改原始数据或判词。

**当前判定**：本轮所测工况的稳定受载保持/返回和正确方向成立；七项保持精度未达，分别是右后髋 twist、左右膝、左右肩 twist、左右肘。当前 PD 保留候选资格，是否满足用途精度尚需明确用途判据；不据此立即加增益，不宣称默认驱动已定稿或力矩上限充足。后续保留六组合、有效边界与正常支撑集成，协调交 RL。

离线前置：旧小幅、新输入、胸部、自重套件及本次续测自检通过，错误批准摘要拒绝。持久 `--self_check` 在内存破坏三处后均失败：去掉续测分支（`dee611f5962e0a7237b9f8c189c429974e83fba9641f4fd21e75bb13ddda8ef1`）、去掉返回误差保护（`3d7e785299a2cf85cbeb0b08d062034dfa7be594c22b1ea592dc076e49a53e8d`）、去掉逐轴过滤（`ef055b4eee425c1c3c81d45f3bdcf75c8d414ca74e5e697735419904d34904f3`）；原候选通过。首次自检调用缺少既有输入检查所需 out 参数，在物理启动前失败；补齐后完成离线检查，未消耗物理预算。

提交前完整离线套件通过：`ALL_OFFLINE_CHECKS_PASSED (37/37 in 49.4s)`；结果回填后 `check_work_docs.py` 及 diff 格式检查通过。格式闸门不代替独立审核。

## 证据引用

- 前次 `rl_exp/out/lizard2_b_loaded_suite_resume_20261021/report.json` SHA256 `add97d4c446a5e883167655629f4c02ada4ac500a192e4b06f28e0f537729811`；新惯量报告批准摘要 `f1f9951a5057e4f5431316be373b5e359fbd3f5f8d79d3c2978bda140f5d06fd`。
- 当次隔离候选 `rl_exp/out/palm_spatial_tracking_axes_HEAD.py.txt` SHA256 `924b773e1ed6ee2077fa0eefb3bf94c49e24b15f71d6b3ef54fb9449d067f799`，由前次真实 source 加本轮续测增量产生，不含工作树 RF/视频等 WIP；同一增量已合入 `rl_exp/tools/diagnose/palm_spatial_tracking.py`，源码提交 `8a6bbfc` 以 `3478787` 为基线，仅纳该候选增量；用独立索引避免收进共享文件的 RF/视频 WIP，限定候选预提交钩子通过。
- 本机运行目录 `rl_exp/out/lizard2_b_loaded_axes_20261021/`；启动日志 `rl_exp/out/lizard2_b_loaded_axes_20261021.log` 首行保留实际编译执行的候选摘要与完整 argv。使用原工具 `__file__` 和 `__candidate_source__` 执行批准 bytes，运行目录保留同一 source 快照。
- 离线自检日志 `rl_exp/out/lizard2_b_loaded_axes_preflight_20261021.log`；实际输入复读与破坏检查脚本 `rl_exp/out/check_loaded_axes_candidate.py` 留在本机，不把它当新的仓库闸门。本机工件引用不承诺入仓。


| 本机工件 | SHA256 |
|---|---|
| 本轮 report.json | `7a9141ed06cf187718309c2db7e17f9a5657fcace542caa7827f76dc7ccc8570` |
| 本轮 tracking_manifest.json | `5c507b912c67a45c46d41eeefc9ef9bc968236baeb03923f2abfd8f1f82a71d4` |
| 直接复核 audit.json | `c3352c9f589f3de2f0b5090c9d273b1a1162093fed1a79d1f64b25024d94a19a` |
| 运行日志 | `8cc8188e9e6092f35fa37e2f813c6141790fe0af34e66ff7e15c7fd6bc11d102` |
| 离线前置日志 | `4c1bf6e4b857400548563d07668a48267323e0495eac3df588874d36ec106f3c` |

直接复读脚本 `rl_exp/out/audit_loaded_axes_20261021.py` 与日志 `rl_exp/out/lizard2_b_loaded_axes_audit_20261021.log` 留在本机；报告不把执行者复读称为独立审核。

持久工具复读入口（新目录；重跑物理需另获预算）：

```cmd
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp\tools\diagnose\palm_spatial_tracking.py --headless --device cuda:0 --all_joints --self_weight_suite --continue_self_weight_axes --resume_self_weight E:/Robot/rl_exp/out/lizard2_b_loaded_suite_resume_20261021/report.json --approved_resume_sha256 add97d4c446a5e883167655629f4c02ada4ac500a192e4b06f28e0f537729811 --approved_inertia_sha256 f1f9951a5057e4f5431316be373b5e359fbd3f5f8d79d3c2978bda140f5d06fd --inertia_report E:/Robot/rl_exp/out/lizard2_e_fresh_inertia_20261020/report.json --out E:/Robot/rl_exp/out/lizard2_b_loaded_axes_replay
```

离线复读同命令去掉 `--headless --device cuda:0`、追加 `--self_check`，保留新 out 参数；不创建输出、不启动物理。

## 未覆盖边界

六个组合尚未执行；没有自由基座/接触支撑、实际求解器力矩/饱和或有效速度触边的验证。受载逐轴结果不能外推步态或任意姿态/载荷，不等于默认 PD 正式定稿。稳定性与精度分别报告，未达项保留；B/C/E/D 未关闭，协调仍交 RL。本文为执行者回填和直接复核，不代填无执笔历史的独立审核。
