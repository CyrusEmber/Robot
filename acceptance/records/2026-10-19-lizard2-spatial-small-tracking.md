# lizard2 三轴候选：固定机身小幅跟踪

## 适用范围

承接 `2026-10-19-lizard2-spatial-inertia-repair.md` 的隔离惯量修正目标和限位 PD 专项步骤 6，运行四腿五角色的小幅逐轴跟踪。候选 USD/URDF、具名连接过滤、固定基座、根高度和无重力条件沿用已绑定输入；不改正式资产、配方或上游导出器。

每次从正常 reset 的零位开始，调用注册任务的真实 action manager：按实测动作列写目标，经 `process_action`、`apply_action`、scene write、物理步和 scene update 读取实际关节状态。未通过 env.step 执行奖励、终止或策略；逐轴结论不外推整段 RL 消费链。当前输入有意将机体固定在离地高度，不能当承重测试。

## 验收条件

执行前在 `palm_spatial_tracking.py:SETTINGS` 固定本切片条件：f=1 Hz、ζ=1，使用已核中立姿态质量矩阵对角计算全部关节 Kp/Kd，armature=0；角度幅值 0.02 rad、quintic 伸出 2 s、停留 1 s、quintic 返回 2 s、停留 1 s。符号按实际 URDF 限位选择，目标保持在限位内；物理及目标更新周期均为 0.005 s，位置驱动的速度目标为零，不加入轨迹速度前馈。每个关节一条 6 s 曲线，不扫描频率或阻尼；最多两次整组物理运行。

本切片诊断判据在比较前固定：全过程目标轴误差不超过 0.012 rad；伸出停留和最终停留的末 0.2 s 误差分别不超过 0.002 rad；其它轴最大绝对偏移不超过 0.01 rad。任意实际角度绝对值达到 0.1 rad、速度达到对应读回限速的一半、接触力超过 1 N 或非有限状态时停止。它们只用于本次小幅诊断，不是 S5/D 的最终性能批准。

从 backend 另读 stiffness、damping 与预期比较，读回角度/速度/力矩上限；运行时 USD 的旋转 drive type 必须为 force，动作列必须完整且与实际 joint ID 对应。质量矩阵对角仅给固定基座下的标量 PD 初值，不预设耦合已消失。记录每个物理步的目标、实际角度、速度、接触力和重建 PD 请求；后者不是实际力矩传感器，不能据其宣布实际饱和已验证。

## 结果

第二次整组运行正常完成，退出 0、`completed=true`、`status=small_tracking_verified`；四腿各五角色共 20 个逐轴工况通过。每个工况保存 1200 个物理步，共 24000 个读数，独立重读逐步数据与报告的最大误差一致。整个组别使用同一规则和同一套中立惯量初值，未因读数修改频率、阻尼或判据。

| 同组最大值 | 读数 | 本切片判据 |
|---|---:|---:|
| 运动中目标轴误差 | 0.005504568182265759 rad | 0.012 rad |
| 伸出停留末段误差 | 1.994378864765209e-5 rad | 0.002 rad |
| 返回停留末段误差 | 1.9915240045520477e-5 rad | 0.002 rad |
| 其它关节偏移 | 0.001589417108334601 rad | 0.01 rad |
| sensor 最大接触力模 | 0 N | 停止界 1 N |

运行时 backend 的全部 Kp/Kd 与按惯量计算的值相符，armature 读回为零；30 个旋转驱动的运行时 USD type 为 force。全部动作列/实际 joint ID 覆盖匹配，四腿的 twist、肘膝、腕踝均有独立实际角度跟踪证据。其它关节的小幅偏移表明这套对角初值没有实现动力学解耦；本轮只验证具名小幅工况，不能据此跳过后续组合激励或实际实体随动核对。

实测最大关节速度 0.017122333869338036 rad/s。由步后 q、qd、目标和 Kp/Kd 重建的最大 PD 请求 0.03871180436483068 N·m，最大请求/力矩上限比为 0.0004838975545603835。这个值不是 implicit 求解器的实测驱动力，也未达到限速边界；不称力矩饱和或有效限速已验证。原惯量修正 manifest 哈希保持不变，增益写入新的隔离 `tracking_manifest.json`，步长/种子/设备覆盖另由报告 `runtime_overrides` 记录。

### 入口问题及实际修正对照

首次准备在 schema 校验时拒绝 `sim.dt`，尚未造环境；将步长/种子留在诊断运行覆盖中，没有放宽 manifest 允许字段。第一次数值运行在完成两个工况后，进度记录重复写入已有文件，触发 `FileExistsError`，退出 1；保存 `failure.json`，没有成功报告。原因是共用 `write_json` 有意只允许新建文件。修正为按工况编号保存 `progress_XX.json` 后，第二次整组完成，所有分段记录和最终成功报告均可读；未覆盖原失败产物。

正常曲线/判词自检通过；同一判词对理想跟踪为正例，对静止响应和交换动作列的合成响应为负例。后两者是口径自检，不冒充真实 PhysX 错列或断驱动实验。没有新增机器闸门，没有重做几何探索或正式参数扫描。

### 下一交接

B/E 复用本次 `tracking_manifest.json` 的候选身份及增益，接近端组合激励和实体随动核对，然后按专项步骤 6 准备自由基座静站、单腿抬落及低速轨迹跟踪。改变重力、基座约束、根高度、目标或载荷时单独声明并验证；本轮跟踪通过不保证该套小幅初值能承重。新轨迹插值/时间映射及有效限速对照继续在办，不回到 A 的已交几何样本重复起步。

## 证据引用

- 上游：`acceptance/records/2026-10-19-lizard2-spatial-inertia-repair.md`。
- 入口：提交 `750349b` 的 `rl_exp/tools/diagnose/palm_spatial_tracking.py`；该代码提交的仓库预提交闸门通过。
- 本机整组产物：`rl_exp/out/lizard2_b_tracking_20261019_run02/`；输出必须新建，原产物不覆盖。本机引用不承诺入仓。
- 入口/当次 `source.py` SHA256：`afe64e5718093ba09ac6a21540ef81fa654efd6d001d10893438841a1bb972d5`。
- `report.json` SHA256：`1498de374a7e8863bb53d271ab3a681b5c8ea5fba96676abec0ebec3948074ae`；`tracking_manifest.json` SHA256：`7a47b91eb97c0e8cd2ee6fb1dc3fd3589eee6bccf581bf2b21bc025daf5d0804`。
- 同目录 `<joint_name>.json` 保存逐步原始读数；`sample_analysis.json` 绑定全部原始文件哈希并汇总读数，SHA256 `65c6dd3cf9ce130c38bb0738bbfea148e4f49dc2d9cf4c6904a784c65ed9c824`。
- 启动准备失败：`rl_exp/out/lizard2_b_tracking_20261019/failure.json`；记录写入故障的实际失败：`rl_exp/out/lizard2_b_tracking_20261019_run01/failure.json`，该目录两个已完成工况的原始文件仍保留。

从仓根复读：

```cmd
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/palm_spatial_tracking.py --self_check
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/palm_spatial_tracking.py --inertia_report rl_exp/out/lizard2_b_inertia_repaired_20261019/report.json --out rl_exp/out/lizard2_tracking_reproduce --viz none --device cuda:0
```

## 未覆盖边界

不验证接触承重、自由基座静站、单腿抬落、步态跟踪、速度触边或有/无限速对照，不能据此采用机体或开始训练。尚未加入近端组合激励，也未用独立网格运动测量复核本轮每个轴的实体随动；已有 FK/网格证据只在其原输入和姿态范围复用。上游惯量主轴转换错误的来源修复、正式导出接线、转向/恢复、躯尾协同及最终集成审核仍在办。
