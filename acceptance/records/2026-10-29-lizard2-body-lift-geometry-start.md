# lizard2 抬身几何准备：通用目标求解与四足端点

## 适用范围

用户要求开始执行两足承重抬身测试，并要求实现适度通用、解耦。本阶段将通用关节限位内的链接目标求解与 lizard2 工况适配分开，复用仓库已有 URDF 树和 FK。只做离线四足端点几何准备；没有运行物理、双足支撑、碰撞或完整路径检查。

## 验收条件

通用求解器由调用者显式提供模型、完整初始关节、可动关节、链接局部点及目标、可选法向和容差；不硬编码腿数或特定机体。拒绝与复用 FK 不兼容的关节类型、关节原点旋转、非法限位及错误目标；无解或未收敛须返回未通过而非宣称物理不可达。真实机体适配器单独提供足端及抬高目标，结果只用于进一步预查。测试需要验证目标运动、冻结关节、不可满足目标和输入拒错。

## 结果

`pose_target_solver.py` 提供有界点与法向求解，`lizard2_lift_geometry.py` 从实际碰撞网格底部采样脚掌参考点，并针对两个机体生成四足端点候选。正式 v6 的20个腿关节、隔离候选的24个腿关节分别进入求解；四足参考点在机体根系中下降2 cm 和5 cm 时，两机体各足的位置及法向目标残差均小于相应设定容差（1e-4 m、1e-3 单位向量距离）。各实例足点初始高度接近，但参考点并非完整接触面。

两个定向单元测试通过，覆盖真实左肘的目标可达与其他关节保持、不可满足的远距离目标及非法法向拒绝。端点求解器与判据共用同一 FK，测试不构成独立模型校验；本结果不证明世界坐标落脚不滑移、尾部净空、碰撞安全、全路径连续、夹具性能或驱动承载。候选资产和诊断代码仍为本机未提交的在办内容，复读依赖实际文件存在。

## 证据引用

- 工作事项 `work/active/lizard2-two-foot-body-lift.md`，测试范围 `acceptance/records/2026-10-29-lizard2-two-foot-body-lift-plan.md`。
- 通用几何求解 `rl_exp/tools/diagnose/pose_target_solver.py`；机体适配 `rl_exp/tools/diagnose/lizard2_lift_geometry.py`；针对性测试 `rl_exp/tools/verify/test_pose_target_solver.py`。
- 本机原始输出 `rl_exp/out/lizard2_two_foot_body_lift/geometry01/v6.json` 与 `candidate.json`；输出包含 URDF 摘要、完整关节结果和逐足残差，不承诺数据入仓。候选 URDF 来自 `rl_exp/out/lizard2_two_axis_20261029/candidate01/lizard2_two_axis.urdf`。
- 从仓根复读需指定不存在的新输出路径：`E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/diagnose/lizard2_lift_geometry.py --urdf <URDF> --out <新报告>`；测试 `E:/IsaacLab/env_isaaclab/Scripts/python.exe -B -m unittest rl_exp.tools.verify.test_pose_target_solver`。

## 未覆盖边界

没有双足接触安排、非支撑脚或尾部离地目标，也没有动力学、加载、导向约束、真实力矩或控制闭环。候选惯量与两轴语义仍须原机体事项核实。需在继续实施时补充实际资源预算、停止条件、动作权限、完整路径与 `body_precheck.py` 全机预查；不以本结果启动或认定物理测试通过。
