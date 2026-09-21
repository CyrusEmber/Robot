---
id: baseline-v2-recipe
title: baseline v2 配方（命令 1–3 m/s + 脚板去动作权限）与其验收冻结
scope: rl_exp/versions/lizard/baseline, rl_exp/tasks, ablation_harness, rl_exp/tools/verify
status: in_progress
landing: rl_exp/versions/lizard/baseline/v2/baseline_params.yaml, rl_exp/versions/lizard/baseline/v2/PLAN.md, rl_exp/tasks/baseline_recipe.py, rl_exp/tasks/agents/rsl_rl_ppo_cfg.py, rl_exp/versions/recipes.json
next: ① 冻结本版验收协议（协议族下一版：命令由定点改区间、逐帧记录**实际下发**命令、两条门槛改相对口径）；② 更新开训前探针使其断言新接口（命令落在区间且逐 env 采样、动作 22 维、脚关节无动作权），并真跑一次探针；③ 启动闸门接上（协议不存在/摘要不符 ⇒ 拒绝开训，见 `eval-protocol-before-training`）；④ 以上齐了才开训，训后按新协议验收并回填 `baseline/v2/NOTES.md`
close_when: 执行者观察两次真跑——（a）探针在新任务上按新断言通过，且改动前的探针断言在 v2 上会红；（b）v2 训练跑完后按冻结协议产出报告，`baseline/v2/NOTES.md` 的结果表与结论据此回填。两个观测都留证据（日志/报告路径）后本项关闭；若训练在冻结前被启动，本项保持 open 并记录"提前开训"这一事实，不得事后改协议去迁就结果
depends_on: baseline-eval-protocol-gap, eval-protocol-before-training
evidence: acceptance/records/2026-09-20-baseline-flat-eval-protocol.md
---

## 问题与本次范围

同线第二版，只加两个变量：命令窗口 `1.0–3.0 m/s`（框架 10 s 重采样）与脚板关节失去动作权限
（动作 26 → 22 维）。配方元素列表与 v1 完全相同，差异全部落在 `baseline_params.yaml`，所以
"v2 是什么"能在一份文档里读完。已落地并通过闸门：`check_cfg_lock`（v1 两项 golden 未变，
证明动作组参数化是值保持的重构）、`check_recipe_build`（v2 的差异声明逐条与实测一致）、
`check_version_docs`（四件套 + 血统边 `base.json` = v1）。

## 当前状态

配方与文档已就位；**验收侧未就位**，因此按 `baseline/v2/PLAN.md` §验收 的硬前置，**本版尚未开训**。
另记一处顺带修掉的记录缺陷：v2 有自己的 runner cfg（独立日志目录 + 声明 10000 iter），
v1 那跑"声明 3000、实际用 CLI 覆盖成 15000"因此不再复现。

## 未覆盖边界

门槛的两条相对口径（归一跟踪误差、位移/期望位移）是本版新定的，无仓库先例，需在冻结前确认并承担
"标定不当"的风险；脚 duty 等步态量仍只作诊断。资产不动（脚关节保留 PD 与执行器组），所以
"脚板能否被动移动"不在本项回答范围内。
