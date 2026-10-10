---
id: eval-column-coupling
title: 套件列间耦合：几何没变的列也会随别的列改变读数
scope: ablation_harness
status: pending_review
landing: ablation_harness/eval.py, ablation_harness/suites.py, acceptance/records
next: 审——**新上下文**（不带执行会话历史）对着 `close_when` 与 `acceptance/records/2026-10-10-eval-column-coupling-initial-state.md` 判三件：① 诊断是否真的把通道收到引擎层（判据两条：未改列写入态逐位相同、零动作几步内即分叉；注意 `RslRlVecEnvWrapper.__init__` 会 reset，起跑态是它之后的写入态，不是构造态）；② 边界有没有写够 —— "引擎内部路径未取证""未做定量放大"是读数还是被读成了结论；③ 据此要不要落**规则与工具** —— "改套件 ⇒ 未变列不可比"（进 HARNESS/协议，或明确记录为不落）与该诊断是否常驻，两件都还没决定。审核读数入 `acceptance/records/`，本项只留指针；审过即移进 `work/closed/2026/`、去掉本 `next`、补 `outcome`
close_when: 至少一条单变量探针跑完，且能指出"改了这个、只有这些列变了"来排除或坐实机制 —— 结论进 `acceptance/records/`、本项只留指针；若两条探针都不动 stairs，则撤销"耦合"这个说法并把复现命令与读数留档（"测不到"也是结论，不许只写判决不写条件）
evidence: acceptance/records/2026-10-10-eval-column-coupling-probes.md, acceptance/records/2026-10-10-eval-column-coupling-review.md, acceptance/records/2026-10-10-eval-column-coupling-initial-state.md
---

## 当前状态

- 执行证据、审核与机制诊断：见 `evidence`；当前动作见 `next`。
- 机制已收到引擎层（改一格的几何会让别的、逐位相同格子上的 env 走出不同轨迹），引擎内部路径仍未取证 —— 读数不复述。

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
