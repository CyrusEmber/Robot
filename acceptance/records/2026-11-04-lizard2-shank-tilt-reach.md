# lizard2 v7 小腿倾角离线可达性：实施中（2026-11-04）

## 适用范围

`work/active/lizard2-thigh-drive-shank-landing.md` 的轴映射、几何可达性核查与 v7 策略诊断。对象为 v7 锁定的 `rl_exp/lizard2_round_feet/` 资产，策略复读对象及条件见下文。已核正式 USD/URDF、实时姿态、五组隔离执行器响应、冻结策略增益干预及真实策略接触采样，并逐片抽帧查看既有九宫格；用户现场身份仍未由用户明确核定，未做新配方重训对照或独立审核，不是完整步态验收或根因结论。

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

### 第 2 步读数与第 3 步接触诊断：原限位执行器动态探测

本轮只做隔离标定，不加载策略、不更新正式配方/资产、不训练。原始 action 正弦幅度 0.5，经过原动作项 scale/offset/clip，控制 50 Hz、物理 200 Hz；频率 0.5 / 1 Hz、每关节 4 周期，拟合舍弃首周期。目标幅度随原 scale 为 swing/abduct 0.10 rad、twist 0.0873 rad、elbow/knee 0.20 rad，不把不同轴的原始 action 响应误作等目标幅度对照。

同一仿真内五环境各一组：原配置；swing/twist Kp×2、Kd×sqrt(2)；swing/twist Kd×0.5；elbow/knee Kp×0.5、Kd×sqrt(0.5)；swing/twist scale×2。其余轴、限位和力矩上限保持原值。本次未做限矩变体；原始小信号是否触及估计饱和先读结果，不能据同限矩组判权限变体已验证。悬空固定根 z=2 m，着地为自由根原高度，两者均保留重力，关闭随机事件；固定根不会消除腿部自重力矩。幅相比用于各工况内部比较，跨悬空/着地差异只解释负载/耦合变化，不直接归因控制器。

**失败现场**：首次悬空 `drive_suspended01.log` 在物理初始化拒绝，原 fork 的 `fix_root_link=True` 产生 Geometry 与 base_link 两个 ArticulationRootAPI：`Expected exactly one ArticulationRootAPI prim ... found 2`。沿既有 `palm_spatial_runtime.py` 固定根诊断适配，只在生成的仿真 prim 去掉 base_link 残余 articulation schema，保留刚体 schema并断言单根，不保存/转换正式 USD。此为标定夹具修正，不是策略根因修复。

`drive_suspended02` / `drive_ground01` 为初版测量；`drive_suspended03` / `drive_ground02` 增加每次复位的初始 q 与求解器增益核对、逐工况根位姿/腹部净接触力、拟合残差及目标发出与采样之间一控制步的相位时间对齐。补证版两次正常退出，各 160 行，保存逐轴波形和元数据；读数及局限见下，不因运行完成宣布驱动根因或修复成立。

**首批悬空完成读数（drive_suspended02，待补证版复核）**：完成 16 轴 × 2 频率 × 5 组，共 160 行；零动作根高度均保持 2 m、腹部净接触力均为 0。1 Hz 前/后 swing 原配置幅比为 0.482 / 0.490，肘膝约 0.929；提高 swing/twist 刚度组 swing 幅比为 0.656 / 0.658，降低阻尼组为 0.938 / 0.968。1 Hz scale×2 只把 swing 目标幅度由 0.10 rad 变为 0.20 rad、实际幅度约翻倍，归一化幅比仍为 0.482 / 0.490，未改善动态跟踪效率。降低肘膝刚度组未改变该悬空 swing 幅比，肘膝自身幅比降至约 0.872。

0.5 Hz 前/后 swing 基线幅比 0.799 / 0.792，降阻尼后 1.113 / 1.090，提示已有幅值放大；1 Hz 降阻尼虽提高幅度，时标对齐后的 swing 滞后仍约四分之一周期，不能据幅比接近 1 判跟踪优秀。前 swing 基线 1 Hz 正弦拟合残差 RMS 约 `1.03e-4 rad`，首批记录没有该字段，本次由保留 NPZ 复拟合。全部首批估计饱和比例为 0，仅支持此悬空小信号窗口未见估计限矩，不能外推接地负载或实际 motor 饱和。

这批读数支持“swing 的频率响应弱于肘膝、刚度/阻尼会改变响应”的候选，不证明其导致策略固定偏置或后腿折叠；不能直接选降阻尼改参。首批 phase 字段按目标发出索引拟合，补证版增加一控制步时间对齐，正式相位引用以补证版为准；着地与复位/增益验证结果仍待完成核查。

**首批着地完成读数（drive_ground01，待补证版姿态/接触复核）**：完成 160 行，但零动作夹具已出现明显支撑差异，不能将五组直接当成同姿态线性传递函数。原初始根高约 0.604 m，基线 2 s 零动作期间最低约 0.453 m、胸腹净接触峰值约 583 N；降阻尼组 0.454 m/610 N，降低肘膝刚度组 0.449 m/536 N，scale×2 组 0.453 m/604 N。swing/twist 提高刚度组最低约 0.504 m、该窗口胸腹峰值 0 N。峰值不是持续承载比例；夹具是零目标、无策略/自动终止，不据此认定训练策略本身必然触腹。

基线 1 Hz 前 swing 幅比接近 0，前 twist 实际角停在约 ±0.524 rad；保存波形显示前 swing 首周期后的全跨度仅约 `5.45e-5 rad`、前 twist 约 `1.91e-6 rad`。这类几乎零幅度的 phase 字段无实际意义，禁止当正常相位读数引用。基线后 swing 幅比约 0.248，降阻尼约 0.386，提高刚度约 0.300；提高刚度还显著改变整体支撑/姿态，不能把全部改善归为单轴响应。降低肘膝刚度组后膝幅比约 0.283–0.288，低于基线 0.630–0.634；其零动作支撑也未满足不触腹要求，当前不支持直接降低小腿刚度。

结论范围：首批着地揭示零目标下的负载/姿态耦合问题，比“限位太小”更值得核查。仍需补证版逐工况根姿态、接触和拟合残差，区分腹部/关节限位约束与单轴驱动能力；没有证明提高大腿刚度能修复已训练策略或满足落地分工，也不能把降阻尼的悬空幅比直接推广到承重工况。

**补证版核查（drive_suspended03 / drive_ground02）**：悬空幅比复现首批，全部 160 行估计饱和为 0；前/后 swing 基线 1 Hz 时标对齐滞后 94.1° / 92.1°，提高刚度 74.7° / 73.2°，降低阻尼 95.4° / 91.4°。说明降阻尼的幅值恢复并未解决该频率的 swing 相位；twist 的相位改善较大，不能把二者统称为同一响应问题。

着地补证推翻“提高大腿刚度即可保持不触腹”的推广：提高刚度组前 swing 激励期间根平均高度约 0.471 m、胸腹峰值 347 N、1–4 s 净接触指示占比 100%，该片段根漂移约 0.118 m；零动作头 2 s 未测到触腹不代表后续安全。其他四组同片段接触指示占比也为 100%。提高刚度组后膝激励峰值可达约 1098 N、拟合残差 RMS 0.020 rad；接触/机体运动明显，单轴幅比不是固定姿态线性响应。基线后 swing 幅比 0.248、降阻尼 0.386、提高刚度 0.300 的比较只能作隔离零目标夹具结果。当前五组均未满足整个动态测量窗口的不触腹要求，不批准任何一组用于正式改参。

**第 3 步推进**：沿真实 model_5999 策略补控制帧足端净垂直力与小腿有向轴（相对世界 -Z）的总倾角、X/Y 分量、机身速度/位移及腹部净力。足端读点是四个圆足 body，净垂直力 >1 N 仅作接触指示；相邻有效控制帧由未接触到接触为候选边沿，不叫真实 touchdown。保留每环境第一局，排除首帧、done 覆盖帧及后续 reset 局。复用通道，不将球足转换成假掌面网格或给 sole 面積判分；完整接触协议与材料点滑移仍由接触专项承担。新接触边沿 helper 的合成正例与 reset 污染负例已运行，未变更冻结协议或奖励。

**真实策略接触帧补证（contact07）**：同一 model_5999，0.5 m/s、seed 123、4 环境、500 步，reset_count=0；与 use05 的逐关节汇总完全一致，采集没有改变策略轨迹。排除首帧后有效控制帧 1996，足端净力指示占比 lf/rf/rl/rr 为 61.8% / 61.6% / 56.7% / 62.5%，接触指示帧总倾角均值 8.04° / 11.63° / 43.29° / 49.39°，后腿世界横向分量均值 -42.35° / 49.23°。力边沿候选数分别 71 / 74 / 72 / 82（跨 4 环境汇总），对应倾角中位数 9.23° / 20.95° / 46.47° / 49.21°。候选数可能含接触抖动，绝不能作为真正落地次数或步频。

该实际策略片段腹部净力 >1 N 指示占比 0，前向速度 MAE 0.0514 m/s，每环境前向位移约 4.90–4.93 m。读数只用于该固定速度短时诊断，不是核心协议速度/跌倒/完成度 verdict。策略能在无腹部接触指示下推进，后腿却在接触指示帧明显侧倾；因此零目标夹具塌低不能直接代表策略行为，且仅靠速度收益并未消除后腿姿态问题。仍不能从这些结果认定某个奖励项或 PD 是唯一根因。

第 2 步已获得五组、两种工况的读数与负例；尚无限矩变体、已学习轨迹上的增益因果对照、正式支撑分类。第 3 步现仅完成控制帧接触候选与速度/位移诊断；真实首次落地、稳定接触与滑移仍未标定，不添加落地奖励或关闭本项。

测量边界：不走 `env.step`，使用正式动作项 process/apply 与 decimation 物理子步，故无自动终止/reset/奖励或策略作用；每工况显式从零姿态复位并稳定 2 s。求解器 Kp/Kd 写入后核对后台读回，改参不依赖隐式执行器旧估计缓存。力矩使用 K*(target-q)-D*dq 的控制帧后估计，50 Hz，不是逐物理帧实测，饱和比例仅标“估计”。腹部为 base_link/chest_pitch 净接触力，不是已核定的逐接触支撑口径；着地若姿态/接触变化，低幅相比不能单独判驱动弱。拟合比例/相位正例与反号、零响应负例已执行，人工波形 0.6 幅比、30° 滞后复现。

**奖励通路只读核对**：`lizard2_recipe.py:lizard2_rewards` 显式移除 `feet_air_time`、`dof_pos_limits`、`flat_orientation_l2`、`dof_acc_l2`、`ang_vel_xy_l2`；manifest 的实际 reward 类别为速度跟随、偏航跟随、垂直速度、动作变化、力矩、腹部接触六项，没有小腿落地姿态或 swing 周期运动目标。`action_rate_l2` 用 raw action 与 prev_action 的差，不用处理后 target；固定大 raw 偏置本身没有动作幅值惩罚，但改变它仍有 rate 成本。`last_action` 返回 raw action，饱和输出不是所有通路都等价。此只表明目标未约束用户期望的分工，不证明哪项导致 swing 正向漂移；须结合动态读数和后续对照。

### 已学习策略增益干预：执行方案

**方向纠正（2026-11-04）**：用户指出，对已训练策略提高 swing 并看是否生成周期目标，与其提出的目标不符。提高 swing 的动机是相对当前过强的肘/膝驱动调整大腿与小腿的驱动配比，供后续训练使用，并非期待旧策略直接学会周期运动。下述冻结策略对照仅保留作既有执行记录，不能用于否定调整驱动配比或预测重新训练效果。Kp 是单位位置误差的驱动刚度，不是实际力矩；实际力矩还受误差、阻尼和力矩上限影响。尚未实施新配方训练对照。

用户要求继续专项，并明确不处理其他会话的 rebuild 成本问题。本次不修改其测试/预算/文件、不另行复测其成本，已有失败日志仍保留，不称通过。

直接沿 model_5999、0.5 m/s、seed 123、4 环境、500 步的已绑定基线，逐运行单独比较：`swing_kp2`（四腿 swing Kp×2、Kd×sqrt(2)）、`twist_kp2`（四腿 twist 同幅修改）、`swing_kd_half`（仅四腿 swing 阻尼减半）。正式 v7 文件、资产、clip、scale、effort limits 和小腿驱动不改，不训练；源策略权重不变，仿真配置干预在实例化前执行并核对求解器增益。基线与变体使用同一诊断口径，保留 reset_count、每环境第一局有效帧数、接触帧倾角、速度误差、位移、腹部接触指示及关节实际/目标摆幅和跟踪误差。

这验证冻结策略闭环在增益干预下的响应，不是新增益训练收益或唯一根因证明。若倒地/触腹/提前终止，保留失败与样本截断，不只比较剩余有效样本的均值。输出 `policy_base08`、`policy_swingkp09`、`policy_twistkp10`、`policy_swingkd11` 各独立目录/日志；没有正式落地阶段口径就不添加奖励、不把接触边沿候选叫 touchdown。结果未出之前不定改参或新版本。

**基线与 swing 刚度干预已完成（policy_base08 / policy_swingkp09）**：均为 10 s、reset_count=0、有效控制帧 1996、腹部接触指示 0，`clip_actions=None`；四腿 swing Kp 恰为基线两倍，其他腿轴 Kp 不变。前腿目标 5–95% 跨度仍为 0，而 lf/rf 实际跨度由 0.144/0.222 rad 降至 0.113/0.181 rad，平均跟踪误差由 0.094/0.072 rad 降至 0.064/0.058 rad。提高驱动只是更紧跟随同侧饱和固定目标，并没有让前腿学出周期运动。

后腿接触指示帧倾角均值由 43.29°/49.39° 变为 41.91°/47.89°，只改善约 1.4°/1.5°；后 swing 实际跨度 rl 0.374→0.410 rad、rr 0.229→0.214 rad，左右变化不一致。速度 MAE 0.05138→0.05110 m/s，不能称显著改善；位移约 4.90–4.93→4.96–4.99 m。仍是单 seed/单速度/短窗口的冻结策略干预，不代表重训收益或唯一根因。

执行器与反馈的边界核实：本 fork `Articulation.reset()` 仅重置执行器状态与外力，不重新加载原始增益；本次基线及 swing 干预又都无 reset。动作 wrapper 本次不裁 raw，20 s episode/0.02 s 控制是 1000 步，500 步是 10 s，不能误称该窗口必然超时重置。比较使用同一 first-episode mask，不混用 reset 后的 top-level 汇总。

**执行失败**：在补记 run plan 的 Python 括号错误后，`policy_twistkp10.log` 记录 `SyntaxError: unmatched ')'`，未创建环境或产生策略证据，后续链中断；已修复并通过全文件 AST 解析，使用全新 `policy_twistkp12` / `policy_swingkd13` 重跑两项，不覆盖失败日志。此为本轮诊断脚本错误，与策略无关；基线与 swing 干预此前完成，不作废其实际输出。

**四组冻结策略干预核查完成**：原定 `policy_twistkp10` 未运行成功、`policy_swingkd11` 未启动，实际 twist / 降 swing 阻尼结果取 `policy_twistkp12` / `policy_swingkd13`；不将方案目录冒充已执行。四组均无 reset，1996 有效控制帧、4 环境、0.5 m/s、10 s，腹部净力接触指示均为 0，未重训。

| 干预 | 速度 MAE（m/s） | rl/rr 接触指示帧总倾角均值（度） | lf/rf swing 实际跨度（rad，p5–p95） | lf/rf swing 目标跨度（rad，p5–p95） |
|---|---:|---|---|---|
| 原配置 | 0.0514 | 43.29 / 49.39 | 0.144 / 0.222 | 0 / 0 |
| swing Kp×2、Kd×sqrt(2) | 0.0511 | 41.91 / 47.89 | 0.113 / 0.181 | 0 / 0 |
| twist Kp×2、Kd×sqrt(2) | 0.0548 | 45.18 / 48.06 | 0.180 / 0.251 | 0 / 0 |
| swing Kd×0.5 | 0.0531 | 42.02 / 49.82 | 0.137 / 0.178 | 0 / 0 |

前腿 swing 的处理后目标在四组中都维持近乎常值，提升驱动不会凭空产生周期目标；twist 提高刚度使左后倾角更大，降低 swing 阻尼也未带来双后腿一致改善。当前证据不支持“改 PD 即解决现有策略的大腿参与和落地姿态”。这不是 PD 对重新学习无价值的证明，也不把后腿改进一两度当作统计显著或合格结果。

本轮落点：已把隔离执行器响应与真实策略闭环响应区分。正式配方保持不变，小腿驱动不削弱，范围不扩大；后续仍需核定落地阶段和多轴配合目标，再由用户选定是否做新版本训练对照。既有速度/动作变化/力矩目标未直接限定用户的前后腿分工，当前仅记录此目标缺口，不直接加入 swing 摆动奖励，避免为摆而摆、影响支撑或规避落地。

### 子步落地阶段采样：执行口径

本步只补专项测量，不修改配方奖励或协议。沿原 model_5999、0.5 m/s、seed 123、4 环境、10 s，新增四个单 body 足端—地面过滤传感器；地面路径取 v7 已存在的 head-floor 终止配置，结构上核实际 CollisionAPI/过滤路径。逐 5 ms 物理子步，调用原 scene.update 后同时读取 filtered force matrix、小腿有向轴、圆足球心、完整关节和根位姿；逐控制窗断言恰有 4 帧。只保留第一局，首控制窗及所有 done 窗整窗排除。

事件口径为“过滤地面垂直力 >1 N，之前至少 20 ms 连续未达阈值，之后至少 10 ms 连续接触”，记录首个阈值达到子步的时间/倾角/球底高度。三种数字是诊断筛选窗，不是合格倾角阈值、不成为训练奖励批准；须对不同窗做敏感性及几何对照，不能把一次浮动边沿冒作已标定首次落地。短抖动、持续接触不计为新事件；合成正例检两个有效边沿，抖动和 reset 污染负例已跑。

失败 `landing14.log`：`resolve_presets` 后 cfg 已是具体 `ContactSensorCfg`，再照未解析 recipe 写 `.default/.physx` 报 `AttributeError: 'ContactSensorCfg' object has no attribute 'default'`。本轮错误已修为直接修改解析后实例；不改框架或正式配方，失败日志留存，新目录 `landing15` 复跑正常退出。

**逐子步落地观测（landing15）**：2000 个物理子步、四环境有效样本 7984、reset_count=0，逐关节汇总与 use05 完全一致；新增 sensor/采样未改变原策略轨迹。过滤力与小腿方向数组同形 `(2000,4,4,3)`、同步 5 ms；选定窗下 lf/rf/rl/rr 事件数 69/74/72/80，总倾角 p10/中位/p90 为 8.23/9.38/11.18°、18.89/21.12/21.66°、35.03/46.61/48.28°、46.65/49.30/52.04°。后腿横向分量均值约 -40.52° / 48.30°；前右在接触刚发生时比持续接触平均姿态更倾斜，不能将支撑均值当落地角。

事件球底高度全范围 -0.33 至 +0.12 mm，和地面附近首次达到净力阈值一致；只是几何/通道一致性，不是材料点接触或滑移认证。窗敏感性（flight/contact）10/10 ms 数 70/88/74/81，20/10 ms 数 69/74/72/80，40/20 ms 数 67/72/72/77；右前的短力间断明显影响次数，仍不能把该计数当步频或真正腾空周期。为固定条件诊断沿用 20/10 ms，不用调整窗消除坏角度。

**多轴落点约束补核**：仅“小腿能竖直”不足，须同时检查它是否需要移走已接地足端。用同一原策略的真实 landing 关节/根位姿，预算每腿 1 s 后最多前三事件，原限位内四轴两初值最小二乘分别解“只对竖直方向”和“原球心不动＋竖直方向”。1 mm / 1° 为求解残差的诊断尺度，不是用户批准的步态容差；局部求解失败不能证明全域不可达，允许足端移动所得竖直姿态不代表仍能支撑。`landing15` 未保存完整 runtime_joint_names，因此其原 NPZ 不猜顺序、不补造元数据；新 `landing16` 保存实际顺序，`landing_geometry17` 作几何对照。未做支撑/碰撞/连续路径验收，不据结果直接加奖励。

**固定脚位补核结果（landing16 / landing_geometry18）**：关节顺序取本次实际 articulation，295 过滤事件；采集仍与 use05 逐关节汇总一致。每腿首三事件共 12 个，原姿态 FK 对球心最大残差 `3.83e-5 m`，方向残差 `7.59e-5`。定根位姿/其他腿与躯尾，原限位内方向目标单独求解都达到近 0°，但这些特定解把脚位移走 0.147–0.403 m；这不是达到竖直必须移这么远的下界。

硬等式保持原 FK 球心位置（解后误差 <1e-6 m），局部 SLSQP 两初值最优残余：lf 0.08–3.28°，rf 12.57–14.53°，rl 37.25–42.72°，rr 34.94–38.07°。完整最小二乘仅作位置/方向折中，重命名 `position_orientation_tradeoff`，不能因误差几 mm 就叫“固定脚位”。这些局部残余不证明全域不可达，但显示当前已选落点、身体姿态与严格竖直目标存在实际约束冲突；直接在整个接触期追竖直，可能迫使换落点、移动身体或滑移。方向数组故意交换分量，FK 一致性断言拒绝 `landing FK direction mismatch`，正例与负例均执行。

因此下一步是选择落地分工目标的语义与容差：落地前的落点/多轴配合，和接触后维持支撑不互相替代。不能把“任意足位可竖直”的离线结论当成当前落点下可原地摆正，也不能仅给固定 swing 更大驱动解决该约束。具体容差和训练对照须用户选择；本项仍 in_progress，不新增正式奖励或启动训练。

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

- 子步落地采样：`rl_exp/out/lizard2_shank_tilt/landing15/result.json`（未保完整 runtime 关节顺序，仅事件读数）及 `landing16/result.json`、`landing16/landing_samples.npz`（含实际关节顺序）；复读 rollout 入口加 `--landing_samples --contact_samples`，全新输出目录；失败 `landing14.log` 保留。
- 落地几何：`rl_exp/tools/diagnose/lizard2_shank_tilt_reach.py --landing_report rl_exp/out/lizard2_shank_tilt/landing16/result.json --out <新 result.json>`；结果 `landing_geometry17/result.json` 为软约束中间证据，`landing_geometry18/result.json` 含硬固定脚位及软折中，不覆盖旧读数。FK 正例检查球心/方向残差，分量置换负例拒绝；零 rpy 前提仍由入口核定。
- 冻结策略干预：`rl_exp/out/lizard2_shank_tilt/policy_base08/result.json`、`policy_swingkp09/result.json`、`policy_twistkp12/result.json`、`policy_swingkd13/result.json` 及各自 `contact_samples.npz`、同级 `.log`。基线同 contact07 无轨迹变化；三干预使用 `--policy_drive_case swing_kp2|twist_kp2|swing_kd_half --contact_samples --viz none`，其余复读命令一致，使用新输出目录。失败留 `policy_twistkp10.log`；括号修复在内存还原旧代码 AST 必败、当前 AST 通过，并已实际跑过两项。轴选择测试确认小腿与非指定轴不改，仿真后台增益与 data 读回一致。
- 第 2 步验证：`rl_exp/out/lizard2_shank_tilt/step2_offline_checks.log` 中 37 项功能检查通过但隔离 rebuild 单测成本超预算；仿真结束再跑 `step2_offline_checks02.log`，37 项功能仍通过，`test_rebuild_gate.py` 单独 25.3 s 超 25 s、整体 exit 1。并行仿真不是全部原因，不将此改称已通过、不改预算。该单测在其他会话的工作树也有改动，本轮不擅自修其归属；成本门未绿，暂不提交/推送本轮动态与接触诊断。
- 真实策略接触诊断：`rl_exp/out/lizard2_shank_tilt/contact07/result.json`、`contact07/contact_samples.npz`、`contact07.log`；复读同 rollout 命令添加 `--contact_samples`，全新输出路径。实际采集保留第一局并排除 done/首帧；helper 合成正例仅留合法边沿，故意忽略有效窗会多出起始/reset 边沿。该 NPZ 不含 floor 过滤或逐子步落地权威，不消费为冻结协议判分。
- 动态入口：`rl_exp/tools/diagnose/lizard2_shank_use_probe.py --checkpoint <本 run/model_5999.pt> --out <新目录/result.json> --drive_probe suspended --viz none`（着地改 `--drive_probe ground`）；各目录 `plan.json` 先于物理标定写入，`progress.json` 和逐关节 NPZ 保存过程。失败 `drive_suspended01.log`，初版 `drive_suspended02`/`drive_ground01` 与补证版 `drive_suspended03`/`drive_ground02` 均保留，日志为同级同名 `.log`，运行完成须以结果与日志实际核查。
- 奖励口径：`rl_exp/tasks/lizard2_recipe.py:225`，框架 `envs/mdp/rewards.py:257`（raw action rate）、`envs/mdp/observations.py:740`（raw last_action），以及本 run `run_manifest.json` 的 `ready_to_learn.term_classes.rewards`。
- 验证：`rl_exp/out/lizard2_shank_tilt/step1_offline_checks.log`，`ALL_OFFLINE_CHECKS_PASSED (37/37 in 51.5s)`；实时复读正常退出，FK 改轴负例通过。回填后 `check_work_docs.py` 再跑 `WORK_DOCS_OK (105 item file(s))`；格式/仓库闸门不证明步态修复或独立审核。
- 原离线扫描复读需指定全新 `--out`（默认 `reach01/result.json` 已存在，现脚本拒绝覆盖）；实时补证复读：`<配置解释器> -B rl_exp/tools/diagnose/lizard2_shank_use_probe.py --checkpoint <本 run/model_5999.pt> --out <新目录/result.json> --pose_samples --viz none`，再用 `<配置解释器> -B rl_exp/tools/diagnose/lizard2_shank_tilt_reach.py --pose_report <上述 result.json> --out <新目录/result.json>`；此入口保存逐轴归零切片并执行改轴负例。
- 本轮输出：`rl_exp/out/lizard2_shank_tilt/usd_axes01/result.json`（正式 USD/URDF audit 与全部锁哈希）、`rl_exp/out/lizard2_shank_tilt/pose06/result.json`（实时姿态）、`rl_exp/out/lizard2_shank_tilt/pose06.log`（仿真日志）、`rl_exp/out/lizard2_shank_tilt/pose_fk02/result.json`（FK/单轴扫描/逐轴归零/改轴负例）；`pose_fk01` 为追加归零字段前的保留中间证据，不覆盖。
- USD audit 复用入口：`rl_exp/tools/diagnose/lizard2_round_feet_usd.py:audit(stage, tree)`；配置解释器下 `Usd.Stage.Open('rl_exp/lizard2_round_feet/lizard2_round_feet.usda')` 与 `ET.parse('rl_exp/lizard2_round_feet/lizard2_round_feet.urdf').getroot()` 传入，完整输出保存于上述 `usd_axes01`；不用只支持导出目录的 CLI，不传 `--repair`。
- 视频目录：`ablation_harness/videos/lizard2_v7_model5999_20261104_101635/`，`matrix.json`、九个单段、`plane_overview.mp4`、既有 `recording.log` 保留；抽帧入口 `rl_exp/tools/diagnose/clip_sheet.py --video <单段> --start 0 --duration 10 --fps 1 --cols 5 --rows 2 --scale 480 --grid 240 --out <新帧图>`。

## 未覆盖边界

- USD/URDF 与实际姿态仅覆盖上述资产与 0.5 m/s、seed 123 的 20 个 env 0 读点，未作连续域、复杂地形或极端姿态核查。
- 几何切片包含足端位置，但无支撑稳定、关节自碰撞与无滑移约束；单轴归零改变落点。可视化范围扩大尚未验证，也未修改正式资产。
- 足端高度与净垂直力仅作两种接触代理；已采控制帧力边沿候选，但未正式测首次落地、限位接触、跌倒率或材料点有效推进；不能将后腿横向倾斜或归零几何收益直接归因到驱动/奖励。
- 已绑定复读 run/checkpoint/资产与既有录像，用户所看现场身份未获显式确认；视频只抽帧，缺完整当时条件与执行记录，不能判整体训后流程完成。
- 五组隔离执行器探测及四组冻结策略短时增益干预已采且核查；限矩变体、新版本训练因果对照、正式落地事件口径及独立审核未完成。其他会话的成本问题按用户要求不处理；既有失败记录保留，不动该会话文件。本轮未提交。
