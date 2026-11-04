---
id: eval-column-coupling
title: 套件列间耦合：几何没变的列也会随别的列改变读数
scope: ablation_harness
status: in_progress
landing: ablation_harness/eval.py, ablation_harness/suites.py, rl_exp/tools/diagnose/column_coupling_probe.py, acceptance/records
next: 执行者处理汇总一致性与机制归因缺口，完成验证后申请独立重审。
close_when: 独立审核确认单变量探针及机制归因、复读链和规则工具去向。
depends_on: eval-column-runtime-recovery
evidence: acceptance/records/2026-10-30-eval-column-coupling-summary-repair-review.md, acceptance/records/2026-10-30-eval-column-coupling-second-closing-review.md, acceptance/records/2026-10-30-eval-column-coupling-closing-review.md, acceptance/records/2026-10-28-eval-column-coupling-repair.md, acceptance/records/2026-10-28-eval-column-coupling-dynamics.md, acceptance/records/2026-10-28-eval-column-coupling-independent-review.md, acceptance/records/2026-10-10-eval-column-coupling-probes.md, acceptance/records/2026-10-10-eval-column-coupling-review.md, acceptance/records/2026-10-10-eval-column-coupling-initial-state.md
---

## 当前状态

- 整体独立复审未通过；历史批次显式复读补修及限定复核见 `evidence`，环境恢复依赖仍未完成。

## 下一步

- 汇总文字勘误及辅助冲突报告重名修复见 `evidence`；复核完整差异，避免把单文件原子写入当跨文件事务。
- 复核历史批次显式复读与整体规则落点；恢复依赖及未观测引擎边界见 `evidence`。
- 修复后交由不带执笔历史的新上下文复审原始数据、比较器、规则工具落点及恢复事项；不得覆盖或删除现存数据。
- 保留引擎内未测状态与定量放大边界，不将未变列当作跨套件可比白名单。

## 关闭条件

- 至少完成一组单变量探针，指出改变及受影响列，据此排除或坐实候选机制；如两条探针都不影响 stairs，撤销耦合说法并保留条件与读数。
- 审核者复核实际落点、原始证据、复读路径、未覆盖边界以及规则和诊断工具的去向；不通过则退回。

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
