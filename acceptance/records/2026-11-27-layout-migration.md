# 目录搬迁验收：机体、实验、运行、评测四块归位

- 日期：2026-11-27
- 范围：`robots/`、`experiments/`、`locomotion/`、`evaluation/`、`tools/`、`blender/`、`tests/`、`train.cmd`、`eval.cmd`、`pytest.ini`、`README.md`、`AGENTS.md`、`.gitignore`
- 结论：七步搬迁全部落地，每步单独提交。最终树上 v7 robust 评测的全部指标与基线逐位相等；`eval.json` 仅有路径、模块名、任务名、哈希类字段变化，逐项列于下。

## 提交

| 步 | 提交 | 内容 |
|---|---|---|
| 1 | `329108d` | `rl_exp/robots/lizard2_round_feet.py` 与资产并入 `robots/lizard2/round_feet/{robot.py, assets/}` |
| 2 | `5845bcc` | 测试并入 `tests/`，`pytest.ini` 的 `testpaths` 改 `tests`，`pythonpath = .` |
| 3 | `35ad442` | `locomotion/env.py` 收敛训练、评测、录像共用的环境装配 |
| 4 | `71878d2` | `train_record.py` 改名 `locomotion/run.py` |
| 5 | `4904831` | `lizard2_v7.py` 改为 `experiments/lizard2/flat_v7.py`，任务 id 内部名随文件名 |
| 6 | `10ad073`、`98ec622` | `evaluation` 内改包内导入并清 `sys.path`，再 `git mv ablation_harness evaluation` |
| 7 | `4c4d9bc` | 代码包去 `rl_exp/` 前缀；`rl_exp/__init__.py` 删除 |

## 与基线对比

模型 `model_5999.pt`（Isaac Lab 根下 `logs/rsl_rl/lizard2_v7/2026-11-03_17-07-29/`），协议 `locomotion_eval_v3`，seed 123，`robust`，`--exp experiments/lizard2/flat_v7.py`。该 Run 是旧 Run，本次运行同时验证了旧 Run 用 `--exp` 回读可行。

| 运行 | 源码 | 产物（该 Run 下 `evaluation/`） |
|---|---|---|
| 基线 | `85deecd7bac5` | `2026-11-25_12-48-23_4b780c57/` |
| 搬迁后 | `4c4d9bc96d47` | `2026-11-27_10-17-47_4858e74e/` |

指标逐位相等：`success_rate` 0.7677162885665894，其余指标同。递归比对 `metrics/eval.json`，不同的字段只有：

- `git_rev_lizard`（两处）、`timestamp`：计划允许。
- `terrain_evidence.definition.module`：`ablation_harness.terrain_geometry` → `evaluation.terrain_geometry`。计划允许。
- `task`、`conditions.run.task`、`terrain_evidence.identity.task`：`lizard2_v7` → `flat_v7`。计划外，第 5 步引入，见下。
- `conditions.experiment.path`、`conditions.experiment.sha256`：路径与内容变化（import 行改动）。计划外。
- `conditions.assets.{urdf,usd}.path`、`conditions.env_cfg.snapshot.scene.robot.spawn.usd_path`：资产路径变化，资产内容哈希未变。计划外。
- `conditions.env_cfg.snapshot.rewards.*.func.__callable__`、`terminations.head_ground_contact.func.__type__`：`rl_exp.locomotion.*` → `locomotion.*`。计划外，第 7 步引入。
- `conditions.env_cfg.digest`：由上面的路径与名字字段派生，无独立来源。计划外。

计划的"仅三项不同"低估了范围：`eval.json` 把路径、任务名和可调用对象的完整名写进了证据，凡搬迁必改。历史产物与新产物这些字段不可比，属已接受代价；指标不受影响。

计划第 5 步"任务 id 与 `register` 名、ckpt 目录绑定"的前提不成立：仓内已无 `gym.register`，ckpt 目录绑的是 `experiment_name="lizard2_v7"`（`experiments/lizard2/flat_v7.py`），`eval.json` 的 `task` 取实验文件名。

## 复审修正（同日）

- 任务名改取 `experiments/` 下的相对路径（`evaluation/experiment_eval.py` 的 `experiment_task`，`eval.py`、`video_matrix.py` 共用）：只取文件名时，`experiments/<机体>/flat_v7.py` 两个机体会得到同一个 `task`。现役值由上表的 `flat_v7` 再变为 `lizard2/flat_v7`；`--exp` 指向 `experiments/` 外的副本时退回文件名。回归 `test_task_names_keep_the_robot_directory` 在修复前失败（`AttributeError: ... no attribute 'experiment_task'`）、修复后通过。
- `tests/test_terrain_geometry.py` 的录像矩阵用例改用新任务名。
- `setup.bat` 的 `.pth` 注释改为"把仓根放进 `sys.path`"；文件名仍为 `rl_exp.pth`，重跑 setup 覆盖而非新增。
- `check_terrain_split_source.py` 扫描根缺失即报红（`db1db25`）。破坏测试：`625ee0d` 版本把 `_ROOTS` 换成 `rl_exp/robots`、`rl_exp/locomotion`，输出 `0 file(s) clean` 与 `TERRAIN_SPLIT_SINGLE_SOURCE_OK`、返回 0；修复后报 `scan root missing: rl_exp/robots`、返回 1。
- 圆足导出断链：`lizard2_round_feet_export.py` 要求骨架构建脚本的 sha256 等于 `rl_exp/out/lizard2_round_feet/skeleton02/build.json` 的 `script_sha256`（`a689c456…`），而第 7 步改了构建脚本的 `parents[N]` 与一行导入（现为 `8cfab1e7…`），导出会在 Blender 内报 `skeleton builder hash mismatch`。计划约束 2"只改路径常量、内容不变则哈希不变"对自定位脚本不成立。修法：导出加 `MOVED_BUILDER_SHA` 一条映射（记录值 → 搬后字节），不重建骨架、不改 `build.json`。回归 `test_export_accepts_the_skeleton_builder_it_ships_with` 离线核对现役构建脚本的哈希在映射里，修复前失败（`StopIteration`）、修复后通过；以后再改构建脚本而不重建骨架会在默认 pytest 红。
- `.gitattributes` 对圆足资产的 `-text` 与 whitespace 钉还写在旧路径 `/rl_exp/lizard2_round_feet/**`，第 1 步后资产落入 `* text=auto eol=lf`。索引本是 CRLF，当时未改字节，但重新 `git add` 时会面临规范化。规则已改到 `/robots/lizard2/round_feet/assets/**`，`git check-attr text` 为 `unset`，工作树无新增改动。

复审后检查：默认 `pytest` 60 通过、13 subtests；`pytest -m sim` 1 通过；`check_terrain_split_source.py` 43 个文件通过。

## 检查

- 默认 `pytest`：58 通过，13 subtests。
- `pytest -m sim`：1 通过。
- `tools/verify/check_terrain_split_source.py`：通过，43 个文件。
- 第 7 步中 `find_python.cmd` 因 `paths.yaml` 相对路径少上移一层而失败，已修，测试 `test_find_python_cmd_priority_and_yaml_parsing` 先失败后通过。

## 未做与限制

- `rl_exp/out/` 与 `rl_exp/lizard2_palm_spatial/` 原地不动。后者已入库（掌足 URDF 与网格），前者被 `.gitignore`。已记录的 Run 与导出哈希引用这些路径。
- 旧 Run 的 `provenance.json`、`params/env.yaml` 与历史 `eval.json` 保留旧绝对路径，不改写；回读必须显式传 `--exp`。
- `_ROOTS` 的破坏测试已补，见"复审修正"。
- 未做 `mdp/`：观测与动作仍内嵌在 `flat_v7.py`，按计划不建。
- `blender/scripts/*` 本机无 Blender，未实际运行。已离线核对：`parents[2]` 解析到仓根，三个 `tools.*` 导入与被绑定的四个源件可解析；构建脚本哈希断链已修（见"复审修正"）。导出所需的三份 `.blend` 在 `rl_exp/out/`，首次真跑仍是未验证项。
- 计划文档 `work/robot-experiment-layout-migration.md` 未入库，随本次复审删除；其约束与偏差已并入本记录。
