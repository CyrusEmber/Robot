# v8 —— 资产解剖学转正 + 全关节重命名（球头 +X；chest/neck/tail1-3）

- 目的/假设: v6 判废根因 = rig 骨命名与解剖学 180° 装反（"neck1-3"=天线尾、
  "tail_yaw/tail_pitch"=球头颈、腿名前后左右全反），v6 把命名头转到任务 +X
  即把解剖学尾转上去，策略按奖励尾朝前走。v8 假设：资产再转 R_z(+180°)
  （对 pre-v6 blend 净 +90°，球头 −y→+x、天线尾→−x）+ 26 关节按解剖学重命名
  + 腿名换正（rl↔rf、lf↔rr）后，v6.2 奖励包（obs 381 / 动作 26 / DR / 地形 /
  网络）零改动即可产出球头朝前的步态。
- 相对 v6 的变更（reward/obs/DR/地形/网络/动作布局 **零变更**，纯资产+命名）:
  - **blend 刚体旋转 +180°**（`blender/rename_flip_v8.py` 一次性：27 骨 + 36
    mesh 锚点 1e-6 刚性自检 + mesh parent_bone 显式重挂 + 末态布局断言——球头
    link 世界 +X、天线 −X、前腿在前、左右腿各就各位）
  - **26 关节解剖学重命名**: rear_yaw/pitch→chest_yaw/pitch、tail_yaw/pitch→
    neck_yaw/pitch（球头颈）、neck1–3→tail1–3（天线尾）、腿 rl↔rf、lf↔rr
    （旧 rl=解剖学右前）。URDF 关节序随 Blender 骨集合重排（rf/lf 提前、尾链
    后移），joint_order 照抄新 URDF 实际序
  - **AXIS_MAP 轴同步**（180°: X/Y 取反）：haa/kfe `1 0 0`→`-1 0 0`、
    pitch/foot `0 -1 0`→`0 1 0`、yaw/hfe Z 不变（`generate_urdf.py`）
  - 全部版本 yaml 机械迁移（`tools/pipeline/migrate_joint_names_v8.py`：joint_order
    改名 + 脊柱正则 `rear_.*`→`chest_.*`、`tail_.*`→`tail[0-9]_.*`；root/v8 yaml
    joint_order = 新 URDF 实际序，满足 export_ue 序列断言）；`teacher_env_cfg.py`
    基类 `joint_pos_spine` 正则同步（旧任务 id 也加载当前资产，基类必须匹配新名）
  - 注册 `Lizard-Rough-v8` / `Lizard-Rough-Play-v8`（runner `lizard_rough_teacher_v8`）
  - URDF/STL/OBJ → convert_urdf → flatten 全链重跑（2.13MB usda，26 关节）；
    mesh 相对路径坑：importer 3.0 按 **URDF 所在目录** 解析，mesh 需同时放
    `versions/lizard/meshes/`（converter 输入位）与 `rl_exp/meshes/`（锁 SSOT 位）
  - 全版本 asset_lock 同 commit `--update-locks`（有意资产退役；v6 旧资产复现走
    git tag）
  - 校验工具: `teacher_smoke_v8.py`（obs 90/208/83 + spine 0.25 + SIR 落格）、
    `check_joints_v8.py`（**布局硬闸**：neck_pitch(球头) 必在 +X、tail3_pitch
    (天线) 必在 −X、前腿在前/左右各就位——v6 教训条目化）
- 版本纪律: v6 已训（8950 iters 判废）→ 训练启动锚不可逆，资产+命名换代影响
  配方行为 → 开 v8（versioning.mdc §A）。v7（ghost 断腿鲁棒性提案）保持占位，
  其"v6 ckpt 微调"前提失效，微调基座改指 v8。
- 训练命令:
  ```bat
  python scripts\reinforcement_learning\rsl_rl\train.py --task Lizard-Rough-v8 --max_iterations 15000 --seed 42
  ```
- log 目录: logs/rsl_rl/lizard_rough_teacher_v8/
- 验收: 同 v6 全部判据，**第 0 条升级**：GUI 回放肉眼确认**球头**朝前（不只
  是"头"朝前——以造型为准）+ `direction_probe.py`（默认已指 v8 最新 run）
  disp_head>0 复验。
- 结果回填: （训练后补：reward 曲线读数 / 反划脚 KPI 读数 / eval 跑分表 / 结论）
- 结论: （一句话，训练后补）
