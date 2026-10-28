# Harness 基线声明解析独立复审（2026-10-28）

## 适用范围

- 不带执笔历史的新上下文审核 `harness-baseline-tag-gate` 的最新声明语法、CLI 和隔离破坏测试。
- 本闸只核对本地标签名称与文档声明，不证明标签指向、远端推送或测量能力。

## 验收条件

- 多声明及异常声明不得静默通过；行内代码和注释不能吞掉实际声明；原破坏测试红、恢复绿。

## 结果

**不通过。** 行内代码中的 `<!--` 被先当作跨行 HTML 注释起点，吞掉后续实际声明。合法基线行末带反引号包裹的 `<!--`，下一行再写 `**代码基线**:v9.9.9`，函数返回 `None`，隔离真实默认 CLI 与 `--self-test` 均退出 0。若将同一行内示例置于唯一合法声明之前，两模式均误报 `matched 0 time(s)`、退出 1。

- 声明行末 `<!-- 说明 -->` 的处理也需明确：当前函数返回非法版本。是否支持该语法须在修复中定义并测试。
- 两组执行记录中的隔离回归均退出 0、`failures: []`；原缺标签和删冒号两模式均红，恢复绿。默认检查退出 0，自测末行为 `check_version_docs: self-test OK (45 fixtures)`。
- Git 不可执行、空标签与自测夹具破坏均按预期失败；隔离套件传播 `FAIL rc=1`。自测成功输出末行变化对外部调用者的影响未知。

## 证据引用

- 实现：`rl_exp/tools/verify/check_version_docs.py` 的 `baseline_tag_problem`；现有隔离复读入口：`acceptance/records/2026-10-28-harness-baseline-tag-gate-execution.md`。
- 前次审核：`acceptance/records/2026-10-28-harness-baseline-tag-gate-second-review.md`。

## 未覆盖边界

- 修复行内代码和 HTML 注释交互并定义声明末尾注释语法，验证修前失败、修后通过及真实隔离 CLI；证据变化后新上下文重审。
- 完整离线套件及外部调用方未验证；临时目录已清理，未修改真实 `HARNESS.md`。
