---
id: eval-column-coupling
title: 套件列间耦合：几何没变的列也会随别的列改变读数
scope: ablation_harness
status: open
landing: ablation_harness/eval.py, ablation_harness/suites.py, acceptance/records
next: 单变量探针定案（本机 GPU 空时跑，每次一条 9 列 eval）—— ① 只把 `suites.lizard_suite_v2` 的 rough_a 幅值改回单值、rough_b 不动：若 stairs 列的读数**跟着动**，污染来自"套件里有列变了"这件事本身；若只有 rough_a 动，则是逐列独立。② 把 rough 两列换到列首（列序变、几何不变）：若 stairs 读数再变，指向"合并 mesh 的三角形顺序 → 接触/求解顺序"这条；若不变，指向 spawn 高度或 reset RNG 流。两条探针的读数与"动了哪几列、动多少"写进 `acceptance/records/`，本项只留指针；定案后按性质落到机制（`suite_lock` 的注记口径 / 协议下一版 / `eval.py` 的 spawn 路径）。
close_when: 至少一条单变量探针跑完，且能指出"改了这个、只有这些列变了"来排除或坐实机制 —— 结论进 `acceptance/records/`、本项只留指针；若两条探针都不动 stairs，则撤销"耦合"这个说法并把复现命令与读数留档（"测不到"也是结论，不许只写判决不写条件）
---

## 当前状态

- **已证**：同一协议重跑逐字段完全相同（两臂各自 `EQUAL`），所以跨协议差异不是重跑噪声。
- **已证**：v2 → v3 只改 rough 两列几何（`relief_p95` 0 → 0.030/0.060 m），而 **mesh digest 逐字相同**的
  `stairs_10cm` completion 差 +0.039、fall 差 −0.125、`stairs_20cm` success 差 +0.091 ⇒ 读数是整个套件的函数，
  不是所在列几何的函数。读数见 `acceptance/records/2026-10-10-cross-protocol-suite-readings.md`。
- **未定**：机制（候选：合并 mesh 三角形顺序 → PhysX 接触/求解顺序；spawn 高度；reset RNG 流）。

## 为什么要单独立项

本项不是"v3 协议对不对"，也不是"策略好不好"：它质疑的是**测量本身**——一条列的读数在什么条件下才可比。
只要它没定案，任何"改套件后旧行还能比"的说法都缺前提，而这件事会再次以"±0.02 不达标"的形式冒出来
（本项就是从 `runtime-acceptance-v3` 的 ① 里冒出来的）。

## 未覆盖边界

- 不含"提高功效"（每列 env 数 / seed 数是协议版本决策，归协议侧）。
- 不改冻结协议文件本身（`locomotion_eval_v2/v3.yaml` 只读；要改语义 = 新版本）。
- 不评策略强弱；上面的 completion / fall 数字只作耦合证据，不作性能引用。
