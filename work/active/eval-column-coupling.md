---
id: eval-column-coupling
title: 套件列间耦合：几何没变的列也会随别的列改变读数
scope: ablation_harness
status: pending_review
landing: ablation_harness/eval.py, ablation_harness/suites.py, acceptance/records
next: 审——**新上下文**（不带执行会话历史）对着 `close_when` 与 `acceptance/records/2026-10-10-eval-column-coupling-probes.md` 判三件：① 两条探针是否各自成立（对照是否真的逐字复现 v2；单列探针的 `relief` 是否真的回到 0）；② 判定的边界有没有写够 —— "非局部但非全局""机制未从求解器取证"是读数还是被读成了结论；③ 剩下的真实缺口（缺一个"不动几何"的探针入口）该就地在 `eval.py` 开一个，还是明确留给协议下一版。审核读数入 `acceptance/records/`，本项只留指针；审过即移进 `work/closed/2026/`、去掉本 `next`、补 `outcome`
close_when: 至少一条单变量探针跑完，且能指出"改了这个、只有这些列变了"来排除或坐实机制 —— 结论进 `acceptance/records/`、本项只留指针；若两条探针都不动 stairs，则撤销"耦合"这个说法并把复现命令与读数留档（"测不到"也是结论，不许只写判决不写条件）
---

## 当前状态

- **已证**：同一协议重跑逐字段完全相同（两臂各自 `EQUAL`），跨协议差异不是重跑噪声。
- **已做（两条探针）**：对照 + 单列探针都跑完，各自的成立条件都核过；结论是**非局部、也不是全局**，
  机制余项与误差边界一并写在 `acceptance/records/2026-10-10-eval-column-coupling-probes.md`（本项不复述读数）。
- **旁证通道**：height-field 列共享全局 numpy 流 ⇒ 改前一列会改后一列的**实现几何**，
  "只改一列"的单变量探针在 hf 列之间本来就做不到。
- **未定**：物理机制未从求解器取证；要排除 reset RNG / spawn 高度，缺一个**不动任何几何**的探针入口。
- **待审**：见 `next`。执行者认为探针部分已完成，故置 `pending_review`。

## 为什么要单独立项

本项不是"v3 协议对不对"，也不是"策略好不好"：它质疑的是**测量本身**——一条列的读数在什么条件下才可比。
只要它没定案，任何"改套件后旧行还能比"的说法都缺前提，而这件事会再次以"±0.02 不达标"的形式冒出来
（本项就是从 `runtime-acceptance-v3` 的 ① 里冒出来的）。

## 未覆盖边界

- 不含"提高功效"（每列 env 数 / seed 数是协议版本决策，归协议侧）。
- 不改冻结协议文件本身（`locomotion_eval_v2/v3.yaml` 只读；要改语义 = 新版本）；
  探针用的是内存注入，没有改 `suites.py` 正文 —— 那次改会静默换掉此后所有 v3 run 的地面。
- 不含"给 `eval.py` 加不动几何的探针入口"这个决定（审时定，可能落成协议下一版）。
- 不评策略强弱；探针读数只作耦合证据。
- 探针行只存在于 `results/locomotion_eval_v3/coupling-probe/`（自带 group），是诊断读数、不进 campaign 表。
