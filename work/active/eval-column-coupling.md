---
id: eval-column-coupling
title: 套件列间耦合：几何没变的列也会随别的列改变读数
scope: ablation_harness
status: in_progress
landing: ablation_harness/eval.py, ablation_harness/suites.py, acceptance/records
next: 执行者对照审核记录修订探针证据：收窄跨列影响与可比性声明、纠正指标粒度、披露实际控制变量与归档边界；先定义能区分候选路径的诊断干预，不把 env 重排当成排除 RNG/spawn 的单变量。保留原 close_when，补齐后置 pending_review，由新上下文复审；若仅收束影响观察，须用户明示变更关闭范围。
close_when: 至少一条单变量探针跑完，且能指出"改了这个、只有这些列变了"来排除或坐实机制 —— 结论进 `acceptance/records/`、本项只留指针；若两条探针都不动 stairs，则撤销"耦合"这个说法并把复现命令与读数留档（"测不到"也是结论，不许只写判决不写条件）
evidence: acceptance/records/2026-10-10-eval-column-coupling-review.md
---

## 当前状态

- 执行证据：`acceptance/records/2026-10-10-eval-column-coupling-probes.md`。
- 独立审核与返工依据：见 `evidence`；当前动作见 `next`。

## 为什么要单独立项

本项不是"v3 协议对不对"，也不是"策略好不好"：它质疑的是**测量本身**——一条列的读数在什么条件下才可比。
只要它没定案，任何"改套件后旧行还能比"的说法都缺前提，而这件事会再次以"±0.02 不达标"的形式冒出来
（本项就是从 `runtime-acceptance-v3` 的 ① 里冒出来的）。

## 未覆盖边界

- 不含"提高功效"（每列 env 数 / seed 数是协议版本决策，归协议侧）。
- 不改冻结协议文件本身（`locomotion_eval_v2/v3.yaml` 只读；要改语义 = 新版本）；
  探针用的是内存注入，没有改 `suites.py` 正文 —— 那次改会静默换掉此后所有 v3 run 的地面。
- 本次审核不授权新增诊断入口或改变正式测量语义；后续诊断须先明确控制变量，正式协议变更仍走升版。
- 不评策略强弱；探针读数只作耦合证据。
- 探针行只存在于 `results/locomotion_eval_v3/coupling-probe/`（自带 group），是诊断读数、不进 campaign 表。
