---
id: baseline-pre-make-record-check
title: baseline 线下一次启动复验 pre_make（v1 首跑记录半截的根因待定）
scope: rl_exp/tools/runrecord/manifest.py, rl_exp/versions/lizard/baseline
status: open
landing: rl_exp/tools/runrecord/manifest.py
next: 下一次 baseline 线启动（v2 首跑）后立刻 `python -m rl_exp.tools.runrecord.manifest --verify <run 目录>`：三阶段齐全且 0 failure ⇒ 判定为 2026-09-20 12 点那次代码状态的产物，本项关（`pre_make` 的根因**不追**）；若再现 `pre_make recording failed: AttributeError: 'NoneType' object has no attribute 'strip'`，它是活的，按缺掉的字段（`argv`、repo rev）把那次调用栈定位到具体哪个 `.strip()` 接的 `None`，或判定为启动链改走 `launch_recipe.py` 后的新形状并另立事项
close_when: 一次复验读数即可关；读数若仍不完整，把"哪个调用抛、为何 None"讲清，或另立活跃事项承接，本项不带着未解释的 `AttributeError` 关闭
evidence: acceptance/records/2026-09-21-baseline-v1-run-record-gap.md
---

## 当前状态

未开工，等一次启动。已知事实（读数在 evidence 里）：88 个 run 中只有 2026-09-20 12 点窗口的两条
baseline run 是半截的，failure 同为 `pre_make` 的 AttributeError；同任务 09-18 的 run 与同日 14:45 起的
teacher run 都完整 ⇒ 是那段代码状态的产物，不是机制常态。baseline 线此后没再起过 run，**现状未复验**。

## 未覆盖边界

本项只复验"记录是否完整"，不修 `manifest.py` 的字段口径、不做重建评级（归 `verified-rebuild-rating`）、
不改 `params/` 与 `checkpoints.json`。若 v2 走 `launch_recipe.py`，复验的是那条链，不是 v1 那条
（两者不同则本项的判定要写明这一层）。
