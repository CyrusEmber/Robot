---
id: record-format-live-checks
title: 记录格式的剩余真跑段（HARNESS 挂账 #2 的未做半）
scope: ablation_harness
status: pending_review
landing: ablation_harness/record.py, ablation_harness/eval.py
evidence: acceptance/records/2026-10-10-record-format-live-checks
next: 待审（新上下文，不看执笔结论）。审什么：① 真跑两条 run 的记录里 `substitutions.baseline` 是否指对 base run、`substitutions` 与 `unproven` 是否只由那一处 ckpt 差异解释、base 记录是否确实**没有** `substitutions` 键；② 记录里的 `runtime.rsl_rl_id` 与训练 manifest 按 `mode` 重建值是否同串；③ 要拍的一处判断——`close_when` ② 的"不相等时两列都出现"在现行写侧结构性不可达（两列同源于 `eval.py:394` 覆盖过的同一个 cfg 对象），本轮只观测到"分列"，这半算不算满足、还是该改 `close_when` 句子；④ 2026-10-10 用户定"pre-format 分支既然不会出现就不处理"，记录里是否只当边界写、没写成"已真跑"。落点与读数：`acceptance/records/2026-10-10-record-format-live-checks.md`。
close_when: ① 同一 run 身份按训练记录的 `mode` 重建后两处取值一致 ⇒ 记"已核到行为"，不一致 ⇒ 记差异并指出是哪一侧的字段口径；② 声明与实际分列、不相等时两列都出现 ⇒ 成立，某侧缺失 ⇒ 报记录不完整。两条都写出观测即关
---

## 当前状态

离线半与真跑半都已核完，读数、复读命令与判据归
`acceptance/records/2026-10-10-record-format-live-checks.md`。真跑两条 run 在 GPU 空出后落地
（新组 `results/locomotion_eval_v3/livecheck/`：base + `--variant` 各一条）：

- ① 写侧调用点已观测 —— base 找对、换 ckpt 落成已证类目、"两侧按 `mode` 重建同串"在同一批真跑上成立；
- ② 只观测到"两列分列"，"不相等"那半在现行写侧结构性不可达 ⇒ 是否算满足**待本次审拍**（见 `next` ③）。

2026-10-10 用户定：pre-format 分支"既然不会出现就不用处理"（写侧两文件同进同出，真 run 产不出该状态），
记录里只作边界写。

## 未覆盖边界

- ② 的"不等格"与 pre-format 分支**没有真跑观测**（前者结构性不可达，后者写侧产不出）⇒ 不得据本项称
  "记录格式已全部真跑"。
- 本项不含协议版本切换的对照（见 `runtime-acceptance-v3`），也不改 `record.py` 的规则（记录格式的
  读侧/写侧语义归 `record.py` 与 `test_eval_record.py`）。
- 真跑两条 run 的分数不作数（`livecheck` 组不进任何对账表）。它们是 v3 下带 ckpt 的真 run，
  `runtime-acceptance-v3` ③ 若要引用，判据归那件事自己。
