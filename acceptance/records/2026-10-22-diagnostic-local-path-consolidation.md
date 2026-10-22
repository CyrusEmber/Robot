# 局部路径存量合并与复读入口生命周期

## 适用范围

事项：`work/active/diagnostic-artifact-lifecycle.md`。本批整理旧局部路径报告和回放图像，
并将 `local_path_check.py` 四模式接入既有 `ArtifactRun`。不修改资产、采样预算、几何阈值、
失败判词或物理配置，不启动 Kit/PhysX。

## 验收条件

- 固定原字节和依赖，保留仍被回归消费的样本，失败对照不升级为成功。
- 写前登记、同名真实 CLI 不改写、真实写后错误留下归属与现场。
- 同组真实反例修前失败、修后通过；四模式完整数值与原实现一致。
- 两档真实 Git 检出，代码和输入共同换根，阻断旧仓读取，错身份/摘要仍拒绝。
- 刷新 writer 与精确范围后删除旧副本；删后复验、仓库闸门及独立审核通过。

## 结果

### 入口推广与缺陷

暂还原修改后的同一真实验证命令，在 `real-red-final` 写出四分点报告后，因没有 `run.json`
失败；旧新 CLI 均支持该命令。早期 fixture KeyError 和一次新参数不兼容保留为调试日志，
不当作该缺陷红绿证明。最终四分点、镜像、组合、支持调度均实际运行并完成登记收尾；
同名真实 CLI 拒绝且原文件与索引不变，真实序列化报告写后注入错误保留报告和 `failed`。
四模式完整报告仅排除改变的 checker 自身执行摘要后与原实现相等，其余摘要、数值和判词均比较。

当前代码按原预算真实生成新绑定源，两腿完整环路；它不替代旧失败报告。
旧报告直接用当前 FK 原本就拒绝 `FK changed since collection`；历史恢复使用匹配的原代码。

完整当前生产恢复先遇到绑定 JSON 检出规范化；恢复包现保留所有绑定文件 `-text`，
归档代码快照按逻辑模块路径恢复。这是恢复包缺口，不计生产修复红绿。
随后真实旧仓隔离暴露旧物理目录未解析，新增可选 `original_absolute_locations`：显式列旧位置，
受原逐文件摘要约束，不凭 basename 或路径后缀放行。该缺陷有独立修前失败、修后通过。

独立审核再复现同路由父子别名相互遮蔽的 P2，已补 `alias-overlap-red.log` 修前失败，
构造时拒绝同路由不同别名的祖先关系；跨路由重叠检查保留。最终六项轻量回归通过，
覆盖四模式、实际生命周期边界、输入变化、完整代码身份/摘要和新别名拒错。

完整生产换根先将原逐字身份比较装回真实采集链，确认迁位误拒且无报告，再运行最终 CLI。
所有源码摘要仍核对；完整报告仅按原/新两个明确仓根的完整路径前缀归一化，
原样溯源路径及所有摘要也比较，不删除 `source_input_sha256_provenance_only`。
最终证据为 `real-final-v4/`；各版本执行源码按原摘要保留位置，不改旧摘要冒充当前源码。
最终 v4 两档各 60 个文件原始/blob/检出字节一致，真实支持调度 CLI 完整运行，
全报告相等、原比较误拒反例和同名无改写均通过；每档三个隔离探针拒绝，正常旧仓读取为零。
自己的临时源仓和检出副本已清理；报告无图像，不声明图像重建能力。

### 存量合并

固定七个根共 25 文件、21,957,982 字节，均未被 Git 跟踪。v3 仍被优化回归消费，
原字节另迁 `rl_exp/out/archive/palm-local-path/regression-input-20261015/`，兼容原逻辑身份。
所有历史报告和图像仍在 ZIP 中保留清单身份，不透明映射 ZIP。

`rl_exp/out/archive/palm-local-path/history-20261015.zip` 包含 25 原文件、39 检查点依赖、
修后接触源报告和精确历史 FK，共 66 路径、62 数据块、11,362,619 字节。
SHA256：`081236772189bd16fa02b3a4d79c31bc4075972711786bdeeb4f3c2fd945e728`。
去重不改原字节，v2/v3 同字节报告仍保留不同清单路径。

最终删前恢复两档各核 485 文件、157 历史路径，其中本包 66 路径。隔离 clone 内执行归档精确 FK
复读四份原报告，随后还原 clone 当前源码。原首轮两腿均零点后摆失败；v2/v3 和修前对照保留
lf 完整、rr 仅一点后失败，坏 build 摘要仍拒绝。可读或归档不使旧几何失败变为通过。
18 份原图共 662 帧可解码，恢复检查核原字节及恢复帧；不宣称当前渲染器重新生成了旧图。
真实 ZIP 破坏覆盖丢 FK、改 GIF 且重建有效 CRC、重复数据块及遗漏历史对照，均拒绝。

删除前再次核七个准确直接子目录的全部文件大小/SHA、无链接及无 Git 跟踪，
核 v3 保留副本与归档摘要、两档恢复及图像帧结果，CIM 未见选定根读写进程。
七个旧根已实际删除，25 文件均仍有原摘要覆盖；主索引在既有锁内定稿。
删前优化回归 3/3 通过（71.508 s），历史测试明确加载匹配 FK，坏身份及四档优化仍拒绝。
删后双档恢复再次成功：每档 485 文件、157 历史路径、本包 66 路径，原失败判词不变，
18 图/662 帧解码通过，正常旧仓 Python 读取为零。
删后入口回归 6/6（0.404 s）、共享运行 12/12（51.189 s）、迁移 16/16（76.300 s）、
优化拒错 3/3（55.920 s）全部通过，迁移还含两档独立重检出及 FK/授权破坏对照。
删后仓库闸门 37/37 通过（172.0 s，jobs=1），未调整预算。总事项继续 `in_progress`。

独立审核（`independent_artifact_review`，2026-10-22）：未参与实现或删除，曾用独占临时目录
真实复现同路由父子别名 P2；修复后重做原反例，构造立即拒绝，合法分离别名及相同别名去重仍可用。
另独立运行最终六项轻量回归（6/6，0.384 s），确认未靠遍历顺序放行。删除前后逐项核对原 25 文件
的大小和摘要，均由固定 ZIP 原字节覆盖；七个准确旧根已不存在，v3 保留副本实际映射和完整身份一致。

实查 v4 四模式完成记录及其精确源码快照，每份 41 输入/17 源码绑定有效；完整报告仅排除执行
checker 自身摘要后与原实现相同，写后失败现场仍为 `failed` 并保留实际报告。实读当前支持调度
双档 60 文件恢复的全报告比较、逐字身份误拒反例、零旧读和清理结果；比较保留全部溯源字段与摘要。
历史删前后双档 485/157/66 恢复及 18 图/662 帧解码日志、原四报告失败判词、四套回归、
最终 37/37 与提交前及事项检查均与记录一致。结论：本批入口推广、别名修复和准确范围合并删除通过，
未发现剩余 P1/P2。

审核未另行采集或重跑完整套件；历史图像验证是原字节恢复解码，当前生产报告没有图像，不能称重建旧图。
当前双档完整生产恢复只实跑支持调度，不外推其它模式或入口整链恢复；不声称原生全部 I/O 隔离、
Kit/PhysX、动力学或资产批准。本机产物及外部备份边界保留，总事项继续在办。

## 证据引用

本机根：`rl_exp/out/runs/diagnostic-artifact-lifecycle/20261022-local-path-consolidation/`。

- `inventory.json`：七个根、全部原文件、归档及 v3 位置。
- `check-before.py`、`current-before-*`、`real-red-final.log`：原实现与缺运行记录真实失败。
- `current-source/`、`real-final-v4/`、`comparison.json`：实际生产、执行源码和完整数值对照。
- `storage-alias-red.log`、`alias-overlap-red.log`、`producer-final-tests.log`：定位缺陷及最终回归。
- `producer-recovery*.log`：恢复缺口和最终完整换根；以最后成功日志为准。
- `recovery-predelete*`、`historical-image-readback.json`、`archive-damage.log`：历史恢复与破坏测试。
- `recovery-before-delete/`：最终删前双档恢复及恢复图像解码；`writer-before-delete.json`、`deletion.json`：刷新及准确删除事实。
- `producer-recovery-final-v4.log`：最终当前生产完整恢复；`recovery-after/`、`test_*-after.log`：删除后恢复和回归。
- `offline-after.log`、`work-docs.log`、`precommit.log`：仓库、事项格式与提交前检查。
- 操作说明：`rl_exp/docs/diagnostic_artifacts.md`。

```text
<python> -B rl_exp/tools/verify/test_local_path_output.py
<python> -B rl_exp/tools/verify/test_local_path_output.py --real_source <bound_source.json> --proof_dir rl_exp/out/runs/diagnostic-artifact-lifecycle/<new_proof>
<python> -B rl_exp/tools/verify/test_artifact_run.py --real_run <completed_local_path_check_run>
<python> -B rl_exp/tools/verify/test_artifact_relocation.py --archive rl_exp/out/archive/palm-spatial/history-20261014.zip --local_archive rl_exp/out/archive/palm-local-path/history-20261015.zip --proof_root rl_exp/out/runs/diagnostic-artifact-lifecycle/<new_local_recovery>
```

## 未覆盖边界

入口推广只覆盖 `local_path_check.py` 四模式；完整当前生产恢复实际运行支持调度，
其它入口不会自动获得生命周期管理，不外推所有模式跨机安装能力。
历史字节、匹配 FK 和几何复读不证明连续域、PD、承重或动力学。
归档、回归输入及运行仅本机保留，推送源码和索引不备份产物。
历史恢复需要归档和 Git 对象 `d243b9e`、匹配 Python/依赖；Python audit 不是原生全部 I/O 沙箱。
其它存量、入口推广、外部备份及底层 PhysX 故障继续在办，不关闭总事项。
