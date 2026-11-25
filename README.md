# Lizard2 机器人强化学习

Windows 上先按 [本机路径示例](paths.example.yaml) 填写 `paths.yaml`。其中 `python` 指向已安装 Isaac Lab、Isaac Sim 和 RSL-RL 的解释器。也可以用 `RL_PYTHON` 指定同一个解释器。

1. **定义机体**。在 [圆足机体](rl_exp/robots/lizard2_round_feet.py) 定义资产、身体部位、动作关节顺序、默认缩放/限幅和 PD。
2. **定义实验**。在 [v7 实验](rl_exp/lizard2_v7.py) 绑定 `ROBOT = lizard2_round_feet`，配置观测、动作、奖励、终止、随机化和 PPO。试新想法直接复制实验文件改参数即可；改机体只改机体模块。
3. **训练**。运行 `.\train.cmd --exp rl_exp/lizard2_v7.py --viz none`。默认只训练（加 `--eval` 才在训后自动跑评测和九宫格；`--train-only` 作为已弃用空操作兼容别名保留，不改变默认纯训练行为）。训练接受工作区改动，每个 Run 在 `rl_exp/out/train/`（首次训练自动创建）下独立保存生效配置、Git 差异、接口签名、权重和 TensorBoard。
4. **评测和看片**。运行 `.\eval.cmd --ckpt <Run/model_5999.pt> --protocol locomotion_eval_v3`。打开输出目录中的 `metrics/eval.json` 和 `video/plane_overview.mp4`。历史 v7 权重旁需要保留 `model_5999.pt.interface.json`，命令再加 `--exp rl_exp/lizard2_v7.py`。手动评测可选 `--mode nominal`。

评测执行工作区的实验文件，并在造环境前把训练口径下的推理关键配置（`scene.robot`、`actions`、`observations`、`sim.dt`、`decimation`、`runner.clip_actions`、`runner.obs_groups`、`runner.actor`）与 Run 的 `resolved_cfg.yaml` 比对；有差异或新 Run 缺失 `resolved_cfg.yaml` 时默认拒绝，仅在显式传 `--allow-drift` 时放行并在 `eval.json` / `matrix.json` 记录实际来源（`--exp` 仅指定实验文件，不豁免漂移校验）。有 Run 资产摘要时，指定 `--exp` 仍会校验资产。历史权重无 `provenance.json` / `resolved_cfg.yaml` 时记录配置比对不可用。

精确复读旧 Run 时，在工作区恢复 `provenance.json` 记录的 Git HEAD，应用 `git.diff`，将 Run 中 `source/` 和实验副本按原路径放回。Isaac Lab 有本地改动时，按记录中的框架 HEAD 恢复并应用 `isaaclab.diff`。用 `resolved_cfg.yaml` 查看当时生效的参数。

## 评测产物

- `metrics/eval.json` 保存实际工况、指标、有效样本和缺测。robust 另有扰动和恢复数据。[评测协议](ablation_harness/protocols/)定义采样和阈值，协议没有总通过阈值时，报告保留未定义。
- `video/matrix.json` 索引三档速度 × 三个视角的九段原片，`video/plane_overview.mp4` 是带标签的合成片。录像采用平地 nominal 工况，扰动与恢复在定量评测中测量。
- `metrics/` 和 `video/` 各有 `execution.json` 及日志，记录命令、时间和退出状态。看完指标和录像再决定下一步。

对照使用相同的权重、协议、seed、框架和采样口径。

## 实验何时需要人写字

| 情况 | 人工记录 |
|---|---|
| 当天试完，普通失败或放弃 | 零手写文档、零强制提交。配置、代码差异、指标和视频由 Run 自行保存。 |
| 值得搜索的小教训 | 可用一次 Git 提交保留实际改动，提交消息写工况、观察和放弃原因。需要恢复参数时可 revert，以后用 `git log --grep` 找回。 |
| 未完，留给下次或交接 | 在 [work/](work/) 写一张 `<id>.md`，只写下一步、Run 路径和实际阻塞。做完删除，有重大结论时转成验收记录。 |
| 采纳基线或否决一条重要路线 | 在 [acceptance/records/](acceptance/records/) 写一份短记录，写改动目的、Run 与权重位置、关键指标与看片观察、决定与适用范围。采纳时给实际运行的源码提交打一个 tag，并确认资产和权重可取且能加载。 |

只写半年后丢了会让人走弯路的决定。代码差异和零散结果留给 Git 与 Run。

## 资产与接口检查

- [隔离候选转换](rl_exp/tools/diagnose/lizard2_two_axis_convert.py)用 `--candidate` 指定 `rl_exp/out/<事项>` 或 `%TEMP%` 下的 URDF，将 USD 写到同目录。[圆足 USD 检查](rl_exp/tools/diagnose/lizard2_round_feet_usd.py)核对碰撞、惯量和依赖：`--formal_dir rl_exp/lizard2_round_feet --output <仓外 JSON>` 只读核验正式资产；`--export_dir <候选目录> --repair <新 .usda>` 在隔离副本上修五处主轴惯量。
- 从仓根用 `paths.yaml` 指定的 Python 执行 `python -m pytest -q rl_exp/tools/verify/test_lizard2_round_feet.py rl_exp/locomotion/tests/test_v7_experiment.py`，检查圆足结构和现役实验配置。
- [圆足接口探针](rl_exp/tools/diagnose/lizard2_round_feet_probe.py)接受 `--task Lizard2-Flat-v7 --viz none --out <新目录>`，在已存在的父目录下保存关节、观测、首步和 reset 报告。`Lizard2-Flat-Play-v7` 选择 Play 配置。训评接线使用 `python -m pytest -m sim`。[腿部回放探针](rl_exp/tools/diagnose/lizard2_shank_use_probe.py)提供专项回放。

旧配方、版本、掌足预检和旧 Lizard 的 UE 导出已退网。按[退网清理记录](acceptance/records/2026-11-24-legacy-entrypoint-cleanup.md#恢复口径)核对逐文件的恢复来源和 SHA-256，来源包括 `archive/pre-refactor` tag、本机归档 `rl_exp/out/archive/pre-refactor/` 和删除前提交。圆足导出按当前仓根定位掌足 URDF 与网格、圆足骨架 `.blend` 与 `build.json`、两份上游 `.blend` 及双轴 JSON。源件迁入本机归档时沿用仓库相对路径，导出仍校验原始摘要。
