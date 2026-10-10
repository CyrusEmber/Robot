# 运行时事实（训练/冒烟/调度脚本时读这里）

验证过的框架事实，任务配置本身用不到，写训练周边脚本（冒烟/调度/曲线导出）时按需读取。
全部与机器人无关（机器人专属验证脚本速查见文末节，实例路径以 FILEMAP.md 为准）。

## 训练 log 目录（train.py）

- **命名 `{timestamp}_{run_name}`**：`--run_name tag` 后目录形如
  `logs/rsl_rl/<experiment_name>/2026-08-28_14-08-22_tag`。
  按 tag 找目录用**后缀**匹配 `endswith("_{tag}")` 取 mtime 最新；前缀匹配永远落空。
  **tag 不可互为后缀**（"base" vs "my_base" 无法区分）。
- **每个 run 自动 dump `params/env.yaml` + `params/agent.yaml`**——训练参数的运行时真值
  免费存档，版本 NOTES 直接引用。

## gym API

- **裸 `ManagerBasedRLEnv.step` 返回 5 元组**（obs, reward, terminated, truncated, info）；
  `RslRlVecEnvWrapper` 包过后才是 4 元组。冒烟脚本注意解包数。
- `env.reset()` 返回 2 元组 (obs, extras)。

## checkpoint

- **文件名按字典序排**：`model_9950.pt` 排在 `model_14999.pt` 之后——"取最终模型"
  按数字，别按文件名。
- `get_checkpoint_path(log_root, load_run, load_checkpoint)` 取"最新 run"——多任务族共用
  experiment_name 时可能取到别族的模型。

## configclass 单例安全（源码验证）

`configclass` 把 `__post_init__` 包成
`_combined_function(用户__post_init__, _custom_post_init)`——用户逻辑先跑，随后
`_custom_post_init` 对**所有成员整体 deepcopy**。推论：

- `__post_init__` 里把模块级 cfg 单例（如地形生成器快照）赋给实例属性是安全的：
  实例拿到独立副本，PLAY 改属性不污染模块单例，同进程多实例互不影响
- 代价：实例化时整树 deepcopy，略慢

## data 属性返回 ProxyArray

本 fork 所有 `robot.data.<field>` / `sensor.data.<field>` 返回 `ProxyArray`——取 torch
张量用 `.torch`（隐式 tensor 操作带弃用警告）；快照要 `.torch.clone()`。
常用：`root_pos_w` / `root_lin_vel_b` / `root_lin_vel_w` / `root_ang_vel_w` /
`projected_gravity_b` / `joint_pos` / `joint_vel` / `joint_pos_target` /
`joint_stiffness` / `joint_damping`（后两个是 DR 后的实时值）、
`write_root_velocity_to_sim(velocity)`（6 维 lin+ang，世界系）。

## 曲线导出

`tools\trainlog\dump_tb.py`：TB 事件 → csv（iteration, tag, value 长表）。
`python <robot>_exp\tools\trainlog\dump_tb.py --log_dir <run目录> --out <csv>`；
`--list_tags` 先看可用 tag，`--tag_filter` 过滤。
（lizard 实测：旧 run 39237 点 / 29 tags，`Curriculum/terrain_levels` 终值与历史记录吻合）

## 私有成员依赖清单（fork 版本升级即碎，改前先验证）

以下赌了 IsaacLab 内部实现（均有注释标注），**升级 IsaacLab fork 前必须逐条验证**：

- `teacher_mdp.py` 用 `asset._physics_sim_view` 建 rigid-body view（框架 events.py 同款
  workaround，有先例但仍是私有）
- `teacher_mdp.py` 的 `FootContactNormalsTerm` 读 `RayCaster.meshes` 类变量 + 直接调
  `raycast_mesh_masked_kernel`（未导出的 warp 内核；两条都在 `framework_pin_check.py`
  的 `NEEDLES` 里，被机器看守）

（lizard2 之前的清单里还有 `staged_curriculum.py` 的两条——写 `action_term._scale`、赌
curriculum manager 把 `cfg.func` 换成 term 实例。该文件与使用它的课程线已于 2026-10-09
随 `lizard/main` 退休删除，条目也随之从 `framework_pin_check.py` 移除。）

配套纪律：IsaacLab fork 版本升级 = 单独一次提交。先跑
`tools\verify\framework_pin_check.py`（把上面三条 + 其余内部依赖做成机器检查：
grep 源码树符号 + 比对已验证 commit `28a37ce`），再跑 `run_offline_checks.bat`
全套闸门 + 全部冒烟脚本，全绿才继续。

## 环境验证脚本速查（改完 env / 资产 / 参数后跑哪个）

以下为 lizard 实例脚本（别的机器人照此模式建自己的），已按类归档在
`<robot>_exp\tools\{verify,diagnose,trainlog}\`，命令从 IsaacLab 根目录执行，
默认 headless（不传 viz 旗标即可）；`--headless` 已弃用，需显式强制时用 `--viz none`。**判读标准是脚本存在的理由**——
输出对了才算环境健康，跑通不报错≠验证通过。

| 时机 | 脚本 | 预期输出（判读） |
|---|---|---|
| 起训前（env / 配方） | `tools\verify\baseline_probe.py` | 命令张量 / obs 组 / 奖励量级与配方一致；不给过就说明配方与运行态已经分家 |
| 资产布局 / 动作分配 | `tools\verify\check_joint_layout.py` | 关节名序与 `joint_order` 一致；动作维数=布局声明的维数 |
| 复位契约 | `tools\verify\reset_check.py` | 全量复位与子集复位后状态逐位一致 |
| 接触归属 | `tools\verify\check_contact_ownership.py` | 每个受罚 body 有 collider、每个接触 body 有对应惩罚项或是脚 |
| 想肉眼确认 | `tools\verify\view_terrain.py`（默认平地） | GUI 持默认位姿不塌 |
| 站姿 / 轴心疑虑 | `tools\diagnose\debug_pose.py` | 各 body 相对 base 坐标符合设计（头在前、四脚对称、尾在后） |
| obs 出 NaN | `tools\diagnose\diagnose_nan.py` | 定位哪个 term 产生 NaN |
| 版本记录 | `tools\trainlog\dump_tb.py`（上节） | csv 行数与迭代数同量级 |

（2026-10-09 前这张表里还有 `teacher_smoke.py` / `smoke_test.py` / `position_check.py` /
`pose_check.py` / `joint_check.py`——随 `lizard/main` 退休删除，入口改由上面这些仍注册的任务
上能跑的脚本承担。）

要点：
- 动作维度**永远写 `env.unwrapped.action_manager.total_action_dim`**，
  不硬编码数字（lizard 曾因硬编码 16 对 26 崩过）
- body 名以 `robot.data.body_names` 为准再 `.index()`，不凭记忆写名字
  （lizard 曾因旧命名 `lf_FOOT` 对 `lf_foot` 崩过）
- PLAY cfg（无 DR）跑静态验证；带 DR 的跑训练侧验证——别混
