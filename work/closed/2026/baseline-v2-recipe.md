---
id: baseline-v2-recipe
title: baseline v2（1–3 m/s + 脚板去权限 + 头链触地终止）
scope: rl_exp/versions/lizard/baseline, rl_exp/tasks
status: superseded
landing: rl_exp/versions/lizard/baseline/v2/baseline_params.yaml, rl_exp/versions/lizard/baseline/v2/PLAN.md, rl_exp/tasks/agents/rsl_rl_ppo_cfg.py, rl_exp/versions/recipes.json
outcome: 线已退休，产物已判 pass；余下的 ②（探针按新接口复测）的断言对象与运行入口随本迭代的代码清理删除 ⇒ 不再有可执行动作，剥离由清理项接管，观察记录仍归 evidence 的两条记录。
superseded_by: retired-family-code-prune
depends_on: eval-protocol-before-training
evidence: acceptance/records/2026-09-20-baseline-flat-eval-protocol.md, acceptance/records/2026-09-23-baseline-v2-first-run.md
---

## 问题与本次范围

同线第二版，只加三个变量：命令窗口 `1.0–3.0 m/s`（框架 10 s 重采样）、脚板关节失去动作权限（26 → 22 维）、
头链**触地终止**（`chest_.*`/`neck_.*` 竖直反力 > 1 N 即终止，dwell 0；原"10% 体重持续 0.5 s"被接触抖动
击穿——66% 的帧压过阈值却从未连续 0.22 s）。配方元素列表与 v1 相同，差异全在 yaml。

## 当前状态

配方与文档已就位并通过闸门（`check_cfg_lock` 两轮都证明 v1 两项 golden 未变 ⇒ 参数化是值保持的重构，
参数改名也碰不到 v1；`check_recipe_build` / `check_version_docs` / `test_contact_load_dwell_term` 均过；
第四次重锚见 `acceptance/records/2026-09-21-baseline-cfg-lock-rebaseline.md`）。
**已开训并于 2026-09-23 按协议 v3 首跑判定 `pass`**（结果与边界见 `baseline/v2/NOTES.md` 与首跑记录）；
仍差的两件：开训前的**探针复测**（见 `next` ②），以及"无协议即拒绝开训"的闸门
（归 `eval-protocol-before-training`）。
注意区分：先前"v2 协议判 pass"判的是 **v1 策略**，与训练 v2 无关（事实更正见
`acceptance/records/2026-09-21-baseline-eval-v2-support-and-protocol-v3.md`）。
阻塞与缺口另见 `baseline-eval-measurement-trust`、`floor-contact-attribution`；
流程定义见 `baseline-eval-pipeline-restructure`。

## 未覆盖边界

两条相对门槛（归一跟踪误差、位移/期望位移）是本版新定、无仓库先例，冻结前需确认；脚 duty 等步态量只作诊断；
资产不动（脚关节保留 PD 与执行器组），"脚板能否被动移动"不在本项内。
