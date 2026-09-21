# eval 记录（3.2）与地形映射（3.3）+ 评审修正（2026-09-17）

## 适用范围

本记录搬运 `rl_exp/versions/lizard/ACCEPTANCE.md` 的以下旧节：

| 旧节 | 主题 |
|---|---|
| §3.2 | eval 记录（离线 + 真跑，2026-09-17）：格式、三态读侧、绑定面比较、覆盖/拒写、同 seed 对拍 |
| §3.3 | 地形映射（离线 + 真跑，2026-09-17）：切分规则唯一真源 + 列→combo 记录 + 两处课程消费 |
| §评审修正 | 2026-09-17 评审 → 当日修，同树复测（六项） |

**本记录内部的前后作废关系（读结论以此为准，被作废的旧句保留作留痕）**：

- **§评审修正 改变"拒写"的判据**：凡上文（§3.2 及更早）写到"拒绝写入"的证据，
  **以 §评审修正 的口径为准** —— 旧口径把两个"都是 unknown"的绑定也当成差异，
  并漏掉了"有结果、无记录"的历史目录。修正后：`differences`（真差异）与 `unproven`（两侧同 unknown）
  分开；`overwrite_refusal` 只在**真有差异**或前记录不完整时拒。
- **§3.2 的"3.2a 9 例"与 §评审修正的"离线闸门 10 例复测通过"是两个时点的读数**，以后者为准。
- **§3.3 的 3.3f（同配方不同 seed 的产物比对）在本轮未启用 ⇒ 记未知**；`§3.3 结论`把"仍未做/未知"清点
  如下，该清点**不自称 Step 3 全部通过**。
- **§评审修正 的第 6 项（探针记录不释放）与本记录内 §3.3 的 3.3a 闸门读数互为证据**
  （3.3a 实测"追加 12 次生成后仍为 8 条"）。

**读本记录须知的通读口径**：历史记录里的 `[N]` 是**当次运行编号**，不是闸门身份，套件总条目数受
`MAX_CHECKS` 棘轮管（本记录横跨 44 → 46 条条目）⇒ 各节的成功行读数**只在当日 commit 上成立**。

## 验收条件

### §3.2 前提

- 施工件依 `ARCH_PLAN.md`「Step 3 施工件表」（3.2a–f）。本轮**全开工**（用户 2026-09-17 拍板："3.2/3.3 全开工，连真跑段"）。
- 记录落 `results/<协议>/[组/]<run_id>/record.json`；**无 `record.json` 的历史 run = legacy**（0c 规则 1），不回写不补齐。
- 离线闸门 `rl_exp/tools/verify/test_eval_record.py` 入套件 [44]（0.2s）。真跑段全部用**同一棵树**、同一 ckpt（`logs/rsl_rl/lizard_rough_teacher_v14/2026-09-15_10-54-06_v14/model_850.pt`）、seed 123、nominal。

### §3.3 前提

真值在仓外（`E:\IsaacLab\...\terrain_generator.py:243-247`），`sub_indices` 生成后即丢；
课程侧原有**两处逐字复制**。本节的证据顺序按施工件表：**3.3a 是闸口**，3.3c 通过后 3.3d/e 才动。

### §评审修正 的前提

评审提出六项，全部修完；修正的判据见上（"拒写"口径改变）。

## 结果

### §3.2 落地（件号 → 产物）

| 件 | 内容 | 证据 |
|---|---|---|
| 3.2a | `ablation_harness/record.py`：格式定义（`eval-record-1`）、三态读侧、绑定面比较、覆盖拒绝判定、checkpoint 文件摘要 | 套件 [44] 9 例（含"把规则还原回去必失败"的临时反证） |
| 3.2b | `eval.py` 四个采集点（env 侧 / `_make_policy`（加载时哈希 + 加载后复核）/ player 之后（时间线+阈值+扰动）/ `_persist` 一次写） | 真跑 `..._850rec_...`：`state=complete`，六类内容齐 |
| 3.2c | run 唯一性：`--variant` 另起身份、`--overwrite` 显式覆盖，否则**拒写** | 真跑拒绝（见下）；A/A 与重跑走"可比即覆盖" |
| 3.2d | 依赖静态闸（不得 import torch/numpy/random）＋ 同 seed 对拍 | 见下：**逐位相同** |
| 3.2e | P04 四项替换反证 | 离线 + 真跑四项（见下） |
| 3.2f | 真跑一次落全六类内容并核验 | `results/locomotion_eval_v2/v14/Lizard-Rough-v14_850rec_nominal_seed123/record.json` |

### §3.2 检查与结果（本机实测）

**记录可比性（`record.compare`，实际记录文件）**

| 对 | 结论 | 差异绑定 |
|---|---|---|
| `850rec` vs `850recA`（A/A，两次独立真跑） | comparable | — |
| vs `..._1150_..._ckpt1150` | not_comparable | `checkpoint.sha256` |
| vs `..._850_..._suite-roughb016` | not_comparable | `suite.digest` |
| vs `locomotion_eval_v1/v1rec/..._proto-v1` | not_comparable | `eval_protocol.digest` |
| vs `locomotion_eval_v2/dev/..._assets-unknown` | **unknown**（缺证据不升级为可比） | 差异 4 项：`checkpoint.sha256` / `assets.declared_digest` / `obs_protocol.identity` / `obs_protocol.digest`；其中 `assets.declared_digest` 为"两侧同为 unknown"（unproven） |

**3.2d 真跑对拍（同树、同 ckpt、同 seed、同模式）**：`off` 臂 = **无记录版本**的 `eval.py`
（`git show 11f19f4:ablation_harness/eval.py` 在临时目录跑），`on` 臂 = 当前 `eval.py`。

- `off` vs `on`：`global` / `segments` / `terrains` **逐位相同** ⇒ 记录代码不改变数字；
- `on` vs `on`（A/A）：**逐位相同** ⇒ 基线自身可重复（3.2d 明写的前提成立，结论不必记未知）；
- 附带事实：`off` 臂的 global 与 2026-09-15（树 `c5f56ed`）的历史 run **也逐位相同** —— 本次改动没有移动这些数字。

**3.2c 拒绝路径（真跑）**：把 `model_850.pt` 写进已存在记录 `..._1150_..._ckpt1150`
（同 run_id、异 ckpt）⇒ 拒写并**点名** `checkpoint.sha256`，提示 `--variant` / `--overwrite`；
原记录未被改动（拒写在任何写入之前）。

**已观察到的记录状态（真跑，非构造）**：`assets=pass`（v14，冻结锁）／`assets=unknown`（dev 配方无锁）／
`checkpoint=none`（零动作 run 的 `policy.kind=zero_action`）。

**§3.2 未覆盖（不得据此宣称通过）**

- **资产的 fail 路径真跑未做**：造 fail 必须改一支已冻结资产（越界）。离线三态 + `manifest._verify_assets` 既有测试覆盖该分支；真跑只落了 pass 与 unknown。
- `num_envs` 的**声明值 ≠ 实际值**这一格未实测（本次两者同为 72）。
- 记录的 `obs_protocol` 落的是 3.1a 声明身份＋已审摘要，**未**与 3.1e 的 live 契约联合判读。
- `--variant` 名由操作者给：名字写错 = 记录与意图不符，闸门不替人判断（结构性敞口，写在此处）。

### §3.3 落地（件号 → 产物）

| 件 | 内容 | 结果 |
|---|---|---|
| 3.3a | `rl_exp/tools/verify/terrain_split_feasibility.py`：构造真 `TerrainGenerator` + 同时验证两个调用点的关联采集 | **通过**（8.5s；58 sub-terrains、4×120；480/480 格配对、0 异常；`difficulty` 实际值 0.001–1.000；负控制（把声明切分改坏）必红 ⇒ 绿灯不是空跑） |
| 3.3b | `rl_exp/tasks/terrain_map.py`：切分规则唯一真源 + 列→combo 记录结构 + 健全性/配对拒绝 | 套件 [45] 6 例（手算切分 / 配对按 cfg 身份 / 每种健全性违规） |
| 3.3c | `rl_exp/tools/verify/terrain_split_probe.py`：调用时立即快照（两调用点配对），不留对象引用 | 因 3.3a 通过 ⇒ **离线**；真跑观测见下 |
| 3.3d | 两处课程 `__init__` 改消费记录、删重算；`components.terrain` 安装探针（生成发生在 `TerrainGenerator.__init__` 内，事后再包来不及） | 真跑消费见下 |
| 3.3e | 删三处测试副本（`test_v5_terrain_sir.py`、`test_joint_sir.py`、`test_resume_state.py`）＋ 扫描闸 `check_terrain_split_source.py` | 见下 |
| 3.3f | 同配方不同 seed 的**产物**比对 | 本轮未启用 ⇒ **记未知** |

### §3.3 检查与结果

- **3.3c/3.3d 真跑观测**（`terrain_split_env_run.py`，真 env 构造，非 mock）：`Lizard-Rough-v11`、32 env、`terrain_origins (4,120,3)` ⇒ 记录 480/480 格、0 异常、58 个 sub-terrain、120 列；课程 term 的逐类型列归属与记录**逐一致**：stairs 22 / stairs_inv 21 / stepping_stones 11 / boxes 10 / random_rough 22 / slope 10 / slope_inv 11 / flat 13 = 120 列。env 构造能走到这一步本身即消费证据（term 读不到可用记录会拒绝）。
- **"副本不得重现"扫描闸**：对**改前**的 `teacher_mdp.py`（`git show HEAD~1:...`）报 3 项（两处 `frac = col / num_cols + 0.001` + "epsilon 与 cumsum 同文件"），今日 0 项（151 个文件）；匹配器自测（prose 不触发）。
- **离线闸门**：套件 [45]/[46] 0.2s / 0.5s；三处课程测试变慢（v5 3.4→6.1s、joint 3.8→7.6s、resume 5.0→11.0s）：改用**真生成**取记录，替代手写期望（25s/条预算内）。

**§3.3 边界（不得据本节宣称）**

- **几何一致性仍未知**：映射一致不替代几何证据（未归档核验 mesh/heightfield，本轮不执行）。
- **模式区分**：探针只观察 curriculum 模式（列映射）；random 模式按格采样、无可声明的列映射，本轮不观察。
- 探针以 **cfg 身份**为键：同进程内同一 cfg 再生成一次会**从头**记录（已实现），但并发两 env 共用同一 cfg 对象的情形未实测。
- 3.3d 的课程迁移只验证了 **v11**（param-grid + joint SIR）这一条线；v5 家族（payload 地形 + 行 SIR）在离线测试里被真生成覆盖，**未**在真 env 里跑过。

**§3.3 结论**

3.2 与 3.3 的**离线段全部落地**；**真跑段**：3.2d/3.2e（四项替换）/3.2f 已做，3.3c/3.3d 已做。
仍未做/未知：3.2 的资产 fail 真跑、3.1e 全量、3.1f 真跑半、3.3f 产物比对、几何一致性、
3.4（蒸馏与导出）＝**未执行**。**不得**据本节称"Step 3 全部通过"。

### §评审修正（2026-09-17 评审 → 当日修，同树复测）

| # | 缺陷 | 修 | 证据 |
|---|---|---|---|
| 1 | **legacy run 目录可被静默覆盖**：只认 `record.json`，只有 `eval.json` 的目录被当成空 run_id —— 仓内 31 个 run 目录里 **25 个**是这种状态 | 有结果、无记录 ⇒ 按 legacy 拒写（新增 `record.legacy_run()`）；`--overwrite` 为唯一放行 | 真跑（伪造 legacy 目录，跑后删）：**15s 拒写**并点名 legacy；加 `--overwrite` 再跑 ⇒ 放行并落全记录。离线 `test_eval_record` 增一例 |
| 2 | **两侧同为 unknown 被当成差异** ⇒ 无冻结锁的 dev 线自跑即拒（`compare(dev, dev) = unknown`），与"同一次测量重跑即覆盖"矛盾 | `compare` 拆开 `differences`（真差异）与 `unproven`（两侧同 unknown：等而无证，仍判 unknown）；`overwrite_refusal` 只在**真有差异**或前记录不完整时拒 | 真记录实测：`dev vs dev → differences {} / refusal None`；`dev vs base → unknown` 并点名 4 项差异 |
| 3 | **记录的是声明阈值，不是实际用到的派生值**：`tilt_cos_min` / `clearance_min` / `sustain_steps` 未入记录 ⇒ 改法不改数 | 三个派生值改由 `main` 算一次并传入（`_analyze` 不再自算），写进 `metrics.derived`。**有意未设为必需字段**：设为必需会让上文 P04 那批 `eval-record-1` 记录读作"不完整"，从而无法再被自身重写 —— 代价大于收益；派生值的兜底是已记录的 `git_rev_lizard`（harness 代码在同一仓） | 新记录含该字段（结构变更）；离线闸门 10 例复测通过 |
| 4 | **拒写发生在 rollout 之后**：错打 `--variant` 要烧完一次完整 rollout 才被拒 | 绑定齐备处（`_make_policy` 之后）前置 `_guard_writes`，`_persist` 留同一道作兜底 | 真跑实测：同名占用拒写 **15s**（修正前同类拒写约 2 分钟） |
| 5 | **无原子写**：`record.json` → `eval.json` → `summary.csv` 三处直写；截断的 `record.json` 会让**下一次** run 崩在 `JSONDecodeError` | `_atomic_write_json`（tmp + `os.replace`），summary 同样；记录不可读 ⇒ 拒写并说明原因，`--overwrite` 可替换 | 代码 + 离线闸门复测 |
| 6 | **探针记录不释放**：一进程内每 env 一条，扫参数场景无界增长 | `_MAX_RECORDS = 8` 上限（插入序逐出）+ `probe.release(terrain)` | 3.3a 闸门实测：追加 12 次生成后仍为 8 条 |

**结构性敞口（记台账不修）**：两套记录词汇并存（训练 `manifest.py` / 评测 `record.py`，同事实两种命名）；
单源扫描闸守"副本"不守"新规则"。见 `PLAN.md` #27。

## 证据引用

- eval 记录：`ablation_harness/record.py`、`ablation_harness/eval.py`、
  `rl_exp/tools/verify/test_eval_record.py`（套件 [44]）；
  真记录 `results/locomotion_eval_v2/v14/Lizard-Rough-v14_850rec_nominal_seed123/record.json`；
  对拍照 `locomotion_eval_v1/v1rec/..._proto-v1`、`locomotion_eval_v2/dev/..._assets-unknown`；
  `off` 臂 `git show 11f19f4:ablation_harness/eval.py`。
- 地形映射：`rl_exp/tasks/terrain_map.py`、`rl_exp/tools/verify/terrain_split_feasibility.py`、
  `terrain_split_probe.py`、`terrain_split_env_run.py`、`check_terrain_split_source.py`；
  套件 [45]/[46]；真值在仓外 `E:\IsaacLab\...\terrain_generator.py:243-247`。
- 记录词汇的台账项：`PLAN.md` #27。
- 相关记录：obs 协议与 live 契约 `acceptance/records/2026-09-16-lizard-obs-protocol-gate.md`；
  地形产物的几何证据 `acceptance/records/2026-09-20-lizard-terrain-artifacts.md`。

## 未覆盖边界

- **§3.2 不可据此宣称通过的部分（原文保留）**：资产 fail 路径真跑未做（造 fail 必须改已冻结资产，
  越界）；`num_envs` 的"声明值 ≠ 实际值"未实测（本次两者同为 72）；记录的 `obs_protocol` **未与 3.1e 的
  live 契约联合判读**；`--variant` 名由操作者给、写错即"记录与意图不符"（结构性敞口）。
- **§3.3 不可据此宣称通过的部分（原文保留）**：几何一致性仍未知（映射一致不替代几何证据，未归档核验
  mesh/heightfield）；random 模式不观察；并发两 env 共用同一 cfg 对象未实测；3.3d 只验了 **v11** 一条线
  （v5 家族未在真 env 里跑过）；3.3f 同 seed 产物比对**未启用 ⇒ 未知**。
- **Step 3 的总体边界**：3.2/3.3 只到自己的范围；仍未做/未知 = 3.2 资产 fail 真跑、3.1e 全量、
  3.1f 真跑半、3.3f 产物比对、几何一致性、3.4（蒸馏与导出）＝**未执行**。**不得**据本节称"Step 3
  全部通过"。
- **§评审修正 的结构性敞口（记台账不修）**：两套记录词汇并存（`manifest.py` / `record.py`，同事实两种命名）；
  单源扫描闸守"副本"、**不守"新规则"**。见 `PLAN.md` #27。
- **有意的不完整**：三个派生值（`tilt_cos_min` / `clearance_min` / `sustain_steps`）**有意未设为必需字段** ——
  设为必需会让旧的 `eval-record-1` 记录读作"不完整"、无法再被自身重写；兜底是已记录的 `git_rev_lizard`。
- **口径边界**：历史 `[N]` 是当次运行编号而非闸门身份；套件条目数（44 → 46）与离线例数
  （9 → 10）只在**当日 commit** 上成立。
