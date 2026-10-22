# 默认速度目标定案与胸俯仰载荷复核

## 适用范围

**用户定案：当前默认驱动的关节目标速度始终为 0 rad/s。RL 只输出目标角度；不增加速度动作，不从相邻动作推导非零参考速度，不加入轨迹插值/速度前馈层。** 此规则适用于后续当前方案的驱动诊断与训练接入，除非用户另行修改决定。实际关节速度允许非零，速度上限是另外的配置；本定案不把“速度目标零”解释为锁死关节。

沿用当前 `palm_spatial` 候选、全部已有 PD/力矩与速度上限、TGS/`enable_external_forces_every_iteration=False`。冻结配方和正式资产未改。前序[左肘升速](2026-10-22-lizard2-left-elbow-speed.md)、[左膝升速](2026-10-22-lizard2-left-knee-speed.md)与[承地静站](2026-10-22-lizard2-standing-joint-force.md)保留各自工况；本次新增胸部分析只读原始数据，没有新物理步或额外载荷。

## 验收条件

`palm_speed_probe.py` 的新物理执行入口须在启动仿真前拒绝历史非零速度计划；当前物理路径继续逐步核对后端速度目标全零。已完成的历史 B 组必须保留真实输入和源码，可离线复读，但不再提供生成/执行该对照的入口，不把非零值抹掉伪装成当前默认试验。

胸部复核消费左肘五档零速度试验的全部原始 q、轴向载荷及绑定 URDF。复用已有 `csc` 树与 FK，在每档静置末 0.2 s、正负保持/返回末 0.2 s 的平均实际姿态，按胸俯仰下游每段质量和质心计算自重力矩；另用总重力势能对胸角的中心差分交叉核算。保存每段贡献、窗口内位置变化、载荷差值，不把静力计算当快速运动力矩预测或独立姿态测量。

## 结果

### 当前控制输入定案已落实

新物理入口仅接受原零速度目标的逐级升速计划，移除未发布的非零速度对照准备入口和运行时速度目标写入分支；历史读取器仍按实际目标区分 A/B。新物理计划拒错由持久 `self_check()` 调用真实执行前校验函数：在内存中用原通用校验替代该限制时，自检报 `historical nonzero velocity experiment accepted for new physics`；恢复限制后通过。没有增加仓库默认闸门或新依赖。

### 已结束的速度参考对照仅保留机制用途

历史对照为左前肘相同 ±0.768 rad 位置轨迹、连续参考峰值 8 rad/s，200 Hz 物理/50 Hz 目标、固定根自重、同 PD/上限、TGS/false；A 速度目标为零，B 为预写五次曲线的解析导数，按 50 Hz 采样保持。B 的实际目标速度峰值约 7.80369 rad/s。每组 1944 步，两组合计 3888 步、19.44 s 命令采集，执行墙钟约 62.36 s；两组都完成，无停止触发。该物理对照在本次定案之前已经结束，本次只复读，不能重复执行。

| 项目 | A：速度目标零 | B：历史参考速度 |
|---|---:|---:|
| 位置差分实测峰值 rad/s | 5.534792 | 8.317131 |
| 最大直接角误差 rad | 0.425862 | 0.133119 |
| 静置后全窗口角误差 RMS rad | 0.106385 | 0.024246 |
| 肘最大绝对步平均轴向载荷 N·m | 32.266834 | 54.869949 |
| 运动期胸部最大载荷/cap | 89.64% | 95.64% |

A 的全部 q 与原最高档逐值相同，最大差为零；A/B 的初始 q 与每步位置目标相同。B 最大误差降低约 68.74%、静置后 RMS 降低约 77.21%，但正负保持静差仍约 0.02285/0.01940 rad，返回约 0.00231 rad。B 存在峰值速度和位置超出参考端点的现象，不称高速精确跟踪通过。该结果只证明改变速度目标在此单肘工况中有明显影响；**当前默认能力仍按 A 判断，B 不进入训练一致性验收、不批准更改训练或增加 RL 速度输出。**

四类内存破坏（伪实际速度、错位置目标列、错时轴、错速度目标）均被实际读取器拒绝。另将真实 B 组速度目标在内存中清零，读取器明确拒绝，日志保留；原始文件未修改。PD 拆项只作代数估计，不能替代 PhysX 隐式求解的实际驱动力矩。

### 下一项：胸俯仰悬空高载荷的自重来源

左肘五档的静置窗口均给出胸关节下游质量 39.9396 kg，包含胸段、头颈及双前肢。按实际姿态计算所需驱动补偿约 −234.993605 N·m，后端平均投影约 −234.991948 N·m，残差约 +0.001657 N·m；胸位置差分速度为零。该窗口的自重力矩贡献主要为 `neck_pitch` 所属刚体约 −132.538 N·m、胸段约 −55.556 N·m，其余为前肢及其它下游段，名称不改变实际质量归属。

五档共 25 个静置/保持/返回窗口，载荷平均值与该姿态自重预测的最大绝对差约 0.012706 N·m；叉乘力矩与总势能差分的最大差约 4.75e−9 N·m。这支持固定根悬空静置时的高载荷主要由下游自重解释，未发现需要用“增益异常放大”解释这部分静态读数的证据。它不解释启动瞬间或快速运动的全部峰值。

原零速度左肘最高档的胸部运动期峰值约 250.996 N·m，占 280 cap 的 89.64%；共同启动瞬间约 265.923 N·m，占 94.97%。另独立复读原自由根承地 5 s 数据，胸部全程峰值约 106.680 N·m，占 38.10%，最后 1 s 峰值约 76.977 N·m；承地静站的原姿态判据失败仍保留，不能由本次载荷复读改为成功。悬空与承地的支撑条件不同，不能用前者直接代表行走余量，也不能用后者排除其它动作峰值。

本轮自检、历史 A/B 复读、五档零速度原始数据复算及承地复读均通过。完整离线套件 `ALL_OFFLINE_CHECKS_PASSED (37/37 in 51.9s)`，日志 `rl_exp/out/lizard2_b_zero_velocity_offline_20261022.log`；事项检查通过，未关闭任何事项。代码/文档提交前钩子分别保存在 `lizard2_b_zero_velocity_precommit_code_20261022.log` / `lizard2_b_zero_velocity_precommit_docs_20261022.log`。

## 证据引用

永久入口为 `rl_exp/tools/diagnose/palm_speed_probe.py` 与既有 `palm_standing_force_audit.py`。本机原始工件不承诺入仓；历史采集源码留在实际输出目录，最终只读器含后续零速度限制与胸部分析，不能冒充原采集源码。

| 工件（相对仓根） | SHA256 |
|---|---|
| `rl_exp/out/lizard2_b_velocity_ref_plan_20261022/attempt02/plan.json` | `19c117641c3968e76de2cf45b0c73ae1f308b538da9da53b96295991d5d9adf9` |
| `rl_exp/out/lizard2_b_velocity_ref_20261022/attempt01/report.json` | `d87fba63d1d793001dd00cf20da88d1fd5c462f923bb657616e64c1cd7929ad3` |
| 同目录 `source.py`（历史采集） | `1f8813d370b8e1575bdb73912ef23a28eaeb0a85393d478058a741411a1a4593` |
| `rl_exp/out/lizard2_b_velocity_ref_audit_20261022.json`（原读取器） | `420f0878e0e6d11e08bfeda6cf0cdf6778574023ea971aa401f9cb410756d77a` |
| `rl_exp/out/lizard2_b_velocity_ref_history_replay_20261022.json` | `820e2e6f586db1db0a283740bb21d9e4515d18ffbd70b6ab6cb1a30c52c042c9` |
| `rl_exp/out/lizard2_b_chest_gravity_audit_20261022.json`（五档零速度输入） | `d79684d10d6cc41c66468f192e16f43af1402b6fabb21d8b03306ed5b6cfcc15` |
| `rl_exp/out/lizard2_b_chest_standing_replay_20261022.json` | `619c825b212a9dabbe5d48380859b5a3b9c4e0cc869ea18c40d422081b04e340` |
| `rl_exp/tools/diagnose/palm_speed_probe.py`（本轮最终读取器） | `53cc95d3ad943935aca2b4e71eadc78356f8d069d70dd9be3d96f04502678b3f` |

输入左肘报告/几何/原始数组取左肘升速记录，承地输入取承地静站记录；本记录不另造输入身份。日志均在 `rl_exp/out/`：`lizard2_b_velocity_ref_20261022_attempt01.log`、`lizard2_b_velocity_ref_erased_target_20261022.log`、`lizard2_b_zero_velocity_guard_before_20261022.log`、`lizard2_b_zero_velocity_guard_after_20261022.log`、`lizard2_b_chest_gravity_audit_20261022.log`、`lizard2_b_velocity_ref_history_replay_20261022.log`、`lizard2_b_chest_standing_replay_20261022.log`。

从仓根只读复算，输出须换全新路径，不需要启动仿真：

```powershell
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/diagnose/palm_speed_probe.py --self_check --out rl_exp/out/unused_speed_selfcheck
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/diagnose/palm_speed_probe.py --replay rl_exp/out/lizard2_b_elbow_speed_20261022/attempt01/report.json --approved_report_sha256 9737ba5630e1e735b24ec839aaf30821453ab9ad95da192a0eec882434abe321 --out rl_exp/out/lizard2_b_chest_gravity_replay.json
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/diagnose/palm_speed_probe.py --replay rl_exp/out/lizard2_b_velocity_ref_20261022/attempt01/report.json --approved_report_sha256 d87fba63d1d793001dd00cf20da88d1fd5c462f923bb657616e64c1cd7929ad3 --out rl_exp/out/lizard2_b_velocity_history_replay.json
```

## 未覆盖边界

本次没有新物理采样；静力方法依赖已绑定质量/质心和实际 q，复用同一 FK，不独立证明所有运动中姿态或源件质量设计合理。步平均载荷不界定子步瞬时电机峰值，cap 占比也不是硬件连续额定/热余量。未增大胸部力矩或 PD，不据此降低 cap。

下一步在当前零速度目标约定下继续补 B/C 的具名动作与载荷边界；真实限幅正例、有/无限速对照、其它关节主动升速、额外载荷及行走余量仍未验证，运行前沿用事项要求核定具体预算。E/D/S5 集成与正式采用、S6 的 RL 协调/性能继续在办。生物角速度讨论没有形成新的数值限速决定；机械全范围不等于实际步态摆幅。此记录为执行者自检，不关闭事项、不批准训练。
