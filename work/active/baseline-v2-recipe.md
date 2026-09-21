---
id: baseline-v2-recipe
title: baseline v2（1–3 m/s + 脚板去权限 + 头链触地终止）
scope: rl_exp/versions/lizard/baseline, rl_exp/tasks
status: in_progress
landing: rl_exp/versions/lizard/baseline/v2/baseline_params.yaml, rl_exp/versions/lizard/baseline/v2/PLAN.md, rl_exp/tasks/baseline_recipe.py, rl_exp/tasks/baseline_mdp.py, rl_exp/tasks/agents/rsl_rl_ppo_cfg.py, rl_exp/versions/recipes.json
next: ① 冻结本版验收协议 = 用 `baseline_flat_v3.json`（命令 box + 相对门槛 + 接触轴；几何门槛已降为诊断——实测它放过颈部入地 7.7 mm 的策略）。v3 已落地并跑通 **v2 管路**（零动作，`results/baseline_flat_v3/v2-recipe-smoke/`），仍差"协议与启动闸门绑定"（见 `eval-protocol-before-training`）；② 探针断言新接口（命令落在区间且逐 env 采样、动作 22 维、脚关节无动作权）并真跑；③ 以上齐了才开训，训后按 v3 验收并回填 `baseline/v2/NOTES.md`
close_when: 两次真跑留证后关闭——(a) 探针在新任务上按新断言通过，且旧断言在 v2 上会红；(b) v2 训完后按 v3 产出报告并回填 NOTES 的结果表与结论。**排序事实（2026-09-21，用户定）**：开训早于**启动闸门**、但不早于协议（v3 于 `1183b2f` 冻结在前）⇒ 记"闸门后补"，不得事后改协议迁就结果；探针复测若跳过，要在这里写明"未做"
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
第四次重锚见 `acceptance/records/2026-09-21-baseline-cfg-lock-rebaseline.md`）。**验收侧仍差一步 ⇒ 本版尚未开训**：
协议 v3 已能判 v2（管路已用零动作跑通），但还没有"无协议即拒绝开训"的闸门。
注意区分：先前"v2 协议判 pass"判的是 **v1 策略**，与训练 v2 无关（事实更正见
`acceptance/records/2026-09-21-baseline-eval-v2-support-and-protocol-v3.md`）。
阻塞与缺口另见 `baseline-eval-measurement-trust`、`floor-contact-attribution`；
流程定义见 `baseline-eval-pipeline-restructure`。

## 未覆盖边界

两条相对门槛（归一跟踪误差、位移/期望位移）是本版新定、无仓库先例，冻结前需确认；脚 duty 等步态量只作诊断；
资产不动（脚关节保留 PD 与执行器组），"脚板能否被动移动"不在本项内。
