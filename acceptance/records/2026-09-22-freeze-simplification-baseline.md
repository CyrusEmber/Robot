# 冻结约束简化·第一步基线（2026-09-22）

## 适用范围

- 对象：`rl_exp/versions/**`（正式版本目录、开发配方目录、`lines.json`/`recipes.json`/两份 lock）与
  `ablation_harness/protocols/**`（评测协议）两类冻结对象的**承诺边界**；外加一条真实评测记录的**复读闭包**。
- 只在**读**的层面取证：本次不改任何规则、不改任何闸门、不重钉任何摘要。
- **不覆盖**：训练侧 `runrecord` 的 manifest（T0/T1/T2）复读；`rl_exp/versions/lizard2` 今天新冻结的协议对维护成本的影响；历史 goldens 的字节。

## 验收条件

1. 三类对象（正式版本 / 开发配方 / 评测协议）各给出"承诺项 × 强制闸门（file:line）"，并**点名**承诺之外的空白。
2. 列出所有**不匹配 `v[0-9]*`** 的版本目录，逐个说明"被哪条闸门读到、被哪条忽略"。
3. 从一条真实 `record.json` 出发，逐环给出解析目标与可解析性，并用可执行命令验证最可疑的一环。
4. 两个操作各产出**一个可复现计数器**：改一个验收阈值、新增一条配方线，各要人工动几处、哪些可派生。

## 结果

### 一、承诺矩阵（第二步要按它决定豁免名单）

| 对象 | 承诺项 | 闸门 |
|---|---|---|
| 正式版本目录 `versions/<fam>/<line>/vN/` | 必备 **5 件**：`<line>_params.yaml`、`PLAN.md`、`NOTES.md`、`asset_lock.json`、`base.json` | `check_version_docs.py:216-226`、`:261-265`；params 唯一由 `recipe_lines.py:110-129` |
| 同上 · 条件件 | `diff.json`（仅 `EXPECTED_DIFFS` 命中的 recipe） | 读 `check_recipe_build.py:249-265`；钉 `:90-125` |
| 同上 · 记录行 | `FAMILY.md` 表行 + `FILEMAP.md` 目录行 | `check_version_docs.py:238-246` |
| 同上 · 资产 | `asset_lock.json` 摘要 == 磁盘 urdf/usda/meshes/本版 yaml | `check_dr_parity.py:363-395`、`:440-457`（只覆盖 `discover()` 认到的 vN） |
| 同上 · golden 字节 | 4 份：`cfg_baselines.json` + main/parkour/baseline 的 `cfg_lock.json` | `check_golden_frozen.py:70-88`、`:110-129` |
| 同上 · tag | `lizard-<rel>` 形式 | `check_version_docs.py:249-260` —— **只 WARN**：`no git tag (...) -- fine for proposals; must exist once training starts`（`:257-260`，`:353-361` 仍判 OK） |
| `lines.json` / `recipes.json` | 线生命周期（二态 + retired 需日期理由）／task→recipe 身份（4 个必需键） | `check_recipe_registry.py:116-122`、`:58-94`；`check_recipe_map.py:116-167` |
| 评测协议 `protocols/*.json|*.yaml`（共 8 份） | 版本号 + 文件摘要 + judge 身份 + `criteria` 块；v4 起还要套件指纹 | 摘要进记录（`record.py:132-144`）；身份：v1–v3 → legacy 白名单（`baseline_metrics.py:83,544-550`）、v4 → `baseline-criteria-1`、`lizard2_flat_v1` → `baseline-criteria-banded-1`（`baseline_metrics.py:69,75`）、loco 四份 → `loco-metrics-1+loco-derivation-1`（`loco_judge.py:28,34`）；套件锁从 v4 起强制（`suite_lock.py:41,105-139`，强制点 `eval.py:793-794`、`:843-859`） |

**空白（无看守）**：版本目录里的 `model_*.pt`、`plots/`、`report.html`、`tb_scalars*.csv`、`DIAGNOSE.md`；tag 缺失；`PLAN.md`/`NOTES.md` 的**内容**（只查存在，无摘要）；`judge_semantics.json:5` 与 `baseline_flat_v4.json:21` 都点名 `rl_exp/tools/verify/check_judge_semantics.py`，**该文件不存在**，真实消费者是 `test_baseline_contract.py:586,962`。

### 二、枚举外目录：3 个，全部在 `rl_exp/versions/lizard/main/` 下

`rough-v0/`、`curriculum-flat-v0/`、`curriculum-rough-v0/`

- **读到它们**：`check_recipe_build.py` 按 `recipe.LINES` 遍历（`:550-551`），三个 delta 计数已钉在 `:114-116`（6 / 11 / 16）；`base_of:330-332` 读 `base.json`、`declared_diff:259-261` 读 `diff.json`；其 task 的 **cfg 内容**经 `params_line` 路由参与 golden 比对（`check_cfg_lock.py:151-173`）。
- **忽略它们**：`recipe_lines.discover()` 只认 `v\d+`（`recipe_lines.py:47,80-81,168-181`）；`check_version_docs.py:210`（`rglob("v[0-9]*")`）；`check_dr_parity.py:311-313,440-457`（只走 `line.versions`）；`check_golden_frozen.py:70-88`（FROZEN 只 4 条）；`lines.json`/`check_recipe_registry.py`（只按 discover 的 line）。

⇒ 三个目录**无** PLAN/NOTES/asset_lock/base 名单要求、**无** tag 要求、**无**资产锁、**无** FROZEN 摘要；其**配置内容**受 golden 看守，其**目录形态**不受任何闸门看守。

### 三、复读闭包（记录 `locomotion_eval_v4/Lizard-Rough-v14_v4unlock_nominal_seed123/record.json`）

可解析（10/13）：协议名与版本（`2855-2856` → `protocols/locomotion_eval_v4.yaml:18-19`）；judge 复合 id（`2840`）→ `judge_semantics.json:207` 冻结块 + `loco_judge.py:68-75`；kernels 8 个函数名 → `metrics.py:27-37`；obs 身份与摘要（`2860-2861`）→ `rl_exp/versions/obs_protocol_anchors.json:53-54`（逐字相符）；资产锁路径（`2866`）；套件名字、指纹与逐格几何证据（`2783-2837`、`terrain/geometry.json:14`）。

**断链 2 处、半链 1 处**：

1. **主断链（本轮实测）**：记录 `runtime.git_rev_lizard = aa86af408e1e`，该 rev **在仓**（`git cat-file -t` → `commit`），但**它的树里没有判据实现**——`git ls-tree --name-only aa86af408e1e ablation_harness/` 只给出 `baseline_metrics.py`、`metrics.py`、`protocols`、`record.py`、`suites.py`，而 `loco_judge.py`、`judge_semantics.json`、`suite_lock.py` **现在**才在入库状态（`git ls-files`）。即该记录由**脏工作树**产出：它能复读出协议与 obs 锚，**不能**从自带的 rev 复读出当时生效的判据实现与语义冻结表。
2. judge 冻结块记的是 **v3** 协议（`judge_semantics.json:211`），而记录跑的是 **v4**（`2855`）。
3. `eval_protocol.digest`（`2857`）与 `assets.declared_digest`（`2865`）在仓内**无第二副本**（grep 只命中记录自身）⇒ "校验"等于跑代码重算，不存在可查的冻结副本；`git_rev_isaaclab` 属另一仓，本仓无法解析。

**旧记录分档**：v3 及更早的 `record.json` **没有 `judge` 块**（`judge.id` 只在 `record.py:143` 的 CONDITIONS 里作跨行比较，不在 `ALWAYS`）⇒ 只能靠协议名+版本推 LEGACY 身份（`baseline_metrics.py:544-550`）；`baseline_flat_v1/v2/v3` 产物只有 `eval.json`、无 `record.json`，走 `record.py:235-241` 的 legacy 档。

### 四、两个计数器（第 5 步要拿它们对比）

**A · 改一个验收阈值**（例：`protocols/baseline_flat_v4.json:30` 的 `criteria.tracking.params.threshold: 0.2`）

- **必须手改：1 处**（协议正文）。
- 同值复述 **2 处**，不改则陈述失真：`baseline_flat_v4.json:21`（`why_v4` 写"数值与 v3 逐字相同"）、`HARNESS.md:20-21`。
- 旧版正文 1 处（`baseline_flat_v3.json:28` 的 legacy 键 `forward_mae_norm_lt: 0.2`）：仅当维持"v4≡v3 数值相同"这条政策时才跟着改。
- **不动**：`CRITERION_KINDS` 只钉参数名不钉值（`baseline_metrics.py:88-108`）；`judge_semantics.json` 的 `kinds_sha256`/`frozen_sha256` 只覆盖 kind 表 + cases，**不含协议数值** ⇒ 改阈值不触发任何红、不换 kind、不换 judge id；测试自设自己的值（`test_baseline_contract.py:629-630`）。

**B · 新增一条配方线**（新 line 或新版本）

- **必须手写**：`rl_exp/tasks/recipe.py` 的 `LINES`/`ELEMENTS`；`versions/lines.json`；`versions/recipes.json`（recipes + tasks 两处）；`rl_exp/tasks/__init__.py` 的 `gym.register`；agent cfg；开发态与冻结态两份 `<line>_params.yaml`；`PLAN.md`/`NOTES.md`；`FAMILY.md` 任务表与版本史；`FILEMAP.md` 两行；计数钉 3 张表 —— `EXPECTED_COMPARED`（3 条线）、`EXPECTED_PENDING`（3 条线）、`EXPECTED_DIFFS`（**17** 条，`check_recipe_build.py:68-125`，实测直读）；`check_golden_frozen.py:70` 的 `FROZEN`（4 条）；`versions/freeze_parity.json`；obs 锚点人工审。
- **可生成**：`base.json`/`diff.json`/`asset_lock.json`；`cfg_lock.json` 与 `cfg_baselines.json`（`check_cfg_lock.py --update --line <line> --reason "<why>"`，`:670-679`）；obs 声明草稿（`obs_protocol_inventory.py --out`）；`declare_family.py` 只**打印** FAMILY/FILEMAP 那两行，不代写（`:24-25,558-563`）。

## 证据引用

命令与原始输出（本仓根执行）：

```
$ git cat-file -t aa86af408e1e
commit

$ git ls-tree --name-only aa86af408e1e ablation_harness/ | findstr /i "judge metrics protocol suite record"
ablation_harness/baseline_metrics.py
ablation_harness/metrics.py
ablation_harness/protocols
ablation_harness/record.py
ablation_harness/suites.py

$ git ls-files ablation_harness/ | findstr /i "judge suite_lock"
ablation_harness/judge_semantics.json
ablation_harness/loco_judge.py
ablation_harness/suite_lock.py

$ python -c "... 扫描全仓 .json/.py/.md 中含 'threshold' 且含 '0.2' 的行 ..."
ablation_harness/protocols/baseline_flat_v4.json 30  "params": {"threshold": 0.2, "normalized": true}
ablation_harness/protocols/lizard2_flat_v1.json 33  "threshold": 0.25,   （独立值，不动）
rl_exp/tools/verify/test_baseline_contract.py 629  protocol["criteria"]["tracking"]["params"] = {"threshold": 0.25, ...}
rl_exp/tools/verify/test_baseline_contract.py 1051 {"tracking": {"kind": "tracking_v9", "params": {"threshold": 0.2, ...}}}
（其余命中为无关事实：v_pr_threshold / speed_threshold / pos_threshold、cfg_lock 的 golden 副本、历史 PLAN 记录）
```

该扫描的已知局限：只匹配**键名含 threshold** 的写法，故 legacy 键 `forward_mae_norm_lt`（`baseline_flat_v3.json:28`）不在命中里，需另查。

表条目数（**直读**，非脚本）：`check_recipe_build.py:68-125`（`EXPECTED_COMPARED` 3 / `EXPECTED_PENDING` 3 / `EXPECTED_DIFFS` 17）、`check_golden_frozen.py:70-88`（`FROZEN` 4）。试图用 `ast` 一行脚本计数**失败**（`TypeError: 'list' object is not callable`，lambda 名冲突），故计数来自逐行直读。

记录字段行号：`ablation_harness/results/locomotion_eval_v4/Lizard-Rough-v14_v4unlock_nominal_seed123/record.json`（`2783-2898` 区间）。

## 未覆盖边界

- 未跑全量离线套件；本次只跑 `check_work_docs.py`（`WORK_DOCS_OK`）。
- **"改阈值不会红"是推断**（依据：判据摘要只覆盖 kind 表与 cases），**未实际改一次阈值验证**。
- `FROZEN`/`EXPECTED_*` 条目数由直读得出，缺少脚本化复现；三个枚举外目录的**资产锁**与 **tag** 未逐项核。
- 未纳入训练侧 manifest（T0/T1/T2）的复读；未测今天新冻结的 `lizard2_flat_v1` 对计数器的影响（它已带 `suite_expected`）。
- 第二条主断链的**成因**（`aa86af408e1e` 那次 run 为何在脏树上跑）未查；记录未写"工作树是否干净"这一字段，属记录格式的缺口，不在本次取证范围。
