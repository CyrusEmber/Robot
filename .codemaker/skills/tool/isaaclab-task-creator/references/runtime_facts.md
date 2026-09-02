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

以下三处赌了 IsaacLab 内部实现（均有注释标注），**升级 IsaacLab fork 前必须逐条验证**：

- `staged_curriculum.py` 写 `action_term._scale`（公开 API 只有 cfg.scale）
- `teacher_mdp.py` 用 `asset._physics_sim_view`（框架 events.py 同款 workaround，
  有先例但仍是私有）
- `staged_curriculum.py` 的 `_dependency_met` 假设 curriculum manager 把
  `cfg.func` 换成 term 实例（赌 `stage_idx` 属性存在）

配套纪律：IsaacLab fork 版本升级 = 单独一次提交。先跑
`tools\verify\framework_pin_check.py`（把上面三条 + 其余内部依赖做成机器检查：
grep 源码树符号 + 比对已验证 commit `28a37ce`），再跑 `run_offline_checks.bat`
全套闸门 + 全部冒烟脚本，全绿才继续。

## 环境验证脚本速查（改完 env / 资产 / 参数后跑哪个）

以下为 lizard 实例脚本（别的机器人照此模式建自己的），已按类归档在
`<robot>_exp\tools\{verify,diagnose,trainlog}\`，命令从 IsaacLab 根目录执行，
全部支持 `--headless`。**判读标准是脚本存在的理由**——
输出对了才算环境健康，跑通不报错≠验证通过。

| 时机 | 脚本 | 预期输出（判读） |
|---|---|---|
| teacher env 改动后 | `tools\verify\teacher_smoke.py` | `OBS_SHAPE (2, 308)`（v2；v1 为 266）；`LAYOUT` 行按 term 名给出切片（与 FAMILY.md 布局表对账）；`ACTION_DIM 26`；`MASS_SUM ≈ 总质量`；`FOOT_FORCES_Z` 合计≈全重；`OBS_FINITE True` |
| 家族 env 改动后 | `tools\verify\smoke_test.py` | `OBS_DIM` 匹配布局；`STEPPED_OK True` |
| 资产/站姿/初始高度改动后 | `tools\verify\position_check.py`（`--rough` 切粗糙地形） | `JOINT_COUNT 26`；base z 轨迹沉降稳定不穿地不悬空；四脚 `force_z` 合计 ≈ 总重×9.8（全重落脚=站姿自洽）；`nan_free True` |
| 几何/命名疑虑 | `tools\verify\pose_check.py` | 各 body 相对 base 坐标符合设计（头在前、四脚对称、尾在后） |
| 想肉眼确认 | `tools\verify\view_terrain.py`（默认平地；`--task Lizard-Rough-Play-vN` 看版本地形） | GUI 持默认位姿不塌 |
| 关节加载疑虑 | `tools\verify\joint_check.py` / `tools\diagnose\debug_pose.py` | 关节角=默认位姿 / 轴心世界坐标符合 URDF |
| obs 出 NaN | `tools\diagnose\diagnose_nan.py` | 定位哪个 term 产生 NaN |
| 版本记录 | `tools\trainlog\dump_tb.py`（上节） | csv 行数与迭代数同量级 |

要点：
- 动作维度**永远写 `env.unwrapped.action_manager.total_action_dim`**，
  不硬编码数字（lizard 曾因硬编码 16 对 26 崩过）
- body 名以 `robot.data.body_names` 为准再 `.index()`，不凭记忆写名字
  （lizard 曾因旧命名 `lf_FOOT` 对 `lf_foot` 崩过）
- PLAY cfg（无 DR）跑静态验证；带 DR 的跑训练侧验证——别混
