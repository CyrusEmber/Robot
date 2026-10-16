# 原局部路径的四肢组合几何检查

## 适用范围

承接 `acceptance/records/2026-10-16-lizard2-local-path-mirror.md`。用户本轮选择“先查四肢组合”：lf/rr 同相、rf/rl 错半个路径周期，固定机身，最多 129 个组合姿态；首次几何失败即停，复用原容差、路径与完整碰撞集合，不求解、不平滑、不宣称承重步态。

主执行者直接实现、运行、自查，不起仿真或训练，不改资产、ROM、PD、正式或冻结配方。运行时、导出器及限位 PD 专项的 E 回交属于并行执行者，本轮不暂存其改动。不新建事项或机器闸门，不展开连续域证明，不关闭 A 或专项。

## 验收条件

- 绑定原两腿完整 `budgeted_local_path` 及同一候选、根姿态、几何依赖、具名五轴与源关节零值；任意缺失、失败源段或不支持的网格不得悄悄补齐。
- 按真实镜像轴和限位推导 rf/rl，lf/rr 原相位保留；用关节线性插值及周期回卷，不复制单腿几何判词。组合参数 s 无量纲，不是秒数。
- s=0..1 均匀 129 个组合姿态，各原段四分点覆盖；每姿态一次全机地面及 139 个非排除碰撞对检查，四掌分别核相位、接地/离地、前后行程、有向掌面、反曲、限位及落掌顺序。
- 全部 30 个关节、18 个碰撞实体及四掌读点保留；完整周期核关节分支及参考点闭合，失败即停且不超预算。
- 记录实际几何接地腿集合；碰撞、闭合或进程退出成功不替代足掌支持判定。符号、错相、插值、漏碰撞扫描、超预算、失败停止及假闭合须有实际函数破坏测试。

## 结果

### 实现与复用

`rl_exp/tools/diagnose/local_path_check.py` 增加互斥的 `--combined` 模式。`_phase_angles`、`_combined_angles` 只消费原接受端点；`_combined_check` 负责顺序、预算、失败停止及闭合；`_combined_run` 绑定具体四肢并写报告。全机几何从原 `_state` 提取到 `_body_state`，组合姿态只检查一次全机网格；原四分点／镜像 `_state` 默认仍直接计算同一口径，不新建 FK、碰撞器或求解器。

组合映射为 lf/rr 相位偏移 0、rf/rl 偏移 0.5，真实镜像仍只有 twist 反号。所有躯干、颈尾关节零位，原 root 不变。输入仍为 `rl_exp/out/lizard2_palm_local_path_contact_20261015/report.json`，绑定 `rl_exp/out/lizard2_palm_spatial_20261014/checkpoint_v3/build.json`；输出为 `rl_exp/out/lizard2_palm_local_combined_20261016/report.json`，模式 `sampled_local_path_combined`。

### 组合几何读数

129 个组合姿态完成，`completed_combined_loop=true`、`failure=null`。无实体相交／包含、超原 1e-5 m 数值容差的全机穿地、翻掌、原反曲判据、限位、相位方向／离地或落掌顺序失败。每个姿态完整 30 关节、18 实体，139 对的实体相交、正间隙及零间隙非实体相交三类分区完整。

| 腿 | 接地阶段最大绝对最低 z [m] | 最大最低 z [m] | 最小掌法向 z |
|---|---:|---:|---:|
| lf | 8.97526931998e-7 | 0.03056987545 | 0.9980709929 |
| rf | 8.97526931998e-7 | 0.03056984695 | 0.9980709929 |
| rr | 3.60725583948e-6 | 0.03056643083 | 0.9977475847 |
| rl | 3.68910273785e-6 | 0.03056742860 | 0.9977475844 |

全机采样最小 z 为 -3.60725583948e-6 m，仍只在原数值容差内，不称物理零穿透。固定机身下掌参考运动不能证明世界无滑移或推进。

### 发现相位支持缺口，不宣称完整步态通过

实际几何接地腿计数：67 个姿态为两掌接地，62 个为零掌接地。零掌接地读点分两组：s=0.2578125..0.4921875、s=0.7578125..0.9921875，各 31 个采样点；该范围描述已有离散读点，不升级为全区间证明。

原因是原单腿后摆接地只占路径前四分之一，其余为抬升、前摆及回中立；两组仅错半个周期，形成所有掌同时离地的组合。原四段路径均分参数并不等于可持续足掌支持的相位安排。此轮只核固定机身几何，零掌接地不触发新增未获准的动力学失败阈值；但明确禁止将 `completed_combined_loop` 当持续承重直行通过。未测尾部支持、腾空动力学或惯性跨越，也不能借拖尾默认解除该缺口。

无需把该读数归因于缺轴、PD 或奖励：下一步先处理相位占比／映射与接缝，再按获准预算重验受影响组合。保留原几何的重参数化可作为候选，但本轮未批准具体映射、根运动或持续支持指标，未自动修改。

### 复核与回归

执行者用 NumPy `interp` 独立比对全部关节的原网格插值、镜像符号及周期错相，所有角度误差低于 1e-14 rad；根姿态、检查／排除对及采集代码绑定一致，躯尾零值不变。完整关节周期回卷与原完整分支闭合被复核。

正常 self-check 通过；六项新增实际函数破坏 `combined_offset/combined_interpolation/combined_pairs/combined_stop/combined_budget/combined_closure` 及十一项原破坏测试均以 AssertionError 退出 1。另直接调用 `_combined_check`，四腿正例通过；仅最后一条 rl 分别注入接地残差、穿地、翻掌、反曲或限位失败，均在首姿态带具名原因停止。组合报告独立复放判词仍闭合、129 姿态，无新增采样。既有输出目录重跑写前拒绝、退出 1，报告未变。

自检首次失败来自新测试使用错误碰撞字段 `surface_crosses`，真实判定消费 `intersects`；改测试输入为真实字段后正例和漏扫描破坏通过验证，未改变生产碰撞分类。源采集／镜像报告及求解器未改；原镜像 258 行映射与判词独立复放不变，无新增采样；原 `local_path_view.py --self_check` 通过。

完整既有离线套件 37/37 通过，48.8 s；baseline 波内 31.1 s、单独复核 24.5 s，符合原 25 s 预算。不改套件或阈值。实现提交 `ad69d2b` 的全部提交钩子通过；这些自查不替代 D 的独立审核。

## 证据引用与复读

- 原路径、四分点、镜像：`acceptance/records/2026-10-15-lizard2-palm-local-contact-repair.md`、`acceptance/records/2026-10-16-lizard2-local-path-quarters.md`、`acceptance/records/2026-10-16-lizard2-local-path-mirror.md`。
- 接缝：`acceptance/records/2026-10-16-lizard2-local-path-postprocess.md`；本轮未修复。
- 实现：`rl_exp/tools/diagnose/local_path_check.py`；路由与边界：`rl_exp/docs/leg_geometry_reuse.md`。
- 源报告 SHA256：`f0671a53a8d5b97c40844f6ea771b655bdd3bf8d5ab98ef64b02a1a7550a34c8`。
- 组合报告 SHA256：`e7dc05ab141ec5a4eecbef63fba0f7cf78163bef0dce410765741de79889d44e`。
- 本轮检查源码 SHA256：`7c49ce3df19797cf43dabf9a1851cb74ca4b0efb84facbb981547b943136e1af`。
- 报告包含候选、全部几何依赖、源码和原报告身份，原报告与历史判词不改写；本机输出不承诺入仓。

从仓根运行，解释器通过 `python -B ablation_harness/host_paths.py --python` 解析。复读输出必须不存在：

```cmd
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/local_path_check.py --self_check
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/local_path_check.py --self_check --break_test combined_offset
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/local_path_check.py --self_check --break_test combined_interpolation
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/local_path_check.py --self_check --break_test combined_pairs
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/local_path_check.py --self_check --break_test combined_stop
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/local_path_check.py --self_check --break_test combined_budget
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/local_path_check.py --self_check --break_test combined_closure
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/local_path_check.py --combined --source_report rl_exp/out/lizard2_palm_local_path_contact_20261015/report.json --output_dir rl_exp/out/lizard2_palm_combined_reproduce
```

负测试应退出 1。采集退出 0、无几何失败及闭合均不判承重通过；同时读取 `geometric_contact_legs`。

## 未覆盖边界与下一步

原相位有实际零掌接地读点，持续足掌支持尚不成立；本轮不进入承重 PD 标定或正式配方。下一步由 A 提出相位占比／映射、接缝处理及根运动口径，获得确认后重验受影响组合，不重跑不受变化影响的资产和旧证据。

完整时间映射、有效限速、世界材料点滑移／滚动、躯尾协调、动力学及用户外观／动作确认仍未完；未生成组合动画、未批准步长／净空或转向恢复范围。不做连续域证明，离散记录不改称全域安全。A 及限位 PD 专项保持 in_progress，P2/P3、运行时与最终 D 的交接继续。
