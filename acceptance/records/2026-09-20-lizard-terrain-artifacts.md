# 地形产物一致（`PLAN.md` #18 ② / ① / ⑤b 收口，2026-09-20）

## 适用范围

本记录搬运 `rl_exp/versions/lizard/ACCEPTANCE.md` 的 §追加（2026-09-20）· 地形产物一致
（`PLAN.md` #18 ② / ① / ⑤b 收口）。

**收的是什么**：地形**几何产物**的一致性与可复算性 —— 同 cfg 同 seed 两次真跑逐位相同、
起伏（路面高差）从真实生成路径量出来、以及"按归档自述重建 ⇒ 摘要一致"。
它补的是地形映射记录（3.3）明确留空的那一格："**几何一致性仍未知**：映射一致不替代几何证据
（未归档核验 mesh/heightfield，本轮不执行）"。

**与其它记录的关系**：

- 地形映射（列→combo 记录、探针、两处课程消费）：`acceptance/records/2026-09-17-lizard-eval-record-and-terrain-map.md`。
- 地形产物里的 `[TERRAIN_GEOMETRY]` 摘要随 run 入库，其"记录写侧"的口径（拒写 / compare / 原子写）也在
  同一条记录里（§评审修正）。
- 重建评级（#18 ①"已验证重建"）的落点与"历史 run 无归档一律 unknown"：
  `acceptance/records/2026-09-15-lizard-resume-payload-chain.md`（§1.5a / 已知瑕疵）。

**读本记录须知的通读口径**：历史记录里的 `[N]` 是**当次运行编号**，不是闸门身份，套件总条目数受
`MAX_CHECKS` 棘轮管 ⇒ 成功行读数**只在当日 commit 上成立**。

## 验收条件

### 前提

- 交付件：`29dee47`（`terrain_geometry.py` / `suites v2` / 协议 v3 / `fork_patches\train_seed_rng.patch`）、
  `4051ed5`（计数语义修正）、`a7e0211`（双跑证据入账）。
- 树：双跑 A/B 为**干净树**；反证臂 C 与评测 smoke 走 `RL_ALLOW_DIRTY_TREE`（另一开发者当时正在编辑
  本文件，理由已写入各自记录；C 的 T0 有 `declaration.dirty_tree_override_reason` 明文）。

### 判据（三条）

| 项 | 判据 |
|---|---|
| ② 同 cfg 同 seed 两次真跑 | 逐格摘要**逐位相同**；换 seed 必须变（反证臂） |
| ①/⑤b 起伏 | 从**真实生成路径**量出 `relief_max`，对"面比脚板格大"的网格记 `null` 而不是给假数 |
| ⑤b 再生核验 | 按归档自述的 `suite` + `seed` **重建** ⇒ 逐格摘要与归档一致，且与真跑打印摘要一致 |

## 结果

### 检查与结果

| 检查 | 实测 |
|---|---|
| ② 同 cfg 同 seed 两次**真跑** | `Lizard-Rough-v14 --num_envs 32 --max_iterations 1 --seed 123` 两次 ⇒ `[TERRAIN_GEOMETRY] cells=200 hashed=200 anomalies=0 digest=sha256:b74cb2278a3396aad01ce493b53e8bf9` **逐位相同** |
| ② 反证臂（换 seed 必须变） | `--seed 7` ⇒ `sha256:0b163edff4f2a75d4a39a6943c16531c` |
| ①/⑤b 起伏（真实生成路径） | v3 零动作 smoke ⇒ `cells=9 hashed=9 anomalies=0 relief_max=0.1100@slope_10deg relief_unmeasurable=5 digest=sha256:1fc13fa2…`；归档 `rough_a 0.030 / rough_b 0.065`（v1 同位置常值 `0.0` 作参照），`flat` / 楼梯 / gap 记 `null` |
| ⑤b 再生核验（离线） | 按归档自述的 `suite`+`seed` 重建 ⇒ 逐格摘要与归档一致；离线重建摘要 == 真跑打印摘要（`1fc13fa2…`，9 格） |

### 本批修正（都是"数字说谎"）

- `early_done_envs` 把末步超时数成"早收局"（`dones = truncated | terminated`，`termination_manager.py:104`）
  ⇒ 实测 `captured=72` 却 `fall=0.000`，读起来像"72/72 全中途摔倒"；改印 `resets_in_rollout` /
  `early_terminations`（`4051ed5`）。
- 起伏的顶点法对"面比脚板格大"的网格给出假数：楼梯列 264 顶点跨 16 m，0.5 m 格报 0.87 m（真值 0.10 m 踢面）
  ⇒ 加面尺寸闸（> 0.5 m 即记 `null`），天花板与升级路径（射线采样）写进 `foot_relief` docstring。

## 证据引用

- 几何产物与协议：`rl_exp/tools/verify/terrain_geometry.py`、`suites v2`、协议 v3、
  `rl_exp/fork_patches/train_seed_rng.patch`。
- 归档与再生：run 目录 `terrain/geometry.json`（如
  `results/locomotion_eval_v3/smoke/.../terrain/geometry.json`）；真跑打印行 `[TERRAIN_GEOMETRY] …`
  （digest `b74cb2278a3396aad01ce493b53e8bf9` / `0b163edff4f2a75d4a39a6943c16531c` / `1fc13fa2…`）。
- 提交：`29dee47`（交付件）、`4051ed5`（计数语义修正）、`a7e0211`（双跑证据入账）。
- 相关记录：`acceptance/records/2026-09-17-lizard-eval-record-and-terrain-map.md`（3.3 地形映射与
  "几何一致性仍未知"的原边界）、`acceptance/records/2026-09-15-lizard-resume-payload-chain.md`
  （重建评级与归档口径）。

## 未覆盖边界

- **归档位置改了**：证据落运行目录 `terrain/geometry.json`，不是 `PLAN.md` 原文的
  `rl_exp/archive/<run_id>/terrain/` —— 它由 suite+seed 可再生、随记录入库即"取回得来"，
  `rl_exp/archive/` 仍留给"rev 取不回的内容"。**此替代需用户确认。**
- **"由 `rebuild.py` 核验"落地为**：`rebuild.py` 核**材料完整性**（`--check` 重算摘要），
  **地形一致由再生判定**。
- **重建评级（#18 ①"已验证重建"）不在本节**，仍单独排期；**历史 run 无归档 ⇒ 一条一律 `unknown`**。
- **三条训练跑都是 `--max_iterations 1` 诊断跑**，**不是可引用的训练结果**。
- **双跑 A/B 的干净树与含 `RL_ALLOW_DIRTY_TREE` 的臂不是同一条件**：反证臂 C 与评测 smoke 在脏树上跑，
  其 T0 带 `declaration.dirty_tree_override_reason` 明文；本节的结论只在**它自己的条件**下成立。
- **口径边界**：三条 digest 与格数（200 / 9）只在**当日 commit 与当日的 suite/协议版本**上成立；
  历史 `[N]` 是当次运行编号，不是闸门身份。
