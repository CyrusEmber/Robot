---
id: parkour-yaw-reinterpretation
title: parkour 线 yaw 取角缺陷：其记录是否重解释（已裁决）
scope: rl_exp/tasks, rl_exp/versions/lizard/parkour
status: done
landing: rl_exp/tasks/parkour_mdp.py, rl_exp/tools/verify/test_baseline_contract.py, rl_exp/versions/lizard/parkour/v1/NOTES.md
outcome: 裁决为"无可重解释"（2026-09-22），依据是本项原前提被推翻：该线**从未训练**——盘上 `logs/rsl_rl/lizard_parkour_climb_v1/` 只有一个 run 目录 `2026-09-17_17-02-16`，其中只有 `run_manifest.json`，内容是退休线拒启（`lifecycle.allowed=false`、`failures` 一条、`stages` 止于 `pre_make`），无 checkpoint、无 eval；`ablation_harness/results/` 下无本线产物 ⇒ 三选一（保留现状/重解释/判废）失去对象。处置：`_yaw_from_quat` 缺陷**保持不修**（线已退休、env 建不出来），白名单条目保留并改为已裁决理由；该线 `NOTES.md` 结论节写明"未训练 + `heading_error` 不可引用"；`baseline/v1/NOTES.md` 里"parkour 线有训练 run"这句错误声明已更正并附裁决。观测收口 = 该线记录与 baseline 侧口径不再互相矛盾，白名单的"已知坏"理由仍在。
evidence: rl_exp/tools/verify/test_baseline_contract.py, rl_exp/versions/lizard/parkour/v1/NOTES.md, rl_exp/versions/lizard/baseline/v1/NOTES.md
---

## 问题与本次范围

`parkour_mdp.py` 的 `_yaw_from_quat` docstring 写 `(x, y, z, w)`、算的是 `(w, x, y, z)` 分支 ⇒ 对 xyzw 输入
恒约等于 π；`PositionCommand` 有 4 处建在它上面（目标采样 `abs_dir = base_yaw + rel_dir` 与 `heading_err`）。
本项要裁的不是修法（同 baseline 侧处方），而是**这条线已入库读数的含义**要不要改。

## 落点（这条为什么算已关闭）

- **原前提不成立**：本项原写"该线有训练 run"，实测只有一份拒启 manifest（`lifecycle.allowed=false`，
  `stages` 止于 `pre_make`）：该线**没有任何读数**，无论重解释还是作废都无对象。
- 缺陷保持白名单登记不修：`rl_exp/tools/verify/test_baseline_contract.py` 的 `_YAW_EXTRACTIONS_ALLOWED`
  保留该项、理由改为已裁决（线退休 + 从未训练）。
- 该线记录写明状态：`rl_exp/versions/lizard/parkour/v1/NOTES.md` 结论节。
- 上游错误声明已更正：`rl_exp/versions/lizard/baseline/v1/NOTES.md` 的跨线发现段。

## 未覆盖边界

**不改 `parkour_mdp.py`**（改代码属实施，且该线 env 已建不出来）。若该线将来复活或复用 `PositionCommand`，
缺陷仍在 ⇒ 那时按 baseline 侧处方修，本项不复用为"已修"依据。缺陷对主线与 baseline 线无影响：
4 处调用点全在 parkour 自己的命令项里。
