# lizard2 胸俯仰 PD 静站保持：历史水平试验与条件撤销

> 下列原试验保留当时判据、读数及退出状态；当前执行条件以末节“用户修订：胸部水平不再作为门槛”为准。

## 适用范围

承接用户授权的“先让现有躯干 PD 在静站时守住水平，再做真实承重抬腿”。复用原自由基座静站资产，仅调整胸俯仰已有 implicit PD；没有夹具、胸部锁止、移重、尾部动作、补偿控制器或驱动上限调整。左前腕自重跟踪结果仍取[水平胸部记录](2026-10-19-lizard2-level-leg-pd.md)，本轮未将其接入自由承重抬腿。

## 验收条件

- 原 5 s 静站、0.005 s 步长、最后 1 s 的根下沉/倾角、关节偏差、竖直速度、每足承重、总支持力及硬停止条件全部保留。
- 本轮试验前将“基本水平”明确为：最后 1 s 实际 chest_pitch actor 的世界倾角不超过 1°。此为自由承重诊断的工程条件，不是上轮夹具的数值精度条件；不以相对关节目标为零替代世界姿态读回。新增条件不追改旧静站记录的原判词。
- 原胸俯仰频率规则为 1 Hz；只试 2 Hz 一套候选，Kp 乘 4、Kd 乘 2，目标仍为零，力矩上限不变。先过静站及水平前提才允许生成下一抬腿输入；不满足则停在胸部保持问题，不追加增益候选或整机控制。
- 重建请求及 actuator computed/applied 系列不当作独立实际电机力矩。读回驱动上限，不因估计量低于上限就宣称有充分余量，也不因估计量超限就宣称已实测饱和。

## 结果

### 原数据复读与唯一物理候选

复读[原承重静站](2026-10-19-lizard2-loaded-standing.md)末段实际根姿态和 q，经已绑定 URDF FK 得到胸部世界倾角；本轮另逐步读取实际 chest_pitch actor 姿态。两份报告的 USD/URDF/网格身份相同，增益读回仅 chest_pitch_joint 的 Kp/Kd 不同；位置范围、速度与力矩上限均相同，运行时仍是自由基座、全部 body 重力开启。

| 指标 | 原静站 | 胸俯仰 2 Hz 候选 |
|---|---:|---:|
| 胸俯仰 Kp N·m/rad | 1010.12939453125 | 4040.517578125 |
| 胸俯仰 Kd N·m·s/rad | 321.5341796875 | 643.068359375 |
| 胸俯仰力矩上限 N·m | 80 | 80 |
| 末段最大胸部世界倾角 ° | 2.2535629664848087 | 1.2572843618524634 |
| 末段胸俯仰平均 q rad | 0.04546500699807755 | 0.01782732720102244 |
| 末段最大根下沉 m | 约 0.00668 | 0.012530088424682617 |
| 末段胸部重建请求绝对值 N·m | 53.26764–53.33646 | 73.91772–74.37999 |
| 全程胸部最大重建请求绝对值 N·m | 79.38380432128906 | 140.48725421574636 |

候选完成 1000 步、5 s，无硬停止。末段根最大倾角 0.004121843129443914 rad、最大关节偏移 0.05419490858912468 rad、根最大竖直速度绝对值 0.021932251751422882 m/s；四足最小竖直力约 208.78、208.55、128.96、129.91 N，平均总支持力 706.32417068434 N，重量 706.3238919067384 N，非批准身体地面力为零。原静站条件满足，但新增水平前提未满足，posture_verdict.passed=false、status=standing_failed，进程退出 1。

增大胸部增益减小了胸俯仰静差，但没有达到本轮 1° 条件，根下沉也没有随之改善。候选未升级基线，没有生成或执行其后续抬腿计划，未把失败结果记作水平保持成功。

### 力矩接口边界及验证

只读核对本机实现：`E:/IsaacLab/source/isaaclab/isaaclab/actuators/actuator_pd.py` 中 ImplicitActuator 的类文档及 compute 明确把该力矩称为 approximate，computed_effort 由目标误差、速度误差和前馈重建，applied_effort 为其裁剪值；PhysX articulation 将 actuator 输出或前馈/估算缓冲写入 computed/applied telemetry。该核对没有建立独立的求解器实际 motor-torque 通道，不证明所有 API 都不可用。

候选晚段重建请求接近设置上限，且瞬态重建值曾超出上限；不能仅拿晚段低于上限当作无饱和或足够余量的证据，也不能据此判定既定上限必然无法达到水平目标。本轮不再盲加 P，不提高上限、不换执行器类型；剩余问题仍限定在现有胸俯仰保持与既定驱动预算的可行性。

普通 `--self_check` 通过：原抬落判词/目标、异常保存失败出口及新增水平正反例均通过。独立进程把水平阈值故意放宽到 3° 后，同一自检对 2° 非水平样本的断言失败、退出 1；源码阈值保持 1°。实际候选也由该新增判词拒绝。末帧全部 actor/FK 最大矩阵分量差 5.834896574796744e-7。

## 证据引用

实现提交 `b31502e`：`rl_exp/tools/diagnose/palm_spatial_standing.py`，源码 SHA256 `db32d86d5922b2179dbc6284c9476e276b7c2aae9221d0fe363bd773c411b32e`；当次 source.py 保留相同版本。该代码提交的 root hygiene、framework pin/self-test、DR parity、version docs、work docs、obs protocol/live 闸门通过，不替代实际动作或独立审核。物理产物、源码快照及本机接口审计原件不承诺入仓。

| 仓根相对路径 | SHA256 |
|---|---|
| `rl_exp/out/lizard2_b_chest2_standing_20261019/report.json` | `5632538e8eeb7248df72ffc546464b7827ce4da3ab20d4eda946f56213e49c77` |
| `rl_exp/out/lizard2_b_chest2_standing_20261019/posture_manifest.json` | `ba121ac099432f25b46ef7f52647b71de236580b2d4741fb9ae04be9d5b20072` |
| `rl_exp/out/lizard2_b_chest2_standing_20261019/comparison_summary_final.json` | `778d0cb9a35c90e41eec0977b18c8c5e87fc4ad9a81663fbd6cc9e9244ef8944` |
| `rl_exp/out/lizard2_b_chest2_standing_20261019/torque_interface_audit.json` | `bfd7cb6ec6adbfeb2cde3fa4344000059a0f8fcd2ac57ea292983fddc84c347b` |
| `rl_exp/out/lizard2_b_chest2_standing_20261019/evidence_index.json` | `d29a1d404767ee7c34147d9de70d2bdc34ce7ee02818440b546fa69cf6536d12` |

原输入报告 SHA256 仍为 `f415264793731a71091ed9e167edd6bce1cfe4ad615772b94c080cef579a20e2`；索引绑定本轮报告、参数、源码、汇总、接口实现文件哈希及破坏日志。初版 comparison_summary.json 的自由/固定字段名不当，最终以 comparison_summary_final.json 的 fixed_base_readback=false 为准，原数值没有改变。

从仓根 PowerShell 按当前代码复读同一物理候选，out 必须为新目录。当前代码已撤销胸部水平门槛，不能预先承诺与历史报告相同的判词或退出码；原水平阈值破坏测试只适用于实现提交 `b31502e`，历史日志由上方 evidence_index 绑定，不再调用已删除的阈值字段。

```powershell
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/diagnose/palm_spatial_standing.py --standing_reference rl_exp/out/lizard2_b_standing_neck2_20261019/report.json --chest_frequency_hz 2 --out rl_exp/out/lizard2_chest2_standing_replay --viz none --device cuda:0
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/diagnose/palm_spatial_standing.py --self_check
# 普通自检预期退出 0；物理候选按当前原静站安全判据判定，本次未重跑。
```

## 未覆盖边界

未获得自由承重下胸部满足 1° 的通过结果，未运行胸部候选与左前腕参数组合后的实际抬腿，也未独立测得 motor torque 或饱和余量。新增的后续抬腿前水平检查及左前腕参数接回路径尚未在该候选上真跑，不以准备好入口代替行为验证。没有新增移重、尾部控制、实际力矩传感器项目或更大的驱动上限；原事项保持在办，不关闭、不取消其它未完动作。

## 用户修订：胸部水平不再作为门槛

用户拍板：2026-10-19，撤销自由基座静站与后续承重抬腿的胸部世界倾角 ≤1° 条件，并同步修正代码与事项；本轮不自动启动物理测试。该条件不是生物学要求，也不是现有零目标关节 PD 必须满足的驱动能力定义。允许胸部俯仰或侧倾，不代表取消整机支撑、安全和动作目标判据。

`rl_exp/tools/diagnose/palm_spatial_standing.py` 删除抬腿前胸部水平中止分支与最终通过门槛，逐步胸部世界姿态及分窗口最大倾角继续输出，仅作观测。原根倾角/下沉、关节偏差、速度、支撑载荷、非法接触、离地/卸载/落掌及失败退出条件保留。CLI 增益覆盖入口保留，但本次未调整任何 PD、力矩/速度上限、资产或正式配方。夹具左前腿测试的严格水平条件仍用于核验隔离夹具，不迁移成自由整机前提。

回归在原 `--self_check` 内，以构造样本提取并执行真实 `_run` 中胸部倾角赋值之后的安全停止分支和最终判定，不覆盖此前的仿真采样/状态读取链：胸部 2°、其它条件满足时静站与抬腿均应通过；失去支撑、根下沉/倾斜、关节偏差、竖直速度、非法接触超限及既有停止状态仍应失败。原胸部门槛保留时同一回归报 `AssertionError: ('benign chest tilt rejected', False, …)`；撤销后输出 `STANDING_LIFT_SELF_CHECK_OK`。这验证代码判定，不替代仿真中的实际抬落。

修订实现提交 `6a1b631`，源码 SHA256 `10e2950d0dbcd0c726d0f4af6b00045288d6b1e9eededa9da2fcc8a460e0e53b`。本轮自检及事项格式检查通过，全套离线检查通过（37/37）；代码提交的 pre-commit 静态闸门通过，不作为新增物理通过证据。独立上下文已对本切片审查，反馈的旧阈值复读命令与测试覆盖表述已修正；不替代原事项关闭审核。

当前自检复读：

```powershell
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/diagnose/palm_spatial_standing.py --self_check
```

原始报告仍保持 `standing_failed` 和当时退出 1，不修改历史产物或伪造新通过报告。此前读数只证明未达到当时人为水平条件，不能由此认定抬腿必然失败、实际电机饱和或驱动不合格。胸俯仰 2 Hz 候选不因撤销条件自动升级基线；后续沿用已绑定的合格静站配置，并显式声明腕部覆盖及载荷条件。实际力矩通道和其它原有未完动作继续保留。
