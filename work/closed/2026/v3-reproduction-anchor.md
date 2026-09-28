---
id: v3-reproduction-anchor
title: v3 复现锚缺失：补 tag 或改记 commit 锚（PLAN #17）
scope: rl_exp/versions/lizard/main/v3, rl_exp/versions/lizard/FAMILY.md
status: done
landing: rl_exp/versions/lizard/FAMILY.md, .codemaker/rules/versioning.mdc
outcome: 走 close_when 的"改锚"支线，但**改成了事实而不是 commit 锚**：核过 v3 的训练（2026-09-01）早于 run manifest 与版本目录化（v3 目录由 2026-09-16 的 A0 布局迁移建立，冻结时它还在旧布局），manifest 无 `repository.rev`、`git log` 只能在旧布局里考古 ⇒ **v3 没有任何可核的 rev 可写**，写一个靠猜的 commit 锚比不写更坏。故 `versions/lizard/FAMILY.md` 的退休注记新增"锚点实况（2026-09-28 核）"段：v1=`v1`、v5=`v5`（旧拼写）；**v3 无锚 ⇒ 不可原地复现，只能作读数来源**；其余无 tag 的版本同样无锚，并写明 `check_version_docs.py` 对缺 tag 按 `versioning.mdc` §A 只 WARN（历史前缀可不统一）⇒ 那些 WARN **不是欠账**。顺带修两处规范不一致：§A 第 5 步的 tag 拼写由 `<family>-vN+1` 改为 `<family>-<line>-vN+1`（与闸门、与盘上 `lizard2-main-v1.4`/`lizard-baseline-v1` 对齐）；`check_version_docs.py` 的 WARN 文案不再对线内版本列出它实际不接受的裸 `vN`（旧文案会把人支去补一个照样报警的名字）
evidence: acceptance/records/2026-09-22-lizard-family-retirement
---

## 当前状态

已收。原文给出的两条出路里，①（补 tag）**不可执行**：没有可核的 rev；②（改锚）以"无锚 + 为什么 +
WARN 作何解释"落地在 FAMILY 退休注记。**与 close_when 字面的偏差已写明**：它要求"给出 v3 的 commit 锚"，
而实际结论是"无锚可给"——这一条由评审挑战，本项不把它藏起来。

## 未覆盖边界

- **只改注记与规范拼写**，不动 v3 的配方、资产与锁，也不重建 v3 的可复现性（退役是资产换代的后果）。
- **不扫其余无 tag 版本**：v0/v4/v7/v9/v12–v15、`parkour/v1` 同样无锚，其中 `parkour/v1` 的 run
  (`lizard_parkour_climb_v1/2026-09-17_17-02-16`) manifest 有 rev 但 `dirty=True`（树不可完整还原）。
  要不要补这类"弱锚"是 owner 判定；本项只把事实记在 FAMILY，不据此派活。
- **闸门仍会 WARN**（按规则允许），本项不追求把 WARN 清零；清零只能靠补 tag 或给旧拼写开白名单，
  两者都不是本项。
- v3 的 `NOTES.md` 是 GBK 编码（按 UTF-8 读是乱码），本项未改；它影响任何按 UTF-8 读该文件的读者，
  若要处置属另一件。
