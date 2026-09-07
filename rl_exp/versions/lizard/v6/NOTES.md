# v6 —— 资产前向轴转正（头 +Y → +X，reward/obs 逐字同 v5）

- 目的/假设: v5 首跑（~2000+ iters，2026-09-07 eval 在案）GUI 回放**横着走**
  （crab-walk）。根因不在 v5 奖励包——在资产坐标系：URDF 长轴 = **Y**
  （neck1 y=+1.0696、tail y=-1.2613、左右腿沿 x 分布，`versions/lizard/lizard.urdf`），
  而速度任务全链路按 IsaacLab 惯例给 **base +X** 付钱（`teacher_mdp.py
  track_lin_vel_xy_lin` 的 yaw 对齐系投影 + `lin_vel_x (0,3)` 命令）。policy 被
  付钱沿自身**右侧**横移 0–3 m/s，且学得很好——`track_lin_vel_xy_lin` 爬到
  0.4+，训练曲线"健康"，横行恰恰是按 spec 的最优解。v3/v4 原地划脚不位移，
  轴错配从未显形；v5 反划脚包让"真位移"首次成为唯一正收益路径，症状才暴露
  （FAMILY 机体几何备忘其实早记了"长轴 = Y"，无人对到任务约定）。假设：轴转正后
  v5 奖励包无需任何改动即可产出朝头方向的前进步态。
- 相对 v5 的变更（obs 381 / reward / DR / 地形 / 网络 **零变更**，yaml 逐字相同）:
  - **资产刚体旋转 R_z(-90°)**：blend SSOT 整体转（头 +y→+x，lf 落正确左侧）——
    `blender/rotate_rig.py`（27 骨 + 36 mesh 锚点 1e-6 刚性自检；**不烘焙**：
    transform_apply 过 bone-roll 往返有浮点漂移，旋转保留为臂架对象变换，
    generate_urdf 改读世界系骨位）
  - **AXIS_MAP 轴同步旋转**（世界功能轴）：haa Y→X、kfe Y→X、pitch X→-Y、
    foot X→-Y、hfe Z 不变、yaw Z 不变（`generate_urdf.py`）
  - `fix_bones.py` 坐标系修正（世界↔臂架显式转换）+ foot 桩外展方向 X→Y
  - URDF 重生成 → STL→OBJ → convert_urdf → flatten 全链重跑；usda 自包含
    （0 外部引用）
  - 全版本 asset_lock 同 commit `--update-locks`（有意资产退役；旧资产复现走
    git tag）
- 版本纪律: v5 已开训 → 训练启动锚不可逆（versioning.mdc §A 状态机），资产换代
  影响配方行为 → **开 v6**，非 v5.M 修订。v5 旧 run（logs/rsl_rl/
  lizard_rough_teacher_v5/）判废保留：横行证据 + v5 奖教会了位移"的
  反向证明。
- 装配验证（2026-09-07）: usda 26 关节/2.1MB/fvi 40/pcapi 18；joint_check 26×
  0.000；debug_pose 去 yaw 后 pivot 与 R·旧值一致（lf (0.596,0.321)、rr
  (-0.481,-0.358)）、四腿对称 rel_z 一致；position_check 落地 z=0.962 稳定无
  震荡、四脚 677N ≈ 体重（单脚偏差 <30%）、无 NaN；`teacher_smoke_v6.py` 全绿
  （obs 90/208/83、forward-only、SIR TRAIN 落格 stepped）；offline 闸门全绿
  （PARITY_OK 含 v6 锁）。
- 训练命令:
  ```bat
  python scripts\reinforcement_learning\rsl_rl\train.py --task Lizard-Rough-v6 --max_iterations 15000 --seed 42
  ```
- log 目录: logs/rsl_rl/lizard_rough_teacher_v6/
- 验收: 同 v5 全部判据（反划脚 KPI），**新增第 0 条**：GUI 回放肉眼确认前进
  方向 = 头朝向（横行消失）。
- 结果回填: （训练后补：reward 曲线读数 / 反划脚 KPI 读数 / eval 跑分表 / 结论）
- 结论: （一句话，训练后补）
