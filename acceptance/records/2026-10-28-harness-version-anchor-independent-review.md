# Harness 基线锚点与覆盖独立审核（2026-10-28）

## 适用范围

- 不带执笔历史的新上下文审核 `harness-version-anchor-missing` 的历史锚点、覆盖声明与耦合对照；不改实现或已发布标签。
- 覆盖检查限定 `0c3ec25..925d997`；不把该范围之外的实现自动判为已覆盖。

## 验收条件

- 原关闭条件要求远端旧锚点、v1.10.0 基线、区间内逐笔覆盖声明及独立耦合读数均成立。

## 结果

**不通过。** 旧锚点与耦合复读通过，但逐笔覆盖记录仍有空白；当前基线已升至 v1.11.0，原条件要求的当前 v1.10.0 不成立，不能通过回滚历史满足。

- 远端 `harness-v1.9.0` 指向 `0c3ec25ac92c0aaaf8bd8755ea26e43f0022eefb`，`harness-v1.10.0` 指向 `925d99781a177d36b62db215f0ed949811f4f17a`；主题分别以对应版本号开头，前者是后者祖先。
- 当前 `ablation_harness/HARNESS.md` 为 v1.11.0，基线段引用的六份记录存在，未发现该段敞口。历史 `5aaeb4b`、`7cbabee^` 和 `7cbabee` 快照中的基线均为 v1.10.0，故旧审核读数有历史依据。后续 `07e5d2f` 升为 v1.11.0，远端 `harness-v1.11.0` 指向该提交，且 `925d997` 是其祖先；升版依据见 `acceptance/records/2026-10-23-lizard2-contact-com-calibration.md`。旧条件不能自动解释为现行基线满足 v1.10.0。
- 按 `git log --name-only 0c3ec25..925d997 -- ablation_harness` 核对共 25 笔：`d60bd3f`、`1fba2b8`、`6de88a0`、`88f6bd9` 在补证①；`601f1d6` 在②；`4ef9fb4`、`f1e6421`、`4d7aa26`、`7168a86`、`862e39f`、`d086fc4`、`21ec102` 在③；`3bce24c` 在③提及并由基线段和关联记录覆盖。
- `925d997`（版本声明）、`ed40aaf` 和 `2dda131`（work 指针）、`f0d0401`、`97f50cb`、`525cc42`、`f5a2007`、`775ed15`、`e015cc4`（仅结果数据）未在三表逐笔列出。本次检查可分别给出非测量实现的排除理由，但补证记录未写明。`b3243ff`（帧格式与足端判据）、`c7ed3cd`（定点场景驱动）、`9fccecf`（身份拒表）在基线段有功能概述，仍未在三表逐笔对齐；不能把概述当逐笔覆盖。
- `lizard2_flat_v1` 的 judge 是 banded，v2–v5 是 settled；v2–v5 的 `criteria` 解析后相等，v3 与 v2、v5 与 v4 的 `judge`、`criteria`、`report_only` 分别相等。v4/v5 比 v2 多四项报告列；这是声明字段比较，不证明物理表现或不同记录可混表。
- 独立复跑同一输入耦合对照：`601f1d6^` 为 `5.995425592306487e-18`，`601f1d6` 为 `1.0`，与既有记录一致；未启动仿真。

## 证据引用

- 原补证及可复读耦合代码：`acceptance/records/2026-10-10-harness-baseline-coverage-fill.md`；前次独立复审：`acceptance/records/2026-10-10-harness-coverage-per-commit-review.md`。
- 独立核对入口：

```bat
git ls-remote --tags origin "harness-v1.9.0" "harness-v1.10.0" "harness-v1.11.0"
git show -s --format="%H %s" 0c3ec25 925d997 07e5d2f
git merge-base --is-ancestor 0c3ec25 925d997
git merge-base --is-ancestor 925d997 07e5d2f
git log --name-only 0c3ec25..925d997 -- ablation_harness
git show 5aaeb4b:ablation_harness/HARNESS.md
git show 7cbabee^:ablation_harness/HARNESS.md
git show 7cbabee:ablation_harness/HARNESS.md
```

- 协议字段来自 `ablation_harness/protocols/lizard2_flat_v1.json` 至 `lizard2_flat_v5.json` 的 `judge`、`criteria`、`report_only`；行为复读代码在上述补证记录。

## 未覆盖边界

- 执行者须补逐笔归属或排除理由，不改写既有冻结历史证据；完成后重新独立审核。
- 关闭条件的时间语义须明确：不回滚现行基线或标签，不把历史审核冒充当前读数。历史与当前的取证范围和判据变化须有明确决定。
- 未跑 GPU rollout，耦合对照不评价策略性能或判据质量；不检查旧跨度之外的测量语义完整性。
