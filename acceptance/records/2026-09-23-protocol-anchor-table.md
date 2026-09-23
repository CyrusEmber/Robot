# 协议批准锚：字节变化必须显式批准（2026-09-23）

## 适用范围

- 落点：**新增** `ablation_harness/protocol_anchors.json`（协议文件 → sha256 + 理由）；核验折进**既有**入口
  `rl_exp/tools/verify/test_eval_frame_v2.py`（套件 `[23]`）的新用例 `test_protocol_anchors_match_the_files_they_pin()`。
- 覆盖两份协议：`protocols/baseline_flat_v4.json`、`protocols/lizard2_flat_v1.json`。
- 已发布的 `judge_semantics.json` id 块**未动**（按 owner 指示：那里保持原样）。
- **不覆盖**：`protocols/` 的**整目录完整性**（新协议到达而未登记仍静默，见末节）；legacy `v1–v3` 与
  `locomotion_eval_*.yaml`（4 份）未锚；阈值以外字段未逐一反证。

## 验收条件

1. 协议文件字节变化、而表未同步更新 ⇒ **失败**（owner 指定的试点：v4 的 `threshold` 0.2 → 0.25）。
2. 反向也要红：表里有条目、盘上没文件 ⇒ 失败（照第 2 步第 2 类的双向纪律）。
3. 每条锚必须带理由：无 `reason` 的条目不算记录过审查。
4. 折进既有入口：套件入口数与 `MAX_CHECKS` 不增。
5. 摘要来自仓里唯一的文件摘要实现（`binding.sha256_file`），不新写一份。

## 结果

**表**（`ablation_harness/protocol_anchors.json`，键为相对 `ablation_harness/` 的路径）：

```json
"anchors": {
  "protocols/baseline_flat_v4.json":  {"sha256": "4b069c59…", "reason": "Frozen at the criteria-identity change…"},
  "protocols/lizard2_flat_v1.json":   {"sha256": "4078869f…", "reason": "Frozen when the lizard2 line's protocol landed…"}
}
```

表头 `why` 里写明 owner 强调的那条边界：**"把门放开之后说文件与表一致，绝不说变更被批准过"**——
"editing this table is the approval act, and it is a human one: pasting the digest the gate prints is
bookkeeping, not review. Clearing the gate afterwards says the file and the table agree -- never that the
change was approved."

**核验**：`binding.sha256_file`（仓内唯一文件摘要实现，`check_record_bindings` 看守）逐条比对；
无理由、文件不存在、摘要不符三种都红；报错同时给出现值，便于照抄重钉。

**反证（owner 指定的试点，逐步执行）**：

```
# 1) 把 v4 的 tracking 阈值 0.2 改成 0.25
$ python test_eval_frame_v2.py
  ok 2 protocol(s) match the bytes their approval records      ← 上一步的绿灯
AssertionError: protocols/baseline_flat_v4.json: the bytes moved since they were approved
      table: 4b069c593172391f573de8318f92753401ee644aea41143bc3d93cda99951de2
      disk:  a63f6adab3a6d075f4b0d05b681b4625cb2783e1d2dd5a53c72a0293efcb105f
      revert the edit, or approve the new bytes with a reason in protocol_anchors.json
$ ... & echo rc=!errorlevel!        → rc=1

# 2) 还原
$ python test_eval_frame_v2.py
  ok terminal frame closes the window …  ok 2 protocol(s) match the bytes their approval records
ALL_EVAL_FRAME_V2_TESTS_PASSED
$ ... & echo rc=!errorlevel!        → rc=0
$ git diff --stat -- ablation_harness/protocols/baseline_flat_v4.json   → 空（byte-exact 还原）
```

**套件**：`[23] eval protocol contract …` 仍绿（标签未改，本检查同属协议契约），全量
`ALL_OFFLINE_CHECKS_PASSED (47/47 in 46.0s)`；`SUITE_SHAPE_OK`（无新增入口/子进程）。

## 证据引用

```
$ python -c "... binding.sha256_file(两份协议) ..."
baseline_flat_v4.json 4b069c593172391f573de8318f92753401ee644aea41143bc3d93cda99951de2
lizard2_flat_v1.json  4078869f798d5db067f5c7adfb6370ab301b695eeb3e8d84dce587dd5fbba792

（反证与套件输出见"结果"节；`git status --short` 提交前只剩本用例与这张新表）
```

## 未覆盖边界

- **整目录完整性未做（本项最大的洞）**：开 v5 时只要没人往表里加条目，核验**不会**提任何意见——
  这与 golden 那次"新线的锁不在表里"是同一类，而那一类已经发生过两次
  （`acceptance/records/2026-09-22-golden-subject-completeness.md`）。补法有先例：要求 `protocols/` 下每份协议
  要么有锚、要么在一张豁免表里写明理由；难点是会牵出 legacy `v1–v3` 与 `locomotion_eval_v1..v4` 的处置，需 owner 定。
- 只锚了两份 `*_flat_*.json`；`locomotion_eval_*.yaml`（含带套件锁的 v4）未锚。
- 只锚"字节"：改文件名 = 表里留陈旧条目（会红，需人工退役）；内容相同而重排的 JSON 也会红（按字节判，符合本仓惯例）。
- 阈值以外的协议字段（命令窗口、`bands`、`terminal_frame`、`post_failure_velocity`…）同受保护，但**未逐一反证**，只证了阈值一项。
- 这张表自身没有摘要看守：表被改、协议未动时不红（靠 git 审查）。
- 白名单是**声明式**的，不是从树上派生的：本文的"整目录完整性未做"即其代价。
