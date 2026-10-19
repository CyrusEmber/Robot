# lizard2 移重后左前腿抬落：胸姿态损失与足尾载荷缺口

## 适用范围

承接[单腿抬落记录](2026-10-19-lizard2-single-leg-lift.md)。新增机体移位参考、四足配套逆解和具名尾部随动候选，仍使用[承重静站记录](2026-10-19-lizard2-loaded-standing.md)的隔离自由基座资产及同一地面接触读回。正式资产、配方、网格、惯量、限位、力矩/速度上限均未变。两个物理候选均未通过，不升级静站基线，不关闭 B/C 或其它事项。

## 验收条件

- 机体向后 0.08 m、向右 0.10 m 的根位移仅作逆运动学参考，不在运行时写基座状态、加外力或固定基座。四掌保持原名义落点，随后左前掌增加 0.06 m 名义高度。初始参考高度沿用原 USD 的 0.001 m 间隙；不改变地面或几何穿透容差。
- 每阶段 17 个逆解节点，关节节点间按 quintic 遍历原直线；移重和抬脚各检查节点与中点，共 66 个有限姿态。保持既有限位、实体碰撞、翻掌、反曲及全体网格地面条件，穿透容差仍为源配置的 1e-5 m。不声称连续域或实际无滑移通过。
- 时间为静站 0–5 s、移重 5–8 s、抬起 8–11 s、保持 11–13 s、落回 13–16 s、返回中立 16–19 s、恢复 19–22 s；步长仍为 0.005 s。静站、保持和恢复分别取 [4,5]、[12,13]、[21,22] s 判断，原离地、卸载、剩余足承重、姿态/跟踪、禁止接地、硬停止及恢复条件保持。
- 增加移重过程的独立判词：在 [7,8] s，左前足平均竖直力须低于静站窗口平均值的 75%。该窗口仍包含移重末段，不能解释为移重后的静态平衡；它与保持段真实离地分别判断，不以根位置移动代替载荷转移。
- 本轮最多两个物理候选。第一套为腿 6 Hz、前腕 6 Hz、颈俯仰 2 Hz；第一轮暴露承重跟踪和尾部零目标缺口后，第二套复用此前的腿 12 Hz，并给尾部随动目标，前腕和颈部不再改。所有阻尼比为 1，其余驱动保持原配置。不追加幅度或频率扫描。

## 结果

### 几何计划

粗略起终点关节插值会穿地。同一根参考高度、同一移重中点 u=0.5，粗路径全体最低点为 −0.005476066816489045 m，分段逆解路径为 0.0010000000000000009 m；前者被原 1e-5 m 条件拒绝，后者通过。对照落在 geometry_regression.json。更大的初始移重请求曾触及后踝范围，未进入物理；最终只交付上述可达目标。

两个最终计划各有 66 个有限几何姿态通过。第二计划的尾部目标来自第一轮前进段实际尾部 q 减去静站末帧 q；yaw 直接作为随动目标，pitch 在原关节范围内拟合，避免名义尾段穿地，落回阶段逆序返回。没有锁住尾部两个世界落点；早期双锚点构想无法给出满足几何约束的交付，已弃用。尾部目标并不保证实际压力分布、随动误差或摩擦状态通过。

### 两个物理候选

两次均完成 4400 步、22 s，无硬停止；禁止身体地面力均为零，落回后四足站姿及恢复重量平衡均通过，失败报告完整可读且进程均退出 1。

| 候选 | 静站左前足平均 N | 移重窗口左前足平均 N | 保持段最大左前足地面力范数 N | 保持段最低掌底 m | 保持段其余足/跟踪 |
|---|---:|---:|---:|---:|---|
| 腿 6 Hz、尾部零目标 | 210.83445048925296 | 182.93228232919873 | 56.79930877685598 | −0.000383702894668117 | 足承重满足；全体跟踪未满足，尾部最大偏差约 0.16415 rad |
| 腿 12 Hz、尾部随动 | 204.6896341048663 | 225.48867668797126 | 17.27131080627457 | −0.00027363825800007235 | 右后足最低 0.846207857131958 N；右后踝最大偏差 0.10232817924759097 rad |

两次 baseline_stable、recovered_stance、returned_to_ground、no_deep_mesh_penetration、recovered_weight_balance 均为 true；actual_clearance、actual_unloaded、supported_hold、transferred_load 均为 false。第一轮虽然减轻了左前足载荷，仍未达到预设的四分之一减载；第二轮移重末段左前足平均承重反而增加。保持段脚底仍贴地，不能将减载称作离地。

第一轮 8 s 实际根位置约 [−0.06352, −0.10657, 0.59805] m，证明机体实际移动；13 s 时左前掌仍承重，右前肘误差约 0.12669 rad，尾部相对零目标偏移也超出保持条件。第二轮 13 s 实际根位置约 [−0.05760, −0.08733, 0.60322] m；保持段最大下沉 0.000582575798034668 m、倾角 0.026442829546907815 rad，根竖直速度均满足原条件，但尾部和脚的载荷没有按预期交接，右后足明显卸载。其移重窗口两后足平均承重仅约 2.63/1.79 N，不能称作预先建立了合格支撑。

### 已定位的高度损失及下一动作

对第二轮 13 s 的同一实际根姿态做 FK 替换分解：命令关节姿态的左前掌最低点为 0.02917947271948977 m；只把胸俯仰替换为实际 0.04237304627895355 rad 后，降为 0.0012103015920921917 m。实际全 q 的 FK 最低点为 1.2812189306293797e-6 m，与实际 actor 网格 1.2115126198780635e-6 m 对齐。保持其它实际 q，仅将胸俯仰恢复中立时，FK 高度为 0.027528386273652256 m。

这定位了约 0.028 m 的胸部承重变形高度损失；它叠加实际根姿态损失，使名义 0.06 m 目标仍未离地。此为同一读回的几何分解，**不是胸部单项修正的物理成功证明**。下一步先处理承重胸姿态补偿及三足/尾部的载荷分配，再重试同一左前腿动作；继续保留静站基线，不能把追加腿部增益或尾部零误差假设作为已解决。

## 证据引用

实现提交 `60dd951`：`rl_exp/tools/diagnose/palm_spatial_transfer.py`（规划）和 `palm_spatial_standing.py`（实际目标、读回与判词）。最终源码 SHA256 分别为 `8e89c73d0de7114773eee7b8ea83ef47650c350577968d449f9dda83a09910dc`、`74c8f3f9477c78eb3bed01af36e27eb038bd98b2bc27bd05002fe6d11f80e08c`；两次实际运行的 source.py 均绑定后者。第二物理目录的 planner_source.py 保存第二计划生成时的规划器，final_planner_source.py 保存最终修复版；第一计划生成时尚无尾部可选分支，其旧规划器字节快照未单独保存，精确物理复读仍使用已序列化计划。该代码提交的 root hygiene、framework pin/self-test、DR parity、version docs、work docs、obs protocol/live 闸门均通过，不替代动作通过或独立审核。

提交前复读发现新增尾部可选分支时，几何循环的局部变量覆盖了可选载荷参考，导致默认入口误进尾部分支。修复前默认 CLI 真实退出 1，错误为 NoneType.resolve；重命名局部变量后，默认及尾部分支均真实生成计划并退出 0。逐字段对照原计划的 keyframes、geometry、windows、duration_s、target_q_rad、desired_root_shift_m、sole_local_m 全部相同，无需重跑未改变的物理目标。回归记录及三份日志留在本机。

原始报告和资产留在本机，以下路径不承诺入仓：

| 路径（仓根相对） | SHA256 |
|---|---|
| `rl_exp/out/lizard2_b_transfer_plan_20261019/plan.json` | `825ebccb383aa555abe91bfb368e2c6bc19113fd77c3f0fb6f7b63311baafb5c` |
| `rl_exp/out/lizard2_b_transfer_plan_20261019/geometry_regression.json` | `684271d08cdca9f0f8b8ea1f778ad43d72a9bf0d6935234f2f3fec60860b6541` |
| `rl_exp/out/lizard2_b_transfer_tail_plan_20261019/plan.json` | `1c61a4cc15372693d1dd3be75ba2015a211953532e284c3ac4dd26a01e6113b5` |
| `rl_exp/out/lizard2_b_transfer_lift_20261019/report.json` | `31559f24f3065cfdd07e81d3a3c0bca6b6a4c760617368ac1d0c741fa4e46380` |
| `rl_exp/out/lizard2_b_transfer_lift_20261019/window_metrics.json` | `80b468dc673e624b827a7e3d6336bc2ddcc3bff014c415191fb2e837a55c6e69` |
| `rl_exp/out/lizard2_b_transfer_tail_lift_20261019/report.json` | `71d21ec120bc2a384cc01c47bc17e3c468e6911dab38a7578c6a65fbc192493d` |
| `rl_exp/out/lizard2_b_transfer_tail_lift_20261019/window_metrics.json` | `9fcdaae8c23f858792f18833e2937ca2cc0c50ff7e36a0efc9e6a197aa0d8844` |
| `rl_exp/out/lizard2_b_transfer_tail_lift_20261019/posture_decomposition.json` | `c4b17a6f6d73d9751ff7860f11069e4c08919ba7334502499e89f36e3db01271` |
| `rl_exp/out/lizard2_b_transfer_tail_lift_20261019/planner_regression.json` | `4761141b541b3859102ab2a3ca1f79c69bebb604d38c4fcb52e10169bd6d8f43` |
| `rl_exp/out/lizard2_b_transfer_tail_lift_20261019/final_evidence_index.json` | `5275d145f637d31bbd4be51278ed809e289cc92facd7e8bac84795125fa8eff8` |

最终索引绑定两份计划及修复后复读计划、两次运行的报告、增益 manifest、运行源码、指标和姿态替换读数；后者不是额外物理运行。第一/第二物理 manifest SHA256 为 `f80ef13f583dc911d48a2f503dd7e0c64350953bd5d03b0566ed89731db36650` / `d73a08e4b677b832d244f62046599e3c94fc07030a1be37bf5a4c3858606d3ba`，原输入身份见前序记录与计划绑定。

从仓根 PowerShell 复读，输出必须使用新目录：

```powershell
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/diagnose/palm_spatial_transfer.py --standing_report rl_exp/out/lizard2_b_standing_neck2_20261019/report.json --pose_report rl_exp/out/lizard2_a_contact_delivery_20261019/report.json --out rl_exp/out/lizard2_transfer_plan_replay
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/diagnose/palm_spatial_standing.py --lift_plan rl_exp/out/lizard2_transfer_plan_replay/plan.json --wrist_frequency_hz 6 --out rl_exp/out/lizard2_transfer_replay --viz none --device cuda:0
# 第二计划的规划命令增加 --load_reference rl_exp/out/lizard2_b_transfer_lift_20261019/report.json，另用新 out。
# 第二物理命令改用该计划，增加 --leg_frequency_hz 12，并另用新 out。
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/diagnose/palm_spatial_standing.py --self_check
```

离线自检通过，覆盖旧抬落判词、分段目标节点/中点、使用新窗口的成功合成样本和移重不足反例，以及既有异常保存失败退出回归。几何正反对照使用上述实际模型，不以声明一致或这些合成样本代替物理动作成功。

## 未覆盖边界

尚无合格单腿离地或合格预先载荷转移；没有后腿/镜像、承重直行、胸姿态补偿的实际对照、完整尾部控制或完整步态。实际掌面微滚动/滑移另有 sole_positions_w_m 读回，本轮没有据此作无滑移通过判词。

最大重建 PD 请求/cap 比值分别约 0.98993 和 0.94758，仍是代理量，不代表实际电机力矩或饱和已验证。尾部第二候选同时改变目标、腿部组频率，不能从两次结果单独归因尾部控制效果。本记录只定位当前缺口，不作资产采用或事项关闭审核。
