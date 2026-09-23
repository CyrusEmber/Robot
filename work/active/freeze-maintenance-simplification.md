---
id: freeze-maintenance-simplification
title: 冻结约束维护流程简化（基线 → 补缺口 → 试点 → 去重 → 推广）
scope: rl_exp/tools/verify, rl_exp/tools/runrecord, ablation_harness
status: open
landing: rl_exp/tools/verify/check_golden_frozen.py, rl_exp/tools/verify/check_dr_parity.py, rl_exp/tools/verify/test_eval_frame_v2.py, ablation_harness/protocol_anchors.json, rl_exp/tools/runrecord/manifest.py, rl_exp/tools/runrecord/binding.py
next: 剩余动作（**全部留本项内，不另立项**；按序）：① 协议锚**已完成**（整目录 + 逐字段）：主体从 `protocols/` 树上读、legacy 按 `LEGACY_PROTOCOLS` **规则**豁免 ⇒ 7 锚 + 3 豁免 = 10 份全覆盖；非阈值字段同样被抓（改 `post_failure_velocity` ⇒ 红，一处证明即覆盖全部字段）；上线的第二天被 `6de88a0` 绕过一次，见 `evidence` 第十条。**遗留一条**：`LEGACY_PROTOCOLS` 是唯一豁免真源且它自身无摘要看守。② 第四步去重：obs 合口可开工（核认完成、前置满足，实施归 `obs-three-tables-merge`）；teacher／`freeze_parity.json` 形态**已定**（`evidence` 第九条 B 节 + `teacher-literal-parity-gate.next`），随之可做；其余候选待指名。③ 两处解码（`binding.git_run`、`lifecycle_entry_run._run`）的永久回归测试 —— 需花套件形状**一个** spawn 名额，一处可覆盖两种形状。④ 三个枚举外目录（`rough-v0`／`curriculum-flat-v0`／`curriculum-rough-v0`）的**目录形态**是否加看守 —— 按第 4 步"能抓什么具体错误"判，不预设。⑤ 两条**无主敞口**（按 owner 指示不立项，记此以免第 5 步裁决漏读）：(a) 旧结果复读断链 —— 记录自带 `git_rev_lizard` 的树里不含 `loco_judge.py`／`judge_semantics.json`／`suite_lock.py`，v3 及更早 record 无 `judge` 块 ⇒ "旧结果可复读"只成立一半，修法要先让记录带"工作树是否干净"一类字段；(b) tag 与摘要表／资产锁三处描述同一棵树却互不校验，tag 缺只 WARN。⑥ 第五步裁决 —— 与第 1 步基线对比，**注意计数已变**（改阈值现为 1 个数字 + 1 条锚条目 + 2 处散文复述），判"推广"或"停止扩展"。⑦ 第二步第三类（开训前协议绑定）**blocked**：形态已定（`eval-protocol-before-training` 的 `next`），等 `baseline-eval-protocol-gap` 的 v2 首跑判定与 NOTES 回填；之后按该事项 `close_when` 另起"缺协议拒绝／有协议放行"两次真启动取证
close_when: 按第五步对比基线：纯阈值调整不必换 kind、不必多处抄同一组数值；新线漏登记明确红；旧协议与旧记录仍可读；批准边界与不同时间点的独立验证保留；agent 一次正常修改需读的材料减少 ⇒ 推广。若需通用注册表或大规模历史迁移 ⇒ 补完修复后停止扩展并记下理由
depends_on: eval-protocol-before-training, teacher-literal-parity-gate, obs-three-tables-merge
evidence: acceptance/records/2026-09-22-freeze-simplification-baseline, acceptance/records/2026-09-22-golden-subject-completeness, acceptance/records/2026-09-23-asset-lock-set-completeness, acceptance/records/2026-09-23-git-output-encoding, acceptance/records/2026-09-23-utf8-assumption-and-entry-run-decode, acceptance/records/2026-09-23-threshold-pilot, acceptance/records/2026-09-23-protocol-anchor-table, acceptance/records/2026-09-23-blocked-chain-and-obs-merge-precheck, acceptance/records/2026-09-23-two-forms-decided, acceptance/records/2026-09-23-protocol-anchor-coverage
---

## 问题与范围

一次正常修改（改阈值／加配方线）要重新理解整套冻结约束并多处手工同步。本项只做维护流程简化：不新增套件入口、不抬 `MAX_CHECKS`、不造统一冻结系统、不重写历史证据、不以"一键重钉"消错。范围＝必要缺口修复＋一个阈值修改试点。

## 状态

五步、每步可单独停止（2026-09-22 定稿）：

1. 基线：**已完成**（`evidence`）。三问结论：五件套 + 条件件 `diff.json`，tag 只 WARN；三个枚举外目录在 `lizard/main/`（`rough-v0`、`curriculum-flat-v0`、`curriculum-rough-v0`）——**内容**经 `params_line` 路由受 golden 看守，**目录形态**无任何闸门看守（是否补声明闸按第 4 步"抓什么具体错误"判，不预设）；复读闭包 10/13 可解析，主断链是记录自带 rev `aa86af408e1e` 的树里**不含判据实现**（`loco_judge.py`／`judge_semantics.json`／`suite_lock.py` 之后才入库），且 v3 及更早 record 无 `judge` 块；计数器 = 改阈值须手改 1 处（另 2 处文档复述），加一条线 11 类手写点（含 3/3/17 条计数钉）。
2. 补缺口、全部折入现有闸门：**golden 集合完整性已完成**（`check_golden_frozen` 主体改为从树上读，第 5 条锁已钉；该缺口是第二次发生 —— baseline 线 2026-09-17、lizard2 线 2026-09-22）；**asset lock 集合完整性已完成**（`check_dr_parity` 双向比对 + "有锁但无人读"判红；自测当场抓到 glob 少一层的实现 bug）；**Git 输出编码已完成**（`git_run` 钉 UTF-8 + replace；崩得含糊是本条的要害；顺带补了 `lifecycle_entry_run._run` —— 同一解码形状且是唯一读真实训练日志的点，它会**静默丢证据**，见 `evidence` 第五、六条）；**入口钉 `PYTHONUTF8` 已测否**（无该环境变量时套件仍 47/47 绿）⇒ 不加，只记事实；**开训前协议绑定**：形态**已定**（`evidence` 第九条 A 节），实施等 `baseline-eval-protocol-gap` 的 v2 首跑判定与 NOTES 回填（见 `next` ⑦）。tag 若只是辅助索引，写明边界。
3. 阈值试点：职责＝协议（阈值与条件组合）／kind（公式与聚合、失败帧语义）／judge（解释与执行）／record（身份与摘要）；流程＝候选 → 差异摘要 → 审查批准 → 检查执行。**已完成**（`evidence` 第七条）：验收三条成立（不必换 kind／手改面＝1 个数字 + 2 处散文复述／旧协议与旧记录可读），但**"检查执行"阶段实测为空** —— 把 v4 的 tracking 阈值 0.2 改成 0.25 后**全量套件 47/47 仍全绿**（`test_v4_reproduces_v3_on_one_record` 证的是"地板一致"不是"数值相同"）。故不建候选生成器（1 个数字的生成器是多余机器）。暴露出的协议数值锚缺失**已按 owner 选定的 ② 补上**：新表 `ablation_harness/protocol_anchors.json`（协议文件 → sha256 + 理由）+ 核验折进 `[23]`，覆盖 `baseline_flat_v4` 与 `lizard2_flat_v1`；已发布的 `judge_semantics` id 块未动；反证＝v4 阈值改 0.2→0.25 ⇒ 入口 rc=1 点名文件与两个摘要，还原 ⇒ 绿（`evidence` 第八条）。**覆盖面随后补齐**：主体改为从 `protocols/` 树上读、legacy 按 `LEGACY_PROTOCOLS` 规则豁免 ⇒ 7 锚 + 3 豁免 = 10 份全覆盖（`evidence` 第十条）。
4. 逐项去重：一次一个候选，删前答三问（原抓什么错／依据来自哪／谁接替＋反例）。候选三类：obs 合口**核认已完成、动工前置满足**（`evidence` 第九条；实施归原事项，边界保留：`--live` 证据强度下降、golden 不动、真实环境验证）；teacher／`freeze_parity.json` 去重形态**已定**（`evidence` 第九条 B 节：① 声明式 + 可执行关系 + C4 静态校验；定案 ≠ 批准取消 teacher 独立快照纪律），随之可做；其余候选待指名。阻塞是分项级，本项仍 open（基线可独立开始）。离线检查与开训重验、生成结果与批准锚、反例与真实运行不因"重复读取"而删。
5. 决定是否继续：与基线对比，收益不明显即停止扩展。

三条已收修正：产出各带可复现计数器；候选默认 stdout、落文件须 gitignore、闸门只读批准锚；m2 保留 LF 规范字节（2026-09-20 已重录，只核验）；接替检查须与生成器不同源。

已核事实：判据实现**不可由记录自带的 rev 复读**（rev 在仓、树里没有判据文件）；`eval_protocol.digest` 与 `assets.declared_digest` 仓内无第二副本，校验等于重算；枚举外目录的**目录形态**是当前唯一"无看守"的版本类事实。

## 未覆盖边界

边界（未做的动作全在 `next`，此处只写"不做"与取舍）：kind 分工只做验证，不改造历史格式、不写通用表达式语言；不追历史 run 的协议与证据、不为历史记录补锚；不为 `PYTHONUTF8` 这类未观测到失败的假设加改动（仓对它有环境级依赖，已记档）；`errors="replace"`（U+FFFD、JSON 安全）而非 `surrogateescape` 的取舍见 `evidence` 第四、六条；不动"记录缺工作树是否干净"这一字段（它是 `next` ⑤a 的修法前提，改记录格式不在本项）。
