# lizard2 三轴候选：固定机身小幅跟踪

> 前段是旧输入四肢逐轴切片；新导出输入的全部关节无重力读数及胸俯仰 280 N·m 有重力试验分节保留。后续按默认驱动/RL 分工，不恢复历史手工抬腿、直行或步态前置。

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

## 新导出输入全部关节小幅驱动复验（2026-10-20）

### 用户范围与工程取值

用户批准：单次整组、全部 30 关节，固定基座/无重力；新输入 neutral M 对角按 f=1 Hz、ζ=1 生成初值，armature=0，幅值 0.02 rad、每 case 6 s/1200 物理步、dt=0.005 s，失败即停、不自动另起目录重跑。沿用原全过程 0.012 rad、平台/终回 0.002 rad、其它轴 0.01 rad 的诊断判据，以及绝对位置 0.1 rad、读回限速一半、接触 1 N、非有限状态停止条件。仅隔离配置，不扫描增益、不测步态、不训练、不正式采用。

### 接线与写前拒错

`palm_spatial_tracking.py` 新 `--all_joints --approved_inertia_sha256` 激活 fresh：先核批准惯量报告，复用上游成对 reset/pose 批准、export/replay/73 工件验证；两姿态完整 M 必须有限、对称、正定且 URDF/USD/raw_actor 已验证。旧检查点 pin 和旧入口保持，fresh 不允许 combined、gain override、夹具、视频或开摄像头。全部 cases 取实测 30 名序，不仅腿 20 轴。

新增逐步读取实际 backend `get_dof_position_targets/get_dof_velocity_targets`，与期望目标/零速度按现有 float32 复读预算比较；保存每 case neutral/2.9 s/5.9 s 的全部 actor/FK 状态。`delta>0` 只作最低检查，独立审计另外用父子相对旋转核有符号实体轴向，不能靠四元数符号差或浮点噪声证明随动。PD request 仍只重建估算，不称实际求解器力矩。

该文件已有其它会话 RF/视频/自由基座未提交改动，本轮保留，不将它们收进本次提交。用基于 HEAD `8786407c03ad8918a040b53ead74e326804c5b21` 的独立 fresh 增量生成候选 bytes；保持原 `__file__` 供相对导入，并显式 `__candidate_source__` 保存实际候选来源。采集 source 与候选逐字同 hash，不拿 mixed-WIP 主文件冒充当次代码。独立提交补丁 `rl_exp/out/palm_spatial_tracking_HEAD_new.diff` 仅增 fresh 实现；当前候选不是 HEAD 原样。

最初增量遗漏 `_run` 的旧 URDF pin 条件，写前真实入口仍拒 fresh；补为 fresh 明确链绑定、legacy 原 pin。`rl_exp/out/palm_spatial_tracking_HEAD_check.log` 保留同真实 `_run` 的破坏红例摘要 `5891a09c857e68485b6305f179327b6d93fc371bde984a24bc5c58b625c669b8` 与终版绿色摘要，红例在 mkdir 前失败、绿色到独占写入/source-copy 边界；未创建仿真目录。fresh 正例/错批准/模式混用/矩阵异常/后端静止或非有限/静止 actor 等持久 selfcheck 通过，截断 30-case 分支反证失败。原曲线判词仍验证理想通过、静止/交换列失败；这些离线口径反证不冒充真实 PhysX 断驱动负例。

预运行独立审核 `a2204c95-c3cd-4bcc-8ce2-5dcf4c960c62` 核 HEAD-only patch、完整真实 `_run` 写前准入、source 身份和旧 WIP 未变；`2768f481-b736-4b30-ad61-a4823be3dd15` 审行为和提交边界，批准有限工况。单次 fullrun 是本轮执行约束，不是跨进程全局锁；本次仅一个启动，不因通过再重复运行。

### 真实结果及独立复算

唯一真实启动退出 0，`completed=true`、`small_tracking_verified`，30/30 case 通过：四腿五角色 20、胸 yaw/pitch 2、颈 yaw/pitch 2、尾三段 yaw/pitch 6。每 case 1200 帧，共 36000 帧；backend position 与 velocity targets 各保存完整 1080000 个有限值，全部比较符合既有预算。固定根无漂移，全部 31 body 禁重力、30 force drive；实际 backend Kp/Kd 与按 neutral M 生成值相符，armature 零。caps 与 URDF 对齐，但仅是加载读回，未证明限制行为。

| 整组读数 | 最大值 | 原判据/边界 |
|---|---:|---|
| 跟踪误差 | `0.005595709579404377 rad` | `0.012 rad` |
| 2.8–3 s 平台误差 | `2.502977848052937e-5 rad` | `0.002 rad` |
| 5.8–6 s 终回误差 | `2.5211380489054136e-5 rad` | `0.002 rad` |
| 非命令关节偏移 | `0.001589417108334601 rad` | `0.01 rad` |
| actor/FK 最大矩阵分量差 | `1.104203694040403e-6` | `1e-5`，分量为 m 或旋转无量纲 |
| 实际全通道速度 | `0.01712434739 rad/s` | 远未触及读回限速 |
| 最大接触力模 | `0 N` | 停止界 `1 N` |
| 最大重建 PD request | `0.7318338292 N·m` | **估算，不是实际力矩** |

独立新上下文 `8e0ee68e-8fad-4ddf-bb57-b6a6bede57f8` 直接读 30 个原始 case、report/manifest/source 和批准资产；逐帧重算所有判词、72000 项 backend 比较、gain/caps、90×31 actor 状态，独立解析 URDF 并以 Rodrigues/tree FK 和父子相对旋转有符号角计算，不调用采集 `csc.fk`。全部 30 轴方向正确，平台 actor signed delta `0.0199860164–0.0200043468 rad`，与 actual q 最大差 `3.67084e-7 rad`；终回 actor 绝对角最大 `1.35166e-5 rad`，独立归一化 quaternion FK 最大 `1.1040631e-6`。未另加 tiny-residual 工程阈值。报告和原 case 判词逐值一致，结束 40 个 scoped 文件及 7 个绑定输入摘要不变。批准本轮固定基无重力小幅驱动切片，无数值或轴向阻塞；该审核未亲自启动进程，退出 0 由本执行者的背景命令结果提供。

### 身份与复读

| 工件（仓根相对路径） | SHA256 |
|---|---|
| `rl_exp/out/lizard2_e_fresh_tracking_20261020/report.json` | `6ae21d6db17a46f2431917c5488ace92b8cf6a57f4c87302ab36c8ca8937bb11` |
| 同目录 `source.py` / 当次 HEAD-only 候选 | `c49c897b0d927df81ebb8ae2128e5efe1b0f91ef04dc137c21bc4bb0e21f441d` |
| 同目录 `tracking_manifest.json` | `3e2ac96e17848c49df9202bea2c6b5373d6e3f956bdef75f20f6189faf80d1a8` |
| `rl_exp/out/lizard2_e_fresh_tracking_20261020.log` | `c280a10d4b07627157c74d6c55809356765b5670da56f82d8166e38e00211d53` |
| `rl_exp/out/palm_spatial_tracking_HEAD_new.diff` | `44936baf325f752504b8bff78776d16599169e6f0db4e88be8c06989cd288fd1` |
| `rl_exp/out/palm_spatial_tracking_HEAD_check.log`（最近一次离线复读） | `95692fe1e87bb93e58b681a4ef42dfeb63ec44c14764919d8f91593018f285d3` |

输入惯量报告 `f1f9951a5057e4f5431316be373b5e359fbd3f5f8d79d3c2978bda140f5d06fd`，replay manifest `d9d8cbc04d7295966c82735b03778fa7eacf990099b3b32d6c0f3e0ad37fa5f3`，新 URDF `e8896feb8b0dbdbeaa35e74a01c2ffcb4ab38d89b52f221831b3f287943edd00`、USD `0c5ffd157b39faf9b65907877badbe069ae5af69585124a1097f94956df3fe76`；来源与实际质量矩阵取当前惯量复验记录。本机工件不承诺入仓。

持久提交入口复读须另获物理预算并使用新目录；`replay` 不是本轮实际采集目录。追加 `--self_check` 时删 `--headless --device cuda:0`，只做持久自检、不起仿真：

```cmd
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp\tools\diagnose\palm_spatial_tracking.py --headless --device cuda:0 --all_joints --approved_inertia_sha256 f1f9951a5057e4f5431316be373b5e359fbd3f5f8d79d3c2978bda140f5d06fd --inertia_report rl_exp\out\lizard2_e_fresh_inertia_20261020\report.json --out rl_exp\out\lizard2_e_fresh_tracking_replay
```

当次真实命令用 `compile+exec` 的上述 HEAD-only bytes、原 `__file__` 与 `__candidate_source__` 后传同参数，实际输出 `rl_exp/out/lizard2_e_fresh_tracking_20261020`；日志首行保留批准源码摘要、完整 argv，不把常规复读命令说成当次启动原文。

### 当前交接与限制

现已具备新输入全部关节的实际 backend 目标、小幅角度跟踪及对应 actor 有符号运动证据；B/C 可接此固定基初值和真实身份做适度组合与已知载荷的保持/跟踪，不须手工抬腿或走路成功。它不证明 mesh 顶点独立运动观测、任意姿态/载荷、自由基座/接触稳定、默认 PD 最终定稿、真实施加力矩/饱和或有效限速；小幅其它轴偏移也不能说动力学已解耦。后续负载/重力/支撑/fixture、误差及停止预算另集中确认，不扫描增益、不加补偿/步态控制器。RL 负责移重、躯尾协调、抬腿和步态；obs 非零语义、gait writer/绘图、终止 hook、其余 E3 与 D 审核仍在办，不关闭 A/B/C/E 或批准训练。

独立回填审核 `bb10b823-b7ce-4fa1-b88b-4229063108b6` 核五文档 diff、实际 report/source/manifest/输入/日志摘要、HEAD 到候选 patch 精确相等、CLI/锚点和未完路由，批准回填，无阻塞；未重跑物理或代替原始数值独立审计。首次完整离线套件 36 项通过、一项失败、零跳过，46.2 s；`RECORD_BINDING_SINGLE_SOURCE_VIOLATED` 指向其它事项的 `test_artifact_inventory.py:57` 与 `test_diagnose_support_output.py:130` 本地文件摘要实现。本轮不修改它们、不放宽闸门。收尾重跑先遇活跃文档总量 180163/180000 bytes，未关闭/取消任何事项、未调预算，只删除 E5 对职责表的重复散文，独立 `faa957e5-f8b3-4519-8735-6872aa81c114` 核未完动作和边界仍保留；最终完整套件返回 0：`ALL_OFFLINE_CHECKS_PASSED (37/37 in 46.9s)`，当前摘要冲突项也通过。本执行者不冒领其它事项实现/测试的修复，也不改写此前失败。限定 HEAD-only 源码增量与五份回填文档暂存后，`git hook run pre-commit` 返回 0；其它在办视频/夹具及共享树改动不纳入。源码提交使用仅该文件增量的独立索引，避免 pathspec commit 把工作树混合 WIP 全量收走。

## 胸俯仰自重280复验

物理试验：2026-10-20；直接复核及回填：2026-10-21。

### 授权、载荷及判据

用户要求真正验证有重力、明确载荷下的保持/跟踪，并明确模型须能以躯干托住和抬动前半身；授权试胸俯仰 280 N·m，随后选择一次 280 测试，而非 240/280 对照。固定根在 z=2 m、全部 31 body 开重力 `[0,0,-9.81] m/s²`，无额外夹具、无地面支撑；其它关节由自己的 PD 保持零目标。胸俯仰下游质量 39.9396 kg，不将其当自由整机站立或承重行走。只改隔离配置，正式资产、URDF/USD、惯量、冻结配方不改。

工程取值事前确认：从零位正常 reset，零目标静置 5 s；随后胸俯仰抵抗重力方向 −0.02 rad，2 s quintic 伸出、1 s 保持、2 s 返回、1 s 恢复，共 11 s/2200 步，dt=0.005 s。其它通道目标全零。以 5 s 自重平衡角 q₀ 为增量基准：沿用全过程误差 ≤0.012 rad、平台/终回末 0.2 s ≤0.002 rad、其它轴运动增量 ≤0.01 rad；同时保留全部轴绝对目标误差 ≤0.1 rad。静置末 0.2 s 漂移 ≤0.002 rad、静差 ≤0.1 rad。绝对角度或目标偏差 >0.35 rad、速度达到读回限速一半、接触 >1 N 或非有限状态即停。无胸部水平前置；一次运行、不自动重试、不扫描增益。

### 静力筛查及隔离初值

已批准新输入的 neutral M 对角为 I；对 URDF 全零及每单轴 ±0.02 rad 共 61 姿态，按真实轴/pivot、子树质量和 COM 计算重力矩最大绝对值 G。一次初值为 `Kp=max(I*(2π)²,G/0.03)`、`Kd=2*sqrt(I*Kp)`、armature=0；0.03 rad 是静差设计尺度，不保证精确定位或动力学解耦。所有关节使用同一规则；只将胸俯仰 `effort_limit/effort_limit_sim` 从 80 改为 280 N·m，其它 cap、速度、关节范围、几何和碰撞过滤保持原值。

胸俯仰中立重力矩 `+234.6846768967044 N·m`，61 姿态最大 `235.0734903376436 N·m`；计算 Kp=`7835.783011254786 N·m/rad`、Kd=`895.5293576650034 N·m·s/rad`。以独立 COM 势能有限差分得到 `dU/dq=-234.68467689284898 N·m`，对 −0.02 rad 的势能增量 `+4.694610260991384 J`，核抬升符号，不仅沿用代码假设。静力范围是有限姿态筛查，不证明整个有静差运动包络；实际运动另由原样本判定。

280 与约 235 的差额不是实际可用力矩实测，不能据此推定任何速度。提高上限只在原上限限制实际驱动时才可能改善响应；同一慢目标曲线也可能得到近似相同速度。**本轮没有运行 240，对“240会慢慢抬、280一定更快”没有比较结论。**

### 已有物理结果与本轮直接复核

2026-10-20 唯一真实启动退出 0，`completed=true`、`chest_self_weight_tracking_verified`，保存全部 2200 步。2026-10-21 用户要求不再创建子 agent，本执行者直接加载原始数据、代码与绑定资产复核，未再起仿真、未重复试验。先前结果审核被用户中断，无独立审核批准可引用；本节是执行者直接复读，不代填无执笔历史审核或整个事项关闭。

| 量 | 原样本直接复算值 | 判据/含义 |
|---|---:|---|
| 胸俯仰 5 s 自重平衡角 | `+0.03003840148448944 rad`（约 `1.72107°`） | 不是目标零位达成 |
| 7.9 s 实际胸俯仰角 | `+0.010016352869570255 rad` | 相对 q₀ 抬升 `−0.020022048614919186 rad` |
| 10.9 s 返回角 | `+0.030038082972168922 rad` | 回到有静差的平衡位置，不是回零 |
| 最大胸俯仰运动增量误差 | `0.0020988853757408464 rad` | ≤0.012 rad |
| 平台/终回运动增量误差 | `2.220135182142216e-5 / 5.979090929031372e-7 rad` | 各≤0.002 rad |
| 其它关节最大运动增量 | `0.009805137757211924 rad` | ≤0.01 rad，接近本轮界限，不放宽判据 |
| 静置末段全体漂移 | `1.7229467630386353e-8 rad` | ≤0.002 rad |
| 静置末段最大绝对静差 | `0.03190210834145546 rad` | ≤0.1 rad |
| 全程最大绝对目标误差 | `0.035109199583530426 rad` | ≤0.1 rad |
| 最大实际速度（胸俯仰/全体） | `0.17192424833774567 / 0.3440144956111908 rad/s` | 含初始静置瞬态；不是280与240比较 |
| 最大接触力模 | `0 N` | 无地面/额外接触支撑证据 |
| 最大重建胸 PD request | `249.73318250797456 N·m` | **估算，不是求解器实际施加力矩** |

直接逐帧核 `(2200,30)` 的 q/v/目标/backend 位置与速度目标全部 finite，时轴精确对应 dt；backend 位置等于命令的 float32 表示，速度目标全零。重算平台/终回/静差/漂移与报告逐值相等，速度/接触/绝对停止界均未触发。PD request 按采集 float32 Kp/Kd 与 q/v 运算重建一致；首次用 float64 重算差约 `7.2648e-6 N·m`，定位为运算精度后按原 dtype 一致，不以此修改判词。

直接对比源 manifest 与新 manifest：只出现已批准重力开关、全体 Kp/Kd、胸俯仰两个 effort 字段及报告 source 路径变化；还原这些后结构完全相等。真实 backend chest cap=280 N·m，其它 effort 与全部 speed cap 均等于 URDF；固定基与 31 body 重力开启均有读回，原 USD/URDF 和全部绑定输入哈希不变。未新增约束、移除自碰撞或改宽关节限位。

对 5/7.9/10.9 s 三快照以独立 Rodrigues/树递推重建 FK，不调用采集 `csc.fk`；最大矩阵分量差 `9.471549091838449e-7`，低于既有 `1e-5` 预算。归一化四元数后，parent-relative 胸轴有符号角为 `0.03003796175442818 / 0.010016370300931082 / 0.030037587404958876 rad`，实际实体抬升差 `−0.0200215914534971 rad`，方向正确且返回；不是以 quaternion 符号或 `delta>0` 噪声判随动。

在内存复制实际 2200 帧，经原 `_chest_verdict()` 分别破坏为静止、反向、绝对静差偏移、静置漂移，四例均拒绝，原文件不改。删除绝对静差约束的实际 AST 分支后，持久 `_chest_self_check()` 报断言失败（破坏源码摘要 `6ece6a48cc72a2b4c065d43b0fdb9735329a561668441ff1f5cfc67e454d6e42`）；恢复原候选后旧、新 fresh、自重自检均通过。该红绿证据是离线判词破坏，不冒称另一次 PhysX 断驱动试验。

### 身份、复读与交付

| 本机工件 | SHA256 |
|---|---|
| `rl_exp/out/lizard2_b_chest280_self_weight_20261020/report.json` | `3d8d90af04238c23e81c9d96340b1641b48eef4a74d3c07f022977f94b375a7a` |
| 同目录 `source.py`；当次 HEAD-only 胸部候选 | `7286bd3ec57ba3696cc6834806fe29a6f3d4f6738954d47861f2911028ee4d1f` |
| 同目录 `tracking_manifest.json` | `03a8d096a29eacd203e58ac430bfd64a7158e87ffad3044080464c209bbd7ebf` |
| `rl_exp/out/lizard2_b_chest280_self_weight_20261020.log` | `255634cf8368c0b30f3e420fc9af4605d9dc668862c3db10a32c674e76a14b85` |
| `rl_exp/out/lizard2_b_chest280_selfcheck_20261020.log` | `22bde698fb220c706c3f2cbc3f03278cfd207e2da8101388738fe993219f3d9d` |

批准输入为新惯量报告 `f1f9951a5057e4f5431316be373b5e359fbd3f5f8d79d3c2978bda140f5d06fd` 与原 replay manifest `d9d8cbc04d7295966c82735b03778fa7eacf990099b3b32d6c0f3e0ad37fa5f3`；USD/URDF 身份仍取上游新惯量记录。完整当次 argv 与源码摘要见日志首行。本机候选是 HEAD `858e82f3473e2fc105ad34f19ec775ea4734fa26` 加独立胸部增量，不包含工作树 RF/视频/自由基座旧 WIP；提交时只纳本轮补丁，不全量收该工作树文件。source 快照与候选 bytes 一致，不以混合文件冒充采集来源。

持久入口复读必须新输出目录及另获物理预算；下例 `replay` 不是本轮已运行目录。离线自检须去掉 `--headless --device cuda:0`、追加 `--self_check`，不创建输出、不起仿真：

```cmd
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp\tools\diagnose\palm_spatial_tracking.py --headless --device cuda:0 --all_joints --chest_self_weight_280 --approved_inertia_sha256 f1f9951a5057e4f5431316be373b5e359fbd3f5f8d79d3c2978bda140f5d06fd --inertia_report rl_exp\out\lizard2_e_fresh_inertia_20261020\report.json --out rl_exp\out\lizard2_b_chest280_self_weight_replay
```

**当前判定**：有限静差下胸俯仰在上述明确自重载荷、280隔离预算和小幅慢曲线中能保持、抬升、返回。其它关节有被动目标保持/静差读数，但本轮没有对其它29关节施加跟踪动作，不能宣布全部关节受载验证完成；`--all_joints` 在该子入口仅要求完整输入绑定，不表示30主动 case。

下一步仍为其它关节的已知载荷保持/跟踪、适度组合、有效速度/力矩边界与正常支撑集成。280没有正式采用，实际求解器力矩/饱和未验证，不承诺任意负载或速度；RL 仍学移重、支撑分配、躯尾协调和步态，不要求先手工抬腿成功。未关闭 B/C/E/D，未把本执行者直接复核称独立关闭审核。

2026-10-21 收尾完整离线套件返回 0：`ALL_OFFLINE_CHECKS_PASSED (37/37 in 37.9s)`。回填路由后一度活跃文档超预算 41 bytes，仅精简同段重复工况文字和长锚点，未取消/关闭/迁移未完动作、未调整预算；`check_work_docs.py` 随后通过。提交候选可编译、摘要等于当次 source，限定补丁精确为 HEAD＋本轮新增，路径 diff 格式通过。记录只把直接复核称自检，不产生新的独立批准。回填后再次完整套件通过：`ALL_OFFLINE_CHECKS_PASSED (37/37 in 41.9s)`；本轮文档限定暂存后的 `git hook run pre-commit` 返回 0。采用独立索引只提交当次胸部增量，保留其它会话暂存及工作树视频/夹具改动，不跳过钩子。
