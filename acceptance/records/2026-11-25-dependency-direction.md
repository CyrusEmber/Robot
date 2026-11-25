# 训练核心不再依赖评测：依赖方向整理与 v3 现行裁定

- 日期：2026-11-25
- 范围：`rl_exp/locomotion/train.py`、`rl_exp/locomotion/tests/`、`ablation_harness/protocol_anchors.json`、`ablation_harness/judge_semantics.json`、`README.md`、`.codemaker/skills/tool/isaaclab-task-creator/SKILL.md`
- 结论：`rl_exp/locomotion` 不再导入评测，也不导入 `tools`（纯 stdlib 的 `rl_exp.tools.runrecord.binding` 除外）。重构前后 v7 评测逐位一致。现行评测协议是 `locomotion_eval_v3`，四份协议全部保留。

## 为什么做

核心反向依赖评测：`train.py` 在 `--eval` 时导入 `ablation_harness.evaluate` 与 `experiment_eval`，并以子进程重入自身，靠 `--run-dir`、`_strip_eval_flag`、`_latest_checkpoint` 把训练与评测串起来。评测依赖训练记录（`train_record`）是合理的单向依赖，保留。

## 改动

- 删 `train.py` 的 `--eval`、`--train-only`、`--eval-mode`、`--eval-protocol`、`_strip_eval_flag`、`_latest_checkpoint`；训后手动跑 `eval.cmd`。`--run-dir` 保留，失败退出测试、已存在目录测试和 sim 冒烟用它指定 Run 路径。提交 `eafde73`。
- 新增 `rl_exp/locomotion/tests/test_dependency_direction.py`：AST 扫 `rl_exp/locomotion`，禁止导入 `ablation_harness` 与 `rl_exp.tools`，仅豁免 `binding`。已在 `0a13d21` 的 `train.py` 上验证失败（`train.py:85-86`），改后通过。提交 `85deecd`。
- 删 `ablation_harness/judge_semantics.json`：全仓代码零读者，其注记指向的 `check_judge_semantics.py`、`test_baseline_contract.py` 已不存在，6 处 `module` 指向已不存在的 `baseline_metrics`。恢复来源为删除前提交。提交 `85deecd`。
- 更正 `protocol_anchors.json` 的 `reason`：协议字节零改动，不构成锚表批准动作。提交 `26a403a`。

## 未做与理由

- 不移动 `binding.py`：它是纯 stdlib、不导入核心与评测，不构成环；`lizard2_round_feet_export.py:181` 把它的路径纳入导出绑定的源件哈希，移动会使已记录的绑定身份漂移；50 余个诊断、blender、verify 脚本复用它。
- 不改名 `ablation_harness`：`eval.json` 的 `terrain_evidence.definition.module` 写着包路径，改名会改变评测记录。
- 不抽共享实验加载函数：重复仅 4 行（`train.py` 与 `experiment_eval.py`），无分叉史。

## 协议裁定

现行是 **v3**：`eval.py:52`、`evaluate.py:96` 默认 v3，README 评测命令用 v3，`metrics.py:110` 写"current protocol is v3"，`results/` 仅存 v3 记录。

- v4：冻结未采用，无任何 Run 或结果命名它。它是唯一携带 `suite_expected` 的协议，`test_eval_frame_v2.py:176-205` 以真实文件钉该指纹，删除会使这条闸门失去被测对象。
- v2：保留，供旧记录复读，并承担 `test_terrain_geometry.py:184` 的 v3-vs-v2 差分证明。
- v1：保留，供旧记录复读。v1 到 v2 的唯一语义变更是采样帧（v1 丢终止帧，dwell 终止的 episode 可能漏记 fall），出处为 `locomotion_eval_v2.yaml` 文件头。

## 验证

模型 `model_5999.pt`，位于 Isaac Lab 根下 `logs/rsl_rl/lizard2_v7/2026-11-03_17-07-29/`，协议 `locomotion_eval_v3`，seed 123，`robust`，`--exp rl_exp/lizard2_v7.py`。

| 运行 | 源码 | 产物（该 Run 下 `evaluation/`） |
|---|---|---|
| 重构前基线 | `a7bab8990fc0` | `2026-11-25_12-28-43_1ecba8f6/` |
| 重构后 | `85deecd7bac5` | `2026-11-25_12-48-23_4b780c57/` |

- 两次 `eval.json` 结构化对比仅 `git_rev_lizard`（两处）与 `timestamp` 不同，六项全局指标及其余字段逐位相等。基线与 11-23 的 `5b9bf541d27f` 那次相比，另有 `terrain_evidence.definition.module`（`rl_exp.tasks.terrain_geometry` → `ablation_harness.terrain_geometry`）不同，已记入 [v7 显式入口切换](2026-11-23-v7-standalone-cutover.md)。
- 九段录像只核文件齐全，未逐帧复核。
- 默认 `pytest` 通过；`pytest -m sim` 1 通过（真实一步 PPO、重载、评测 rollout，约 137 s）；`test_eval_frame_v2.py` 加 `test_terrain_geometry.py` 17 项通过；verify 专项 43 项通过。

## 适用范围

此记录只证明训练核心与评测之间的导入方向和 v7 评测数值未变。环境装配、实验加载、机体资产位置、`sys.path` 补丁与平铺导入均未改。
