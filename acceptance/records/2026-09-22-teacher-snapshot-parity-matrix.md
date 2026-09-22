# teacher 快照同步：反向验证矩阵（2026-09-22）

## 适用范围

本记录是 `work/active/teacher-snapshot-asset-sync.md` 要求的**反向验证读数**：核 `check_dr_parity` 的
④机器人块 / ⑤资产契约 / ⑥asset lock 三条，对"资产换代时漏同步教师快照"到底覆盖到什么程度，
并单独查有没有**间接闸门**补位。

**怎么做**：在独立 worktree（`git worktree add --detach <tmp> HEAD`）里逐例"改一处 → 跑闸 → 立即还原"，
主工作树零改动（跑完 `git status` 干净）、旧冻结版本一字未改（变异只活在一次性副本里，随 worktree 删除）。
本记录**只报覆盖与症状**：该补哪条闸、哪些同步动作保留人工纪律，都归 `work/active/teacher-literal-parity-gate.md`
与用户裁决，不在本记录结论里。

**判据的三处收紧（用户 2026-09-22 指出，已按此执行）**：

1. ④**不是**逐行对称比较：实现把规范化行转成 **set**（`rl_exp/tools/verify/check_dr_parity.py:212-227`），
   忽略顺序与重复次数 ⇒ 空 allowlist 只保证"**行集合**一致"，不是"逐行一致"。
2. ③只能先说"不在 ④⑤⑥ 的**直接**覆盖内"，必须另查 cfg_lock 这类机制是否间接覆盖；而"间接锁住单侧配置"
   也**不等于**验证两侧同步。
3. 关节数变化**不必然**要求重算地形尺度：判据是实际体尺、足底尺寸与运动范围，不是"30 关节"这个数字
   （本记录的 C3 因此只改一个尺寸参数，不主张"全量地形都要重算"）。

## 验收条件

- **判据**：每例记录"④⑤⑥ 是否报 + 报的是哪一类错"，并把**控制读数**先跑出来当基线扣除。
- **前提**：`check_cfg_lock.py` 要把本机 `paths.yaml` 复制进 worktree，否则 IsaacLab rev 解析为 `unresolved`
  ⇒ 基线组合对不上、闸门无关地红（复现时必须带这一步）。

## 结果

### 控制读数（未变异）

| 闸 | 结果 |
|---|---|
| `check_dr_parity --strict` | 带 **1 条与本实验无关的红**：worktree 检出的那个提交上 `lizard2\main\v1` 的 asset lock 与 `assets/lizard2/lizard2.usda` 不一致；主工作树当时绿（该锁随后被 `7387031` 更新）。谁先谁后未追，属 lizard2 侧 |
| `check_cfg_lock --line lizard/main` | `CFG_LOCK_OK (32 tasks, 1 line(s), isaaclab=28a37cecdd43|…)` |
| `check_obs_layout` | `OBS_LAYOUT_OK` |

### 逐例（变异 → 报什么）

| 例 | 单侧变更 | ④ 机器人块 | ⑤ 资产契约 | ⑥ asset lock | 其他闸门 |
|---|---|---|---|---|---|
| C1 | 教师 `ArticulationCfg` 内 `max_depenetration_velocity=1.0 → 1.25` | **报**（成对：`family-only` + `teacher-only robot line`） | — | — | — |
| C2a | v14 yaml `joint_order` 改一个关节名 | — | **报结构错误**：`joint_order entry missing in usda: rf_toe_joint` | **报锁变化**：该版本 yaml 的哈希变了 | — |
| C2b | v14 yaml `usd_path` 改指不存在的文件 | — | **报路径错误**：`usd_path missing on disk`；**且该 yaml 的其余声明检查整体消失**（`joint_order` 22→21、body-name lists 65→61） | **报锁变化** | — |
| C3 | 教师冻结地形字面量一个尺寸 `0.35 → 0.99` | **静默** | **静默** | **静默** | **cfg_lock 补位**：4 条 `config drift vs golden`（`Lizard-Rough[-Play]-v1/v2`） |
| C4 | 教师 `_VERSION_FAMILY "lizard" → "lizard2"` | **静默** | **静默** | **静默** | cfg_lock 报 24 条 `golden entry has no registered task (retired task or renamed id)` |

### C4 的机制（报了，但**诊断是错的**）

改 `_VERSION_FAMILY` 后教师任务**照旧注册**（28 条 Rough task id 一条不少），但类的
`params_line` 变成 `'lizard2/main'` —— 教师任务改口自称另一条线 ⇒ `--line lizard/main` 的 cfg_lock
找不到它们，于是报成"**任务消失 / 被改名**"。
这与 `teacher_env_cfg.py:56-63` 注释声称的"错路径会在 cfg 构造时抛错"**不一致**：当误写出的家族**真实存在**时，
注册期**没有任何东西抛错**。

### 覆盖结论（按判据读）

- ④⑤⑥ 报的都是"**你那边的东西变了**"：⑤ 验声明是否成立、⑥ 验内容是否变化、④ 验两侧**行集合**是否一致。
  **没有一条在验证"教师副本与家族侧已同步"**。
- **③ 确认漏检**：教师侧独有的资产派生字面量（本例＝冻结地形尺寸）在 ④⑤⑥ 上**三条全静默**。
  cfg_lock 会因"cfg 变了"报警，但它**无法区分**"有意给教师调参"与"漏同步家族侧改动" ⇒ 不构成同步验证，
  只构成"必须有人来看一眼"。
- 因此**不能**用"三个反例被拦住"推导"覆盖完整"：本矩阵给出的恰是反例的**反面**——有一类缺口三条都不拦。

## 证据引用

- 被验证的实现：`rl_exp/tools/verify/check_dr_parity.py`（④`check_robot_block_parity`、⑤`check_asset_contract`、
  ⑥`check_asset_locks`）、`rl_exp/tools/verify/check_cfg_lock.py`、`rl_exp/versions/freeze_parity.json`
  （subject 声明、`wiring_allowlist` 21 条、`robot_block_allowlist` **空**）。
- 变异点：`rl_exp/tasks/teacher_env_cfg.py`（`ArticulationCfg` 字面量 / `TEACHER_TERRAINS_CFG` / `_VERSION_FAMILY`）、
  `rl_exp/versions/lizard/main/v14/main_params.yaml`（`joint_order` / `usd_path`）。
- 复现：独立 worktree + 一次性探针脚本（逐例改写后 `finally` 还原）；脚本随 worktree 删除，
  本记录持有矩阵的输入与观测输出。闸门落点见 `work/active/teacher-literal-parity-gate.md`。

## 未覆盖边界

- **只跑了单侧变异**：未测"两侧同改到同一个错值"（那种形状要靠 ⑤ 兜底，见 C2a/C2b）。
- **C4 只测了"误写成另一个真实存在的家族"**；误写成不存在的家族未测（按注释应在构造期抛错）。
- **C3 只测了一个尺寸参数、一条版本**：地形字面量里其余资产派生量（网格尺寸、平台宽、border 等）与
  足底/运动范围派生量未穷举 ⇒ 本条只证明"存在一类静默缺口"，不给出缺口总量。
- **cfg_lock 的诊断误导只在 `--line` 过滤下观察到**，全量跑的症状未测。
- 控制读数那条无关红（lizard2 asset lock）归 lizard2 侧，本记录不追其成因。
- 本记录不裁"补哪条闸"、也不裁"哪些同步动作保留人工纪律"。
