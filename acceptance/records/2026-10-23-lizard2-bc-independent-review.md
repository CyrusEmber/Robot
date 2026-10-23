# lizard2 B/C 有限证据输入独立审核

## 适用范围

本审核由未参与 B/C 执笔的新上下文执行。先读仓库 `AGENTS.md`、`.codemaker/rules/work-ledger.mdc`、台账工具模块文档，再按 `FILEMAP.md` 定位，读取家族身份、总项 B/C/D 与关闭条件、用户取消决定及必要来源。主对象为[交付清单](2026-10-23-lizard2-bc-handoff.md)，审核时文件 SHA256 为 `040dc9ddfc817b3241b1a77d94d7ecc0a60aeb1d01fd0a717e3acd1616b1c89a`。

收尾元数据修订后另行只读复核，当前主对象 SHA256 为 `e6b029dbfa649d24707bd4e046afb4057731daf40e07319dba1735e15037c474`；下述有限接收结论继续有效，范围未扩大到 S5 草案。

只判定现有 B/C 证据是否可作为 D/S5 的有限输入。遵循[计划盘点](2026-10-23-lizard2-plan-inventory.md)：不重开剩余限速边界、限矩或对称复测，不改变零速度目标和 TGS/false；取消与未测均不视为通过。未审核新增 S5 配置草案，不启动环境、物理或训练，不关闭或迁移任何 work。

## 验收条件

- 从原报告、manifest、实际资产和原始样本核身份；不以清单文字、读取器退出码或旧结论替代行为证据。
- 逐名比较旧全轴、六组合、当前左膝与承地的全部 PD/caps，区分自身增益不变和整机背景不变。
- C 十关节均具名核动作与 q/dq 观测顺序；检查非零样本，避免把相同宽度或全零数组误作语义一致。
- 复算原成功与失败判词，保留增量误差/直接目标误差、设置读回/物理能力、固定根/自由根的边界。
- 发现实际矛盾则具名退回；仅有已声明未知且已由用户取消的试验，不扩成新阻塞。

## 结果

**接受此有限 B/C 输入。** 未发现阻止 D 接收这组具名历史测量与当前设置的真实矛盾。此结论不等于 B/C 全域驱动验收、D 整体通过、S5 实装完成或训练放行，总项仍在办。

收尾元数据复核：直接检查工作区 diff，将主清单第 72、96 行逆替换为最初审核文字后，完整字节 SHA256 精确恢复为上述旧值，确认仅两处审核指针/检查结果文字改变。重新核四 report、四 manifest、六份交付 JSON 哈希均未变；读取 `precommit.log` 末段确认 `WORK_DOCS_OK` 及 `static gates passed`。未重复物理或全部读取器，不将这些格式/静态结果提升为行为证据，也不审核新增 S5 配置草案。

实际审核过程及复核结果如下：

1. 直接计算四份原 report、四份 manifest、各实际 URDF/USD 和六份交付 JSON 的 SHA256，均与交付清单及绑定相符。四报告 URDF 均为 `e8896feb8b0dbdbeaa35e74a01c2ffcb4ab38d89b52f221831b3f287943edd00`。固定根 USD 为 `0c5ffd157b39faf9b65907877badbe069ae5af69585124a1097f94956df3fe76`；承地自由根 USD 为 `721e8a4053c2a6114b5c4607e57ed34f287fe317f8f9abb47a5e857b845e9c0e`。两种基座身份没有混成同一物理工况。
2. 按各 report 的实际 joint_names 比较：旧全轴与六组合全部 Kp/Kd/effort/speed 相同；相对当前仅 `rl_knee_joint`、`rr_knee_joint`、`lf_elbow_joint`、`rf_elbow_joint` 四轴改变，Kp 由 65 变 220，Kd 由约 8.126 变约 14.950。当前左膝报告与承地报告全部 30 轴 Kp/Kd/caps 精确相同。当前 manifest 的 PD 经 float32 转换与 backend 逐名相等，默认 q/dq 均零。
3. **胸部覆盖必须保留**：当前 `chest_pitch_joint` manifest/backend effort cap 是 280 N·m，同 URDF 的 limit effort 是 80 N·m。这是原胸部试验已有的显式运行时覆盖，不是本轮发现的新物理失败。当前驱动参数须取 manifest；S5 若只按 URDF 重建 cap，会改变本次交付对象。速度 cap 则在 URDF、显式配置和 backend 逐名相同。TGS/false 的设置证据直接取 legacy 速度报告读回；没有用 true 工况替代。
4. 阅读持久读取器实现后，在内存执行五个读取入口：`self_weight_audit.audit` 的 102000 帧、`palm_standing_force_audit.audit` 的 1000 帧、`palm_velocity_limit_audit.audit`、`palm_policy_channel_audit.audit` 的构造与 36000 帧，结果均与交付 JSON 相同。左膝脚本通过 `runpy` 运行，唯一写出函数被内存捕获，6800 帧结果与 `knee.json` 完全相同，没有新建输出或改变原件。cap 字典的浮点键经 JSON 规范化后比较；三项既有配置/读回破坏检查实际拒绝。
5. 原全轴单轴标定在其固定根、自重、旧 PD、±0.02 rad 工况通过；独立 actor/FK 最大矩阵差约 `1.137e-6`。该判词采用自重平衡角的增量，不是全部关节直接目标误差均 ≤0.002 rad。当前左膝两例的增量及直接目标角判词复算一致，保持段通过；原 wrench 投影最大差 `3.052e-5 N·m`，源归因检查保留。步平均载荷小于 cap 不能证明实际限幅阈值、子步峰值或电机额定。
6. 对旧六组合全部 20400 原始帧另行重算 q[999] 基准、双向保持/返回/其它轴误差、静置漂移与绝对误差；逐项等同 report summary 和 `coverage.json`，并核 backend float32 位置目标、零速度目标及各原始 case 哈希。四肢组合保持误差约 0.00374–0.00382 rad，仍失败；颈、尾分别约 `9.108e-5`、`0.001582 rad`，原通过保留。本审核没有再次独立计算六组合 actor/FK，不能将 scalar 重算称作新的实体测量。
7. 当前承地完整 5 s、1000 帧无安全停止，复算状态仍为 `standing_force_observation_standing_failed`，失败为 root_drop 和两个前肘；最终根下降约 0.03499 m、全程最大关节目标误差约 0.13811 rad。读取器成功证明这份失败观测可复算，不使静站或承重协调通过。
8. C 十轴自身增益均与旧标定一致，已有各自单轴受载记录；颈/尾联合激励只覆盖它们自己的旧两组，胸部未加入该联合激励。四膝肘改变了整机背景，不能把自身参数相同写成当前背景已物理重验。诊断构造器实际解析候选 30 动作、冻结 v3 22 动作；冻结选择器直接套新关节集合仅剩胸颈尾 10 轴，不能只换资产路径。

C 的列绑定另外从原双符号非零观测夹具读取，核 q/dq/backend/raw action 与 policy 切片逐值相等，30 列各值不同；十轴映射如下。局部 q/dq 列为 r，动作列为 a，policy 绝对列分别为 `12+r`、`42+r`、`72+a`（均从零开始）。

| 关节 | r | a |
|---|---:|---:|
| chest_yaw_joint | 0 | 20 |
| chest_pitch_joint | 4 | 21 |
| neck_yaw_joint | 8 | 22 |
| neck_pitch_joint | 14 | 23 |
| tail1_yaw_joint | 1 | 24 |
| tail1_pitch_joint | 5 | 25 |
| tail2_yaw_joint | 11 | 26 |
| tail2_pitch_joint | 17 | 27 |
| tail3_yaw_joint | 22 | 28 |
| tail3_pitch_joint | 27 | 29 |

该额外观测复核是旧零增益状态注入夹具的消费链检查，不是当前 PD 下动态跟踪或承地试验。原清单将非零正式 obs/reset 接入交 D/S5，未将本表包装成正式训练权限已开放；此边界可接受。

## 证据引用

- 职责与判据：[总项 B/C/D](../../work/active/lizard2-body-drive-candidate.md)、[取消决定](2026-10-23-lizard2-plan-inventory.md)、[单轴记录](2026-10-21-lizard2-calibrated-loaded-pd.md)、[六组合](2026-10-21-lizard2-calibrated-combinations.md)、[左膝载荷](2026-10-21-lizard2-left-knee-joint-force.md)、[承地](2026-10-22-lizard2-standing-joint-force.md)。这些文档用于解释范围，原始样本是上述实际复核的依据。
- 四份 report 位于 `rl_exp/out/`：`lizard2_b_calibrated_20261021/report.json` SHA256 `c5500ee862043111f68b65d5e0c2a03a8a9d4154f143a8b38775fd3281def9dc`；`lizard2_b_combinations_20261021/report.json` `903ec4dcf17ba4c6bd7c7f2e4e4e1a68ed0794cf0c17f18356554574b386de82`；`lizard2_b_joint_force_probe_20261021/report.json` `13929c53eccdb51d454ade60cf071c3eaa614bf5c90684dd2e06f4017d2485ef`；`lizard2_b_standing_force_20261022_run02/report.json` `5a4c6a3f4572ab8db566637c64c67933ee5aa3857092b1fe7ed1b102724453c6`。
- 各自 manifest SHA256 顺序为 `edfdf31455f901f2a09db5b2a193d9b6eba860366a6930a70ef0f4c5cf5d563a`、`90aa3cc9e7d206341405d7606f655d6a916026c8fbac3dfc0e7f145430d84018`、`2cfa367012c32f2b5589abac32e09d6284d2193ed73c7757f29ba87a56d1c442`、`2f39ca4e6268d90cee08600510f05a3eae78c1272fdbeebb811ba911405569f2`。实际文件路径取各原 report，避免将不同 USD 名称当身份相同。
- 交付输出 `rl_exp/out/lizard2_bc_handoff_20261023/` 中 calibrated/knee/standing/caps/channels/coverage JSON 的哈希均直接复核，与[主清单](2026-10-23-lizard2-bc-handoff.md)所列一致；未改写工件。五个永久读取器位于 `rl_exp/tools/diagnose/`，复读命令取主清单和[通道记录](2026-10-22-lizard2-rl-coordination-handoff.md)；有输出的 CLI 必须使用新路径，不能覆盖本次证据。
- 通道原输入 `rl_exp/out/lizard2_e_fresh_tracking_20261020/report.json` SHA256 `6ae21d6db17a46f2431917c5488ace92b8cf6a57f4c87302ab36c8ca8937bb11`；额外观测样本 `rl_exp/out/lizard2_e_obs_values_20261022/attempt02/report.json` `6b6be92e7971f14dfbc318da8ed27ae1e167ba15a0342f18a78c0af3a6a431bb`，绑定 measured manifest `d876713b1a4aa6a4fef51f39bed284f4a15a01d562815eefefcf74eebfb77137`，实际 URDF 同上。来源/持久读取示例见[在线值记录](2026-10-22-lizard2-e-live-values-gait.md)。
- 审核仅写本记录；执行使用 `python -B`，未另存脚本、日志或复读 JSON。初始 Python 启动被文件沙箱拒绝后，获自动审查允许执行同一只读离线核验；没有绕过文件写入范围。
- 记录写入后运行 `check_work_docs.py`：`WORK_DOCS_OK (91 item file(s))`；本记录路径的 `git diff --check` 无报错。格式检查与本记录存在本身不作为行为通过依据。
- 元数据复核所读 `rl_exp/out/lizard2_bc_handoff_20261023/precommit.log` SHA256 为 `05ae80597340da7b6680c2e5b765bb58aaf8a9e99d0527f1502b8d312ce203fd`；主清单的历史审核哈希与当前审核哈希在本记录同时保留。

## 未覆盖边界

未证明当前全机背景下全部 30 轴或所有组合的同精度、全姿态/连续域、额外载荷、长期站稳、最大速度/力矩、硬件能力及步态。速度观测偏差仍会进入 joint_vel；存在具名可读通道不表示物理速度偏差已消除。未测范围保持未知，用户取消试验不恢复排期。

D/S5 仍须在实际接入对象核配置、动作权限/scale/clip、非零 obs、接触采样及根状态/动作缓存/后端目标/接触历史 reset；尤其应保留胸部显式 280 cap 与三种列序。以上是交接责任边界，不新增物理试验或手工动作要求。新配置采用、S5 实装、D 整体审核、协议与 S6 训练评测均不由本记录放行；本机原工件不承诺随仓分发，证据或参数改变后须针对变化重审。
