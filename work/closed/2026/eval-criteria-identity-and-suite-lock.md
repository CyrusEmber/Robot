---
id: eval-criteria-identity-and-suite-lock
title: 判据身份化与套件指纹锁（显式判据 kind + 判分器身份 + 套件两步锁 + 同表条件面）
scope: ablation_harness, rl_exp/tools/verify
status: done
landing: ablation_harness/baseline_metrics.py, ablation_harness/loco_judge.py, ablation_harness/suite_lock.py, ablation_harness/judge_semantics.json, ablation_harness/record.py, ablation_harness/run_ablation.py, ablation_harness/protocols/baseline_flat_v4.json, ablation_harness/protocols/locomotion_eval_v4.yaml, ablation_harness/HARNESS.md
outcome: 两半都收了。① `locomotion_eval_v4` 的套件指纹由 2026-09-22 一次真机打印后人工批注（cfg / 几何 / 环境三项），随后一次不带指纹开关的 v4 冒烟真跑正常落 record，且 `suite.lock` 三项均为 match；② `judge_semantics.json` 现有三个 id 块，locomotion 那块 14 条用例全绿，负控制（改 fixture 的 dwell 而冻结块不动）会红并点名用例。真跑抓出两处只有真跑才看得见的缺陷：`cfg_snapshot.digest` 与 `record.digest` 的**算法前缀拼写差**（已改为按摘要而非拼写比较并加回归），以及 `--print-suite-fingerprint` 的退出路径会跳过 Kit 关停（已改为从 `main()` 返回、交给模块自身的关停路径）。反转条件：日后给 loco 判据加新内核或新派生量，按机制应新增 id 块而非改旧块（本项不算回退）；换机器跑 v4 时锁给 unknown 而非 match，那是设计，不是本项回退。
evidence: acceptance/records/2026-09-22-harness-criteria-and-suite-lock.md
---

## 未覆盖边界（不在此处复述，指向记录）

本项关闭时已知未取到的东西全在 `evidence` 那份记录的「未覆盖边界」里：跨机器一致性、
v4 只有零动作冒烟档位真跑过、`ENV_FIELDS` 封闭列表、用例表只覆盖写下来的用例、
`_physx_version()` 的三个拼法只命中过一个。`diagnostic-run-gate`（同表条件面不含
`policy.kind`）是另一项，仍开着，不在本项范围。
