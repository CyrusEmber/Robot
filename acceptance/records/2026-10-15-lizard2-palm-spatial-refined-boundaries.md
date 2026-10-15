# 后腿机身／踝掌局部干涉转折

## 适用范围

用户要求继续执行，并确认定位后腿干涉转折、数值角宽取 0.0001 rad。承接 `acceptance/records/2026-10-15-lizard2-palm-spatial-static-slices.md` 的实际四个后腿相交姿态；只加密相邻异态边，不重跑完整切片、不开新步态目标，不修改资产、ROM、PD 或安全余量。

## 验收条件

- 沿源报告中右后腿 `base_link ↔ rr_ankle` 的相邻分离／相交边定位，固定边外所有角度；新报告保留完整具名两端姿态及目标与全体检查对的实体判词。
- 核对源候选、根摆位、过滤、角网格、完整姿态和依赖身份；两端重新进行完整碰撞检查。重复源行、被改变的零上下文或检查对集合必须拒绝且不产生成功报告。
- 二分保持两端异态并收缩；角宽仅为数值定位，不代表机械接触精度、连续安全域、单调域或最终限位。

## 结果

### 方法与绑定

在现有 `rl_exp/tools/diagnose/palm_spatial_probe.py` 增加 `--refine_slices`；复用 `_static_prepare`、实际 `Leg`、具名角网格、地面读点和全体 `Collision.check`。读取旧 270 姿态报告后，只选右后腿目标对的相邻异态边，共 9 条：四条 twist 边、四条膝角边、一条踝角边。相同状态的边不扫描；非单调边可能有多个转折，二分只保留其中一个异态括号。

候选集合、根摆位与全体检查／排除对保持源报告一致：30 个可动关节完整列，根高度 0.602799 m，139 对检查、14 对排除。当前 probe 新增模式造成的代码摘要变化与源摘要分别记录，其余直接依赖摘要必须一致。用于定位的每个源端点重新核目标及完整实体相交集合，未把碰撞检查缩成单一目标对。保留此前 1e-9 m 精检触发，安全余量为 null。

### 两端异态括号

下表每个区间低端分离、高端实体相交，其它关节均为零；列出的固定角为该条边的上下文。角度单位 rad，所有角宽均不超过用户选择的 0.0001 rad。

| 加密轴 | 固定上下文 | 分离端～相交端 [rad] |
|---|---|---|
| hip_twist | knee=1.2，ankle=-0.261799388 | 0.484610097～0.484674013 |
| hip_twist | knee=1.2，ankle=0 | 0.420118988～0.420182904 |
| hip_twist | knee=1.2，ankle=0.261799388 | 0.370200697～0.370264613 |
| hip_twist | knee=1.2，ankle=0.523598776 | 0.331531598～0.331595514 |
| knee | hip_twist=0.523598776，ankle=-0.261799388 | 1.176123047～1.176196289 |
| knee | hip_twist=0.523598776，ankle=0 | 1.137011719～1.137084961 |
| knee | hip_twist=0.523598776，ankle=0.261799388 | 1.106909180～1.106982422 |
| knee | hip_twist=0.523598776，ankle=0.523598776 | 1.086254883～1.086328125 |
| ankle | hip_twist=0.523598776，knee=1.2 | -0.400816397～-0.400752481 |

表内固定 twist 四舍五入显示；实际姿态取报告完整 `q_rad`，不以表中近似值代替复读输入。twist 转折随踝角从约 27.77° 移到约 19.00°；固定 twist 时膝角转折同样随踝角改变。这证明本次所选高屈膝切片的机身／踝掌干涉是耦合的，不支持将表中最小值抄成独立关节安全盒。

九条括号两端的踝掌最低网格顶点均在固定地面以上，约 0.2221～0.2604 m；因此这些反例的目标对判词来自机身内部干涉，不是地面穿透。其它工况地面和碰撞仍须分别检查，不能由此推出整条动作可行。

### 检查与反证

`--self_check` 同时覆盖原静态口径与两端方向、手算阶跃、非单调限制和粗分辨率。`refine_state` 与 `refine_shrink` 在内存中破坏同一二分函数，再运行同一检查，分别以 `lost opposite states`、`bracket did not shrink` 退出 1；恢复实现后通过。

实际源报告破坏三例：复制网格行、修改固定零姿态、删检查对，均退出 1，输出目录未创建。实际加密退出 0，9 条括号均保持分离／相交两端且宽度符合选择；退出 0 是定位完成，不是姿态全部合格。

不带执笔历史的新上下文核对代码、源输入校验、端点缓存跨轴复用、两端状态与过滤集合，未发现阻塞。该审核未运行正式加密，不替代执行者的实际报告读数核对；整个重构事项仍在办。

完整离线套件 `offline_suite.py --python E:/IsaacLab/env_isaaclab/Scripts/python.exe --jobs 4` 37/37 通过，47.4 s；波内合计 162 s 仅信息，不改变预算。另一个不带执笔历史的新上下文抽查实际报告、记录和在办交接，确认目标对、九条异态括号、角宽和未完边界一致，无阻塞；未逐条独立复算全部角值、哈希或检查对数量，这些读数由执行者实际汇总核对，不能冒称完整独立复算。两项审核均不授权关闭整个重构事项。

## 证据引用与复读

- 源报告：`rl_exp/out/lizard2_palm_spatial_static_20261015/report.json`，SHA256 `60d5e017c039a89fca5abe52d66b069e22d22c622af2b6ac6e7dc7540bad19dd`。
- 加密报告：`rl_exp/out/lizard2_palm_spatial_refined_20261015/report.json`，SHA256 `95c4a03ea1047070cde4e32e2f2dba891922a0659c69de164e556c80b47f56d3`。保留每条边的来源网格 index、原角端点、新端点的完整 `q_rad`、目标网格对判词、全体实体相交对、掌最低网格顶点和方向。
- 实现入口：`rl_exp/tools/diagnose/palm_spatial_probe.py` 的 `_refine_slices`、`_refine_bracket`。产物本机保存，不承诺入仓。

从仓根运行，解释器由 `python -B ablation_harness/host_paths.py --python` 解析；复读须换不存在的输出目录，不改源报告：

```cmd
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/palm_spatial_probe.py --self_check
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/palm_spatial_probe.py --self_check --break_test refine_state
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/palm_spatial_probe.py --self_check --break_test refine_shrink
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/palm_spatial_probe.py --refine_slices --build_report rl_exp/out/lizard2_palm_spatial_20261014/checkpoint_v3/build.json --source_report rl_exp/out/lizard2_palm_spatial_static_20261015/report.json --angle_resolution 0.0001 --output_dir rl_exp/out/lizard2_palm_spatial_refined_reproduce
```

## 未覆盖边界与交接

本次未扫描同态边、内部窄失败带、全部 twist／膝／踝组合、swing／abduct 非零或根姿态变化；不宣称单调或完整安全域。未做镜像后腿切片、连续动作、承重、速度、驱动和策略验证。角宽是该数值判词括号的宽度，不是物理接触准确度。

下一步将具体耦合反例交限位 PD 专项作为诊断输入；选取相位动作时需绑定真实组合姿态，避免用独立限位裁剪替代轨迹验证。其余几何前提、相位目标与候选动作输入继续按原在办路线推进，不为局部反例擅改骨骼、范围、体高或驱动，也不因加密完成而关闭事项。
