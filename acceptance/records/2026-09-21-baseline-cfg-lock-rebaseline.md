# 冻结基线第三次与第四次重锚：baseline 线的 `cfg_lock.json`（v2 落地 / v2 终止项改判据）

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

## 第四次重锚（同日）：v2 头链终止从**承重**判据改成**接触**判据

**触发**：真跑读数推翻了原判据的可执行性。v2 第三个变量原写"胸/颈法向力 > 10% 体重持续 0.5 s 即终止"，
但接触抖动让它形同虚设——同一策略 **66% 的帧**压在 10% 体重之上（颈部时均 87.2 N = 12.3% 体重），
却**从未连续超过 0.22 s**，照旧定义训练期会整段穿过。改为**触地即终止**：竖直反力 > **1 N**
（与 `base_contact` 同一个"接触"值）、`dwell_s: 0`。

| 项 | 值 |
|---|---|
| 旧摘要 | `c012501dbb0e6483076ed428085dbf897ed30ed212e34fef23f5cc421bcce2c0`（第三次重锚写入） |
| 新摘要 | `c20eb597be577118be6147b71f9e355f75d50b30d644604e511413bb6fa6b055`（174828 字节，4 条任务） |
| 逐字段漂移 | 三条，且**只在** `Lizard-Baseline-Flat-v2` 与 `Lizard-Baseline-Flat-Play-v2`：`head_load_contact.params.load_fraction_of_weight: 0.1 -> <absent>`、`…dwell_s: 0.5 -> 0.0`、`…load_n: <absent> -> 1.0` |
| v1 两条任务 | **逐字段未变**（`--update` 的 `change:` 行只列 v2 两条） |
| 闸门 | `check_cfg_lock` → `CFG_LOCK_OK`；本记录更新摘要后 `check_golden_frozen` → `GOLDEN_FROZEN_OK` |

条件 1–3 与上文相同。这一轮还顺带验证了一件事：**参数名换掉**（`load_fraction_of_weight` →
`load_n`）之后 v1 的两条任务仍然逐字段不动 ⇒ 该终止项对 v1 的解析路径确实无关，v1 的 golden 不可
被这条线的后续改动碰到。

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
