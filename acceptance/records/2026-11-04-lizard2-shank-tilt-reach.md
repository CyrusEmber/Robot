# lizard2 v7 小腿倾角离线可达性：实施中（2026-11-04）

## 适用范围

`work/active/lizard2-thigh-drive-shank-landing.md` 的轴映射、几何可达性核查与 v7 策略诊断。对象为 v7 锁定的 `rl_exp/lizard2_round_feet/` 资产，策略复读对象及条件见下文。已核正式 USD/URDF 和已采实时姿态，并逐片抽帧查看既有九宫格；用户现场身份仍未由用户明确核定，未做执行器分项探测或独立审核，不是完整步态验收或根因结论。

## 验收条件

- 读出各腿 swing / abduct / twist / elbow(knee) 对小腿倾角的作用方向与量级。
- 判定“swing 能否把已倾斜小腿摆竖直”。
- 脚本自带破坏检查：swing 轴改为 Y 后其灵敏度必须明显变化，否则脚本不算测到轴配合。

## 结果

条件：根体直立（单位四元数），胸/颈/尾关节为零，其余腿关节取零；倾角为小腿有向轴（elbow/knee 连杆原点到足端连杆原点）相对世界 -Z；每腿四关节在 URDF 限位内各取 11 点，共 14641 组合。

- 零位灵敏度（rad/rad，[前后向, 横向]）：swing = [0, 0]；abduct 与 elbow/knee 数值相同（两轴平行），lf = [0.342, -0.94]，rl = [-0.342, -0.94]；twist lf = [-0.926, -0.337]，rl = [-0.926, 0.337]。前后向分量主要由 twist 提供，横向分量由 abduct/elbow(knee) 提供。左右腿横向符号相反。
- swing 单独扫描（±0.6）：由 abduct=0.4 的横向倾斜出发，总倾角 0.4 → 0.4；由 twist=0.3 出发，0.296 → 0.296。四条腿一致。
- 可达总倾角范围（含任意组合）：前腿 0–1.665 rad，后腿 0–1.851 rad；各腿竖直（0）可达，但须靠 abduct/twist/elbow(knee) 的组合。
- 原因为结构性：swing 是腿链第一个关节且轴为世界 Z，绕竖直轴转动不改变任何下游连杆相对竖直的倾角。该性质不要求大腿水平。前腿父体为 chest_pitch，其 yaw/pitch 非零及根体倾斜会破坏这一精确性，本次未量。

读数与用户假设一致：单独 swing 只改倾斜朝向，不改倾角。

### v7 策略 rollout 读数（用户反馈“大腿 swing 不怎么动”）

对象：`E:\IsaacLab\logs\rsl_rl\lizard2_v7\2026-11-03_17-07-29\model_5999.pt`（该 run 的 manifest 任务为 `Lizard2-Flat-v7`，仅有的一个 v7 run；仅按目录检索得到，未与用户确认它就是出问题的那一个）。`Lizard2-Flat-Play-v7`，nominal，4 环境，命令 0.5 m/s，seed 123，500 步（10 s），两次运行关节位置标准差逐项一致。站立相用足端球心高度 < 0.10 m 近似，不是接触测量。

- 前腿 swing（lf/rf）：动作目标均值 0.60/0.60，目标最小值 0.31/0.25，最大 0.60（clip 上限），目标 5–95% 跨度近 0；位置均值 0.50/0.52。即目标长期贴着上限，不是“幅度小”，而是被推到位置边界附近。
- 后腿 swing：rl 目标均值 0.56，范围 -0.44–0.60，位置 5–95% 跨度 0.38；rr 目标均值 -0.05，范围 -0.60–0.25，位置跨度 0.23。后腿 swing 在摆，但 rl 同样偏置在正上限一侧。
- 四条腿 twist 位置 5–95% 跨度 0.23–0.44 rad，目标跨度 0.46–0.68；elbow/knee 位置跨度 0.12–0.58 rad，跟踪误差均值 0.17–0.25，高于 swing 的 0.05–0.10。
- 站立相小腿倾角均值（度）：lf 9.8、rf 11.6、rl 43.0、rr 49.1；p10–p90 前腿 3–21，后腿 38–52。后腿站立相小腿离竖直很远，与用户“后腿折起来、小腿不垂直”的反馈方向一致。

解读限制：swing 贴 clip 上限；其不改总倾角仅是根直立/胸零位下的离线性质，实际姿态补证见下。后腿倾角须结合 swing/abduct/twist/knee 的实际轴组合判断（rr abduct 目标均值 0.58，贴近 0.6 上限）。这是单个 checkpoint、单一速度、单一 seed 的读数，不能据此归因到奖励或 scale，也不能断言 swing 偏置的原因；未做 scale/刚度/限矩分项探测。

### 放宽 swing 动作 clip 的探测（use03 基线、use04 放宽）

做法：探针运行期把四个 `*_swing_joint` 的动作 clip 临时改为 ±1.2（`--swing-clip 1.2`，改的是动作项私有 `_clip`，不改配置、资产或版本），其余同上。策略按 ±0.6 训练，放宽后属训练分布外的运行，只回答“目标被钳住时位置会不会走更远”，不代表在新 clip 下重训的结果。

- 原始动作：前腿 swing 原始输出均值 4.9/5.5（p5–p95 约 3.6–6.7），scale 0.2 下对应目标 ≈ 1.0 rad，远超 ±0.6。即策略在 clip 之外仍把前腿 swing 往正向推，目标被 clip 截断，超出同侧边界的原始动作映射到相同关节目标；这不等于全部学习信号消失（见下文校正）。rl 均值 4.6，rr 均值 -0.26（rr 并不饱和）。
- 目标：前腿 swing 目标均值 0.6→0.94/1.05，最大 1.2（新上限）；rl 0.56→0.87。
- 关节位置：前腿 swing 位置均值 0.50/0.52→0.58/0.57，位置跨度 0.15/0.23→0.11/0.20，基本不变，均值贴近 URDF 限位 ±0.6（未直接读限位接触，按位置贴 0.6 推断为被限位挡住；Kp×(目标-限位)≈24 N·m 远低于力矩上限 180，不像力矩不足）。
- 结论：本次单放宽动作 clip 没有明显扩大实际运动范围，位置贴近原关节限位；这只支持原物理范围可能约束更大目标的响应，未直接测得限位接触，也不能解释策略为何学成固定偏置或证明扩大物理限位能改善步态。正式资产未改动。
- rr swing 不饱和且摆幅小（位置跨度 0.23，目标均值 -0.05），与用户“后腿 swing 其实也很少”一致；其原因不在 clip 或限位。

### 训练阶段复读与原始动作口径

同一 run 的 model_500 / model_1500 / model_3000 按同一探针复读（nominal、0.5 m/s、seed 123、4 环境、500 步），未放宽 clip。表中为前腿 swing 的原始动作均值与处理后的目标均值（rad）；model_5999 使用基线复读，不使用放宽 clip 的反馈轨迹。

| checkpoint | lf raw 均值 | rf raw 均值 | lf 目标均值 | rf 目标均值 |
|---|---:|---:|---:|---:|
| model_500 | 1.06 | 1.86 | 0.19 | 0.35 |
| model_1500 | 2.76 | 1.64 | 0.51 | 0.33 |
| model_3000 | 4.38 | 4.48 | 0.58 | 0.59 |
| model_5999 | 4.93 | 5.47 | 0.60 | 0.60 |

这些样本显示前腿逐渐形成较大的正向偏置，但 rf 在 500→1500 回落，不是逐阶段严格单调；不同 checkpoint 产生不同状态轨迹，不能从这些均值推断某奖励项持续施加正向压力。

原始动作口径：探针断言 `torch.equal(leg_term.raw_actions, act[:, :len(leg_names)])`，保存实际动作顺序、scale、offset、clip 以及 `clip_actions`；本次 offset 为零，swing scale 为 0.2，wrapper `clip_actions=None`。因此 raw=0 对应目标零位，但训练后策略输出不必为零；前腿 raw≈5 不是默认姿态偏移或把关节位置误读成 raw。

### 限位与学习机制解释校正

- 用户指出卡限位是表现，不能据此解释 swing 为什么缺少周期运动；认同此区分。放宽后可能只在新的边界形成固定偏置，当前未验证改善。
- 用户提出在可视化中将 swing 范围扩大至 ±0.8，用于查看足端前后可达范围和轴间配合。此为几何观察候选，不记录为已执行；可视化无重力、接触和 PD，显示范围修改不自动更新训练使用的 USD、URDF、action clip 或冻结版本，也不构成重训批准。
- 撤回此前“clamp 饱和使 PPO 梯度归零，因此学不回来”的解释。PPO 通过动作概率的策略梯度优化，不通过仿真和动作 clamp 反传；clamp 的局部导数为零不是 PPO 梯度为零的证明。相同饱和目标可能减少关节实际探索差异，但 raw 动作仍可能影响 last_action、动作变化惩罚与后续状态；实际启用项及口径尚待核对，不能笼统称饱和区没有学习信号。
- 未核定的优先排查：swing/twist 驱动与阻尼、abduct/elbow(knee) 的代偿，以及奖励/正则是否允许固定大腿、主要靠小腿推进。仅列候选，不写作根因或改参批准。

### 第 1 步补证：正式 USD、实时姿态与录像（2026-11-04）

**身份核对**：该 run 的 `run_manifest.json` 声明 TRAIN `Lizard2-Flat-v7`、recipe `lizard2-flat-v7@1`，seed 42、4096 环境、6000 迭代、无 resume；当时资产 `missing_or_changed=[]`。本轮逐一哈希检查 v7 `asset_lock.json` 的全部 31 个文件，无差异。checkpoint SHA-256 为 `ab6b30ad775b036b829bf28e13c284cc03735921cd4f81b8cae60d66d0f46aef`，既有九宫格九段均绑定该摘要。manifest 明确记录脏树授权，不因此宣称当前树可逐字重建训练；用户所看现场身份仍未获得显式确认。

**正式资产核对**：复用 `lizard2_round_feet_usd.audit()` 只读调用，不转换或修资产。31 刚体、26 revolute + 4 fixed、连接、轴、局部枢轴/旋转及限位检查全通过，完整 audit 无失败。左侧 swing 的子体轴为 +Z，右侧为 -Z，左右不能按同号解释；右轴符号用于镜像，不代表转换错误。

**实际姿态对照**：沿原基线复读 0.5 m/s、seed 123、4 环境、500 步，每 0.5 s 保存 env 0 的完整关节与 link 位姿、实际 USD 父/子两侧关节轴和枢轴，共 20 样本；4 环境 reset_count=0。使用本 fork 的 xyzw 四元数、link frame（非 COM frame），把根体位姿与全部胸颈尾关节加入 URDF FK：全样本最大位置残差 `1.35e-6 m`、轴向量残差 `1.03e-6`；USD 父子轴差 `2.69e-7`、枢轴差 `9.70e-7 m`。负例仅改 lf swing 轴为 Y，最大 FK 轴残差变为 `1.414`，内置断言通过，证明读点能辨别改轴；不是动力学破坏测试。

实际根体/胸部会倾斜，故“swing 完全不改总倾角”只在先前根直立/胸零位条件成立，不能直接推广到 rollout。固定每个实测样本的根位姿及其他关节，仅在原 ±0.6 扫 61 个 swing 值：从 1 s 后的足端高度代理样本汇总如下（离散几何样本，不是正式落地统计）。

| 腿 | 代理样本数 | 原总倾角均值（度） | swing 单独最优后均值（度） | 采样中最小剩余倾角（度） | 前后/横向分量均值（度） |
|---|---:|---:|---:|---:|---|
| lf | 16 | 9.90 | 9.20 | 2.50 | -2.77 / 6.17 |
| rf | 18 | 11.24 | 7.13 | 1.36 | 8.97 / -0.79 |
| rl | 14 | 44.86 | 34.79 | 28.96 | 2.86 / -44.06 |
| rr | 18 | 49.19 | 46.86 | 42.23 | 0.61 / 49.01 |

后腿该窗口的倾斜以世界横向分量为主，单改 swing 仍剩明显倾斜。不是“前后倾角都该靠 twist”的零位推算能概括的实际姿态。2.52 s 的逐轴归零切片：rl 原 41.92°，只把 knee 归零为 17.34°（swing 归零为 39.54°）；rr 原 47.98°，只把 abduct 归零为 22.91°（knee 归零为 30.97°，swing 归零为 48.21°）。提示左右后腿用不同轴组合形成横向倾斜，优先核 abduct/knee 配合；归零会同时改变足端落点，未检支撑/碰撞，不能据此批准清零目标或降低驱动。

**九段逐片观察**：复用已存在的视频，不重录、不补造录制 execution；执行者 CodeMaker agent，验看时间 2026-11-04 本轮，方法为 `clip_sheet.grid_sheet` 抽帧，各单段 0–9 s 每 1 s 一帧，首/中/尾已覆盖；保存图和 `sampling.json` 于视频目录的 `shank_review01/`。不是连续播放，1 Hz 可混叠步态，不能判周期、支撑力、瞬态滑移或量化角度。视频为 recorder 的 nominal 工况、无 recovery kick；完整当时 DR/reset 快照与执行起止记录缺失，不伪称其已齐备。

| 目标速度（m/s） | 视角 | 抽帧观察（0–9 s，重点 1/5/9 s） | 帧图（相对视频目录） |
|---|---|---|---|
| 0.5 | side | 躯干保持低姿态、头颈抬起；可见小腿姿态变化，近侧大腿前后行程视觉上较小，遮挡不能分清远侧腿 | `shank_review01/0.5_side.png` |
| 0.5 | front | 前腿外展/弯曲及头胸姿态有左右差异；后腿被遮挡，不能判其落地角 | `shank_review01/0.5_front.png` |
| 0.5 | rear_oblique | 两后腿保持折叠，前后肢形态不同，后足靠近机身；抽帧未见侧翻 | `shank_review01/0.5_rear_oblique.png` |
| 1.5 | side | 近侧小腿与胸颈姿态变化，大腿姿态仍相近；尾部较低，阴影不构成触地证据 | `shank_review01/1.5_side.png` |
| 1.5 | front | 前腿/头部左右姿态不对称，后腿遮挡；画面跟随主体 | `shank_review01/1.5_front.png` |
| 1.5 | rear_oblique | 后腿持续弯折且侧向收拢，可见肢端姿态变化；不能由该投影量化横向倾角 | `shank_review01/1.5_rear_oblique.png` |
| 3.0 | side | 前小腿/胸部变化更明显，躯干仍低、尾随动；不能据 1 Hz 断言摆动频率增加 | `shank_review01/3.0_side.png` |
| 3.0 | front | 前腿交替姿态可见，头部遮挡关节与后腿，未见主体出画 | `shank_review01/3.0_front.png` |
| 3.0 | rear_oblique | 后肢弯折仍存在，前肢姿态变化；抽帧未见倒地，但不作跌倒率判定 | `shank_review01/3.0_rear_oblique.png` |

九段原片、索引、带速度/视角标签九宫格已存在且九图逐一查看。本次只完成专项的逐片抽帧观察；视频缺完整录制条件/执行记录，核心评估与足端承载口径也未在本项补齐，整体训后评估按 `HARNESS.md` 仍不能判完成。下一未完步骤为原限位执行器动态探测，并补正式落地事件与有效推进口径。

## 证据引用

- 脚本：`rl_exp/tools/diagnose/lizard2_shank_tilt_reach.py`（内置破坏检查）。
- 输出：`rl_exp/out/lizard2_shank_tilt/reach01/result.json`。
- 复读：`E:\IsaacLab\env_isaaclab\Scripts\python.exe rl_exp\tools\diagnose\lizard2_shank_tilt_reach.py`。
- rollout 脚本：`rl_exp/tools/diagnose/lizard2_shank_use_probe.py`，输出 `rl_exp/out/lizard2_shank_tilt/use01/result.json`（无均值字段）与 `use02/result.json`（含目标均值与极值）。复读：`E:\IsaacLab\env_isaaclab\Scripts\python.exe rl_exp\tools\diagnose\lizard2_shank_use_probe.py --checkpoint <model_5999.pt> --out <新路径> --viz none`。
- 配置参照（未作为结论使用）：`rl_exp/versions/lizard2/main/v7/main_params.yaml` 按 Kp × scale 推算（前腿）：swing 约 7.9、twist 约 11、abduct 约 137、elbow 约 88。前后向倾角主要靠 twist 而 twist 处低位，仅为待验证线索，须经探测核定。
- clip 对照输出：`rl_exp/out/lizard2_shank_tilt/use03/result.json` 与 `rl_exp/out/lizard2_shank_tilt/use04_swingclip1p2/result.json`；放宽复读使用同一 rollout 命令并加 `--swing-clip 1.2`，必须写入新输出路径。
- 原始动作基线：`rl_exp/out/lizard2_shank_tilt/use05/result.json`；同一 rollout 脚本内含动作切片与 action term 输入一致的断言。
- 训练阶段复读输出：`rl_exp/out/lizard2_shank_tilt/drift_500/result.json`、`rl_exp/out/lizard2_shank_tilt/drift_1500/result.json`、`rl_exp/out/lizard2_shank_tilt/drift_3000/result.json`；复读使用同一 rollout 命令，分别替换为该 run 的对应 checkpoint 及新输出路径。
- 可视化实现：`rl_exp/tools/diagnose/lizard2_spatial_pose_slider.py`；打开本次机体需传 `--urdf rl_exp/lizard2_round_feet/lizard2_round_feet.urdf`，默认路径仍为历史 palm_spatial，不能把默认机体误作 v7。

- 验证：`rl_exp/out/lizard2_shank_tilt/step1_offline_checks.log`，`ALL_OFFLINE_CHECKS_PASSED (37/37 in 51.5s)`；实时复读正常退出，FK 改轴负例通过。回填后 `check_work_docs.py` 再跑 `WORK_DOCS_OK (105 item file(s))`；格式/仓库闸门不证明步态修复或独立审核。
- 原离线扫描复读需指定全新 `--out`（默认 `reach01/result.json` 已存在，现脚本拒绝覆盖）；实时补证复读：`<配置解释器> -B rl_exp/tools/diagnose/lizard2_shank_use_probe.py --checkpoint <本 run/model_5999.pt> --out <新目录/result.json> --pose_samples --viz none`，再用 `<配置解释器> -B rl_exp/tools/diagnose/lizard2_shank_tilt_reach.py --pose_report <上述 result.json> --out <新目录/result.json>`；此入口保存逐轴归零切片并执行改轴负例。
- 本轮输出：`rl_exp/out/lizard2_shank_tilt/usd_axes01/result.json`（正式 USD/URDF audit 与全部锁哈希）、`rl_exp/out/lizard2_shank_tilt/pose06/result.json`（实时姿态）、`rl_exp/out/lizard2_shank_tilt/pose06.log`（仿真日志）、`rl_exp/out/lizard2_shank_tilt/pose_fk02/result.json`（FK/单轴扫描/逐轴归零/改轴负例）；`pose_fk01` 为追加归零字段前的保留中间证据，不覆盖。
- USD audit 复用入口：`rl_exp/tools/diagnose/lizard2_round_feet_usd.py:audit(stage, tree)`；配置解释器下 `Usd.Stage.Open('rl_exp/lizard2_round_feet/lizard2_round_feet.usda')` 与 `ET.parse('rl_exp/lizard2_round_feet/lizard2_round_feet.urdf').getroot()` 传入，完整输出保存于上述 `usd_axes01`；不用只支持导出目录的 CLI，不传 `--repair`。
- 视频目录：`ablation_harness/videos/lizard2_v7_model5999_20261104_101635/`，`matrix.json`、九个单段、`plane_overview.mp4`、既有 `recording.log` 保留；抽帧入口 `rl_exp/tools/diagnose/clip_sheet.py --video <单段> --start 0 --duration 10 --fps 1 --cols 5 --rows 2 --scale 480 --grid 240 --out <新帧图>`。

## 未覆盖边界

- USD/URDF 与实际姿态仅覆盖上述资产与 0.5 m/s、seed 123 的 20 个 env 0 读点，未作连续域、复杂地形或极端姿态核查。
- 几何切片包含足端位置，但无支撑稳定、关节自碰撞与无滑移约束；单轴归零改变落点。可视化范围扩大尚未验证，也未修改正式资产。
- 足端高度仅作支撑代理，未正式测首次落地、限位接触、跌倒率或有效推进；不能将后腿横向倾斜或归零几何收益直接归因到驱动/奖励。
- 已绑定复读 run/checkpoint/资产与既有录像，用户所看现场身份未获显式确认；视频只抽帧，缺完整当时条件与执行记录，不能判整体训后流程完成。
- 执行器分项探测、奖励因果对照、正式落地事件口径及独立审核未完成。
