# harness 代码基线覆盖复审：逐笔对照抓出一笔未点名（2026-10-10）

## 适用范围

- 对象：`work/active/harness-version-anchor-missing.md` 的复审，在**新上下文**（不带执笔会话历史）里按 `close_when` ①②③④ 与落点核判，不以事项正文或补证记录的完成摘要代替证据。
- 前序：`2026-10-10-harness-version-anchor-review.md`（退回 `in_progress`）与补证 `2026-10-10-harness-baseline-coverage-fill.md`。
- 本次只判锚点、覆盖声明与可复现性，不改实现、不改已推 tag；覆盖声明的补齐留在退回后的 `in_progress` 里做。

## 验收条件

1. `close_when` ①：远端同时有两枚 tag，分别指向对应版本声明提交，提交主题以版本号开头，且旧基线提交是新基线提交的祖先。
2. `close_when` ②：`ablation_harness/HARNESS.md` 的代码基线为 v1.10.0、无敞口段、所列记录路径都存在。
3. `close_when` ③：逐笔对照 `git log 0c3ec25..925d997 -- ablation_harness` 与覆盖声明，每一笔被点名或写明为何不计入，且声明不与实现落点矛盾。
4. `close_when` ④：审核者在本地独立复跑补证记录里的耦合对照，读数与 `evidence` 一致。

## 结果

**①②④ 通过，③ 缺一笔 ⇒ 不通过，事项退回 `in_progress`。**

### ① 锚点

远端读数与祖先关系符合 `close_when`：

| tag | 远端指向 | 提交主题 |
|---|---|---|
| `harness-v1.9.0` | `0c3ec25ac92c0aaaf8bd8755ea26e43f0022eefb` | `harness-v1.9.0: declare the version, log the anchor it needs` |
| `harness-v1.10.0` | `925d99781a177d36b62db215f0ed949811f4f17a` | `harness-v1.10.0: declare the baseline, and anchor it together with v1.9.0` |

`git merge-base --is-ancestor 0c3ec25 925d997` 退出码 0。

### ② 声明、记录与落点

- `ablation_harness/HARNESS.md:29` 代码基线为 v1.10.0；扫「待补 / 漏 / 未覆盖 / 敞口 / TODO」全文件只剩 `:33` 的"分开做就有一半会漏"，非敞口段。
- 基线段列出的四份记录、补证记录与本审核记录均存在。
- 落点抽查与补证记录一致：`baseline_metrics.py:866`（`_LEG_TOKENS` 五 token）、`:894`（腿关节集合）、`:923`（`spine_leg_coupling` 写入；补证记录 ② 写作"读数 `:916`"，那是配对构造行、写入在 `:923`，同处一段，不构成矛盾）。
- 补证记录 ① 引的八处行号（`:344`、`:368`、`:448`、`:472`、`:497`、`:512`、`:1279`、`:1411`）逐行 blame，分别归 `6de88a0` 与 `1fba2b8`，归属正确，无矛盾。
- 类规则核对属实：逐字段打印 `lizard2_flat_v1..v5` 的 `judge` 与 `criteria` ⇒ `v3`/`v4`/`v5` 与 `v2` 的判据数值逐字相同、`judge` 同为 `baseline-criteria-banded-settled-1`，故"身份副本不改判据数值"成立。

### ③ 逐笔对照：`d60bd3f` 既未点名也无排除理由

span 内非 `results/` 的 harness 提交 19 笔，逐笔对齐后 18 笔落在声明里（点名、排除表或类规则），剩一笔：

| 提交 | 改了什么 | 现状 |
|---|---|---|
| `d60bd3f`（2026-09-22，`Lay the banded criteria's declarations into the baseline reader (not frozen yet)`） | `baseline_metrics.py` +34：`CRITERION_KINDS` 加 `tracking_banded_v1`/`displacement_banded_v1`/`non_foot_load_sum_v1`、新增 `BANDED_JUDGE_ID`、`JUDGE_KINDS` 身份→种类绑定、`GATE_ORDER` 加 `no_non_foot_load_sum` | 既不在 `HARNESS.md` 基线段，也不在补证记录 ①②③ 任何表 |

- 这是改**测量语义**的一笔（kind 集合即判词面，绑定决定协议能否到达新语义），不是纯文件搬移。
- 补证记录自己写着"同一跨度里其余的 `ablation_harness/` 改动逐笔列出，附不计入的理由 —— 不列出的空白下次还会被当成漏项"，故该记录自身验收条件 ④ 也未满足。
- 性质是"没提到"，不是"说错"：语义与落点已由 ① 的 kind 名与八处 blame 覆盖，故不需要新裁决、不涉编号。
- 附带：补证记录 ① 末段的"协议 `v3/v4/v5`"指 `lizard2_flat_v3`/`-v5`，未带家族前缀，易被读成 `locomotion_eval` / `baseline_flat` 的同名编号；那一句也在 ①，而两笔副本提交属"不计入本编号"，位置应归 ③ 表。

### ④ 耦合对照复现

同一段代码在本上下文独立执行（仓内 Git 历史 + 已安装 torch，不起仿真、不落脚本文件），读数与补证记录、审核记录逐位相同：

| reader 源码 | `spine_leg_coupling` |
|---|---|
| `601f1d6^` | `5.995425592306487e-18` |
| `601f1d6` | `1.0` |

## 证据引用

### 锚点与记录路径

```bat
git ls-remote --tags origin "harness-v1.9.0" "harness-v1.10.0"
git show -s --format="%H %s" 0c3ec25 925d997
git merge-base --is-ancestor 0c3ec25 925d997
git log --format="%h %s" 0c3ec25..925d997 -- ablation_harness/*.py ablation_harness/protocols ablation_harness/judge_semantics.json ablation_harness/protocol_anchors.json
git blame -L 344,344 -L 368,368 -L 448,448 -L 472,472 -L 497,497 -L 512,512 -L 1279,1279 -L 1411,1411 ablation_harness/baseline_metrics.py
git show --stat --format="=== %h %s" d60bd3f 7168a86 4d7aa26 97f50cb f0d0401 2dda131 ed40aaf
git show --format="=== %h %s" --unified=2 d60bd3f -- ablation_harness/baseline_metrics.py
```

### 协议副本逐字段对照（声明一致）

用 `python ablation_harness\host_paths.py --python` 返回的解释器读 `ablation_harness/protocols/lizard2_flat_v*.json`，打印每个文件的 `judge` 与 `criteria` 全文；结论：`v3`/`v4`/`v5` 与 `v2` 的判据**逐字数相同**。

### 耦合对照（行为，可复读）

代码与 `2026-10-10-harness-baseline-coverage-fill.md` 的证据节相同；本次以该解释器 `-B` 执行临时副本后删除，未留文件。

## 未覆盖边界

- 不判这些判据与报告项**是否好用**（阈值合理性、数值质量归各家族版本记录）。
- 未跑 GPU rollout；耦合对照只证"同一输入下报告计算改变"，不产任何策略性能结论。
- 本轮不改任何已落盘记录、不改覆盖声明文本：补 `d60bd3f` 一笔与协议全名由执笔侧在退回的 `in_progress` 里做，之后仍需新上下文再审 ③。
- 不对 tag 区间之外的后续 `ablation_harness/` 改动做完整性判断。
