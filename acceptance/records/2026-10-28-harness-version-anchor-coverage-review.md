# Harness 历史覆盖补证独立复审（2026-10-28）

## 适用范围

- 不带执笔历史的新上下文审核 `harness-version-anchor-missing`，按用户选择分别核对历史 v1.10.0 快照与现行 v1.11.0 锚点。
- 逐笔范围限定 `0c3ec25..925d997`，不声称覆盖之后所有测量语义变更。

## 验收条件

- 历史跨度逐笔有可核验覆盖或排除依据，现行基线声明所指证据准确；远端锚点及独立耦合对照成立。

## 结果

**不通过。** 远端锚点、25 笔新补证和耦合复现均通过；现行基线段仍把旧记录描述为完整逐笔排除表，而旧表并不完整，新补证仅在事项 evidence，未纠正该声明。

- `ablation_harness/HARNESS.md` 基线段指向 `acceptance/records/2026-10-10-harness-baseline-coverage-fill.md`，称该记录列出这一段不计入编号的改动及理由。反例 `f0d0401` 仅新增结果文件，新补证列有排除理由，旧表未列；另有版本声明、文档指针及结果提交漏列。
- 独立以 `git log --name-only` 和逐笔 `git show` 核对新补证 25 行；包括 `b3243ff` 的足端采集与判据、`c7ed3cd` 的场景驱动、`9fccecf` 的汇总身份拒表；新表与补丁相符。结果数据不因此变成行为能力证据。
- 远端 `harness-v1.9.0`、`harness-v1.10.0`、`harness-v1.11.0` 分别指向 `0c3ec25ac92c0aaaf8bd8755ea26e43f0022eefb`、`925d99781a177d36b62db215f0ed949811f4f17a`、`07e5d2f3cf4e5de302b4c28b57f6c9e27cc6e23d`；版本主题与两个祖先关系符合。历史快照为 v1.10.0，当前声明为 v1.11.0；当前工作树不等同于 v1.11.0 标签树。
- 协议字段核对：v2/v3、v4/v5 的 `judge`、`criteria`、`report_only` 分别相等，v4 比 v2 多四项报告；这是声明字段一致，不证明混表许可或物理表现。
- 新上下文用 host Python 复现同输入耦合对照：`601f1d6^` 为 `5.995425592306487e-18`，`601f1d6` 为 `1.0`。

## 证据引用

- 新逐笔表：`acceptance/records/2026-10-28-harness-version-anchor-coverage-repair.md`；历史补证与可复读耦合代码：`acceptance/records/2026-10-10-harness-baseline-coverage-fill.md`。
- 现行声明：`ablation_harness/HARNESS.md` 代码基线段；前次复审：`acceptance/records/2026-10-28-harness-version-anchor-independent-review.md`。
- 命令：`git log --name-only 0c3ec25..925d997 -- ablation_harness`、逐笔 `git show`、`git ls-remote --tags origin`、`git show -s --format="%H %s"`、`git merge-base --is-ancestor`；耦合代码复读入口在历史补证。

## 未覆盖边界

- 修正现行基线段的证据指向与措辞，不回写冻结历史记录或改动已推标签；证据变化后独立复审。
- 资产失败路径的授权仍归 `work/active/asset-fail-path-live-check.md`；未跑 GPU rollout，也未审核 v1.10.0 至 v1.11.0 的完整覆盖。
