# 运行时事实（训练/冒烟/调度脚本时读这里）

验证过的框架事实，任务配置本身用不到，写训练周边脚本（冒烟/调度/曲线导出）时按需读取。
全部与机器人无关。

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

各 exp 目录的 `dump_tb.py`：TB 事件 → csv（iteration, tag, value 长表）。
`python <robot>_exp\dump_tb.py --log_dir <run目录> --out <csv>`；
`--list_tags` 先看可用 tag，`--tag_filter` 过滤。
（lizard 实测：旧 run 39237 点 / 29 tags，`Curriculum/terrain_levels` 终值与历史记录吻合）
