---
id: project-simplification-b
title: 测试套件、台账与历史入口的独立精简评估
scope: rl_exp/tools/verify, rl_exp/versions, work, acceptance, .codemaker/rules
status: open
landing: rl_exp/tools/verify, rl_exp/versions, work, .codemaker/rules
next: Codex 在独立切片用现有 manifest 反例对照 pytest 与原入口的覆盖和耗时。
close_when: 新上下文核验三项精简的证据、取舍及后续归属。
---

## 当前范围

现役入口、显式 v7、续训、冻结与单文件试点由[架构重构](robot-experiment-architecture-refactor.md)承接。此项独立验证测试套件、台账和历史入口的维护收益。回放修复、本机产物和资产处置归[诊断产物事项](diagnostic-artifact-lifecycle.md)。

## 下一步

- **pytest 先做单模块试点。** `test_run_manifest.py` 的 `main()` 用例须显式接入，选现成破坏样例验证新旧入口都报错，再比较同机耗时。全量迁移、撤手写 `CHECKS` 和元闸门按试点收益另排。需要干净进程的检查继续保持隔离。
- **文档先减重复。** 当前 work 关闭时保留结论指针，结果归 `acceptance/records/`。用一次实际检索测重复填写和查找成本，再决定是否合并和同步改规则。核对 `ARCH_PLAN.md` 等归档散文的读者，按实际用途调整检查频率。
- **历史按已有承诺处置。** 未实施提案保留可查路径，以 `lizard/main/v15` 为例。已有复跑承诺的版本核对相应历史入口和材料，按现有可用锚复跑。补 tag 按确需的版本单独裁决，同时保留现役拒绝启动的行为。

各切片留改前改后证据和回退点。切换失败时回到上一可用入口，保留失败现场和实际运行数据。

## 关闭条件

- 新上下文对照验收记录核验 pytest 的实际断言与成本、台账检索成本、历史入口及复跑承诺。
- 有收益的改动各自留验收和回退落点。全量 pytest、单记录和补 tag 依各自收益及裁决推进，未完动作保留承接。
