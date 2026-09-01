# Ablation Harness——版本与挂账（SSOT）

> 本文件 = 评测台（`ablation_harness/`）版本与待办的唯一真源。
> 评测台是共享测量仪器：服务所有机器人家族（换家族后仍在），**不进任何家族
> 的配方版本管理**（versioning.mdc「范围边界」）。修订纪律沿用 versioning.mdc
> B 节（vN.M.K + 本文件修订记录 + 版本号开头的 commit message），**编号独立
> 于家族配方版本**（冻结 tag：家族叫 `lizard-vN`，这里叫 `harness-vN`）。
> 仓根 `PLAN.md` 挂账 #12 只留指针。

## 当前状态

- 协议版本：**locomotion_eval_v1**（`protocols/locomotion_eval_v1.yaml` 冻结；`results/` 按协议目录组织）
- 代码基线：v1（= 本文档建立时的树态：Phase A 修复已落，commit 5725396；更早历史 git 考古）
- 部署形态：仓根独立目录 + `E:\IsaacLab\ablation_harness` junction（挂账 1 完成后删）

## 版本历史

| 版本 | 日期 | 摘要 | 依据 |
|---|---|---|---|
| v1 | 2026-09-01 | 建档基线：协议 locomotion_eval_v1 冻结（早于本文档，git 考古）+ Phase A 修复（eval 快照 / DR 锁面 / smoke 断言，commit 5725396） | — |

## 挂账

| # | 事项 | 优先级 |
|---|---|---|
| 1 | G3 剩余：`eval.py:69-77`（"故意不 resolve" junction hack）/ `run_ablation.py:36` / `_log_dir_for_tag` glob 改读 `RL_ISAAC_ROOT`（缺省向上探测 `source/isaaclab` + `logs`）→ 删 `E:\IsaacLab\ablation_harness` junction，评测台完全脱离 IsaacLab 树 | 🟡 闸门依赖已解，纯收尾 |

## 升级触发（防"永远不升"）

harness 代码高频变更 / 多机器人共用 / 评测协议 v2 出现时 → 目录化 `versions/harness/vN/`（协议 yaml + NOTES 进版本目录，与家族配方同款冻结纪律）。

## 与 rl_exp 的契约（单向消费，改动必跑闸门）

- 任务 id：suites 引用 rl_exp 注册的 gym 任务（`import isaaclab_tasks` 触发注册链）
- DR 事件名：`components/dr_controller.py` ↔ rl_exp `play_utils.py` 9 事件清单，`check_dr_parity` 双向看守
- 机器人块：ArticulationCfg parity（family vs teacher）

→ 任何 harness 代码变更后必跑 `rl_exp\tools\verify\run_offline_checks.bat`（闸门红 = 不提交）。

## 修订记录

| 日期 | 版本 | 变更 |
|---|---|---|
| 2026-09-01 | v1 建档 | 版本文档从 lizard v3 计划 §7.5 与仓根 PLAN.md 挂账 #12 剥离至此（用户拍板：仓库不拆、只拆版本文档） |
