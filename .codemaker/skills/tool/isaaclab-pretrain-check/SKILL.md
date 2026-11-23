---
name: isaaclab-pretrain-check
description: >
  开训前检查实验配置、机体绑定与地形（或查阅旧配方地形预检归档）。
---

# 开训前检查

现役独立实验（如 `rl_exp/lizard2_v7.py`）使用显式 `ROBOT` 模块和 `make_env_cfg()`，入口见仓库 [README](../../../../README.md)。

1. **配置与绑定离线检查**：在仓库根目录运行 `pytest`，验证 `rl_exp/locomotion/tests`、`rl_exp/tools/verify`、`rl_exp/tools/diagnose` 全部通过（含 `exp.ROBOT` 绑定、观测/动作接口签名和资产摘要检查）。
2. **短训冒烟**：运行 `.\train.cmd --exp rl_exp/<exp>.py --num-envs 4 --max-iterations 1 --viz none`，确认 Run 目录（默认落盘在首次训练自动创建的 `rl_exp/out/train/`）正常产出 `resolved_cfg.yaml`、`provenance.json`、`interface_signature.json` 和 `model_0.pt`。
3. **复杂粗糙地形预检**：历史参数网格地形预检脚本（`terrain_preflight.py` / `view_terrain.py`）服务已退网的旧配方，如需复查旧流程请从 `archive/pre-refactor` tag 检出。
