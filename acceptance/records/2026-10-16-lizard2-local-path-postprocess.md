# 局部路径独立后处理与斜率接缝读数

## 适用范围

用户要求轻量解耦、可复用，并确认独立后处理入口：求解采集和原报告不变，先完成已采轨迹、侧／俯视动画及路径斜率接缝分析；段内接地加密另定预算。本轮由主执行者直接实现、自查和运行，无子任务或独立关闭审核。不修改正式资产、ROM、PD、冻结配方，不起仿真、训练或重新求解。

## 验收条件

- 后处理独立读取 `budgeted_local_path` 报告，不导入 `palm_spatial_probe` 求解器；复用既有 SHA256、URDF／OBJ 与 FK。通用斜率计算不硬编码腿数、关节数、相位点数或固定 ds。
- 原输入不变；仅使用原接受端点／中点。动画不平滑、补帧、造姿态或增加接地采样；失败报告只回放接受前缀，不纳入拒绝段，不伪造闭合接缝。
- 真实碰撞三角网格侧／俯视回放，标注腿、相位、s、端点／中点、最低顶点身份、参考点及掌法向；标记与绑定 FK 对齐。显示一致性不冒称接触／碰撞重新验收。
- q(s)、实际 ds 下的逐段 dq/ds、内部斜率跳变及仅完整闭合路径的周期跳变可复读。s 无量纲，不以动画时长推导物理速度，不增设无依据的合格阈值。
- 同一入口复用闭合和失败报告；斜率缩放、周期跳变符号、中点对应关系及根坐标变换的实际函数破坏均须被自检拒绝。

## 结果

### 解耦落点与复用边界

新增 `rl_exp/tools/diagnose/local_path_view.py`，单一后处理入口。层次为 `_path_stats` 数组算术、`_track/_load` 原报告与身份适配、`_plot/_render` 图表／真实网格显示；没有插件、类层、通用格式注册器或新依赖。复用已安装 NumPy、Matplotlib、Pillow 和仓内 `check_self_collision` 的 URDF／OBJ／FK 读点及 `binding.sha256_file`，不导入求解器、不调用碰撞扫描。

`_path_stats(s, q, phases, closed)` 不依赖具体机器人或关节名称，支持非均匀 s 和部分路径；当前 CLI 只适配 `budgeted_local_path`，不是任意历史 CSV／运行时报告通吃的框架。其它采集者若采用相同报告契约可直接复用；不同格式应先显式适配，不静默猜列。

求解器及采集报告完全未改。正常闭合报告为 `rl_exp/out/lizard2_palm_local_path_contact_20261015/report.json`，SHA256 仍为 `f0671a53a8d5b97c40844f6ea771b655bdd3bf8d5ab98ef64b02a1a7550a34c8`。历史失败输入为 `rl_exp/out/lizard2_palm_local_path_20261015_v3/report.json`，保留旧源码身份；后处理不要求旧求解器磁盘版本仍在，仅要求实际消费的候选／FK 身份相同。

### 输出与实际复读

最终闭合输出：`rl_exp/out/lizard2_palm_local_path_view_20261015_v2/`，每腿 `*_trajectory.png`、`*_side.gif`、`*_top.gif` 与共享 `analysis.json`。每条 GIF 800×500、65 帧：初始端点加 32 个接受端点及 32 个原中点，全部显示，不额外插值。单帧显示时长 100 ms 是播放设置，不是 s 或物理时间。使用全机 18 个碰撞实体、7260 个实际三角面，不用骨架线或凸包替换；橙色是活动腿，蓝色是其它实体，参考点不是材料接触点。

历史失败输出：`rl_exp/out/lizard2_palm_local_path_partial_view_20261015/`。lf 仍为完整 65 帧；rr 只保留 1 个接受点、3 帧，`cycle_slope_jump_rad_per_s_parameter` 为 null，失败阶段为 backward_contact。拒绝端点未画入接受轨迹；GIF 重播只是展示循环，不是从接受末点回中立的已验证段。

执行者复读两份输出：每帧完整 30 个关节对应实际 URDF，原中点恰为相邻端点关节均值；最低顶点位置、最低高度、法向与初始定义的固定参考点和绑定 FK 对齐。所有源摘要、后处理源码摘要、六个图像工件摘要均核对；Pillow 完整解码确认帧数与显示时长。另用 `diff(q)/diff(s)` 独立算术逐项比对报告斜率。已打开轨迹 PNG 与 GIF 查看布局，主执行者确认坐标、相位与标记可读；这不等于独立审核，也没有把肉眼观察当微米级接地证明。

首版 `rl_exp/out/lizard2_palm_local_path_view_20261015/` 保留初版代码身份；v2 补标记/FK复核及 dy 曲线，不覆盖历史产物或让当前摘要冒认旧身份。最终后处理源码 SHA256 为 `7a4078a3b7a1bb0f5de6307242cce744c6c21d02a961652f943ba00a86176c50`。

### 接缝读数：发现折点，不做无阈值通过声明

以下单位均为 rad／无量纲路径参数，不是 rad/s。内部跳变为 outgoing slope − incoming slope；周期跳变为第一段 slope − 最后一段 slope。

| 腿 | 后摆→抬升 s=0.25 最大绝对跳变 | 抬升→前摆 s=0.5 | 前摆→归中立 s=0.75 | 周期接缝最大绝对跳变 |
|---|---:|---:|---:|---:|
| lf | 0.2786116884 | 0.3036953630 | 0.3708902072 | 0.3758227205 |
| rr | 0.2689124108 | 0.4210275544 | 0.5186838101 | 0.6106363096 |

全体内部接缝的最大值恰在 s=0.75：lf 为 `lf_elbow_joint`，带符号 -0.3708902072；rr 为 `rr_ankle_joint`，+0.5186838101。周期最大值：lf 为 `lf_elbow_joint`，+0.3758227205；rr 为 `rr_knee_joint`，+0.6106363096。报告包含所有内部接缝及全部 30 关节向量，不只保留最大值。

完整关节位置仍闭合，分段线性路径连续但这些接缝不是 C1 光滑。报告揭示需要处理的路径折点，未把非零跳变自动判为机构不可达或动力学失败，也没有用后处理平滑隐藏它们。真正的速度满足 dq/dt=(dq/ds)(ds/dt)，时间映射与有效限速尚未确定；不能由图中斜率或动画帧率反推批准周期。

### 自检与检查

`--self_check` 正常通过。四个 `--break_test` 分别破坏同一实际函数：`slope_scale` 取消 ds 缩放、`cycle_sign` 反转周期差分、`midpoint` 放过错误关节中点、`world` 丢失根平移；运行相同自检均退出 1。正常自检还覆盖重复 s、假闭合、接受前缀及失败段排除，不新增测试框架或仓库闸门。

仓库完整离线套件 37/37 通过，57.8 s；baseline 波内 25.1 s、单独复跑 24.5 s，通过原 25 s 单项预算。未改套件或预算；工作格式与实现提交 `d46288a` 的全部提交钩子通过。另验证对既有输出重跑被拒绝、退出 1，六个工件和分析报告未变，原采集报告摘要未变。方法自检不替代两腿动作、连续接地或独立审核。

## 证据引用与复读

- 前置修复：`acceptance/records/2026-10-15-lizard2-palm-local-contact-repair.md`；历史失败：`acceptance/records/2026-10-15-lizard2-palm-local-path-probe.md`。
- 入口与口径：`rl_exp/tools/diagnose/local_path_view.py`；`rl_exp/docs/leg_geometry_reuse.md` 的“已采路径后处理”。
- 最终闭合 `analysis.json` SHA256：`845884b4d07aeeb93adf1417bfd3e207821a72e056dce48acd26cfd2854e2679`。
- 历史失败复用 `analysis.json` SHA256：`3b86a3c55a0e19f8217cc827458963bedcd1781cb17f2dcf09704fcc279bacc1`。
- 各分析报告保留原 source_identity、源报告摘要、后处理源码与依赖版本、图像工件摘要；本机动画／报告不承诺入仓。

从仓根运行，配置解释器由 `python -B ablation_harness/host_paths.py --python` 解析。输出目录必须不存在：

```cmd
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/local_path_view.py --self_check
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/local_path_view.py --self_check --break_test slope_scale
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/local_path_view.py --self_check --break_test cycle_sign
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/local_path_view.py --self_check --break_test midpoint
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/local_path_view.py --self_check --break_test world
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/local_path_view.py --source_report rl_exp/out/lizard2_palm_local_path_contact_20261015/report.json --output_dir rl_exp/out/lizard2_palm_view_reproduce
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/local_path_view.py --source_report rl_exp/out/lizard2_palm_local_path_20261015_v3/report.json --output_dir rl_exp/out/lizard2_palm_partial_view_reproduce
```

正常后处理退出 0 只表示显示／分析完成。失败报告也可正确生成显示，不能从退出码或文件存在判局部闭合、接触或动力学通过。

## 未覆盖边界

本轮完成动画与接缝**读数**，没有修复接缝。段内连续接地、连续碰撞、特征切换窄带、材料接触点滑移／滚动均未新增覆盖；全部回放只是原端点与中点，不能从动画称全区间安全。透明正投影不含真实遮挡光照，也不是运行时或 Blender 重开回放。

下一步仍需明确段内加密／区间验证预算与接缝处理规则；任何平滑或改分支会改变原几何路径，须重新验证接触与碰撞。其它两腿镜像、四肢组合、时间映射、有效限速、承重及 PD 保持未完，运行时 E 的交接不被本轮替代。两项 work 保持 in_progress，不宣布完整 5a 或事项关闭。
