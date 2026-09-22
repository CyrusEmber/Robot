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

## P006 "关掉随机化"顺手把关关节复位也关了（资产级 reset 不写关节状态）

**日期**: 2026-09-18
**影响**: baseline 线 v1 配方（`reset_robot_joints` 与其余五项一起置 None）。终止/超时的回合**不恢复
关节位置与速度**：机器人被放回默认高度与姿态，但带着上一回合摔倒时的关节角与角速度继续跑。首回合
之后的每个初始条件都被上一回合污染，而所有闸门全绿。

### 症状

无报错、无告警。配置读起来完全合理（"零 DR"意味着所有随机化事件置 None），启动探针也通过——它读的
是 `data.default_joint_pos` **模板**：模板两边一样，写没写都一样，所以"没复位"和"复位正确"在配置与
探针两侧长得完全一样。

实测（`reset_check.py --task Lizard-Baseline-Flat-v1`，修复前）：

```
B excite 20 steps    excited envs 8/8  worst |dq| 0.4089 rad
FAIL C/joint-pos-after-reset: worst 0.4089 rad (tail1_pitch_joint 0.4089, rl_haa_joint 0.3426, ...)
FAIL C/joint-vel-after-reset: worst 9.3779 rad/s
FAIL D/subset-back-at-default: worst 0.3395 rad
```

reset 前后偏差**一模一样**（0.4089 → 0.4089）：关节根本没被写过，不是写得不准。

### 根因

本框架（pin `28a37cec`）里 reset 的写入者是**事件**，不是资产：

- `InteractiveScene.reset(env_ids)` → `Articulation.reset(env_ids)`
  （`interactive_scene.py:599`）；
- 而 `Articulation.reset()` 只做三件事：执行器内部状态、newton adapter、
  两个 wrench composer（`isaaclab_physx/assets/articulation/articulation.py:222-246`）。
  **没有任何关节状态写入**；
- 关节位置/速度的唯一写入者是 reset 事件 `mdp.reset_joints_by_scale` /
  `reset_joints_by_offset`（`envs/mdp/events.py:1924-2003`）。

所以停掉 `reset_robot_joints` = 停掉关节复位。`reset_base` 只把 root 拉回默认位置/速度，替代不了它。

**为什么容易一起删**：复位写入与随机化**共用同一个 term**（stock 那个 term 就是"缩放默认姿态"），
"关 DR"的清单里于是混进一个不是随机化的东西。

### 修复

`baseline_no_dr` 不再置 None，改为**保留并钉死**：`position_range=(1.0, 1.0)`、
`velocity_range=(0.0, 0.0)`。`sample_uniform` 是 `rand*(upper-lower)+lower`（`utils/math.py:1427`），
上下界相等时结果**精确**等于该值，所以这是"写默认姿态 + 零速度"，不是"近似复位"。断言侧同步：
`baseline_probe.py` 的 DR 名单去掉该项，改为断言"存在 + func 正确 + 钉死"，并补上
`reset_base` 的逐轴范围检查（原来只查"term 存在"，不读数字）。

固定范围要随机化初值时，应新增独立 term（如主线 v12 的 `reset_joints_by_offset` 包），
**不要**回头改这个 term 的倍率——那会连复位一起改掉。

### 通用规则

**"关掉随机化"的清单要区分"随机化"与"复位本体"。** 一个 term 同时干两件事时，
先问"把它删掉，仿真状态还回得去吗"。另：**配置门证明不了状态被写**——快照里没有"少了写入者"
这个字段，只有 rollout 能看见。

### 检测方法

```bash
# 平台契约（无版本名，任何线都能跑；先激励再 reset，否则测不出来）
"E:/IsaacLab/env_isaaclab/Scripts/python.exe" rl_exp\tools\verify\reset_check.py --task Lizard-Baseline-Flat-v1
```

判据是 C（全量 reset 后实际 joint_pos/vel 回到默认）与 D（子集 reset 后，未被点名的 env **逐位不变**）。
两者都带空转守卫：B/D 先确认关节真的离开了默认，否则"回到默认"与"没人动过"无法区分。
配方侧另有 `baseline_probe.py` 的 `events/reset-joints-*` 三条（存在/func/钉死）。


## P007 记录的源头在机器本地，抽样入库才是它唯一的家

### 症状
需要"当时那条曲线"时，`<ROOT>\logs\` 下的 tfevents 已经不在了（换机、清盘、同名目录被覆盖），
于是记录里只剩结论、没有过程。v1.5.2 之前每次 run 的原始曲线就是这种状态。

### 根因
tfevents 写在**机器本地**且体积大（单版 20–22 MB），既不入库也没有第二份；而记录体系的读侧
（`record.read_state`）对缺失一律回 `unknown`，于是"过程取不回"表现为"这条记录没有证据"。

### 修复
v1.5.2 起按 run 抽样入库（每版 `vN/tb_scalars.csv`，20–22 MB → 210–227 KB），全量仍留机器本地。

### 通用规则
**不可再生的东西必须在还能取到的时候入库**；可再生的（几何、图表、由 seed 决定的产物）不入库、靠再生。
区别对待的理由只有一个：入库是为了让记录自足，不是为了让记录变大。

### 检测方法
问"这条记录能不能只靠仓内材料回答它自己的每一个读数"——不能，就说明有东西没入。

## P008 别把"我是从哪儿被调起来的"当配置

### 症状
provenance 里 `git_rev_<repo>=unknown` 且**串位**：另一个仓的 rev 被填进本仓的字段（v1.5.1 实测）。

### 根因
从**调用路径的父目录**推断"代码家在哪儿"。调用链里有多棵树（IsaacLab 树、git 仓、venv），
父目录只是"这次恰好从哪进来的"，不是配置。

### 修复
路径参数化：机器本地事实（IsaacLab 根 + venv 解释器）登记在 `paths.yaml`，唯一读者 `host_paths.py`，
其余模块一律问它，不再各自从调用路径猜。

### 通用规则
**配置只有一个真源，绝不从运行时上下文推断**；凡是"猜出来的"值，都要能复述它是从哪一条声明来的。

### 检测方法
从任意 cwd 调用入口，provenance 结果必须逐位相同；不同则说明还在从路径推断。

## P009 用 URDF 轴值手算关节行程（轴"在哪一端"决定量级，本次错 60×）

**日期**: 2026-09-21
**影响**: 讨论"哪条关节能产生前进推力"时，把 `hfe` 的竖直轴当成过髋点，估出 ±1.2 rad ⇒ 单腿前后行程
0.44 m；实测 0.3 rad 只让脚移 **15 mm**（差约 60×）。照推算下结论，会把"够不到目标速度"误判成策略问题
而不是几何问题，v2 那条"够不到 ⇒ 瓶颈在资产"的假设本可提前答。

### 症状
手算：脚到**髋**竖轴的水平半径 = 0.4188（股骨横向）+ 0.0097 + 0.0395 ≈ 0.47 m ⇒ 0.3 rad × 0.47 = 0.14 m。
实测（FK）：`lf_hfe_joint +0.30` ⇒ 脚移 **0.015 m**。

### 根因
URDF 里 joint 的 `origin xyz` 是它在**父连杆系**里的位置，即该轴穿过的那一点；`axis xyz` 只给朝向。
`rf_hfe_joint` 的 origin 落在股骨**远端**（离髋 0.502 m），轴穿过那里 ⇒ 半径只有 0.049 m。手算时只读了
`axis` 与骨长，没把轴的**位置**代进半径。`FAMILY.md` 的镜像表（轴 vs 镜像面）同样不含位置，看表推不出量级。

### 修复
`check_joint_layout.py` 的 **FK 段**（2026-09-21 加）：零动作、注入 +0.3 rad、`sim.forward()` 只更新运动学
不推物理（PD/重力/地面都进不来），印 `turn=`（子连杆轴×角，机体系，**模长 = 注入角 = 自校验**）与 `d=`
（链末端位移）。同时记下两条读法陷阱：

1. `d=` 对"链末端就是该关节自己的子连杆"的关节结构性读 0（`*_foot`、`neck_yaw`、`neck_pitch`、
   `tail3_pitch`）——URDF 子连杆原点坐在自己的关节轴上。这类关节只能读 `turn=`。
2. 别自己拼四元数差：本 fork 的 buffer 阶数与手写 `axis_angle_from_quat` 的假设不一致，印出 2.84/3.11
   （真值 0.30）。用 `quat_apply` 转子连杆基向量、取叉积，绕开阶数。

### 通用规则
**关节的可动量级由"轴穿过哪里"决定，不由轴的朝向决定。** 任何"× rad ⇒ × m"的估算只能来自实测 FK；
手算必须把轴的位置代进半径，并当场标注是估算。`FAMILY.md` 早有"禁手算极性"，本条把范围扩到**行程量级**。

### 检测方法
怀疑"某关节摆不动 / 摆太多"时跑 `check_joint_layout.py --task <PLAY 任务>`，看 FK 段 `turn=` 的模长是否
等于 0.300：不等于说明读法错，不是资产错。

### 补记：单关节表不是上界，组合扫描自己也是三条新坑（2026-09-21 当晚实测）

- **单关节行程小 ≠ 这条腿没有该方向的能力**：`hfe` 单关节 0.015 m/0.3 rad，而 `hfe × kfe` 组合在站姿
  高度下把掌板中心前后推到 **0.392 m**（26×）。两个关节会复合（一个改半径、一个绕轴转），乘积不是和的
  量级。凡"某关节只能动几毫米 ⇒ 推不动"的推论，一律先扫组合再说话——本条是当天从错误结论里撤回来的。
- **组合扫描自己的三条读法**（第一版三条全踩，靠"中格必须复现刚量到的稳态"这一条自检才暴露）：
  1. 参考行必须是**受载稳态的关节状态**，不能是全零位——零位 = "未受载的腿 + 已下沉的机身"，两不像；
     该系统承重下垂实测 ‖q_ref‖ = 0.178 rad，照零位扫出来的中格根本不是刚量到的站姿。
  2. 测点必须是**固定材料点**（如掌板 bbox 中心）。"取最低的 bbox 角"会随姿态换身份：那次量到
     143–644 mm 的"行程"，量的是掌板自身的 0.458 m 尺寸。
  3. 坐标要剥掉出生 yaw（与 `pos_b` 同法）。世界系 x 会把机身前后与左右混在一起；本次 yaw ≈ 0 才侥幸同值，
     换一次随机出生 yaw 结论就会漂。
- **通用规则**：任何"可达范围"的数字都要写明三件套——参考姿态、测点身份、坐标系；且必须留一条已知答案
  的自检（本项用中格 vs 稳态，差 1 mm）。

### 再补记：力臂要在**同一姿态**下测，测点要**按腿**取（2026-09-22 逐腿表实测）

给 `check_joint_layout.py` 加"每个腿部关节各自扫遍 URDF 行程"的表时，同一天踩出两条新坑，都被机制抓住：

1. **跨姿态复用方向**：轴线在零位姿态下测过（FK 段），却在**落定姿态**的量测里当下用它算力臂
   （`arm = 点到轴线的垂距`）。机体落定时已下垂 0.178 rad，两个姿态的基座系相差一个旋转 ⇒
   lizard 的 `rr_hfe` 力臂偏小 8%（0.064 vs 0.073 m）。抓它的机制是新增的**弦长断言**
   `dx ≤ 2·arm·sin(Δθ/2)`：读法错会直接算出 `dx/chord = 1.12 > 1`（几何不可能）。修好后该值 = 1.00。
2. **测点不按腿取**：四腿共用一个"掌板中心"，于是扫右后腿的关节时读左前脚 —— 位移恒 0.000、
   力臂 1.2–1.7 m（那是到左前脚的距离）。症状很隐蔽：表本身看起来"右后腿没能力"。
   正确做法是**每条腿量自己的脚掌**（`leg_probes()` 的 endpoint），此时四腿髋的前后行程一致（0.546–0.558 m）。
3. **推论**：给每条腿/每个关节出数时，"哪条链、哪个点、哪个姿态"必须与"哪条轴"同源；跨姿态或跨腿借量，
   错的是读数不是资产——所以宁可用几何上界（chord）当断言，也不要用"看起来合理"当验收。
