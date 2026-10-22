# 诊断运行的创建与收尾

当前已接入口：`rl_exp/tools/diagnose/local_path_view.py`、`diagnose_support.py`、`palm_spatial_probe.py`。其它生产入口仍按
`work/active/diagnostic-artifact-lifecycle.md` 推广，不能由本入口推定全覆盖。

从仓根用配置解释器运行；输入取已有报告，不重新采集物理：

```text
<python> -B rl_exp/tools/diagnose/local_path_view.py --source_report <support_report.json> --drive_report <reset_probe_report.json> --root_translation --output_dir rl_exp/out/runs/local-path-view/<new_run> --topic local-path-view --work_id <active_work_id> --owner <executor> --retention_reason "<why retain this run>"
```

目录必须全新。旧 CLI 参数仍可用；新调用显式填写事项与执行者，省略事项时由
`diagnostic-artifact-lifecycle` 承接归属核对，不能据此冒称原实验已经交接。
无需手工补索引：入口在第一份图像写入前创建 `run.json` 并向现有
`artifact_index.json` 注册位置。索引只指向运行记录，状态和保留决定归运行记录。

运行记录保存输入、代码的逻辑身份、当前位置、摘要及复跑参数；新分析同时保存
`input_bindings`，历史绝对路径不再是唯一读点。`analysis.json` 的图像绑定不包含
随后仍需收尾的 `run.json`，运行记录最终绑定分析与所有图像。完整性检查复用
`binding.py` 的摘要实现。开始写产物前及收尾时检查绑定；它不是不可变执行快照。

```text
<python> -B rl_exp/tools/diagnose/artifact_run.py --inspect_run <run_directory>
```

只有 `completed`、唯一索引登记和全部输入/代码/输出摘要同时成立时返回成功。
此检查只读。源码或输入后来改变也会拒绝，先恢复对应字节再复读，不改旧摘要冒充通过。

| 磁盘状态 | 执行者动作 |
|---|---|
| `completed` 且检查通过 | 按记录中的保留理由复用，核对原证据适用范围 |
| `failed` | 按 `owner`、`error`、`next` 排查；保留现场，重新执行用新编号 |
| `registering` / `running` | 先确认原执行者是否仍在写；进程已停止也不能当成功或自动删除 |
| 缺记录、缺登记、损坏或缺文件 | 视为未完成；由原执行者与维护者核对，不凭报告文件存在补成功状态 |

索引写入用操作系统锁协调本入口的并发写者，失败即停止产物写入；人工修改索引仍须
协调。登记或收尾失败会返回失败并尽量写失败记录；连记录也写不了时，目录及原状态
留下供检查识别。强制结束进程不会执行 Python 清理，留下的 `running` 同样不合格。
该入口不自动删除任何失败现场，不自动继续向半写目录追加。

行为回归和完整换根复读：

```text
<python> -B rl_exp/tools/verify/test_artifact_run.py
<python> -B rl_exp/tools/verify/test_artifact_run.py --real_run <completed_run_directory>
```

后一入口要求本机仍具备记录绑定的全部源码与输入，用记录重建临时恢复包，给绑定源码
配置精确的 `-text` 属性以保住运行时原字节；这与一般源码检出的文本规范化用途不同。
它真实 add/commit/clone，两档检出均核字节，阻断旧仓 Python 文件读取，完整生成图像，
比较逐帧像素及关键分析，最后清理自己的恢复目录。失败时返回错误，不能以缺输入的
运行代替有效恢复验证。图像语义仍需人工查看；逐像素相等只证明同环境再生成一致。

输出默认本机保留且被 Git 忽略；索引、源码与验收记录入仓不等于运行字节有外部备份。
恢复证明的范围、结果及已知边界见事项的验收记录指针。

## 支撑诊断入口

`diagnose_support.py` 使用同一索引和收尾机制，输出根保留为
`rl_exp/tools/diagnose/out/`。默认 label 放进 `runs/support/`；显式 `--label`
仍相对该根定位，必须是安全的新目录。原 case JSON、原始下采样时序和摘要继续输出，
各报告通过相邻 `run.json` 找到绑定；完成生产不代表资产或物理表现通过验收。

```text
<python> -B rl_exp/tools/diagnose/diagnose_support.py --headless --task Lizard2-Flat-v3 --checkpoint <existing_checkpoint.pt> --phases 0,1 --heights "" --label runs/support/<new_run> --work_id <active_work_id> --owner <executor> --retention_reason "<why retain this run>"
<python> -B rl_exp/tools/diagnose/artifact_run.py --inspect_run rl_exp/tools/diagnose/out/runs/support/<new_run>
<python> -B rl_exp/tools/verify/test_diagnose_support_output.py
```

空高度只选择平地单环境，Phase 3 必须指定台阶高度；原多高度默认值保持。checkpoint、
目标声明、USD/URDF 及引用网格、配方/命名声明和实际仓内源码绑定在运行记录中，解析后的
环境与 runner 配置用已有配置序列化器保存。外部 checkpoint 仍按实际外部位置校验，
本入口不自动备份或搬迁 checkpoint，也不宣称已有支撑仿真的完整异机恢复机制。

写 case/摘要失败会保留已写报告；Phase 0 的提前返回也经过收尾。环境通过退出栈关闭，
CLI 将错误码传给 Kit 原生快速关闭，控制台采用 UTF-8，避免成功写报告却丢失失败状态。
原生进程崩溃无法执行 Python 收尾，保留的 `running` 必须视为未完成。
支撑入口对整个诊断网格使用 `scene.replicate_physics=False`：逐环境复制 USD 并分别解析物理，
避开当前框架在原生复制阶段的访问冲突。所有地形列继续运行，资产和物理参数沿用目标绑定；
实际模式保存在配置快照中。代价是场景初始化较慢，底层原生复制故障仍需跟进。
多环境与台阶路径可用新 label 复验：

```text
<python> -B rl_exp/tools/diagnose/diagnose_support.py --headless --task Lizard2-Flat-v3 --checkpoint <existing_checkpoint.pt> --phases 0,1,2,3 --speeds 0.3 --reps 1 --label runs/support/<new_run> --work_id <active_work_id> --owner <executor> --retention_reason "<why retain this run>"
```

实际覆盖、失败对照及原生故障边界见事项最新验收记录；完成生产不代表台阶通过率合格。

绑定校验在创建和读取端共用：输入、源码、身份、位置、摘要及归属不可擦空；命令首项
必须有效，后续参数允许合法空字符串。源码采集只把绝对仓内 Python 来源当文件绑定，
框架动态模块的相对伪文件名不会被拼成仓内源文件；真实绝对源码缺失仍拒绝。

## 支撑原生复制的历史对照

`support_native_ab.py` 从 Git 读取旧、新完整入口，使用当前绑定输入配对运行至 Phase 0，
用于定位初始化故障。先确保参考运行的输入和辅助源码仍可校验，再使用全新输出目录：

```text
<python> -B rl_exp/tools/diagnose/support_native_ab.py --output_dir E:/Robot/rl_exp/tools/diagnose/out/runs/support-native-ab/<new_run> --crash_reporter off
<python> -B rl_exp/tools/diagnose/support_native_ab.py --output_dir E:/Robot/rl_exp/tools/diagnose/out/runs/support-native-ab/<another_new_run> --crash_reporter local
<python> -B rl_exp/tools/diagnose/support_native_ab.py --inspect_results E:/Robot/rl_exp/tools/diagnose/out/runs/support-native-ab/<completed_run>
```

`--reference_run` 可显式指定输入绑定来源；`--before`、`--after` 指定历史源码版本。
local 模式先验证报告器启用、上传 URL 为空、跳过旧转储上传、禁止启动上传；校验失败即停止。
off 模式关闭报告器并同样禁止旧转储和启动上传。实验的 `completed` 只表示全部试验已记录，
逐次物理结果须读 `report.json`。`--inspect_results` 只读核验原证据，保留原分类并给出当前分类器判读。

源码归档在 `sources/`，驱动归档在 `driver.py`，实际命令保留临时 sibling 路径；
不能直接从归档目录执行原脚本，因为它依赖相对仓根和 sibling imports。复跑优先用本工具创建新运行，
单次重放须按记录恢复相同源码位置并换新 label。实验期间不要同时跑全仓源码扫描，以免碰到临时源清理。
本工具不修改生产入口或原生回调，比较范围与结果归事项最新验收记录；不把小样本运行当作底层故障修复。

## 空间几何探针

`palm_spatial_probe.py` 的历史对照、`--static_slices`、`--refine_slices`、`--local_path`
共用运行登记和收尾，原几何报告仍为 `report.json`。沿用几何复用指南的模式和判据，
输出必须为两诊断输出根下的全新目录；`--self_check` 不建产物目录，优化模式明确拒绝。

```text
<python> -B rl_exp/tools/diagnose/palm_spatial_probe.py --static_slices --build_report <build.json> --output_dir rl_exp/out/runs/palm-spatial/<new_static> --work_id <active_work_id> --owner <executor> --retention_reason "<why retain this run>"
<python> -B rl_exp/tools/diagnose/palm_spatial_probe.py --refine_slices --build_report <build.json> --source_report <static_report.json> --angle_resolution <rad> --output_dir rl_exp/out/runs/palm-spatial/<new_refinement>
<python> -B rl_exp/tools/diagnose/artifact_run.py --inspect_run rl_exp/out/runs/palm-spatial/<new_static>
<python> -B rl_exp/tools/verify/test_palm_spatial_output.py
```

写图/报告失败留已有文件和 `failed` 记录；同名不会重采或覆盖。`completed` 仅指采集和产物收尾完成，
几何判词仍按报告读取。历史对照不合格的退出仍使运行记失败，局部探索的失败前缀继续按原结构保留。
现代模式绑定候选自包含文件、build/源报告和实际源码；原始源输入只作溯源，历史对照仍真实核读旧机构输入。
使用既有可信索引映射后，build 和源报告可从当前位置调用；身份比较按完整逻辑路径，摘要按实际读取文件。
实际覆盖、旧根隔离和失败注入复读参数见事项最新验收记录，不外推其它消费者或整机异地恢复。

空间探针旧目录的历史基准与归档路由：

| 用途 | 当前落点与读取方式 |
|---|---|
| 当前候选输入 | `rl_exp/out/lizard2_palm_spatial_20261014/checkpoint_v3/`；仍由现有消费者读取 |
| 原 v3 几何正反例 | `rl_exp/tools/diagnose/baselines/palm-spatial-20261014/{probe,locked}/`；原逻辑路径由 `ArtifactPaths` 解析 |
| 早期历史构建与对照 | `rl_exp/out/archive/palm-spatial/history-20261014.zip`；按 `manifest.json` 将 `blobs/<sha256>` 恢复到清单路径 |

ZIP 为本机归档，不随 Git 检出；异机须先取得同摘要归档。索引未提供 ZIP 透明读取。
恢复验证使用全新证明目录，将代码与输入一并换根，在旧仓不可读的子进程中执行实际几何入口：

```text
<python> -B rl_exp/tools/verify/test_artifact_relocation.py --archive rl_exp/out/archive/palm-spatial/history-20261014.zip --proof_root rl_exp/out/runs/diagnostic-artifact-lifecycle/<new_recovery>
```

这条命令验证恢复并清理自身临时副本；正式恢复按清单操作，不覆盖已有目录。
处置结果与早期报告的复读边界见 `acceptance/records/2026-10-22-diagnostic-spatial-consolidation.md`。
当前输入的其它消费者迁移仍由原事项推进。
