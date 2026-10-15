# 两腿预算内局部路径首次探测

## 适用范围

用户确认执行首次有预算的局部闭合路径探测，随后要求不再调用子任务。中断前没有产生本脚本改动；本轮由主执行者直接实现、核对和运行，不冒称有无执笔历史的独立审核。承接两腿相位契约及既有切片／转折证据，未启动仿真、未改机体、ROM、PD 或正式配方。

## 验收条件

- 实际 lf／rr 分别处理，五轴全部参与，根姿态和其它肢体保持中立；位置与接地目标不额外锁死掌法向。
- 探索步距取各腿实测较短骨段的 1%，每相位最多 8 点；这是获准探索增量，不是合理步长或能力上界。位置／接地数值误差为 1e-5 m，单次各轴变化不超过 0.05 rad。
- 每次求解最多 200 次实际残差调用（包含有限差分），每点最多 3 个确定性初值；误差、预算、端点或关节线性插值中点几何失败即停止该腿，不放宽条件。达成任务容差后立即停止，不为优化冗余姿态继续耗尽预算。
- 记录全体碰撞实体地面间隙、完整关节、掌面有向状态、端点与中点、失败阶段与残差；闭合需要完整关节分支回中立，不以参考点相同冒称闭合。

## 结果

### 实现与输入

`rl_exp/tools/diagnose/palm_spatial_probe.py` 新增 `--local_path`，复用 `_static_prepare`、实际五轴 `Leg`、独立树 FK、实际网格地面读点和全部碰撞对。没有引入依赖或改写历史诊断／切片／加密模式。预算与本模式数值口径集中在报告 `config`。

候选为 `rl_exp/out/lizard2_palm_spatial_20261014/checkpoint_v3/build.json` 绑定的自包含集合。根摆位、38 个候选文件、139 对检查和 14 对排除沿用既有验证口径；其它可动关节均为零。每个端点与中点保留全部 30 个具名关节。root +X 定义前向，固定根下后摆不称世界无滑移。

从实际 FK 的非共点枢轴量骨段：lf 上段 0.501644009 m、下段 0.382121 m；rr 上段 0.501659010 m、下段 0.382120 m。步距分别 0.00382121 m 和 0.00382120 m。增量比率为本次用户确认的探索采样，不由旧步長／周期推导，也不等于最终步态尺度。

任务残差为参考点 XY 与实际掌网格最低高度，五轴受候选限位和前一姿态 ±0.05 rad 约束；冗余分支以连续初值及微弱姿态正则保持邻近，不锁死法向。后摆接地、抬升、空中前摆各最多 8 点；返回中立沿完整关节分支分成 8 段，检查端点／中点落掌高度不增加、地面与碰撞判词。路径参数 s 无时间单位，不报告速度或承重合格。

### 初轮失败与责任层修正

初轮产物为 `rl_exp/out/lizard2_palm_local_path_20261015/report.json`。两腿首个接地后摆点都达到数值任务容差，却因最小二乘继续优化微弱正则，各 3 次尝试耗满 200 次残差调用而被预算判为失败。实际位置／接地残差约浮点舍入量级；不是机构不可达证据。

修复共享 `_local_solve`：回调已达到获准任务容差时立即返回当前最好候选，预算仍严格计入有限差分，几何检查仍在外层执行。没有提高预算、放宽误差、缩小探索步距或跳过中点。持久回归在关掉达标停止分支时失败，恢复后通过。

随后 v2 产物可读同样动作结果；自查又补初始中立验证及落掌中点到端点的高度检查，以最终版本生成 v3，不覆盖早期产物或把新源码哈希冒认旧报告身份。

### 最终实际读数

最终产物：`rl_exp/out/lizard2_palm_local_path_20261015_v3/report.json`。

| 腿 | 本次结果 | 接受点 | 实际残差调用 | 原因／覆盖 |
|---|---|---:|---:|---|
| lf | 局部闭合完成 | 32 | 330 | 四相位各 8 点，端点与关节插值中点均通过本次数值检查，完整关节归零 |
| rr | 停止，未闭合 | 1 | 38 | 第二个接地后摆点的关节插值中点离开几何接地容差 |

lf 参考点前后跨度约 0.0305678475 m，掌最低网格顶点最大离地约 0.0305694033 m；这是选定探索路径的读数，不是最终步长／抬脚批准值。最大单步各轴变化约 0.0109464892 rad，单次求解最多 19 次实际残差调用。

rr 第二个后摆端点任务已达标、没有实体相交或翻掌；其关节线性插值中点掌最低高度为 2.6102393348e-5 m，超过 1e-5 m 接地数值容差，故停止。中点全体网格最低高度为零（其它腿仍在地面），目标掌发生离地而不是全机穿地。该腿只接受第一个约 3.8212 mm 后摆增量；不能把包含拒绝端点的参考点跨度约 7.6424 mm 当接受行程。

失败来自本次局部解分支的线性关节插值未保接触，不是预算耗尽，也不证明后腿所有接地路径不可行。后续须针对该中点直接求接触约束的连续姿态或在获准规则下加密，而不是放宽接地阈值、跳过中点或扩大碰撞过滤。

### 方法检查与限制

自检覆盖实际残差调用预算、全机穿地、反面掌、反曲、实体相交、关节步距与完整分支闭合。五个局部破坏例（`local_budget`、`local_ground`、`local_step`、`local_closure`、`local_stop`）都通过修改同一实际函数后运行同一检查得到退出 1，恢复后正常自检通过。

完整离线套件 `offline_suite.py --python E:/IsaacLab/env_isaaclab/Scripts/python.exe --jobs 4` 37/37 通过，52.0 s；波内合计 177 s 为信息，不修改预算。最终代码身份与 v3 报告中的实际摘要一致。套件通过不证明两腿目标都已完成，也不能替代独立关闭审核。

本轮为主执行者直接自查，没有独立新上下文审核；代码检查、复读和仓库闸门不能替代事项关闭审核。前腿完成仅指本次点和中点的局部几何循环，不称连续域证明、自然步态或完整 5a 通过。尚未输出侧／俯视动画、四肢组合、材料点滑移或运行时验证。

## 证据引用与复读

- 相位意图：`work/active/lizard2-restored-limits-pd-validation.md` 步骤 5。
- 前置方法与当前候选：`rl_exp/docs/leg_geometry_reuse.md`；`acceptance/records/2026-10-14-lizard2-palm-spatial-trial-checkpoint.md`。
- 最终报告 SHA256：`74fbdd6905b4b08c96989a80c865b69c28108ef896c3f82cf2282bfc5f614e5b`。其中 `identity` 包含实际候选与本次源码绑定，源码 probe SHA256 为 `8e3b1c7449bd2f592d6cb7ac7d6aa87ef4c575e38992e96fa322754dadfea2a3`。
- 早期 v1／v2 与最终 v3 报告各自保留代码身份；本机产物不承诺入仓。

从仓根运行；配置解释器由 `python -B ablation_harness/host_paths.py --python` 解析。复读目录必须不存在：

```cmd
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/palm_spatial_probe.py --self_check
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/palm_spatial_probe.py --self_check --break_test local_stop
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/palm_spatial_probe.py --self_check --break_test local_budget
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/palm_spatial_probe.py --self_check --break_test local_ground
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/palm_spatial_probe.py --self_check --break_test local_step
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/palm_spatial_probe.py --self_check --break_test local_closure
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/palm_spatial_probe.py --local_path --build_report rl_exp/out/lizard2_palm_spatial_20261014/checkpoint_v3/build.json --output_dir rl_exp/out/lizard2_palm_local_path_reproduce
```

正常诊断退出 0 仅代表采集完成，各腿失败仍保留于报告；破坏自检退出 1。不可从命令退出码推导闭合通过。

## 未覆盖边界

后腿未完成两腿要求，不可宣布两腿 5a 交付。未做任意初值／路径全域搜索、四肢组合、任意连续段证明、承重、推进、时间映射、PD、转向或恢复。掌网格最低顶点是几何特征，不是已验证材料接触点或无滑移滚动通道；报告不证明这些能力。反曲以当前候选具名膝肘平面角作禁区检查，不代表完整解剖方向包络已有验收。

重构及专项保持在办；下一步定位后腿接地段的中点求解／分支连续性缺口，继续补完整几何轨迹及真实运行时接线。正式资产、训练和事项关闭均未授权。
