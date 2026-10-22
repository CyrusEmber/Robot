# 诊断生产试点修复与 support 窄推广独立复核

## 适用范围

承接 `2026-10-22-diagnostic-producer-review.md` 的独立 P2，不改写原不通过结论。本上下文没有修改实现、测试或 work，按父上下文明确授权复核最终共享检查器、两个输出根，以及 `diagnose_support.py` 接入生产生命周期的窄切片。过程中只读主仓和保留产物；破坏仅在临时复制品或进程内。

最终复核对象为当前 `artifact_run.py`、`diagnose_support.py` 及相应测试；逐文件摘要保存在本次 `final-content-source.log`。共享模块最终摘要为 `48f8b4642d20f047926478880550d662f4704c2bc3e1be71e682fd791008d041`，support 最终摘要为 `dda4b9cb7915468973487e9747bba3fb1059a0ad608ed79be82263eb3b586049`。最终 view 证据取 `support-drive-root-20261022-final`，不是较早的 `review-fix` 中间运行。

## 验收条件

- 原空输入/代码绑定反例及单侧擦除必须拒绝；归属、命令、绑定身份/位置/摘要及必需输出列表不能被擦除后仍通过。有效空参数值必须保留，空命令或非字符串参数仍拒绝。
- 仅开放既有两个诊断输出根的子目录；独占、写前归属/登记、失败留存和只读检查保持。
- 最终 view 同带 drive/root_translation，由定版源码作完整 Git 换根、旧仓读取隔离、真实 CLI 及逐帧再生成核验。
- support 的真实 main/JSON writer/summary、资源关闭及特有失败有回归；真实仿真 CLI 完成一次有内容的创建和收尾，同名 CLI 拒绝且原文件与索引不变。失败现场不能借已有报告冒充成功。
- 明确试点及本轮 support 工况边界；不以局部推广或本记录存在替代总事项其它阶段。

## 结果

**原 P2 修复通过；阶段 1 的最终 view 证据复核通过；support 在显式平地单环境 Phase 0/1 的窄推广通过。本次范围内没有待修的 P1/P2；总事项仍不能关闭。**

### 共享检查器与原反例

审查确认创建和检查共用 `_validate_metadata`：输入和代码分别非空，绑定行须有身份、位置及 64 位小写摘要，归属和复跑命令、非空且安全的必需输出列表都显式检查。

在最终真实 view 运行的临时复制品上独立做 **15 项擦除**：输入空、代码空、双空，主题/事项/执行者/命令/保留理由/输出列表擦除，以及输入和代码首行各自的 identity/location/sha256 擦除，全部拒绝；原有效复制品通过。两个输出根子目录可创建；根本身及其它目录拒绝。复制品自动清理，未改原清单。

最后的命令验证窄修订保留 `--heights` 后的合法空字符串；独立核 `[]`、空或空白首命令、非字符串后续参数均拒绝，三种空绑定仍拒绝。最终生命周期回归独立运行 **12/12 通过，43.526 s**。原修前新增测试确有 `bindings-red.log` 的失败，不以修后绿色代替覆盖证明。

### 最终 view 的完整恢复

`rl_exp/out/runs/local-path-view/support-drive-root-20261022-final/` 已 completed；绑定最终共享模块。独立运行 `test_artifact_run.py --real_run`，两档 `core.autocrlf=true/false` 各 **60 文件**真实 add/commit/clone，原始/blob/检出字节一致；移除 source 后由新根代码完整生成八份产物。同名真实 CLI 拒绝且文件和索引不变；每档三个旧仓读取破坏探针被拒绝，正常旧仓读取为零。

全部 PNG 和两份各 109 帧 GIF 像素相等，四项关键分析一致，drive 摘要均为 `36344c8af1ccf56552c931d252008fb50a9b6951265e8fe083f2079bd340d115`；自己的恢复临时根已清理。另将最终所有图像帧及根平移/根前置/时间前置/各腿分析，与本上下文此前亲自审图的 `support-drive-root-20261021-final` 比较，全部一致。此前原三项迁移修复的独立通过结论不变。

### support 的实际生产与失败

审查 `main` 到 `ArtifactRun`、`_run_session` 和 `ExitStack` 的实际接线：写报告前登记，环境建立后注册 close 回调，summary 失败仍关闭环境并记录现场；Phase 0 提前返回也收尾。最终 support 回归独立运行 **15/15 通过，5.401 s**，覆盖真实 JSON/summary writer、同名真实写入路径、部分失败、登记失败、summary 失败、动态模块来源、原生退出码、空高度和平地/Phase 3 边界。

两处真实运行暴露的问题已修并核验：

- 动态模块的相对伪 `__file__` 曾被解析为 `E:/Robot/_classes.py`。最终只将绝对仓内源码列入集合，真实绝对仓内文件缺失仍拒绝。独立用真实 `torch.classes` 对象登记到临时 `sys.modules` 后运行生产 main：有过滤时 completed；仅在内存移除该行则复现 unreadable artifact。没有通过跳过全部不可读真实源码来放行。
- Kit 原生 close 可能以零退出掩盖 Python 异常；最终 `_run_cli` 先输出异常，再传失败 exit_code。GBK 控制台又曾在 summary 写完后打印 `²` 时失败。独立以真实 GBK 文本流和临时生产 main 复现 UnicodeEncodeError 及 failed+四产物；经最终 CLI 的 UTF-8 重配置后 completed+四产物、close(exit_code=0)。无需依赖未写进命令的解释器编码开关。保留失败退出码的回归通过。

最终真实运行是 `rl_exp/tools/diagnose/out/runs/support/lifecycle-v3-flat-utf8-20261022/`。独立检查 **49 项输入、23 项代码、四份产物**；保存了外部 checkpoint、目标资产/源配置、有效配置快照和含 `--heights ""` 的复跑命令。报告实际包含 Phase 0 测量/零动作对照、两个 Phase 1 case 及 summary；两个 case 的 16 类原始时序各有 **50/100** 个样本，非仅文件名占位。检查返回 completed，五个文件和索引在检查前后字节一致。

执行者真实同名 CLI 的 `support-repeat-cli.log` 有 `FileExistsError`；`support-repeat-proof.json` 记录 exit 1、五文件摘要/文件数不变及 index 不变。独立读核该证据，并再次核保留运行的实际内容和绑定；未另起并发 Kit。

真实失败现场原样保留：`lifecycle-v3-flat-20261022` 在 GBK 打印失败后为 failed+四份产物；`lifecycle-v3-20261022` 在多环境 PhysX 初始化原生崩溃后为 running。二者均有 owner/next，独立只读检查分别拒绝 failed/running，前后字节不变。已有完整报告没有被当作成功。

## 证据引用

- 原独立不通过记录：`acceptance/records/2026-10-22-diagnostic-producer-review.md`；事项 `work/active/diagnostic-artifact-lifecycle.md` 阶段 1/2 和关闭条件。
- 本机独占目录：`rl_exp/out/runs/diagnostic-artifact-lifecycle/20261022-independent-review-followup/`。
  - `manifest-roots-final.log`：最终真实复制品的 15 项擦除与根边界；`empty-argv-final.log`：合法空值及非法命令/空绑定；`lifecycle-final.log`：最终 12 项回归。
  - `real-recovery-final.log`：最终源码两档完整 Git 恢复和清理；`final-content-source.log`：全部图像/关键分析与人工审图参考的一致性及最终源码摘要。
  - `support-final.log`：最终 15 项回归；`support-real-inspect.log`：实际成功及两种失败现场的内容/绑定/只读核验。
  - `torch-origin-red-green.log`：真实动态对象的内存破坏对照；`gbk-main.log`、`utf8-cli.log`：真实 GBK 文本流修前失败/修后完成。较早 `real-recovery.log`、`manifest-roots.log` 只属中间源码，本记录以 `*-final.log` 为最终依据。
- 执行者本机目录 `rl_exp/out/runs/diagnostic-artifact-lifecycle/20261022-support-producer/`：`bindings-red.log`、`virtual-source-red.log`、`flat-only-red.log`、`empty-argv-red.log`、`stdio-red.log`；`support-flat-utf8-cli.log`、`support-repeat-cli.log`、`support-repeat-proof.json`；真实失败日志 `support-cli-final.log`、`support-flat-final-cli.log`。已读其全仓 `offline.log` 为 37/37，通过结果属于执行者该次基线，不冒称本上下文另跑全仓。

最终复读入口：

```powershell
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/verify/test_artifact_run.py
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/verify/test_diagnose_support_output.py
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/verify/test_artifact_run.py --real_run rl_exp/out/runs/local-path-view/support-drive-root-20261022-final
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/diagnose/artifact_run.py --inspect_run rl_exp/tools/diagnose/out/runs/support/lifecycle-v3-flat-utf8-20261022
```

## 未覆盖边界

support 正常真实运行只覆盖显式空 heights 的单环境平地 Phase 0/1。多环境台阶的原生 PhysX 崩溃尚未解决，Phase 2/3 正常仿真本轮未验证；不能将平地成功外推为默认多环境配置、全部支持能力或物理批准。空高度的 Phase 3 显式拒绝，不用零个台阶冒充验证。

support checkpoint 位于本机 `E:/IsaacLab/logs/...`，保留了绝对位置与摘要；未做 support 整套仿真跨机/Git 恢复，不能以 view 的恢复证明代替。运行、失败现场和审核日志是本机证据，入仓的索引和记录不是异地备份。磁盘绑定不是不可变执行快照；审计钩子不是 OS 沙箱。

此次仅证明阶段 1 和一个已继续使用入口的窄接入。其它入口清单、推广、存量截点/差异处置、外部备份、维护交接及总事项关闭审核仍按原 work 推进。本上下文不改 work 指针、不提交；记录和指针须由执行者同次提交。后续源码、索引或证据改变需按实际影响复核，不能用本记录抹除原审核发现或替代未来审核。
