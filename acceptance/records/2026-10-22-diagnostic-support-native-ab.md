# 支撑诊断原生复制：历史完整脚本配对对照

## 适用范围

事项：`work/active/diagnostic-artifact-lifecycle.md`。本轮回答重构是否为原生复制崩溃的必要条件；
不修改生产入口的独立物理解析模式，不调整资产、训练配方、驱动、阈值或物理参数。
操作入口：`rl_exp/docs/diagnostic_artifacts.md`；工具：`rl_exp/tools/diagnose/support_native_ab.py`。

对比 Git 原始完整脚本，未插桩原生回调：

| 组别 | Git 版本 | diagnose_support.py 原字节 SHA-256 |
|---|---|---|
| before | `6d89441a2c9d4b9e243a30d388a61612978db726` | `94909c4f197ff273d04b9155699df2ad106da396748394dae398035d48dc2061` |
| after | `8d94688d746b3bb60a1ddb23ed6d875a6d375332` | `dda4b9cb7915468973487e9747bba3fb1059a0ad608ed79be82263eb3b586049` |

两份历史脚本均使用当前依赖、checkpoint 和资产，原生复制开启、默认九环境，执行完整入口至
Phase 0 的环境创建、策略加载与测量；不执行 Phase 1–3。环境构造配置块的 AST 一致，
但完整脚本仍包含 agent 配置构造顺序、元数据与控制台处理等差异，不冒称只改变一个变量。

引用已验收运行 `runs/support/lifecycle-v3-nineenv-summary-20261022` 的 49 个输入和
22 个仓内辅助源码；另绑定驱动工具源码及四个当前框架源文件，共 53 个输入、23 个代码绑定。
框架文件为 `physx_replicate.py`、`physx_manager.py`、`interactive_scene.py`、`simulation_context.py`。
这些绑定约束本次比较，并非历史整机、全部二进制及缓存快照。

## 验收条件

- 使用 Git blob 原字节执行旧、新完整脚本；每对共享输入、配置、解释器、base_seed 和 hash seed，
  交替 AB/BA 顺序，保留每次命令、退出状态、日志、测量及摘要，不用报告存在推断成功。
- 崩溃报告器关闭和仅本地处理两种模式均限制上传；仅本地模式先用无物理 Kit 进程读取有效设置，
  不满足约束则不开始物理实验。
- 实验完成与物理子运行完成分开；保留真正原生失败、超时、Python 失败和不完整输出的区别。
- 历史源码及驱动源码归档且保持执行身份、字节摘要和真实命令；临时入口结束后清理，旧证据不借当前源码校验。
- 针对审核发现保留修前失败、修后通过；只读重判保留原分类，相关检查及仓库闸门通过。

## 结果

两组实验均完成；这里的完成仅指比较流程收尾，不表示每次物理运行成功。
每组四对，hash seed 为 0、1、2、3，顺序 AB、BA、AB、BA；base_seed 均为 1000，
相同 checkpoint、四档默认台阶高度及九环境，每个子运行期限 150 秒。

| 报告器模式 | before | after | 已完成测量的配对核对 |
|---|---|---|---|
| off | 4 次完成 | 4 次完成 | 4 对去掉新版 run_record 指针后内容一致 |
| local | 3 次完成、1 次原生失败 | 4 次完成 | 前 3 对同样一致；末对旧版没有测量 |

local 的 `pair3-before` 由未改的旧脚本触发：日志先报访问冲突，后报 `0xc0000374`，
均位于 `physx_replicate.py:102 attach_end_fn`；进程真实退出码为 `3221226356`，未被期限强杀，
崩溃发生在环境初始化阶段。这证明旧脚本在当前栈、同一调用位置也能原生崩溃，
**重构不是这类故障发生的必要条件**。不能据此排除重构影响发生概率、存在独立故障或其它触发因素；
也没有确定底层 C++ 内存错误的起因。继续保留生产入口 `replicate_physics=False` 的规避方式。

运行初次申请被自动权限审核拒绝，理由是崩溃报告器可能上传转储及元数据。随后使用 Carbonite
支持的环境覆盖及 Kit 设置关闭报告器、旧转储上传和启动上传，获准执行。第二组保留报告器，
但上传 URL 为空；在物理开始前实读 `/crashreporter/enabled=true`、`/crashreporter/url=""`、
`/crashreporter/skipOldDumpUpload=true`、`/app/uploadDumpsOnStartup=false`。
设置语义见 [Carbonite CrashReporter 文档](https://docs.omniverse.nvidia.com/kit/docs/carbonite/208.3.2/docs/CrashReporter.html#debugging-crashes)，
本机有效值见第二组 `reporter_check.json`，执行日志未出现上传尝试标记。两组依次运行且驱动版本不同，
不把组间差异归因于报告器开关。

独立审核发现并修复两处实验工具缺口：

1. 旧分类器只认 `0xc0000005`，把这次实际原生堆损坏误记为 `incomplete`。现按非零退出及原生异常日志
   归 `native_failure`，保留原退出值、十六进制和调用帧；退出为零且报告完整的原生异常日志另行标记，
   期限终止也单独标记，均不冒充真实异常退出。
2. 本地报告器校验未强制 enabled 和 skipOldDumpUpload 的有效值。现生成的 Kit 探针和父进程都要求四设置成立。
   反例中关闭 enabled 或关闭 skipOldDumpUpload 均在物理启动前拒绝。

两项新增回归在修改分类器和校验前真实失败，共三个失败断言；修后完整支撑回归 25/25 通过。
另保留已执行源与归档源不一致的拒绝、后续活跃源码变化仍能读归档绑定、只读重判不改文件及损坏日志拒绝的测试。
`--inspect_results` 先核原运行完整性与日志/测量摘要，再输出 `reported_outcome` 和 `reviewed_outcome`、
分类器源码摘要及原报告摘要；原始 `pair3-before.json` 和 `report.json` 仍保留 `incomplete`，未追改实验历史。

两组父运行完整性及全部八份新版子运行记录通过；旧版在该历史版本没有生命周期记录，父实验记录承接其日志与测量。
父驱动和新版子运行的源码位置指向已核相同字节的归档副本，身份、摘要不变；命令保留实际临时脚本路径。
两组分别保留各自执行的 `driver.py`，新工具自动处理驱动绑定。临时 sibling 源码均已清理。
第一组旧驱动曾有异常日志后提前结束的分支，但这组没有原生异常日志，八次均正常退出，未走该分支；第二组取消此分支，等待真实退出或期限。

执行者最终仓库离线闸门 37/37 通过（50.3 s，jobs=6），提交前钩子通过；事项文档检查为 WORK_DOCS_OK。没有为本轮放宽闸门。日志为 `native-ab-offline-final.log`、`native-ab-precommit.log`、`native-ab-work-docs.log`。

### 独立复核

独立审核上下文 `independent_artifact_review` 未参与工具实现，只读审核历史 Git 源、两组真实落点、退出日志、控制参数及归档绑定，没有另起 Kit 或重跑全仓。首次发现的两个 P2 已闭合：实际 `0xc0000374` 原生退出现在能被当前分类器识别，本地报告器四项设置也均须成立；修前失败证据可用，独立运行最终 25/25 轻量回归通过（4.623 s）。最终判读源码摘要为 `256f95ead43db6b66bc768102ad673fbc2c0994fef5ea5ad8613cb61281e3179`。本轮范围内无剩余待修 P1/P2，实验记录及其限定结论通过独立复核。

独立核两份历史 source 与所列 Git blob 原字节相同，环境配置块 AST 一致；保留了 agent 构造顺序等真实版本差异。每对的 hash seed、base_seed、解释器和完整参数一致，差异为实际源码与新 label，顺序符合 AB/BA 交替。临时入口位于原脚本同目录且已清理，不能直接把归档目录当作执行位置。两份父驱动及八份新版子运行均可从已核相同字节的归档源码校验；旧版没有子运行记录的边界已明确。首组四对和第二组前三对测量在去掉 `run_record` 后一致，第二组末对旧版确实没有测量，日志保留原生复制帧、访问冲突及堆损坏退出。

独立调用最终 `inspect_results`，两父运行、日志和测量摘要检查通过；第一组 33 文件、第二组 37 文件及索引前后均未改变。第二组原 `reported_outcome=incomplete` 和原报告摘要保持，复核输出另列 `reviewed_outcome=native_failure`、`0xc0000374` 和 `attach_end_fn`，没有用新分类追改原始证据。两父驱动唯一代码绑定均指向各自 `driver.py`，身份和摘要不变。禁上传控制的选项语义核对了本记录所链官方文档，local 探针实际四值与约束一致；没有把“日志未见上传标记”扩张成额外的网络测量证明。独立证据在 `native-ab-independent-review/`：`tests-final.log`、`inspect-final.log`、`reporter-negative.log` 及初次路径/配对核验日志。

独立接受的因果结论仅为：旧完整脚本在当前栈、同一上层原生复制调用位置也能失败，因此本次重构不是该观察故障类发生所必需。相同调用帧不能单独确定相同底层内存错误；小样本、固定工况和顺序分组不能排除重构影响触发概率或另有缺陷，不能认定新版更稳定，也不能把两组差异归因报告器。未重建历史整机环境，未验证 Phase 1–3 的版本因果关系，底层故障未根治。本轮无需、也不得据此关闭总事项或恢复生产入口的原生复制模式。

## 证据引用

本机运行根（均位于 `rl_exp/tools/diagnose/out/` 下，默认 Git 忽略）：

- `runs/support-native-ab/20261022-paired/`：原始 `report.json`、八个 pair 记录与日志、归档源码、驱动和新版子记录。
- `runs/support-native-ab/20261022-local-reporter/`：同上，另有 `reporter_check.*` 和本地 dumps 目录；
  关键失败为 `pair3-before.log`、`pair3-before.json`。
- 两组驱动 SHA-256 分别为 `978cd5242fb5f070406190139b7887de2506b1904425da0599440ef619379616`、
  `8ee4aecea339fc46067a0db2b3a237d2dc76fe9ab0b9ace4d340720ff6bc0661`。

检查日志根：`rl_exp/out/runs/diagnostic-artifact-lifecycle/20261022-support-multienv/`。

- `native-ab-review-red.log` / `native-ab-review-green.log`：两项审核反例修前失败与修后完整 25 项通过。
- `native-ab-classifier-red.log`：退出为零、测量完整而含原生异常日志时，原分类错误的修前失败。
- `native-ab-evidence-check.json`：最终分类器只读核两父运行、八子运行、七对有效测量一致及临时源清理。
- `native-ab-offline.log`：实验临时源退出清理与全仓扫描并行导致文件消失，首次闸门 36/37；
  属检查时序失败，未改仓库闸门以忽略文件，待实验退出后完整重跑。
- `native-ab-offline-final.log`、`native-ab-precommit.log`：最终仓库闸门与提交前检查日志。
- `native-ab-independent-review/`：独立上下文审核日志，结果见本记录的独立复核条目。

只读复核（在仓根，使用配置解释器）：

```text
<python> -B rl_exp/tools/diagnose/support_native_ab.py --inspect_results E:/Robot/rl_exp/tools/diagnose/out/runs/support-native-ab/20261022-paired
<python> -B rl_exp/tools/diagnose/support_native_ab.py --inspect_results E:/Robot/rl_exp/tools/diagnose/out/runs/support-native-ab/20261022-local-reporter
<python> -B rl_exp/tools/verify/test_diagnose_support_output.py
```

复跑用工具读取上述 Git 源字节并在新目录执行，操作参数见子系统文档。归档的 source 不能直接在归档目录执行，
因为原脚本依据 `__file__` 寻找仓根和 sibling imports；如逐条重放，须把相同源字节恢复到原命令的临时 sibling 位置，
改用新 label，保留同一输入和报告器约束。当前只读重判不需要恢复或运行这些临时源。

## 未覆盖边界

- 没有重建历史整机依赖、全部原生二进制、缓存、ASLR、并发负载等；本轮是当前依赖下的完整历史脚本比较。
- 样本小且是顺序分组，不能估计可靠故障率、证明新版本更稳定、证明报告器影响故障或排除重构影响。
- 比较仅到 Phase 0；此前独立解析模式的九环境 Phase 0–3 复验证据仍归
  `2026-10-22-diagnostic-support-multienv.md`，本轮不重写该记录。
- 保留位置是本机证据，不等于外部备份或完整异机恢复；索引、源码与本记录入 Git，原始运行字节未上传。
- 原生故障根因、其它入口推广和存量处置继续由原活跃事项承接；本轮不关闭事项。
