# 地形证据的归档位置与核验职责（规格裁决，2026-09-22）

## 适用范围

本记录承接 `work/closed/2026/archive-location-decision.md`（HARNESS 挂账 #4）的**两条规格裁决**，
2026-09-22 由用户拍板。它不搬任何旧节：两条现状在裁决前**已实施并生效**（`rebuild.py` 按运行目录取材；
再生闸按归档自述重建），卡住的不是实现，而是"这算不算照原文交付"的认可。

**与其它记录的关系**：

- 地形几何本身的一致性读数与判据：`acceptance/records/2026-09-20-lizard-terrain-artifacts.md`
  ——本记录解除它「此替代需用户确认」这条边界，**不复述它的任何读数**。
- 重建评级（`PLAN.md` #18 ①"已验证重建"）与"历史 run 无归档一律 `unknown`"：
  `acceptance/records/2026-09-15-lizard-resume-payload-chain.md`；余下动作仍归
  `work/active/verified-rebuild-rating.md`，本裁决不改它。
- 归档目录的定义（放"rev 取不回的内容"）：`ARCH_PLAN.md` 的归档位置判。

**旧关闭条件已作废**：原事项写的观测句"两处不再出现『未获确认前不得当成照原文交付』"**从未以该措辞
存在过**，且它指向的 `PLAN.md` #18 已只剩索引、`ACCEPTANCE.md` 相关正文已迁入记录 ⇒ 不能再用"旧免责句
消失了"当验收，故关闭条件按本记录重写。

## 验收条件

- **判据**：两处规格各只有一种读法 —— ① 地形证据只住运行目录 `terrain/geometry.json`，不再复制一份；
  ② `rebuild.py` 只判**材料完整性**，地形几何一致由**离线再生闸**判，"已验证重建"评级另归
  `verified-rebuild-rating`。引用者不再遇到"未获确认"这类免责语。
- **前提**：裁决建立在"离线再生核验成立"这一事实上，故复跑该闸并以本记录留读数。

## 结果

### 裁决

| # | 裁决 | 依据 |
|---|---|---|
| ① 归档位置 | 保留运行目录 `terrain/geometry.json`，**不**复制到 `rl_exp/archive/<run_id>/` | `rebuild.py` 已按此取材，位置不是措辞而是接线；`rl_exp/archive/` 的定义是"rev 取不回的内容"，而地形可由 suite+seed 再生 ⇒ 放那里既破坏该定义，又造出第二份可与运行目录漂移的副本 |
| ② 核验职责 | `rebuild.py` 核**材料完整性**；"地形几何一致"由**离线再生闸**核；"已验证重建"评级归 `verified-rebuild-rating` | "材料还在不在"与"地面对不对"是两种断言；塞进同一个 verdict，会让绿色同时代表两件不同的事 |

### 理由改正（用户 2026-09-22 指出；这条改正收紧本裁决的边界）

原状理由写的是"该证据由 suite+seed 即可再生 ⇒ 随记录入库即为取回得来"。**这条不成立**：
suite+seed 可再生，**不等于**历史证据可取回 —— 平台代码、IsaacLab 版本与生成器实现都会变
（再生闸自己的天花板自述：归档 pin 住的是"当时的地面是什么"，不是把它复活）。故：

- **必须保留原始几何记录及其版本身份**（归档自述的 `suite` + `seed` + 定义摘要）——它才是那份地面的证据；
  再生闸是"这份自述今天还解释得通吗"的检查，**不是它的替代品**。
- **历史缺证据的 run 继续判 `unknown`**，不得由当前代码补出真实性。

### 复跑读数（2026-09-22，本裁决当日）

| 闸 | 命令 | 结果 |
|---|---|---|
| 地形再生 | `E:\IsaacLab\env_isaaclab\Scripts\python.exe -m pytest rl_exp/tools/verify/test_terrain_geometry.py -q` | `6 passed, 55 warnings in 5.13s`，含按归档自述重建那一例（摘要与逐格均一致） |
| 账本形状 | `python rl_exp/tools/verify/check_work_docs.py`（另跑 `--self-test`） | 绿：`WORK_DOCS_OK`；自检 `WORK_DOCS_SELF_TEST_OK` |
| 版本记录 | `python rl_exp/tools/verify/check_version_docs.py` | 绿：`VERSION_DOCS_OK`（含"未冻结版本无 tag"的既有 WARN） |

## 证据引用

- 现状实现（裁决的载体）：`rl_exp/tools/runrecord/rebuild.py`（把运行目录的地形件当材料交给 `--check` 重算摘要）。
- 再生闸与其自述天花板：`rl_exp/tools/verify/test_terrain_geometry.py`、
  `rl_exp/tools/verify/terrain_split_probe.py`（`[TERRAIN_GEOMETRY]` 打印行）。
- 归档目录的定义：`ARCH_PLAN.md` 的归档位置判。
- 本裁决的入站指针：`ablation_harness/HARNESS.md` 挂账 #4 行、
  `acceptance/records/2026-09-20-harness-migration.md` 的挂账去处表、
  `work/active/verified-rebuild-rating.md`、`acceptance/records/2026-09-20-lizard-terrain-artifacts.md`。

## 未覆盖边界

- **缺件是静默的，本裁决接受这一静默**：`rebuild.py` 取运行目录的地形件时是"存在才收"——run 目录
  **没有** `terrain/geometry.json` 时既不拒采也不报问题，该 run 的"地形产物一致"**根本没被核过**。
  本裁决的读法是"**不宣称一致**"（≠"判定不一致"），**未新立动作**；要改成可见的 `unknown`，
  须在 `work/active/verified-rebuild-rating.md` 里另立窄项。
- **不覆盖"这份地面今天还跑得动"**：几何摘要一致 ≠ 训练/评测行为一致；物理与渲染侧的复现仍归"已验证重建"。
- **只裁规格，不裁排期**：评级与历史 `unknown` 的取回路径不在本记录。
- **再生闸的有效范围**：只对归档自述的 suite+seed 有效；套件或协议定义改动后历史归档会比不过——
  这正是"必须保留原始记录与版本身份"的原因，不是回归。
