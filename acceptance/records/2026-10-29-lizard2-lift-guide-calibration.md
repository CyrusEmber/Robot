# lizard2 抬身导轨标定与首例参数

## 适用范围

用户要求继续物理夹具、接触力和电机负载试验，并分别观察脚掌、膝和肘。先以正式 v6 的左前＋右后对角支撑做隔离诊断；双轴候选的碰撞相交缺口仍按原事项保留。本记录截至执行前仅含夹具标定及首例固定参数，不代表机器人落地或抬身通过。

## 验收条件

导轨先经独立物体自由落体正反对照，再经空中整机对照；记录竖直约束力口径。机器人试验绑定实际资产及预查的两足姿态，50 Hz 目标、0.005 s 物理子步，5 s 立稳、2 s 抬高 0.02 m、保持 2 s、回落 2 s、恢复 2 s，至多一次 2600 步，墙钟 900 s；不按失败重试或扫描增益。

延用既有静站/抬腿诊断的单关节目标偏差 0.35 rad、下沉 0.15 m、关节速度达到读回限速一半、禁止部位对地力 5 N 停止线，并设导轨轴向传递力绝对值超过 5 N 或显式导轨驱动非零、非有限值及墙钟停止。静置末 1 s 两支撑足各平均法向力须不小于 5 N，否则停止后续抬身。5 N 仅为诊断停止线，不是硬件或证据精度标准。任一硬停止保存全部已采样数据，不推测未执行动作。

逐子步记录地面过滤力、实际角度/速度、位置目标、关节六维传递 wrench 与轴投影、显式力输入和基座姿态；导轨原始传递力需核坐标与零驱动，步平均轴向载荷的驱动归因仍需复读。按受载期共同动作报告，不能据相关性宣称某关节独立可抬身或精确力矩余量。

## 结果

独立 2 kg 物体在横向与竖直重力作用下，导轨自由落体的竖直加速度与自由对照一致、横向受限；由加速度差反推的轴向约束力接近零。将导轨改成固定关节的真实负例被拒，反推竖直约束力约 19.62 N；无接地。首次启动仅因导入路径错误在建场前失败，修正后正反例均保留。

直接将世界—机器人根关节替换成移动关节的整机试验被 PhysX 作为固定基座处理，空中质心反推竖直支撑接近整机重量，不能使用。增加一个世界固定的无碰撞载体，并在载体与真实 base_link 之间增加无驱动的竖直关节后，空中 0.2 s 的机器人质心竖直加速度约 -9.81 m/s²，反推导轨竖直力约 0.0001 N；新增固定载体质量从机器人质心计算中排除。基座 incoming wrench、导轨显式驱动力有原始采样；这只是有限空中标定，不能替代受载力平衡、力通道坐标/其他贡献审核。

本记录登记首例参数；该例的实际结果另记，不把本标定写作抬身能力通过。

## 证据引用

- 原工作 `work/active/lizard2-two-foot-body-lift.md` 与方案 `acceptance/records/2026-10-29-lizard2-two-foot-body-lift-plan.md`；有限几何与失败见 `acceptance/records/2026-10-29-lizard2-two-foot-geometry-precheck.md`。
- 独立体标定 `rl_exp/tools/diagnose/lift_guide_calibration.py`：本机 `rl_exp/out/lizard2_two_foot_body_lift/guide_calibration03/report.json` 与 `guide_calibration_negative01/report.json`；输入 `--viz none --device cuda:0 --out <新报告>`，负例另加 `--break_test`。
- 导轨资产生成 `rl_exp/tools/diagnose/lift_guide_asset.py`；本机载体资产 `rl_exp/out/lizard2_two_foot_body_lift/guide_asset03/lizard2_guided.usda`。无载体失败 `guide_robot_probe01/report.json`，有载体标定 `guide_robot_probe03/report.json`；入口 `lift_guide_robot_probe.py`。
- 机器人首例入口 `rl_exp/tools/diagnose/lift_guided_trial.py`，绑定 `geometry04/v6-lf-rr.json` 和 `precheck_midpoints01/v6-lf-rr/report.json`；后者含离散节点和关节线性中点。输入与输出皆在 `rl_exp/out/lizard2_two_foot_body_lift/`，不承诺入仓。

## 未覆盖边界

单体和空中整机标定不证明受载夹具反力可靠、真实脚部接触、膝肘/腕踝负载能力、路径连续安全或学习策略表现。真实硬件额定扭矩与动力性能未验证。双轴候选连接相交和惯量缺口仍在办，不由此校准自动解除。
