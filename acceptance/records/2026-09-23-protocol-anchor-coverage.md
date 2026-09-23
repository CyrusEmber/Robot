# 协议锚的整目录覆盖（`next` ① 前半，2026-09-23）

## 适用范围

- 落点：`ablation_harness/protocol_anchors.json`（补 5 条锚 + 写入"主体从树上读、豁免是规则"的 why）、
  `rl_exp/tools/verify/test_eval_frame_v2.py`（新用例 `test_every_protocol_is_anchored_or_declared_legacy`）。
- 属 `work/active/freeze-maintenance-simplification` 的 `next` ① **前半**（整目录完整性）。
- **不覆盖**：`next` ① 后半（阈值以外的协议字段逐一反证）；legacy `baseline_flat_v1/v2/v3` 不锚——按规则豁免。

## 验收条件

1. 主体**从树上读**（不是声明式）：新协议到达即被覆盖，不靠有人记得登记。
2. 豁免必须是**规则**，不是第二张要手维护的清单。
3. 反证先行：只加规则、不补锚时必须红并点名具体文件。
4. 不新增套件入口（折进既有 `[23]`）。

## 结果

**一、活体缺口（无需造变异）**：`lizard2_flat_v2.json` 于 **2026-09-23** 随 `6de88a0`
（"Fix two defects in the banded criteria, add the settled reader"）落地——**锚表当天已经存在**，而核验当时只报
`ok 2 protocol(s) match the bytes their approval records` + `ALL_EVAL_FRAME_V2_TESTS_PASSED`，对这份新协议**零意见**。
即：锚表上线**第二天**就被人绕过一次，形状与 golden 那次（新线的锁不在表里）完全同类，那是这一类的第三次。

**二、规则**：主体＝`ablation_harness/protocols/` 下全部 `.json`/`.yaml`；豁免＝**规则**——
其 `(name, version)` 落在 `baseline_metrics.LEGACY_PROTOCOLS`（即 `Baseline-Flat-v1/v2/v3`，早于锚存在的协议）；
其余必须出现在 `anchors` 里，否则红。

**三、反证（先红后绿）**：

```
# 只加规则、未补锚 ⇒ 点名 5 份
AssertionError: protocols/lizard2_flat_v2.json: on disk but neither anchored nor declared legacy -- ...
                protocols/locomotion_eval_v2.yaml: on disk but neither anchored nor declared legacy -- ...
                protocols/locomotion_eval_v1.yaml: ...   protocols/locomotion_eval_v3.yaml: ...
                protocols/locomotion_eval_v4.yaml: ...

# 补 5 条锚 ⇒
  ok 7 protocol(s) match the bytes their approval records
  ok 7 protocol(s) anchored, 3 declared legacy, none uncovered
ALL_EVAL_FRAME_V2_TESTS_PASSED
```

7 + 3 = 10 = 盘上协议数。legacy 三份被**规则**豁免（不是我另列一张表）。

**四、口径互证**：`locomotion_eval_v4.yaml` 的锚摘要 `f33328ddf66e03e8…` 与评测记录里的
`eval_protocol.digest` 逐字相同 ⇒ 锚用的是与记录侧同一套算法（`binding.sha256_file`），不是又一套。

**五、套件**：`ALL_OFFLINE_CHECKS_PASSED (47/47 in 47.4s)`；`[23]` 标签未改、入口数未增。

**六、非阈值字段同样被抓（补证，2026-09-23 同日）**：锚按**字节**判，因此不挑字段。改 v4 的
`post_failure_velocity`（`"zero"` → `"keep"`，一个非阈值字段）⇒
`AssertionError: protocols/baseline_flat_v4.json: the bytes moved since they were approved`；还原 ⇒
`ok 7 protocol(s) match…` + `ALL_EVAL_FRAME_V2_TESTS_PASSED`，且 `git diff` 对该文件为空。
⇒ **不需要逐字段枚举**：一处证明已覆盖全部字段（命令窗口、`bands`、`terminal_frame` 等同一机制）。

## 证据引用

```
$ python -c "... binding.sha256_file(protocols 下 10 份) ..."
baseline_flat_v1.json 6477f94d…   baseline_flat_v2.json 2dd810df…   baseline_flat_v3.json a288b898…
baseline_flat_v4.json 4b069c59…   lizard2_flat_v1.json 4078869f…    lizard2_flat_v2.json c37851db…
locomotion_eval_v1.yaml 5dcf491b… locomotion_eval_v2.yaml 4c13f5aa… locomotion_eval_v3.yaml 00f8c067…
locomotion_eval_v4.yaml f33328dd…

$ git log --date=short --format="%h %ad %s" -2 -- ablation_harness/protocols/lizard2_flat_v2.json
6de88a0 2026-09-23 Fix two defects in the banded criteria, add the settled reader

（反证与绿判词见"结果"节；套件 47/47）
```

## 未覆盖边界

- 阈值以外的字段**已补证**（见"结果"节六：锚按字节判，一处证明即覆盖全部字段），不再列为未覆盖。
- **`LEGACY_PROTOCOLS` 本身无摘要看守**：它是现在唯一的豁免真源，谁把一份新协议加进那对白名单，核验就不会出声。
- 只认 `.json`/`.yaml`：未来出现 `.yml` 会被静默忽略（当前无此情况）。
- 豁免按 `(name, version)` 判，**改文件名不影响豁免**；反之，改 `name`/`version` 字段会让一份已锚协议"变成"另一份身份。
- 我给 `locomotion_eval_v1/v2/v3` 写的理由是"superseded by v4"，但**没有核**这三份是否真的不再被任何路径读取（未查读者）。
- 锚表仍无自身摘要看守（表被改、协议未动时不红），靠 git 审查。
