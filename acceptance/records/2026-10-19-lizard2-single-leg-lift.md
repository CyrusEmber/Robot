# lizard2 左前腿抬落：实际未离地与报告失败修复

## 适用范围

承接[承重静站记录](2026-10-19-lizard2-loaded-standing.md)，在其同一自由基座、重力、碰撞和接触读回链上执行一次左前腿抬起—保持—落回动作。仅修改隔离目标和具名增益，不改正式资产、限位、力矩/速度上限或配方。本轮三个物理候选均未通过抬起判据，不能作为单腿动作成功或 B 完成的证据。

## 验收条件

- 从[接触边修正记录](2026-10-19-lizard2-contact-path-correction.md)的组合路径选择左前掌实际几何高度最大的节点，仅取该腿五个关节目标，其余目标为零。新中立到目标的直线关节桥检查 33 个有限采样点：限位、实体碰撞、地面穿透、翻掌和反曲。该有限检查不构成连续域证明。
- 复用实际静站末帧的 actor 姿态、URDF 质量/质心及实际承重 body；排除左前掌后，对其余承重 body 的近底部网格点求水平凸包，要求质心投影在内。这只是几何前提，不证明实际接触压力分布或动态稳定。
- 时间固定为静站 5 s、quintic 伸出 3 s、保持 2 s、返回 3 s、恢复 3 s，共 16 s；物理及目标步长 0.005 s。保持段最后 1 s 要求实际左前掌整个碰撞网格最低点至少离地 0.01 m、该掌到唯一地面的接触力范数不超过 1 N、其余三足地面竖直力各至少 5 N。允许原自然落地尾段承重。
- 静站末 1 s 和恢复末 1 s 要求四足各至少 5 N；保持及上述窗口要求根下沉不超过 0.02 m、倾角不超过 0.1 rad、全体关节跟踪误差不超过 0.1 rad、根竖直速度绝对值不超过 0.05 m/s。恢复末段掌底不高于 0.005 m，平均总竖直支持力与重量偏差不超过 20%；全程掌底不低于 −0.005 m。
- 硬停止沿用静站的根下沉 0.15 m、倾角 0.35 rad、关节跟踪误差 0.35 rad、非批准身体地面力 5 N。读回实际动作名称/索引/单位缩放、零偏置、全部实际 Kp/Kd 和 body→地面接触过滤路径，不以目标 FK 或 body 总合力替代实际离地/卸载。
- 原计划两个物理候选；首跑暴露保存故障并分析腕部承重与机体下沉后，执行前明确增加为总共三个：原静站 PD、仅前腕组调整、再仅腿部组调整。目标、时序及判据相同；达到三次即停止，不扫描幅度或频率网格。失败报告可读、失败进程非零退出。

## 结果

### 几何输入与物理结果

目标来自组合路径 c=0.875 的 forward_air 节点。左前腿目标（rad）：shoulder_swing 0.045461547306661694、shoulder_abduct −0.05770792081616326、shoulder_twist −0.04163052472831483、elbow 0.08513682796285779、wrist 0.019309178119866863。名义根姿态下掌底高度为 0.030569875449533823 m；实际加载静站、排除左前掌后的几何凸包余量为 0.22506112937376516 m，质心水平坐标为 [−0.004942990249021553, 0.00020496335985172368] m。桥的有限采样通过；后两次计划补入显式反曲检查，目标未变。

三个候选都运行完 3200 步，没有触发硬停止，落回后四足站姿和恢复重量平衡均满足条件；抬起保持段均失败。以下频率仅表示由已核惯量生成 Kp/Kd 的组别规则，阻尼比均为 1；颈俯仰保持 2 Hz、踝及其它脊柱保持 1 Hz。

| 物理候选 | 保持段最小掌底高度 m | 保持段最大左前掌地面力范数 N | 其余三足承重/姿态条件 | 抬落判定 |
|---|---:|---:|---|---|
| 合格静站 PD：腿 6 Hz、前腕 1 Hz | −0.00000671778641422871 | 131.9717559814465 | 通过 | 未通过：未离地、未卸载 |
| 腿 6 Hz、前腕 6 Hz | −0.000006861529076737649 | 131.2575531005871 | 通过 | 未通过：未离地、未卸载 |
| 腿 12 Hz、前腕 6 Hz | 0.0000011034763138656478 | 29.07162666320827 | 未通过：右后足最小竖直力 2.0991733074188232 N | 未通过：未离地、未卸载、剩余足承重不足 |

第一行由首跑完整样本前缀恢复后重新判词，原 report.json 无有效完整 JSON，详见下节。最后候选保持段根最大下沉 0.00401813 m、倾角 0.01397445 rad、跟踪误差 0.04181739 rad，均满足条件；右后足承重不足是其 supported_hold 失败的具体原因。恢复平均总支持力 706.3238593974517 N，与运行时重量 706.3238919067384 N 一致；所有非批准身体的地面力均为零。

首跑 9.5 s，名义目标含初始间隙时的掌底高度约 0.03157 m，将同一目标放到实际根姿态后仅剩 0.00474744 m；实际腕角约 −0.03376 rad，相对目标约差 −0.05307 rad。腕部重力矩估计约 −0.36512 N·m，原 Kp 约 0.35181 N·m/rad，简单静态比值约 −1.03782 rad，已超腕部约 ±0.52360 rad 的范围；该估计解释调整腕组的动机，不是接触耦合系统的精确稳态解。只改前腕没有解除贴地；提高腿组改善下沉和卸载，却同时卸掉右后足载荷，仍未形成合格抬脚。

结论限于本目标和三个配置：**名义几何抬脚不等于承重后实际抬脚**。保留原已通过的静站 PD，两个失败增益候选不升级为基线。下一步需先明确抬脚前载荷转移、机体及剩余支撑足目标，再给出一次有预算的局部轨迹；不从本结果直接断言资产不可用、增加自由度或继续盲扫 P。

### 报告保存及退出码缺陷

首跑完成后，判词中的 NumPy bool 无法被 JSON 序列化，report.json 写到 lift_verdict 中途失败；异常分支再次保存同一对象，又失败，随后 App.close 将进程结束为 0。原 report.json 和 failure.json 保留原样，均不能当完整报告读取。

从首跑 report.json 中 `lift_verdict` 前的完整对象字段恢复成独立 recovered_samples.json，保留全部 3200 个原样本、输入身份和最终实体，不补造缺失判词。当前 `_lift_verdict` 对这些样本重算后的结果见 serialization_exit_regression.json，明确为未通过。

修复一：判词布尔值统一转 Python bool，可完整序列化。修复二：即使 failure.json 再次保存失败，也分别打印保存异常和原始异常并 flush，以 os._exit(1) 保住失败状态。后两次真实物理失败均留下完整报告、进程退出 1。

离线自检覆盖曲线边界、成功合成样本、贴地/仍承重/缺恢复反例及判词序列化；还从实际 `_run` 抽取异常处理 AST，在子进程注入原始异常、保存异常和会退出 0 的模拟 close。首跑旧处理返回 0 且到达 close，修复后返回 1、不达 close、两种异常可见。最终版本 `--self_check` 通过；`--self_check --break_failure_handler` 去掉保存保护后以 assertion/退出 1 失败，证明确实覆盖吞错路径。此子进程测试不是又一次 PhysX 故障注入，不替代跨入口成功/失败真跑要求。

## 证据引用

实现提交 `171548e`：`rl_exp/tools/diagnose/palm_spatial_standing.py`；本轮最终源码 SHA256 为 `4fa61f228930b5ffb9dad276538187bedc9e110355f0c3d69ebdb939fe90ed94`。各物理目录的 source.py 保存实际运行版本；最终追加的离线自检不改物理目标/判词。该代码提交的 root hygiene、framework pin/self-test、DR parity、version docs、work docs、obs protocol/live 闸门通过；闸门不替代实际动作验收或独立审核。下列原始大报告、产物和日志在本机，不承诺入仓。

| 文件（仓根相对路径） | SHA256 |
|---|---|
| `rl_exp/out/lizard2_b_standing_neck2_20261019/report.json` | `f415264793731a71091ed9e167edd6bce1cfe4ad615772b94c080cef579a20e2` |
| `rl_exp/out/lizard2_a_contact_delivery_20261019/report.json` | `1d5ae02e0f7c4724144f1eb956c25f95899a53367603a0662c5196ae4052dc3b` |
| `rl_exp/out/lizard2_b_lift_plan_20261019/plan.json` | `f9e96950f5f2d67a8764e62998d09097d3648d54cd0f9e5be8b08a4db0fad26a` |
| `rl_exp/out/lizard2_b_lift_plan_wrist6_20261019/plan.json` | `47c67c6ce4a81a340023ef16136f5aef22883328a41d8e80f1f3861ff6788436` |
| `rl_exp/out/lizard2_b_lf_lift_20261019_run01/recovered_samples.json` | `f7e1334b9870dea5ea015836b4ad704f2e105c975ebc8c3a34210fcb71eb12da` |
| `rl_exp/out/lizard2_b_lf_lift_20261019_run01/serialization_exit_regression.json` | `73d1d45ab0434f77c97c6d41b5e61dd2c2feb65b31ae08a9e0bf522ada1f1741` |
| `rl_exp/out/lizard2_b_lf_lift_wrist6_20261019/report.json` | `3513de8871eb9dfe867256dc14093fb707224ae717aabbc93c7993bbd2c40d65` |
| `rl_exp/out/lizard2_b_lf_lift_legs12_20261019/report.json` | `7f53463b5cfef4418d2785c81d00b4b63de341a3b0ef8216c8ad5de63b2f8abc` |
| `rl_exp/out/lizard2_b_lf_lift_legs12_20261019/evidence_index.json` | `33cb06ab5f1613cd93709f9aef42baa9350907ae1c82c66f9f9172fe1a921dc4` |

索引逐文件绑定上述两份计划和三次物理目录的 JSON/源码，包括未完成写入的原件。第二次 source.py SHA256 为 `8e4abb3e9ada6fbc818f031300aaa4303c7cd8fac65d036f2f66b79dba089a4a`，第三次为 `81e7dcc01aa6d201662af83e82747dea8d4d5f3763e2db5d7f4ff96fef7e98fa`。第二/三次 lift_manifest.json 分别为 `8024b04177085c94f55fbdf0ed621f30175215642ec904947727a7cd49438831`、`fe1cc1a7ece9234350d0a1fdd0933189ec6216373126bdaa542e9ea7c766ee1f`；原合格静站 manifest 为 `5942253636b0f3b4006135bcec39c74711f9796afc2f1b47707199ad5f87908b`。URDF 保持 `2c78117020458d5e7934219a2064bf7241430b81c2a736acd8cc0761c7a1461f`。

复读入口（仓根 PowerShell；用新输出目录，不覆盖原证据）：

```powershell
# 当前计划设置已统一为三次预算，首跑历史计划保留原两次预算，不直接喂当前 loader。
@'
import sys
from pathlib import Path
sys.path.insert(0, 'rl_exp/tools/diagnose')
import palm_spatial_standing as s
s._make_lift_plan(Path('rl_exp/out/lizard2_b_standing_neck2_20261019/report.json'), Path('rl_exp/out/lizard2_a_contact_delivery_20261019/report.json'), 'lf', Path('rl_exp/out/lizard2_lift_plan_replay'))
'@ | & E:/IsaacLab/env_isaaclab/Scripts/python.exe -B -

& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/diagnose/palm_spatial_standing.py --lift_plan rl_exp/out/lizard2_lift_plan_replay/plan.json --out rl_exp/out/lizard2_lift_base_replay --viz none --device cuda:0
# 两个具名对照分别增加 --wrist_frequency_hz 6，以及 --wrist_frequency_hz 6 --leg_frequency_hz 12，并各用新 out。
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/diagnose/palm_spatial_standing.py --self_check
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/diagnose/palm_spatial_standing.py --self_check --break_failure_handler
# 最后一条预期非零；三个物理候选亦预期判词未通过并非零退出。
```

## 未覆盖边界

没有合格单腿离地、后腿/镜像抬落、载荷转移轨迹、承重直行或完整步态。本次没有把失败增益升级为候选，也未为其补全其它动作的标定。几何凸包含尾段，不能称为纯三足支撑验证。

重建请求 `Kp*(q_target-q)-Kd*v` 仅是代理量，不是实际 motor torque。第二/三次最大请求与 cap 比值约 0.98993/0.82839，不能据此证明真实饱和裕量；静站记录中的胸俯仰瞬态风险和实际驱动力通道缺口仍在。正式导出、消费者链、有效限速、最终外观/动作确认及跨入口异常退出审核均继续由原在办项维护；本记录不关闭任何事项，也不是独立关闭审核。
