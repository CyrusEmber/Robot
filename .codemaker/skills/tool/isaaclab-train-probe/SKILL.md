---
name: isaaclab-train-probe
description: >
  IsaacLab 训练中巡检：一条命令读 tfevents 出训练健康快照（进度/reward 趋势/
  终止计数/课程值/iters-per-h+ETA/NaN 与骤降告警），不起仿真、秒级。
  当用户提到"probe"、"看下训练情况"、"训练巡检"、"训练进度检查"、"训练健康检查"、
  "训练怎么样了"、"train probe"、"check training"、"run 到哪了/还正常吗"等需求时使用此 skill。
  开训前地形检查用 isaaclab-pretrain-check；训完跑分评测用 isaaclab-eval-harness。
metadata:
  version: "1.0.0"
---

# IsaacLab 训练中巡检（tfevents 健康快照）

## 核心规则

1. **只读日志，不起仿真**：探针数据源是 run 目录的 tfevents + `params/agent.yaml` +
   `model_*.pt`；要跑 env 看行为属于 play/eval，不是本 skill。
2. **结论必须带数字**：引用探针输出的 last/win 均值与 Δ%，禁止"看起来挺稳"式结论。
3. **WARN 逐条判读**：探针给出的告警（NaN、reward 骤降、事件停更、ckpt 落后）必须
   逐条给出解释或处置建议，不允许无声跳过。
4. **判读标准对照版本 NOTES**：打开 `rl_exp/versions/<family>/<vN>/NOTES.md` 的
   验收线/启动前警示（如 v4：起步 ~100 iters 无 NaN / 非零 reward / 终止计数正常；
   卡排判据看 terrain_levels），对照着给"继续训 / 建议查 X"结论。
5. **不代替用户拍板**：给事实 + 建议，停训/续训用户定。

## 工作流程

### 第 1 步：定位 run

- 用户在训哪个版本 → 对应实验目录 `logs/rsl_rl/<experiment_name>/`（命名规则：
  runner 的 `experiment_name`，见 `rl_exp/tasks/agents/rsl_rl_ppo_cfg.py`）。
- 什么都不传 = 全局最近有事件写入的 run（即"当前在训的那个"）。

### 第 2 步：跑探针（IsaacLab 根目录下）

```bat
<venv python> <REPO>\rl_exp\tools\trainlog\probe_run.py                :: 默认=最活跃 run
<venv python> <REPO>\rl_exp\tools\trainlog\probe_run.py --exp v4       :: 版本子串匹配
<venv python> <REPO>\rl_exp\tools\trainlog\probe_run.py --run logs/rsl_rl/<exp>/<ts> --window 200
<venv python> <REPO>\rl_exp\tools\trainlog\probe_run.py --tags Loss,Policy   :: 只看关心的组
```

- `<REPO>` = 本仓目录（原机 `E:\robot`，可用 `RL_ISAAC_ROOT` 同级约定推断）；
  `<venv python>` 见仓 README；`logs` 根相对 cwd，必须在 IsaacLab 根运行或 `--logs` 覆盖。
- 输出分组：头部（iter/总进度/最新 ckpt/事件新鲜度/iters·h/ETA）→ CORE →
  CURRICULUM → LOSS → TERMINATION → REWARDS → OTHER → WARNINGS。
- 每行 = tag、last 值、窗口均值、对前一窗口的 Δ%（趋势方向即健康方向，
  注意 error/fps 类越小/越大语义相反）。

### 第 3 步：判读要点

- **起步 sanity（~100 iters）**：无 NaN、reward 非零、`Episode_Termination/*` 计数正常
  （time_out 占比高 = 存活好；fall/tilt 类暴涨 = 趴窝信号）。
- **课程活性**：`Curriculum/terrain_levels` 长期贴 0 或顶格不动 → 对照版本 PLAN 的
  卡排判据；`*/stage` 是否按计划推进。
- **策略塌缩**：`Policy/mean_std` 骤降到 ~0、`Loss/entropy` 暴跌 → 过早收敛信号。
- **速度**：iters/h 对比历史 run（v3 参考 ~460），掉一半先查 Perf/collection_time
  与是否共享 GPU。
- **接触栈溢出类物理问题不在本探针**：v4 的 `[contact check]` 量化监控走
  `view_terrain.py`（skill isaaclab-pretrain-check 第 3 步）。

### 第 4 步：汇报

- 给用户：进度一行 + 关键指标趋势表 + WARN 判读 + 与版本 NOTES 验收线的对照结论。
- 训练结束后的正式记录仍走 `dump_tb.py` → `versions/<family>/<vN>/tb_scalars.csv`
  → `plot_tb.py`（探针是过程监控，不替代冻结记录）。

## 注意事项

- resume 后同目录多个 events 文件：探针已按 step 合并去重（后写覆盖），读数可信。
- `--window` 默认 100 样本；短 run（<200 iter）调小才有趋势对比。
- 判读阈值（多少算"骤降"）随任务量级变化，以该版本 NOTES/PLAN 为准，勿套用他版数字。
