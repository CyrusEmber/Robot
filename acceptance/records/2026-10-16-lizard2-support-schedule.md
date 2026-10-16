# 支持相位与保几何节点重参数化复验

## 适用范围

承接 `acceptance/records/2026-10-16-lizard2-local-path-combined.md` 的零掌接地缺口。用户本轮选择“支持相位＋接缝重参数化”：接地后摆占无量纲周期 5/8，抬升、前摆、落掌各 1/8；lf/rr 同相，rf/rl 错半周期。每条原关节直线段用五次缓入缓出遍历，保留全部几何与原节点，但节点一、二阶参数导数归零。最多 129 个组合姿态，首次失败即停，采样至少两掌几何接地，不定秒数、不判承重。

已向用户明确每个原节点停速这一简化，不把它隐藏成自然步态。无需新求解器或几何平滑，不改源报告、资产、ROM、PD、正式或冻结配方，不起仿真或训练。并行运行时及验收改动不归本轮。连续接触／碰撞域证明不在授权内；A 和专项保持在办。

## 验收条件

- 原关节直线段与全部节点保留，实际映射消费获准相位占比和镜像符号；不改源报告、根姿态、容差或过滤。
- 复验不超 129 个组合姿态，首失败停止；每采样至少两掌几何接地，逐掌相位及全机地面／碰撞判据仍检查。
- 同一判据修复前失败、修复后通过；节点一、二阶参数导数、全部关节闭合与原几何保留有实际检查，负测试能拒错。
- 不把节点停速 C2 映射、采样接地或进程完成称为物理速度、连续安全域、稳定承重或正式采用。

## 结果

### 实现与验收口径

在 `rl_exp/tools/diagnose/local_path_check.py` 新增 `--combined --support_schedule`，旧三种模式默认语义不变。`_support_map` 将无量纲 c 分成 `[0,5/8,3/4,7/8,1]` 四段，每相位仍有原 8 个节点区间；单区间用 H(u)=10u³−15u⁴+6u⁵，保持原关节线段，映射为源 s=(区间编号+H(u))/32。记录 ds/dc、d²s/dc²，并按原直线段斜率与镜像符号算 dq/dc、d²q/dc²。

H(0)=0、H(1)=1；一、二阶导数在两端为零，故新 q(c) 在全部原节点及周期接缝有 C2 接续。原 q(s) 仍有原折点，不改写原斜率记录；这个算术性质不是连续接地／碰撞证明。每节点停速、三阶导数一般不连续，物理时间、加速度和限速尚未批准。

`_support_samples` 合并两组所有原节点，再取相邻合并节点的中点，计划 109 个完整组合姿态，低于 129 上限。新模式不沿用“原源段四分点全部重采”的口径，明确采的是变化后的组合节点／中点；不自动加密。复用 `_combined_check`、真实镜像、完整五轴 FK、原全机地面及 139 对碰撞；原 14 对排除和 1e-5 m 数值容差不变。每采样姿态增加至少两掌最低碰撞点在同一数值接地容差内的要求，检查原相位接地、离地、方向、落掌、掌面、反曲、限位、完整关节分支闭合。

### 实际结果

输入仍为 `rl_exp/out/lizard2_palm_local_path_contact_20261015/report.json`，候选绑定仍为 `rl_exp/out/lizard2_palm_spatial_20261014/checkpoint_v3/build.json`。新输出 `rl_exp/out/lizard2_palm_support_schedule_20261016/report.json`，模式 `sampled_local_path_support_schedule`。

109 个组合姿态完成，`completed_combined_loop=true`、`failure=null`。94 个姿态两掌几何接地，15 个姿态四掌几何接地，零掌／单掌接地采样数均为 0。无实体相交／包含、超原容差穿地、相位接地残差、离地／方向、翻掌、原反曲判据、限位或落掌高度增加失败。全机采样最小 z 为 −3.54200520769e-6 m，仅在原数值容差内，不称物理零穿透。

| 腿 | 接地阶段最大绝对最低 z [m] | 最大最低 z [m] | 最小掌法向 z |
|---|---:|---:|---:|
| lf | 8.97526931998e-7 | 0.03056987545 | 0.9980709929 |
| rf | 8.97526931998e-7 | 0.03056984695 | 0.9980709929 |
| rr | 4.68003030363e-6 | 0.03056408673 | 0.9977475847 |
| rl | 5.67925619366e-6 | 0.03056508388 | 0.9977475844 |

每姿态完整 30 个关节、18 个碰撞实体，139 对分类分区完整；躯、颈、尾零位，根变换不变。左右参考 X 跨度仍约 0.0305692 m／0.0306383 m，仅为原探索路径读数，不批准步长或净空。

执行者按报告逐行检查实际相位标签与 local_c：名义接地段为 local_c≤5/8，包括端点，其余保持原非接地相位。每组有全部原节点，所有节点 dq/dc、d²q/dc² 为零；周期导数跳变也为零。原周期 dq/ds 最大跳变 lf 0.37582272049、rr 0.61063630963 rad/源参数，保持原值。两者使用不同参数，不能用跳变归零声称物理速度改善或无需限速标定。

### 回归与独立检查

- **同判据修复前失败、修复后通过**：将新“至少两掌几何接地”判据作用于原组合报告，首次在 c=0.2578125 失败、闭合完成字段为 false；作用于新报告，109 个已有读点全部通过。复放不新增几何采样，不改历史报告。
- 正常自检通过；新增 `support_fraction/support_curve/support_derivative/support_gate/support_samples` 实际函数破坏及原 17 项破坏均以 AssertionError 退出 1，共 22 项。分别拒错相位占比、线性替代五次映射、非零节点导数、漏支持判据、漏半周期组节点。自检初版把 c=0.5 误当源 s=0.2 的线性映射，纠正为五次映射的独立手算值后通过，生产映射未改以迁就读数。
- 用 NumPy Polynomial 及其独立导数核全部行的映射／导数，NumPy interp 核全部具名关节，角度差低于 1e-14 rad；核原节点、相位占比、代码与候选身份及完整碰撞分区。无新增几何采样。新输出目录重跑写前拒绝，报告摘要未变。
- 新上下文针对性研究审查无阻塞缺陷；提示接地腿数不应冒称物理占空比、导数依赖不同相位长度、节点停速有适用边界。本执行者另核实际报告的名义相位覆盖及全部节点导数；不把该短审查当 work 关闭或 D 集成审核。
- 原 `local_path_view.py --self_check` 通过。完整既有离线套件 37/37 通过，45.6 s，baseline 20.4 s，未改清单或预算。实现提交 `8a73947` 的提交钩子全部通过。

## 证据引用

- 原缺口：`acceptance/records/2026-10-16-lizard2-local-path-combined.md`；原接缝：`acceptance/records/2026-10-16-lizard2-local-path-postprocess.md`。
- 原源报告 SHA256：`f0671a53a8d5b97c40844f6ea771b655bdd3bf8d5ab98ef64b02a1a7550a34c8`。
- 新报告 SHA256：`85ab07309f4eaca67fb2895b11f30616948d1d19d438640465910041926e0086`。
- 本轮检查源码 SHA256：`f1856ad62ee6c9c4fb7536c2410a8e96c1a2f21598e675ee4c5a10ed4d776722`。
- 报告含实际完整依赖身份、相位／插值、采样 c、各腿映射导数、全机几何、掌接触集合及失败字段；本机产物不承诺入仓。原源、镜像及组合报告不改写身份。

从仓根运行，解释器由 `python -B ablation_harness/host_paths.py --python` 解析；复读输出必须不存在：

```cmd
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/local_path_check.py --self_check
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/local_path_check.py --self_check --break_test support_fraction
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/local_path_check.py --self_check --break_test support_curve
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/local_path_check.py --self_check --break_test support_derivative
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/local_path_check.py --self_check --break_test support_gate
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/local_path_check.py --self_check --break_test support_samples
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/local_path_check.py --combined --support_schedule --source_report rl_exp/out/lizard2_palm_local_path_contact_20261015/report.json --output_dir rl_exp/out/lizard2_palm_support_reproduce
```

负测试退出 1。采集退出 0 仅表示报告完成，需同时读取 failure、completed_combined_loop 及 geometric_contact_legs；不证明承重。

## 未覆盖边界

获准采样下的足掌支持空档已修复；保几何重参数化解决新 q(c) 的节点一、二阶参数接缝，不代表原几何路径变成圆滑自然步态。逐节点停速可引入实际控制问题，定时间与 PD 前必须按有效限速、驱动、接触跟踪复验；不自行用 URDF 占位 velocity 反推秒数。

四肢组合动画／用户动作确认、世界根运动与材料点滑移／滚动、有效限速与承重标定、躯尾协调、转向恢复及运行时交接仍未完成。两掌接地不说明支持力、质心支持区或稳定性，固定机身后摆仍可能有世界滑移。下一步交 A 做可读组合回放与根运动方案、交限位 PD 专项接时间／限速前提；不新增连续域证明，不进入正式训练或采用，不关闭 A、专项或总项。
