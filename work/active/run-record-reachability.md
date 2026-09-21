---
id: run-record-reachability
title: 实跑引用走不到：run 记录的文档可达落点
scope: rl_exp/tools/runrecord/manifest.py, rl_exp/versions/lizard
status: open
landing: rl_exp/tools/runrecord/manifest.py
next: 先量后决——① 查清 run 记录（T0/T1 manifest + argv/seed/session_overrides）现在落在 log dir 还是能进仓（`runrecord/rebuild.py` 会把记录与 checkpoint 复制进重建树，先确认那棵树是否仓内可达）；② 定"NOTES 里的实跑引用"该长什么样，使读者能沿链接在仓内取到 argv/seed/checkpoint；③ 若裁决不可达，把 §A-2 的口径降级为"NOTES 记 run id + 记录落点说明"，不假装可点
close_when: 读者只沿 NOTES 的实跑引用即可取到 argv/seed/checkpoint（或明确裁决不可达并把口径改写）⇒ 任一结果都算成立；后者须同时改掉 `versioning.mdc` §A-2 里会误导的措辞
evidence: acceptance/records/2026-09-21-version-doc-read-cost.md
---

## 当前状态

未开工。缺口是读取成本 A/B 读数顺带暴露的：**两个读者在版内四份文件里都取不到实跑命令行**——
`PLAN.md` 只有带占位符的示例，NOTES 按新口径把实跑外链到"运行记录"，而 run 记录的落点在 log dir，
文档侧无路径可走。`baseline/v1` 的 NOTES 已按新口径写成"实跑引运行记录"，读者侧目前走不通。

## 未覆盖边界

不改运行记录本身的字段与写入时机（那是 `manifest.py` 的契约，已有闸门与验收）；不重开已完成的重建评级；
不改历史 NOTES 的既有跑分正文（引用形态的返工只做新建与未冻结版本）。
