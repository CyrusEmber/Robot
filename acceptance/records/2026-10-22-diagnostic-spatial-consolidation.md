# 空间探针旧混合目录的合并、迁移与删除

## 适用范围

事项：`work/active/diagnostic-artifact-lifecycle.md`。本批处置
`rl_exp/out/lizard2_palm_spatial_20261014/`：当前 `checkpoint_v3/` 输入保留原位，
三个已跟踪对照文件迁入 `rl_exp/tools/diagnose/baselines/palm-spatial-20261014/`，
其余历史子树合并进 `rl_exp/out/archive/palm-spatial/history-20261014.zip`。
复用既有索引、ArtifactPaths 和迁移验证器，未增加依赖、位置库或默认闸门。

## 验收条件

- 删除前刷新文件集合、大小、摘要、Git 状态及 writer；明确绝对删除范围，无链接穿透。
- 基准原字节迁移，目标 attributes 保住 Git blob 和检出字节；原身份经既有映射保留。
- 归档完整覆盖拟删文件和实际重放依赖；代码、索引、输入及证据共同换根。
- 真实 add/commit/clone 覆盖两档 autocrlf，旧仓不可读时运行真实 CLI 和授权检查。
  隔离破坏对照、缺映射、错摘要及未授权同名文件须拒绝。
- 删除后再次恢复，保留正反例原判词；相关回归、仓库检查和独立审核通过。

## 结果

初始根有 134 文件、27,935,178 字节，其中 43 文件受 Git 跟踪。
执行前全量逐文件校验未变；CIM 快照仅见 MCP Python 服务，未见选定根的写入命令或
运行中的 Blender/Kit。进程快照不是全系统写锁。本轮删除逐项解析路径、限定父目录，
拒绝 reparse point，并在每次删除后落盘记录。

已实际删除 11 个旧目录：`candidate_v1`、`checkpoint_candidate`、`checkpoint_locked`、
`checkpoint_probe`、`checkpoint_v2`、`closeout_locked`、`closeout_probe_before`、
`probe_v1`、`probe_v2`、`checkpoint_v3_probe`、`checkpoint_v3_locked`。
原根现仅有 `checkpoint_v3/` 的 39 个当前输入及根 attributes，共 40 文件、7,853,251 字节。

两个 v3 对照目录的三文件迁到基准目录 `probe/` 与 `locked/`，与原文件及 Git HEAD 字节相同。
新基准 attributes 保留历史 CRLF 字节，旧根移除两条失效规则；索引保留原逻辑身份和逐文件摘要。
不改原报告的路径字符串、代码身份和判词，不升级为资产批准。

其余九目录的 91 文件、19,504,582 字节合并进单一 ZIP；额外保存重放所需的 39 个源输入，
共 130 个清单路径、52 个唯一摘要数据块，压缩后 3,400,931 字节。
SHA256：`870a4949aad78dc152e0a93965e58fe8de966a78b48a326549a04dd53f7c10fe`。
ZIP 使用 `manifest.json` 和 `blobs/<sha256>`；额外源输入原件未列入删除范围。
恢复后为独立文件，不共享可写副本。

最终合并验证实现删除前、后均完成两档真实 Git 恢复；每档逐文件核对 428 文件的原始、
blob、检出字节，归档全部 130 路径恢复。临时源仓在子进程复读前删除。
子进程从新根导入代码，导入前安装旧仓 `open` 审计钩子；`builtins.open`、`io.open`、
`os.open` 和实际 `sha256_file` 的旧根破坏对照均被拦截。
读取两份迁移基准，实际 `runtime.check_build(runtime.BUILD)` 通过，同名/异名未授权 build 拒绝；
破坏基准摘要拒绝，去掉映射后旧根读取被拦截，正常复读无非预期旧仓读取。

生产 CLI 对归档 v2 build 重跑正例与锁轴反例，完整报告仅排除执行 `probe_sha256` 后一致；
正例完成记录通过检查，锁轴反例保持 `REGRESSION_REJECTED`、失败记录和原报告。

既有迁移回归初次出现三项 `FK changed since collection`：历史报告绑定 FK 摘要
`3425518c66192b60fad9edc44a586adf8b7b2dedcf9f73d27d792e9b6d8d7bf6`，
当前实现已在 `5891f67` 修改。测试夹具从已提交的 `d243b9e` 恢复并校验原 FK 字节，
在临时根真实导入，Git 恢复包同样使用原字节；未修改生产 FK、历史报告或放宽绑定。
首轮修正后检出父进程仍指向临时源文件，剩一项身份拒绝；改为指向 clone 中相同字节后，
最终默认迁移回归 **10/10 通过（43.721 s）**。独立新根子进程仍真实导入该 FK，
两档各六种隔离探针被拦截，错 FK 字节与同名异族文件均拒绝，正常旧仓读取为零。
仓库离线闸门 **37/37 通过（51.4 s）**，暂存后的 `hooks/pre-commit` 通过。
最终脚本另经 `recovery-final/` 两档归档恢复，退出 0；与前后恢复相同的几何正反例通过。
最终恢复时跟踪源码集合已新增一个并行事项的文件，两档分别核对 429 文件，归档路径仍为 130；
该文件只进入临时验证包，不属于本批提交或删除范围。

独立审核（`independent_artifact_review`，2026-10-22）：未参与本批实现或删除，实查删除前全部
134 文件与固定清单一致，ZIP 的 130 路径、52 个数据块与原件逐项同摘要同大小，无多余或重复成员；
三份迁移基准同时与原目录及 Git HEAD 原字节一致。删除后实查 11 目录不存在，94 个消失文件逐项
由归档或基准副本覆盖；当前 39 个输入摘要未变，原根仅余这些文件及获授权精简的 attributes。
主索引从三个旧基准路径真实解析、校验并读回新副本，未发现归档遗漏或缺映射绕行。

复核最终验证源码及删除前、删除后、最终两档恢复日志，实查历史 FK 原字节与报告绑定摘要相同，
夹具真实导入与新根子进程校验仍拒绝错摘要及同名异族源码，未修改历史绑定或放宽生产身份校验。
最终 429 文件恢复、默认 10/10、离线 37/37 及提交前闸门结果与日志一致。结论：本批合并、基准迁移
和明确范围删除通过，未发现剩余 P1/P2。审核只读核验实际文件与日志，未另行重采；不把本机 ZIP
视为外部备份，不声称 v1 全部报告已重放、其它当前输入消费者已迁移或物理能力已通过，总事项继续在办。

## 证据引用

本机证据根：`rl_exp/out/runs/diagnostic-artifact-lifecycle/20261022-spatial-consolidation/`。

- `inventory.json`、`prepared.json`：固定范围、初始摘要和跟踪状态、归档身份。
- `deletion.json`：实际删除的绝对路径、剩余文件数和归档摘要。
- `recovery-predelete/`、`recovery-after/`：各自的 `checks.json`、`child-true.log`、`child-false.log`。
- `recovery-final/`：包含历史 FK 夹具修正的最终脚本，两档恢复汇总与真实 CLI 子进程日志。
- `relocation-tests.log`、`relocation-tests-fixed.log`、`relocation-tests-final.log`：历史 FK 夹具修正前后对照。
- `offline.log`、`precommit.log`：仓库离线闸门与暂存后提交前检查。
- 操作入口：`rl_exp/docs/diagnostic_artifacts.md`；路由：`rl_exp/tools/diagnose/artifact_index.json`。

```text
<python> -B rl_exp/tools/verify/test_artifact_relocation.py --archive rl_exp/out/archive/palm-spatial/history-20261014.zip --proof_root rl_exp/out/runs/diagnostic-artifact-lifecycle/<new_recovery>
<python> -B rl_exp/tools/verify/test_artifact_relocation.py
```

## 未覆盖边界

ZIP 和运行证明为本机保留、被 Git 忽略，未建立外部备份；索引、验证器、记录入仓不等于
归档随 Git 检出。异机须先取得同摘要 ZIP。它不是透明位置映射，须按清单显式恢复。
默认迁移回归还需本机 CONTACT 等原始样本及 Git 可读取 `d243b9e` 的绑定 FK 历史源码；
浅克隆缺该对象会明确失败，不能仅凭当前代码检出直接复跑；这是默认回归的前提，区别于上述 `--archive` 恢复入口。

本批实跑 v2 几何正反例和当前 build 授权检查；早期 v1 报告及其绝对网格路径按原字节保存，
未重算该代报告。字节保存不代表每份早期报告都重放通过。不覆盖 Kit、PhysX、整机仿真或资产批准。

当前 `checkpoint_v3/` 仍被 `check_export`、运行时准备及通用 body precheck 直接消费；
下一批须先接通这些实际消费者并验证完整入口，再迁移当前输入，不能由 `check_build` 单项通过外推。
其余混合目录、生产入口推广、外部备份及原生复制故障继续由原事项承接，事项保持 `in_progress`。
