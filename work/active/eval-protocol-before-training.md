---
id: eval-protocol-before-training
title: 开训前必须已有冻结的验收协议（启动闸门，而非事后补口径）
scope: rl_exp/tools/runrecord, rl_exp/tools/verify, ablation_harness, rl_exp/versions/lizard
status: open
landing: rl_exp/tools/runrecord/manifest.py, rl_exp/tools/verify/offline_suite.py, ablation_harness/HARNESS.md
next: 执行者按正文实现协议身份/摘要闸门；当前 lizard2 首轮按训练优先修订接入，不等待此通用闸门或完整动态协议。
close_when: 执行者真起一次训练命令观察启动行为——本版本无协议 ⇒ 训练在 begin 处被拒且提示写明缺哪份协议；补上协议后同一命令开训成功。两个分支各留一条证据（日志片段或测试），写入 `acceptance/records/`，本项关闭
evidence: acceptance/records/2026-09-20-baseline-flat-eval-protocol.md
---

## 问题与本次范围

本轮暴露出的是**流程漏洞**，不是缺数据：验收口径是在训练跑完之后才被追问"够不够"的，而开训前
并没有任何机制要求"这个版本将被什么判据判"。开训前的探针钉了标准（四脚承重、头链零载荷），
验收器却读了另一套更弱的口径——两套工具、两把尺子，谁都没错，合起来就是漏判。

本项要的是**顺序**：协议的冻结与摘要绑定发生在训练之前，训后协议只读。已有可用的机器：
`manifest.begin` 的拒绝集合（脏树拒绝先例）、`obs_protocol` 的"声明协议 + 摘要"形态、
离线套件的契约式检查。本项不新造机制，只把它们接起来。

## 当前执行要求与适用范围

当前 lizard2 首轮按[训练优先修订](../../acceptance/records/2026-10-23-lizard2-training-priority-plan.md)推进：开训前明确并绑定学习目标、命令工况及已确认可信的有限评测依据，不等待完整偏转/滚动/滑动标定、新动态协议或本通用闸门实现；未验证的新指标不进入奖励、终止或合格判定。这不是运行时 override，也不跳过已存在的启动检查。该范围外的通用机制目标保持，事项不关闭。

1. 载体按 `acceptance/records/2026-09-23-two-forms-decided.md` A 节：`rl_exp/versions/obs_protocols.json` 的 task 路由加 `eval_protocol`，按 task 核 `(line, version)`，不放进配方 YAML/PLAN。摘要复用 `binding.sha256_file` 的路径与预期值；已在 `protocol_anchors.json` 的文件须与批准锚一致。
2. 除上述本轮 lizard2 范围，目标仍覆盖所有新启动及旧版本重启，不只检查有声明的任务、不设运行 override。`begin` 在 T0 写盘前记录事实、写盘后按已有拒绝流程处理；本项仍是待实现的通用机制，不以此计划假称已有机器闸门。
3. 保留缺协议拒绝、协议摘要改变拒绝的真实反证和同条件正例；“已有历史产物不代证闸门行为”的约束保持。实施前置输入取 `acceptance/records/2026-09-23-baseline-v2-first-run.md`，旧 lizard2 v3 缺协议描述不作为当前候选的自然反例。
4. 实施时同步 HARNESS 与版本 kickoff 的协议身份/冻结纪律。不得由此要求本轮 lizard2 补完整动态分类后才能接正式配置或训练；新增判分使用前验证仍由对应评测事项负责。本轮只改路由，不执行上述训练正反例。

## 排序决定（2026-09-21，用户）：v2 先开训，本闸门后补

事实与边界要分清，免得日后读成"先训后补口径"：

- **协议先于训练冻结**：`baseline_flat_v3.json` 在开训前就是冻结文件（commit `1183b2f`），
  "训完再想怎么判"这件事没有发生。缺的只是**机制**——没有东西能在启动处拒绝一次无协议的 run。
- **不得回溯补证**：本项落地后，两个分支（无协议 ⇒ 拒；有协议 ⇒ 放行）各自要**新的**真跑证据，
  不能拿 v2 这次 run 当"被闸门放行"的例子：那次 run 没有被任何闸门看过。
- 因此 v2 的这次 run 在 `baseline-v2-recipe` 里记的是"开训早于**闸门**（不是早于协议）"。

## 未覆盖边界

只管"协议存在且被绑定"这一条，不管协议内容是否恰当（内容归版本 PLAN 与验收记录）。
不覆盖已在跑的旧线；不追溯为历史 run 补协议。
