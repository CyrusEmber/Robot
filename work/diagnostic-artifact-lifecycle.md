---
id: diagnostic-artifact-lifecycle
title: 诊断产物整理、证据复用与收尾管理
scope: rl_exp, ablation_harness
status: in_progress
landing: rl_exp/tools/diagnose/artifact_index.json, rl_exp/tools/diagnose/artifact_run.py, rl_exp/tools/diagnose/diagnose_support.py, rl_exp/docs/diagnostic_artifacts.md, rl_exp/tools/diagnose/self_weight_audit.py, rl_exp/tools/diagnose/support_archive_index.json, acceptance/records
next: Codex 诊断维护者用配置解释器复现回放命令缺陷，修正记录后用既有源报告复验。
close_when: 不带执行历史的新上下文核验清单闭合、在用产物可复读、退役依据完整及新运行收尾机制。
evidence: acceptance/records/2026-10-28-loaded-axes-compression.md, acceptance/records/2026-10-28-single-leg-failure-compression.md, acceptance/records/2026-10-28-lizard2-v4-whitespace-archive.md, acceptance/records/2026-10-28-diagnostic-combinations-archive.md, acceptance/records/2026-10-28-diagnostic-fixed-replay-blocked.md, acceptance/records/2026-10-28-diagnostic-inventory-consolidation.md, acceptance/records/2026-10-28-diagnostic-commit-scratch-archive.md, acceptance/records/2026-10-22-diagnostic-local-path-consolidation.md, acceptance/records/2026-10-22-diagnostic-export-consolidation.md, acceptance/records/2026-10-22-diagnostic-checkpoint-relocation.md, acceptance/records/2026-10-22-diagnostic-spatial-consolidation.md, acceptance/records/2026-10-22-diagnostic-spatial-producer.md, acceptance/records/2026-10-22-diagnostic-support-native-ab.md, acceptance/records/2026-10-22-diagnostic-support-multienv.md, acceptance/records/2026-10-22-diagnostic-support-producer.md, acceptance/records/2026-10-22-diagnostic-producer-review-followup.md, acceptance/records/2026-10-22-diagnostic-producer-review.md, acceptance/records/2026-10-21-diagnostic-producer-lifecycle.md, acceptance/records/2026-10-21-diagnostic-artifact-review-fixes.md, acceptance/records/2026-10-21-diagnostic-artifact-review.md, acceptance/records/2026-10-21-diagnostic-artifact-decoupling-cleanup.md, acceptance/records/2026-10-21-diagnostic-artifact-drive-runtime-retention.md, acceptance/records/2026-10-21-diagnostic-artifact-second-archive.md, acceptance/records/2026-10-20-diagnostic-artifact-first-archive.md, acceptance/records/2026-10-20-diagnostic-artifact-preflight.md, acceptance/records/2026-10-20-diagnostic-artifact-plan-review.md
---

## 当前范围

覆盖诊断脚本、两输出根及评测、录像、TensorBoard 和资产管线的本机生成物。保留在用输入、失败对照与复读入口。正式评测、训练和资产契约仍归原专项。

按依赖解耦、合并、重构、迁移活跃链并删除替代材料，处置归 evidence；机器人、驱动与判据归原专项。

协调入口：[机体与驱动总项](lizard2-body-drive-candidate.md)、[候选接线](lizard2-candidate-wiring.md)、[限位与 PD 验证](lizard2-restored-limits-pd-validation.md)。按实际读写关系确定迁移批次；正在写入的目录先协调停写，接通消费者并复验后迁移，未完成实验仍归原事项。

未覆盖项按下述阶段推进。

## 分类与保留原则

重构顺序见[面向机器人实验的架构精简与单向解耦重构](closed/2026/project-simplification.md)（原分批总纲已取消并归档至 `work/closed/2026/project-simplification.md`）。按[版本文档与原始产物](../rl_exp/docs/diagnostic_artifacts.md#版本文档与原始产物)核定在用和退役范围。存量先从验收记录定位版本结论，从当前消费者核定仍需原件的范围。

## 目标落点与复用

- 方案 A 逐步用现有路径机制把新原始产物归到一个 Git 忽略的缓存根，沿用 `runs/<主题>/<运行编号>/`，重试换编号。已在运行的进程继续用原路径。历史根和 `archive/` 按实际消费者接线，一次性文件优先系统临时目录。
- 持续保存 `eval.json`、抽样 `tb_scalars.csv` 和版本验收文档。帧先支持判分及失败恢复，`--keep-frames` 作为成功、结果可靠落盘后的留帧策略候选。失败、在用回归和正式训后九宫格、单段原片、`matrix.json` 继续按现有契约保留。
- 复用 manifest、绑定工具与既有索引，记录身份、用途、位置、依赖、归属和保留理由；不另建并行位置库、通用调度平台或逐包专用工具。结果唯一归验收记录。
- 新产物分开表达证据身份与存储位置，读取统一走既有定位能力；历史路径仅作兼容身份，不继续作为新报告的唯一定位依据。位置映射不授予资产批准，原报告字节与授权边界保持。
- 索引说明验证范围、资产/配置/工况、复读命令与适用性；复用前核对，输入变化只补受影响检查，旧资产或驱动证据不得外推。
- 源码、配置、索引、验收记录及必要的最小回归样本纳入 Git；运行输出默认忽略。已跟踪产物按冻结版本及资产契约逐项处理。
- 在用产物迁移时核验恢复和真实读取，再清理旧副本。旧版本原件在停写、无在办依赖、文档结论完整且处置核定后退役，记录实际可用范围。

## 迁移前必须补齐

整理执行者与脚本维护者按受影响链落实下表；已完成切片见 evidence，文档不代替行为证明。

| 缺口 | 必须落实的动作与验收 |
|---|---|
| 读取与隔离不完整 | 接通真实消费者及传递依赖，缺映射、错摘要拒绝，drive 摘要取实际读取字节；旧根缺失和旧副本冲突均验证。隔离覆盖 `Path.open`、`builtins.open` 及实际读取通道，先用旧根直接读取破坏对照验证隔离有效；旧根及链接不可读时运行完整入口，不只测 `_load`。 |
| 换根与检出恢复 | 代码、索引、证据及必要依赖一同恢复到新根，用新根代码的子进程运行 CLI 和 `check_build`；不得借原源码路径或删除授权校验通过。目标 attributes 随迁移核对；执行 add、commit、重新检出，覆盖 `core.autocrlf=true/false`，原始、blob、检出字节及绑定逐文件一致。 |
| 同名覆盖 | `diagnose_support.py` 及其输出根须覆盖真实报告和摘要写入：隔离样本同名重跑在覆盖前拒绝，旧文件内容、数量、摘要不变，不能只测 mkdir。 |
| 优化模式绕身份校验 | 必要 `assert` 改显式拒绝；不支持优化的入口在读写前拒绝。普通、`-O`、`PYTHONOPTIMIZE=1/2` 均测错误身份拒绝且无输出，正常身份按声明范围验证。 |
| 忽略与跟踪混淆 | 覆盖两根，实查暂存与忽略状态。已跟踪产物按当前消费者与版本契约逐项核定，在用基准可检出。未核定证据及仍待处理的失败现场保留。 |

回归保留修前失败、修后通过；按行为判定，不只看退出码。隔离样本不动现存证据，结果归验收记录。

## 下一步

按阶段推进；缺口未闭合，不以扩大盘点、分类或框架代替交付。验收入口闭环和完成批次，不以目录数、记录数或节省空间计进度。

### 精简批次 1：局部路径检查与回放

1. **修正回放命令并复用基线。** 用 `paths.yaml` 中的解释器运行入口，复现 `local_path_view.py` 的 `run.json.command[0]` 仍为裸 `python`，再与 `local_path_check.py` 统一为 `sys.executable`。新记录须能在仓根直接用记录中的 argv 复跑，复跑另给新输出目录。已有 `run.json` 保留原字节，复读时显式用配置解释器。历史四模式的同源输入为 `rl_exp/out/runs/palm-local-path/contact-20261015/report.json`，对应报告为 `rl_exp/out/lizard2_palm_local_quarters_20261016/report.json`、`rl_exp/out/lizard2_palm_local_mirror_20261016/report.json`、`rl_exp/out/lizard2_palm_local_combined_20261016/report.json` 和 `rl_exp/out/lizard2_palm_support_schedule_20261016/report.json`。当前源码真跑以 `rl_exp/out/runs/diagnostic-artifact-lifecycle/20261022-local-path-consolidation/current-source/report.json` 为输入，改前、改后用同一输入。历史四模式仅与同源结果对照。
2. **按字段验收，顺手删重复。** 四模式逐项比较适用的 `pose_count`、`new_pose_count`、`failure`、`completed_*`、`full_source_loop_quarters_pass`、`legs` 下各采样状态的 `task_m` 及 `sampling`，回放比较 `legs` 的读数及适用的根平移和驱动读数。预期差异逐项核对 `report.json` 的 `identity.code_sha256`，`analysis.json` 的 `postprocess_code_sha256`、`artifacts_sha256`，以及 `run.json` 的 `command`（含解释器与输出目录）、代码与产物摘要、运行位置和时间。每个变更摘要须能从对应文件重算，同源输入的摘要须相同，图像摘要差异须核对相应产物。移出的实际执行代码同次纳入 `run.json.code` 和相应报告的显式 `code_paths` 或后处理代码清单，复用现有采集边界并用遗漏或错摘要反例验证。历史源身份按原依赖边界核验，新增读侧代码写入当前产物的绑定。顺手删除先拼回放命令再覆盖的步骤和可直接复用的 `view.*` 转接，避免为这些转接新增模块。以 `git diff --numstat <改前提交> -- rl_exp/tools/diagnose/local_path_check.py rl_exp/tools/diagnose/local_path_view.py` 记录规模，若有新增共享文件纳入同一文件集，未跟踪时用 `git diff --no-index --numstat -- NUL <新增文件>` 补计。评审只把删掉的执行代码计为精简，搬移、注释和文档串不计收益，净行数仅报告。
3. **跑既有回归和旧报告复读。** 改前、改后复用 `test_local_path_output.py --real_source <上述当前源码输入> --proof_dir <新证明目录>`，覆盖真实四模式、同名拒写和写后失败留存。证明目录各用 `rl_exp/out/runs/diagnostic-artifact-lifecycle/<新运行编号>`，以满足产物登记和源码快照路径约束。另外用 `local_path_view.py` 实际复读上述历史同源报告并核验新 argv，跑仓库离线检查。重复验证沿用已有入口，证据归验收记录。

本批验收代码与产物字段。改前、改后实跑和绑定位点归本批验收记录。

### 一次性探针与代码目录内材料

`rl_exp/tools/diagnose/` 的 Python 脚本均归本事项核定，包含绑定旧线、旧版或历史资产的入口。用 Git 文件清单、`lines.json` 和实际消费者判断归属。批次 1 的回放试点单独验收，余下探针按调用链分段核定，阶段 2 的生产入口推广继续在本事项跟踪。批次 4 每个清理切片先核受影响的写者与读者。

Codex 诊断维护者先核 `dump_all_parts.py`、`inspect_blend.py`、`inspect_glb.py` 和 `legacy_contact_wiring.py` 的实际启动方式、在办用途与历史复读依赖。仍复用的维护入口留 `diagnose/`，确需复读的历史工具按现有 `rl_exp/tools/archive/` 约定接通，核定无用途的才删。文本零命中只用于筛候选。`archived_support_read.py` 仍由现有复读命令和测试使用，变更位置须同次接通两侧。

按用途选择登记。下游会读取、需要交接或有明确恢复需求的入口复用 `ArtifactRun` 和现有索引。一次性探针独占输出并就地记录 `git_rev`、`argv`、输入路径，必要时补实际输入或源码摘要，省去全局登记。换根实跑用于改变读写路由的批次。

按读取方式标明同目录 JSON 的归属。以 `palm_5b_targets.json`、`body_precheck_lizard2.json` 和 `support_archive_index.json` 为首轮例子，分别核对默认配置、显式配置和历史读取索引。配置沿现有读取入口，实际输出按产物收尾。迁移的文件在原路径不可用时用真实入口复读，再处置旧副本。

`test_lizard2_leg_drive_baseline.py`、`test_lizard2_leg_drive_protocol.py` 作为总纲批次 2 的套件外候选，将实际保护的判据和既有按需命令交给该批核定。是否进默认套件沿用现有准入和成本规则。

### 可独立处理的本机大件

先核明确可再生的子集，和回放代码修复独立验收。两个诊断输出根仍按下节保留集合处理。

- `ablation_harness/results/**/eval.frames.pt`。核对同目录 `eval.json`、真实消费者和冻结协议。旧版及 `_superseded` 帧逐项检查，[旧帧事项](legacy-frames-rejudged-invalid.md)所需样本留到裁决及回归结束。
- `ablation_harness/videos/`。先确认训练验收已完成和原片用途，优先核可重建的合成片和重复输出。原片和索引说明见 [README 的评测产物](../README.md#评测产物)。
- `rl_exp/versions/**/tb_scalars.full.csv`。核已有抽样 CSV 和写者状态，完整曲线仍用于回归时暂留。依赖再生的条目先核原始事件文件和抽样命令，按摘要退役的条目先核版本文档足够。
- `rl_exp/blender/` 的临时导出与备份、本机 `*_urdf/` 及 `rl_exp/assets/` 的未跟踪生成物。先查写者、源件和 USD/URDF 相对引用。跟踪的 `lizard.blend`、旧基准包与 checkpoint 走总纲资产支路。

验收记录列具名路径、保留理由、实际腾出的本机字节和真实消费者检查。Git 跟踪文件的检出减量单算。

### 两个输出根的保留集合与清理

本节在总纲批次 4 执行。整理执行者用现有索引、清单及真实读写关系定出保留集合，先核定以下种子和传递依赖。

- `rl_exp/out/runs/palm-local-path/contact-20261015/`，历史四模式同源输入与迁移现任位置。
- `rl_exp/out/archive/palm-local-path/regression-input-20261015/`，历史局部路径回归输入。
- `rl_exp/out/archive/palm-spatial/approved-export-20261019/`，批准导出及关联输入。
- 上节列出的当前源码输入、四模式基线和本轮对照所需产物，至少留到批次 1 验收及相应在办依赖结束。仍在写入、用途未明和待处理失败现场也列入保留集合。

1. **核定首轮候选。** 复用 `artifact_inventory.py` 分别排查 `rl_exp/out/` 和 `rl_exp/tools/diagnose/out/` 的散落目录、`runs/`、`archive/`。先核 `rl_exp/out/lizard2_b_lf_lift_20261019_run01/report.json`，其生产入口为 `palm_spatial_standing.py`，执行源见同目录 `source.py`，现场由 `rl_exp/out/lizard2_b_lf_lift_legs12_20261019/evidence_index.json` 绑定。复用 `acceptance/records/2026-10-19-lizard2-single-leg-lift.md` 和 `acceptance/records/2026-10-28-single-leg-failure-compression.md` 定用途。后续核 `lizard2_b_calibrated_20261021/`、`lizard2_b_loaded_axes_20261021/` 的审计和续跑依赖，分别核定原件、恢复样本、ZIP 和日志。
2. **处置和索引同批生效。** 确认写者停写与真实消费者。迁移在用材料时保留逻辑身份，同次更新 `relocation`、`current_location`、涉及的 `run_record` 和实际读取入口。退役前确认版本结论、工况和边界可从验收文档找到，处置具名范围并同次移除已退役运行的索引登记、更新在用指针。保留原索引和旧副本供本次回退，真实消费者复验后再处置旧副本。
3. **核定散落脚本。** 两根分别查 `.py` 的调用与归属。仍会复用的维护代码迁到 `rl_exp/tools/diagnose/` 并复验调用；作为在办运行源码快照的字节归原运行绑定，按产物保留集合核定。确认无用途后按具名范围删除，记录原归属和处置依据。
4. **验收清到保留集合。** 两根分别比对实际剩余与保留集合。在旧路径不可读的隔离根，用实际 CLI 或读取链验证迁移映射、摘要、`_load`、`describe` 及适用的 `--inspect_run`，核对本批涉及的索引目标可解析，无新增悬空。验收记录列停写证据、保留范围、移除路径、文件数和字节数。
5. **收住新增输出。** 新诊断沿用 `runs/<主题>/<运行编号>/` 和已有运行记录，重试换编号。一次性文件优先系统临时目录。运行用途结束时由事项负责人核定退役，持续保存对应版本的验收文档。

### 其余推进阶段

1. **已接入口维护——Codex 诊断维护者负责。** 已接入口的操作与范围见 landing、最新 evidence。继续修改须复核受影响绑定、故障留存、真实写入和恢复路径；记录存在不代替行为证明，不外推未覆盖模式。
2. **按用途推广入口——脚本维护者接入，实验执行者使用。** 查两根及其它发现落点的生产入口，按下游读取与恢复需求决定登记。真实消费者依赖的登记继续验证，`diagnose_support.py` 的另一输出根和同名写入路径必须覆盖。一次性探针走轻量记录。子系统文档留操作入口，公开 API 按弃用规则处理。
   - Codex 诊断维护者跟进底层 PhysX 原生复制故障，保留现场；support 独立解析模式的复验入口见 landing，修改须复验受影响模式，其它入口逐项推广。入口规避不等于底层修复，试点闭环不替代其余入口验收。
   - **退出条件**：受影响入口完成真实创建与收尾，验证同名拒写或入口特有失败。登记入口可独立复读，轻量入口在自身目录可追溯。未覆盖入口及新增产物仍有归属。
3. **分批消化存量——整理执行者负责，消费者维护者核对。** 明确存量清单的截点，后续新增走阶段 2；关闭前对差异补核。每批限定文件集与依赖闭包，记录大小、哈希、Git 状态、生产/消费者、事项、保留理由、动作和回退；执行前刷新文件与 writer 状态。展开代码、配置、报告、资源的传递引用，不反复全仓扫描代替处置。
   - 先用批次 1 的局部路径源报告与左前腿首跑失败现场，分别核对在办依赖和旧版本文档。仍用原件的条目查到具体文件、摘要和真实复读入口。历史结论的断链先补文档，未核定条目标明责任人和动作。
   - 六组合日志与临时索引批次原件保留；核实写者和当前消费者，仍有用途时接通索引并验证恢复。证据和阻塞见 `acceptance/records/2026-10-28-diagnostic-combinations-archive.md`。
   - 固定机身回放三目录先保留；核定当前是否仍需历史重跑。仍需重跑时查找精确渲染源码、恢复依赖并实跑。证据见本事项最新固定回放记录。
   - **退出条件**：在用迁移完成后复验真实消费者及恢复；退役条目核实停写、无在办依赖、旧版本结论可查且实际处置已记录。执行时核删除绝对范围并清理隔离副本，失败现场与未核定条目留责任人和动作。
4. **收敛与交审——整理执行者交付，维护者承接。** 对照存量截点、后续差异和生产入口清单逐项闭合；运行相关检查及仓库闸门，结果归记录并更新指针。机制交脚本维护者，日常收尾交实验执行者；超限只报告，新增闸门须有真实缺陷与破坏测试。完成后置 `pending_review`，由 `next` 点名新上下文审核者。

## 关闭条件

- **独立审核**：不带执行历史的新上下文对照实际落点、清单、映射、摘要、复读命令及恢复证据检查全部阶段退出条件，不依赖执行者总结。
- **清单闭合**：存量截点、后续差异和全部入口有处置；未分类、在写入或依赖待确认不算完成。后续动作同次用脚手架建新事项承接，不随关闭消失。
- **复用与退役**：从诊断问题可找到对应版本结论；在用输入、适用报告与尚需的失败对照可复读，迁移按前置表验证。退役有文档依据和明确范围，历史判词及已经记录的绑定保持原样。
- **新增与交付**：阶段 1、2 成立，正常运行无需整理者补账；维护者与执行者完成阶段 4 交接。运行输出不误入 Git，必要基准与最小样本可获取，记录说明本机独有证据与复现限制。
- **行为证明**：前置表和最新审核的修前失败、修后通过齐备；索引、helper、规则声明及试点通过均不能替代真实使用或全覆盖。
- **结果处理**：通过审核后关闭；可修缺口退 in_progress，仅用户能解决的缺口置 blocked。
