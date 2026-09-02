# 排坑记录

## P001 Kit 启动报 TfNotice 错（omni.UsdMdl 加载失败）

**日期**: 2026-09-01
**影响**: 所有 teacher 系任务（Lizard-Rough-Play-v1/v2/v3 等）带 `--viz kit` 启动即崩；Flat 任务不受影响。

### 症状

```
RuntimeError: extension class wrapper for base class
pxrInternal_v0_25_11__pxrReserved__::TfNotice has not been created yet
[ext: omni.kit.usd.mdl-1.1.9] Failed to startup python extension.
```

### 根因链

环境里有两套 `pxr`（USD Python 绑定）：

1. pip `usd-core 25.11`：单体构建（单个 `usd_ms.dll`），位于 `site-packages/pxr`，是 `isaaclab` 包的依赖。
2. Isaac Sim 扩展 `omni.usd.libs`：分体构建（`usd_tf.dll` 等几十个），位于 `extscache/omni.usd.libs-*/pxr`。

`omni.kit.usd.mdl` 扩展的 `_usdMdl.pyd` 按分体构建编译。若 kit 启动**前** pip 版 pxr 已进 `sys.modules`，扩展里 `from pxr import Tf` 命中缓存的错误版本 → TfNotice wrapper 未创建 → 崩。

污染路径（修复前）：

```
play.py 顶层解析 hydra
→ rl_exp.tasks.teacher_env_cfg
→ rl_exp.tasks.teacher_mdp 顶层 import RayCaster
→ isaaclab.sensors.ray_caster → isaaclab.sim.simulation_context
→ isaacsim（包 __init__ 直接 import pxr）
→ pip 版 pxr 进 sys.modules
→ AppLauncher 再启动 kit → omni.kit.usd.mdl 崩
```

Flat 任务能跑：`lizard_env_cfg` 的 import 链不经过 `RayCaster`。

### 修复

`rl_exp/tasks/teacher_mdp.py`：`RayCaster` 从模块顶层移到 `FootContactNormalsTerm.__init__` 内延迟导入（运行时 kit 已启动）。见该文件模块顶注释。

### 通用规则

**hydra compose / AppLauncher 之前的 import 路径，禁止触发 `isaacsim` 或 `pxr` 导入。** 高危顶层导入：

- `isaaclab.sensors.ray_caster`（及任何 `isaaclab.sensors` 深层子模块）
- `isaaclab.sim.simulation_context` / `isaaclab.sim.utils.stage`
- `isaacsim.*`

需要这些符号时，在 `__init__` / 函数体内延迟导入。

### 检测方法（one-liner）

```bash
python -c "import sys; import rl_exp.tasks.teacher_env_cfg; print('PXR LEAKED' if 'pxr' in sys.modules else 'CLEAN')"
```

干净时输出 `CLEAN`。任何 env cfg / mdp 模块改动后跑一次。

## P002 课程 gate 恒读 0（metrics buffer 记完即清）

**日期**: 2026-09-02
**影响**: v3.6 速度课程全程 stage 0，首跑 5000 iter 档位从未推进。

### 症状

TB `Curriculum/speed_curriculum/metric` 恒 0.000、`stage` 恒 0，而
`Metrics/success_rate` 已到 0.36——gate 与日志读数脱节。

### 根因

`ManagerBasedRLEnv._reset_idx` 的顺序：

```
curriculum_manager.compute()      # gate 在这里读 command.metrics → 全 0
...
command_manager.reset()           # term.reset: 先写 episode 终值 → 记日志 → 立刻清零 buffer
```

`CommandTerm.reset`（command_manager.py:132-136）对 reset 的 env **记完即清零**
`self.metrics`。课程 term 读 `command.metrics["success_rate"].mean()` 时 buffer
永远是零（mid-episode env 是 0，刚 reset 的又被清）。单测用假 command 的常驻
buffer 喂值，测不出这个时序。

### 修复

`StagedCurriculumTerm._gate_metric` 改读 `env.extras["log"]["Metrics/<term>/<metric>"]`
（或统一路径 `Metrics/<metric>`）——command term 在 reset 里写日志的标量，
是跨步持久的真值；配 EMA（`metric_ema_alpha`，默认 0.05）平滑单批次噪声。

### 通用规则

**读别的 manager 的瞬时 buffer 前，先查 step 内调用顺序和清零时机**；
日志 extras 通常比内部 buffer 更可靠。课程/统计类 term 优先消费
`env.extras["log"]`。

### 检测方法

训练 TB 里 `Curriculum/<term>/metric` 与 `Metrics/<metric>` 长期背离
（一个恒 0、一个在涨）即同类 bug。
