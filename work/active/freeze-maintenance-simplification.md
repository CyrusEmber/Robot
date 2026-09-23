---
id: freeze-maintenance-simplification
title: 冻结约束维护流程简化（基线 → 补缺口 → 试点 → 去重 → 推广）
scope: rl_exp/tools/verify, rl_exp/tools/runrecord, ablation_harness
status: open
landing: rl_exp/tools/verify/check_golden_frozen.py, rl_exp/tools/verify/check_dr_parity.py, rl_exp/tools/verify/test_eval_frame_v2.py, ablation_harness/protocol_anchors.json, rl_exp/tools/runrecord/manifest.py, rl_exp/tools/runrecord/binding.py
next: 协议数值锚**已按 ② 落地**（新表 `ablation_harness/protocol_anchors.json` + 核验折进 `[23]`，覆盖 v4 与 lizard2_flat_v1；字节变而表未同步 ⇒ 红）。下一步 owner 二选一：(a) 补 `protocols/` **整目录完整性**（每份协议要么有锚、要么在豁免表里写明理由；会牵出 legacy `v1–v3` 与 `locomotion_eval_v1..v4` 的处置）；(b) 转第四步去重（现成候选 `obs-three-tables-merge`，带动工前置）。第二步第三类（开训前协议绑定）仍 **blocked**（等形态拍板 + `baseline-eval-protocol-gap` 的 v2 首跑；两事项互相 `depends_on`，环）
close_when: 按第五步对比基线：纯阈值调整不必换 kind、不必多处抄同一组数值；新线漏登记明确红；旧协议与旧记录仍可读；批准边界与不同时间点的独立验证保留；agent 一次正常修改需读的材料减少 ⇒ 推广。若需通用注册表或大规模历史迁移 ⇒ 补完修复后停止扩展并记下理由
depends_on: eval-protocol-before-training, teacher-literal-parity-gate, obs-three-tables-merge
evidence: acceptance/records/2026-09-22-freeze-simplification-baseline, acceptance/records/2026-09-22-golden-subject-completeness, acceptance/records/2026-09-23-asset-lock-set-completeness, acceptance/records/2026-09-23-git-output-encoding, acceptance/records/2026-09-23-utf8-assumption-and-entry-run-decode, acceptance/records/2026-09-23-threshold-pilot, acceptance/records/2026-09-23-protocol-anchor-table, acceptance/records/2026-09-23-blocked-chain-and-obs-merge-precheck
---

## 问题与范围

一次正常修改（改阈值／加配方线）要重新理解整套冻结约束并多处手工同步。本项只做维护流程简化：不新增套件入口、不抬 `MAX_CHECKS`、不造统一冻结系统、不重写历史证据、不以"一键重钉"消错。范围＝必要缺口修复＋一个阈值修改试点。

## 状态

五步、每步可单独停止（2026-09-22 定稿）：

1. 基线：**已完成**（`evidence`）。三问结论：五件套 + 条件件 `diff.json`，tag 只 WARN；三个枚举外目录在 `lizard/main/`（`rough-v0`、`curriculum-flat-v0`、`curriculum-rough-v0`）——**内容**经 `params_line` 路由受 golden 看守，**目录形态**无任何闸门看守（是否补声明闸按第 4 步"抓什么具体错误"判，不预设）；复读闭包 10/13 可解析，主断链是记录自带 rev `aa86af408e1e` 的树里**不含判据实现**（`loco_judge.py`／`judge_semantics.json`／`suite_lock.py` 之后才入库），且 v3 及更早 record 无 `judge` 块；计数器 = 改阈值须手改 1 处（另 2 处文档复述），加一条线 11 类手写点（含 3/3/17 条计数钉）。
2. 补缺口、全部折入现有闸门：**golden 集合完整性已完成**（`check_golden_frozen` 主体改为从树上读，第 5 条锁已钉；该缺口是第二次发生 —— baseline 线 2026-09-17、lizard2 线 2026-09-22）；**asset lock 集合完整性已完成**（`check_dr_parity` 双向比对 + "有锁但无人读"判红；自测当场抓到 glob 少一层的实现 bug）；**Git 输出编码已完成**（`git_run` 钉 UTF-8 + replace；崩得含糊是本条的要害；顺带补了 `lifecycle_entry_run._run` —— 同一解码形状且是唯一读真实训练日志的点，它会**静默丢证据**，见 `evidence` 第五、六条）；**入口钉 `PYTHONUTF8` 已测否**（无该环境变量时套件仍 47/47 绿）⇒ 不加，只记事实；**开训前协议绑定 blocked**（等形态拍板 + v2 首跑）。tag 若只是辅助索引，写明边界。
3. 阈值试点：职责＝协议（阈值与条件组合）／kind（公式与聚合、失败帧语义）／judge（解释与执行）／record（身份与摘要）；流程＝候选 → 差异摘要 → 审查批准 → 检查执行。**已完成**（`evidence` 第七条）：验收三条成立（不必换 kind／手改面＝1 个数字 + 2 处散文复述／旧协议与旧记录可读），但**"检查执行"阶段实测为空** —— 把 v4 的 tracking 阈值 0.2 改成 0.25 后**全量套件 47/47 仍全绿**（`test_v4_reproduces_v3_on_one_record` 证的是"地板一致"不是"数值相同"）。故不建候选生成器（1 个数字的生成器是多余机器）。暴露出的协议数值锚缺失**已按 owner 选定的 ② 补上**：新表 `ablation_harness/protocol_anchors.json`（协议文件 → sha256 + 理由）+ 核验折进 `[23]`，覆盖 `baseline_flat_v4` 与 `lizard2_flat_v1`；已发布的 `judge_semantics` id 块未动；反证＝v4 阈值改 0.2→0.25 ⇒ 入口 rc=1 点名文件与两个摘要，还原 ⇒ 绿（`evidence` 第八条）。
4. 逐项去重：一次一个候选，删前答三问（原抓什么错／依据来自哪／谁接替＋反例）。候选三类：obs 合口**核认已完成、动工前置满足**（`evidence` 第九条；实施归原事项，边界保留：`--live` 证据强度下降、golden 不动、真实环境验证）；teacher／`freeze_parity.json` 去重 **blocked**，等该事形态三选一（定案 ≠ 批准取消 teacher 独立快照纪律）；其余候选可独立审查。阻塞是分项级，本项仍 open（基线可独立开始）。离线检查与开训重验、生成结果与批准锚、反例与真实运行不因"重复读取"而删。
5. 决定是否继续：与基线对比，收益不明显即停止扩展。

三条已收修正：产出各带可复现计数器；候选默认 stdout、落文件须 gitignore、闸门只读批准锚；m2 保留 LF 规范字节（2026-09-20 已重录，只核验）；接替检查须与生成器不同源。

已核事实：判据实现**不可由记录自带的 rev 复读**（rev 在仓、树里没有判据文件）；`eval_protocol.digest` 与 `assets.declared_digest` 仓内无第二副本，校验等于重算；枚举外目录的**目录形态**是当前唯一"无看守"的版本类事实。

## 未覆盖边界

kind 分工只做验证，不改造历史格式；**协议锚是声明式的、整目录完整性未做**（开 v5 而无人登记仍静默，与 golden 那次同类，见 `evidence` 第八条末节）；`git_run` 与 `_run` 的取舍都是 `errors="replace"`（非 UTF-8 字节变 U+FFFD，JSON 安全）而非 `surrogateescape`，两处**都没有永久回归测试**——本机复现要求非 UTF-8 宿主，得动套件形状那张 spawn 名单（要加就加**一处**，覆盖两种形状）；折入三条后复核套件预算闸；仓对未写下的 `PYTHONUTF8=1` 有环境级依赖（实测套件不需要，故不钉）；"记录缺工作树是否干净这一字段"是记录格式的缺口，本次不动。
