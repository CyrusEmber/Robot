---
id: robot-experiment-architecture-refactor
title: Lizard2 v7 最小实验闭环与文档流程
scope: rl_exp, ablation_harness, work, acceptance, README.md, AGENTS.md, .codemaker/rules, hooks
status: open
landing: rl_exp, ablation_harness, README.md, work, acceptance
next: 实现者保留旧入口作对照，接通圆足 v7 的训练、PLAY、评测与录像。
close_when: 核对删旧后的 v7 训评、普通试错零手写收尾与已采纳基线的回放。
---

## 目标

研究者复制一个实验文件、改一个奖励权重就能开训。训练自动留痕，评测给出指标与视频，人决定下一步。普通失败可以随本地 Run 清理；采纳的基线应能从一份仓内记录找到当时的代码、资产和权重并重新加载。

## 实验的四步

| 步骤 | 入口与行为 |
|---|---|
| 定义机体 | `rl_exp/robots/lizard2_round_feet.py` 指向圆足 USD/URDF 及相对网格，声明动作关节顺序、执行器分组和默认 PD。现有同名资产目录继续存资产。 |
| 定义实验 | `rl_exp/lizard2_v7.py` 显式选机体，写清观测、动作、奖励、终止、随机化、命令范围及 PPO 参数。复用现有函数，把 v7 实际需要且依赖旧 recipe 的代码移入 `rl_exp/locomotion/`。保留 TRAIN 的随机化和命令范围，PLAY 只覆盖推理所需配置。 |
| 训练 | 目标命令 `train --exp rl_exp/lizard2_v7.py`。独立入口 `rl_exp/locomotion/train.py` 接通 AppLauncher、环境和 PPO runner，失败返回非零状态。允许新文件和未提交改动直接开训，省去 Gym 自动发现、版本登记、训前冻结和逐函数源码校验。 |
| 评测与决策 | 目标命令 `eval --ckpt <checkpoint> --protocol <protocol>`。扩展现有 `ablation_harness/eval.py`，从 Run 取实验配置；旧权重可显式传 `--exp rl_exp/lizard2_v7.py`。真实训练结束后默认跑 robust，nominal 由用户选择。调用现有 `video_matrix.py` 录三档速度 × 三个视角，保留标签、九段原片和合成视频，逐片验看后决定采纳、放弃或继续实验。 |

## Run 自动留下什么

每次运行使用独立目录。训练保留 checkpoint、TensorBoard 日志，并自动写三类材料：

- `resolved_cfg.yaml` 保存 CLI 覆盖后的生效配置和实际 seed。想知道两次实验改了什么，直接 diff。
- `provenance.json` 和 `git.diff` 保存实验入口、HEAD、框架与资产来源，以及暂存和未暂存的代码差异（排除 `*.pt`/`*.usda`/`*.blend`/`*.obj`/`*.stl` 大二进制）。另存实验文件、本次 `sys.modules` 命中的仓内未跟踪 Python 源码，以及实际加载的 `.usda` / `.urdf` 文件 `sha256`（防止路径相同但资产被覆盖）。
- 从运行中的环境读取观测组、有序项名及宽度、动作关节顺序及维度，随 Run 和新 checkpoint 保存。加载时在首个不匹配处报错；历史 v7 权重缺签名时，从旧环境取对照。

评测直接把固定数值项、有效样本数及缺测原因写入 `eval.json`，区分报告项和协议通过门槛。`matrix.json` 索引实际录像工况与片段；eval 和录像各自的 `execution.json` 由启动端写命令、工作目录、起止时间与退出状态。程序只报告实际测到的内容；步态等定性判断来自看片。终端直接展示已有结果，省去 `eval_summary.json`、全局 `LOG.md` 和专用汇总脚本。

## 实验何时需要人写字

| 情况 | 唯一的人工记录 |
|---|---|
| 当天试完，普通失败或放弃 | 零手写文档、零强制提交。看完九宫格即可结束，无需逐片填表。 |
| 有个值得搜索的小教训 | 把实际实验改动提交到 Git，在提交消息写工况和观察，例如“v7 肘部 kp 40→20，本次落地塌陷，弃用”。需要恢复参数时可 revert，原提交仍可用 `git log --grep` 找回。 |
| 采纳基线，或否决一条技术路线 | 在 `acceptance/records/` 写一份短记录，分四段写改动目的、Run 与 checkpoint 位置、关键指标与九宫格逐片看片观察、决定与适用范围。只在采纳基线时，将当时实际运行的源码落实到提交并打一个 tag，确认对应资产可取、权重有保留位置且能加载。 |
| 中途需要续做或交接 | 在 `work/active/<id>.md`（退网后收口为 `work/<id>.md`）写下一步、Run 路径，有阻塞才写阻塞。做完删除；有重大结论时转为上面的一份记录。 |

README 给出四步用法。切换文档流程时，同次更新 `AGENTS.md`、`FILEMAP.md`、`HARNESS.md` 与训后模板，撤下逐 Run 手抄表和普通实验的逐片填表义务（仅采纳基线时写进验收记录）；同步调整 work-ledger、versioning、`check_work_docs.py`、`check_version_docs.py` 及其 `hooks/pre-commit`/离线调用。普通改参免建 PLAN/NOTES 等版本材料，简短待办免脚手架、预算、强制复审与关闭搬运。沿用已有历史记录，无需回填或重分类。精简 B 中的 pytest 耗时、台账成本与批量补历史 tag 试点退出本次实施路径。

## 实施与验收

1. **保留旧入口做一次 v7 对照。** 使用现有 Run `2026-11-03_17-07-29/model_5999.pt`。有同条件旧结果就复用，缺失才用旧 `Lizard2-Flat-v7` 补跑。新入口加载同一权重跑 PLAY，核对同输入的首帧观测、首步动作；交换同宽观测项或动作关节时应拒载。固定资产、框架、协议、seed、环境数、命令段与采样窗口，跑一轮 robust eval，比较有效样本、平地指标与协议判定，其他地形分列。逐片看九宫格，解释影响判定或步态的差异；缺有效样本时对齐仍待验证。[v7 Run 位置](../../rl_exp/versions/lizard2/main/v7/NOTES.md)
2. **证明训练入口能写出可用权重。** 从新入口完成一次 PPO 更新，核对实际生效值、Run 留痕、指标有限值，以及新 checkpoint 保存和重载推理。这个测试只验证训练接线，v7 行为对照始终使用第一步的同一权重。
3. **对齐后一次退网。** 在最后可运行的旧提交打 `archive/pre-refactor`。按真实调用迁出评测和录像仍依赖的共享函数，删除旧 `lizard2_recipe.py`、`recipe_tasks.py`、`cfg_lock.json`、`recipes.json`、`obs_protocol_anchors.json`、退役线目录、专属元检查，以及绑定旧锁与旧构建的 `work/active/` 历史挂账（无需逐个走 `pending_review`），并同步更新 `hooks/pre-commit` 与仓级导航/规则。用删旧后的正常入口复验训练、PLAY、eval 和录像。行为检查统一由 pytest 覆盖现役机体加载、环境构造、签名错序或错维度拒载、一次训推与评测口径。本机大产物清理另行处理，归档 tag 只兜底 Git 已跟踪的内容。
4. **用实际操作验收文档流程。** 普通改参从开训到看完放弃，可以零份 Markdown 收尾；一张交接待办可以正常添加和删除；从一份已采纳基线记录能读懂采纳理由，并用其中的源码 tag、资产和 checkpoint 实际加载策略。复用这些操作验证，无需另建台账。
