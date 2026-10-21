# 诊断迁移审核三项缺陷修复

## 适用范围

响应用户要求修复 `2026-10-21-diagnostic-artifact-review.md` 的 P1 隔离缺口、P2 drive 摘要和 P2 代码换根问题。落点为 `artifact_paths.py`、`local_path_view.py`、`palm_spatial_runtime.py` 和 `test_artifact_relocation.py`。保持原报告、资产、原身份和物理判据；不扩展为整个产物治理事项完成。

## 验收条件

- 隔离覆盖哈希实际使用的 `builtins.open`；先用旧根直接读取破坏对照证明有效，恢复子进程不得读取原仓代码或证据字节。
- drive 读取和摘要来自迁移后位置，保留逻辑身份并记录实际位置；旧根缺失、旧副本冲突均不影响绑定，真实 `_run` 写出的分析不得带空摘要。
- 代码、索引、证据和必要声明共同 Git 检出到新根，子进程运行新根真实消费者；保留完整逻辑身份、FK 摘要和检查点授权，不能按 basename 放行。
- 保存修前失败、修后通过，运行优化模式回归、自检及仓库闸门；独立复审和全事项关闭分开。

## 结果

### 修前行为

新增回归先在未修实现上执行：旧隔离未拦住真实 `sha256_file`，drive 绑定了注入的旧副本零摘要，真实 `_run` 与 JSON writer 在旧摘要读点不可用时写出 `None`。writer 测试仅替代绘图，解析、传递来源、速率、drive 和 JSON 写入走真实实现。

新根子进程初次因测试包缺 `assets.json` 失败，不计缺陷证明；补齐真实声明后，在未修实现上复现新根 `_load` 的 `FK changed since collection`。另一同 API 对照复现 `BUILD` 随代码换根后错误拒绝 `only checkpoint_v3/build.json is authorized`。没有用缺输入或不支持新参数冒称行为缺陷。

### 修复与范围

- **隔离**：父 fixture 同时拦 `Path.open`、`builtins.open`、`io.open`、`os.open`；恢复子进程在导入代码前安装 CPython `open` 审计钩子，拒绝原仓全部文件字节读取。探针覆盖 builtins、io、FileIO、os.open、真实哈希及含 `..` 的同一路径别名。拒绝用 AssertionError，不能被 hash helper 的 OSError 出口吞成空摘要。这是实际 Python 读取通道的证明，不称操作系统权限沙箱。
- **drive**：逻辑 `path` 与实际 `location` 分开，读取和摘要均取 location，摘要不可为空。`drive_report` 保留原身份，新增 `drive_report_location` 记录读点。缺旧副本、冲突旧摘要和 `_run` 写盘均核到原摘要 `36344c8af1ccf56552c931d252008fb50a9b6951265e8fe083f2079bd340d115`。
- **身份**：仅当显式迁移项的原绝对根精确对应完整逻辑后缀时，导出旧仓根别名；与当前存储根共同按完整仓库相对路径比较。未知根仍用绝对身份，不按 basename 或任意后缀回退。FK 必须唯一匹配原身份且摘要相等；runtime 保留原具名逻辑检查点、38 文件覆盖和原 URDF/Blend pin。

### 验证

最终迁移回归 **10/10 通过（33.437 s）**。`core.autocrlf=true/false` 均真实 add/commit/clone，逐文件核证据原始/blob/检出字节后移除临时 source 仓。新根 `-I -B` 子进程排除原仓导入路径，确认 view、runtime、FK、路径解析器、包与哈希模块来自 clone，再运行 `_load`、`check_build`。两档各六种破坏探针被拒绝，正常消费者旧仓读取尝试均为 **0**；改坏 FK 字节、同名文件放到其它相对路径、伪造构建路径均拒绝。

原优化模式回归 **3/3 通过（57.207 s）**，普通、`-O`、`PYTHONOPTIMIZE=1/2` 的支持/拒绝范围保持不变；view 与 runtime 原有 self_check 通过。全仓 **37/37 通过（53.1 s，jobs=4）**，本次路径 `git diff --check` 通过；未增加默认闸门或改变预算。此记录不充当独立复审通过证明。

实现与回归提交 `3a735ea`，只含本轮四个文件，实际 pre-commit 钩子通过，日志为 `precommit-code.log`；本记录与事项证据指针同次提交，未纳入其它会话的改动。

## 证据引用

- 原审核：`2026-10-21-diagnostic-artifact-review.md`；原实施：`2026-10-21-diagnostic-artifact-decoupling-cleanup.md`。历史记录不改写为已覆盖本轮反例。
- 本机目录 `rl_exp/out/runs/diagnostic-artifact-lifecycle/20261021-review-fixes/`：`red.log`、`code-root-red.log`、`runtime-root-red.log`、`drive-run-red.log`、`green.log`、`green-final.log`、`optimization.log` 及后续检查日志。`code-root-red.log` 是补齐输入后的真正换根缺陷对照。
- fixture 仅在 TemporaryDirectory 中复制、改坏和恢复，既有诊断材料只读；日志本机保留，实现和本记录进入 Git。

仓根使用配置解释器复读：

```text
<python> -B rl_exp/tools/verify/test_artifact_relocation.py
<python> -B rl_exp/tools/verify/test_local_path_optimization.py
<python> -B rl_exp/tools/diagnose/local_path_view.py --self_check
<python> -B rl_exp/tools/diagnose/palm_spatial_runtime.py --self_check
<python> -B rl_exp/tools/verify/offline_suite.py --jobs 4
```

## 未覆盖边界

换根证明限定本轮路径/授权消费者和必要依赖，不等于全部采集器、USD 运行时或跨操作系统复现完成。`_run` 回归替代绘图，不冒称真实图像/动画验收；真实 CLI 的完整生产收尾试点仍按事项下一阶段推进。未起仿真、训练或修改其它会话在办文件。整个事项保持 `in_progress`，本轮三项修复待独立复审，其余生产治理、存量处置及外部备份动作继续保留。
