# cfg_lock 体量与"锁正文该不该读"判定（2026-09-21）

## 适用范围

`versions/lizard/` 三份配方锁（`main` / `parkour` / `baseline` 的 `cfg_lock.json`）与全仓共享的
`versions/cfg_baselines.json`：① 体量是否构成成本、是否该缩；② 正文是否该被当作阅读对象（人 / AI）。
判定对象是**闸门产物本身**，不是任何配方。触发本记录的追问：锁为什么这么大 → 有没有必要缩小 →
要不要改成只存 hash → 要不要定规则不让 AI 读正文。

## 验收条件

判定依据必须可复算，且**每一项都能用一条命令重测**：

1. 压缩比与 parse 时长（体积是否构成存量 / 时间成本）；
2. 条目内与条目间的重复度（"多余"到底多在哪）；
3. 闸门是否已经在用"先比 digest"这条快路；
4. 正文被哪些工具当**数据**读（决定删掉正文的连带面）。

**重新考虑的条件（任一成立再动，届时先加只读汇总，不是先缩）**：注册任务数翻到约四倍（锁到
~10 MB、parse 到百毫秒量级）；出现必须通读锁正文的真实需求；再有人提"只存 hash"。

## 结果

**判定 ①：不缩减锁内容。** 体积不构成成本；"只查 hash"**已经是现状**（闸门先比每条 entry 的
`digest`，相等即结束，只有不等才去打印字段路径），所以这条不是待做的优化；而"只存 hash"是净亏 ——
删掉的是漂移**定位**能力与 `--update` 的"我即将吸收什么"打印（反事故机制本身），并牵连四个把正文当
数据读的消费者。省下的只是压缩后约一成的字节。

**判定 ②：读取纪律落规则 —— 已落。** 同日写入 `.codemaker/rules/versioning.mdc` 的红线段：配方锁
正文是闸门产物、不是阅读对象，取用与判定只走 `check_cfg_lock.py` 输出，改动只走
`--update --line <线> --reason`。

**明确不做的**：不为"让关闭看起来有机制支撑"而额外造体积阈值断言；不改任何 golden、不重锚；不做零散
瘦身（要缩须整批 + 重锚 + 偏差声明）。

## 证据引用

实测（2026-09-21，`main/cfg_lock.json` = 2,484,439 B / 97,268 行 / 32 条 entry）：

| 读数 | 值 |
|---|---|
| zlib -9 后 | 241,885 B（**9.7%**） |
| `json.loads` | 23.5 ms |
| 32 条 snapshot | 全 distinct，合计 1,429,052 B（占正文 99%） |
| `env.scene.contact_forces` | 32 条同内容（1 种 / 32），209,472 B |
| `env.sim` | 2 种 / 32，128,386 B |
| 共享叶同步漂移（模拟 `contact_forces.update_period`） | 64 行 / 32 hunk |
| 历史真实改动 | 8/8、24/24 行（`git log --numstat`） |

闸门路径（"只查 hash 已是现状"的出处）：`rl_exp/tools/verify/check_cfg_lock.py` 的 `verify_entries`
先比 digest（:291-305），不等才 `_print_diff`；:455 写明要"concrete changed field paths, not just
'the digest moved'"；`--update` 拒写时要求先看字段路径（:502）。

锚层**本来就**是 hash-only：`rl_exp/tools/verify/check_golden_frozen.py` 的 FROZEN 表（四份锁的 sha256 +
`FROZEN_REVS`，拒自动重算）、`rl_exp/versions/obs_protocol_anchors.json`。即"只存 hash"这件事在**锚层**
已成立，而锚层要的是拒绝、不是解释；正文这一层的职责是**解释**。

把正文当数据读的消费者（删正文的连带面）：`rl_exp/tools/runrecord/manifest.py`（`build_entry` /
`walk_diff` / `combination`）、`check_obs_protocol.py`、`check_pxr_leak.py`、`check_recipe_build.py`。

## 未覆盖边界

- 只实测 `versions/lizard/` 一族三份锁；其它家族若出现，结论按同一形态外推，未实测。
- 只覆盖 `cfg_lock.json` 类产物；`vN/asset_lock`、`obs_protocol_anchors.json` 仅作"同类锚层"引用，未逐项测量。
- 判定 ② 的规则文本**无机器闸门**："谁逐字读了正文"不可判。可守的只有两条侧面 —— 手改正文（digest
  自洽检查）、锚被移动（FROZEN）。**因此该纪律不是可验证项，属声明面规则。**
- 未设体量上限、未加阈值断言：到触发条件时先加只读汇总（各线条目数 / 体积 / 漂移有无），而不是先缩。
- 本记录不含"该不该把结论抄进事项"的口径 —— 该口径归 `AGENTS.md`。
