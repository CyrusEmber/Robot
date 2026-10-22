# 诊断绑定复审修复与支撑入口收尾

## 适用范围

承接 `diagnostic-artifact-lifecycle` 的独立复审及阶段 2 首次推广。修复完成记录可擦空输入/源码绑定的缺口；将同一生命周期机制接入 `diagnose_support.py` 的既有输出根。独立审核正文归 `2026-10-22-diagnostic-producer-review.md`，后续复核归 `2026-10-22-diagnostic-producer-review-followup.md`，不改写原不通过结论。

本轮不训练、不改 checkpoint、机器人资产、配方、驱动或物理判据；实际运行使用既有 `Lizard2-Flat-v3` checkpoint。它是生产入口的收尾验证，不是新的机体或策略验收。

## 验收条件

- 读检查与创建共用归属/绑定不变式；擦空输入、源码、身份、位置、摘要或必要归属时拒绝。合法空 CLI 参数可保存并复跑，不能被新校验误拒绝。
- `diagnose_support.py` 在真实 case 写入前自动归属、登记、独占目录；成功有清单和保留决定，提前返回、采样/摘要/登记失败均经过收尾。真实同名 CLI 在写前拒绝，全部文件与索引保持。
- 源码采集区分框架虚拟相对文件名与真实绝对仓内源码；缺真实源文件仍拒绝。控制台编码错误及 Kit 快速关闭不得掩盖失败。
- 用真实 CLI 完成创建与收尾，保留原生崩溃和部分/完整报告后失败的对照；不以单环境成功外推多环境。最终源码进行真实回放与独立复核，相关回归、仓库闸门及工作文档检查通过。

## 结果

### 绑定缺口与共享机制

独立审查的空绑定反例转成修前失败回归；两个用例产生 **12 个失败子情形**，覆盖双侧/单侧擦空、绑定身份及归属字段。`ArtifactRun` 创建和 `inspect_run` 现在共用 `_validate_metadata`：非空输入/源码列表、每行完整身份/位置/64 位摘要、主题/事项/执行者/保留理由、命令及输出清单。最终生命周期回归 **12/12，36.300 s**。

命令列表须非空、首项有效、所有项为字符串，后续空字符串是合法 argv。真实 `--heights ""` 暴露了初版校验误拒绝空参数，已保存修前失败并改正，未改写复跑参数来绕过校验。共享机制只扩展至既有 `rl_exp/out/`、`rl_exp/tools/diagnose/out/` 两根的子目录，不允许根本身或其它位置。

### 支撑入口与真实故障

`diagnose_support.py` 保留显式 label 的旧路径用法，默认新增放到该输出根的 `runs/support/`。绑定 checkpoint、目标声明、USD/URDF 和引用网格、配方/命名声明、实际仓内源码；以已有配置序列化器保存解析后的环境/runner 配置。case/测量报告通过 `run_record` 指向相邻记录，不另建索引。写入失败保留报告，退出栈关闭环境；Phase 0 提前返回也正常收尾。

首次真实启动在源码绑定处遇到框架的相对伪文件名 `_classes.py`，被误拼成 `E:/Robot/_classes.py`；Kit 原生快速关闭又将异常吞为退出 0。保留行跟踪及具体异常后，源码采集限定绝对仓内 Python 来源，真正的绝对源码缺失仍拒绝。CLI 在关闭前输出异常并传递失败码。后续真实编码失败返回 **1**，证明未再被关闭流程伪装成功。

多地形 **3 环境**真实运行 `rl_exp/tools/diagnose/out/runs/support/lifecycle-v3-20261022/` 在 PhysX `attach_end_fn -> rep.replicate` 原生访问冲突退出，进程码 **-1073741819**。登记已完成，记录保留 `running`、执行者、下一步及绑定；未写 case，检查拒绝成功。本轮没有修改外部 PhysX 实现。

增加显式空高度选择平地单环境，原多高度默认值保持；Phase 3 空高度明确拒绝。平地真实运行 `lifecycle-v3-flat-20261022/` 已写测量报告、两个 case 和摘要，随后 `print(summary)` 因 GBK 无法编码 `²` 失败；记录为 `failed` 并绑定四份已写产物。用真实 GBK 文本流先复现，再在 CLI 内统一 UTF-8；不依赖未记录的解释器开关或环境变量。

最终成功运行：`rl_exp/tools/diagnose/out/runs/support/lifecycle-v3-flat-utf8-20261022/`。相同既有 checkpoint，显式 `--phases 0,1 --heights ""`；**49 输入、23 源码、1 环境**，生成 `p0_measure_check.json`、两个 Phase 1 case JSON、`summary.md`。实际记录为 `completed`，进程退出 **0**，只读检查通过并决定保留。正常完成只表示生产过程结束，不把报告中的物理读数升级为合格结论。

从运行记录的命令列表再次启动真实 CLI、使用同一 label，退出 **1** 且含 `fresh isolated output required`；**5 文件**的集合/摘要及索引字节均未变，原运行仍可通过检查。原生崩溃、编码失败两份现场保留为真实失败对照，不删除或补成成功。

### 回归与恢复

support 新增的四个生命周期用例先在原 writer 上失败（两失败、两错误），最终真实 main/writer 回归 **15/15，3.126 s**。只替代仿真输入/读数，实际目录创建、JSON、摘要、运行登记和故障收尾走生产实现；覆盖 case 采样中断、摘要写失败、登记失败、Phase 0 返回、同名旧文件/空目录、虚拟来源/真源缺失、原生关闭码、合法空参数及 GBK 输出。单独的 binding 自检通过，旧过滤破坏对照保持。

修复后保留完整 drive/根平移回放：`rl_exp/out/runs/local-path-view/support-drive-root-20261022-final/`，供最终独立复核。完整恢复、图像及独立反例的结论以 followup 审核记录为准；本执行记录不冒充独立审核。

最终原迁移回归 **10/10，52.144 s**；最终全仓闸门 **37/37，60.5 s，jobs=4**。中途一轮被另一已完成提交流程遗留的 `commit_rl_handoff_20261022.py` 拦下：该脚本违反既有 revision 拼写单源检查。先核它的两个精确提交已在当前历史、目标文件组干净且原生进程查询无使用者，再清理一次性脚本及其两个真实 DIRC 临时索引；未跳过或放宽闸门。

同时核本轮 `support-drive-root-20261022-review-fix` 中间回放全部图像逐帧像素和关键分析均与最终回放一致，清理目录及对应索引项。以上共移除 **4 项、12,186,713 B**，逐文件摘要和替代位置归 `cleanup-final.json`；唯一的原生崩溃与编码失败现场保留，不为减数量删除反例。

实现、回归及索引提交 `8d94688`，仅包含本轮五个相关文件；提交前和实际 pre-commit 钩子均通过。审核记录、执行记录、操作文档及工作指针另组同步，未夹带其它会话的在办文件。

## 证据引用

- 实现：`artifact_run.py`、`diagnose_support.py`；回归：`test_artifact_run.py`、`test_diagnose_support_output.py`。操作方法：`rl_exp/docs/diagnostic_artifacts.md`。
- 本机 `rl_exp/out/runs/diagnostic-artifact-lifecycle/20261022-support-producer/`：`bindings-red.log`、`bindings-green-final.log`、`support-red.log`、`support-green.log`、`virtual-source-red.log`、`empty-argv-red.log`、`stdio-red.log`、`support-trace.log`、`support-exception.log`、各次 CLI 日志、`support-repeat-cli.log`、`support-repeat-proof.json`、`support-self-check.log`、`relocation-final.log`、`offline-final.log`（遗留脚本反例）、`offline-clean.log`（最终通过）、`cleanup-final.json`。这些日志和运行输出本机忽略保留，源码/索引/记录入 Git 不等于异地备份。
- 独立审查及复核记录、它们列出的独立日志是另一个上下文的证据，不用本执行者摘要替代。

仓根复读：

```text
<python> -B rl_exp/tools/verify/test_artifact_run.py
<python> -B rl_exp/tools/verify/test_diagnose_support_output.py
<python> -B rl_exp/tools/diagnose/diagnose_support.py --self_check_bindings
<python> -B rl_exp/tools/diagnose/artifact_run.py --inspect_run rl_exp/tools/diagnose/out/runs/support/lifecycle-v3-flat-utf8-20261022
<python> -B rl_exp/tools/verify/test_artifact_relocation.py
<python> -B rl_exp/tools/verify/offline_suite.py --jobs 4
```

## 未覆盖边界

原生多环境复制故障仍须由 Codex 诊断维护者复现和定位；本次平地成功不能代表多环境或 Phase 3 可用，也没有为其更改物理配置/阈值。外部 checkpoint 保留原外部路径，没有自动备份或承诺支撑仿真整条链异机恢复；原生崩溃无法执行 Python 清理，只能据运行记录识别未完成。

仅已接两入口具备该机制，继续使用/历史/未覆盖入口的逐项登记与具名动作、两输出根的完整推广、存量批次及交接仍未完成。事项保持 `in_progress`，不以本轮复核通过或文件数量变化关闭总事项。其它会话的脏文件未纳入本轮提交。
