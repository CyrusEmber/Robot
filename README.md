# Lizard2 机器人强化学习

Windows 上先按 [本机路径示例](paths.example.yaml) 填写 `paths.yaml`。其中 `python` 指向已安装 Isaac Lab、Isaac Sim 和 RSL-RL 的解释器。也可以用 `RL_PYTHON` 指定同一个解释器。

1. **定义机体**。在 [圆足机体](rl_exp/robots/lizard2_round_feet.py) 定义资产、动作关节顺序和默认 PD。
2. **定义实验**。在 [v7 实验](rl_exp/lizard2_v7.py) 选机体，配置观测、动作、奖励、终止、随机化和 PPO。试新想法可以直接复制这个实验文件改参数。
3. **训练**。运行 `.\train.cmd --exp rl_exp/lizard2_v7.py --viz none`。训练接受工作区改动，默认训完跑 robust 评测和九宫格。每个 Run 在 `rl_exp/out/train/` 下独立保存生效配置、Git 差异、接口签名、权重和 TensorBoard。
4. **评测和看片**。运行 `.\eval.cmd --ckpt <Run/model_5999.pt> --protocol locomotion_eval_v3`。打开输出目录中的 `metrics/eval.json` 和 `video/plane_overview.mp4`。历史 v7 权重旁需要保留 `model_5999.pt.interface.json`，命令再加 `--exp rl_exp/lizard2_v7.py`。手动评测可选 `--mode nominal`。

评测执行工作区的实验文件。文件与 Run 副本有差异时，`eval.cmd` 会提示，指标和录像也会记录实际来源。有 Run 资产摘要时，指定 `--exp` 仍会校验资产。

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

专项诊断有[圆足接口探针](rl_exp/tools/diagnose/lizard2_round_feet_probe.py)和[腿部回放探针](rl_exp/tools/diagnose/lizard2_shank_use_probe.py)。旧配方、版本和配方诊断从 `archive/pre-refactor` 检出后复跑。
