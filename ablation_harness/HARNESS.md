# Ablation Harness——版本与挂账（SSOT）

> 本文件 = 评测台（`ablation_harness/`）版本与待办的唯一真源。
> 评测台是共享测量仪器：服务所有机器人家族（换家族后仍在），**不进任何家族
> 的配方版本管理**（versioning.mdc「范围边界」）。修订纪律沿用 versioning.mdc
> B 节（vN.M.K + 本文件修订记录 + 版本号开头的 commit message），**编号独立
> 于家族配方版本**（冻结 tag：家族叫 `lizard-vN`，这里叫 `harness-vN`）。
> 仓根 `PLAN.md` 挂账 #12 只留指针。

## 当前状态

- 协议版本：**locomotion_eval_v3 当前**（`protocols/locomotion_eval_v3.yaml`，套件 `lizard_suite_v2` —— rough 两列改成真起伏）；`locomotion_eval_v2` 冻结封存（其 rough 两列实为均匀抬升平板，见挂账 #3 收账），老结果留 `results/locomotion_eval_v{1,2}/` 原地（**三版任一不得混表**）
- 代码基线：v1.7.3（**A3 写侧离线化**：`record.run_dir` + `record.baseline_evidence` —— 基线查找与三条 reason 文案从 `eval.py`（模块级 `parse_args()` + 起仿真 ⇒ 离线不可 import）搬进 `record.py`，`eval.py` 留薄壳；此前 v1.7 **eval 记录格式**：`record.py` + `eval.py` 四个采集点，每次 run 落 `record.json`，run 唯一性拒覆盖；v1.6 协议 v2 采样帧；v1.5.2 抽样入库 / v1.5 协议 v2 迁移规则 / v1.4 报告；可视化产物**不入库**）
- 部署形态：仓根独立目录，全部自定位。机器本地事实（IsaacLab 树 + venv 解释器）登记在仓根 `paths.yaml`（模板 `paths.example.yaml`），唯一读者 `host_paths.py`；`E:\IsaacLab\ablation_harness` junction 已废，原机可 `rmdir` 摘链接

## 记录格式（`record_format`，独立于 eval 协议版本）

一次 eval 的**条件**写在 `results/<协议>/[组/]<run_id>/record.json`（`eval.py` 与 `record.py`）：
env cfg 与 agent/wrapper 配置（含 `clip_actions`）、实际命令时间线与解析出的 segment 窗口、
扰动（`t`/`kick_mps`/方向 seed/步数）与指标阈值、**派生阈值**（`metrics.derived`：`tilt_cos_min` /
`clearance_min` / `sustain_steps`，即指标实际用到的值，v1.7.2 起写入、**非必需字段**：v1.7.2 之前的
`eval-record-1` 记录没有它，读作未知而不算缺字段）、`eval_protocol_digest`（协议 yaml 内容+name+version）、
`obs_protocol_digest`（3.1a 声明身份+已审摘要，两者分开命名）、**加载时**哈希的 checkpoint
（`sha256`+`size`+`mtime`，加载后立即复核）、资产（声明锁摘要 vs 实际文件 pass/fail/unknown）、
运行时（实际 `device`/`num_envs` 与声明值分列、rsl_rl/sim 版本、两侧 git rev）。
`gym.make` 后的 `cfg` 装不下这些：命令播放器、robust push、阈值与评估步数都在其后另建。

**版本号独立**：协议语义变化（时间线/阈值/地形/DR/指标/采样帧）才开新 `locomotion_eval_vN`；
纯溯源字段补充**不开新协议**，改这里的版本号（现行 `eval-record-1`）。

**四条读侧规则**（`record.read_state`，合规即通过，违规即红，不做兼容）：

1. 无 `record_format` = **legacy**：缺字段一律读作未知，不回写、不补齐、不推导；
2. 有 `record_format` 但缺该格式必需字段 = **记录不完整**：既不得按 legacy 放行，也不得算通过
   （未知值写 `"unknown"` 字符串，**空槽不算记录**）；
3. 可比／不可比／未知分别有测试，缺证据**不得**自动升级为可比；
4. 记录行为不得改变 rollout、随机数消费或指标计算 —— `record.py` 不 import torch/numpy/random，
   由静态闸看守（`test_eval_record.py` 末例）。

**可比性只看绑定面**（`record.BINDINGS`：checkpoint / suite / assets / eval 协议 / obs 协议身份+摘要）：
任一侧 legacy 或不完整、或某绑定读作 unknown ⇒ **未知**；`differences` 只收录**真差异**（`unproven` 另记"两侧同为 unknown"的绑定，等而无证）。
其余元数据（run_id、时间戳、分组）不参与比较。

**写侧硬门（2026-09-17 评审后收紧）**：绑定齐备处（`_make_policy` 之后）与 `_persist` 各判一次 ——
①记录不完整 ⇒ **拒绝落盘**；②同一 `run_id` 已有**可比**记录 ⇒ 重跑自重写，其余一律拒：记录有真差异、记录为
legacy/不完整、目录**有结果无记录**（pre-format run，仓内 25 个）、记录文件不可读。放行只有 `--variant`（另起身份）
或 `--overwrite`（显式替换）。拒写发生在 rollout **之前**，故错打变体名秒级被拒，不再是两分钟。
`record.json` / `eval.json` / `summary.csv` 一律 tmp+`os.replace` 原子落盘：截断的记录会让下一次 run 崩在解析上，
而不是崩在一个决定上。

## 版本历史

| 版本 | 日期 | 摘要 | 依据 |
|---|---|---|---|
| v0（史前） | 2026-08-28 | 设计定稿（四轮收敛：suite → 双模式 → recovery push → 协议版本化）+ 全链路实现验证（零动作策略双模式冒烟自洽：stop 段 success=1.0、MAE 段≈命令速度、kick 后 fall 检测生效；同 seed 多次运行数值逐位一致）+ 三轮代码审查（b6098c9 / f22f43f：修 2 🚨 glob 前缀 bug / 训练失败杀 sweep + 3 ⚠️ 协议默认单一真源 / recovery 子集 / 死参数，configclass 单例疑点源码排除）——均发生在 09-01 建档前 | 自 eval-harness SKILL.md 状态节并入 |
| v1 | 2026-09-01 | 建档基线：协议 locomotion_eval_v1 冻结（早于本文档，git 考古）+ Phase A 修复（eval 快照 / DR 锁面 / smoke 断言，commit 5725396） | — |
| v1.1 | 2026-09-01 | `eval.py::_prepare_env` 补 `handle_deprecated_rsl_rl_cfg(agent_cfg, rsl-rl 版本)`——train.py 有、harness 无，rsl-rl 5.4.2 的 `MLPModel` 拒收 legacy `stochastic` 字段，带 `--checkpoint` 直接 `TypeError`（v1 之前只跑过零动作冒烟，该路径从未 exercised） | teacher v1 首跑评测 |
| v1.2 | 2026-09-01 | 结果按 **campaign 分组**：`eval.py --group v1` → `results/<protocol>/v1/<run_id>/` + 组内 `summary.csv`（行只落一处，协议根 summary 不再混装）；`run_ablation.py` 透传 spec 的 `group`，`--summarize` 缺省汇总"协议根 + 各组"，`--summarize --group v1` 只看一组。已有 6 行 v1 结果 git mv 入组 | 用户要求 v1 评测单独成目录 |
| v1.3 | 2026-09-01 | 逐地形与可视化：`run_ablation.py --by-terrain [--group v1]` 从 eval.json 反向生成组内 `terrains.csv`（run × terrain 长表，108 行/12 run）+ 三张「地形 × ckpt」pivot；新增 `plot_eval.py`（趋势图 + 逐地形热力图，纯读盘不起仿真）；家族侧新增 `tools\trainlog\plot_tb.py`（tb_scalars.csv → 4 张训练曲线）。teacher v1 补测到 6 ckpt（2k/6k/10k 新增，共 12 行） | 用户要求逐地形数据 + 可视化 |
| v1.4 | 2026-09-02 | 汇总报告 + 可读性：`plot_eval.py --report <版本目录>` 产出**单个自包含 HTML**（内联 SVG，无 JS/CDN、离线可开、放大不糊）——训练曲线（读该目录 `tb_scalars.csv`，竖线 = 已评测 ckpt，自动从 eval.json 推迭代号，免手传 `--mark`）+ 两张评测图 + `summary.csv` 表格 + git rev 溯源（混 rev 自动黄条警告）。训练曲线图构建函数抽入 `plot_tb.figure/series_to_figs` 供两侧共用（防"哪些 tag 回答哪个配方问题"漂移）。PNG 默认 DPI 120→200（840×480→1400×800），可 `--dpi` 覆盖；`--out_dir` 改为可选，与 `--report` 可单用/并用。**可视化产物退出仓库记录**：`plots/` 与 `report.html` 进 `.gitignore`，v1 已提交的 6 张 PNG `git rm --cached`（磁盘文件保留）——记录只有数据（eval.json / summary.csv / terrains.csv / tb_scalars.csv），图和 HTML 是秒级可再生的视图（纯读盘，不起仿真）；要贴图进工单/POPO/PPT 时才用 `--out_dir` 出 PNG | 用户要求训练结果也在 eval 侧汇总、图能放大看，且确认派生产物不必入库 |
| v1.4.1 | 2026-09-02 | 报告新增第 5 张训练曲线 **iteration ↔ 墙上时间**（家族侧 `plot_tb.py`，报告自动带上）：数据不新算——rsl_rl 把 `Train/mean_reward/time` 的 **step 轴写成墙上秒数**，`_derive()` 直接换成小时轴。口径自洽校验：`Σ(Perf/collection_time + learning_time)` = 25.735 h = TB 自记终值，逐位相同。**读出来的事实**：v1 名义算力 ≈ 14000 × 4.5 s（median，p90 4.9 s）≈ 17.5 h，但总耗时 25.7 h —— 差额几乎全在 `it=11438` 一次 **25839 s（7.2 h）** 的单迭代尖峰上（休眠/抢占，非计算），曲线上一道竖直跳变即见。做消融前先按此估时间预算，别拿"迭代等长"当假设 | 用户要求对比 iteration 与耗时 |

## 挂账

| # | 事项 | 优先级 |
|---|---|---|
| 1 | **运行时验收尚未跑**（2026-09-18 起转到 **v3**：v2 已冻结封存 ⇒ ②③ 的对照若还想要，也只能在 v3 下做，且 v2 行不得混表）：① v14 零动作冒烟（核对 `terminal frames captured=` == `resets_in_rollout`，= 0 即 hook 失效；**注意**：`dones` 含 `time_out`，末步全体超时 ⇒ 这两个数天然等于 env 总数，"early_terminations" 才是中途终止数 —— 2026-09-20 实测 `captured=72 == resets_in_rollout=72`、`early_terminations=0`，原先那行把它印成 `early_done_envs=72/72` 会读成"全员中途摔倒"）；② 同一 ckpt 跨协议对照（预期 fall_rate 单调、其余指标在 ±0.02 内）；③ 基线（v13/v10 的 ckpt）在 v3 下重跑，v3 行才有对账对象；④ **新**：v3 的 rough 两列要真看到起伏（`relief_p95` 与 completion 分布），否则等于换了名字没换地形。原 #1（路径参数化）已由 v1.5.1 落地 | 高 |
| 2 | **记录格式的真跑段**（`ARCH_PLAN` Step 3.2d/3.2e 真跑半）——**2026-09-17 已做**：① 同 seed 无记录重复（`A/A`，用 `git show 11f19f4:ablation_harness/eval.py` 在同一棵树上跑 off 臂）与记录臂 `global`/`segments`/`terrains` **逐位相同**；② 一次真实 run 落全六类（3.2f）；③ P04 四项真跑替换（ckpt / suite / 协议 / 资产）与拒绝路径各一次，明细见 `rl_exp/versions/lizard/ACCEPTANCE.md` §3.2。**仍未做**：资产的 **fail** 路径真跑（造 fail 要改冻结资产，越界）、`num_envs` 声明≠实际的格子。**2026-09-18 追加未做**：写侧 `substitutions` 与 `runtime.rsl_rl_id` 仍未真跑核对（口径：`rsl_rl_id` 是 `source:<rev>`/`installed:<ver>`，训练记录 `code.rsl_rl.rev` 是裸 rev ⇒ 须按 `mode` 重建同一身份再比；变体 run 的 `comparison`/`substitutions` 取值；`…suite-roughb016`/`…ckpt1150` 是否落 `unknown` + pre-format reason）—— 见 `PLAN.md` #27 | 中 |
| 3 | **地形随机源的两处实测缺口（2026-09-18 开、2026-09-18 收）**：① **套件里没有真正的粗糙地形列**（`rough_a`/`rough_b` 单值 `noise_range` ⇒ `height_range` 只剩一个元素、`np.random.choice` 退化成常量，实测 p2p 恰为 0.05/0.15 = 均匀抬升平板；`suites.py:18` 的"seed 钉住 RNG 流"机制上不成立）⇒ **已修**：套件升 `lizard_suite_v2`（rough_a `(0.02,0.06)`/`noise_step 0.01`、rough_b `(0.08,0.16)`/`0.02`、`downsampled_scale=0.5`），协议新建 `locomotion_eval_v3`（与 v2 只差 `name`/`version`/`suite`），`eval.py` 默认协议改 v3 且每次运行把几何摘要写进 `eval.json.suite.geometry_digest`；离线反证 `tools/verify/test_terrain_geometry.py`（`relief_p95`：v2 > 0.02 vs v1 == 0.0；同 seed 重复摘要一致、抽掉播种则三次三样）。② **训练侧同一 cfg 两次真跑几何不同**（`stepping_stones`/`random_rough` 抽未播种的全局 numpy 流、`boxes` 抽全局 torch 流）⇒ **已修**：训练入口 `configure_seed(env_cfg.seed)` 提到 `gym.make` 之前（存档 `fork_patches/train_seed_rng.patch`，`framework_pin_check` 逐字节重建看守）。离线预览自证可复现（`terrain_preflight --self-test`）。**仍未做**：① **已完成（2026-09-20）**：起伏改在**真实生成路径**逐格测量并**随运行归档**（`<run_dir>/terrain/geometry.json` = 逐格摘要 + 起伏 + 身份 `suite`/`seed` + 定义），离线闸按该身份重建并逐格比（`tools/verify/test_terrain_geometry.py` 第 5 例）；顶点法只对"最大面 ≤ 脚板格 0.5 m"的网格成立（hfield 面 0.14–0.28 m ✓；楼梯/gap/平面是 13–22 m 巨面 ⇒ 记 `null`，实测过 0.87 m 的假起伏），天花板与升级路径（射线采样）写在 `foot_relief` docstring；归档实测 `rough_a 0.030 / rough_b 0.065`（v1 同位置常值 0.0 作参照）；② **已完成（2026-09-20 真跑）**：同 cfg 同 seed 两跑 `[TERRAIN_GEOMETRY]` 逐位相同（`sha256:b74cb2278a3396aad01ce493b53e8bf9`，200 格、0 异常），换 seed 反证臂摘要不同（`0b163edff4f2a75d4a39a6943c16531c`）⇒ 摘要对几何敏感，"相同"不是摘要迟钝；eval 侧同 seed 两次独立调用摘要亦相同（`sha256:1fc13fa2…`，9 格）。前两跑为干净树；反证臂因另一开发者在改 `ACCEPTANCE.md` 而走 `RL_ALLOW_DIRTY_TREE`（理由已落它的 T0）；③ **⑤b 已接通（2026-09-20）**：真跑路径采集（生成器交出 mesh 那一处）→ 归档（运行目录内 `terrain/geometry.json`，随记录入库；`rebuild.py` 的取材也把它收进材料并逐文件核摘要）→ 再生核验（离线闸按归档自述的 `suite`+`seed` 重建，逐格比摘要，含起伏断言）。**替代说明**：⑤b 原文写"由 `rebuild.py` 核验"，本轮的 `rebuild.py` 负责**材料完整性**，"地形产物一致"由**再生**判定（离线可跑，且更贴原意）；至于重建评级 = #18 ①，仍单独排期 | 低 |

## 升级触发（防"永远不升"）

harness 代码高频变更 / 多机器人共用 / 评测协议 v2 出现时 → 目录化 `versions/harness/vN/`（协议 yaml + NOTES 进版本目录，与家族配方同款冻结纪律）。

**协议 v2 落地时（预立规则，防跨协议对比静默断）**：老跑分留在 `results/locomotion_eval_v1/` 原地不迁移；**跨协议禁止直接对比**（任何表格/图表不得混 v1/v2 行）；新协议新起 campaign 目录，`--report`/`--summarize` 按协议目录天然隔离。

## 与 rl_exp 的契约（单向消费，改动必跑闸门）

- 任务 id：suites 引用 rl_exp 注册的 gym 任务（`import isaaclab_tasks` 触发注册链）
- DR 事件名：`components/dr_controller.py` ↔ rl_exp `play_utils.py` 9 事件清单，`check_dr_parity` 双向看守
- 机器人块：ArticulationCfg parity（family vs teacher）

→ 任何 harness 代码变更后必跑 `rl_exp\tools\verify\run_offline_checks.bat`（闸门红 = 不提交）。

## 修订记录

| 日期 | 版本 | 变更 |
|---|---|---|
| 2026-09-01 | v1 建档 | 版本文档从 lizard v3 计划 §7.5 与仓根 PLAN.md 挂账 #12 剥离至此（用户拍板：仓库不拆、只拆版本文档） |
| 2026-09-01 | v1.1 | agent cfg 迁移修复落地 + teacher v1 六行评测分入 `results/locomotion_eval_v1/`（离线闸门全绿后跑） |
| 2026-09-01 | v1.2 | 分组落盘落地（`--group`），teacher v1 六行迁入 `results/locomotion_eval_v1/v1/` 并独立成表；协议根 summary 只留未分组的零动作冒烟两行 |
| 2026-09-01 | v1.3 | `--by-terrain`（组内 `terrains.csv` + 地形×ckpt pivot）与 `plot_eval.py` 落地；v1 campaign 扩到 12 行（6 ckpt × 双模式），图 6 张入 `versions/lizard/v1/plots/` |
| 2026-09-02 | v1.4 | `plot_eval.py --report` 单文件 HTML 汇总报告落地（训练曲线 + 评测图 + summary 表 + rev 溯源），首份产物 `versions/lizard/v1/report.html`（12 run / 6 图 / 1.1 MB）；PNG 默认 DPI 提到 200；`plots/` 与 `report.html` 加入 `.gitignore`，v1 六张 PNG 移出索引（磁盘保留，可再生） |
| 2026-09-02 | v1.4.1 | 训练侧第 5 图：iteration ↔ 墙上时间（`Train/wall_time_h`，从 `/time` tag 的 step 轴派生）；报告升到 7 图，v1 = 25.735 h / 14k 迭代，其中 it=11438 单次停顿 7.2 h |
| 2026-09-02 | v1.4.2 | eval-harness SKILL.md 瘦身（记录性合入）：状态节史实并入本档（新增 v0 史前行）；指标表去协议数值（协议 yaml 为唯一真源）；可视化注释压缩——skill 只留方法与契约 |
| 2026-09-03 | v1.5 | 预立协议 v2 迁移规则：老跑分不迁移、跨协议禁止直接对比、新协议新起 campaign 目录 | 用户拍板：2026-09-03（规范整改临时 plan #8） |
| 2026-09-07 | v1.5.1 | **主机路径参数化（挂账 #1 收账）**：新增仓根 `paths.yaml`（模板 `paths.example.yaml`，机器本地不入库）+ `host_paths.py`（纯 stdlib、不 import `rl_exp`、**无 PATH 兜底**，宁缺不猜）。六处改问同一解析器：`eval.py` IsaacLab 根、`run_ablation.py` 的 `_ISAAC_ROOT`（连带 `_log_dir_for_tag` 的 `logs/rsl_rl` glob 与 train/eval 的 cwd；找不到直接 SystemExit，`--summarize`/`--by-terrain` 不依赖故仍可裸跑）、`--python` 缺省、`run_offline_checks.bat` 引导、`hooks\pre-commit` 的 `PY`、`framework_pin_check.detect_root`。**provenance 同批修**：lizard 根改问 `git rev-parse --show-toplevel`，IsaacLab 根改问登记路径——旧代码把"调用路径的爹"当配置，junction 布局一死就把自己仓的 rev 记成 IsaacLab 的（表现为 `git_rev_lizard=unknown` + `git_rev_isaaclab` 串位），v5 campaign 各行已按新逻辑重跑纠正 | 用户："不同环境会找不到，要注册 isaac lab 与 env 的位置"；v5 评测实测踩到 rev 串位与 `_ISAAC_ROOT` 落错树 |
| 2026-09-11 | v1.5.2 | 入库 CSV 瘦身：`dump_tb.py` 加 `--max_points`（按 tag 自适应抽样、保首尾——首尾必须留，`plot_tb` 标的就是末值；同长 tag 抽样后仍同长，否则墙上时间图静默消失）与 `--csv_in`（重抽样不需 tensorboard、不需 tfevents）；已训三版 `tb_scalars.csv` 20-22 MB → 210-227 KB，全量转 `tb_scalars.full.csv` 留机器本地（`.gitignore`），入库记录由全量抽样得到、可复现；`test_dump_tb_sampling.py` 入离线闸门 | 用户质疑"代码可生成的东西不该入库"——记录链的源头（tfevents）在 IsaacLab 树、机器本地且会被清理，故记录必须入库，缩的是存什么 |
| 2026-09-15 | v1.6 | **协议 v2 落地（采样帧）**：`protocols/locomotion_eval_v2.yaml`（时间线/阈值/suite/DR 全抄 v1，唯一变更 = 帧定义）。`eval.py` 采样点从 `step()` 之前（obs 帧）移到之后（reward 帧），并 hook `mbenv._reset_idx` 在 auto-reset 覆盖数据前抓下**终止帧**——`step()` 内 `scene.update()` 与 `_reset_idx()` 之间是唯一可读窗口，IsaacLab 无公开回调（`record_pre_reset` 是 HDF5 形状），hook 失效由每次运行的 `terminal frames captured=N` 暴露。副产物：`end_pos` 改用终止帧（H1 的 pre-step 近似作废）。回归闸 `rl_exp/tools/verify/test_eval_frame_v2.py`（v1 截断读作 no-fall / v2 满窗读作 fall）入离线套件第 [20] 步。**已知代价**：帧右移一个 `step_dt`（20 ms），全指标有微小漂移 ⇒ 与 v1 行不可比 | 代码审查 #3：v1 丢掉终止帧，门闸 dwell 恰好满 25 帧收局的 episode 只能看到 24 帧 → fall 漏记 |
| 2026-09-17 | v1.7 | **eval 记录格式（`ARCH_PLAN` Step 3.2a/3.2b/3.2c 离线半）**：新增 `record.py`（纯 stdlib：格式定义、三态读侧、绑定面比较、覆盖拒绝判定、checkpoint 文件摘要）+ `eval.py` 四个采集点与 `record.json` 落盘；新参数 `--variant`（替换项另起 run 身份）/`--overwrite`（显式覆盖）。闸门 `rl_exp/tools/verify/test_eval_record.py`（9 例：0c 四规则三态 / 同 run_id 拒覆盖 / P04 四替换 / 记录模块不碰 RNG 与框架）入离线套件第 [44] 步（0.2s，wave 178s）。规则节见上「记录格式」 | `ARCH_PLAN` v0.21 Step 3 施工件表；用户 2026-09-17 拍板"3.2/3.3 全开工，连真跑段" |
| 2026-09-17 | v1.7.1 | **记录的真跑段**：`clip_actions=None`（无裁剪是事实，不是空槽）归一为 `"none"` 写入记录；真跑证据入 `rl_exp/versions/lizard/ACCEPTANCE.md` §3.2（off/on 逐位相同、A/A 逐位相同、P04 四项替换与拒绝路径、`assets=pass/unknown` 与 `policy.kind=zero_action` 两种状态实落）。新增真跑驱动 `rl_exp/tools/verify/terrain_split_env_run.py`（不进套件，起点仿真）配合 3.3c/3.3d | 记录写侧首次真跑即暴露 `clip_actions=None` 被读作"缺字段"，说明"空槽 vs 事实"必须在写侧归一 |
| 2026-09-17 | v1.7.2 | **评审六修**：①"有结果无记录"的历史 run 目录按 legacy 拒写（仓内 25/31 属此列，此前会被当空 run_id 静默覆盖）＋`record.legacy_run()`；②`compare` 拆 `differences`/`unproven`，"两侧同 unknown"不再算差异，dev 线自跑可自重写、跨线仍拒；③派生阈值（`tilt_cos_min`/`clearance_min`/`sustain_steps`）改为 `main` 算一次传入并写入 `metrics.derived`（`_analyze` 不再自算）；④拒写前置到绑定齐备处（实测 15s，此前约 2 分钟）；⑤三处落盘改 tmp+`os.replace`，不可读记录 ⇒ 拒写（`--overwrite` 可替换）；⑥探针记录表加 8 条上限 + `probe.release()`。逐条证据见 `ACCEPTANCE.md` §评审修正 |
| 2026-09-20 | v1.7.5 | **地形产物一致（挂账 #3 ① / ⑤b 收账）**：`rl_exp/tasks/terrain_geometry.py` 成为几何测量的唯一家 —— `stats`/`foot_relief`（自 `terrain_preflight.py` 搬入；`foot_relief` 对"最大面 > 脚板格 0.5 m"的网格返回 `None`，因为顶点法在那里量的是大面角点跨度：实测楼梯列 264 顶点跨 16 m，0.5 m 格报出 0.87 m 假起伏，而 hfield 面 0.14–0.28 m ⇒ 顶点即表面、精确）+ `evidence`（归档形态：定义 + `suite`/`seed` 身份 + 逐格摘要/起伏）。`terrain_split_probe` 逐格记 `relief`，`[TERRAIN_GEOMETRY]` 行加 `relief_max=…@<列> relief_unmeasurable=N`；`eval.py` 每次运行写 `<run_dir>/terrain/geometry.json`（摘要不因起伏改变 ⇒ 与既有记录可比）；`terrain_preflight` 表对不可测列印 `n/a` 而非数字；`rebuild.py` 取材把该文件收进材料 ⇒ `--check` 重算其摘要。离线闸新增第 5 例：读归档 → 按它自述的身份重建 → 逐格比摘要 + 断起伏（`rough_a > 0.02`、`rough_b > rough_a`、楼梯与平面必须 `None`）。实测同批：v3 零动作 smoke 归档 `rough_a 0.030 / rough_b 0.065`，楼梯/gap/平面 `null` | 挂账 #3 收账；⑤b 原文的"`rebuild.py` 核验"改由**再生**判定（材料完整性仍归 `rebuild.py`） | 评审⑤：真跑证据必须来自真实生成路径并归档，且"测不了"不许冒充数字 |
| 2026-09-18 | v1.7.4 | **地形可复现（挂账 #3 离线半收账）**：新增 `rl_exp/tasks/terrain_geometry.py`（`seed_rngs` = numpy **与 torch** 全局流播种；`geometry_digest(mesh, origin)` = 逐 mesh 顶点/面按固定 dtype 字节序 + origin，支持单 mesh 或序列）—— 视图与真跑两处共用一份实现（`terrain_preflight.py` 的本地副本删除）。**评测侧**：`suites.py` 升 `lizard_suite_v2`（rough_a/b 由"均匀抬升平板"改成真起伏：`noise_range (0.02,0.06)/(0.08,0.16)` + `noise_step 0.01/0.02` + `downsampled_scale 0.5`），新协议 `protocols/locomotion_eval_v3.yaml`（与 v2 只差 `name`/`version`/`suite`，由测试断言看守），`eval.py` 默认协议 v3、`gym.make` 前 `seed_rngs(suites.SUITE_SEED)`、记录里落 `suite.geometry_digest`。**训练侧**：入口 `configure_seed(env_cfg.seed)` 提到 `gym.make` 之前（存档 `fork_patches/train_seed_rng.patch`）。离线闸新增两条（`terrain_preflight --self-test` + `test_terrain_geometry.py` 四例），`MAX_CHECKS` 44 → 45 | 挂账 #3（2026-09-18 评审：真实几何只能在生成器交出 mesh 处采、历史 run 不得事后补认） | 评审⑤：⑤a 离线回归 vs ⑤b 真跑证据必须分开；反证必须能"抽掉播种即红" |
| 2026-09-18 | v1.7.3 | **A3 写侧离线化**：`eval.py` 的 `_baseline_evidence` 连布局规则（`_run_dir`）搬进 `record.py`（`record.run_dir` + `record.baseline_evidence`，`args_cli` 变显式参数），`eval.py` 只留薄壳 —— 该模块 import 期即 `parse_args()` + 起仿真，三段 reason 文案此前**离线不可达**（`PLAN.md` #27 ③ 挂账）。`test_eval_record.py` 18 → **22 例**：三条异常路径（pre-format 邻居 / 完全不存在 / 坏 JSON —— 后者只钉业务前缀 `… is unreadable (`，不锁解析器原文）+ **一条成功路径**（同 protocol 同 group 的邻居真被读到）。**反证**：把 `run_dir` 的 group 去掉 ⇒ 成功例红且报 `nothing at <path>`，即"路径拼错 ⇒ 永远 unknown"确实能被抓住（仅靠三条异常路径抓不到）。已记录值零变化（`baseline.path` 仍是同一绝对路径） | `PLAN.md` #27 ③ 挂账 + 2026-09-18 评审修正 | 评审：`record.json` 缺失被当空 run_id、unknown==unknown 判成差异、记录的是声明而非实际派生值、拒写在 rollout 之后、无原子写、探针表无界 |
