---
name: isaaclab-train-probe
description: >
  训练中巡检：读取 Run 目录的 TensorBoard tfevents 输出进度、reward、终止与告警快照，不起仿真、秒级。
---

# 训练中巡检（tfevents 快照）

## 核心规则

1. **只读日志，不起仿真**：数据源是 Run 目录的 `events.out.tfevents.*`、`resolved_cfg.yaml` 与 `model_*.pt`。
2. **结论必须带数字**：引用探针输出的 last / 窗口均值与变化率，禁止模糊描述。
3. **WARN 逐条解释**：对 NaN、reward 骤降、事件停更、ckpt 落后给出解释或建议；停训/续训由用户拍板。

## 使用方法

- 现役新训练的 Run 默认位于 `rl_exp/out/train/<timestamp>_<id>/`（首次训练自动创建；历史旧权重位于 Isaac Lab 根下 `logs/rsl_rl/`）。
- 运行探针：
  ```
  <python> rl_exp/tools/trainlog/probe_run.py --run <run_dir> [--window 100] [--tags Loss,Policy]
  ```
- `<python>` 取 `paths.yaml` 中的 Isaac Lab 解释器（见 [README](../../../../README.md)）。
- 关注：无 NaN、reward 趋势、`Episode_Termination/*` 比例、`Policy/mean_std` 与 `Loss/entropy` 是否塌缩、iters/h 是否异常下降。
- 训练结束后的定量评测与看片使用 `.\eval.cmd`，见 [README](../../../../README.md#评测产物)。
