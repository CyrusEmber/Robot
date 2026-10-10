# baseline / Lizard2 eval 解耦机制的事后补审（2026-10-10）

对象 = 已关闭事项 `baseline-eval-pipeline-restructure`（`work/closed/2026/baseline-eval-pipeline-restructure.md`，
2026-09-23 commit `b29a346` 关闭，`status: open → done` 一步到位、未经 `pending_review` 阶段）。
本次为**事后自愿补审**：`pending_review` 机制 2026-10-10 才落地且其边界明写"不追溯历史关闭项"，
故本记录不评判它当年为何没走待审态，只判它的四项出口今天是否站得住。

**判定：PASS-WITH-GAPS。** P1/P3 的出口在磁盘与测试上真成立（破坏测试咬得住）；P4 只到"声明一致"级；
P2 的一条出口被仓内真实旧记录**行为反证** —— 它声明"完整性检查不作废旧判决"，而三条已入仓的
`baseline-frames-1` 记录今天复判全为 `invalid`，同目录 `eval.json` 记的却是 `fail`/`pass`。

## 适用范围

只判 `close_when` 里 P1–P4 四项出口在其 `landing`/`evidence`/`outcome` 上是否成立；不重开它的技术决策，
不评价家族协议与产品阈值，不判 `baseline_metrics` 的报告项依赖列规则本身该不该这样设计。覆盖：
`ablation_harness/baseline_frames.py`、`ablation_harness/baseline_metrics.py`、`ablation_harness/baseline_eval.py`、
`ablation_harness/components/command_player.py`、`ablation_harness/frame_semantics.json`、`ablation_harness/HARNESS.md`、
`rl_exp/tools/verify/test_baseline_contract.py`。真实 Kit 真跑不在覆盖内（见未覆盖边界）。

## 验收条件

1. P1：契约按记录 `format` 分派 —— 必需 meta / 合法列 / 形状轴标都读所选格式；旧格式有独立 fixture；
   破坏旧列、旧单位、必需 meta 必须红（否则该检查只是声明）。
2. P2：新 reader 的指标与报告项声明表在位；接触点速度复用 `diag_metrics`；**完整性检查不作废旧判决**。
3. P3：协议可选 `scenes`，按 env 分配、冻重采样、逐步注入、条件入 meta，判分侧同表核对并给逐场景有效帧。
4. P4：`HARNESS.md` 的机制契约已更新；未完成的版本声明按仓规另立活跃事项。

## 结果

**P1 成立（行为层，带破坏测试）。** 声明按 `format` 分派在 `baseline_frames.py:120-126`（`_FORMATS` 三份声明
各带 `columns`/`axis_kinds`/`required_meta`）、`:233`、`:273` 与 `baseline_metrics.py:1044`（`spec = format_spec(...)`）
`:1052`/`:1115`/`:1126` 成立；`test_baseline_contract.py:236-242` 的旧格式 fixture 是**手写常量**，不生成自当前 `COLUMNS`。
破坏测试（解释器内存内改声明，不落盘）：改 V1 的 `pos` 单位 ⇒ `test_frame_semantics_are_frozen` 红；删 V1 的 `yaw`
⇒ `test_an_older_format_record_is_read_under_its_own_declaration` 红；从最新格式抽掉 `foot_geometry` ⇒
`test_the_newest_format_demands_...` 红（证明该检查真读所选格式的 spec）；反向给最新格式**加**一条 meta ⇒ 旧格式记录仍绿。
残留两条（无一影响判决）：① `baseline_metrics.py:48` 的 `_BASE_COLUMNS` 仍是模块级常量（被 `:1083`、`:1208` 用），
今天无害（三种格式都声明这六列），但属本项点名要清的那类全局读取；② 事项 `landing` 写 `_expected_shape`，
代码里是 `expected_shape`（`baseline_frames.py:148`），符号名对不上。

**P2 部分成立：指标与声明表成立，出口"不作废旧判决"不成立。** 成立的部分：`FOOTED_JUDGE_ID`、
`foot_lift_v1`/`foot_slip_v1`、`REPORT_ITEMS` 声明表、`JUDGE_REPORTS` 只声明最新 reader
（`baseline_metrics.py:94,217-221,239-249`）；接触点速度 `foot_point_velocity:563-574` **直接 import**
`rl_exp.tools.diagnose.diag_metrics.contact_point_velocity`，无第二份叉乘；六种合成反例与参照在位。
不成立的部分（实跑，两处读数并列）：

```
E:\IsaacLab\env_isaaclab\Scripts\python.exe -m ablation_harness.baseline_metrics ^
  ablation_harness\results\lizard2_flat_v1\v1\Lizard2-Flat-v1_13999_deterministic_seed123\eval.frames.pt
# -> "verdict": "invalid"，四条理由皆 "the protocol reports foot_slip_mps, which reads
#    foot_lowest_point/foot_com_pos/foot_lin_vel/foot_ang_vel, but the record never measured it"
#    gates 全 null，metrics/diagnostics 空；"protocol_file": "embedded in the record"
# 同目录 eval.json:1664 -> "verdict": "fail"（judge baseline-criteria-banded-1）
```

三份已入仓帧记录（`lizard2_flat_v1/v1/...`、`lizard2_flat_v2/v1/...`、`..._settle0.5_superseded`）都是
`baseline-frames-1` + 内嵌协议声明 15 个 `report_only`（含 `foot_slip_mps`、`foot_yaw_deg`），今天全判 `invalid`；
同目录 `eval.json` 分别记 `fail` / `pass` / `fail`。**帧与协议字节未变，冻结判决不可再复读。**
根因：`_contract_reasons:1094-1101` 的报告项依赖列检查对**任何** reader 都生效（P2 承诺的"只对新 reader 强制"
只覆盖 `_judge_reasons` 的未实现名那一半：`:1096-1097` 的 `declared is None → continue`），而 P2 把 `foot_*`
加进了 `REPORT_ITEMS`。钉住这件事的测试用 `build(frozen, 20)`（默认写最新格式），所以永远看不到
"旧格式真实记录 × 声明了足端项的协议"这个组合 ⇒ 绿得理直气壮。这是"查声明一致 ≠ 查行为成立"的分界。

**P3 成立（代码 + 离线测试）；真跑读数不可再复读。** `command_player.py:74-106` 的 `scene_assignment`
（`index % len(scenes)` + `torch.randperm(generator=manual_seed(seed))`）与 `scene_commands` 在位；
`baseline_eval.py:114-130` 协议可选 `scenes` 校验 + `resampling_time_range=(1e9,1e9)`、`:277-287` 逐 env 注入
`vel_command_b`、`:322-325` 条件入帧 meta；判分侧 `_scene_reasons:1160-1199` 真被 `_data_reasons:1220` 调用，
逐场景有效帧 `diagnostics["scene_valid_frames"]:1358`。`2026-09-23-baseline-fixed-scenes.md` 的
"不对齐 ⇒ 点名空带 fail / 对齐 ⇒ 四带各 4000 帧"与机制自洽（空带那句出自带判据 `_band_label` + `measured nothing`，
记录归因正确；16 env × 1000 帧 / 4 带 = 4000 自洽）。但承载它的 `%TEMP%\baseline_eval_p0_probe` 已不在 ⇒
属记录自述，不可复读。

**P4 部分成立（声明一致级）。** `HARNESS.md:20-28` 有判据身份与 `report_only` 依赖列规则，`:29-36` 有
「代码基线 v1.9.0」与「敞口」，对应提交 `0c3ec25`（2026-09-22）同时建了 `work/active/harness-version-anchor-missing.md`；
该活跃事项 `status: open`，本地 `git tag -l harness*` 只有 `harness-v1.8.0` ⇒ 锚点确实未打。缺的一半：
`HARNESS.md` 全文没有帧记录 / 帧格式 / 足端四列 / 足端判据 / `scenes` 块（`frames` 只在 `:84` 文件清单里出现一次），
P4 的核心句"同一检查点新采集后默认全流程与同帧离线复判一致"在**本项 evidence 内没有观测**（那份真跑读数属兄弟项
`baseline-eval-persist-before-judge` 的 `2026-09-23-persist-before-judge-real-run.md`），而"验收总账即本行"
是拿 `outcome` 给自己作证。可独立复核的只有离线套件那一半。

**附带形状缺陷（不改判定）：`outcome` 复述了读数。** 按 `AGENTS.md` §Where the work lives 的"只有一个家"条，
数值/摘要只归本目录。逐条一致性核对结论：**无矛盾** —— `4000` ↔ `2026-09-23-baseline-fixed-scenes.md:23`；
`20 ms / 1 帧` ↔ `2026-09-23-baseline-frames-format-2-foot-reading.md:36`；`12+4 列 + 两条 meta` ↔
`baseline_frames.py:45-95`（`COLUMNS_V1` 12 项、`FOOT_COLUMNS` 4 项、`REQUIRED_META_V2=("ground_source","foot_geometry")`）。
无闸门管这件事（`check_work_docs.py` 只要求 `outcome: <what happened>`；`check_version_docs.py` 的
"no verdict readouts outside the ledger" 只扫版本文档族），故属散文纪律、靠 review 发现。

**`outcome` 自陈的"当时两处 `gait_probe.py` 单源闸门红"：今天都绿，且与本项无关。**
`python rl_exp\tools\verify\check_record_bindings.py` → `RECORD_BINDING_SINGLE_SOURCE_OK`（148 files clean，rc=0）；
`python rl_exp\tools\verify\check_terrain_split_source.py` → `TERRAIN_SPLIT_SINGLE_SOURCE_OK`（149 files clean，rc=0）。
当时成因有仓内记录：`acceptance/records/2026-09-23-decode-guard.md:67-68`（另一会话在飞 `gait_probe.py`，
其 `read_bytes()` 摘要点名使 `check_record_bindings` rc=1）。与本项无关成立：`gait_probe.py` 不在本项
`scope`/`landing` 内。**第二处闸门的具体身份在全库记录里未找到**（`单源|SINGLE_SOURCE` 只命中 4 处，无第二处红的自述）。

**附带发现（他人事项，仅点名不代改）：** `work/active/harness-version-anchor-missing.md` 的 `close_when` 仍只要
`harness-v1.9.0`，而它自己 2026-09-29 的追加正文要求编号 **≥ `harness-v1.10.0`**（`HARNESS.md:29` 也还写 v1.9.0）
⇒ 该文件内部判据自相矛盾，随该项下次改动并句即可。

## 证据引用

- 全量离线套件（含本项相关 `[13/37] test_baseline_contract.py`、`[9/37] work-ledger shape`）：
  `rl_exp\tools\verify\run_offline_checks.bat` → `ALL_OFFLINE_CHECKS_PASSED (37/37 in 79.7s, wave 382s/informational, jobs=6)`；
  工作台账 `WORK_DOCS_OK (75 item file(s))`。
- 两条单源闸门（不需 torch，PATH python 即可）：`python rl_exp\tools\verify\check_record_bindings.py`、
  `python rl_exp\tools\verify\check_terrain_split_source.py`。
- P2 反证（旧帧复判）：
  `E:\IsaacLab\env_isaaclab\Scripts\python.exe -m ablation_harness.baseline_metrics ablation_harness\results\lizard2_flat_v1\v1\Lizard2-Flat-v1_13999_deterministic_seed123\eval.frames.pt`
  → `invalid`；同目录 `eval.json:1664` → `fail`。
- P1 破坏测试：以 `E:\IsaacLab\env_isaaclab\Scripts\python.exe -c` 导入 `rl_exp/tools/verify/test_baseline_contract.py`，
  分别在改 `baseline_frames.COLUMNS_V1['pos']` 单位、删 `COLUMNS_V1['yaw']`、抽掉 `_FORMATS[FORMAT]['required_meta']`
  的 `foot_geometry` 之后调用对应测试 —— 三者都红，未破坏的基线先绿（内存内改、不落盘、不留文件）。
- 代码落点：`ablation_harness/baseline_frames.py:45-95,120-126,148,233-243,273-277`、
  `ablation_harness/baseline_metrics.py:48,94,107-166,217-249,563-574,1044-1132,1160-1199,1358`、
  `ablation_harness/components/command_player.py:74-106`、`ablation_harness/baseline_eval.py:114-130,277-334`、
  `ablation_harness/HARNESS.md:20-36,84`、`rl_exp/tools/verify/test_baseline_contract.py:236-242,433-494,652-711`。
- 事项与邻居：`work/closed/2026/baseline-eval-pipeline-restructure.md`、`work/active/harness-version-anchor-missing.md`、
  `work/closed/2026/pending-review-before-close.md`（机制与"不追溯"边界）、
  `acceptance/records/2026-09-23-decode-guard.md:67-68`（当时闸门红的成因）。
- 收口项：`work/active/legacy-frames-rejudged-invalid.md`（本记录的反证落地）。

## 未覆盖边界

1. 三项真跑（帧格式 2 的几何/轴/短接触读数、定点场景两次对照、`scenes` 块的 assignment）的原始 `*.pt` 在
   `%TEMP%\baseline_eval_p0_probe`，现已不存在 ⇒ 只能引记录文本，属"声明一致"，不是本记录的读数。
2. 需真实 Kit / 检查点 / 训练资产的项一律未跑：256-env 正式判决、早终止取证、场景驱动在 256 env 下的行为。
   `2026-09-23-lizard2-v1-first-eval.md`、`2026-09-23-lizard2-v1-gait-skate.md` 两份 evidence 的读数同属此列。
3. 当时第二处单源闸门的身份未找到（全库记录无自述）。
4. `frame_semantics.json` 现为三份格式（V3 由 2026-09-29 加），本记录按本项关闭时的两份判。
5. 本记录不判"报告项依赖列检查该不该对旧 reader 生效"这一设计取舍 —— 那是 `legacy-frames-rejudged-invalid`
   的处置口径，需用户拍板（修行为 vs 改声明）。
6. 只判这一条事项的关闭是否站得住；`work/closed/2026/` 其余历史关闭项按机制不追溯。
