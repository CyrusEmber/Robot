# 左前肘自重下逐级升速观测

## 适用范围

用户询问其它部位后，同意继续验证左前肘。本轮仅主动激励 `lf_elbow_joint`，不把左后膝结果复制为其它关节通过；对照取[左后膝升速记录](2026-10-22-lizard2-left-knee-speed.md)。复用同一候选、固定根高 2 m、31 body 自重、原具名连接过滤，以及原力矩参考的全部 PD/上限。其它关节保持各自 PD 的零目标，允许耦合运动，并非机械锁死。

左前肘实际读回 Kp=220、Kd=14.950068、力矩上限 180 N·m、速度上限 10 rad/s；TGS/`enable_external_forces_every_iteration=False`、200 Hz 物理、50 Hz 位置目标、后端速度目标全零。没有额外载荷、增益扫描或改变训练/冻结配方。本记录为执行者自检，不替代独立关闭审核或正式采用。

## 验收条件

先按左前肘实际树/网格单独运行 `body_precheck.py`：其它关节零位，肘角 −1 至 +1 rad 每 0.05 rad 一点，另加 ±0.768 rad，共 43 姿态；全部 18 个碰撞实体，仅原直接相连排除及六对具名连接过滤。离散通过只供本轮轨迹准备，不声明连续安全或动态漂移姿态已检。

几何通过后采用 ±0.768 rad 往返，单程五次曲线时间 1.44/0.72/0.36/0.24/0.18 s，对应连续参考峰值 1/2/4/6/8 rad/s。每档先静置 5 s，正负各保持 1 s、返回后恢复 1 s；误差窗口取保持/返回最后 0.2 s。幅度经本肘预查，时间/载荷/预算与获准的升速方案相同，目标峰值不当作实际速度。

五档共 11,352 个命令采集物理步、56.76 s，硬上限 12,000 步，执行墙钟上限 900 s。环境启动/reset 不计入命令采集步数。主动停止线：肘角 1 rad、其它角 0.35 rad；肘后端或位置差分速度 9 rad/s、其它后端速度为各自 cap 一半；肘步平均轴向载荷 144 N·m、接触 1 N；非有限值、缓存/后端错配、预算耗尽也停止。性能不足不自动重跑或加 PD。

每物理步保存完整 q/v、位置/速度目标、incoming wrench、活动轴投影、显式 effort 输入、接触与时轴。永久复读器核绑定、50 Hz 目标列、q 差分速度、误差、载荷投影与 cap 占比，不只读报告摘要。入口新增 `--prepare --joint lf_elbow_joint`；执行与复读从绑定计划取 joint，不接受另行覆盖。历史无 joint 字段仍明确解析为左后膝，旧报告已实读复算通过；历史 `knee_*` 停止参数名保留以兼容旧证据，其数值作用于当前主动关节。

## 结果

预查 `pass`、`whole_machine=pass`，43 姿态、5977 次碰撞配对检查。五档一次采完，退出 0，`completed=true`、`speed_observation_completed`；11,352 步，执行墙钟 147.25 s，无续接/重采，无停止触发，接触全零。所有 PD/上限与原力矩参考逐值一致，实际 scene TGS/false 与重力已读回。

| 连续参考峰值 rad/s | 位置变化实测峰值 rad/s | 后端速度峰值 rad/s | 最大直接角误差 rad | 肘最大绝对步平均轴向载荷 N·m |
|---:|---:|---:|---:|---:|
| 1 | 0.988120 | 1.013853 | 0.084452 | 5.094490 |
| 2 | 1.931822 | 1.958212 | 0.151495 | 6.654780 |
| 4 | 3.501445 | 3.530363 | 0.268683 | 14.441957 |
| 6 | 4.686660 | 4.686901 | 0.361451 | 23.383490 |
| 8 | 5.534792 | 5.516606 | 0.425862 | 32.266834 |

本轨迹名义 8 档实测约 5.53 rad/s（69.18%），与同工况左后膝约 5.54 接近；这不证明两者物理最高速度相同，也不能仅凭相似结果锁定唯一原因。肘载荷峰值占 180 N·m 约 17.93%，后端速度峰值占 10 rad/s 约 55.17%，未观察到肘接近这些上限，不能将速度差归因于已证实的限幅。载荷为后端每物理步平均活动轴投影，不是子步瞬时电机峰值；手工轴投影复核一致，显式 effort 输入全零。

正向保持最大直接误差约 0.022842–0.022851 rad，负向约 0.019388–0.019395 rad；返回零目标约 0.002287–0.002311 rad。较大摆角及本次零目标恢复窗口均未达到旧 0.002 rad 线；未据此把稳定驱动写成关节不能用，也未自动提高刚度。没有独立验证当前左前肘受载 ±0.02 rad 小动作的精度，不把本轮保持窗口冒充该项通过。

**全机余量仍需分开判断。** 全机最大载荷占比来自胸俯仰：共同静置初期 0.12 s 约 −265.923 N·m，占 280 cap 的 94.97%。t>5 s 的最大载荷仍来自胸俯仰，随五档分别约 236.552/237.567/242.744/247.807/250.996 N·m；最高档 6.4 s 达 89.64%。采样中任一轴达到 99% cap 的步数均为零，不据步平均量保证子步瞬时余量。不能用肘的低占比代表整机余量，也不把悬空固定根读数与四足承地工况混为一谈。

全机实际位置到 URDF 限位的最小余量约 0.444782 rad；各档终态 actor/FK 通过原检查，不能据终态声称运动全程独立姿态已验证。原始证据的伪造实际速度、错目标列、错时轴三个内存破坏均被实际复读器拒绝，原文件未改。自检、历史膝报告兼容复读及新肘复读通过；完整离线套件 `ALL_OFFLINE_CHECKS_PASSED (37/37 in 64.1s)`，未新增默认闸门。

## 证据引用

本机工件不承诺入仓。永久入口 `rl_exp/tools/diagnose/palm_speed_probe.py`；本轮准备、采集及最终读取器源码一致。输入/原始数组摘要和动作通道读回取绑定报告；实际源文件快照留在各输出目录。

| 工件（相对仓根） | SHA256 |
|---|---|
| `rl_exp/out/lizard2_b_elbow_plan_20261022/attempt01/plan.json` | `a24235a1715c24ae78676830bda738dbd24d6dde1fec58938883bbd7a46d1b8e` |
| 同目录 `geometry_config.json` | `ceeab5a0842c369fb254865473784d28b672d49a87aa671da7ce903fc6c9af8f` |
| 同目录 `geometry_report.json` | `ebb4ddd210588001d83ba5065a47d1f20fd641a6f83e457874ea5befb472a755` |
| `rl_exp/out/lizard2_b_elbow_speed_20261022/attempt01/report.json` | `9737ba5630e1e735b24ec839aaf30821453ab9ad95da192a0eec882434abe321` |
| 同目录 `source.py` | `0756dad95d7c3b65aa29bc8e2758bb7dd4b86b485bff1da86fbe895d2a94cd3a` |
| `rl_exp/out/lizard2_b_elbow_speed_audit_20261022.json` | `6dc44f4866c5649f3b115f061fc57701f30423c6fbd297c7b2553466ec318f63` |

日志在 `rl_exp/out/`：`lizard2_b_elbow_prepare_20261022.log`、`lizard2_b_elbow_speed_20261022_attempt01.log`、`lizard2_b_elbow_speed_audit_20261022.log`、`lizard2_b_elbow_selfcheck_20261022.log`、`lizard2_b_knee_compat_replay_20261022.log`、`lizard2_b_elbow_offline_20261022.log`。预提交钩子输出另存 `lizard2_b_elbow_precommit_code_20261022.log` / `lizard2_b_elbow_precommit_docs_20261022.log`。

只读复算，不启动仿真；输出须为新路径：

```powershell
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/diagnose/palm_speed_probe.py --self_check --out rl_exp/out/unused_speed_selfcheck
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/diagnose/palm_speed_probe.py --replay rl_exp/out/lizard2_b_elbow_speed_20261022/attempt01/report.json --approved_report_sha256 9737ba5630e1e735b24ec839aaf30821453ab9ad95da192a0eec882434abe321 --out rl_exp/out/lizard2_b_elbow_speed_replay.json
```

## 未覆盖边界

左前肘五档预算已执行完，不自动重复；尚未证明实际 8 rad/s、10 rad/s 触限机制或同条件有/无限速对照。额外负载、自由根/承地、五轴组合及其它关节主动升速仍缺证。腕踝与胸颈尾不能照搬 8 rad/s，原限速与几何范围分别约束后续方案。

胸俯仰的固定根悬空余量、肘膝较大摆幅静差/快轨迹滞后及旧正式配方实际 cap 来源继续交 B/C；E/D/S5 的集成与正式采用、S6 的 RL 协调/性能各自继续在办。本记录不批准训练，不关闭上述缺口。
