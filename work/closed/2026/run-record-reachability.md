---
id: run-record-reachability
title: 实跑引用走不到：run 记录的文档可达落点
scope: rl_exp/tools/runrecord/manifest.py, rl_exp/versions/lizard
status: done
landing: rl_exp/tools/runrecord/manifest.py
outcome: 裁决 = **可达性是"路径 + 时间戳"，不是"仓内可点"**。`versioning.mdc` §A-2 改为：实跑必须写 run 目录路径 `logs/rsl_rl/<experiment_name>/<时间戳>`（同一 `experiment_name` 下有多条 run，缺时间戳指向的是目录），正文留该目录的 `run_manifest.json` / `checkpoints.json`，记录本体机器本地不进仓（IsaacLab 根由 `paths.yaml` 解析），**记录不完整时写明缺什么、结果凭什么锚住**。`baseline/v1/NOTES.md` 的实跑段照此填了具体路径 + 复读命令，并**照实写出那次记录是半截的**：`.../lizard_baseline_v1/2026-09-20_12-23-09` 的 `pre_make` 崩于 `AttributeError`，无 argv、无 repo rev、119 个 checkpoint 的 `t1_sha256` 全 `null`，结果的可复现锚是评测报告的 provenance 行（`rev = 2a07c881bc0b`）。这一次的读数另存 `acceptance/records/2026-09-21-baseline-v1-run-record-gap.md`，并查明半截只出现在 2026-09-20 12 点那个窗口的两条 run（88 个 run 普查），故"下一次 baseline 启动复验"另立 `baseline-pre-make-record-check`
evidence: acceptance/records/2026-09-21-baseline-v1-run-record-gap.md, acceptance/records/2026-09-21-version-doc-read-cost.md
---

## 当前状态

已收。读数顺带证明：读者沿 NOTES 的实跑引用能定位到目录与复读命令，**能不能取到 argv 取决于那一次
run 的记录是否完整**——这正是 §A-2 新增那句的由来。

## 未覆盖边界

- 只钉 `baseline/v1` 那一次的读数，不外推其它版本；未复现 AttributeError 的调用栈
  （`prov.code_sources()` 今天实测正常），故"是历史产物还是活缺陷"留给 `baseline-pre-make-record-check`。
- 未测 `launch_recipe.py` 那条启动链；未改 `manifest.py` 的字段口径与写入时机。
- 记录本体不进仓是**裁决**而非妥协缺省：checkpoint/TB 属训练产物（git-auto-sync 判据），
  但其轻量摘要要进仓就得有导出机制，本项不做（那会造第二份可能失真的副本）。
