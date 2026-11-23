# Lizard2 机器人强化学习

Windows 上先按 [本机路径示例](paths.example.yaml) 填写 `paths.yaml`。其中 `python` 指向已安装 Isaac Lab、Isaac Sim 和 RSL-RL 的解释器。也可以用 `RL_PYTHON` 指定同一个解释器。

1. **定义机体**。在 `rl_exp/robots/lizard2_round_feet.py` 定义圆足资产、动作关节顺序和默认 PD。
2. **定义实验**。在 `rl_exp/lizard2_v7.py` 选机体，配置观测、动作、奖励、终止、随机化和 PPO。试新想法可以直接复制这个实验文件改参数。
3. **训练**。运行 `.\train.cmd --exp rl_exp/lizard2_v7.py --viz none`。训练接受工作区改动，默认训完跑 robust 评测和九宫格。每个 Run 在 `rl_exp/out/train/` 下独立保存生效配置、Git 差异、接口签名、权重和 TensorBoard。
4. **评测和看片**。运行 `.\eval.cmd --ckpt <Run/model_5999.pt> --protocol locomotion_eval_v3`。打开输出目录中的 `metrics/eval.json` 和 `video/plane_overview.mp4`。历史 v7 权重旁需要保留 `model_5999.pt.interface.json`，命令再加 `--exp rl_exp/lizard2_v7.py`。手动评测可选 `--mode nominal`。见 [评测格式](ablation_harness/HARNESS.md)。

评测执行工作区的实验文件。文件与 Run 副本有差异时，`eval.cmd` 会提示，指标和录像也会记录实际来源。有 Run 资产摘要时，指定 `--exp` 仍会校验资产。

精确复读旧 Run 时，在工作区恢复 `provenance.json` 记录的 Git HEAD，应用 `git.diff`，将 Run 中 `source/` 和实验副本按原路径放回。Isaac Lab 有本地改动时，按记录中的框架 HEAD 恢复并应用 `isaaclab.diff`。用 `resolved_cfg.yaml` 查看当时生效的参数。采用基线后，记录源码 tag、可取的资产和权重位置。

普通试验只留 Run。交接写一张 [待办](work/)，完成即删除。重大决定写一份 [验收记录](acceptance/records/)。旧配方和旧版本从 `archive/pre-refactor` 检出后复跑。
