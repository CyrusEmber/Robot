# 受载保持精度未达关节的一次小幅 PD 对照

## 适用范围

2026-10-21 用户确认“试试，只增加到有误差的关节”。承接[原逐轴结果](2026-10-21-lizard2-loaded-remaining-axes.md)和[稳定性/精度口径](2026-10-21-lizard2-loaded-precision-interpretation.md)，仅选择原保持精度未达的左右后髋 twist、左右膝、左右肩 twist、左右肘共八轴；不是把所有非零误差轴都纳入。不创建子 agent。

## 验收条件

八轴同时使用 `Kp×1.2`、`Kd×sqrt(1.2)`，后者约增加 9.5445%，沿用现有中立惯量近似的阻尼比设计；其它 22 轴增益不变。力矩/速度上限、armature、几何/限位/过滤和输入不变，仅改隔离配置，不写正式资产或冻结配方，不自动采用为默认值。

固定根 z=2 m、31 body 开重力、无夹具/地面支撑；每轴从正常 reset 开始，静置 5 s、正/负各 0.02 rad 的 6 s quintic 往返，dt=0.005 s、零速度目标；每轴 3400 步，一次整组最多 27200 步。全过程增量误差 ≤0.012 rad，保持/返回末段 ≤0.002 rad，其它轴增量 ≤0.01 rad，静置漂移 ≤0.002 rad、静差和绝对目标误差 ≤0.1 rad。仅保持精度未达可记录后继续，返回/其它判据或安全条件失败仍停；绝对角度/误差 >0.35 rad、速度达到读回限速一半、接触 >1 N、非有限或 actor/FK 不一致即停。不重跑原通过轴，不运行六组合，不扫描增益、不自动重试或再加码。

以两轮各自 5 s 自重平衡角为增量基准比较原双向保持、返回和最大误差；同时保留静差、其它轴偏移及速度/接触读数。一次改动八轴意味着每项的其它七个调增轴也用新增益保持零目标；本试验评价该八轴配置整体，不冒称只改被命令单轴的完全隔离因果对照。

## 结果

一次整组完成八轴、27200 步，未重试；`completed=true`、`selected_cases_completed=true`、状态 `self_weight_gain_trial_completed_precision_unmet`。八轴保持误差均下降，但仍全部高于原 0.002 rad 阈值，八项原判词均为 false。退出码 1 表示严格精度未达，非中途异常。

| 关节 | 原双向保持误差上界 rad | 本轮上界 rad | 降低比例 |
|---|---:|---:|---:|
| `rl_hip_twist_joint` | 0.0027659558505 | 0.0023579192162 | 14.75% |
| `rr_hip_twist_joint` | 0.0027659241855 | 0.0023579452932 | 14.75% |
| `rl_knee_joint` | 0.0057986373827 | 0.0050777476095 | 12.43% |
| `rr_knee_joint` | 0.005798581969 | 0.00507773038 | 12.43% |
| `lf_shoulder_twist_joint` | 0.0032717441022 | 0.0028033866361 | 14.32% |
| `rf_shoulder_twist_joint` | 0.0032718968391 | 0.0028034359962 | 14.32% |
| `lf_elbow_joint` | 0.0057867714018 | 0.0050663691759 | 12.45% |
| `rf_elbow_joint` | 0.0057870321721 | 0.0050665107369 | 12.45% |

**判定：小幅增加这八轴 PD 对本次保持偏差有缓解作用，下降范围 12.43%–14.75%，但未达到原诊断精度线。** 不把增益比例与误差改善比例当线性规律，不从一次对照倒推再增多少即可达标；没有继续加码、改变阈值或自动正式采用。

执行者直接复算全部 27200 帧的时轴、双向目标、backend 位置/零速度目标与全部判词逐值一致；实际正负运动方向正确、返回条件均满足。全过程增量误差最大 0.00620063392226 rad，返回末段最大 2.75205820799e-06 rad，其它轴增量最大 0.000173571519554 rad，均在各自原界内。绝对角度、绝对误差、速度、接触、finite、静置和 actor/FK 条件均通过，没有安全停止。最大接触 0 N；全体最大速度为读回限速的 7.02966%，仍未触边。

独立 XML RPY/Rodrigues 及归一化 actor 四元数重建 40 份、每份 31 body 的实际姿态 FK，最大矩阵分量差 1.04085213781e-06，小于 1e-5。PD request 依采集运算类型全帧精确重建，差为零；仍是请求估计，不是实际求解器力矩或饱和观测。

直接核对 design 和 backend：只有选定八轴 Kp/Kd 按批准比例变化（读回按 float32 表示），其它 22 轴读回逐值不变；其它 design 字段和 readback 完全一致。新旧 tracking manifest 仅 source 路径及八轴刚度/阻尼值变化，还原这些后结构全等；effort/speed cap、固定基、31 body 重力、输入和绑定资产不变。

本轮只证明该八轴配置在原受载小幅工况中减小保持偏差且维持已检查的稳定/返回行为。当前增益试验保留为隔离候选，正式默认增益尚未定稿；是否保留或继续优化须结合用途精度和支撑/组合表现，不将协调任务转交 PD。

提交前完整离线套件通过：`ALL_OFFLINE_CHECKS_PASSED (37/37 in 53.3s)`；回填后另核台账及 diff 格式。自检与格式闸门不等于无执笔历史的独立审核。

离线前置：复读原 29 轴的完整样本/判词和恢复链，自动选择八个仅保持精度失败轴；旧小幅、新输入、胸部、自重套件与新入口自检通过，错误批准摘要拒绝。持久自检在去掉 gain trial 分支、使未选轴也被调增、取消 Kp 增量三种源码破坏后均失败，恢复原候选后通过。破坏摘要分别为 `8484f2b3da46d8fdaf9bb5ec2d8a503087533ea953fa40d5ab1c66ca5195e6d4`、`118d58bf1fc7842412fda6e8a7d2aa48a876ae741caf67a161b25f6d3ccebeac`、`6bed81bc0c7bfbdaf55c5f5b6f3f70d72ba7aa16ea67c3f76663c7ca932e6323`。

## 证据引用

- 原 17 轴续测 report：`rl_exp/out/lizard2_b_loaded_axes_20261021/report.json`，SHA256 `7a9141ed06cf187718309c2db7e17f9a5657fcace542caa7827f76dc7ccc8570`；其恢复链同时绑定此前 12 轴，合计 29 轴原始判词。批准惯量报告摘要仍为 `f1f9951a5057e4f5431316be373b5e359fbd3f5f8d79d3c2978bda140f5d06fd`。
- 本轮候选 `rl_exp/out/palm_spatial_tracking_gain20_HEAD.py.txt` SHA256 `0b945cefe7de2b03182956e0d89ba7bc599e6f8774585a0b1c2a402ef57e3b19`，以 `5da3844` 的工具源码为基线加本轮增量，不含工作树 RF/视频 WIP；同一增量已合入工具，源码提交 `c9ac9c8` 限定该候选，使用独立索引保留共享文件其它 WIP；提交前钩子通过。
- 真实启动日志 `rl_exp/out/lizard2_b_gain20_20261021.log` 首行记录候选摘要及完整 argv；用原工具 `__file__` 与 `__candidate_source__` 编译执行批准 bytes。运行目录 `rl_exp/out/lizard2_b_gain20_20261021/` 保留 source、manifest、逐轴原始样本及报告。
- 前置日志 `rl_exp/out/lizard2_b_gain20_preflight_20261021.log`；本机复读及破坏检查 `rl_exp/out/check_gain20_candidate.py` 留存。不把本机工件引用当入仓承诺。

| 本轮本机工件 | SHA256 |
|---|---|
| report.json | `4e3d140b619bc9236da4cead7322c15c9b0f887a1efe031b12087f6019ac3f7a` |
| tracking_manifest.json | `78e9e97ae589e818c4ee2d81322c4ee2cc296045ecce47a9306de0270accde1e` |
| audit.json | `4bfce05a71eab84b6a53c9d8118766ba76eee229fd304fef1fda8433ce1f587b` |
| 运行日志 | `cb38a5e7f6c301babc525474111e51ff49adcfe61db1ee2029856f26f1c2b6dc` |
| 前置日志 | `1661caccce0093c98d125d626e1b600439ce8d2114ab883dcaf3dd1f0696f259` |

逐帧直接复读脚本 `rl_exp/out/audit_gain20_20261021.py` 与日志 `rl_exp/out/lizard2_b_gain20_audit_20261021.log` 留存本机；不冒称独立关闭审核。

持久入口（复跑物理须另获预算，新输出目录）：

```cmd
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp\tools\diagnose\palm_spatial_tracking.py --headless --device cuda:0 --all_joints --self_weight_suite --precision_gain_trial --resume_self_weight E:/Robot/rl_exp/out/lizard2_b_loaded_axes_20261021/report.json --approved_resume_sha256 7a9141ed06cf187718309c2db7e17f9a5657fcace542caa7827f76dc7ccc8570 --approved_inertia_sha256 f1f9951a5057e4f5431316be373b5e359fbd3f5f8d79d3c2978bda140f5d06fd --inertia_report E:/Robot/rl_exp/out/lizard2_e_fresh_inertia_20261020/report.json --out E:/Robot/rl_exp/out/lizard2_b_gain20_replay
```

离线自检去掉 `--headless --device cuda:0`，追加 `--self_check`，保留新 out 参数；不创建输出或启动物理。

## 未覆盖边界

本轮不重测原通过轴的主动动作，不覆盖六组合、自由基座接触支撑或步态，也没有实际求解器力矩/饱和及有效速度触边实测。PD request 是估计，不能据此宣布力矩上限不足或充足。即使精度改善也不自动正式采用；本轮为执行者直接复核，不代填独立审核或关闭 B/C/E/D，协调仍交 RL。
