---
id: eval-protocol-before-training
title: 开训前必须已有冻结的验收协议（启动闸门，而非事后补口径）
scope: rl_exp/tools/runrecord, rl_exp/tools/verify, ablation_harness, rl_exp/versions/lizard
status: open
landing: rl_exp/tools/runrecord/manifest.py, rl_exp/tools/verify/offline_suite.py, ablation_harness/HARNESS.md
next: ① 定形态：在 `manifest.begin` 的拒绝集合里加一条"本版本没有冻结的验收协议（或协议摘要与声明不符）即拒绝开训"，与既有 `dirty_tree_refusal` 同一位置、同一报错风格；判定所需的"协议绑定"从哪来（`obs_protocol` 已有 `declared protocol + digest` 先例，照抄该形态而不新造注册表）在动工前写清。② 写反证：缺协议 ⇒ 拒绝且报错点名缺什么；协议存在但被改 ⇒ 摘要不符即拒。③ 落文档：`ablation_harness/HARNESS.md` 写清"协议在开训前冻结、训后只读"，版本模板的 kickoff 清单加一行
close_when: 执行者真起一次训练命令观察启动行为——本版本无协议 ⇒ 训练在 begin 处被拒且提示写明缺哪份协议；补上协议后同一命令开训成功。两个分支各留一条证据（日志片段或测试），写入 `acceptance/records/`，本项关闭
depends_on: baseline-eval-protocol-gap
evidence: acceptance/records/2026-09-20-baseline-flat-eval-protocol.md
---

## 问题与本次范围

本轮暴露出的是**流程漏洞**，不是缺数据：验收口径是在训练跑完之后才被追问"够不够"的，而开训前
并没有任何机制要求"这个版本将被什么判据判"。开训前的探针钉了标准（四脚承重、头链零载荷），
验收器却读了另一套更弱的口径——两套工具、两把尺子，谁都没错，合起来就是漏判。

本项要的是**顺序**：协议的冻结与摘要绑定发生在训练之前，训后协议只读。已有可用的机器：
`manifest.begin` 的拒绝集合（脏树拒绝先例）、`obs_protocol` 的"声明协议 + 摘要"形态、
离线套件的契约式检查。本项不新造机制，只把它们接起来。

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
