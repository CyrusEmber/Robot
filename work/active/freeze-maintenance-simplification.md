---
id: freeze-maintenance-simplification
title: 冻结约束维护流程简化（基线 → 补缺口 → 试点 → 去重 → 推广）
scope: rl_exp/tools/verify, rl_exp/tools/runrecord, ablation_harness
status: open
landing: rl_exp/tools/verify/check_golden_frozen.py, rl_exp/tools/verify/check_dr_parity.py, rl_exp/tools/runrecord/manifest.py, rl_exp/tools/runrecord/binding.py
next: 第二步第二类：asset lock 集合完整性折进 `check_dr_parity.check_asset_locks` —— 反例 = 锁里列了、盘上没了（或锁被移出当前枚举）⇒ 必须红，且先证明旧实现绿。随后按序折入开训前协议绑定（`manifest.begin`，反例 = 缺协议／摘要不符均拒）、`binding.git_run` 编码（反例 = 非 ASCII git 输出不再崩）。每条先证明旧实现失败，套件入口数与 `MAX_CHECKS` 不增
close_when: 按第五步对比基线：纯阈值调整不必换 kind、不必多处抄同一组数值；新线漏登记明确红；旧协议与旧记录仍可读；批准边界与不同时间点的独立验证保留；agent 一次正常修改需读的材料减少 ⇒ 推广。若需通用注册表或大规模历史迁移 ⇒ 补完修复后停止扩展并记下理由
depends_on: eval-protocol-before-training, teacher-literal-parity-gate, obs-three-tables-merge
evidence: acceptance/records/2026-09-22-freeze-simplification-baseline, acceptance/records/2026-09-22-golden-subject-completeness
---

## 问题与范围

一次正常修改（改阈值／加配方线）要重新理解整套冻结约束并多处手工同步。本项只做维护流程简化：不新增套件入口、不抬 `MAX_CHECKS`、不造统一冻结系统、不重写历史证据、不以"一键重钉"消错。范围＝必要缺口修复＋一个阈值修改试点。

## 状态

五步、每步可单独停止（2026-09-22 定稿）：

1. 基线：**已完成**（`evidence`）。三问结论：五件套 + 条件件 `diff.json`，tag 只 WARN；三个枚举外目录在 `lizard/main/`（`rough-v0`、`curriculum-flat-v0`、`curriculum-rough-v0`）——**内容**经 `params_line` 路由受 golden 看守，**目录形态**无任何闸门看守（是否补声明闸按第 4 步"抓什么具体错误"判，不预设）；复读闭包 10/13 可解析，主断链是记录自带 rev `aa86af408e1e` 的树里**不含判据实现**（`loco_judge.py`／`judge_semantics.json`／`suite_lock.py` 之后才入库），且 v3 及更早 record 无 `judge` 块；计数器 = 改阈值须手改 1 处（另 2 处文档复述），加一条线 11 类手写点（含 3/3/17 条计数钉）。
2. 补缺口、全部折入现有闸门：**golden 集合完整性已完成**（`check_golden_frozen` 主体改为从树上读，第 5 条锁已钉，见 `evidence` 第二条；该缺口是第二次发生 —— baseline 线 2026-09-17、lizard2 线 2026-09-22）；待做 asset lock 集合完整性（`check_dr_parity.check_asset_locks`）、开训前协议绑定（`manifest.begin`，正文见 `eval-protocol-before-training`）、Git 输出编码稳定（`binding.git_run`）；每条先证明旧实现失败。tag 若只是辅助索引，写明边界。
3. 阈值试点：职责＝协议（阈值与条件组合）／kind（公式与聚合、失败帧语义）／judge（解释与执行）／record（身份与摘要）；流程＝候选 → 差异摘要 → 审查批准 → 检查执行。先验证分工，不改造历史格式。
4. 逐项去重：一次一个候选，删前答三问（原抓什么错／依据来自哪／谁接替＋反例）。候选三类：obs 合口依 `obs-three-tables-merge` 自己的核认前置（builder 改动静下来后一次落；实施归原事项，边界保留：`--live` 证据强度下降、golden 不动、真实环境验证）；teacher／`freeze_parity.json` 去重 **blocked**，等该事形态三选一（定案 ≠ 批准取消 teacher 独立快照纪律）；其余候选可独立审查。阻塞是分项级，本项仍 open（基线可独立开始）。离线检查与开训重验、生成结果与批准锚、反例与真实运行不因"重复读取"而删。
5. 决定是否继续：与基线对比，收益不明显即停止扩展。

三条已收修正：产出各带可复现计数器；候选默认 stdout、落文件须 gitignore、闸门只读批准锚；m2 保留 LF 规范字节（2026-09-20 已重录，只核验）；接替检查须与生成器不同源。

已核事实：判据实现**不可由记录自带的 rev 复读**（rev 在仓、树里没有判据文件）；`eval_protocol.digest` 与 `assets.declared_digest` 仓内无第二副本，校验等于重算；枚举外目录的**目录形态**是当前唯一"无看守"的版本类事实。

## 未覆盖边界

kind 分工只做验证，不改造历史格式；`binding.git_run` 必须"明确报错"；折入四条后复核套件预算闸；"记录缺工作树是否干净这一字段"是记录格式的缺口，本次不动。
