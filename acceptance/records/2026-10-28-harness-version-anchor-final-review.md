# Harness 历史覆盖与现行锚点最终独立审核（2026-10-28）

## 适用范围

- 不带执笔历史的新上下文审核 `harness-version-anchor-missing`，按用户裁决分别验收历史 v1.10.0 快照与当前 v1.11.0 锚点。
- 逐笔覆盖限定 `0c3ec25..925d997`；不把其后的工作树视为 v1.11.0 标签树，也不宣称后续跨度已逐笔覆盖。

## 验收条件

- 现行基线声明准确指向补齐的逐笔表；历史及现行远端锚点、历史跨度覆盖、协议副本与独立耦合对照成立。

## 结果

**通过。** 当前基线段明确旧排除表不完整，并指向新逐笔表；历史和现行基线各自核验，无需回滚或重打标签。

- 远端 v1.9.0、v1.10.0、v1.11.0 标签分别指向 `0c3ec25ac92c0aaaf8bd8755ea26e43f0022eefb`、`925d99781a177d36b62db215f0ed949811f4f17a`、`07e5d2f3cf4e5de302b4c28b57f6c9e27cc6e23d`；主题对应版本，两段祖先关系检查均成功。历史声明及所查快照为 v1.10.0；现行声明与 v1.11.0 标签快照均为 v1.11.0。
- 独立核对历史跨度 25 笔提交与新表，语义归属及非测量排除理由与补丁相符。`b3243ff` 涉足端帧列及判据，`c7ed3cd` 涉逐环境场景命令，`9fccecf` 涉汇总身份拒表；六笔纯结果提交不作为算法能力证据。
- v2/v3、v4/v5 的 `judge`、`criteria`、`report_only` 分别相等；v4 相对 v2 多四项报告。字段一致不证明可混表。
- 使用 host Python 独立复读同输入耦合对照：`601f1d6^` 为 `5.995425592306487e-18`，`601f1d6` 为 `1.0`。相关记录路径存在，现行基线段未发现敞口。

## 证据引用

- 现行声明：`ablation_harness/HARNESS.md` 代码基线段；逐笔表：`acceptance/records/2026-10-28-harness-version-anchor-coverage-repair.md`。
- 前次独立复审及声明修正：`acceptance/records/2026-10-28-harness-version-anchor-coverage-review.md`、`acceptance/records/2026-10-28-harness-version-anchor-declaration-repair.md`。
- `git ls-remote --tags origin`、`git show -s --format="%H %s"`、`git merge-base --is-ancestor`、`git log --name-only 0c3ec25..925d997 -- ablation_harness` 及逐笔 `git show`；耦合复读代码见 `acceptance/records/2026-10-10-harness-baseline-coverage-fill.md`。

## 未覆盖边界

- 未逐笔审核 v1.10.0 至 v1.11.0 的并行历史，未运行 GPU rollout，也未证明物理表现、策略性能或判据质量。
- 资产失败路径授权仍归 `work/active/asset-fail-path-live-check.md`；真实接触标定和正式协议不由本项关闭。
