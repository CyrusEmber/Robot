---
id: verified-rebuild-rating
title: 隔离重建的「已验证重建」评级（#18 ①；② 半已收）
scope: rl_exp/tools/runrecord, rl_exp/versions/lizard
status: open
landing: rl_exp/tools/runrecord/rebuild.py, rl_exp/tools/runrecord/provenance.py, rl_exp/versions/lizard/ACCEPTANCE.md
next: 三件要同时接通才算落地：① 归档 —— 不可由 rev 取回的内容（含 `code.<source>.untracked*`）落 `rl_exp/archive/<run_id>/` 并随仓提交，无落点仍硬拒采；② rebuild 校验接住归档材料，使"与历史那份同源"可判；③ 旧格式降级 —— 旧记录缺摘要一律读作 unknown，**不得**用当前文件补出历史真实性。② 半（地形产物一致）已收：读法与未覆盖边界在 `work/closed/2026/terrain-evidence-18b.md` 与 `work/closed/2026/terrain-suite-v2-rng.md`，本条不复述
close_when: 执行者在一次真 run 上走完 ①→②→③ 并观察：run 目录里未跟踪代码既有名字也有内容摘要、随仓提交后能在重建位置被核；旧记录读作 unknown 而不是被当前文件补齐 ⇒ 三件成立即关。任一未接通 ⇒ 保持 open 并写明断在哪一件。归档位置与 `rebuild.py` 角色的规格**已裁决**（`acceptance/records/2026-09-22-terrain-evidence-archive-and-verification.md`）：证据住运行目录、`rebuild.py` 只管材料完整性；本项只管评级与历史 `unknown`
---

## 未覆盖边界

本项不改"历史 run 未采到的证据保持 unknown"这条读侧口径（standing 规则，见 `HARNESS.md` 记录格式节），也不重开归档位置的裁决；`--capture`/`--check` 的通过判词不复述。
