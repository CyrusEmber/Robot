---
id: runtime-acceptance-v3
title: 运行时验收的跨协议判定与证据勘误（HARNESS 挂账 #1）
scope: ablation_harness
status: in_progress
landing: ablation_harness/eval.py, ablation_harness/protocols/locomotion_eval_v3.yaml, ablation_harness/results
next: 按审核记录补齐①超差后的口径判定与依据；不得把“几何相同”改称“mesh digest 相同”当作通过。若需隔离实验，消费关联事项的证据；若改关闭范围，明示决定与原条件差异。执行记录补具名勘误（completion 均值与分布、量化口径、rough 配置差异、首跑双 rev），不无痕改写原工件。完成后置 pending_review，由新上下文对原 close_when、勘误与新增证据复审
close_when: 两条都跑完并观测：① 同一 ckpt 在 v2/v3 各一次（各臂另重跑一次作可复现性对照）—— 落在 ±0.02 内即记录并接受，超出则记差异清单并判断是哪一侧的口径问题；② 有 ckpt 的 run 完成后看 9 列 completion —— 有分布即成立。读数与判定进 acceptance/records，本项只留指针；审核通过后才能关闭
evidence: acceptance/records/2026-10-10-cross-protocol-suite-readings.md, acceptance/records/2026-10-10-runtime-acceptance-v3-review.md
---

## 当前状态

当前审核判定与证据边界见 `acceptance/records/2026-10-10-runtime-acceptance-v3-review.md`；真跑材料见执行记录。补齐动作见 `next`，本项不保存读数或复述结论。

关联事项 `work/active/eval-column-coupling.md` 承接机制隔离；其存在不替代本项关闭所需的口径判定。
