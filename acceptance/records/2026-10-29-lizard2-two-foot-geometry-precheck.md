# lizard2 对角支撑几何预查

## 适用范围

继续执行双足抬身事项，按用户要求分离通用目标求解、lizard2 工况生成与现有整机预查。此次仅验证离散几何候选，不运行物理、测量接触力或判定电机能力。初始姿态使用两组对角足支撑，非支撑足目标相对零位提高；尾部通过临时目标抬起以获得实际网格净空，不修改正式机体或驱动配置。

## 验收条件

- 复用 `body_precheck.py` 的实际 URDF、全部碰撞网格、限位、地面和全机实体配对。引用旧静站 manifest 的具名连接对和实际树中直接连接的有碰撞实体作为排除，报告明确记录；双轴新增载体会改变直接连接关系，不自动推断旧脚掌对仍应排除，也不视为已核运行时过滤。
- 每组支撑的两只非支撑足目标在参考零位上提高 0.04 m，尾首 pitch 设 0.1 rad；非支撑实体最小离地间隙设为 0.001 m 的本次几何筛查值，支撑脚允许最大 0.005 m 地面间隙或穿透。初始根高由两只支撑脚碰撞网格最低点确定，之后跟随指定升高幅度；不得以参考点代替完整网格检查。
- 支撑足目标保持位置及法向，0 至 0.05 m 区间等分为 11 个高度样本，逐点接续求解，位置容差 1e-4 m、单位法向向量距离容差 1e-3；仅为离散采样，节点通过不代表节点间路径通过。碰撞忽略已声明连接对，不证明其本身没有干涉。
- 定向测试使用真实 v6 机体，正常尾部几何通过后将尾首 pitch 改为 -0.1 rad，实际地面预查必须拒绝该穿地姿态。结果及原配置、各逐体间隙和配对保存于独立目录。

## 结果

正式 v6 的两组对角支撑，各 11 个高度样本的目标求解与全机限位、自碰撞和地面筛查均通过；抬起两足和尾部后，检查内非支撑实体达到本轮最小间隙。预查使用既有具名过滤及直接连接排除，未核实际运行时过滤；样本不覆盖连续轨迹、真实接触和力。

双轴候选两组对角支撑的端点求解完成，使用同一几何预查时，三个端点均在四组肘/膝与对应腕/踝连接对被判网格相交：`lf_elbow/lf_wrist`、`rf_elbow/rf_wrist`、`rl_knee/rl_ankle`、`rr_knee/rr_ankle`。新轴使这些实体之间插入无碰撞网格的载体，原本直接连接的实体不再是直接父子；这是可核的拓扑差异，不足以证明 PhysX 实际过滤或这些相交均合理。现保留失败，不添加排除，也不推断机体必然不可用。

先前尾部零目标样本的一组尾网格最小高度在地面附近，另一组有浮点尺度负值；两者都不足以证明明确离地。抬尾候选采用显式筛查净空，不把极小数值解释为实际接触力。三个定向测试通过，其中真实负例经实际全机预查拒绝尾部穿地。没有因候选相交失败改变过滤或开始物理试验。

## 证据引用

- 工作 `work/active/lizard2-two-foot-body-lift.md`；原方案 `acceptance/records/2026-10-29-lizard2-two-foot-body-lift-plan.md`；第一阶段 `acceptance/records/2026-10-29-lizard2-body-lift-geometry-start.md`。
- 工具 `rl_exp/tools/diagnose/pose_target_solver.py`、`lizard2_lift_geometry.py`、`lizard2_lift_precheck.py`；原通用检查 `rl_exp/tools/diagnose/body_precheck.py`；测试 `rl_exp/tools/verify/test_pose_target_solver.py`、`test_lizard2_lift_precheck.py`。本轮文件尚属本地在办，执行前应核实际版本。
- 本机 `rl_exp/out/lizard2_two_foot_body_lift/geometry02/`、`precheck01/` 保留初始尾零样本及失败；`geometry03/`、`precheck02/` 保留抬尾四组端点；`geometry04/`、`precheck03/` 保留正式 v6 两组 11 点路径。每个 precheck 目录有完整 config.json 与 report.json，含网格摘要、样本、逐实体地面间隙与逐对碰撞结果；本机输出不承诺入仓。
- 从仓根复读：`E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/diagnose/lizard2_lift_geometry.py --urdf rl_exp/lizard2_palm_spatial/lizard2_palm_spatial.urdf --support lf-rr --tail_pitch 0.1 --samples 11 --out <全新报告路径>`；将输出及 `rl_exp/out/lizard2_b_standing_force_20261022_run02/standing_manifest.json` 分别传 `lizard2_lift_precheck.py --ik ... --manifest ... --out_dir <全新目录>`。另一对角用 `rf-rl`；候选需指定候选 URDF。
- 定向测试：`E:/IsaacLab/env_isaaclab/Scripts/python.exe -B -m unittest rl_exp.tools.verify.test_pose_target_solver rl_exp.tools.verify.test_lizard2_lift_precheck`。

## 未覆盖边界

无法由静态几何推断落地接触、受力、机身抬升能力、实际驱动余量或控制器稳定。候选新的惯量及轴定义未复验；其失败连接对尚无独立归属及运行时过滤证据。测试使用模型 FK 与目标求解共用的数据，缺少独立运动学对拍。有限点和连接排除不能证明连续路径、实际安全或完整运动范围；夹具、传感、物理停止条件和对应试验依然待实施。
