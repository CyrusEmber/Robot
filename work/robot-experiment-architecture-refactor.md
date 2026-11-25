---
id: robot-experiment-architecture-refactor
title: 运行与评测依赖方向整理
scope: rl_exp/locomotion, rl_exp/tools/runrecord, ablation_harness, train.cmd, README.md, .codemaker/skills/tool/isaaclab-task-creator
status: open
next: 重构前基线已回填（HEAD `a7bab8990fc0`，`evaluation/2026-11-25_12-28-43_1ecba8f6/`）。做步骤 1：先写依赖方向 AST 测试并确认当前代码上失败。
close_when: `rl_exp/locomotion` 不导入评测与 `tools`；v7 `make_env_cfg()` / `make_runner_cfg()` 导出配置与重构前逐字段等价；`model_5999.pt` 在 `locomotion_eval_v3`、seed 123 下的 robust 评测与回填后的基线逐位一致；默认 pytest 全绿；`-m sim` 冒烟全绿。
evidence: work/v7-workflow-hardening.md, acceptance/records/2026-11-23-v7-standalone-cutover.md
---

## 背景

承接已删除的 `work/active/robot-experiment-architecture-refactor.md`（`21a0bcb` 创建，`1af99c4` 删除）。其中的实验发现与注册、`lines.json` 生命周期、冻结台账已被 v7 单文件实验取代，不再做；本项只承接依赖方向。

真缺陷是 `rl_exp` 核心反向依赖评测与 `tools`，不是目录名：

- 核心指向评测：`train.py:85-86` 在 `--eval` 时导入 `ablation_harness.evaluate`、`experiment_eval`。
- 核心指向 `tools`：`train_record.py:18` 导入 `rl_exp.tools.runrecord.binding`。
- 评测指向核心（`eval.py:341`、`video_matrix.py:223`、`experiment_eval.py:16` 导入 `train_record`）是合理的单向依赖，保留。

## 步骤（每步单独提交、可回滚）

1. 依赖方向 AST 测试，放进 `rl_exp/locomotion/tests/`（`pytest.ini` 的 `testpaths` 只覆盖这里）：`rl_exp/locomotion` 不得导入 `ablation_harness`，不得导入 `rl_exp.tools`。在当前代码上必须失败。
2. 删除 `train.py` 的 `--eval`、`--train-only`、`--eval-mode`、`--eval-protocol`、`--run-dir`（仅服务重入）、`_strip_eval_flag`、`_latest_checkpoint` 及对评测的导入；训后评测手动跑 `eval.cmd`。保留 `train.py:162` 的最终 checkpoint 存在性检查。同步改 `test_v7_experiment.py:130`（去掉 `--train-only`）、`:288-301`、`:353-374`（删 `--eval` 与 `--train-only` 相关测试，保留异常退出子进程测试）、`README.md:7`、`.codemaker/skills/tool/isaaclab-task-creator/SKILL.md:27`。`--train-only` 为破坏性删除，先确认无外部调用方。`v7-workflow-hardening` 已完成批次不回改，本步骤取代其“保留兼容别名”条款。
3. `rl_exp/tools/runrecord/binding.py` 单文件移到 `rl_exp/locomotion/`，改约 20 处导入（`tools/`、`ablation_harness/`、测试、`blender/scripts/`），删空的 `tools/runrecord/`。`train_record` 与 `experiment_eval` 各留原处，不合并；不抽共享实验加载函数（重复仅 4 行，无分叉史）。AST 测试转绿。
4. 退网残留：纠正 `protocol_anchors.json` 的“v4 现行”口径（现役口径是 v3，见 `README.md`、`metrics.py:110`）；协议 v1/v2/v4 先核 `test_eval_frame_v2.py:184`、`test_terrain_geometry.py:191` 的读者再决定删除，冻结协议遵循“改语义 = 新版本”，删除须留恢复来源（tag 或记录）。`judge_semantics.json` 在全仓 `*.py`、`*.cmd`、`*.ini`、`*.yaml` 零引用：先查是否有字符串拼接式读取，无读者则删除，删后跑默认 pytest 与 `eval.cmd` 确认。
5. 全部完成后跑一次逐位评测对比。

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
