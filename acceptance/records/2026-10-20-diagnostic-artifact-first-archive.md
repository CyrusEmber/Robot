# 诊断产物逐包路由与首批实际归档

## 适用范围

用户选择“逐包归属＋首批可恢复归档”，不删除证据。对应 [诊断整理事项](../../work/active/diagnostic-artifact-lifecycle.md)。本轮只迁移两包自包含、明确作废但需留档的历史支撑诊断，不触碰候选检查点、几何路径或 runtime/驱动输入。

## 验收条件

- 迁移包须有明确历史保留依据、完整文件清单、原始摘要和固定生产源码；不得用日期、final 名称或无搜索命中代替判定。
- 旧路径无文件或链接时能实际读取归档，缺映射、错身份、路径逃逸、缺失/额外文件明确拒绝；历史 JSON 与判词不改写。
- 真实历史后处理消费者读存储统计，重现原 summary 全文；不得把下采样曲线冒称全频统计复算。
- 独立临时仓按归档布局实际 add/commit/clone/检出，两种 autocrlf 设置均保持绑定字节并成功运行恢复消费者。
- 存量路由不冒称分类闭合；未知在写状态及其它会话在办产物保持原位；归档不是外部备份。

## 结果

### 已搬移两包

| 原逻辑路径 | 当前落点 | 保留依据 |
|---|---|---|
| `rl_exp/tools/diagnose/out/smoke_p1c/` | `rl_exp/out/archive/lizard-v10-support/smoke_p1c/` | `rl_exp/versions/lizard/main/v10/DIAGNOSE.md:106-107` 明确旧口径作废、仅留档不入结论；保留早期失败对照 |
| `rl_exp/tools/diagnose/out/smoke_p1d/` | `rl_exp/out/archive/lizard-v10-support/smoke_p1d/` | 同一历史依据；生产源码与列 schema 不同，不冒称字节重复 |

实际 `Path.rename` 搬移两个目录，共 6 文件、666,642 bytes。搬前核精确文件集、原摘要、目标不存在、Git 未跟踪状态和固定生产源码；搬后逐文件摘要相同。旧目录实际不存在，没有 junction、symlink 或原位副本兜底。没有删除文件，释放空间为 0；固定生产源码另保留 2 文件。

迁移前进程快照只有本仓 MCP server 的 python，没有观察到诊断/Blender/Kit 生产进程；两包文件身份在搬前再核。此证据仅限两个冻结历史包，不宣称其它目录没有 writer。

### 映射与真实消费者

- `rl_exp/tools/diagnose/support_archive_index.json` 是 Git 内原逻辑根到新位置的两包映射及文件摘要。SHA256 `fa2ece0182f4cc9731a0535dea5d1634b56394ab1afec809431d8c4bd530c60d`。
- `rl_exp/tools/diagnose/archived_support_read.py` 只批准这两个逻辑根，强制固定生产 revision/source 摘要、精确文件集及存储根范围；校验是显式异常，不依赖 assert。索引是调用方批准路由，不是外部签名或对抗写权限攻击的机制。
- 消费者从实际历史 `main` 提取 Phase 1 摘要渲染 AST，执行真实列选择与字符串生成，结果全文等于原 `summary.md`。只消费已存储 50 Hz `stats`，不从 10 Hz `series_json` 推回原全频统计，不重新起仿真，不恢复作废测量的有效性。
- 固定源码原字节在 `rl_exp/out/archive/lizard-v10-support/metadata/`：p1c 对应 `d5ff5ce791262f7825fcb6836e2f6fe353b3a551`，p1d 对应 `29deefe0acf735b8af4359d221fb21a888734668`；其摘要由 reader 内 PINS 和映射共同固定。未执行历史源码 imports、仿真入口或完整 main。
- 本轮未接通 `local_path_view._load`、`palm_spatial_runtime.check_build` 的迁移定位；所有涉及该链的当前证据保持原位。这两个自包含历史包使用独立限定 reader，不外推到候选链。

### 恢复验证与拒错对照

`test_archived_support_read.py` 6/6 通过，真实材料回归含：

1. 旧根含宿主绝对路径访问均被拒，旧式直接读取失败；有映射的新 reader 对两种 schema 重现原摘要。
2. 未知/缺失/重复映射、schema 互换、错误摘要、生产 pin 错、源字节篡改、路径逃逸、文件集缺失或增加均拒绝。
3. 改 `series_json` 并刷新测试摘要不改变输出；改真实 `stats.drift_m` 并刷新摘要后渲染对照失败，证明不是只做 JSON/hash 读取。
4. 全部 6 证据文件、2 源码和测试索引在独立临时 Git 真实提交、clone，删除临时原 bundle 后以 `core.autocrlf=true/false` 检出并运行实际 reader 和 CLI；原真实证据未被删除。
5. 真实归档后再跑同一回归通过；普通、`-O`、`PYTHONOPTIMIZE=1/2` 下两个归档 CLI 均输出原摘要全文。测试 fixture 取源根据映射适配搬后位置，不依赖旧目录继续存在。

这是新增限定读法的旧路径失败/缺映射失败→恢复成功对照，不称修好了其它生产者的历史路径硬绑定。测试需要本机证据及 Git 历史，不是可无材料运行的 portable unit test；临时 Git 未关闭用户签名/钩子配置。

日志：`rl_exp/out/runs/diagnostic-artifact-lifecycle/20261020-preflight/archive-recovery-final.log`，SHA256 `a423393b8bae37fd002e79a58dc411c5ecd7a37b7c604c12bd61cd17e55ffca0`。完整仓库闸门 `ALL_OFFLINE_CHECKS_PASSED (37/37 in 53.2s, jobs=4)`；新增恢复回归按需运行，未新增默认套件条目。

### 存量逐包路由：只完成部分归属核定

`rl_exp/tools/diagnose/artifact_index.json` 覆盖观察时两根顶级条目，加上已归档逻辑根：170 条，10 当前依赖、16 历史对照、142 pending、2 容器。索引只留位置、类别、责任入口、保留理由、文档提及、报告 mode/status 与下一步，不复制结果数字或判词。报告顶层元信息已实际读取；文档提及不等于运行消费者，只有明确代码引用的条目标 direct_code_reference。

整理期间仍有其它会话新输出；后续新增未保证全部纳入。runs/archive 只登记为容器，子实验未逐个核定。因此不能称“逐包归属已全部完成”；142 个 pending 含未确定变体价值和未交接的 RF/视频/源码快照，全部保留原位。此路由表不是完整传递依赖清单，完整观察仍参照前轮 inventory 快照与其限制。

### 中断后恢复复核（2026-10-21）

前轮索引任务两次超时，改为有界生成后完成归档；执行停在提交收尾，尚未提交本批文件，不是归档/仿真进程仍在运行。恢复时只观察到 MCP server 的 python，未重新搬移或删除任何包。

恢复后重新核对两个旧根不存在、全部 6 文件绑定摘要相符、既有恢复日志摘要未变；同一真实恢复回归 6/6 通过，普通、`-O`、`PYTHONOPTIMIZE=1/2` 的实际归档 CLI 对两个包均重现原摘要。170 条路由无重复逻辑根，登记位置与文档指针存在；这是旧索引一致性检查，不保证后来新增条目已分类。事项/验收记录格式检查通过；完整仓库闸门再次 `ALL_OFFLINE_CHECKS_PASSED (37/37 in 48.3s, jobs=4)`。

恢复提交时 Git 报 `index.lock` 已存在；未观察到 Git/SSH/GPG 进程。经用户明确允许，再次查无相关进程后将锁原字节改名保存在 `.git/index.lock.preserved-20261021-100607529`，140,052 bytes，SHA256 `dfc4b6f1185e879f379a2175f51955154a4adf8e45e141985fccc8bf45251fca`；未删除锁内容、未重置或替换真实索引。此为提交阻塞处理，不改变归档材料或原实验结论。

### 独立审查

新上下文静态审核实际落点、索引、reader 和测试，未发现阻断本批交接的问题；确认不把归档当测量有效或全部事项完成。审查提醒测试材料本机依赖、可写目录检查/读取之间 TOCTOU、本机单副本及调用方批准路由的信任限制。本轮不新增锁/框架，仍需生产者停写再操作，不以 reader 当原子快照。审查中关于空 builtins 自动注入的推断不成立：代码已显式传入 `__builtins__={}`；真正执行边界是固定生产源码摘要，不以空 builtins 宣称安全沙箱。

## 证据引用

仓根执行：

```text
python -B rl_exp/tools/diagnose/archived_support_read.py --index rl_exp/tools/diagnose/support_archive_index.json --package rl_exp/tools/diagnose/out/smoke_p1c
python -B rl_exp/tools/diagnose/archived_support_read.py --index rl_exp/tools/diagnose/support_archive_index.json --package rl_exp/tools/diagnose/out/smoke_p1d
<配置解释器> -B rl_exp/tools/verify/test_archived_support_read.py
```

隔离恢复使用同一索引、保持相对归档布局复制完整 6 证据文件及 2 固定生产源码，传 `--storage_root <恢复根>`。原宿主路径和旧根不得作为恢复条件。

回退仅在原目录不存在、目标 3 文件集和摘要仍匹配、没有诊断 producer 写入时，把各目录原样 rename 回 `old_root`；不改文件内容、不创建 junction。回退同时撤销两条映射并更新路由位置/证据，同轮重验。目标冲突或摘要变化时停下，不覆盖任一侧。

## 未覆盖边界

- 两包及生产快照仍本机单副本、Git 忽略；映射入 Git 不代表材料可从云端恢复，未建立外部备份，不删除唯一证据。
- 其余大部分条目保留原位，逐包保留价值/责任交接/运行停止状态未核齐；不能用通配类别或记录路径存在替代验证。
- 活跃 local_path/runtime/导出输入的传递迁移定位仍未接通，未触碰 43 个已跟踪基准；其它实际输出根及新运行收尾机制仍待办。
- 本轮新增 reader 与必要回归限定两个历史包；没有改机器人构型、驱动参数、物理阈值，没有复验原专项结论。
- 整个事项保持 in_progress，本记录不是关闭审核。
