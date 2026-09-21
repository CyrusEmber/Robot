---
id: baseline-v2-recipe
title: baseline v2（1–3 m/s + 脚板去权限 + 头链触地终止）
scope: rl_exp/versions/lizard/baseline, rl_exp/tasks
status: in_progress
landing: rl_exp/versions/lizard/baseline/v2/baseline_params.yaml, rl_exp/versions/lizard/baseline/v2/PLAN.md, rl_exp/tasks/baseline_recipe.py, rl_exp/tasks/baseline_mdp.py, rl_exp/tasks/agents/rsl_rl_ppo_cfg.py, rl_exp/versions/recipes.json
next: ① 冻结本版验收协议（协议族下一版：命令由定点改区间、逐帧记录实际下发命令、两条门槛改相对口径；**几何门槛不得背书 `≥ −0.01 m`**——实测它放过颈部入地 7.7 mm 的策略，与探针的"逐帧 > 0"不一致，口径归 `baseline-eval-protocol-gap` 拍板后再冻结）；② 探针断言新接口（命令落在区间且逐 env 采样、动作 22 维、脚关节无动作权）并真跑；③ 启动闸门接上（见 `eval-protocol-before-training`）；④ 以上齐了才开训，训后按冻结协议验收并回填 `baseline/v2/NOTES.md`
close_when: 两次真跑留证后关闭——(a) 探针在新任务上按新断言通过，且旧断言在 v2 上会红；(b) v2 训完后按冻结协议产出报告并回填 NOTES 的结果表与结论。若开训发生在冻结之前，保持 open 并记"提前开训"这一事实，不得事后改协议迁就结果
depends_on: baseline-eval-protocol-gap, eval-protocol-before-training
evidence: acceptance/records/2026-09-20-baseline-flat-eval-protocol.md
---

## 问题与本次范围

同线第二版，只加三个变量：命令窗口 `1.0–3.0 m/s`（框架 10 s 重采样）、脚板关节失去动作权限（26 → 22 维）、
头链**触地终止**（`chest_.*`/`neck_.*` 竖直反力 > 1 N 即终止，dwell 0；原"10% 体重持续 0.5 s"被接触抖动
击穿——66% 的帧压过阈值却从未连续 0.22 s）。配方元素列表与 v1 相同，差异全在 yaml。

## 当前状态

配方与文档已就位并通过闸门（`check_cfg_lock` 两轮都证明 v1 两项 golden 未变 ⇒ 参数化是值保持的重构，
参数改名也碰不到 v1；`check_recipe_build` / `check_version_docs` / `test_contact_load_dwell_term` 均过；
第四次重锚见 `acceptance/records/2026-09-21-baseline-cfg-lock-rebaseline.md`）。**验收侧未就位 ⇒ 本版尚未开训**：
v2 协议在真跑上判 **pass**，两条新门槛弱于开训前探针（见 `baseline-eval-protocol-gap`）。
阻塞与缺口另见 `baseline-eval-measurement-trust`、`floor-contact-attribution`；
流程定义见 `baseline-eval-pipeline-restructure`。

## 未覆盖边界

两条相对门槛（归一跟踪误差、位移/期望位移）是本版新定、无仓库先例，冻结前需确认；脚 duty 等步态量只作诊断；
资产不动（脚关节保留 PD 与执行器组），"脚板能否被动移动"不在本项内。
