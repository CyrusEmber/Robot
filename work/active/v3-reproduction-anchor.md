---
id: v3-reproduction-anchor
title: v3 复现锚缺失：补 tag 或改记 commit 锚（PLAN #17）
scope: rl_exp/versions/lizard/main/v3, rl_exp/versions/lizard/FAMILY.md
status: open
landing: rl_exp/versions/lizard/FAMILY.md, .codemaker/rules/versioning.mdc
next: 二选一（执行者按可考古性定，v5 先例 = tag 当日撤、NOTES 记 git commit 锚）：① 考古训练起点 commit，补打 tag；或 ② 把 FAMILY 退休注记里"v1/v3/v5 复现走 `git checkout <tag>`"的 **v3 那一条**改成 commit 锚（v1 与 v5 各有自己的锚，不动）。`check_version_docs.py` 对缺 tag 只 WARN；本项不动 v3 的配方、资产与锁
close_when: 执行者对照 FAMILY 退休注记与 `check_version_docs.py` 输出：补 tag 走法 = v3 目录不再出现在 "no git tag" 的 WARN 里；改锚走法 = 退休注记那行给出 v3 的 commit 锚（不再只写 `git checkout <tag>`），并写明 tag WARN 对本线作何解释 ⇒ 任一成立即关；两者都没做 ⇒ 保持 open
---

## 当前状态

血统闸 review（2026-09-11）发现：v3 已训（2026-09-01 首跑）但无 git tag，而 FAMILY 的退休注记把 v1/v3/v5 一起写成"复现走 `git checkout <tag>`"——对 v3 落空。原地复现已整体退役，所以需求弱（旧 ckpt 本就不能回放），但注记与事实不一致会继续误导；`check_version_docs.py` 对缺 tag 持续 WARN。

## 未覆盖边界

本项只补锚或改注记，不重建 v3 的可复现性（退役是资产换代的后果，属已成立的家族事实），也不动 tag 纪律本身（归 `.codemaker/rules/versioning.mdc`）。
