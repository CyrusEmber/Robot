# 2026-09-23 真复位帧掩码：现有真跑语料里不可达（生存门槛只有绿侧）

## 适用范围

- 对象：固定窗口验收器的"**真复位帧不进门槛**"这条路径，在**现有真跑语料**里能不能取到样本
- 语料：`ablation_harness/results/**/eval.json` 全部 14 份（v1 线 3 份、v2 线 6 份 v3 协议 + 5 份 v2 口径、
  lizard2 3 份），零动作 / 随机 checkpoint / 未训 / 随机策略 / 训练 9999 与 13999 iter 都在内
- 覆盖：语料普查读数、"造不出真样本"的原因、以及该路径现在还靠什么背书
- 不覆盖：判据逻辑本身（归 `ablation_harness/baseline_metrics.py` 的合成回归与
  `acceptance/records/2026-09-21-baseline-eval-measurement-contract.md`）；不覆盖阈值依据

## 验收条件

- 要么有一份**真早终止**记录（`term ≠ time_out`），在其上读一次复位帧掩码；
- 要么给出"不可达"的证据：语料普查 + 为什么这批策略造不出，且把该路径当前的背书来源写明。
- 不许以"合成回归过了"当作"该路径在真跑上验过"——两者不是同一件事，这是本记录存在的理由。

## 结果

普查：14 份 `eval.json` 的 `first_episode_timeout_fraction` **全部 = 1.0**。
零动作（`baseline_flat_v3/v2-recipe-smoke`）、随机 checkpoint（`baseline_flat_v2/collector-check-random`）、
未训/随机策略（`collector-check-untrained`/`-sampled`）、训练后的 9999/13999 iter——**没有一份出现提前终止**。

原因：`Lizard-Baseline-Flat-Play-*` 的提前终止项是**基座接触**（`base_contact`，v2 另加 `head_load_contact`），
而这批策略在平地 20 s 窗口内既没把 `base_link` 压到 1 N、也没让头链触地 ⇒ 不是"没去找"，是这批**策略不会倒**。
要造出真样本就得在采集路径里做一次**受控摔倒注入**（外力/推倒），那是新机制，不是再挑一条策略。

该路径当前的背书：`rl_exp/tools/verify/test_baseline_contract.py` 的合成回归（掩码语义与门槛语义），
**判据级**。真跑级的接线（采集器把一个真复位标进帧记录）本轮无样本。

## 证据引用

- 普查读数：`ablation_harness/results/**/eval.json` × 14（逐个读 `gates.survival.first_episode_timeout_fraction`）
- 验收侧前序记录：`acceptance/records/2026-09-21-baseline-eval-measurement-contract.md`
- 判据级背书：`rl_exp/tools/verify/test_baseline_contract.py`、`ablation_harness/baseline_metrics.py`
- 采集侧：`ablation_harness/baseline_eval.py`、`ablation_harness/baseline_frames.py`
- 同源缺口（口径侧）：`acceptance/records/2026-09-23-baseline-v2-first-run.md` 的"照实写的两处缺口"第 1 条
  ——存活与姿态两条门槛在本线真跑里同样只有绿侧

## 未覆盖边界

- **采集侧把真复位标进帧记录这件事，仍无真跑样本走过**；本轮由所有者决定不为它另立活跃事项（2026-09-23），
  即：这个洞是**已知并接受**的，不是被遗忘的。要补，需要一次受控摔倒注入的采集跑。
- 本记录不声称"该路径是错的"：合成回归已覆盖判据语义，未覆盖的只有采集到判据之间那一段布线。
- 只在平地、这批资产与这批策略上成立：换地形/换资产/换终止集合后"倒不了"这个前提要重测。
