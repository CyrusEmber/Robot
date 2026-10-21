# 诊断读取解耦、活跃依赖迁移与开发散文件清理

## 适用范围

用户明确纠正此前“不删除、不搬活跃链”的保守执行范围，要求该解耦、合并、重构、删除的实际完成。本轮处理局部路径读取链和输出根的开发散文件；对应 `work/active/diagnostic-artifact-lifecycle.md`。不改机器人、PD、物理阈值或原判词。

## 验收条件

- 历史身份与原报告字节不改写；实际读取通过原身份定位新存储，错摘要、漏映射和路径逃逸拒绝，不借旧根或链接通过。
- 活跃报告实际迁移，原根不存在时真实消费者及传递来源读取成立；授权仍限定原具名检查点，不因搬迁接受其它构建。
- 重复审计逻辑收敛为参数化工具，用同一批真实样本逐字段对照原审计；一次性开发材料合并后实际删除散文件，删除前实际恢复核验。
- 运行仓库闸门；本轮处置和未完范围分开，不把局部完成当全项目关闭。

## 结果

### 实际落点

`artifact_paths.py` 直接消费已有 `artifact_index.json` 中显式迁移条目，不另建位置数据库。映射保留原绝对身份、原逻辑根、新存储根和每文件摘要；新位置缺文件或摘要不符立即拒绝，不回退旧副本。目标拒绝越界、symlink/reparse point、重复或嵌套路由。它是可信本地路由，不是新的资产批准来源。

`local_path_view._load`、分析所需来源/构建/drive 读点，以及 check/contact 的来源定位接通该读法。`palm_spatial_runtime.check_build` 先将位置还原为原身份再检查原检查点授权，随后读取迁移字节。其它运行时准备、采集和资产消费者尚未全接通，因此本轮没有搬检查点资产树。

实际将 `rl_exp/out/lizard2_palm_local_path_contact_20261015/report.json` 移至 `rl_exp/out/runs/palm-local-path/contact-20261015/report.json`，原目录已不存在，没有 junction。SHA256 保持 `f0671a53a8d5b97c40844f6ea771b655bdd3bf8d5ab98ef64b02a1a7550a34c8`。原报告、组合报告、支持相位报告和接触交付报告通过真实 `_load` 读取；后三者原有 `source_report` 字符串未改写，实际来源通过新映射读取。

支持相位的真实 `_rate_prerequisites` 也从已迁移来源复读，20 关节的完整返回对象与原 final 分析 `time_mapping_prerequisites` 逐字段相等；日志为 `transitive-rates.json`。这验证了传递分析读点，不宣称重新验证碰撞或物理时间映射。

### 工具合并与删除

四份审计脚本的共同样本算术和独立 actor FK 收敛到 `self_weight_audit.py --report ... [--output FRESH.json]`，不再依赖输出根的候选源码副本。真实 loaded_axes、gain20、knee30、calibrated 四批分别复读 17/8/1/30 个单轴 case、57800/27200/3400/102000 步；输出与原 `audit.json` **逐字段完全相等**。审计一致为真不代表原物理判词通过。新入口仅承担共同样本复核，各变体增益公式、准备和写前拒错的历史源脚本单独留在合并包，不冒称新工具验证了这些不同职责。

输出根的 46 个 `.py`、`.diff`、`.py.txt`、临时 `.index` 散文件已删除。其中 8 个实际内容以 `DIRC` 开头的开发暂存 Git index 已彻底丢弃，共 1,123,388 bytes；它们不是运行输入或诊断 evidence_index，不把这些临时暂存状态永久归档。其余 38 份历史源码/补丁合并为单一 `rl_exp/out/archive/diagnostic-development/tracking-scratch-20261021.zip`。

按内容摘要存唯一 blob，内置 manifest 记录每个原相对路径、大小与摘要；初批 46 份曾在临时目录恢复校验后才删除散文件，去掉临时 Git index 的终版包又对全部 38 份逐文件实际恢复核验。原散文件共 1,959,351 bytes；保留历史源原始 835,963 bytes，最终压缩包 228,188 bytes，SHA256 `4d8157208fa5628738415a1f4bf99ba73c84c7e003044ab4060a485407ee5d58`。这是开发散文件收拢，不代表全部诊断输出空间或全部目录已整理完。

删除前进程快照仅见 MCP server 的 Python，未观察到诊断/Blender/Kit writer；这不是锁或并发写入绝对保证。未改共享工作树中其它会话的 dirty 源文件或其验收记录，未触碰真实 `.git/index` 或 Git objects。

### 行为证明与检查

同一旧 API 的迁移回归在改消费者前失败，两个真实消费者分别命中 `OLD_EVIDENCE_READ`；不是仅以新增参数不被旧函数接受作为修前证明。修复后通过；实际搬移后再次通过。测试把报告和完整检查点复制到新存储，禁止旧证据根及其 resolved alias 的读取，覆盖原/新位置授权、错摘要、缺映射、未绑定文件和路由逃逸。测试依赖本机原材料，不是可凭 Git 检出独立获得的最小样本。

- 最终迁移回归 6/6 通过。真实 39 个证据文件在目标布局执行 Git add/commit/clone，`core.autocrlf=true/false` 两档的原始、blob 和检出字节逐文件相等；移除临时 source 仓后，旧证据根拒读状态下真实 `_load` 与 `check_build` 仍通过。执行代码仍取当前工具树，不据此声称全部源码/其它消费者已可跨机重建。
- `test_local_path_optimization.py` 3 项通过，覆盖普通、`-O`、`PYTHONOPTIMIZE=1/2`；解耦初版提前将原坏 build 的 AssertionError 变为 ValueError，导致旧调用方的 8 个场景失败，已恢复旧拒错语义并跑同一回归通过。映射本身的摘要/路径拒绝使用显式异常，不依赖 assert。
- 合并审计最终重新核四批输出与原审计完全相等；篡改一帧目标后实际算术拒绝，`-O`、`PYTHONOPTIMIZE=1/2` 在写输出前拒绝。view/check/contact 和 runtime 原有 self_check 通过。未以格式存在代替这些行为检查。
- 首次全仓检查因活跃 work 总量 `180326/180000` 超限失败；只精简本项重复说明，未取消/关闭待办或抬预算。最终 `ALL_OFFLINE_CHECKS_PASSED (37/37 in 57.5s, jobs=4)`，新增迁移回归为按需入口，未增默认闸门。
- 代码与路由提交 `b5e35f6`，仅含本轮 8 个文件；实际 pre-commit 钩子通过。最终包导入和正常 build 检查通过，未将其它会话的 dirty 文件收入本轮提交。事项和本记录同次提交，保留全事项在办状态。

## 证据引用

本轮本机运行目录：`rl_exp/out/runs/diagnostic-artifact-lifecycle/20261021-retention-continuation/`。包含只读 `inventory.json`、`relocation-red-behavior.log`、`relocation-green.log`、`relocation-after-move.log`、`relocation-commit.log`、`optimization-final.log`、`active-contact-migration.json`、`scratch-consolidation.json`、`scratch-finalization.json`、四份 `audit-*.json/log`、`audit-final-verification.json` 及 `offline-final.log`。归档现状以 finalization 为准，consolidation 中的初批包摘要不再代表终版。

初始盘点看到两根 3231 文件、2,567,185,843 bytes、43 tracked、227 顶级包；`rl_exp/out` 扫描期间 10 处发生变化，其边界为 unknown，不能用作迁移原子快照。实际迁移/删除另按本批精确文件集与重新实算摘要决定，未按旧盘点猜测。该次扫描的 unresolved 审计有截断，词法无引用不能单独支持删除。

仓根用配置解释器复读（输出必须用新路径）：

```text
<python> -B rl_exp/tools/verify/test_artifact_relocation.py
<python> -B rl_exp/tools/verify/test_local_path_optimization.py
<python> -B rl_exp/tools/diagnose/self_weight_audit.py --report rl_exp/out/lizard2_b_calibrated_20261021/report.json --output <新审计.json>
<python> -B rl_exp/tools/verify/offline_suite.py --jobs 4
```

历史包的 manifest 可由标准库 `zipfile.ZipFile` 直接读取；其 `files[原仓库相对路径].sha256` 对应 ZIP 内 `blobs/<sha256>`。恢复时由新临时根拼接 manifest 原相对路径，写入 blob 并用 `runrecord.binding.sha256_file` 对照，再查看历史源码；不要直接在当前仓根还原或运行已替代的一次性写文档/改源码脚本。

## 未覆盖边界

这轮已经迁移活跃依赖并实际清理散文件；其余混合子树、旧重复导出、过期盘点快照、全部生产者运行收尾和外部备份仍需继续。检查点迁移目前只验证真实 `check_build` 与路径读取，完整运行时准备及其它资产消费者仍有直接路径读点，不能立即搬整个资产树。整理期间其它实验继续新增组合试验脚本与报告，未把这些后来产物冒称已在本批删除或核定。压缩包仍是本机保留材料，不冒称外部备份。未启动物理/训练、未更新原专项结论，也未进入整个事项的独立关闭审核。
