# 两腿局部路径端点／中点联合接地修复

## 适用范围

承接 `acceptance/records/2026-10-15-lizard2-palm-local-path-probe.md` 的后腿接地中点缺口。用户选择“原预算内联合求解”：端点与关节线性中点接地联合求解，仍每点最多 3 次尝试、每次最多 200 次实际残差调用，不增加路径采样、不放宽数值容差。本轮由主执行者直接实现、自查和运行，无子任务或独立新上下文审核；不改正式资产、冻结配方、ROM、PD，不起仿真或训练。

## 验收条件

- 实际 lf／rr 五轴分别处理；其它关节零，根与候选身份、网格、139 对检查／14 对排除和既有路径增量保持不变。
- 接地后摆求解端点参考 XY、实际掌网格最低高度及关节线性中点最低高度。停止判据包含全部数值任务，不含末尾逐关节正则；端点和中点仍执行原完整几何检查，不因加入求解约束而取消外层拒错。
- 原每相位 8 点、每点最多 3 次确定性尝试、每次 200 次实际残差调用、1e-5 m 任务／接地数值容差及 0.05 rad 关节步距不变。一个联合回调包含端点和中点网格读数，计一次残差调用；调用次数计入有限差分，额外网格计算不冒称耗时不变。
- 真实候选关掉联合约束后复现原失败，恢复后通过；持久自检须拒绝遗漏中点任务及停止判据仅核前三项。点和中点通过不称连续段接地或完整 5a 验收。

## 结果

### 责任层与实现

旧失败段两端接地但中点离地，最低特征从顶点 380 切到 320。诊断回放中，旧段四分之一处最低高度 4.0441312728e-5 m，高于中点 2.6102393348e-5 m；特征切换附近仅核中点会漏过更高离地值。这些读数属于旧段责任层诊断，不代表修后段四分之一处已复核，更不证明实体姿态不连续。

`rl_exp/tools/diagnose/palm_spatial_probe.py:619` 的 `_local_residual` 复用原 FK 和网格最低特征，接地相位追加线性关节中点高度任务，不新增独立中点求解器或改为非线性插值。求解选择邻近端点分支，使本次原线性插值中点满足接地容差。

`_local_solve` 原来只核残差前三项；直接追加中点任务会被错误的“达标即停”忽略。新增回归先在旧停止判据下实际失败，报 `AssertionError: midpoint task ignored`；修为核除末尾逐关节正则以外的全部任务后通过。新 L2 停止条件要求所有缩放任务的联合范数不超过 1，未放宽任一分量容差。报告保留原字段 `best_scaled_position_error`，其现含全部任务范数；具体口径由 `config.solver_task_norm` 写明。

仅接地后摆增加中点求解任务；其它相位仍用原端点任务，所有相位保留端点／中点地面、碰撞、反面掌、反曲及关节步距检查。返回中立仍走原完整关节归零路径。实现未新增依赖、资产或闸门。

### 真实修前／修后对照

相同绑定检查点：`rl_exp/out/lizard2_palm_spatial_20261014/checkpoint_v3/build.json`。

- 修前控制：`rl_exp/out/lizard2_palm_local_path_contact_before_20261015/report.json`。内存中仅将 `_local_residual` 的 `contact` 强制为 False，外层检查不变；rr 全部报告行与旧 v3 完全相同，仅接受 1 点，在第二个后摆段因中点 `contact residual` 停止。该中点高度 2.6102393348e-5 m。报告的源码摘要描述磁盘代码，不记录内存改动；此控制必须连同下方改动命令解释，不可冒认未改动的正常运行。
- 修后：`rl_exp/out/lizard2_palm_local_path_contact_20261015/report.json`。lf／rr 各接受 32 点并回到完整中立关节分支。rr 第二个后摆段中点高度 1.1935701627e-7 m、端点最低高度 -5.1487008546e-8 m，均在原容差内。该点首次尝试 120 次调用、任务范数 3.14349，未达标；第二次 31 次调用、范数 0.0132501 达标。首次未达标不是预算耗尽，也未被当成功；未增加尝试数量。

### 修后读数与核对

| 腿 | 接受点 | 实际残差调用 | 单次最多调用 | 最大端点各轴步距 [rad] | 接地端点／中点最大绝对高度 [m] |
|---|---:|---:|---:|---:|---:|
| lf | 32 | 330 | 19 | 0.01094654535 | 8.9752693200e-7 |
| rr | 32 | 534 | 120 | 0.01216885885 | 3.6072558395e-6 |

lf 参考点 X 跨度 0.03056918937 m、掌最低特征最高离地 0.03056987545 m；rr 分别为 0.03063829811 m、0.03056408673 m。这是原探索路径的读数，不是合理步长／抬脚高度或共同目标的批准值。前腿调用数量虽与旧报告相同，联合残差改变了微小求解姿态，报告行并非逐字相同。

全体碰撞网格采样最小地面高度：lf -8.9752693200e-7 m、rr -3.6072558395e-6 m；均在原数值容差内，但不冒称精确零穿透。端点／中点未检出实体相交、反面掌或原平面角反曲禁区；最低掌法向 z 分别 0.9980709929／0.9977475847。后摆最低顶点身份 lf 为 320，rr 为 320／380，不把顶点身份变化称为材料滚动或无滑移。

执行者直接另核最终报告：候选文件身份、根姿态、全部检查／排除对及原配置键值与旧 v3 相同，报告源码摘要与磁盘一致；各腿 32 点／中点都有完整 30 关节，全部归零、没有失败项，原每点尝试及每次调用预算、关节步距和接地容差均成立。每个采集姿态仍经独立 stdlib 链 FK 与原 numpy FK 比较。这些是执行者复核，不是独立审核。

### 回归与仓库检查

正常自检通过。`local_contact` 与 `local_task` 修改同一实际残差／停止函数后运行同一自检，均退出 1；原 `local_stop/local_budget/local_ground/local_step/local_closure` 五项也全部退出 1。真实修前控制仍发生 rr 中点失败，恢复联合任务后两腿闭合；不是只跑绿色测试宣称覆盖缺陷。

完整既有离线套件两次均 37/37 通过：首次 52.1 s，提交前复核 52.9 s。首次 baseline 波内 25.5 s、单独复跑 22.1 s，通过原 25 s 单项预算；末次 baseline 24.8 s。未增减套件项或改预算。工作／记录格式检查通过；实现提交 `6c1ee3a` 的全部提交钩子通过，未跳过闸门。

## 证据引用与复读

- 前置相位契约：`work/active/lizard2-restored-limits-pd-validation.md` 步骤 5；首次失败证据：`acceptance/records/2026-10-15-lizard2-palm-local-path-probe.md`。
- 复用口径：`rl_exp/docs/leg_geometry_reuse.md`；本次源码 SHA256：`27e60da2cac2c36bfcf8a430594a334af25a92717370905117418409553e4add`。
- 修后报告 SHA256：`f0671a53a8d5b97c40844f6ea771b655bdd3bf8d5ab98ef64b02a1a7550a34c8`。
- 修前控制报告 SHA256：`e880c0cea15bf05199d617322a41abd6649346c0c10bd6e74827fdb65076c15f`。
- 原 v1／v2／v3 和本轮对照均保留各自身份，不覆盖历史产物；本机产物不承诺入仓。

从仓根运行，配置解释器由 `python -B ablation_harness/host_paths.py --python` 解析。下面输出目录必须不存在：

```cmd
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/palm_spatial_probe.py --self_check
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/palm_spatial_probe.py --self_check --break_test local_contact
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/palm_spatial_probe.py --self_check --break_test local_task
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/palm_spatial_probe.py --local_path --build_report rl_exp/out/lizard2_palm_spatial_20261014/checkpoint_v3/build.json --output_dir rl_exp/out/lizard2_palm_contact_reproduce
```

修前控制仅内存取消接地中点任务，不改文件。报告源码摘要仍是磁盘版本；此命令是必要的控制来源：

```cmd
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B -c "import sys; from pathlib import Path; sys.path.insert(0,'rl_exp/tools/diagnose'); import palm_spatial_probe as p; original=p._local_residual; p._local_residual=lambda model,q,previous,root,target,config,contact=False:original(model,q,previous,root,target,config,False); p._local_path(Path('rl_exp/out/lizard2_palm_spatial_20261014/checkpoint_v3/build.json'),Path('rl_exp/out/lizard2_palm_contact_before_reproduce'))"
```

正常采集退出 0 只表示报告完成，必须读各腿 `completed_local_loop` 与失败详情；破坏自检应退出 1。真实修前采集退出 0 不代表后腿通过。

## 未覆盖边界

本轮只补原点／中点局部闭合，未增加采样。因此修后线性段的四分之一点、特征切换位置及任意连续区间未核，不能因为两点接地加中点接地就称整段接地。局部解存在不证明全域可达、最优尺度、自然步态或完整两腿 5a 已交付。

轨迹图／侧俯视动画、dq/ds 与分段斜率接缝、获准加密下的接触连续性、材料点滑移／滚动、其它两腿镜像及四肢组合仍未完。世界系无滑移、时间映射、有效限速、质量／惯量、驱动和自由基座承重须按专项继续；其它会话运行时接线不被本轮取代或冒称完成。

两项 work 保持 in_progress。下一步整理本次已采轨迹及相位可视化，补路径斜率与接触连续性验证规则后再扩展，不暗增预算。正式资产、训练及独立关闭审核不在本轮完成范围。
