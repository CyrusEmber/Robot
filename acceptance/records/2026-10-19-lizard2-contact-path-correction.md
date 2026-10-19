# A 支撑接触边修正与几何交付

## 适用范围

承接用户“继续执行”及 `2026-10-19-lizard2-a-geometry-replay.md` 的支撑段材料点残差。只修正原支持相位 109 个参数位置上的关节姿态；候选资产、根平移、相位占比、关节限位、接地/穿地数值容差及碰撞集合均沿用输入。不启动仿真或修改正式配方。

## 验收条件

- 从真实掌网格选取支撑材料点，目标在同次支撑内固定于世界地面；跨周期按已绑定根净平移延拓。
- 保留掌面拨动自由，不将全片掌底固定或始终平掌当作需求。抬脚段保留原网格净空，并平滑连接支撑偏移。
- 所有修正姿态重新核完整五轴 FK、全机地面、全部非排除碰撞对、限位、反曲/翻掌、相位方向/离地及闭合；沿用原 129 姿态上限、每尝试 200 次优化残差调用和至多三次尝试，首失败停止。
- 修复前后用同一材料点位移口径比较，不以新锚点自身误差替代其它接地点位移；数值重建精度不升级为获准的物理滑动阈值。

## 结果

### 方法及实际落点

新增 `rl_exp/tools/diagnose/local_path_contact.py`，复用真实腿链、FK、网格、限位及原碰撞实现。支撑锚点取中立接地带的最前缘实际顶点，本候选四腿均为 391；接触边另取实际材料顶点 320。保持锚点世界位置、掌底接地及接触边的水平朝向，允许绕接触边拨动，不固定完整掌面法向。摆动段沿原轨迹，用五次权重接回支撑端点的水平偏移，最低网格高度仍取原采样值。

每帧以同帧原关节姿态为初值和局部修正边界，避免欠约束摆动解逐帧偏离原分支；相邻修正姿态另按原步距判据检查。优化在原调用预算内收敛，保留失败/耗尽读数。最后一帧复用首帧关节分支并核目标残差，不凭末端位置相近宣称闭合。

`local_path_view.py` 增加修正报告读取，严格应用已绑定的根偏移，不再对修正接触点重新拟合根运动；指定根轨迹有独立自检。报告只保留原相位安排作为来源，不复制原轨迹解析导数。修正后仍是有限姿态几何候选，原节点零速度/C2 结论不沿用到新关节轨迹。

### 本轮几何与材料点读数

最终 `rl_exp/out/lizard2_a_contact_delivery_20261019/report.json` 完成全部 109 姿态，`failure=null`、`completed_combined_loop=true`。完整关节分支首尾相同；每姿态重新检查 18 个碰撞实体、139 个检查对，原 14 个排除不变。未检出实体相交、超原容差穿地、翻掌、反曲、限位、相位方向/离地、落掌顺序或少于两掌几何接地失败。

| 同口径读数 | 修复前 | 接触边修正后 |
|---|---:|---:|
| 同一持续接地材料点的最大相邻采样水平位移 [m] | 0.0007961633893181728 | 0.000004727436951070913 |

上述修复前读数取原根平移回放，修复后取同一根偏移下的新姿态。修正后全部 240 个最低点材料读数在前后帧均位于原接地带；额外复读所有前后均在该带内的材料顶点，共 3017 个顶点/间隔读数，最大水平位移同为约 4.7274e-6 m，未靠仅挑选锚点隐藏其它接触位移。这些是已采位置的位移，不是物理滑动速度或周期总滑动量。

独立 FK 核得锚点最大三维位置误差 2.9266910836339607e-10 m；全机最低高度 −3.535626236228495e-10 m，仍按原数值容差解释。相对原姿态的最大关节修正 0.03206675906551188 rad，相邻修正姿态最大步距 0.03606330729373918 rad；单次优化尝试的记录调用数不超过 200，几何与最终残差读回单列，不作为优化迭代。

### 相关验证及失败边界

正常目标自检及回放自检通过；将真实支撑目标函数改回随原脚移动，目标自检以 AssertionError/退出 1 失败。按同一数值位置精度对照修复前后材料点位移，原数据不能满足重建精度，新数据满足；这不是新增仓库闸门或物理性能批准。最终修正/回放代码、报告及图像哈希匹配，原指定根偏移逐项相同，两份 GIF 均为 109 帧，确认没有携带旧解析导数；侧视和位移图已人工查看。

探索中，沿前帧欠约束解继续会在半周期落掌失败；同帧源姿态初值消除了该分支漂移。只固定一个掌底点时，其它接地点仍有残余位移；整片掌底 XY 固定的试作在首姿态停止，不能据此证明所有平掌方案不可达。当前保留边缘支撑与接触边朝向约束，而不继续扩大运动域。相关试作产物保留为诊断，不是最终交付或通过证据。

### 交付与未完责任

修正轨迹与配置归 `rl_exp/out/lizard2_a_contact_delivery_20261019/report.json`；侧/俯视动画、原身体坐标对照和世界根偏移/位移图归 `rl_exp/out/lizard2_a_contact_delivery_view_20261019/analysis.json`。该报告的 `root_translation` 使用给定根路径，图像哈希绑定实际产物。

A 当前交用户确认外观/动作，E/B/C 从本记录接修正候选，不再按旧记录重复处理原支撑段残差。资产与导出未改，E 只复验实际受新轨迹影响的消费；B 按新 q(c) 明确插值、时间映射、限速及承重跟踪，旧解析速度/加速度读数不能套用，C 接躯尾协同。几何阶段可供交接，不等于承重通过；A、专项与总项保持在办，未代做独立关闭审核。

## 证据引用

- 上游计划及原根运动：`work/active/lizard2-body-drive-candidate.md` A4，`acceptance/records/2026-10-19-lizard2-a-geometry-replay.md`。
- 原支持相位：`acceptance/records/2026-10-16-lizard2-support-schedule.md`；输入 `rl_exp/out/lizard2_palm_support_schedule_20261016/report.json`。
- 根轨迹来源：`rl_exp/out/lizard2_a_geometry_delivery_20261019/analysis.json`，不重拟合、不改写。
- 修正源码：提交 `90bd8ad` 的 `rl_exp/tools/diagnose/local_path_contact.py`，SHA256 `1fdbf779043cbb02eab467d3152b15b6c9880486077052f53e2bda9ca5da20e1`；该提交的仓库闸门通过。
- 回放源码：`rl_exp/tools/diagnose/local_path_view.py`，SHA256 `12bb09829bf03bbcbd4bafc6d49c146847df9d665eb50c326bb3b378d071af63`。
- 最终修正报告 SHA256：`1d5ae02e0f7c4724144f1eb956c25f95899a53367603a0662c5196ae4052dc3b`。本机产物引用不承诺入仓。
- 最终回放分析 SHA256：`aac769420725b0242e7011563ccc010f598211c1ad6e4a6a0477ab89be36fa6d`，路径为 `rl_exp/out/lizard2_a_contact_delivery_view_20261019/analysis.json`。

从仓根复读，输出目录必须不存在：

```cmd
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/local_path_contact.py --self_check
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/local_path_contact.py --self_check --break_target
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/local_path_contact.py --source_report rl_exp/out/lizard2_palm_support_schedule_20261016/report.json --root_report rl_exp/out/lizard2_a_geometry_delivery_20261019/analysis.json --output_dir rl_exp/out/lizard2_contact_reproduce
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/local_path_view.py --source_report rl_exp/out/lizard2_contact_reproduce/report.json --output_dir rl_exp/out/lizard2_contact_reproduce_view
```

`--break_target` 预期退出 1。采集退出 0 只代表报告完成，仍须看 `failure` 与 `completed_combined_loop`。完整接地带材料点复核使用相邻帧真实网格 FK，取两帧 `abs(z)<=source_config.position_tolerance_m` 的索引交集，再对同一索引做世界 XY 差；不从切换的最低点坐标相减。

## 未覆盖边界

未新增中点或更密采样，不证明采样之间始终接触或无碰撞。关节姿态改变后，不继承原重参数化轨迹的解析导数、节点停速或物理速度结论；B 的插值/时间映射和承重验证继续。未证明无滑移物理步态、动力稳定性、可训练性或转向恢复，未确认新外观/动作，也未授权采用。先前失败试作不用于断言构型不可行；剩余工作按总项原职责承接。
