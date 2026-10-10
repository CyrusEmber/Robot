# ISAAC_ROOT 参数化收尾：执行探针记录（2026-10-10）

## 适用范围

`work/closed/2026/isaac-root-parameterisation.md` 的执行与独立审核记录。对象 = 该事项 `close_when` 的两半：
① 三处参数化调用点在**无 junction 布局**下确实生效；② 摘掉 `E:\IsaacLab\ablation_harness` 之后，
一条 train/eval 命令能起来且日志目录的 glob 落在真实 IsaacLab 树。

本记录只写这两半的现场读数与落点。`paths.yaml` / `RL_ISAAC_ROOT` 的解析口径归 `host_paths.py`
与其闸门，不复述；原探针 spec 已删，补证输入与产物保留，两批的证明边界见末节。

## 验收条件

- (a) `E:\IsaacLab\ablation_harness` 不存在（junction 已摘）。
- (b) 三处调用点读的是同一个来源，且**在无 junction 下**各自给出真实 IsaacLab 树：
  `eval.py` 的 `_ISAAC_ROOT`、`run_ablation.py` 的 `_ISAAC_ROOT`、`_log_dir_for_tag` 的 glob。
- (c) `rl_exp\tools\verify\run_offline_checks.bat` 全绿。
- (d) 一条 train/eval 命令能走完（`sweep done, failures=0`），日志目录落在 `E:\IsaacLab\logs\rsl_rl\`
  下的真实树而不是本仓。
- 判据形状：全绿按套件自己的收尾行判；train/eval 那半按进程真的起了、真的写了产物判，不看声明。

## 结果

### (a) junction 已摘

`dir /AL "E:\IsaacLab" | findstr /I "ablation_harness"` 无输出（无重解析点），
`if exist "E:\IsaacLab\ablation_harness"` → `MISSING`。`HARNESS.md` 部署形态段那句"可 rmdir"已是既成事实。

### (b) 三处调用点（代码面）

| 落点 | 形态 |
|---|---|
| `ablation_harness/eval.py:109-111` | `_find_isaac_root()` 直接委托 `host_paths.isaac_root()` |
| `ablation_harness/eval.py:122` | `_ISAAC_ROOT = _find_isaac_root()` |
| `ablation_harness/run_ablation.py:44` | `_ISAAC_ROOT = host_paths.isaac_root()`（模块级，唯一来源） |
| `ablation_harness/run_ablation.py:47-59` | `_isaac_root()` 在 `None` 时硬停并指名 `paths.yaml` / `RL_ISAAC_ROOT`，不回落父目录 |
| `ablation_harness/run_ablation.py:62-74` | `_log_dir_for_tag` 在 `_isaac_root().glob("logs/rsl_rl/*/*")` 上匹配，不再拿"harness 的父目录" |

### (c) 离线闸

`rl_exp\tools\verify\run_offline_checks.bat` → `ALL_OFFLINE_CHECKS_PASSED (37/37)`
（改动前、改动后各跑一次；两次同一行）。

### (d) 原执行声明：探针一（新训）+ 探针二（复用路径；审核结论见后）

两条探针都从本仓根用 `paths.yaml` 记录的解释器发起，spec 在仓外（一次性，见「未覆盖边界」）。

| 探针 | 形态 | 现场读数 |
|---|---|---|
| 一 | 新训 `max_iterations=2`（`Lizard2-Flat-v3`） | 训练完成，日志目录真落在 `E:\IsaacLab\logs\rsl_rl\lizard2_v3\2026-10-10_11-41-26_isaac_root_probe`；harness 的 glob 打印的就是这个绝对路径 ⇒ **glob 半成立**。随后 `[ABLATION] ERROR: expected model_2.pt not found under <同路径>`（缺陷二，见下） |
| 二 | 复用探针一的 checkpoint（`max_iterations=1`，`model_1.pt` 已在）→ 跳过训练，直接打 eval 半 | 修复后：`[EVAL] protocol=Locomotion-Eval-v3 … run_id=Lizard2-Flat-v3_isaac_root_probe_it1_nominal_seed123` 起并有终局读数，`[EVAL] wrote results/…/{eval.json,record.json}`，`[ABLATION] sweep done, failures=0` ⇒ **eval 半成立** |

### 本次修掉的一处（进本项 landing）

`run_ablation.py:117` 的 eval 子进程原用相对路径 `"ablation_harness/eval.py"`，而 `cwd=_ISAAC_ROOT`
⇒ 只有 `E:\IsaacLab\ablation_harness` junction 在时才成立。摘掉 junction 后实测：

```
cd /d E:\IsaacLab && E:\IsaacLab\env_isaaclab\Scripts\python.exe ablation_harness/eval.py --help
→ python.exe: can't open file 'E:\IsaacLab\ablation_harness\eval.py': [Errno 2] No such file or directory
```

改为 `str(_HARNESS_DIR / "eval.py")`（`_HARNESS_DIR` 是模块级绝对路径）。`eval.py` 自定位
`_HARNESS_DIR`/`_RESULTS_ROOT`（`eval.py:91-92`），命令其它部分不依赖 cwd，故绝对路径是充分修法。
**不加模块、不改测量语义 ⇒ 按 `ablation_harness/HARNESS.md` 的代码基线规则不进编号**。
原记录这一段存在截断残句；本次审核删除无法解释的片段，不据此恢复或推断缺失内容。

### 独立审核（2026-10-10；基线 `6ded61d`）

审核上下文未携带执笔会话历史；从事项的 `close_when`、落点、保留产物与本记录出发。
初始 `git status --short` 无输出。此次只审核并回填，不修改调度器、不新增闸门、不启动训练或 eval。

| 核验 | 独立读数 / 判断 |
|---|---|
| 无 junction 布局 | `Path.exists()` 与 `os.path.lexists()` 对 `E:\IsaacLab\ablation_harness` 均为 `False`；不仅目标缺失，链接本身也不存在 |
| 主机根与日志 glob | `host_paths.isaac_root()`、调度器 `_ISAAC_ROOT` 与从 `eval.py` AST 提取后执行的 `_find_isaac_root()` 均返回 `E:\IsaacLab`；`_log_dir_for_tag("isaac_root_probe")` 命中保留日志目录，属于 IsaacLab 树、不属于本仓。AST 提取只执行根解析函数，不等同于运行 eval |
| 离线套件 | 本次独立执行 `rl_exp\tools\verify\run_offline_checks.bat`，退出码 0；末行 `ALL_OFFLINE_CHECKS_PASSED (37/37 in 52.5s, wave 234s/informational, jobs=6)`。wave 是信息量，不作成本审计结论 |
| eval 启动参数 | 调用真实 `_run_eval`，只替换 `subprocess.run` 为返回码 0 的捕获器：入口是存在的绝对路径 `E:\Robot\ablation_harness\eval.py`，cwd 是 `E:\IsaacLab`。证明 argv/cwd，不证明仿真或产物落盘 |
| 新训完成判定 | 保留目录有 `model_0.pt`、`model_1.pt`、`checkpoints.json`、`run_manifest.json`，没有 `model_2.pt`。调用真实 `_run_train(max_iterations=2)`，只把训练子进程替换成成功返回，仍报 `expected model_2.pt not found` 并返回 `None`；未再次开训 |
| 训练器命名依据 | 本机 `rsl_rl/runners/on_policy_runner.py:77-79,112,127-134`：循环上界不包含 `total_it`，最后保存 `model_{current_learning_iteration}.pt`；从 0 新训 N 次时末文件下标为 N−1。这是本机源码核验，不是猜测 |
| eval 证据可复核性 | 探针二的 `eval.json` / `record.json` 与汇总行已删，spec 也未保留。现存记录中的终局文字不能替代被删产物；那条旧相对路径的失败复现也不能证明修复后的成功 |

#### 越界裁定

接受 `656b142` 的局部修复，但不是因为“只有一行”。缺陷由摘 junction 直接暴露，修改位于原 landing，
只把本仓 eval 入口绑定到本仓绝对路径，保留 IsaacLab cwd，不改 spec、协议、指标或公共 API；用户本次说明
该修复按其选择执行。属于有授权、因果直接、可逆的就地修复，不是架构调整。

`close_when` 的“失败就记下并保持 open”不因此失效：它约束失败后的关闭动作，不意味着修完即可免验收。
失败记录应保留，修复后的成功仍须重新证明；本次不能把“允许修复”偷换为“允许关闭”。

另有落点文档失真：`ablation_harness/HARNESS.md:41-42` 写“子进程入口一律绝对路径 / cwd 不是定位手段”，
但 `_run_train` 仍以 `scripts/reinforcement_learning/rsl_rl/train.py` 相对 IsaacLab cwd 启动。
不存在 junction 依赖不等于不存在 cwd 依赖；补证时应把该句收窄为“eval 入口使用本仓绝对路径，train 入口
相对已解析的 IsaacLab cwd”，不必为了迁就文档改训练命令。


#### 关闭裁定与补证要求

**不通过关闭审核；事项退回 `in_progress`。** 路径委托、无 junction、真实日志 glob 与离线套件已独立核验；
“一条完整 train/eval 命令成立”未被当前可核验证据证明。新训探针失败与复用探针的已删成功产物，不能拼成
一条完整新训链的通过证明。原事项只写“能起来”，本记录 (d) 却写“能走完”，两者强度不同；本次不暗改
`close_when`。即使只按“能起来”，现有捕获器也未真起 eval，已删产物的自述仍不足以核验。

最短补证路径：先在 `work/active/ablation-sweep-final-checkpoint-name.md` 修复并独立验收新训判定，
再以无旧 checkpoint、无旧 eval 结果的独立 tag/group 真跑一条 spec，保留 spec 的复读输入、完整命令、
带时间戳的训练目录与 eval 产物。用独立组隔离探针，不再为了避免污染既有表而删除唯一证据；不把探针分数
解释成策略性能。若只想用复用路径验本项，应明确保留其输入与产物，并说明证明边界。

#### 闸门裁定

**值得独立的“新训分支行为成立”断言；不值得仅为本事故新增一个离线进程。** 来源缺陷就是本记录探针一；
套件全绿却漏掉主功能分支，已是实际失败，不是“以防万一”。默认按 `OFFLINE_CHECKS.md` §4，把最小回归
折进已导入调度器、且不导入 torch/numpy 的 `rl_exp/tools/verify/test_eval_record.py`；同步声明受保护产物为
`ablation_harness/run_ablation.py`。不泛化成“所有无人走路径”框架，不抬条数棘轮。

回归应调用真实 `_sweep` / `_run_train` / `_run_eval`，只隔离仿真子进程与共享目录：

- 全新临时日志与结果目录；训练替身成功返回并按本机已核验的训练器契约只落 `model_{N-1}.pt`，默认
  checkpoint 选择也应走通 train → eval，而非显式指定 checkpoint 绕过默认分支。
- 留一例既有 checkpoint 的复用路径，确认不会意外重训；失败训练或缺末 checkpoint 不得被当成完成。
- 无 harness junction 的两树布局下捕获 eval argv/cwd，入口应指向本仓 eval，日志应取 IsaacLab 树。
- 在旧实现上先红、修复后绿；分别还原完成凭据/default checkpoint 的 off-by-one 与 eval 相对入口，
  确认对应断言确实红。破坏测试读数与成本证据归后续记录，本次**未实施、未准入新闸门**。

一年后的脆弱点是训练器保存契约漂移：替身若永久硬编码 N−1，也会产生虚假安全感。该回归只能证明
调度分支与所模拟契约一致，不能独自证明安装的训练器遵守契约；修复事项仍必须核对实际安装源码并真跑。
真实 GPU 冒烟不进离线套件（§5）。只把 `max_iterations` 文档化为“复用下标”会退掉已声明的新训能力，
不能当修复；除非用户明确选择缩窄功能，本次不推荐这条路。

### 补证（2026-10-10；修复提交 `3420339`）

审核要求的补证已全部执行。判定时以产物与退出行为为准，不以本段文字为准。

| 步骤 | 读数 |
|---|---|
| 修复形态 | 完成凭据改为读目录（`run_ablation.py` 的 `_latest_checkpoint` / `_trained_to_budget`：最新 checkpoint ≥ 预算−1 才算训完）；未指名 `eval_checkpoints` 时默认取该 run 末档。训练器契约按本机 `on_policy_runner.py:77-79,112,127-134` 核验 |
| 单测 | `test_eval_record.py` 32 条全绿（新增 4 条覆盖：新训走通并默认末档 / 已达预算不重训 / 半途或失败不算完成 / eval 绝对入口与 cwd、日志 glob 属 IsaacLab 树） |
| 破坏测试一 | 还原完成凭据到 HEAD 旧实现 ⇒ 红，报错即原缺陷原文 `expected model_2.pt not found`，复用路径也被认出会意外重训 |
| 破坏测试二 | 只把 eval 入口还原成相对路径 ⇒ 红在目标断言 `the eval entry has to be an existing absolute path` |
| 全套件 | `run_offline_checks.bat` → `ALL_OFFLINE_CHECKS_PASSED (37/37 in 48.8s)`；回归折进既有检查，条数不变 |
| 真跑探针 | spec `ablation_harness/specs/isaac_root_reprobe.yaml`（仓内，可复读）：无旧 checkpoint 新训 2 迭代 → `[ABLATION] sweep done, failures=0`；训练目录 `E:\IsaacLab\logs\rsl_rl\lizard2_v3\2026-10-10_14-38-48_isaac_root_reprobe`（机器本地，含 `model_0.pt`/`model_1.pt`/manifest）；eval 产物在仓内 `ablation_harness/results/locomotion_eval_v3/isaac-root-reprobe/Lizard2-Flat-v3_isaac_root_reprobe_it1_nominal_seed123/`（`eval.json` + `record.json`，保留不删）。默认进 eval 的正是 `model_1.pt`（it1） |
| 脏树偏差 | 探针启动时工作树含另一会话在办改动（`check_version_docs.py` 等），manifest 按 `RL_ALLOW_DIRTY_TREE` 记为偏差；探针代码本身已提交于 `3420339`。前两次未声明的启动被脏树闸门硬拒（T0 落盘、未训练），闸门行为符合设计 |
| 分组修正 | 初跑产物落 smoke 组，summarize 因与既有行条件不同报冲突并退出 1（sweep 本体 `failures=0`）。产物移入独立组 `isaac-root-reprobe`，smoke 汇总表还原，`--summarize` 复跑退出 0。教训：探针行与任何既有行条件不同就别共用组，别靠事后删产物 |

探针策略只训 2 迭代，其读数不具性能含义，本记录不复述数值。

### 补证独立审核（2026-10-10；基线 `8935cc4`）

审核从 `close_when`、landing 与保留产物出发，未携带执行会话历史。初始工作树干净；本次未新训、
未重新仿真，只读保留证据、重跑离线套件与复用调度路径。用户授权评审并回填状态；仅裁定本项，
`ablation-sweep-final-checkpoint-name` 仍待其独立审核。

| 核验 | 独立读数 / 判断 |
|---|---|
| 无 junction | `E:\IsaacLab\ablation_harness` 的 `Path.exists()` / `os.path.lexists()` 均为 `False` |
| 三处根与日志 | `host_paths.isaac_root()`、调度器 `_ISAAC_ROOT` 与 AST 提取执行的 eval `_find_isaac_root()` 同为 `E:\IsaacLab`；真实 `_log_dir_for_tag("isaac_root_reprobe")` 命中补证保留目录，属于 IsaacLab 树、不属于本仓。AST 核验不算运行 eval |
| 离线套件 | 独立执行退出 0：`ALL_OFFLINE_CHECKS_PASSED (37/37 in 46.1s, wave 212s/informational, jobs=6)`；其中 `test_eval_record: 32 passed`。关闭落地后复跑退出 0：`ALL_OFFLINE_CHECKS_PASSED (37/37 in 46.2s, wave 216s/informational, jobs=6)`；单独事项形状检查亦为 `WORK_DOCS_OK` |
| 真训与 eval 绑定 | manifest 声明 `resume=false`、`max_iterations=2`，T0/T1 与 `model_0.pt` / `model_1.pt` 保留；`checkpoints.json` 与 eval 的 `checkpoint.resolved` 指向同一末档。重算末档 SHA-256 与索引、`record.checkpoint.sha256`、`sha256_after_load` 一致；`record.read_state` 为 `complete`。实际 eval 产物时间在训练末档写入之后 |
| 安装训练器 | 本机 `env_isaaclab/Lib/site-packages/rsl_rl/runners/on_policy_runner.py:77-79,112,127-134` 仍按 0..N−1 循环并收尾保存末下标；不是仅接受测试替身假设 |
| 修复代码归因 | 训练记录 rev 为 `342033952003`、eval rev 为 `67707c0361e7`；两提交间 `run_ablation.py` / `eval.py` 无差异，修复在训练和评测两半均已存在。rev 不同不据此声明整树相同 |
| 入口破坏测试 | 仅在内存把 `_run_eval` 入口还原为相对路径、保留模块 globals 使仿真替身仍隔离：目标断言红，原文 `the eval entry has to be an existing absolute path, not 'ablation_harness/eval.py'`；恢复真实函数后同一测试绿。未修改生产文件 |
| 复用复读 | 当前 spec 再执行不重训、不重评，打印 `eval exists, skip` 与 `sweep done, failures=0`。只证明断点复用；新训与真实 eval 成立依据是上述保留的训练记录、checkpoint 绑定及 eval 产物，不把这次 skip 当新训成功 |
| manifest 边界 | `manifest --verify` 无 blocking，但退出 2：`RUN_MANIFEST_PARTIAL (2 required claim(s) unknown)`。本仓当时脏树 diff 已不匹配，本机 IsaacLab 有未归档的 untracked code；记录完整和末档校验成立，整树可重建未知，不声称复现能力已验 |

#### 分组与汇总勘误

入口破坏测试的首次内存构造使用了复制的 globals，未随测试的模块 patch 替换 subprocess，导致
尝试启动已不存在的相对 eval 入口，并在 Python 打开文件阶段失败（未起仿真）；随后核对根因，改为
绑定原模块 globals，才得到上表的有效隔离红/绿结果。首次构造失败不算回归断言证据。

补证表里的“移入独立组，summarize 复跑退出 0”不能据此称为新组汇总成立：当前独立目录没有
`summary.csv`，保留 `record.json:1577` 的 `run.group` 仍为 `smoke`。独立执行
`--summarize --group isaac-root-reprobe` 虽退出 0，输出却是 `no results under ...`，没有读取该探针行。
当前仓内 spec 的组与保留记录的实际启动组不同；保留记录不改写，物理迁移不冒充重新生成。

此缺口属证据归档/声明的局部问题，不是路径架构问题。本项不验汇总与同表能力，故不以其阻拦
`close_when`，也不认可“完整 CLI 含汇总已验证”的扩大结论。`HARNESS.md:41-43` 已明确 eval 绝对入口、
train 相对已解析 cwd；末句“不是定位手段”只可理解为 cwd 不用于发现 IsaacLab 根，train 文件定位仍依赖 cwd。

#### 关闭裁定

**本项关闭审核通过。** 严格按原 `close_when` 的“train/eval 能起来、日志 glob 落真实 IsaacLab 树”，
无 junction、独立套件全绿与保留的真实 train → checkpoint → eval 绑定均成立，不再用被删的旧探针
或替身成功替代真实产物。本项移入 `work/closed/2026/`；不代关关联的完成凭据事项。

最大的长期脆弱点是把 tag/文件名当运行身份与训练契约：当前后缀 glob 不校验 task/seed，N−1 回归替身
也不会自动察觉安装训练器的保存契约漂移。本次独立 tag、manifest 与 checkpoint 摘要绑定消除了本次证据
混用，不证明所有未来排程都无此风险；本项不借机重构。整树可重建与探针汇总不在关闭承诺内。

## 证据引用

- 事项：`work/closed/2026/isaac-root-parameterisation.md`。
- 代码：`ablation_harness/run_ablation.py:47-77,149-174`、
  `ablation_harness/eval.py:109-122`、`ablation_harness/host_paths.py:76-97`。
- 文档：`ablation_harness/HARNESS.md:39-43` 的「部署形态」；当前分别声明 eval 本仓绝对入口与
  train 相对已解析 IsaacLab cwd，不将初次“子进程入口一律绝对路径”失真句当当前事实。
- 训练器侧命名：`E:\IsaacLab\env_isaaclab\Lib\site-packages\rsl_rl\runners\on_policy_runner.py:77-79,112,127-134`
  （机器本地，不进仓）。
- 复读命令（都在本仓根跑，除标注外）：
  - 离线闸：`rl_exp\tools\verify\run_offline_checks.bat`
  - junction 已摘：`if exist "E:\IsaacLab\ablation_harness" (echo EXISTS) else (echo MISSING)`
  - 修掉的那处（等价最小复现，任选一个不存在的相对路径即可）：
    `cd /d E:\IsaacLab && E:\IsaacLab\env_isaaclab\Scripts\python.exe ablation_harness/eval.py --help`
- 补证复读输入：`ablation_harness/specs/isaac_root_reprobe.yaml`；完整调用
  `"E:\IsaacLab\env_isaaclab\Scripts\python.exe" ablation_harness\run_ablation.py --spec ablation_harness\specs\isaac_root_reprobe.yaml`。
  当前执行是复用，不重新证明新训；仓内 spec 的组是归档组、不是保留记录实际启动时的 `smoke`。
- 补证训练记录复读：
  `"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -m rl_exp.tools.runrecord.manifest --verify "E:\IsaacLab\logs\rsl_rl\lizard2_v3\2026-10-10_14-38-48_isaac_root_reprobe"`。
- 补证产物：`ablation_harness/results/locomotion_eval_v3/isaac-root-reprobe/Lizard2-Flat-v3_isaac_root_reprobe_it1_nominal_seed123/`
  的 `eval.json` / `record.json` / `terrain/geometry.json`；末档位于上条训练目录的 `model_1.pt`。
- 探针产物：探针一的日志目录留在 `E:\IsaacLab\logs\rsl_rl\lizard2_v3\2026-10-10_11-41-26_isaac_root_probe`
  （机器本地，不进仓）；探针二写在 `results/locomotion_eval_v3/smoke/` 的那一行与目录**已删除**（见下）。

## 未覆盖边界

- 原探针一/二 spec 是仓外一次性输入，旧 eval 产物已删；只保留其失败/退回审核历史，不再承担关闭证明。
  当前补证输入与产物见「证据引用」，不得把原探针与补证混读。
- 补证只覆盖 `Lizard2-Flat-v3` 一条 nominal train/eval，不覆盖其它任务 id、robust 与多 checkpoint 排程。
  本次复读了 summarize，但独立组无 summary，故没有汇总成立证据；`--by-terrain` 未测。
- 补证记录完整、checkpoint 绑定已核验；脏树与未归档源码使整树可重建未知。路径能力成立不等于
  `RUN_MANIFEST_OK` 或策略性能通过。
- 本项不评价 `paths.yaml` 的解析口径（归 `host_paths.py` 与其闸门），也不动 `paths.yaml` 的机器本地事实。
- 完成凭据修复虽已用于本次链路，其独立关闭裁定仍归 `work/active/ablation-sweep-final-checkpoint-name.md`。
