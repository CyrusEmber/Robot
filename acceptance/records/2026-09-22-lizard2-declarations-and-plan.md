# 2026-09-22 lizard2 的两处声明、diff 论证与 v1 方案

## 适用范围

- 声明/契约：`versions/obs_protocols.json`（新增 `Lizard2-Flat-v1`、`Lizard2-Flat-Play-v1`）、
  `versions/obs_protocol_anchors.json`（宽度改为**按资产键**，新增 lizard2 的 102）、
  `versions/joint_order_runtime.json`（从 `versions/lizard/` 移出，按资产键的注册件归位）、
  `rl_exp/tasks/obs_protocol.py`、`rl_exp/tools/verify/check_obs_protocol.py`、
  `rl_exp/tools/verify/test_obs_protocol_gate.py`、`rl_exp/tools/runrecord/manifest.py`、
  `rl_exp/tools/pipeline/export_ue.py`。
- 计数钉：`rl_exp/tools/verify/check_recipe_build.py` 的 `EXPECTED_COMPARED` / `EXPECTED_PENDING` /
  `EXPECTED_DIFFS` 加 `lizard2/main`。
- 论证：`versions/lizard2/main/v1/diff.json`（9 条 env 理由 + 43 条 agent 理由）、
  `rl_exp/tools/pipeline/emit_diff_declaration.py`（再生成时保留已写理由）。
- 方案：`versions/lizard2/main/v1/PLAN.md`（写满）、`NOTES.md`（未开训的骨架 + 离线事实引用）。
- 不覆盖：训练、启动探针改造（PLAN 硬前置 2，仍在办）、tag、旧家族任何锁/资产。

## 验收条件

1. 套件两级红（`EXPECTED_DIFFS` 未钉、obs 声明缺两个 task id）必须消失，且**总数不涨**：
   新断言只能折进已有闸的 `--self-test`。
2. obs 宽度必须是**实测**并留下可追的引用，而不是把 90 抄给 102 或把 102 手填成"已批准"。
3. 每条已声明 task 的资产必须有**实测并钉死**的装配关节序（否则 checkpoint 无法溯源）。
4. `diff.json` 的 9+43 条理由必须是人写的论证、不许留 TODO，且再生成（`--out` 覆盖）**不能删掉**它。
5. `PLAN.md` 必须有可执行的验收口径与判废线（固定窗口、失败后如何处理），不留 TODO。

## 结果

| 项 | 实测 |
|---|---|
| 硬 A 计数钉 | `EXPECTED_DIFFS[("lizard2/main","v1")] = 107`（64 env 路径 + 43 agent 叶子，闸门两半都数）；`EXPECTED_COMPARED = 2`；`EXPECTED_PENDING = ()` ⇒ `RECIPE_BUILD_OK (38 task(s) … 467 declared difference(s))` |
| obs 声明 | 声明由 `obs_protocol_inventory.py --out` 生成后按任务表合并（**不手抄**）：11 协议 / 40 任务 / 40 条 golden 比对，两个 lizard2 任务落在既有布局 `a25a8c39001b`（内容摘要即键） |
| 宽度（本轮的模型修正） | 协议键是**布局**，不含宽度；旧结构把"已批准宽度"挂在协议上 ⇒ 30 关节的 102 会被拿去和 26 关节的 90 比。改为 `dims = {assets/<family>/<family>.usda: {group: width}}`（与 `joint_order_runtime.json` 同一"事实属于资产"的理由），`dims_digest` 覆盖两层，闸门新增"该资产的宽度是这条协议上真的会被读取的资产"与"键必须是资产路径"两个反例 |
| 宽度实测 | `obs_protocol_live.py --viz none --tasks Lizard2-Flat-v1 Lizard2-Flat-Play-v1 --pin --reason …` ⇒ `PINNED assets/lizard2/lizard2.usda: 30 joints`；两条任务 `policy=102`、`bodies=31`；批准入档（引用这次运行） |
| 装配序覆盖 | `obs_protocol_live.py --all-tasks` ⇒ `OBS_PROTOCOL_LIVE_OK (40 declared task(s), all pinned; no env built)` |
| 变体（PLAY）与协议 | 两个 lizard2 任务与 baseline 的 flat 任务同协议、**不同宽度**：这正是本轮改模型的原因，改后可同时记录并各自被核对 |
| diff 理由 | 9 条 env（每条按该 element 自己的 docstring 与 yaml 值写成，且写明"与框架 stock 比"）+ 43 条 agent（两条本版自有：`experiment_name`/`max_iterations`；其余 41 条逐字继承 `LizardBaselinePPORunnerCfg`，并写明该继承的后果）；`TODO` 残留 0；`--out` 覆盖再生成后理由逐条保留（实测 preserved: True/True） |
| 方案 | `PLAN.md`：硬前置 5 条（协议冻结 / 探针复测 / 落地目视 / **执行器能力曲线** / **自碰撞检查**）、固定窗口口径、主轴 7 条（判据**点名 `CRITERION_KINDS` 种类 + 参数**：`sustained_tilt_v1` / `survival_v1` / `non_foot_carrier_v1` 现成，`tracking_banded_v1` / `displacement_banded_v1` / `non_foot_load_sum_v1` / `gait_swing_v1` 待新增）、零命令与聚合口径、诊断项列表、启动命令、8 条预注册风险与 4 条判废线；`NOTES.md` 记"未开训"+离线事实 |
| 套件 | `ALL_OFFLINE_CHECKS_PASSED (47/47)`；新增的反证折进 `check_dr_parity.py --self-test`（条数棘轮未被抬高），条目同时带上 `freeze_parity.json` 与 `declare_family.py` 两个契约 |
| 评审 #1：缺宽度静态放行（复现的两例） | 修前：`dims` 整个删掉、或把某资产的值设成 `{}` 并更新摘要，都返回 `[]`（前者因为规则只在 `dims` 是字典时执行，后者因为 `if body and missing` 放过空表）。修后两例都红：`no approved widths at all, but declared task(s) load [... 'assets/lizard2/lizard2.usda']` 与 `dims['assets/lizard2/lizard2.usda'] has no width for ['policy'] -- an empty or partial table is not an approval`；反例 `dims/whole-map-absent`、`dims/empty-asset-table` |
| 评审 #2：解析失败被跳过 | 解析改为**共用运行侧读取器**（`check_obs_protocol` 以 `importlib.util.spec_from_file_location` 直接加载 `rl_exp/tasks/obs_protocol.py`，不经包 `__init__`，离线闸门仍不需要 gymnasium/isaaclab），调用新公开的 `usd_path_for_route(line, version)`；**解析不出来的已声明任务报红**（反例 `dims/unresolvable-task-refused`）。旧正则 `^\s*usd_path:...` 会漏 `usd_path: … # 注释` |
| 评审 #3：姿态判据方向 | 原写"tilt ≤ 40° 持续 0.5 s"是**反的**：活体 `metrics.fall_flags` = `sustained_any(tilt_cos < limit)`，即**超阈连续 ≥ 0.5 s 即跌倒**。改为 `sustained_tilt_v1 {threshold_cos 0.766, sustain_s 0.5}`，并写明聚合是**任一 env 破线即不通过**（`_gate_sustained_tilt_v1` 的 `.any()`），不是比例 |
| 评审 #4：零命令与聚合 | PLAN 写死：`v_cmd < 0.1` 的帧**单独成零命令带**、按绝对口径 `\|v_fwd\| ≤ 0.15 m/s` 且只在 `alive` 帧上算（否则跌倒后速度≈0 白拿分）；相对分母 `max(v_cmd, 0.5)`（替换旧实现的 `clamp_min(1e-6)`）；位移改为**先按带求和再相除**（替换旧的逐 env 先除后平均）；失败后帧在相对口径记 1.0、其命令仍进位移分母；逐带全过才算过 |
| 评审的两条待拍板（所有者 2026-09-22） | ① 跟踪 0.25 = 本版**预注册工程阈值**，并写明"不是从旧版 0.2 推导"，配套固定评测命令覆盖 + 分低速/高速报告；② 非足接触**不**整体升门槛，升的是**持续非足承重**（`non_foot_carrier_v1`，body 维先 `any` 再判持续），且**作为通过条件**；瞬时碰撞留诊断 |
| 第二次评审 #1：执行器预算口径（**我先前的分母是错的**） | 核实：本 fork 的 `ImplicitActuatorCfg` 在未设 `velocity_limit_sim` 时把 `cfg.velocity_limit` **置 None** 并只发 warning（`isaaclab/actuators/actuator_pd.py:80-91`），而本线仍传它（`lizard2_recipe.py:129`）⇒ **`velocity_limit` 不构成仿真分母**；`effort_limit` 则转成 `effort_limit_sim` 生效（同文件 60-67）。数字更正：2 m/s ⇒ f≈1.82 Hz、τ≈123 N·m（**68%** of 180）、峰值 ≈6.9 rad/s；2 Hz ⇒ ≈83%。PLAN 新增硬前置 4（悬空跟踪 / 承重协调两层 + 上限口径实测），并写明估算假设（质量同半径，**可高估也可低估**、非保守下界）与 `computed/applied_effort` 只是**近似力矩** |
| 第二次评审 #2：非足承重（方向 + 漏洞） | 核实 `_gate_non_foot_carrier_v1`（`baseline_metrics.py:149`）= `(non_foot_fraction >= fraction).any(dim=-1)` 再判 dwell：`fraction` 是**破线水平**，**调高更宽松**（原先"抬 fraction"的建议是反的）；且 body 维先 `any` ⇒ **两部位各 8%、合计 16% 可绕过**。PLAN 改为两条判据（保留旧 kind 语义 + 新增总量 `non_foot_load_sum_v1`），阈值改用正常/异常样本 + 噪声标定，不贴历史故障值 |
| 第二次评审 #3：自碰撞 | 核实本线 `enabled_self_collisions=False`（`lizard2_recipe.py:149`）⇒ 训练不会惩罚穿腿/穿身，而新髋让"腿绕身体横摆"第一次可达。PLAN 新增硬前置 5：用**交叠或有符号穿透**（普通距离非负测不出交叠）、区分相邻关节允许重叠、粗网格只找反例、还要覆盖实际动作轨迹 |
| 第二次评审 #4/#5/#6 | 低速带 `[0.1,0.5)` 声明为**不可比**（要另跑同初态 + 定点 0.5 + 同窗口/模式的测试；训练命令分布仍不同 ⇒ 只到"两个方案同一测试的表现差异"）；步态判据新增 `gait_swing_v1`（只在移动命令上判、多指标合取、`min_swing_feet` 由所有者冻结）；髋惯量表述更正（有效惯量是整条下游链，1e-6 只是数值条件），`*_kfe` 区分"没建碰撞形状"与"惩罚列表保留无效条目" |
| 第二次评审 #7：理由的静默沿用 | `emit_diff_declaration` 记录 `authored_against`（每个 env 组 + 整个 agent 段一份值摘要），**值变化时保留原文 + 打 REVIEW 标记**（不再静默认可）。实测：安静再生成**逐字节稳定**、理由全留；伪造基线后只有受影响的组与 agent 段被标记、文本原样保留；`TODO` 不标、标记幂等。改这一段时**我自己引入过一次"再生成抹掉全部理由"的回归**，被这条测试当场抓住并修好 |
| 终止条件加头守卫（所有者指示，2026-09-22） | `terminations.head_contact` = `chest_.*`/`neck_.*` 接触力 > **1.0 N**（与 `base_contact` 同一个"接触"值）即终止；实现只用框架 `illegal_contact`（不新增核、不加额外 dwell——dwell 交给接触传感器 3 帧 history 取最大）；yaml 加 `names.head_contact_body_names` 与 `terminations.head_contact_threshold`（两份 yaml 仍逐字节相同，7581 B）；元素 `lizard2_base_contact` 更名 `lizard2_contact_gate` 并同时写两条终止。机器侧连锁按机制走了一遍：硬 A 先报出**三处**漂移（built cfg ≠ golden / `terminations.head_contact` 未声明 / `base_contact…body_names` 的作者名与新元素不符），再 `check_cfg_lock --update --reason` 重钉 golden（2 task 变化）、`check_dr_parity --update-locks --family lizard2` 重钉 v1 锁、re-emit 后路径 64 → **65**、`EXPECTED_DIFFS` 107 → **108** ⇒ `RECIPE_BUILD_OK (38 task(s); 468 declared difference(s))`；套件 **47/47**；真实 env 构建通过（`obs_protocol_live --tasks Lizard2-Flat-v1`：`policy=102`、`bodies=31`、`joints=30`，无正则不匹配报错） |

## 证据引用

- 复读：`run_offline_checks.bat`（47/47）、`check_recipe_build.py`、`check_obs_protocol.py --self-test`、
  `obs_protocol_live.py --all-tasks`、`obs_protocol_inventory.py`（声明草稿）、`check_version_docs.py`。
- 评审 #1 的两个反例可原样复现：把 `versions/obs_protocol_anchors.json` 里协议 `a25a8c39001b` 的 `dims`
  删除（或把 `assets/lizard2/lizard2.usda` 的值改成 `{}` 并重算 `dims_digest`），`check_anchors()` 立即报出
  "no approved widths at all …" / "has no width for ['policy']"。
- 落点：`work/active/lizard2-family-landing.md`（`next` ①-④）；机器件见 `FILEMAP.md` 的"机器件"与
  "`joint_order` 有两种"两条。

## 未覆盖边界

- **头守卫从未被观测触发**：它构建、解析并通过真实 env 构建（正则匹配到 body），但**没人见过它真的触发**；
  1.0 N 这个水平是"与 `base_contact` 同一个接触值"，属**类比继承**而非实测标定。要钉住它需要一次
  "把头压到地上"的探针读数（或在探针里扫一条逐渐下压的指令）。另外 `head_contact_body_names` 含 `chest_.*`，
  比"只有头"更严：若平地爬行时前胸合理擦地，会提前终止——这是刻意选宽（旧线故障是整条前链承重），
  但要留一条"触发率过高就收窄到 `neck_.*`"的判据。
- **训练终止与评测判据是两套**：训练侧现在是两条**接触**终止（瞬时、同一 1.0 N）；评测侧仍是
  `sustained_tilt_v1`/`survival_v1`/分带跟踪位移 + 待新增的**持续**非足承重（单部位与总量）与 `gait_swing_v1`。
  方向一致（都堵"靠非足承重"），但阈值口径不同，别互相引用。
- **宽度缺失现在是静态红**（评审 #1 修完）：`check_anchors` 按"这条协议上已声明任务**自己加载**的资产"
  强制要求**完整**宽度表——整表缺失 / 该资产无条目 / 条目缺活跃组，三种形状都红，各有反例。
  **仍未覆盖**：宽度**变了但两边都批准过**的那种（同一路径原地换代）；离线读的是 golden，里面没有宽度，
  只有 `obs_protocol_live` 活体重建能发现，而它不在离线套件里。
- **协议身份仍不含宽度**：两个宽度不同的资产可以名正言顺地共享一个协议键；`dims` 的资产层是补丁式修正，
  不是"身份即内容"的复原。要做到后者，摘要必须覆盖被实例化后的宽度，而宽度只有活体构建才知道
  （`manager.group_obs_term_dim`）——除非让 golden 开始记录宽度。
- **解析共用有前提**：`assets_on_protocol` 按文件位置直接加载 `obs_protocol.py`，所以"离线闸门不需要框架"
  靠的是该文件自己只 import 标准库；哪天它引入别的依赖，这条链会退化成"全部任务解析失败"（是红不是静默过，
  但错误信息会淹没真问题）。
- **评审 #4 的实现未落地**：`tracking_banded_v1` / `displacement_banded_v1` / `non_foot_load_sum_v1` /
  `gait_swing_v1` 四个种类**都不存在**（`CRITERION_KINDS` 里没有，`baseline_metrics.py` 仍用 `clamp_min(1e-6)`
  与逐 env 先除后平均），本线协议文件也还没写——属已声明的冻结前置（本项 `next` ①）。
- **执行器能力曲线与自碰撞检查都还没跑**（PLAN 硬前置 4、5）：0–2 窗口的上界是否物理可达、新髋横摆是否穿身，
  目前**只有量级估算与风险声明**，没有实测。这两条按所有者意见列为开训前最高优先。
- **`non_foot_carrier_v1` 的 `sustain_s` 未定**（`fraction` 与其标定样本也未定）；"非足 = 除 `*_foot` 外全部 link"
  是按本线资产说的，换家族要重述。
- **本轮套件整体是红的**，但红在另一处工作：`rl_exp/tools/verify/test_video_matrix.py`（非本项产物）被加进套件后
  触发"未声明地 spawn 解释器"与条数棘轮（48 > 47）两条问题，未见本项改动引入新红（改动过的检查在本轮运行里全绿）。
  按"不碰别人在做的工作"处理，只报告。
- **搬家不改历史**：`acceptance/records/2026-09-16-lizard-obs-protocol-gate.md` 仍写着旧路径
  `versions/lizard/joint_order_runtime.json`（当日事实），未回改；现行路径以 `FILEMAP.md` 为准。
- **PLAN 的配方表是人工摘要**，差异的唯一维护位置是 `diff.json`；两者若不一致，以闸门读的那份为准。
- 启动探针改造（30 维动作 / 102 维 / 区间命令 / 重采样）**未做**，本轮的 102 是构建期实测而非探针断言；
  落地姿态目视、tag 亦未做。
