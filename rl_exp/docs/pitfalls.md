，# 排坑记录

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
python rl_exp\tools\verify\check_pxr_leak.py
```

干净时输出 `OK (resolved task cfg chain is pxr-clean: N tasks constructed)`。任何 env cfg / mdp
模块改动、或 cfg 构造期行为改动后跑一次（该闸门构造注册任务的 cfg，覆盖 import 面与构造面）。

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

## P003 Kit 启动报 "No to_python (by-value) converter"（omni.physx 崩）

**日期**: 2026-09-11
**影响**: v10 训完后的 GUI 回放（play.py）启动即崩；同一 import 链下 TRAIN
也会崩。09-09 启动的 v10 训练进程不受影响（毒 import 09-10 才落地）。

### 症状

```
TypeError: No to_python (by-value) converter found for C++ type:
class pxrInternal_v0_25_11__pxrReserved__::UsdTimeCode
[ext: omni.physx-110.1.11] Failed to startup python extension.
RuntimeError: Caught an unknown exception!   (omni.usd.libs 的 UsdShade 命中
site-packages\pxr 的 Tf，两套 25.11 混载)
```

### 根因链

v11 落地（commit `a9bacea`）在 `teacher_mdp.py` 顶层加了
`from isaaclab.envs.mdp.commands import UniformVelocityCommand`：

```
teacher_mdp 顶层 import（hydra compose 阶段，pre-AppLauncher）
→ velocity_command.py:17  from isaaclab.assets import Articulation
→ base_articulation.py:19 from ...sim import SimulationContext
→ simulation_context.py:31 from isaaclab.scene_data import SceneDataProvider
→ scene_data_provider.py:16 from pxr import UsdGeom   ← pip usd-core pxr 进 sys.modules
→ Kit 启动：extscache 分体 pxr 与 pip 单体 pxr 同版本标签（25.11）混载
  → C++ 转换器注册冲突 → omni.physx 崩
```

P001 同族（毒源换了）：P001 是 `isaaclab.sensors.ray_caster`，本例是
`isaaclab.envs.mdp.commands` 的**类**模块。stock 自己不被毒是因为
`UniformVelocityCommandCfg.class_type` 默认就是字符串懒解析
（`"{DIR}.velocity_command:UniformVelocityCommand"`，configclass 包成
`ResolvableString`，命令管理器构建期才 import）。

### 修复

- `teacher_mdp.py`: 顶层 import 换成无毒的 `commands_cfg`（只有 Cfg 类）；
  `ParticleVelocityCommand` 改 `_build_particle_command()` 工厂 + 模块
  `__getattr__` 懒构建；Cfg 的 `class_type` 用字符串
  `"rl_exp.tasks.teacher_mdp:ParticleVelocityCommand"`（stock 同款机制）。
- 新闸门 `check_pxr_leak.py` 进 `run_offline_checks.bat`（P001 的
  one-liner 闸门化——v11 当时 13 项闸门全绿仍炸，缺的就是这项）。

### 通用规则

P001 规则升级：除 `isaaclab.sensors.*` 外，**类模块**（含
`isaaclab.envs.mdp.commands.velocity_command`）同样会把 pxr 拖进
sys.modules；对应的 `commands_cfg` 模块无毒。凡"类定义需要基类"的场景，
用字符串 `class_type` + 工厂懒构建，不要在模块顶层 import 类模块。

### 检测方法

`run_offline_checks.bat` 的 `[14]` 就是 `check_pxr_leak.py`（2026-09-18 起改为**构造**注册任务，见 P004）。手工单跑：

```bash
python rl_exp\tools\verify\check_pxr_leak.py
```

## P004 Kit 启动期 pxr 泄漏：cfg **构造期**的副作用（闸门看不见的那一半）

**日期**: 2026-09-18
**影响**: 真实训练入口（`train.py --task Lizard-Rough-v14` 等 teacher 系）在 hydra compose 期就把 pip usd-core pxr 拉进 `sys.modules`；与 P001/P003 同族，崩哪个扩展取决于 Kit 启动顺序。

### 关键点（与 P001/P003 的差别）

前两条都在**模块 import 面**（顶层 import 了谁）。这条在**构造面**：cfg 是 pre-Kit 构造的
（`load_cfg_from_registry` → `cfg_cls()`），而它描述的 env 是 post-Kit 才建的 —— 任何"只在
后半段才该做"的事一旦落进 `__post_init__`，就踩同一条坑。所以**只 import 模块的闸门永远
看不见它**：旧版 `[14]` 只 import teacher/lizard/agents 三个模块，一直是绿的。

### 根因链（实测栈，2026-09-18）

```
train.py:414 main()
→ isaaclab_tasks/utils/hydra.py:484 wrapper → register_task → parse_cfg.py:120 load_cfg_from_registry   cfg = cfg_cls()
→ rl_exp.tasks.recipe_tasks 的生成类（入口已切到这里）
→ recipe.py:922 __post_init__ → base.__post_init__(self)
→ teacher_env_cfg.py:591 components.terrain(...)
→ components.py:277 terrain_split_probe.install()
→ terrain_split_probe.py  install() 内 `from isaaclab.terrains import TerrainGenerator`
→ isaaclab/terrains/terrain_generator.py:22 from .utils import ...
→ isaaclab/terrains/utils.py:14 from pxr import UsdGeom   ← pip usd-core pxr 进 sys.modules
```

探针必须在 `TerrainGenerator` 被构造**之前**装好（生成发生在 `TerrainGenerator.__init__` 内），
而 `install()` 是 cfg 构造期（pre-Kit）被调用的 —— 于是"装补丁"这件事本身成了毒 import。

**与 C2 入口切换无关**：旧入口（版本类）的 `__post_init__` 是同一段代码，同样会漏；引入
时间点是探针落地（ARCH_PLAN 3.3d）。入口切换只让"闸门按模块名单走"这件事显得更可疑。

### 修复

- `terrain_split_probe.install()`：pre-Kit 不再主动 import 生成器模块，改把补丁**挂到
  `builtins.__import__` 上等**（`_patch_when_imported`）：每次 python 级 import 返回后检查
  生成器类是否已就绪（类在 = 模块执行完），就绪即打补丁并摘掉自己；模块已就绪则立即补。
  不变式不变：补丁仍在任何 generator 构造之前到位。（早先用的是 `sys.meta_path` 钩子，
  被 Kit 的 finder 抢走 —— 见 P005。）
- 闸门 `check_pxr_leak.py` 改成**跟着 registry 的解析结果走**：遍历已注册任务，按
  `env_cfg_entry_point` / `rsl_rl_cfg_entry_point` **构造**（不 `gym.make`），再断言 `pxr`
  不在 `sys.modules`。入口以后再换、构造期再加副作用，它都跟得上。

### 通用规则

**cfg 构造期（pre-Kit）只准放纯数据工作。** 需要 sim / 地形 / USD 的符号，要么字符串懒
解析，要么推迟到 post-Kit 的调用点。判据不是"顶层 import 干净"，而是"**构造一个 cfg 不会
拉 pxr**"。

### 检测方法

```bash
python rl_exp\tools\verify\check_pxr_leak.py
```

判据刻意只有一比特（pxr 进没进 `sys.modules`）—— 毒源已经换过两次名字（P001 ray_caster / P003
commands / P004 terrains），任何"毒模块名单"都会腐烂。失败时另打**首个毒族请求 + 调用栈 + 构造期
新引入的运行时模块**，所以诊断不必回查本文档。

两条反证：
- 套件 `[47]` `test_pxr_leak_gate.py`：注入一个 `__post_init__` 里 import `isaaclab.terrains` 的
  cfg 形类，断言判据**必然判为泄漏**且归因能指回构造它的那一帧（防"只跑真链、其实什么都没判"）。
- 端到端：把 `install()` 的延迟等待换回直接 import ⇒ `[14]` 必红（构造面才是它测的面）。

## P005 延迟等待被别人的 finder 抢走（补丁不落地，参数网格主线真跑全灭）

### 症状

`160240a` 之后，**每一个参数网格地形的主线任务真跑都死**，栈落在课程 term 构造时：

```
teacher_mdp.py:757 in __init__ → terrain_split_probe.record_for(terrain)
terrain_map.SplitRecordError: no split record for this terrain:
    the probe was not installed before the generator ran
```

而**同一个任务在离线/仪器路径下通过**：`terrain_split_env_run.py --task Lizard-Rough-v14`
报 `mode=curriculum cells=200/200 anomalies=0`。离线套件全绿。

### 根因

补丁**从未落地**。训练进程内单独实测（只读 spy 包住 `record_for`，不改写任何状态）：

```
installed=True patched=False records=0  wrapped=TerrainGenerator._get_terrain_mesh
generator_imported=True   meta_path[1]=_PatchWhenImported
```

`install()` 跑了、钩子还挂在 `sys.meta_path`、模块也导入了，但钩子**一次都没被问过**：导入机制
在**第一个返回非 None spec 的 finder** 处停止，Kit 会把自己的 finder 插到 `sys.meta_path[0]`
（我们 install 之后），它把这次导入接走。离线复现（无 sim，20 秒）：

```
installed=True patched=False hook queued=['_PatchWhenImported']
after import: patched=False wrapped=TerrainGenerator._get_terrain_mesh
VERDICT STOLEN IMPORT LEAVES THE PATCH UNLANDED
```

于是生成时 `_watched(cfg)` 静默成立但没人记，`_RECORDS` 为空 ⇒ 消费端拒绝。

**为什么仪器测不出来**：`terrain_split_env_run.py` 提前 import 了 `isaaclab.terrains`，走的是
"模块已就绪⇒立即 `_patch()`"分支，钩子那条路根本没被走。**仪器比真路更宽松，就等于没有仪器。**

### 修复

- 等待机制换成 `builtins.__import__`（`_patch_when_imported`）：每个 python 级 import 都过它，
  **不赌在列表里的位置**；就绪判据是"生成器类已存在"（模块可能在 `sys.modules` 里但仍未执行完，
  此时打补丁会 `AttributeError`），打完即摘。
- 同一个坑的第二半：**异常穿过 `launch_simulation` 的 `finally: close_fn()` 时，sim teardown 自己
  杀进程，退出码被改写成 0**（实测：只有一个 traceback、没有 `<module>` 帧、`os._exit`/`sys.exit`/
  `atexit` 一个都没触发）。所以 `train.py` 的 `__main__` 包装器看不到它。修法是**在失败点离开**
  （`_or_die(gym.make, ...)` / `_or_die(runner.learn, ...)`），与声明式拒绝的 `os._exit(2)` 同一惯例。

### 通用规则

**"等某人 import 我关心的事"不要用 `sys.meta_path` 插钩子**——那是竞态，任何后插的 finder 都能
截胡，而失败是静默的（少记录、不报错）。用 `builtins.__import__`（必经之路）或直接推迟到调用点。
另：**进程内可观测的状态要用真跑进程去读**，离线复现只证明机制，不证明它在 Kit 里也成立。

### 检测方法

```bash
python rl_exp\tools\verify\check_split_probe_wait.py      # 抢走导入后补丁仍必须落地
```

两条例行验证（都要真跑，离线测不到）：
- `train.py --task Lizard-Rough-v14 --num_envs 64 --max_iterations 1` 必须跑完并写出 checkpoint；
- 同一命令 `--num_envs 0` 必须 **RC=1**（失败可观测），而不是 0。
