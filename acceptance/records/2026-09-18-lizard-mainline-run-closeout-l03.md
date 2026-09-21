# 主线真跑收口 + L03 真跑臂（`PLAN.md` #23，2026-09-18）

## 适用范围

本记录搬运 `rl_exp/versions/lizard/ACCEPTANCE.md` 的 §主线真跑收口 + L03 真跑臂（`PLAN.md` #23，2026-09-18）。

**本记录要收的是什么**：`160240a`（pre-Kit pxr 泄漏修复）把 `terrain_split_probe.install()` 的打补丁
动作改成"等框架 import 生成器模块时再打"，载体是 `sys.meta_path` finder。当日起**参数网格地形的主线任务
真跑全灭**：异常在课程 term 构造时抛出
`terrain_map.SplitRecordError: no split record for this terrain: the probe was not installed before the generator ran`，
而进程**退出码 0**。本记录记修复、真跑证据与 L03 两臂。

**与其它记录的关系**：L03 在入口侧此前的状态（"缺状态 resume 硬拒仍只有离线半边，真跑需一个缺课程状态的
ckpt 臂"）记在 `acceptance/records/2026-09-17-lizard-entry-switch-and-declaration-gap.md`；
本记录的两臂把那个缺口在**真跑面**上补上。地形映射本身（3.3）见
`acceptance/records/2026-09-17-lizard-eval-record-and-terrain-map.md`。

**读本记录须知的通读口径**：历史记录里的 `[N]` 是**当次运行编号**，不是闸门身份，套件总条目数受
`MAX_CHECKS` 棘轮管 ⇒ 成功行读数（`48/48`）**只在当日 commit 上成立**。

## 验收条件

### 前提

- tree：IsaacLab `28a37cecdd43` + fork 补丁；本仓 rev 见本记录「证据引用」末行"提交归属"。
- task：`Lizard-Rough-v14`（`lizard/main`），`--num_envs 64`，`--max_iterations 1`。
- 运行都带 `RL_ALLOW_DIRTY_TREE`（窗口内树脏），只用于取证，**不作"可重建"声明**。

### 判据（三条，全部本机真跑/进程内实测）

| 现象 | 实测 |
|---|---|
| 补丁在训练进程里**不落地** | 只读 spy 包住 `record_for`：`installed=True patched=False records=0`、`wrapped=TerrainGenerator._get_terrain_mesh`、模块已导入、`_PatchWhenImported` 仍列在 `sys.meta_path` |
| 失败**退出码 0** | 栈穿过 `sim_launcher.launch_simulation` 的 `finally: close_fn()`；`os._exit`/`sys.exit`/`atexit` 一个都没触发 ⇒ sim teardown 自己杀进程，`train.py` 的 `__main__` 包装器看不到 |
| 仪器与真路不一致 | `terrain_split_env_run.py --task Lizard-Rough-v14` **通过**（`mode=curriculum cells=200/200 anomalies=0`）——它提前 import 了 `isaaclab.terrains`，从不走等待分支 |

**根因**：导入机制在**第一个给出 spec 的 finder** 处停止，Kit 会把 finder 插到 `sys.meta_path[0]`
（`install()` 之后），于是钩子一次都没被问过。离线复现（无 sim）同判：
`STOLEN IMPORT LEAVES THE PATCH UNLANDED`。详见 `docs/pitfalls.md` P005。

## 结果

### 修复

- 等待载体换成 `builtins.__import__`（`_patch_when_imported`）：每个 python 级 import 必经，**不赌位置**；
  就绪判据 = 生成器**类**已存在（模块可能在 `sys.modules` 里仍未执行完），补丁打完即摘。
- 失败出口放到失败点：`_or_die(gym.make, …)` / `_or_die(runner.learn, …)`。**天花板**：with 体内其它
  异常仍会丢退出码，写在 `_or_die` 的 docstring 里并附升级路径。

### 真跑证据

| 臂 / 命令 | 结果 | run 目录 |
|---|---|---|
| 修复前 resume 两臂（v14） | 都死在 env 构造，`SplitRecordError`，**exit 0** | `2026-09-18_10-26-34`、`10-26-59` |
| 修复后 v14 短训 1 iter | 无 pxr 污染、无 `SplitRecordError`、`Training time 5.21 s`、写出 `model_0.pt` | `2026-09-18_10-55-11` |
| 反向控制：同命令 `--num_envs 0` | 栈落在 `_or_die`，**RC=1**（旧行为 0） | `2026-09-18_10-55-58` |
| **L03 arm2**：剥掉 `infos[STATE_KEY]` 的 ckpt，`--resume` 按声明要求状态 | **exit 2 硬拒**，文案含 `no curriculum state` / `cold-start`；T0 记 `drop_curriculum_state=false`、`load_checkpoint=model_stripped_nostate.pt` | `2026-09-18_11-00-48` |
| **L03 arm3**：同一 ckpt + `--drop_curriculum_state` | **exit 0 放行**；T1 `resume.resumed=true`、`curriculum_state.status="dropped"`、`evidence="none"`、`source=<…>/model_stripped_nostate.pt`（`source_sha256 a59b364e…`） | `2026-09-18_11-01-06` |

`lifecycle_entry_run.py --track resume` ⇒ `LIFECYCLE_ENTRY_RUN_OK`，报告 `problems: []`。

### 闸门

- 新增 `[48] check_split_probe_wait.py`（0.4 s）：外来导入（模块由别人放进 `sys.modules`）后补丁仍须
  落地，且 `install()` 不得自己 import 生成器。**反证已跑**：把等待换回 `sys.meta_path` finder ⇒ 该闸门
  报红并点名 "position-dependent again"。
- 全表 `48/48 ALL_OFFLINE_CHECKS_PASSED`（38.5 s 墙钟，wave 193 s，jobs=6）；`framework_pin_check.py`
  ⇒ `PIN_CHECK_OK`（`train.py` 改动已重钉进 `fork_patches/train_run_manifest.patch`）。
- `lifecycle_entry_run.py` 的报告曾把 lifeline 档的 `task`/`line` 当运行主语打印（`--track resume` 实跑
  v14 却报 parkour）⇒ 改为按档记 `tracks_run`/`lifeline`/`resume`。

## 证据引用

- 探针与载具：`rl_exp/tools/verify/terrain_split_probe.py`（`install()` / `_patch_when_imported` /
  `_or_die`）、`rl_exp/tasks/terrain_map.py`。
- 闸门：`rl_exp/tools/verify/check_split_probe_wait.py`（套件 `[48]`）、`framework_pin_check.py`（`[1]`，
  `PIN_CHECK_OK`、补丁重钉进 `fork_patches/train_run_manifest.patch`）。
- 真跑目录（`logs/rsl_rl/lizard_rough_teacher_v14/`）：`2026-09-18_10-26-34`、`10-26-59`（修复前）、
  `10-55-11`（修复后短训）、`10-55-58`（`--num_envs 0` 反向控制）、`11-00-48`（L03 arm2）、
  `11-01-06`（L03 arm3）。
- L03 入口：`rl_exp/tools/verify/lifecycle_entry_run.py --track resume` → `LIFECYCLE_ENTRY_RUN_OK`。
- 机制与坑：`rl_exp/docs/pitfalls.md` P005。
- **提交归属**：`6b5e1ee`（修复 + 闸门 + 归档重钉）· `ab49089`（报告主语）· `6176189`（P005 文档）·
  `5dd2e96`（出口守卫天花板）。
- 相关记录：`acceptance/records/2026-09-17-lizard-entry-switch-and-declaration-gap.md`（L03 的离线半边与
  入口侧状态）、`acceptance/records/2026-09-17-lizard-eval-record-and-terrain-map.md`（地形映射 3.3）。

## 未覆盖边界

- 本节的绿**只**证明"参数网格主线真跑不再死"与"L03 两臂成立"；**不证明训练收敛、不证明 v14 达标**。
- **出口码修复只护两个调用点**（`_or_die(gym.make, …)` / `_or_die(runner.learn, …)`）：with 体内其它异常、
  以及所有 `__main__` 之外的路径**仍可能以 0 退出**（天花板写在 `_or_die` 的 docstring 里）。
- 新闸门守的是**等待机制**，**不是**"Kit 不会再抢导入"这件事本身 —— 那只能真跑观测。
- 上述 run 都在**脏树**上、带 `RL_ALLOW_DIRTY_TREE`，**不作可重建声明**。
- 真跑窗口是当日快照：`48/48` 与各 run 目录只在**当日 commit** 上成立；`[N]` 是当次运行编号，
  不是闸门身份。
