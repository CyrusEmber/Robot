# 冻结基线第三次重锚：baseline 线的 `cfg_lock.json`（v2 落地）

## 适用范围

本记录 = `rl_exp/versions/lizard/baseline/cfg_lock.json` 这一次**有意的 re-baseline**：该线新增
第二版 `v2`，锁定文件从 2 条任务变为 4 条。`check_golden_frozen.py` 的 §B0 表与
`rl_exp/versions/lizard/ACCEPTANCE.md` 的索引行随之更新。

- 看守：`check_golden_frozen.py`（摘要）与 `check_cfg_lock.py --line lizard/baseline`（逐字段）。
- 不覆盖：其它三条冻结基线（`cfg_baselines.json`、main 与 parkour 的 lock）本轮**摘要未变**；
  也不覆盖"重锚流程本身"——流程证据在 `acceptance/records/2026-09-16-lizard-frozen-baseline-reanchors.md`。

## 验收条件

1. 重锚必须是**有意的**：先跑 `check_cfg_lock.py --line` 看逐字段漂移，确认只有 v2 两条任务变化。
2. v1 的两条任务**逐字段不得变**——本次唯一的目的是新增版本，不是改旧版本。
3. 摘要更新与理由必须落在同一变更内，且 §B0 表、ACCEPTANCE 索引、本记录三者互指。
4. 未通过上述三项前，闸门 `[35]` 必须保持红。

## 结果

| 项 | 值 |
|---|---|
| 旧摘要 | `a84f19acb7428e544f7385fc74ad5cad51840bc7f8af3d05eb6d6f5f80731929`（2026-09-18 v1.1 重锚写入） |
| 新摘要 | `c012501dbb0e6483076ed428085dbf897ed30ed212e34fef23f5cc421bcce2c0`（174805 字节，4 条任务） |
| 漂移内容 | `2 task(s) added: ['Lizard-Baseline-Flat-Play-v2', 'Lizard-Baseline-Flat-v2']`；随后的两次 `--update` 各自只改这两条（v2 的 runner cfg、v2 的 `head_load_contact` 终止项） |
| v1 两条任务 | **未漂移**（每一轮 `check_cfg_lock --line lizard/baseline` 都先看到只报 v2） |
| 逐字段证据 | `check_cfg_lock.py --update --line lizard/baseline --reason ...` 打印的 `change:` 行，共三轮（新任务 / runner cfg / 终止项） |
| 闸门 | `check_cfg_lock` → `CFG_LOCK_OK (4 tasks)`；`check_golden_frozen` → `GOLDEN_FROZEN_OK` |

**为什么这次能证明"参数化是值保持的"**：v2 把"动作组驱动哪些关节"与"守卫哪些 body"做成 yaml 参数，
改的是共享 element；如果参数化改变了 v1 的解析结果，v1 两条任务会同时漂移。它们没有 ⇒ 重构对已训版本
是逐字段等价的——这是本轮最想要的证据，也是"重锚前必看逐字段漂移"这条规矩的直接收益。

## 证据引用

- 重锚点：`rl_exp/tools/verify/check_golden_frozen.py` §`FROZEN`（baseline 一行 + 理由注释）、
  `FROZEN_REVS`（两步式的第二笔，指向本次落摘要的提交）。
- 索引：`rl_exp/versions/lizard/ACCEPTANCE.md` 的 §B0 行。
- 冻结文件本身：`rl_exp/versions/lizard/baseline/cfg_lock.json`。
- 配方侧证据：`acceptance/records/2026-09-20-baseline-flat-eval-protocol.md`（v1 漏判）、
  `work/active/baseline-v2-recipe.md`（v2 的三条变量与其硬前置）。

## 未覆盖边界

- 摘要只覆盖 `baseline/cfg_lock.json`；**其它三条基线本轮未复核**（它们未变，但不是本轮证的）。
- `FROZEN_REVS` 的 rev 是"落摘要的那次提交"，需要一笔跟进提交才能填准——这是本仓两步式重锚的固有
  形状（先摘要、后 rev），不是遗漏；在本记录写下时该行仍是上一次的 rev。
- 本次重锚**不**主张 v2 已冻结：v2 的开训前置（验收协议冻结 + 探针复测）尚未完成，见
  `work/active/baseline-v2-recipe.md`。锁的是"v2 的配方解析结果"，不是"v2 可以开训"。
