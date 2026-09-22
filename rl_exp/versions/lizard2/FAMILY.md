# lizard2 训练家族总文档

> 一个版本 = 一代训练配方（参数冻结副本 + 版本文档 + 训练记录）。代码共享继承，参数严格按版本隔离：
> 跑某个 `vN` 只读它自己目录里的冻结副本，开发态参数的修改永不影响已冻结版本。
> **本文只收已成立的事实（现在时/过去时）**：任何"待/未/若"字头的内容住 [PLAN.md](PLAN.md)。
> **继承机制按引用不复制**：升版五步、状态机、记录规范、PLAN/NOTES 必含骨架从
> `.codemaker/rules/versioning.mdc` §A 继承，本文不复制规则正文；目录职责、闸门清单、
> 版本目录登记行见仓根 `FILEMAP.md`（本文不重复）。

## 家族身份

lizard2 = lizard 的**四足构型修正版**：在每条腿的根部**插入一条竖直轴髋关节（`*_hip`）**，
腿链成为 `hip(Z) → haa(−X) → hfe(−X) → kfe(−X) → foot(+Y)`，共 30 关节；
旧构型腿链是 `haa(−X) → hfe(Z) → kfe(−X) → foot(+Y)`，26 关节。
家族存在的原因是"迈步轴装错了段"：旧构型唯一带竖直轴、名义上负责迈步的关节 `hfe` 坐在股骨远端
（轴线到脚掌的力臂仅 0.06–0.07 m），承重姿态下扫满行程也只有 0.11–0.13 m 脚掌前后移动；
把竖直轴移到腿根后力臂 0.49 m，四腿承重行程 0.55 m。实测表与口径见
`acceptance/records/2026-09-22-lizard2-stride-at-load.md`（旧构型对照见同名 2026-09-21 记录）。
其余 27 个共有 link 的质量与网格与 lizard 逐字节相同（`acceptance/records/2026-09-22-lizard2-family-landing.md`）。

## 线

- `versions/lizard2/main/` = 本家族第一条线。线根放该线的开发态参数与配方锁
  （`main_params.yaml` / `cfg_lock.json`），`vN/` 放冻结副本。
- 家族级文档（`FAMILY.md` / `PLAN.md`）落在 `versions/lizard2/`，**不在 `main/` 里**。
- 线之间的隔离是硬约束：本线不 import 其它线的 cfg/mdp，要哪个核就复制一份进本线自己的模块。

## 任务注册表

真源是 `rl_exp/tasks/recipe.py` 的配方表 + `versions/recipes.json`（本文只留人类速查）。

| 任务 id | 配方来源 |
|---|---|
| `Lizard2-Flat-v1` | `lizard2-flat-v1@1`（冻结参数 `versions/lizard2/main/v1/main_params.yaml`） |
| `Lizard2-Flat-Play-v1` | `lizard2-flat-play-v1@1`（冻结参数 `versions/lizard2/main/v1/main_params.yaml`） |

## 版本历史

血统 SSOT = 各版本目录 `base.json`（唯一母本边；决策引用留在 PLAN 散文）。`vN` 编号只是句柄，不是顺序契约。
**身份（这版是什么）与教训只在这里**；判决读数归各 `vN/NOTES.md`。

| 版本 | 日期 | 摘要 | 教训 |
|---|---|---|---|
| main/v1 | 2026-09-22 | 新骨骼上的第一条线：髋轴补齐 + 无 DR、无课程的平地速度追踪配方（`lin_vel_x ∈ [0, 2]`，奖励/终止沿用 v1 基线）；血统根 ⇒ `base.json` 为 `null`，比较对象是框架 stock | （训练后补） |
