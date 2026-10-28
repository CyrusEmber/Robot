# 指针扫描修复独立复审（2026-10-28）

## 适用范围

- 不带修复执笔历史的新上下文审核 `work-doc-hint-scan-scope` 的实际实现、原关闭条件、原审核及修复记录。
- 本次审核不修改历史版本文档，也不以格式检查替代行为审核。

## 验收条件

- 对照原关闭条件：冻结证据类不被扫描，活文档中的过时指针仍报 HINT；原缺陷应有真实来源和有效破坏测试。
- 核对修复是否改变原验收口径，及其对 HINT 信道的影响。

## 结果

**需用户裁决，不能按原条件关闭。** 修复使版本树活文档及相似目录的过时指针可被扫描，但它也扫描冻结版本文档：原事项明确将版本记录列为冻结证据，修复后的条件却允许这些记录产生 HINT。不能以变更后的条件通过代替原条件通过。

- 历史恒噪豁免现在仅覆盖 `acceptance/records/`；版本树中冻结文档、可回填的 NOTES 和提案文档均被扫描。目录、资产锁或退休状态不能可靠区分所有活路由与历史痕迹，详见 `.codemaker/rules/versioning.mdc` 关于提案、冻结、退休与结果回填的约束。
- 本次默认检查报告 9 条版本树 HINT，其中包括历史引用和同一 Markdown 链接两次命中；其中 `rl_exp/versions/lizard2/main/v2/PLAN.md` 的旧事项路径属于已退休版本，`rl_exp/versions/lizard/ACCEPTANCE.md` 则有需要人工判断的引用。不能将所有版本树提示一概作为活路由或历史痕迹。
- 原缺陷真实：`34c4917` 关闭 `runtime-acceptance-v3`，其历史验收记录保留旧路径；未复原当时完整工作树，不独立确认历史提示计数。
- 复跑修复记录中的内存还原旧范围命令：`WORK_DOCS_SELF_TEST_DRIFT (7)`，退出码 1；修复后自测和实际检查通过。撤掉记录豁免后出现 `FALSIFIER: the pointer scan read a dated evidence record`、`WORK_DOCS_SELF_TEST_DRIFT (1)`，退出码 1。
- 两次检查之间工作区事项数有变化；独立默认检查输出 `WORK_DOCS_OK (94 item file(s))`。计数反映执行时工作树，不作为固定基线。

## 证据引用

- 原事项条件可由 `git show 19f2366:work/active/work-doc-hint-scan-scope.md` 复核；原验收：`acceptance/records/2026-10-10-work-doc-hint-scope.md`。
- 原审核：`acceptance/records/2026-10-28-work-doc-hint-scope-review.md`；修复的红绿及破坏测试复读命令：`acceptance/records/2026-10-28-work-doc-hint-scope-repair.md`。
- 实现与自测：`rl_exp/tools/verify/check_work_docs.py` 的 `_FROZEN_REFS`、`_inbound_hints` 和 `self_test`。

## 未覆盖边界

- 等待用户决定：接受版本树全扫描及历史 HINT 人工判别的口径变更；或继续寻找并验证冻结证据边界，同时不漏活文档。
- 若接受新口径，仍须明确保留历史噪声的人工判断责任，不能声称原条件已满足；若继续修复，证据变化后须新上下文复审。
- 本记录不是关闭结论；未逐条判定所有版本树 HINT。
