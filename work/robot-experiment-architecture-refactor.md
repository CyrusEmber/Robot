---
id: robot-experiment-architecture-refactor
title: 运行与评测依赖方向整理
scope: rl_exp/locomotion, rl_exp/tools/runrecord, ablation_harness, train.cmd, README.md, .codemaker/skills/tool/isaaclab-task-creator
status: open
next: 步骤 1、2、5 已做并验收，步骤 3 取消，步骤 4 仅剩人工裁定：`protocol_anchors.json` 的“v4 现行”口径与旧协议 v1/v2/v4 去留。裁定并处理后删除本项，结论转验收记录。
close_when: `rl_exp/locomotion` 不导入评测，也不导入 `tools`（共享原语 `binding` 除外）；v7 `make_env_cfg()` / `make_runner_cfg()` 导出配置与重构前逐字段等价；`model_5999.pt` 在 `locomotion_eval_v3`、seed 123 下的 robust 评测与基线逐位一致；默认 pytest 全绿；`-m sim` 冒烟全绿；协议锚口径与旧协议已裁定。
evidence: work/v7-workflow-hardening.md, acceptance/records/2026-11-23-v7-standalone-cutover.md
---

## 背景

承接已删除的 `work/active/robot-experiment-architecture-refactor.md`（`21a0bcb` 创建，`1af99c4` 删除）。其中的实验发现与注册、`lines.json` 生命周期、冻结台账已被 v7 单文件实验取代，不再做；本项只承接依赖方向。

真缺陷是 `rl_exp` 核心反向依赖评测与 `tools`，不是目录名：

- 核心指向评测：`train.py:85-86` 在 `--eval` 时导入 `ablation_harness.evaluate`、`experiment_eval`。
- 核心指向 `tools`：`train_record.py:18` 导入 `rl_exp.tools.runrecord.binding`；它是无环的纯 stdlib 原语，保留（见步骤 3）。
- 评测指向核心（`eval.py:341`、`video_matrix.py:223`、`experiment_eval.py:16` 导入 `train_record`）是合理的单向依赖，保留。

## 步骤（每步单独提交、可回滚）

1. 【已做】依赖方向 AST 测试 `rl_exp/locomotion/tests/test_dependency_direction.py`：`rl_exp/locomotion` 不得导入 `ablation_harness`，不得导入 `rl_exp.tools`（唯一例外：`rl_exp.tools.runrecord.binding`，见步骤 3）。已在 `0a13d21` 的 `train.py` 上验证失败（`train.py:85-86`），步骤 2 后通过。
2. 【已做，`eafde73`】删除 `train.py` 的 `--eval`、`--train-only`、`--eval-mode`、`--eval-protocol`、`_strip_eval_flag`、`_latest_checkpoint` 及对评测的导入；训后评测手动跑 `eval.cmd`。`--run-dir` 保留：现有失败退出与已存在目录的子进程测试及 sim 冒烟依赖它指定 Run 路径，不只服务重入。`v7-workflow-hardening` 已完成批次不回改，本步骤取代其“保留兼容别名”条款。
3. 【取消】不移动 `rl_exp/tools/runrecord/binding.py`。它是纯 stdlib、不导入核心与评测，不构成环；`v7-workflow-hardening` 已裁定它原地作为唯一家（50+ 诊断、blender、verify 脚本复用）；`lizard2_round_feet_export.py:181` 把它的路径纳入导出绑定的源件哈希，移动会改变已记录的绑定身份。收益只是目录观感，代价是约 25 处导入加绑定漂移。AST 测试对它开唯一豁免。
4. 退网残留：
   - 【已做】删除 `ablation_harness/judge_semantics.json`：全仓代码零读者，其注记指向的 `check_judge_semantics.py` 与 `test_baseline_contract.py` 均已不存在，且含 6 处指向已不存在模块 `baseline_metrics` 的 `module` 值。恢复来源：删除前提交。
   - 【待人工裁定】`protocol_anchors.json` 的“v4 现行”口径与协议 v1/v2/v4：`test_eval_frame_v2.py:184`、`:299-301` 读 v4，`test_terrain_geometry.py:191` 读 v2，锚表自述“改表是人工批准动作”，协议头声明冻结。改口径或删协议属批准动作，且要同步改上述测试，不在本项自动执行。
5. 【已做】HEAD `85deecd` 逐位评测：产物 `evaluation/2026-11-25_12-48-23_4b780c57/`，退出码 0，与基线 `2026-11-25_12-28-43_1ecba8f6` 的 `eval.json` 仅 `git_rev_lizard`（两处）与 `timestamp` 不同，其余字段逐位相等；九段录像仅核文件齐全。`pytest -m sim` 1 通过（真实一步 PPO、重载、评测 rollout）；默认 pytest 与 verify 专项 43 项通过。


## 非目标

- 不改名 `ablation_harness`，不动 `sys.path` 补丁与平铺导入：改名与目录归位（机体资产并入机体目录、测试归位、`mdp/`、两级嵌套、去 `rl_exp/` 前缀）不属本项，有需求时另立项。
- 不引入 `RobotSpec` / `BaseExperiment` / 注册表（沿用 `v7-workflow-hardening` 非目标）。
- 不抽独立 `env.py`；评测的套件地形、`apply_eval_mode`、高度射线是有意覆盖，不是分叉。

## 验证

- 每步只跑离线闸门：依赖方向 AST 测试、`make_env_cfg()` / `make_runner_cfg()` 导出配置重构前后逐字段比对（`test_v7_experiment.py` 已有相关断言）、默认 pytest。
- 全部完成后跑一次逐位评测：`model_5999.pt` + `locomotion_eval_v3` + seed 123 robust，与回填后的基线逐位对比。基线已在 HEAD `a7bab8990fc0` 重跑并回填（见 `v7-workflow-hardening` Batch 3.3）；对比时 `git_rev_lizard`、`timestamp` 预期不同，其余字段须相等。`eval.json` 的 `terrain_evidence.definition.module` 写着包路径，任何包改名都会改它，这是不改名的又一依据。
- 旧 Run 回读：`provenance.json` 的 `repo_path` 与 `experiment_files` 回读路径不因本项变化失效，改动前后各验一次。

## 风险

- 在 `v7-workflow-hardening` 收尾前动手，逐位对比失去基线；本项排在其后。
- 步骤 4 删协议或锚表条目前，须确认没有现存评测记录依赖它们读回。
