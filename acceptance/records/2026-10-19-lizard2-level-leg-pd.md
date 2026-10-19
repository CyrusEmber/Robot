# lizard2 水平胸部夹具下左前腿自重 PD 跟踪

## 适用范围

按[范围收束](2026-10-19-lizard2-pd-scope-correction.md)执行一次受控左前腿 PD 诊断。基座固定在原隔离高度 2 m，非左前腿的 25 个关节在隔离 USD 中设为零位附近的有限夹具范围，左前腿五个关节保留原范围；开启重力。该夹具承受机身及其它部分的载荷，左前腿只承受自身重力，不承担整机重量。没有移重、尾部随动或胸部补偿控制器，也不作地面离地/站立平衡结论。

正式资产、URDF、网格、惯量、力矩/速度上限和冻结配方未改。两次只比较原静站 PD 与仅左前腕调整后的隔离配置，不推广其它腿或完整 PD 标定结论。

## 验收条件

- 新入口仍为 `palm_spatial_tracking.py`，通过注册动作管理器执行 `--level_leg_plan`。只接受原左前腿目标，不接受移重关键帧；目标五角沿用[原单腿记录](2026-10-19-lizard2-single-leg-lift.md)，不增加幅度或路径扫描。
- 夹具范围为 ±1e-6 rad，仅写隔离 USD；保留 30 个动作/关节通道。运行时读回固定基座、重力 [0,0,−9.81] m/s²、全部 body 重力开启、25 个夹具范围及实际 Kp/Kd。由实际 chest_pitch actor 的世界姿态计算局部 +Z 与世界 +Z 的最大分量差，全程须不超过 1e-5；超出则停止，不能仅凭胸俯仰目标为零判水平。
- 先在零目标下静置 5 s，记录实际自重平衡角 q₀，再按原 2 s quintic 伸出、1 s 保持、2 s 返回、1 s 恢复执行一次五关节组合，共 11 s、步长 0.005 s。
- 将自重静差与运动跟踪分开：相对 q₀ 的运动增量沿用原跟踪条件，最大误差 ≤0.012 rad，保持末段与返回末段误差 ≤0.002 rad，其它夹具关节的增量 ≤0.01 rad。同时报告动作段绝对目标误差，须 ≤0.1 rad；不把增量条件解释为绝对定位达到 0.002 rad。
- 左前腿绝对目标误差 >0.35 rad、胸部非水平或接触力 >1 N 时停止；速度仍须低于读回上限的一半。仅两个物理对照，不追加频率扫描。失败须退出非零，成功须退出 0。

## 结果

### 原配置的真实失败

腿组沿用合格静站的 6 Hz、颈俯仰 2 Hz，原腕部 1 Hz。左前腕实际 Kp=0.3518143594264984 N·m/rad、Kd=0.11198599636554718 N·m·s/rad。在 0.195 s、目标仍为零、抬腿命令尚未开始时，腕角达到 −0.35952654480934143 rad，因 leg_absolute_error 停止；共 39 步，未完成静置或动作。胸部水平条件始终满足，最大分量误差 1.1387172662580274e-6，无接触力，进程退出 1。

这证明该原腕部设置不能在本次自重和偏差限制内保持零目标；失败不能归因于胸部偏转或整机平衡。未运行到硬限位，不据此宣称实际电机力矩饱和。

### 仅调整左前腕的对照

左前腕复用此前试过的 6 Hz 频率规则，阻尼比不变，实际 Kp=12.665316581726074、Kd=0.6719160079956055；其余关节 PD 不变。两次 USD/URDF 哈希、运行时范围、重力、目标与夹具一致，增益读回中仅 lf_wrist_joint 的 Kp/Kd 改变，对照见 comparison.json。

完整运行 2200 步、11 s，level_leg_tracking_verified，进程退出 0：

| 量 | 实际读数 |
|---|---:|
| 全程最大胸部水平分量误差 | 1.1387172662580274e-6 |
| 最大运动增量误差 | 0.004281607287194664 rad |
| 保持末段运动增量误差 | 0.0005871947443651659 rad |
| 返回末段运动增量误差 | 4.1211023926734924e-8 rad |
| 其它夹具关节最大运动增量 | 1.2541877367766574e-6 rad |
| 动作段最大绝对目标误差 | 0.02986419334601273 rad |
| 左前腕静置末角 q₀ | −0.028886040672659874 rad |
| 最大接触力 | 0 N |
| 两份实际实体快照的 actor/FK 最大矩阵分量差 | 9.747102922950476e-7 |

五关节运动增量最大误差分别为 swing 0.00216192、abduct 0.00274410、twist 0.00225668、elbow 0.00428161、wrist 0.00097879 rad。绝对偏差仍在，尤其腕部约 0.029 rad 的自重静差；本次通过仅按上述明确条件，不宣称精确绝对定位或已做重力补偿。

普通 `--self_check` 通过，含不运动、胸部非水平、绝对偏差超限反例。另在独立进程把水平容差故意改为 1，运行同一自检，其非水平反例断言失败并退出 1，证明该检查放坏后测试会变红；源码容差仍为 1e-5。既有逐轴/组合入口与默认无重力口径保留，未重复整套无变化物理测试。

## 证据引用

实现提交 `9ea6391`：`rl_exp/tools/diagnose/palm_spatial_tracking.py`，源码 SHA256 `9f82886dbb2279a9ea05df1987ed822c1e7d4045179fbd0856f8436ed4a0b80d`，两次目录的 source.py 均保存该版本。该代码提交的 root hygiene、framework pin/self-test、DR parity、version docs、work docs、obs protocol/live 闸门通过，不代替实际动作或独立审核。原始大报告及资产在本机，不承诺入仓。

| 仓根相对路径 | SHA256 |
|---|---|
| `rl_exp/out/lizard2_b_level_leg_original_20261019/report.json` | `bd1318f1022fca8acc79a5047ca9fec380f230fcd8420816994378105aa8ee82` |
| `rl_exp/out/lizard2_b_level_leg_original_20261019/lf_level_self_weight.json` | `0036e57c29322a55728eb21df68e52ac7af3f6ed134f8723df7cde28a89a42de` |
| `rl_exp/out/lizard2_b_level_leg_wrist6_20261019/report.json` | `34707e679a0dbd122bcc38a0bd357c62a7aa09f3f8fe87b99ffd0b40e859a268` |
| `rl_exp/out/lizard2_b_level_leg_wrist6_20261019/lf_level_self_weight.json` | `1f24eb2016583a10f3b6a63bd51801f5d008dfc1c359d90d4e957c3001277dc0` |
| `rl_exp/out/lizard2_b_level_leg_wrist6_20261019/measurement_summary.json` | `e5071269a37d22d4367f23f501a76f97c2e967a100802942d3f4d58285977765` |
| `rl_exp/out/lizard2_b_level_leg_wrist6_20261019/evidence_index.json` | `a3e679afbad3a9b51028abde3d136fb42df41e9ec603338aabe35c80f92f97a7` |
| `rl_exp/out/lizard2_b_level_leg_wrist6_20261019/comparison.json` | `4a97ada1e19b31bbb3f0c0d2c014e36b23214470fbf028a86047fa3cea0c1753` |

原/调整后 tracking_manifest.json 哈希为 `c69bc15251d66537512af65e07dcf203d6ff04d52ff727555c9bf3ba7ffff97d` / `6e77eab34864ba4f41528385abc641696f37ab0ea79a94e5cb8ba116d9c92345`。索引绑定两份报告、样本、USD/URDF、源码和指标；随后生成的 comparison.json 单独列哈希。输入惯量、静站和几何身份按报告 input 与前序记录追溯。

复读（仓根 PowerShell，输出须为新目录；原配置去掉腕部覆盖参数）：

```powershell
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/diagnose/palm_spatial_tracking.py --inertia_report rl_exp/out/lizard2_b_inertia_repaired_20261019/report.json --gain_reference rl_exp/out/lizard2_b_standing_neck2_20261019/report.json --level_leg_plan rl_exp/out/lizard2_b_lift_plan_wrist6_20261019/plan.json --wrist_frequency_hz 6 --out rl_exp/out/lizard2_level_leg_replay --viz none --device cuda:0
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/diagnose/palm_spatial_tracking.py --self_check
@'
import sys
sys.path.insert(0, 'rl_exp/tools/diagnose')
import palm_spatial_tracking as t
t.LEVEL_SETTINGS['level_tolerance'] = 1.
t._self_check()
'@ | & E:/IsaacLab/env_isaaclab/Scripts/python.exe -B -
# 最后一条是破坏对照，预期退出 1；普通自检与腕部覆盖后的本切片预期退出 0。
```

## 未覆盖边界

没有整机自由承重、地面支撑、外加载荷、其它腿的自重对照或全套 PD 合格结论。该夹具改变约束条件；本次左前腕诊断参数不默认替换正式或自由静站配置。绝对定位精度、实际电机力矩与有效限速边界仍按原事项保留，不由重建 PD 请求代替。原项目未完动作不取消、不关闭，本轮不追加整机控制。
