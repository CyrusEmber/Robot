---
id: baseline-pre-make-record-check
title: baseline 线下一次启动复验 pre_make（v1 首跑记录半截的根因待定）
scope: rl_exp/tools/runrecord/manifest.py, rl_exp/versions/lizard/baseline
status: superseded
landing: rl_exp/tools/runrecord/manifest.py
outcome: 本项的唯一触发条件是"baseline 线下一次启动"，该线随退役清理消失、不会再起 run ⇒ 复验动作永久不可达，剥离性动作由清理项接管；半截记录的事实仍归 evidence 的记录。
superseded_by: retired-family-code-prune
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
