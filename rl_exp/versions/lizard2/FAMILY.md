# lizard2 训练家族总文档

> 一个版本 = 一代训练配方（参数冻结副本 + 版本文档 + 训练记录）。代码共享继承，参数严格按版本隔离：
> 跑某个 `vN` 只读它自己目录里的冻结副本，开发态参数的修改永不影响已冻结版本。
> **本文只收已成立的事实（现在时/过去时）**：任何"待/未/若"字头的内容住 [PLAN.md](PLAN.md)。
> **继承机制按引用不复制**：升版五步、状态机、记录规范、PLAN/NOTES 必含骨架从
> `.codemaker/rules/versioning.mdc` §A 继承，本文不复制规则正文；目录职责、闸门清单、
> 版本目录登记行见仓根 `FILEMAP.md`（本文不重复）。

## 家族身份

lizard2 = lizard 的四足构型修正版，保留每腿 `hip → haa → hfe → kfe → foot` 与机身关节，共 30 个可动关节。当前 main/v3 采用用户于 2026-10-08 批准的候选站姿骨架；旧机体 main/v1、main/v2 同次退休，保留历史配方与任务身份，不再承诺新训/续训与当前树复现。

家族起源与旧机体的轴向/网格事实归历史记录 `acceptance/records/2026-09-22-lizard2-family-landing.md`、`acceptance/records/2026-09-22-lizard2-stride-at-load.md`。当前机体来源与采用记录归 `acceptance/records/2026-10-08-lizard2-v3-landing.md`。

## 设计入口

当前版本为 main/v3：2026-10-10 冻结（tag `lizard2-main-v3`）并启动训练（预算 6000 迭代），方案入口见 [PLAN.md](PLAN.md)，正文唯一归 [main/v3/PLAN.md](main/v3/PLAN.md)。

## 线

- `versions/lizard2/main/` = 本家族第一条线。线根放该线的开发态参数与配方锁
  （`main_params.yaml` / `cfg_lock.json`），`vN/` 放冻结副本。
- 家族级文档（`FAMILY.md` / `PLAN.md`）落在 `versions/lizard2/`，**不在 `main/` 里**。
- 线之间的隔离是硬约束：本线不 import 其它线的 cfg/mdp，要哪个核就复制一份进本线自己的模块。

## 资产树（2026-10-08）

声明 `versions/lizard2/assets.json` 指向 `lizard2_candidate/meshes`。当前正式机体为 `lizard2_candidate/lizard2_candidate.usda`，同目录 `<stem>.urdf` 与相对网格引用构成实际资产集合。USD 采用原候选转换产物，未重算骨架；来源 DCC 为 `blender/lizard2_stance_candidate.blend`。
旧 `versions/lizard2/meshes` 与 `assets/lizard2/lizard2.usda` 留作历史，不由当前活跃配方消费。资产换代退休规则从版本纪律继承。

## 任务注册表

真源是 `versions/recipes.json`（身份映射）+ 本线自己的配方声明模块（元素表与配方表 = `rl_exp/tasks/lizard2_recipe.py`；`rl_exp/tasks/recipe.py` 只留 `LINES` 路由与构建机制）（本文只留人类速查）。

| 任务 id | 配方来源 |
|---|---|
| `Lizard2-Flat-v1` | `lizard2-flat-v1@1`（冻结参数 `versions/lizard2/main/v1/main_params.yaml`） |
| `Lizard2-Flat-Play-v1` | `lizard2-flat-play-v1@1`（冻结参数 `versions/lizard2/main/v1/main_params.yaml`） |
| `Lizard2-Flat-v2` | `lizard2-flat-v2@1`（冻结参数 `versions/lizard2/main/v2/main_params.yaml`） |
| `Lizard2-Flat-Play-v2` | `lizard2-flat-play-v2@1`（历史参数 `versions/lizard2/main/v2/main_params.yaml`；退休） |
| `Lizard2-Flat-v3` | `lizard2-flat-v3@1`（参数 `versions/lizard2/main/v3/main_params.yaml`） |
| `Lizard2-Flat-Play-v3` | `lizard2-flat-play-v3@1`（参数 `versions/lizard2/main/v3/main_params.yaml`） |

## 版本历史

血统 SSOT = 各版本目录 `base.json`（唯一母本边；决策引用留在 PLAN 散文）。`vN` 编号只是句柄，不是顺序契约。
**身份（这版是什么）与教训只在这里**；判决读数归各 `vN/NOTES.md`。

| 版本 | 日期 | 摘要 | 教训 |
|---|---|---|---|
| main/v1 | 2026-09-22 | 新骨骼上的第一条线：髋轴补齐 + 无 DR、无课程的平地速度追踪配方（`lin_vel_x ∈ [0, 2]`，奖励/终止沿用 v1 基线）；血统根 ⇒ `base.json` 为 `null`，比较对象是框架 stock | （训练后补） |
| main/v2 | 2026-09-28 | v1 对照版：脚板四关节退出动作接口，其余沿用 v1；母本 main/v1。2026-10-08 因机体采用退休 | 历史结果见 main/v2/NOTES.md |
| main/v3 | 2026-10-08 | 用户批准的候选机体采用；基于 v2 摘除 kfe 策略动作，保留全部可动关节、PD 与默认零目标；唯一母本 main/v2，旧机体版本同次退休 | 自检/限制见 `acceptance/records/2026-10-08-lizard2-v3-landing.md` |
