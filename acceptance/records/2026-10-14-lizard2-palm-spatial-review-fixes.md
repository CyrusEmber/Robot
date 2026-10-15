# 肩髋三轴方案评审与定点修复

## 适用范围

用户要求先评审新的在办方案，随后确认执行本轮评审修复。关联重构事项、机体总项、限位 PD 专项及 S5/S6 交接。只修已复现的几何读点、旧求解器拒错与报告角色选择，补齐相位和策略决策施工要求；不是三轴完整候选实施、正式采用、训练或关闭审核。

## 验收条件

- 新链共中心 twist 不得被当作骨段或肘膝；几何读点对旧链、五轴链与旋转关节坐标系均有手算回归。
- 四轴历史求解器拒绝包含未消费 twist 的实际链；拒绝不留下可误读的成功报告。
- spatial 报告保留肘膝面板，不把 twist 当原肘膝；四种绑定经过同一真实报告验证和绘图消费者。
- 步态相位与五角色策略选择明确留给对应执行者，不擅定工程阈值、全部开放动作或修改旧目标/协议。

## 结果

### 评审发现

1. `check_leg_reachability.py` 的真实树读取支持 spatial，但旧 `straight_hfe`、`thigh_shank_angle` 用第三/第四位原点计算骨段，第三位 twist 共中心原点为零。实际检查点左前三个读点（含 `load_case_angles`）均复现 `ZeroDivisionError`。
2. `palm_gait_kinematics.Leg` 固定四轴直接拼接，接受实际五轴 URDF 却遗漏 twist。对实际左前腿注入 twist 10°，旧拼接结果与真实 FK 的腕部位置差 0.065627706 m、旋转矩阵最大元素差 0.161649347。专项 5a/5b 不能直接沿用此入口。
3. `plot_joints.report_tokens` 固定位置 2，spatial 前后肢选中 twist 而非 elbow/knee。此问题为报告语义迁移，不靠列集合完整即可发现。
4. 相位与策略交接是计划缺口：旧水平掌面样本本来声明为历史对照，不据此称新步态实现 bug；S5 需逐角色明确 twist 等动作开放/固定/阶段门控，诊断五角色可控不自动成为正式策略接口。

### 本轮修复

- 保留几何公开函数名字和签名，按 `hfe/elbow/knee` 定位真实关节、以 FK 枢轴识别非零上下段并在同一根坐标系计算。spatial 折叠工况选择 elbow/wrist 或 knee/ankle，旧命名与短链读点保留；任意非平面骨段是否能完全共线仍不承诺。
- 历史 `palm_gait_kinematics.Leg` 在拼接前核对真实父子链，包含未消费轴时明确拒绝。公共构造签名不变；5b 及旧接触诊断复用该拒错，不把补五元素数组当已完成新求解器。旧 5a 在输入验证成功前不创建输出目录。
- spatial 报告按明确 elbow/knee 角色选择三面板；旧报告面板与协议保持原义，twist 仍存在于完整五角色列集合，不强行改变历史报告布局。
- 所需真实链拒错和四种绑定报告回归折入现有 `test_baseline_contract.py`，没有新增闸门、依赖或正式版本。

### 回归与复读

解释器由 `python -B ablation_harness/host_paths.py --python` 解析为本机配置。下列命令从仓根运行：

```cmd
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/verify/check_leg_reachability.py --self-check
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/verify/check_leg_reachability.py --break-test
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/verify/test_baseline_contract.py --binding-only
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/verify/test_baseline_contract.py
```

修复前先加入同一持久回归：几何回归在原实现触发零向量异常；报告回归断言得到 `(shoulder_swing, shoulder_twist, wrist)` 而失败；漏轴回归要求 `Leg` 拒绝五轴却被接受而失败。修复后定向几何自检/破坏测试通过，绑定报告与漏轴回归输出 `TARGET_BINDING_REPORT_OK`。几何逐函数回退原实现时同一回归分别抓到两个零向量异常及 spatial 折叠错位。

完整离线套件首轮复跑 37/37 通过，50.4 s，命令 `offline_suite.py --python E:/IsaacLab/env_isaaclab/Scripts/python.exe --jobs 4`。新增报告测试包含真实 `baseline_frames.save/load` 和判分 reader；绘图报告 writer 侧仍是 fixture，仅调用真实 `summarise`、验证及绘图 reader，不宣称 `gait_probe` 仿真采集已验。

不带执笔历史的新上下文核对本轮代码、测试和方案，结论为本轮范围通过，不能关闭整个 work；指出上段 rpy 不变量需更直接覆盖、非平面共线角语义需说明、绘图 writer 证据边界需点明。随后补上段不变断言及函数语义边界，保持真实 writer 未跑的限制。实际检查点四腿几何读点复验：前腿 straight 约 -80.157526°，后腿约 -80.1649°；在相应肘膝角回代后骨段残差 1.06e-5～2.26e-5°，这是导出坐标/轴小数截断读数，不是机械精度或验收容差。首次临时探测采用 1e-5° 切线而失败，随后用 1e-4° 观察截断量级；未据此修改任何获准工程阈值，持久手算回归仍使用其原精度。四腿旧 `Leg` 均在真实 twist 链上明确拒绝。实际读点可用下列只读入口复读（打印读数，不设置设计通过阈值）：

```cmd
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B -c "import sys,pathlib,math; sys.path.insert(0,str(pathlib.Path('rl_exp/tools/verify').resolve())); import check_leg_reachability as r; p=pathlib.Path('rl_exp/out/lizard2_palm_spatial_20261014/checkpoint_v3/palm_spatial.urdf'); exec('for leg in r.joint_names.LEGS:\n c=r.load_chain(p,leg,r.joint_names.PALM_SPATIAL_NAMING)\n a=r.straight_hfe(c)\n q=[0.0]*len(c)\n q[next(i for i,j in enumerate(c) if j[\"token\"] in (\"elbow\",\"knee\"))]=a\n print(leg,math.degrees(a),r.thigh_shank_angle(c,q),r.load_case_angles(c,r.joint_names.PALM_SPATIAL_NAMING)[\"fold\"])')"
```

最终追加上段 rpy 不变断言后，自检、九项破坏测试、绑定报告和 work 检查均通过；四种命名原有数值判分和绘图读数一致。最终完整套件复跑 37/37 通过，45.4 s（wave 152 s 仅作信息，jobs=4）；命令与首轮相同。修订后另一不带执笔历史的新上下文复核代码、记录及四项交接，结论为本轮修复通过、无阻塞，不构成候选或 work 关闭验收。

## 证据引用

- 当前候选检查点：`acceptance/records/2026-10-14-lizard2-palm-spatial-trial-checkpoint.md`，实际输入 `rl_exp/out/lizard2_palm_spatial_20261014/checkpoint_v3/palm_spatial.urdf`。
- 几何实现及手算回归：`rl_exp/tools/verify/check_leg_reachability.py` 的 `_knee_geometry`、`_knee_geometry_check`、`load_case_angles`。
- 四轴真实链拒错：`rl_exp/tools/diagnose/palm_gait_kinematics.py:Leg`。
- 报告实现及跨绑定回归：`rl_exp/tools/diagnose/plot_joints.py:report_tokens`，`rl_exp/tools/verify/test_baseline_contract.py:test_target_binding_report_roundtrip`、`test_palm_solver_rejects_inserted_axis`。
- 相位目标与命令收口：`work/active/lizard2-restored-limits-pd-validation.md` 步骤 5；策略决策：`work/active/lizard2-family-landing.md` 正式配方接入。

## 未覆盖边界

本轮未实现五轴自然步态求解、逐相位输入或完整轨迹，不运行 Blender、USD/IsaacLab、承重或 PD 标定。旧水平掌面目标和历史报告没有改写；未跟踪的接触试作不属于本轮实现。独立几何采样与接口回归不能证明运行时安全、连续域、动力学或策略性能。重构、总项、专项与 S5/S6 仍保持在办，未请求或执行关闭。
