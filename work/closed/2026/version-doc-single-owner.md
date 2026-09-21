---
id: version-doc-single-owner
title: 版本记录单一维护位置：治理"复制继承 + 修订失联"
scope: .codemaker/rules/versioning.mdc, rl_exp/versions/lizard/baseline/v1/NOTES.md
status: done
landing: .codemaker/rules/versioning.mdc, rl_exp/versions/lizard/baseline/v1/NOTES.md
close_when: 两读法各留一次实测读数 ⇒ (a)(b) 两个决定都有结论即可关；未做的动作（措辞闸门、若决定做）另立活跃事项
outcome: 规则改在唯一维护位置：§A 步骤 1 加"copy 后重置正文"，步骤 2 的骨架改为 PLAN 管设计 / NOTES 记实际与结论 + 差异引用，§B 加第 6 条（差异集合或比较基线变了 ⇒ 改 `diff.json`，含义改向还须复核 `why`/`base.json.note`/重点摘要；历史漂移豁免不清零）。试点落在 `baseline/v1`（该线 copy 源头），记为 v1.2 记录性修订并补 PLAN §修订行。A/B 双读者读数：A（摘要+链接）3 份 23054 B 答全 4 问，B（只声明）2 份 7486 B 只答 2 问且 Q3 结构性无解 ⇒ **决策 (a) 保留 1–2 句重点变化但不承诺完整性、(b) 不做措辞闸门**（根因已由 §A-1/§B-6 承接；禁令会误伤有范围限定的合法事实并与"冻结历史不改写"冲突），闸门**重议触发保留**：再开两个新版本后若仍现全量句失真则重提。读数另暴露一条缺链——实跑命令行在版内四份文件里都不存在，已另立 `run-record-reachability`
evidence: acceptance/records/2026-09-21-version-docs-drift-audit.md, acceptance/records/2026-09-21-version-doc-read-cost.md
---

## 问题与本次范围

治理两件事，不是"删手写摘要"：**复制继承**（`copy vN vN+1` 连 `PLAN.md`/`NOTES.md` 正文一起继承）
与**修订失联**（修订只补「修订历史」「目的」段，差异段要点不动）。

保留 1–2 句"本版重点变化"作**阅读提示**，撤掉它的**完整性承诺**——危险的是"其余照 X / 零变更"
这类会被后续修订推翻的全量句，不是摘要本身。

## 试点结果

`baseline/v1`（已冻结；选它因为它就是该线的 copy 源头，下一版继承的正是它这套骨架）：差异段改为
阅读提示 + `diff.json` 链接、命令段分「计划 / 实跑（引运行记录）」，头部与 `PLAN.md` §修订同步记 v1.2。
锚点未破——配方、`diff.json`、结果表逐字未动，tag 仍指原 commit，T1 摘要钉的是 cfg 不是文档。

## 未覆盖边界

- **不重写历史**：`baseline/v2`、`main/v3`、`main/v8` 的 stale 差异段保留，历史 stale 明确豁免、不清零；
  新规则只对新建与未冻结版本生效。
- 未新增运行记录：`argv`/`seed`/`num_envs`/`session_overrides` 已在 `rl_exp/tools/runrecord/manifest.py`
  的 T0/T1 里；`why` 的语义漂移无自动判据（`main/v12` 的方向错误仍靠人复核）。
- 未做措辞闸门（决策见 `outcome`，重议触发已记）。
- 读数只两个读者、一个版本，无统计意义；run 记录可达性另立事项，不在本项。
