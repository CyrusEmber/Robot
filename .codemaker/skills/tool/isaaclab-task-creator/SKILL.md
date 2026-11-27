---
name: isaaclab-task-creator
description: >
  在 E:\Robot 中新建或修改独立强化学习实验（exp.py）与机体定义（robots/<body.py>）。
  当用户提到“新建实验”、“改奖励权重”、“改观测/动作/终止/DR”、“新建或更换机体”、
  “调整 PPO 超参”等需求时使用此 skill。
  URDF→USD 资产处理用 isaaclab-asset-pipeline；评测用 isaaclab-eval-harness。
---

# 独立实验与机体定义

现役工作流已退网旧版 Gym 注册、YAML 参数版本与配方锁。完整入口见仓库 [README](../../../../README.md)。

## 职责分离（两个核心文件）

| 文件 | 职责 | 何时修改 |
|---|---|---|
| `robots/<body.py>` | 机体物理定义：`USD_PATH`、`URDF_PATH`、`ROOT_BODY_PRIM`、`BELLY_BODY`、`CHEST_BODY`、`HEAD_BODY`、`HEAD_BODY_PRIM`、`NOMINAL_WEIGHT_N`、`LEG_ACTION_JOINTS`、`SPINE_ACTION_JOINTS`、`ACTION_JOINTS`、`ACTION_SCALE`、`ACTION_CLIP`、`make_robot_cfg()` | 换资产、改关节布局、改默认 PD/摩擦/动作缩放、改部位 link 名 |
| `rl_exp/<exp>.py` | 实验定义：绑定 `ROBOT = <body_module>`，提供 `make_env_cfg(play=False)`（调用时从 `ROBOT` 绑定场景/动作/传感器/奖励/终止）与 `make_runner_cfg()` | 改奖励权重、观测、命令范围、终止策略、随机化、PPO 超参 |

可复用的奖励与终止项放 `locomotion/rewards.py` 与 `locomotion/terminations.py`。

## 日常操作

1. **试新奖励/超参**：直接复制 `experiments/lizard2/flat_v7.py` 改参数，运行：
   `.\train.cmd --exp rl_exp/<your_exp>.py --viz none`
   - 只训练，不串接评测；训完手动跑 `eval.cmd`。
   - 无需注册任务、无需清理工作区、无需手写版本文档。
   - Run 自动在 `rl_exp/out/train/`（首次训练自动创建）下记录 `resolved_cfg.yaml`、`provenance.json`、`git.diff`、`interface_signature.json`、权重和 TensorBoard。
2. **改机体**：只改 `robots/<body.py>`，实验里保持 `ROBOT = <body_module>` 并在 `make_env_cfg()` 调用期读取 `ROBOT` 属性，不在模块导入期静态绑定。
3. **评测与防漂移**：运行 `.\eval.cmd --ckpt <Run/model_N.pt> --protocol locomotion_eval_v3`。
   - 造环境前会用训练口径比对 `resolved_cfg.yaml` 中的 `scene.robot`、`actions`、`observations`、`sim.dt`、`decimation` 与 `runner.clip_actions`；不一致默认拒绝，仅显式传 `--allow-drift` 才放行（`--exp` 不豁免漂移）。

## 框架硬事实（Isaac Lab 3.0 fork）

- `robot.data.*` / `sensor.data.*` 返回 `ProxyArray`，取 PyTorch 张量用 `.torch`，做快照用 `.torch.clone()`。
- 裸 `ManagerBasedRLEnv.step` 返回 5 元组，经 `RslRlVecEnvWrapper` 包装后返回 4 元组。
- `configclass` 实例化时会自动 deepcopy 成员，在 `make_env_cfg()` 内构造新实例彼此隔离。
- 历史旧配方与注册流程归档在 `archive/pre-refactor` tag，现役实验不再回退使用。
