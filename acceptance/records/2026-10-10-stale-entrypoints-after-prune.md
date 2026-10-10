# 清理后遗留的死入口与陈旧指针：执行记录（2026-10-10）

## 适用范围

`work/closed/2026/stale-entrypoints-after-prune.md` 的执行落盘记录。对象 = 退休线清理
（`acceptance/records/2026-10-09-retired-family-prune-execution.md`）**之外**留下的四类残留：
① 不 import 已删模块、因而闸门看不见的旧任务 id 默认值；② 主体已随旧线消失的两个工具；
③ `.codemaker/skills` 里把已删脚本当现成入口的两处；④ 一次性脚本与两处记录口径。

本记录只写落盘事实与判据；清单级的删除判据归 10-09 的两份记录，不复述。

## 验收条件

- (a) 每个 `--task` / `--tasks` 默认值要么是**仍注册**的 id，要么改成必填；工具自身 docstring 与之一致。
- (b) `play_keyboard_task` 的 `KEY_SENSITIVITY` 与活跃版本 yaml 的命令范围对得上，注释写的是现状。
- (c) skill 里已删脚本的入口改指仍存在的脚本，历史差异写明而不留假入口。
- (d) 一次性脚本不再留在 `rl_exp/tools/verify/` 主路径。
- (e) 两处 `SERIAL_BUDGET_S` 口径与 `offline_suite.py` 的常数一致。
- 判据形状：`run_offline_checks.bat` 全绿；逐个工具 `--help` 打印的默认值是注册表里的 id。
  不预先断言本次会通过（见下节实测）。

## 结果

### (a) 默认值改写（12 处 / 12 个文件）

| 文件 | 位置 | 改前 | 改后 |
|---|---|---|---|
| `rl_exp/tools/diagnose/diagnose_nan.py` | `:1` docstring、`:13` `TASK` | `Lizard-Velocity-Flat-v0`（stock 模板残留 id） | `Lizard2-Flat-v3` |
| `rl_exp/tools/diagnose/diagnose_support.py` | `:82` 描述、`:83` `--task`、`:84-87` `--checkpoint` | `v10 支撑异常诊断`、`Lizard-Rough-v10`、硬编码 `lizard_rough_teacher_v10/2026-09-09_18-15-19/model_14999.pt` | 描述去掉 v10、`Lizard2-Flat-v3`；`--checkpoint` 改 `required=True`（那条日志路径本身已随旧线退役，留默认值就是留一个跑不通的路径） |
| `rl_exp/tools/diagnose/play_keyboard_task.py` | `:12` docstring、`:218`/`:252` 自检默认、`:60-65` 注释、`:182` 报错文案 | `Lizard-Rough-Play-v8`；注释按 v8 的 yaml（x `(-1, 3)`、y `(-0.5, 0.5)`、yaw `(-1, 1)`） | `Lizard2-Flat-Play-v3`；注释按 v3 的 yaml（x `(0, 3)`、y `(0, 0)`、yaw `(0, 0)`）并写明 y/yaw 在训练里被钉零 ⇒ 键盘点这两轴是**离分布探查**，不是复现训练命令窗 |
| `rl_exp/tools/verify/baseline_probe.py` | `:12`、`:28` | `Lizard-Baseline-Flat-v1` | `Lizard2-Flat-v3` |
| `rl_exp/tools/verify/check_contact_ownership.py` | `:27`、`:44` | `Lizard-Baseline-Flat-v2` | `Lizard2-Flat-v3` |
| `rl_exp/tools/verify/check_joint_layout.py` | `:97` | `Lizard-Rough-Play-v8` | `Lizard2-Flat-Play-v3` |
| `rl_exp/tools/verify/lifecycle_entry_run.py` | `:320` `--resume-task` | `Lizard-Rough-v14` | `Lizard2-Flat-v3`（`:47` 的 `RETIRED_TASK` 是**故意**的退休样例，不动） |
| `rl_exp/tools/verify/obs_protocol_live.py` | `:17`、`:28` | `["Lizard-Rough-v14"]` | `["Lizard2-Flat-v3"]` |
| `rl_exp/tools/verify/reset_check.py` | `:41`、`:53` | `Lizard-Baseline-Flat-v1` | `Lizard2-Flat-v3` |
| `rl_exp/tools/verify/terrain_split_env_run.py` | `:13`、`:26` | `Lizard-Rough-v11`（param-grid 地形任务） | **改必填**，无默认值 —— 该探针要 param-grid 地形任务，而有过这种任务的 id 全随 `lizard/main` 退役，lizard2 是平地（`terrain_generator=None`）⇒ 没有可指向的活跃 id。docstring 写明缘由 |
| `rl_exp/tools/verify/view_terrain.py` | `:24-29` docstring、`:36` 默认 | `Lizard-Rough-Play-v4/-v8` 示例、默认 `Lizard-Velocity-Flat-Play-v0` | 示例改 `Lizard2-Flat-Play-v3`，并注明该脚本原本围绕的粗糙地形 id 已退役 |
| `rl_exp/tools/launch_recipe.py` | `:21-22` docstring | `--task Lizard-Rough-v14` | `--task Lizard2-Flat-v3`（该文件是被 `test_launcher` 用 `contract=` 看守的产物，只动示例） |

保留不动的旧 id 属**故意**，逐条依据：`test_eval_record.py`（纯字符串夹具，不建 env）、
`test_rebuild_gate.py:36`（喂 `_record()` 桩，不查注册表）、`test_terrain_geometry.py:39`
（合成路径串）、`test_lifecycle_gate.py:48`（退休拒绝样例）、`lifecycle_entry_run.py:47`。

### (b) 删除（2 个工具）

| 文件 | 判据 |
|---|---|
| `rl_exp/tools/diagnose/direction_probe.py` | `:45` import `LizardRoughTeacherEnvCfg_V8_PLAY`、`:47` glob `lizard_rough_teacher_v8` —— 该符号与日志目录随旧线消失，文件今天连 import 都过不去，主体是 v8 机体朝向探查 |
| `rl_exp/tools/verify/time_foot_rings.py` | `:62-63` 的被测对象是 `Lizard-Rough-v3` 的 208 束脚环 vs `v2` 的 135 束基线网格，两个 id 都已注销 ⇒ `run_task` 里的 `gym.spec` 直接抛；工具整个就是那次计时对照 |

### (c) 归档（2 个一次性脚本移出主路径）

| 文件 | 去处 | 处置 |
|---|---|---|
| `_b3_remove_version_classes.py` | `rl_exp/tools/archive/` | 已执行过；它按类名定位，而目标版本类已随旧线消失（原为 `AGENTS.md` 的"提交前删"欠账）。docstring 加"已执行"标注，usage 行改归档路径；`acceptance/records/2026-09-16-lizard-layout-migration-lifecycle.md` 里的复读路径随之仍可解析 |
| `_a0_layout_migration.py` | `rl_exp/tools/archive/` | 同类：`versions/lizard/main/` 就是它的产物，同样是花掉的一次性脚本（本项新发现的第二个，10-09 记录只点了 `_b3`） |

`rl_exp/tools/verify/_a0_paths.py` **不动**：它是活机制（`check_work_docs` 的路径口径等直接引用），
不在"一次性"之列。

### (d) skill 入口改准（4 个文件）

| 文件 | 处置 |
|---|---|
| `.codemaker/skills/tool/isaaclab-task-creator/SKILL.md` | `tasks\` 目录表去掉已删的 `staged_curriculum.py`（改为"按需的课程组件"）；课程 API 一节标题改为"`staged_curriculum.py` 的模式，该机器人有时直接复用" |
| `.../isaaclab-task-creator/references/runtime_facts.md` | 私有成员清单：删两条 `staged_curriculum.py`（文件已不存在），保留并补全 `teacher_mdp` 的两条（`_physics_sim_view`；`RayCaster.meshes` + `raycast_mesh_masked_kernel`，后者是 `framework_pin_check.NEEDLES` 的看守对象）；环境验证脚本表整体改指**仍存在**的脚本（`baseline_probe` / `check_joint_layout` / `reset_check` / `check_contact_ownership` / `view_terrain` / `debug_pose` / `diagnose_nan` / `dump_tb`），并注明被替换的五个脚本已随旧线删除 |
| `.../isaaclab-asset-pipeline/SKILL.md` | 转换后验证链的"位置/受力"与"关节对表"两行从 `position_check` / `joint_check` 改为 `baseline_probe.py` / `check_joint_layout.py`，`debug_pose` 加回显式路径；标准顺序随之更新 |
| `.../isaaclab-asset-pipeline/references/blender_pipeline.md` | 第 7 步验证链与"站姿判定标准"标题里的 `position_check` 改为 `baseline_probe`，并留一行历史说明 |

### (e) 记录口径（2 处）

| 文件 | 改前 | 改后 |
|---|---|---|
| `acceptance/records/2026-10-09-retired-family-prune-execution.md:101` | "`SERIAL_BUDGET_S` 的实测值归下一个独立提交（本次未动该常数）" | 本次随条数棘轮移动（175 → **160**），依据是 37 条下重新实测的 quiet **146s** |
| `acceptance/records/2026-10-09-retired-family-prune-manifest.md` §3 | "`SERIAL_BUDGET_S = 175.0` 须实测后再钉" | 补"已执行：实测 146s ⇒ 收到 160"及其口径出处 |

### 判词（可复读）

```
rl_exp\tools\verify\run_offline_checks.bat
```

## 证据引用

- 前置：`acceptance/records/2026-10-09-retired-family-prune-manifest.md`（§3 套件与常量）、
  `acceptance/records/2026-10-09-retired-family-prune-execution.md`（未覆盖边界四条）。
- 活跃任务表：`rl_exp/tasks/__init__.py`（6 个 `Lizard2-*` 注册）。
- 命令范围来源：`rl_exp/versions/lizard2/main/v3/main_params.yaml:107-111`。
- 判词：上节复读命令。

## 未覆盖边界

- **未真跑**：本项只保证"默认值指向注册表里存在的 id / 必填"，没有真起过仿真验证任何一个工具跑通
  （它们都要起 app）。判据到此为止。
- 两个删除（`direction_probe` / `time_foot_rings`）是**我的裁决**，不是用户拍板：判据是主体随旧线消失，
  但"从不恢复"只有 git 历史与 tag `lizard-final` 兜底。
- `diagnose_support.py` 的默认值改准了，但它的 `--phases/--heights/--approach` 语义仍是 v10 台阶支撑诊断
  的形状（`work/active/floor-contact-attribution.md` 把它列为 landing 才没删）；要对 lizard2 有意义需要
  重写那套 case 构造，不属本项。
- `terrain_split_env_run.py` 改成必填后**仍无活跃 id 可用**：它有工具、无被试对象，等 lizard2 接入地形
  课程（`work/active/dr-widening-policy.md`）才复活。
- `.codemaker/skills` 是**模板**（"别的机器人照此模式建自己的"）：本项只把 lizard 实例的入口改准，
  没有核对这些模板对未来的其他机器人是否仍然成立。
- `ablation_harness` 侧的旧线默认值（`baseline_eval.py` 等）与 `versions/lizard/**` 历史文档里的旧口径
  按 10-09 的边界不动，仍在盘上。
- 本轮只动"默认值 / 死工具 / skill 入口 / 一次性脚本 / 两处记录口径"；`teacher_mdp` 保留段的去向归
  `work/active/teacher-mdp-residual-kernels.md`。
