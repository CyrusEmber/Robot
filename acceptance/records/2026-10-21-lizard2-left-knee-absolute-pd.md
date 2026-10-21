# 左后膝按实际目标关节角误差校准 PD

## 适用范围

2026-10-21 用户要求先选左膝做 PD 校准，并追问五轴组合运动时如何计算误差、两种精度口径何者更合适。执行者推荐以实际关节角对发出目标角的误差为主，增量误差辅助诊断；本轮只将该口径用于左后膝，不将其它 29 轴或历史[六组合记录](2026-10-21-lizard2-calibrated-combinations.md)重标为绝对精度通过。用户已授权左膝校准，不创建子 agent。

## 验收条件

`q_i` 是关节自身父子框架间绕活动轴的转角，不是 link 世界位置或世界 Euler 角。髋转动携带膝部在世界空间移动，不直接算作膝自身转角错误；前级动作改变重力/惯性负载而使膝自身未跟足目标时，则应计入。原 FK 检查只核实际 q 与实体姿态一致，不是足端世界轨迹验收。

后端目标仍从零到 ±0.02 rad。原增量误差 `|(q_i-q_i0)-u_i|` 扣除零目标下的自重平衡角 q_i0；本轮左膝主判据为 `|q_i-u_i|`，不扣平衡角。这里“绝对”指直接对目标计算，坐标仍是关节自身的相对转角。两种读数分开报告。左膝静置末段、双向保持末段和返回末段的实际目标角误差均须 ≤0.002 rad；运动瞬态不新增全程 0.002 rad 要求。原全组增量判据继续保留，不能以新判据通过掩盖其它轴响应失败。

用前序实际输入的静态重力平衡模型估算：Kp=138 可使增量保持误差约 0.00190 rad，但负向实际目标角误差仍约 0.00301 rad；Kp=210 的负向模型值约 0.002013 rad，Kp=220 约 0.001925 rad。模型仅选候选，不构成仿真实际、动态或全姿态精度保证。前序 Kp=65 的组合实际目标角保持误差独立复算为正向 `0.00147224448621273`、负向 `0.00615559563040733 rad`；原记录的 0.00382 rad 仍是增量误差，不能与这些数混称。

只将 `rl_knee_joint` Kp 从 65 改为 220 N·m/rad，Kd 从 8.126223472032024 改为 14.950076790041491 N·m·s/rad，即按 sqrt(220/65) 配套提高，保持原中立惯量近似下的名义阻尼比；其名义频率约 4.68 Hz，不当作接触下的精确模态。其它 29 轴 PD、全部 cap（左膝仍 180 N·m）、armature、求解器和限位/过滤不变，不增加补偿控制器。Kp×0.02=4.4 N·m 只是位置项尺度，不是总力矩预算或实际余量证明。

一次物理进程，最多两例：左后腿五轴组合 `rl_combined`，再左膝单轴 `rl_knee_joint`。组合中髋摆动/外展/扭转、膝、踝同步同方向 ±0.02 rad；固定根 z=2 m、31 body 开重力、脚掌不承地、无额外砝码，其它轴目标为零。每例 reset 后静置 5 s，正负各 6 s（2 s quintic 伸出、1 s 保持、2 s 返回、1 s 恢复），dt=0.005 s、零速度目标，各 3400 步，共 6800 步，不扫描、不重试。

原组级判据仍是：增量运动最大误差 ≤0.012 rad、增量保持/返回 ≤0.002 rad、其它轴增量 ≤0.01 rad，静置漂移 ≤0.002 rad；全组静差/绝对目标误差 ≤0.1 rad。绝对角/目标误差 >0.35 rad、读回速度达到 cap 一半、接触 >1 N、非有限或 actor/FK 不符即停；只允许单纯精度不达标时保存后继续第二例，其它失败停。新绝对角判据只作用于左膝；不把其余轴原自重静差强制收紧为 0.002 rad。

## 结果

两例均完整完成，一次 6800 步，物理退出 0，`left_knee_absolute_trial_verified`、`completed=true`、`selected_cases_completed=true`、`all_selected_cases_passed=true`。左膝新主判据与原全组增量判据都通过。

| 工况 | 左膝正向保持实际误差 rad | 左膝负向保持实际误差 rad | 左膝最大返回实际误差 rad | 左膝最大保持增量误差 rad |
|---|---:|---:|---:|---:|
| `rl_combined` | 0.000416402220726 | 0.00199608176947 | 0.000792805512901 | 0.00120910779107 |
| `rl_knee_joint` | 0.000188057795167 | 0.00139714635909 | 0.00079270999413 | 0.000604655225761 |

左膝最大保持实际误差 `0.0019960817694664 rad`（约 `0.114367°`），最大返回实际误差 `0.000792805512901396 rad`，静置末段最大实际误差 `0.000792707083746791 rad`，均满足 0.002 rad。最差保持只剩 `3.91823053359948e-06 rad`、即门限约 `0.195912%` 的余量，属于本工况贴线通过，不是负载变化后的鲁棒余量证明；未为扩大余量继续加码。

左膝运动期间最大实际目标角误差 `0.00263072515571853 rad`，高于 0.002 rad；本轮保持/返回判据通过不等于全程轨迹误差均在 0.002 rad 内。组合中原全组最大保持增量误差约 0.001976 rad，属于该组全部命令轴的最大值，不能误写成左膝独有误差。其它轴响应、返回、接触与原安全检查均通过。

执行者独立逐帧复算全部 6800 帧的目标时轴、两个工况的主动列、backend float32 位置目标与零速度目标、原增量误差和新增左膝实际误差，判词逐项相等；10 份 actor 快照×31 body 独立 XML/Rodrigues/FK 最大矩阵分量差 `9.47154930361349e-07`，满足 1e-5。请求估算重建差为 `0 N·m`，最大接触 `0 N`，速度通道读数未触原停止线。PD/manifest 对照恰好仅左膝刚度/阻尼及 source 路径变化，其它 29 轴、其它 readback、输入与资产保持。

原套件与新入口自检通过，错误批准摘要拒绝。以相同的“始终偏离目标 0.0035 rad、增量跟随正确”样本检验新要求：旧增量口径通过，新实际角口径拒绝；这是口径差异的行为正反例，不将旧约定追认成旧实现缺陷。移除绝对判据、误用右膝误差、误改右膝增益三种破坏均被拒绝；恢复候选后通过。完整离线套件 `ALL_OFFLINE_CHECKS_PASSED (37/37 in 46.0s)`，台账/提交钩子按本轮日志核对，不替代独立关闭审核。

源码首次提交钩子因并行活跃台账总量超额而拒绝，未跳过闸门；只收拢本轮两份事项中正文已有明确链接的重复前言证据索引，正文、状态和未完动作不变，随后台账与提交钩子通过。去重审计 `rl_exp/out/left_knee_absolute_work_route_dedup_20261021.json` SHA256 `24b778f5f03319a33649ba36f23210135c4845e1b865f99d5089811b77030b33`。

判定：只调左后膝 PD 后，本轮组合与单轴的直接目标角保持/返回精度通过，增量诊断也通过。其余三肢原组合精度失败仍保留，未按左膝结果自动修改其它关节或宣布全部默认驱动定稿。

## 证据引用

- 前序六组合 report SHA256 `903ec4dcf17ba4c6bd7c7f2e4e4e1a68ed0794cf0c17f18356554574b386de82`；启动前重新复读六组合、全部单轴及此前来源链，不覆盖原数据。输入惯量批准摘要仍为 `f1f9951a5057e4f5431316be373b5e359fbd3f5f8d79d3c2978bda140f5d06fd`。
- 本轮源码提交 `c09c6fd81e47bd2af2b44e8d21a21c30d4fbf7f3`，实际 entry SHA256 `2cc8b303ac9bb3c2fca1ff20f80899cdd9e09741f948b3af603526363c11961e`；已提交工具、候选 `rl_exp/out/palm_spatial_tracking_left_knee_absolute_HEAD.py.txt` 和物理 source.py 逐字节相同，不含共享文件 RF/视频 WIP。
- `rl_exp/out/lizard2_b_left_knee_absolute_20261021/report.json` SHA256 `361fb3816cc0c3ef28995c3343926fea934d25447ee3c0b3cfc5d4b2ec11668b`。
- `rl_exp/out/lizard2_b_left_knee_absolute_20261021/tracking_manifest.json` SHA256 `529a7b84e35225f9804ea8158d035515eca2e789855575073acb11c907d3eaad`。
- `rl_exp/out/lizard2_b_left_knee_absolute_20261021/audit.json` SHA256 `a6c87658f41a5617a8c5b1bbadb1a24853f33c2cfe3909025941c3206f3c6805`。
- `rl_exp/out/lizard2_b_left_knee_absolute_20261021.log` SHA256 `a2cd3d8616f7430076e13ba44f04a5e2ae53a723109b59404871b1ac0d11839a`。
- `rl_exp/out/lizard2_b_left_knee_absolute_preflight_20261021.log` SHA256 `8013ca918489162d40b1858af62e0985dc22022a76936aa3f5bbd04608160188`。
- `rl_exp/out/lizard2_b_left_knee_absolute_audit_20261021.log` SHA256 `19044492cc796cedd04295fc9d4a7fc045603b928d34d540b341daf7fa75d098`。
- `rl_exp/out/lizard2_b_left_knee_absolute_offline_20261021.log` SHA256 `e1852831cbb9753320a7e3645a29bf7b6d473fe8cf31663f6bbd9476f24dc3fc`。
- `rl_exp/out/lizard2_left_knee_angle_scope_plan_20261021.json` SHA256 `db9aa7655e5d2937ceaa5f240c43d34701407a381812106670bd8d290a0aa104`。
- 本机复读入口 `rl_exp/out/audit_left_knee_absolute_20261021.py`、前置正反例 `rl_exp/out/check_left_knee_absolute.py`、静态候选比较 `rl_exp/out/plan_left_knee_angle_scope.py` 留存；目录内原始逐帧 JSON、source、manifest、progress 与 audit 保留。本机工件引用不承诺入仓。

持久复跑入口（物理复跑需新预算和新 out；本轮未追加执行）：

```cmd
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp\tools\diagnose\palm_spatial_tracking.py --headless --device cuda:0 --all_joints --self_weight_suite --left_knee_absolute_trial --resume_self_weight E:/Robot/rl_exp/out/lizard2_b_combinations_20261021/report.json --approved_resume_sha256 903ec4dcf17ba4c6bd7c7f2e4e4e1a68ed0794cf0c17f18356554574b386de82 --approved_inertia_sha256 f1f9951a5057e4f5431316be373b5e359fbd3f5f8d79d3c2978bda140f5d06fd --inertia_report E:/Robot/rl_exp/out/lizard2_e_fresh_inertia_20261020/report.json --out E:/Robot/rl_exp/out/lizard2_b_left_knee_absolute_replay
```

离线自检去掉 `--headless --device cuda:0` 并加 `--self_check`，仍需新 out，不启动物理。新实际角判据正反例复读取前述本机检查脚本，不把入口准备检查等同全部负例覆盖。

## 未覆盖边界

只覆盖左膝本轮固定根、自重、中立附近的两例；不是全姿态、异相组合、其它关节、自由根/承地、额外负载、硬件或全程轨迹精度保证。实际驱动力矩/饱和与已有速度读数偏置仍未验证；不以 shadow PD 或本轮通过证明力矩余量。原其余组合失败、边界、reset 与训练前集成继续在办，不关闭 B/C/E/D，不冒称新上下文审核。
