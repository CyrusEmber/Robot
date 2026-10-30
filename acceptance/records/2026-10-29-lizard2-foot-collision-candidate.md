# lizard2 双轴脚掌连接碰撞形状试修

## 适用范围

用户要求先修复双轴候选脚掌与下腿连接处的相交配置，明确不应直接把相交当作正常。只生成隔离碰撞形状试作，不修改正式资产、原候选、视觉网格、关节结构或驱动。该记录为失败和有限通过的执行证据，不是正式配置或机体采用。

## 验收条件

- 不通过扩大自碰撞排除掩盖相交；用实际碰撞网格对四组下肢与脚掌连接逐对检查，绑定输入、完整样本和产物。使用相同检测算法和相同有限轴角，保留修前失败、修后结果。
- 保留可视网格、URDF、脚底最低点及其它碰撞网格；按脚掌局部关节枢轴截取碰撞凸包，截面仅是诊断值，不视作经批准的真实脚掌机械形状。脚底最低点一致不等同完整脚底材料点、实际摩擦和接触动力学一致。
- 用两组对角姿态预查检查限位、地面和全机未排除配对；单独检查中立及两轴正负非零角，失败不得报告修复完成。独立 FK、连续范围、双轴组合、动力学和碰撞表示转换不在本轮覆盖内。

## 结果

原双轴碰撞脚掌在局部枢轴上方约 0.030783 m 仍有几何；下腿下端与脚掌在连接区的网格被判相交。隔离候选将四个脚掌的碰撞凸包截到枢轴下方 0.005 m；四足局部最低点与原始一致。该操作改变碰撞外形，未证明视觉/机械形状与接触等价。

两组对角支撑各 11 个有限采样姿态，在原连接过滤之外的整机预查均通过。进一步单独检查每足原轴与新增轴各 ±0.2 rad：原候选 20/20 个样本失败；隔离候选中立及部分侧翻方向通过，但仍有 12/20 个样本相交。故试修**未完成**，不能采用此候选、不能推断全运动范围已修，也不以中立通过代替非零运动验证。失败原因尚未分离脚掌与下肢何者需改，不能单方面继续压缩脚掌或删去大段碰撞几何追求通过。

## 证据引用

- 活跃事项 `work/active/lizard2-two-foot-body-lift.md`、原预查 `acceptance/records/2026-10-29-lizard2-two-foot-geometry-precheck.md`。
- 试作入口 `rl_exp/tools/diagnose/lizard2_foot_collision_candidate.py`，有限单轴对照入口 `rl_exp/tools/diagnose/lizard2_foot_collision_sweep.py`；共用 `body_precheck.py`、`pose_target_solver.py`。本轮入口为本机在办文件，尚未完成提交。
- 隔离输出 `rl_exp/out/lizard2_two_foot_body_lift/collision_candidate01/`，记录脚掌源和候选摘要；`collision_geometry01/`、`collision_precheck01/` 为两组对角姿态；`collision_sweep01/old.json` 与 `new.json` 为相同有限姿态修前、修后逐对记录。工件为本机文件，不承诺入仓。
- 从仓根复读需全新输出：`E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/diagnose/lizard2_foot_collision_candidate.py --urdf rl_exp/out/lizard2_two_axis_20261029/candidate01/lizard2_two_axis.urdf --out_dir <全新目录> --ceiling -0.005`；使用 `lizard2_foot_collision_sweep.py --urdf <原或新URDF> --out <全新报告>` 复现各自单轴样本。

## 未覆盖边界

尚未确认实际机械结构及连接区应有的碰撞形状，未对当前试作进行 USD 重新导入、PhysX 对拍、承载/滑移、完整脚底接触面、非零双轴组合、全 ROM 或连续轨迹验证。不得使用它进行正式训练或作为受载抬身通过证据。下一步须先分析非零角相交区域和脚底/下腿几何影响，提出可验证的碰撞形状配置并复验，不新增忽略碰撞对来替代修复。
