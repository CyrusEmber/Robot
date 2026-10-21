# 已采路径回放的生产生命周期闭环

## 适用范围

`diagnostic-artifact-lifecycle` 阶段 1：`local_path_view.py` 的真实创建、登记、收尾、失败留存与换根复读。复用已有支持相位、同候选 drive、构建及绑定资源；不重新采物理，不改资产、驱动、判据或历史报告字节。原三项审核修复见 `2026-10-21-diagnostic-artifact-review-fixes.md`。

## 验收条件

- 第一份图像写入前有主题、事项、执行者、输入/代码身份、复跑参数及唯一运行位置；成功明确输出清单和保留理由。
- 同名真实 CLI 在写前拒绝，原文件集、全部字节及索引不变。
- 写入中失败、登记失败、初始/终端记录不可写及进程被强制结束均保留可辨认的现场；报告存在不能单独表示成功。
- 代码、输入、索引及必要声明真实 Git add/commit/clone，核原始/blob/检出字节，两个 autocrlf 设置均在新根完整运行 CLI；原仓所有 Python 文件读取通道被审计钩子拒绝。新报告绑定非空且正确，实际检查图像语义，再比较再生成像素与关键分析。
- 验证后清自己的恢复目录及可替代中间输出；回归与仓库检查通过，剩余入口推广与存量处置不随试点消失。

## 结果

### 创建与失败收尾

新增 `artifact_run.py` 复用既有 `artifact_index.json` 和 `binding.py` 摘要；不新建并行位置库。目录独占创建，初始 `run.json` 先落盘，再注册索引，最后进入产物写入。操作系统文件锁协调本入口的索引写者，JSON 通过同卷临时文件原子替换。索引只保存位置和运行记录指针，当前状态、执行者、保留决定归运行记录。

`local_path_view.py` 保留原 CLI，补可选主题/事项/执行者/保留理由。输入与代码分开保存逻辑身份、仓库相对当前位置及非空摘要；新分析保存 `input_bindings`。创建前和结束时重核绑定；`analysis.json` 不把仍会收尾的 `run.json` 纳入图像摘要，最终运行记录绑定分析和所有图像。

最初四个回归在未接机制的 writer 上全部失败：生产写入前没有归属记录，故正常收尾、写中失败、登记失败和终端记录失败均不满足预期。最终生命周期回归 **10/10 通过，33.794 s**，使用真实历史输入、真实解析/速率/drive/根平移和 JSON writer，绘图仅在这些故障注入测试中替换为小载荷。

覆盖部分 GIF 后抛错、索引原子替换失败、初始记录写不出、终端记录连续失败、单次终端失败后保留下一步、输入在渲染期间变化、输出损坏、登记缺失，以及真实子进程写出部分文件后被 kill。强制结束保留 `running` 与归属/下一步；终端记录不可写也保留磁盘上先前的未完成状态。只读检查均拒绝，不自动删除或把已存在的分析当成功。

单次终端失败的下一步还用内存破坏对照验证：保留收尾前的 `next=None` 而不重置，回归明确失败在缺下一步；生产源码未因此改写。测试注入须命中实际目标，未施加成功的尝试不计缺陷证明。

### 真实生成与完整恢复

最终保留运行：`rl_exp/out/runs/local-path-view/support-drive-root-20261021-final/`。原 CLI 同时带 `--drive_report`、`--root_translation`，生成四张轨迹 PNG、两份各 **109 帧**的组合 GIF、根平移 PNG 和分析，共 **8 份产物**及 `run.json`；自动登记及只读完整性检查通过。同名再次运行在写前拒绝，文件集、字节和索引均保持不变。

人工检查轨迹图、根平移图及侧视/俯视 GIF 的首/中/末帧：图中有实际碰撞三角网格、四掌标记、相位、根偏移及“播放不是物理时间”的说明；根 x 随相位推进，y/z 保持，曲线和材料点残差有内容。轨迹图关节图例较密，本轮不调整既有绘图口径；图像不构成步态或动力学批准。

恢复测试从运行记录的完整闭包生成临时包：绑定输入 **45 项**、源码 **13 项**，连 `.gitattributes`、索引共 **60 文件**。首次严格核字节时发现本机 `binding.py` 为 CRLF，普通源码属性会规范化为 LF；这次未继续冒充恢复成功。修正恢复包属性，给绑定源码逐路径 `-text` 保存执行时原字节，主仓源码属性和 `binding.py` 均未改。

`core.autocrlf=true/false` 两档各真实 add/commit/clone，逐文件原始/blob/检出字节相同，删除临时 source 仓，再由 clone 代码完整 CLI 生成全套产物。导入前的 CPython `open` 审计钩子屏蔽原 `E:/Robot` 全根；三种直接读取破坏探针均拒绝，正常完整回放旧根读取尝试均 **0**。两档所有 PNG 及 GIF 的全部帧像素与原运行相等，根平移、根前置读数、时间前置读数和各腿分析完全一致。drive 摘要均为 `36344c8af1ccf56552c931d252008fb50a9b6951265e8fe083f2079bd340d115`。恢复临时根核验后已清理。

两份本轮中间回放与最终运行逐帧图像、关键分析一致，清理前记录文件集、大小、摘要及替代位置，再删除目录和对应索引项；移除 **23,794,771 B**。只保留最终运行，未扩展删除到既有证据。

### 回归与交付

原迁移回归 **10/10，37.176 s**；优化模式回归 **3/3，62.091 s**，原身份拒绝、FK、构建授权和无输出约束保持。全仓离线检查 **37/37，47.5 s，jobs=6**；未加默认闸门或调整预算。操作入口见 `rl_exp/docs/diagnostic_artifacts.md`。

实现与回归提交 `9a83234`，仅含本轮六个代码/索引/测试文件；提交前手跑及实际 pre-commit 钩子均通过。验收记录、操作文档及事项指针另组同步，未带入其它会话的在办修改。

## 证据引用

- 最终运行的 `run.json`、`analysis.json`、轨迹 PNG、组合 GIF、`root_translation.png`；位置在上文，输出被 Git 忽略，本机保留。
- 本机 `rl_exp/out/runs/diagnostic-artifact-lifecycle/20261021-producer-proof/`：`lifecycle-red.log`、`lifecycle-green.log`、`terminal-next-red.log`、`real-cli-final.log`、`real-recovery.log`、`relocation.log`、`optimization.log`、`offline.log`、`interim-cleanup.json`、`precommit-code.log`、`commit-code.log` 和首/中/末帧 `qa-side.png` / `qa-top.png`。清理账保存被替代输出的逐文件摘要；它不是外部备份。
- 实现/复读入口：`rl_exp/tools/diagnose/artifact_run.py`、`local_path_view.py`、`artifact_paths.py`、`rl_exp/tools/verify/test_artifact_run.py`、`test_artifact_relocation.py`。

仓根使用配置解释器：

```text
<python> -B rl_exp/tools/diagnose/artifact_run.py --inspect_run rl_exp/out/runs/local-path-view/support-drive-root-20261021-final
<python> -B rl_exp/tools/verify/test_artifact_run.py
<python> -B rl_exp/tools/verify/test_artifact_run.py --real_run rl_exp/out/runs/local-path-view/support-drive-root-20261021-final
<python> -B rl_exp/tools/verify/test_artifact_relocation.py
<python> -B rl_exp/tools/verify/test_local_path_optimization.py
<python> -B rl_exp/tools/verify/offline_suite.py
```

## 未覆盖边界

仅试点入口具备本轮机制；`diagnose_support.py` 的另一输出根及其它活跃生产者仍须按阶段 2 接通，阶段 3 存量批次继续。默认事项由整理事项承接核对；新实验应显式填写真正的事项与执行者。索引锁协调本机制写者，不承诺与绕锁人工编辑形成数据库事务。

审计钩子证明实际 Python 文件读取隔离，不是操作系统权限沙箱。逐像素一致限定当前库版本和主机环境；源码摘要是磁盘绑定，不是不可变执行快照。恢复包及源码位置必须可读取且摘要匹配，普通 clone 或记录入 Git 不等于本机忽略产物已有异地备份。

本记录是执行证据，未冒充独立审核。事项保持 `in_progress`；阶段 1 及前次三项修复仍需不带执行历史的新上下文复核，完整入口推广、存量闭合和交接后才能交审关闭。
