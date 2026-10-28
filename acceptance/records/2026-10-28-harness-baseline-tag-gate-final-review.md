# Harness 基线标签闸门最终独立审核（2026-10-28）

## 适用范围

- 不带执笔历史的新上下文审核 `harness-baseline-tag-gate` 的 Tab 缩进修复、关闭条件及真实隔离 CLI。
- 本闸只检查本地标签名称与声明一致，不证明标签指向、远端推送或测量能力。

## 验收条件

- Tab 与混合空格缩进围栏不得吞掉声明；自测、正常 CLI、原缺标签和缺冒号破坏测试及恢复检查可复读。
- Git 失败状态和调用链的失败传播不被修复破坏。

## 结果

**通过。** 四列制表位展开修复了已复现的 Tab 缩进缺陷，未发现本次审核范围内的实际新缺陷。

- 内存还原为旧实现后自测退出 1，报告四个 Tab 反例；当前实现退出 0，`check_version_docs: self-test OK (83 fixtures)`。未修改真实文件。
- `acceptance/records/2026-10-28-harness-baseline-tag-gate-fourth-review.md` 的隔离 CLI 复读退出 0、`failures: []`；Tab 反例的默认和自测两模式均退出 1，恢复后均退出 0。
- `acceptance/records/2026-10-28-harness-baseline-tag-gate-execution.md` 的原隔离回归退出 0、`failures: []`；缺标签、缺冒号两模式均退出 1，恢复后退出 0；隔离套件传播 `FAIL rc=1`。另以原条件的 `v9.9.9` 复测，两模式均退出 1。
- 补测四列制表位、注释、行内跨度及顶层围栏等边界，31 项均符合预期。83 个自测夹具计数含 14 个缩进及围栏组合。
- 真实仓自测退出 0，默认检查通过，末行为自测判词。执行记录保留了前几轮独立审核、破坏及修复证据。

## 证据引用

- 实现与持久自测：`rl_exp/tools/verify/check_version_docs.py` 的 `baseline_tag_problem` 和 `self_test`。
- 隔离破坏和复读命令：`acceptance/records/2026-10-28-harness-baseline-tag-gate-fourth-review.md`、`acceptance/records/2026-10-28-harness-baseline-tag-gate-execution.md`。

## 未覆盖边界

- 不是完整 Markdown 解析器；允许语法与拒绝歧义的范围见代码与执行记录。未知外部调用方对自测末行的依赖未验证。
- 未验证标签指向、远端推送或测量能力；远端锚点另归 `work/active/harness-version-anchor-missing.md`。
- 本次独立审核未运行完整离线套件，也未以真实 Git 解码失败复现；隔离套件失败传播和注入解码失败已验证。
