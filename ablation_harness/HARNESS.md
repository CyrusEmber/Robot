# Ablation Harness——版本与挂账（SSOT）

> 本文件 = 评测台（`ablation_harness/`）版本与待办的唯一真源。
> 评测台是共享测量仪器：服务所有机器人家族（换家族后仍在），**不进任何家族
> 的配方版本管理**（versioning.mdc「范围边界」）。修订纪律沿用 versioning.mdc
> B 节（vN.M.K + 本文件修订记录 + 版本号开头的 commit message），**编号独立
> 于家族配方版本**（冻结 tag：家族叫 `lizard-vN`，这里叫 `harness-vN`）。
> 仓根 `PLAN.md` 挂账 #12 只留指针。

## 当前状态

- 协议版本：**locomotion_eval_v1**（`protocols/locomotion_eval_v1.yaml` 冻结；`results/` 按协议目录组织）
- 代码基线：v1.4.1（v1.4 报告 + 训练侧新增 iteration↔墙上时间曲线；可视化产物**不入库**，PNG 默认 200 DPI）
- 部署形态：仓根独立目录 + `E:\IsaacLab\ablation_harness` junction（挂账 1 完成后删）

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
| 1 | G3 剩余：`eval.py:69-77`（"故意不 resolve" junction hack）/ `run_ablation.py:36` / `_log_dir_for_tag` glob 改读 `RL_ISAAC_ROOT`（缺省向上探测 `source/isaaclab` + `logs`）→ 删 `E:\IsaacLab\ablation_harness` junction，评测台完全脱离 IsaacLab 树 | 🟡 闸门依赖已解，纯收尾 |

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
