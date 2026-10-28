# 指针扫描范围独立审核（2026-10-28）

## 适用范围

- 不带原执行会话历史的新上下文，按事项关闭条件、现有实现、自测及原验收记录审核 `work-doc-hint-scan-scope`。
- 审核对象为指针扫描自身的行为，不证明被扫描文档的内容正确。

## 验收条件

- 冻结证据中的过时指针不报 HINT，活文档中的过时指针仍报 HINT。
- 原缺陷有真实来源，撤掉记录豁免的破坏测试能使自测失败。

## 结果

**不通过，退回修复。** 原缺陷真实，原有冻结记录与普通活文档夹具及破坏测试成立；但版本树下的活文档漏扫，目录名前缀相似的活文档也被误排除，不能据此认定活文档边界成立。

- `34c4917` 关闭 `runtime-acceptance-v3` 后，历史记录保留旧路径；在当前树内存撤掉记录豁免后，出现 35 条 HINT，均来自 `acceptance/records/`。未复原当时完整工作树，不独立确认原记录中的历史计数。
- `_FROZEN_REFS` 对 `rl_exp/versions` 的豁免早于本次改动，但其中也有活计划，例如 `rl_exp/versions/lizard2/PLAN.md`。隔离临时目录中，版本树内的活计划夹具带过时引用时无 HINT，同内容的 `notes/live.md` 有 HINT。
- 同一隔离测试中，`acceptance/records-live/` 和 `rl_exp/versions-live/` 因字符串前缀匹配而漏报。当前仓库未发现这两个实际目录；这是夹具复现的边界缺陷，不代表已有实际文件受影响。
- `--self-test` 通过；默认检查为 `WORK_DOCS_OK (93 item file(s))`，无 HINT。内存撤掉 `acceptance/records` 豁免后输出 `FALSIFIER: the pointer scan read a dated evidence record`、`WORK_DOCS_SELF_TEST_DRIFT (1)`，子进程退出码 1。

## 证据引用

- 原记录：`acceptance/records/2026-10-10-work-doc-hint-scope.md`；实现：`rl_exp/tools/verify/check_work_docs.py` 的 `_FROZEN_REFS`、`_inbound_hints`、`self_test`；离线套件入口：`rl_exp/tools/verify/offline_suite.py`。
- 冻结记录与普通活文档自测及破坏测试复读：

```bat
python -B rl_exp\tools\verify\check_work_docs.py --self-test
python -B rl_exp\tools\verify\check_work_docs.py
python -B -c "import sys;sys.path.insert(0,'rl_exp/tools/verify');import check_work_docs as w;w._FROZEN_REFS=('rl_exp/versions',);sys.exit(w.self_test())"
```

- 漏扫读数来自 `tempfile.TemporaryDirectory()` 内构造的文档夹具，直接调用 `_inbound_hints([])`；未改仓库文件。修复须将这些反例纳入可复读自测，验证修复前失败、修复后通过。
- 原记录破坏测试命令打印返回值但不传给进程退出码；上面的命令使用 `sys.exit`，预期退出码为 1。

## 未覆盖边界

- 审核未修改实现，也未定义版本树中哪些文档属于冻结记录；修复时须按实际版本文档语义划定范围。
- 未全面审计所有目录或活指针，前缀相似目录仅通过隔离夹具验证。
- 修复及证据变化后须由新上下文重新审核；本记录不是关闭结论。
