# Harness 基线标签闸门修复独立复审（2026-10-28）

## 适用范围

- 不带执笔历史的新上下文审核 `harness-baseline-tag-gate` 的自测输出修复、真实 CLI 和调用方。
- 本闸只检查本地标签名称与声明，不证明标签指向、远端或行为能力。

## 验收条件

- 自测末行判词和夹具计数准确；默认检查正常；缺标签与无法读取基线行的破坏测试红、恢复后绿。
- 审核时发现足以让不合法基线静默通过或误导诊断的缺陷时，不得关闭。

## 结果

**不通过安全审核。** 原关闭条件的两条破坏测试、自测输出及 18 个夹具计数通过，但发现版本号截断误放行和 Git 失败时的误导诊断。

- `baseline_tag_problem()` 用已有 `harness-v1.11.0` 测试 `v1.11.0.1` 和 `v1.11.0-invalid`，两者均返回 `None`：正则只匹配合法前缀，错误声明会静默通过。
- 模拟 `_git_tags()` 返回 `None`，`main()` 返回 1，但同时错误声称真实基线标签缺失；Git 读不到时不能断言标签不存在。
- 实际自测退出 0，末行 `check_version_docs: self-test OK (18 fixtures)`；默认检查退出 0，末行 `VERSION_DOCS_OK`。18 为五组夹具 4、3、4、2、5 的总数。
- 隔离仓测试原关闭条件中的 `v9.9.9`、移除基线冒号，默认及自测模式均退出 1，恢复后退出 0。还原修复前代码时，自测末行回归断言失败；当前修复通过。模拟自测夹具自身失败退出 1。
- 自测成功后仍执行默认检查，默认检查失败返回非零；自测失败会提前返回，不继续默认检查。离线套件按退出码判定但成功摘要末行变为自测判词；pre-commit 使用默认模式。外部依赖旧末行者仍有兼容风险。

## 证据引用

- 执行记录及可复读的隔离测试代码：`acceptance/records/2026-10-28-harness-baseline-tag-gate-execution.md`；首次独立审核：`acceptance/records/2026-10-28-harness-baseline-tag-gate-review.md`。
- 落点：`rl_exp/tools/verify/check_version_docs.py` 的 `_BASELINE_LINE`、`baseline_tag_problem`、`_git_tags` 与 `main`；调用方 `rl_exp/tools/verify/offline_suite.py`、`hooks/pre-commit`。
- 隔离测试复读（只在临时目录创建副本）：

```bat
python -B -c "import pathlib; p=pathlib.Path('acceptance/records/2026-10-28-harness-baseline-tag-gate-execution.md'); exec(compile(p.read_text(encoding='utf-8').split('```python',1)[1].split('```',1)[0], 'execution-record-test', 'exec'))"
```

## 未覆盖边界

- 临时仓复制真实本地标签名称，不复现标签指向或远端；远端锚点另归 `work/active/harness-version-anchor-missing.md`。
- 两处缺陷须补修复前失败、修复后通过的回归测试；修复与证据变化后须新上下文重新独立审核。
- 本次未运行完整离线套件，不证明外部调用方兼容。
