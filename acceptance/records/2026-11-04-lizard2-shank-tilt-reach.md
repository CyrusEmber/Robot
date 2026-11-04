# lizard2 v7 小腿倾角离线可达性：实施中（2026-11-04）

## 适用范围

`work/active/lizard2-thigh-drive-shank-landing.md` 的轴映射、URDF 几何可达性核查与 v7 策略诊断。对象为 `rl_exp/lizard2_round_feet/lizard2_round_feet.urdf`（v7 `asset_lock.json` 锁定资产的 URDF 侧），策略复读对象及条件见下文。尚未与 USD 比对，该 run 是否为用户问题现场及多视角录像未核定，未做执行器分项探测，未独立审核；不是完整步态验收或根因结论。

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

解读限制：swing 贴 clip 上限、几何上又不改倾角，后腿小腿倾角由 abduct/twist/knee 的组合决定（rr abduct 目标均值 0.58，贴近 0.6 上限）。这是单个 checkpoint、单一速度、单一 seed 的读数，不能据此归因到奖励或 scale，也不能断言 swing 偏置的原因；未做 scale/刚度/限矩分项探测。

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

## 未覆盖边界

- 未与 USD 轴向比对；离线 FK 未含根体倾斜、胸/颈关节、关节动态与地形。
- 只给倾角几何可达，不含接触、支撑稳定、关节自碰撞与足端落点；可视化范围扩大尚未验证，也未修改正式资产。
- rollout 只覆盖单一速度、seed 与短时片段，以足端高度作站立相代理，未正式测首次落地、限位接触、跌倒率或有效推进；样本汇总不构成完整步态验收。
- 已选定策略复读对象，但用户问题现场身份与多视角录像未核定；未做执行器分项探测、奖励因果对照或独立审核。
