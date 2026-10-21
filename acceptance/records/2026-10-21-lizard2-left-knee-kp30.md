# 左后膝 Kp=30 的单次受载双向对照

## 适用范围

2026-10-21 用户要求“再增加到30试试？kd也近似增加”。承接[八轴小幅增益试验](2026-10-21-lizard2-loaded-gain20.md)，仅将当前配置的 `rl_knee_joint` Kp 从 `20.15938973548149` 改为 `30 N·m/rad`，Kd 从 `4.525543810055274` 改为 `5.520681727025171 N·m·s/rad`，即按 `sqrt(30/20.15938973548149)` 配套增加。其它 29 轴维持当前值，包括上一轮已增加的其余七轴；不回退或再调整它们。不创建子 agent。

## 验收条件

沿用同一绑定输入、固定根 z=2 m、31 body 开重力、无夹具或地面支撑，armature=0、胸俯仰 cap=280 N·m，其它 cap/速度/限位/过滤不变。沿用原求解器配置，不开启外力逐次更新、不改求解器迭代，不把速度读数核验变成这次 PD 对照的前置物理试验。

一次工况：正常 reset，静置 5 s，正/负 0.02 rad 各 6 s 往返（2 s quintic 伸出、1 s 保持、2 s 返回、1 s 恢复），dt=0.005 s、零速度目标，共 3400 步；不重试、不追加增益、不运行其它主动轴或组合。增量基准为各轮自身 5 s 自重平衡角；最大增量误差 ≤0.012 rad，保持/返回末段 ≤0.002 rad，其它轴增量 ≤0.01 rad，静置漂移 ≤0.002 rad，静差/绝对目标误差 ≤0.1 rad。绝对角度/目标误差 >0.35 rad、速度达到读回限速一半、接触 >1 N、非有限或 actor/FK 不一致即停；其它非保持精度判据失败同样不追加运行。

## 结果

一次物理进程完成 3400 步，`completed=true`、`selected_cases_completed=true`、`left_knee_kp30_precision_unmet`。退出码 1 保留原精度失败，不是中途异常。前次八轴报告、逐轴原始样本及来源链在启动前重新复核；没有覆盖或重跑原结果。

| 量 | 正向 | 负向 |
|---|---:|---:|
| 最大增量误差 rad | 0.004961165950698766 | 0.004960774795217428 |
| 保持末段误差 rad | 0.0037219482287764553 | 0.0037210495024919514 |
| 返回末段误差 rad | 5.587935447692871e-8 | 9.220093488693237e-8 |
| 其它轴最大增量 rad | 0.00016448833048343658 | 0.0001647844910621643 |

前次 Kp≈20.16 的保持误差上界 `0.005077747609 rad`，本轮为 `0.003721948229 rad`，降低约 **26.7%**；相对原 Kp≈16.80 的 `0.005798637383 rad` 降低约 **35.8%**。本轮约 `0.213°`，占 0.02 rad 动作幅度约 18.6%，仍高于原 `0.002 rad` 阈值；此前简化模型给出的约 0.0037 rad 预测与本轮接近，但不据此自动推定下一档、正式采用或最终所需刚度。

**判定：增加左后膝刚度继续减小保持偏差，已检查的受载方向、返回与位置稳定行为保持，原保持精度线仍未达。** 未继续加码，未改阈值；不把本轮记成关节不能驱动，也不宣称默认 PD 已最终定稿。

执行者逐帧复算 3400 帧的时轴、双向目标、backend 位置目标 float32 表示和零速度目标、全部误差与判词一致；正负实际增量方向正确，q/v/目标/接触 finite，所有原停止条件未触发。最大静置漂移 `1.7229467630386353e-8 rad`，最大静置静差 `0.03190210834145546 rad`，全程最大绝对目标误差 `0.035109199583530426 rad`；最大接触 `0 N`。独立 XML/Rodrigues 与归一化 actor 四元数重建五份快照、各 31 body，FK 最大矩阵分量差 `9.471549303613491e-7`，小于 1e-5。

直接对比新旧 design/backend：只有左后膝 Kp/Kd 按批准值变化（读回为 float32 表示），其余 29 轴逐值不变，其它 readback/design 字段完全一致。tracking manifest 仅 source 路径和左后膝刚度/阻尼变化，还原后与前次结构全等；输入、资产和全部 cap 不变。PD request 依采集类型精确重建，差为零，仍是估计而非实际求解器力矩。

离线自检：旧小幅、新输入、胸部、自重套件及本次入口通过，错误批准摘要拒绝。取消新入口、错选右膝、误改额外关节时持久自检均失败，破坏摘要分别为 `d7dfb87d4087daac4bc42ddad1ef889c9315d1c2d6a567065a14a3a71f8d12a8`、`272c8d2da506723d22c511afd360cb8211aa93e43d4220e8e14ef65d47ca95c3`、`a9285ca2cf48fe3b148e3de4a12d6e05840334b2223f4d0b9ef1209b56e116f4`；恢复候选后通过。

完整离线套件通过：`ALL_OFFLINE_CHECKS_PASSED (37/37 in 44.9s)`；台账及 diff 格式检查通过，格式检查不代替独立审核。

## 证据引用

- 原八轴 report `rl_exp/out/lizard2_b_gain20_20261021/report.json` SHA256 `4e3d140b619bc9236da4cead7322c15c9b0f887a1efe031b12087f6019ac3f7a`；批准惯量报告仍为 `f1f9951a5057e4f5431316be373b5e359fbd3f5f8d79d3c2978bda140f5d06fd`。
- 隔离候选 `rl_exp/out/palm_spatial_tracking_knee30_HEAD.py.txt` SHA256 `163a7643b3a9fbb4edda2168726e15db25944e01763572cdbdd3dc7969b8b9e4`，以 `3a5df53` 源码为基线，不含共享文件 RF/视频 WIP；同一增量合入工具，源码提交 `475bb98` 仅纳该候选，独立索引保留其它 WIP，提交钩子通过。
- 本轮 `rl_exp/out/lizard2_b_knee30_20261021/report.json` SHA256 `071689b93852e93829d300ae26ab2b1f8ec3758e9538df2717a6f03580569723`；同目录 `tracking_manifest.json` 为 `c5b65e6d7f4b832ca53b7ce2379959d9b8ae209e8d5a60f45551dc017e2716c7`。
- 真实日志 `rl_exp/out/lizard2_b_knee30_20261021.log` SHA256 `fcc7713abebec60682f53323c1c4e6e2c6a6b4cd2340ff4d33c6fbb1945eb5ff`，首行保留实际候选摘要及完整 argv；使用原工具 `__file__`、`__candidate_source__` 编译执行批准 bytes，并保存相同 source 快照。
- 本机逐帧复读入口 `rl_exp/out/audit_knee30_20261021.py`、输出同目录 `audit.json` 与日志 `rl_exp/out/lizard2_b_knee30_audit_20261021.log` 留存；audit.json SHA256 `10c1ee89fca6a92f8e7c7b8758878722583f0a417268c846c911b469477496e9`；前置检查脚本 `rl_exp/out/check_left_knee30.py`、日志 `rl_exp/out/lizard2_b_knee30_preflight_20261021.log`（SHA256 `e6219e5fe476bf9224bddbe9c168f815113e82e553aaa087dfa132b116799065`）留存。本机工件引用不承诺入仓。

持久复读入口（物理复跑需另获预算及新目录）：

```cmd
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp\tools\diagnose\palm_spatial_tracking.py --headless --device cuda:0 --all_joints --self_weight_suite --left_knee_kp30 --resume_self_weight E:/Robot/rl_exp/out/lizard2_b_gain20_20261021/report.json --approved_resume_sha256 4e3d140b619bc9236da4cead7322c15c9b0f887a1efe031b12087f6019ac3f7a --approved_inertia_sha256 f1f9951a5057e4f5431316be373b5e359fbd3f5f8d79d3c2978bda140f5d06fd --inertia_report E:/Robot/rl_exp/out/lizard2_e_fresh_inertia_20261020/report.json --out E:/Robot/rl_exp/out/lizard2_b_knee30_replay
```

离线自检同命令去掉 `--headless --device cuda:0`，追加 `--self_check`，保留新 out；不创建输出或启动物理。

## 未覆盖边界

此前离线复查发现保持段速度读数与位置差分不一致，TGS 外力设置/速度迭代是待验证解释，尚未开展因果对照；本轮按用户要求保持求解器不变。沿用速度停止读数并不等于速度通道准确性已验证，不能据此定案阻尼或实际力矩/饱和。原位置误差和本轮改善是已保存的角度行为，不外推其它主动轴、六组合、自由基座/接触或任意姿态载荷。正式采用、速度边界和其它未完动作仍保留；本记录是执行者直接复核，不冒称独立关闭审核，不关闭 B/C/E/D。
