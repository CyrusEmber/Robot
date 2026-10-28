# Harness 覆盖声明指针修正（2026-10-28）

## 适用范围

- `harness-version-anchor-missing` 的现行基线段证据指向修正；不改历史补证、已推标签、协议或实现。

## 验收条件

- 现行声明不再把历史不完整排除表描述为逐笔完整，并能直接找到经逐笔补齐的证据。

## 结果

- `ablation_harness/HARNESS.md` 保留历史补证对判分语义、整腿扩列及几何来源的证据作用，明确其排除表不完整，并指向 `acceptance/records/2026-10-28-harness-version-anchor-coverage-repair.md` 的完整历史区间逐笔表。
- 本次是文档指针与措辞修正，不改变 v1.11.0 基线、历史 v1.10.0 标签、协议文件或测量语义；未声称 v1.10.0 至 v1.11.0 的全部变动已经逐笔覆盖。

## 证据引用

- 发现及复审：`acceptance/records/2026-10-28-harness-version-anchor-coverage-review.md`。
- 补齐表及复读命令：`acceptance/records/2026-10-28-harness-version-anchor-coverage-repair.md`。
- 检查入口：`python -B rl_exp/tools/verify/check_version_docs.py`、`python -B rl_exp/tools/verify/check_work_docs.py`。

## 未覆盖边界

- 当前声明和新证据需由不带执笔历史的新上下文独立复审；本记录不是审核结论。
- 不证明历史覆盖之外的测量语义、标签之后工作树与标签树相同、物理行为或策略性能。
