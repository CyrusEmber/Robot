# 空间检查点当前输入迁出旧混合根

## 适用范围

事项：`work/active/diagnostic-artifact-lifecycle.md`。承接上一批历史子树合并删除，
将剩余 `rl_exp/out/lizard2_palm_spatial_20261014/checkpoint_v3/` 原字节迁入既有诊断基准的
`rl_exp/tools/diagnose/baselines/palm-spatial-20261014/checkpoint/`。
保持原逻辑身份、报告、SHA 绑定和授权范围，接通实际消费者后移除旧根。
此批不改机器人、配方、几何判据、物理参数，不批准新资产或开始训练。

## 验收条件

- 固定原根清单和 Git 字节，检查 writer 与绝对删除范围；目标 attributes 不改变原字节。
- 导出校验、运行时输入复制、注册准备、几何与通用预检实际读点走既有映射，错身份、错摘要拒绝。
- 先保留修前真实失败，再用同一反例验证修后；配置、源报告及传递输入共同恢复。
- 两档 autocrlf 真实 add/commit/clone，移除临时源仓，新根代码和真实 Blender 不能借原仓读取通过。
- 保留完整机体预检原判词和几何正反例；删除旧根后再恢复，相关回归和仓库检查通过。

## 结果

固定截点为上一批后剩余 40 个跟踪文件：39 个检查点输入，共 7,853,087 字节，及根 attributes。
新基准下继承已有 `** -text` 属性。原 build、Blend、URDF、36 个网格的字节不变；
索引新增准确到 39 文件的子根映射，不给旧父目录添加重叠映射。

修前新回归三项真实失败：`check_export` 和运行时复制准备的 `builtins.open` 哈希读取被旧根隔离阻断；
通用机体预检无法读取批准输入，完整报告与原结果不同。修后同三项通过，默认回归 13/13 通过。
生产修复只解析物理位置：导出仍需独立报告/URDF 批准，保留完整源身份与结构比较；
所有实际 BUILD 哈希、复制、XML/FK 读取使用映射位置，公开 BUILD 常量保留原逻辑路径。
通用预检绑定输入、源 JSON 和源内候选路径使用同一定位能力，批准摘要与实际 URDF 对应仍核对。

原机体预检本身为 `fail`，10 个案例、1530 次实体对检查；碰撞失败、角色证据与完整源姿态缺证均保留。
换根比较仅排除执行代码摘要，并将物理路径还原为逻辑身份；不删除数值、判词、覆盖或失败原因。
迁移验证通过不能称机体预检通过。

完整恢复曾依次因缺冻结配方 YAML、声明母机体、注册输入 URDF 引用网格而失败。
这些失败只说明恢复包不完整，不计生产缺陷修复证据；已通过现有配方文件、`body_for_task`、
`urdf_refs` 保存真实依赖，未使用配置或资产桩通过准备入口。

沿报告传递引用另接通 Blender 导出器及其真实自检。新导出解析源位置后仍核批准 build SHA、
完整候选文件绑定和实际参考结构；打开 Blend 的路径同步使用已校验目标位置。
旧脚本字节从 Git `21a9260` 恢复，原版两入口在同样隔离下应失败且无新输出；
现版真实 Blender 自检必须通过，生成的 73 个工件摘要与原批准导出一致。
`bpy.data.filepath` 核对实际加载新根 Blend，不能仅以 Python audit 声称覆盖原生文件读取。

删除前完整恢复已退出 0：`core.autocrlf=true/false` 每档均核对 614 个文件的原始、Git blob、
检出字节，恢复历史归档的 130 个清单路径。实际运行新根代码的几何正反例、机体预检 CLI、
73 工件导出校验及 17 个破坏对照、注册准备/复验 CLI、两类真实输入复制均通过。
Blender 每档完成 2 个正例、31 个负例，73 个生成工件与原批准导出同字节；
Python 正常消费者旧仓读取为零，主 Blend 实际从新根加载。不把 Python audit 外推为原生全部 I/O 隔离。

删除前刷新全 40 原文件与目标 39 文件的大小/SHA，确认范围无 reparse point，
CIM 快照无选定根命令进程，再删除准确的整个旧根及过时 attributes，`deletion.json` 保留绝对范围。
`rl_exp/out/lizard2_palm_spatial_20261014/` 已实际不存在；39 输入均在诊断基准下，报告未改。
主索引在既有 OS 锁内原子定稿，旧父容器标为移除，子根映射继续兼容旧身份。
迁移前预检报告 SHA256：`dd94f6bcbe6ad82f0f811b3b23bde16b3c2b641cffbe322cf6a3b5b0cdc9efce`。

通用预检回归通过，最终 source_geometry 分组累计 329 个断言；离线仓库闸门 37/37 通过（60.2 s）。
删除后 `recovery-after/` 同样退出 0：两档各 614 文件、130 历史路径，完整 CLI 和真实 Blender 全部通过，
迁移前报告摘要未变；每档 Blender 仍为 2 正例、31 负例和 73 工件同字节。
删除后默认迁移回归 13/13 通过（56.678 s），暂存迁移后 `hooks/pre-commit` 通过。
删除后仓库离线闸门再次 37/37 通过（63.6 s），排除保留旧副本时闸门碰巧通过的可能。

独立审核（`independent_artifact_review`，2026-10-22）：未参与本批实现或删除，实读生产与验证改动、
固定清单、删除记录及最终 child/Blender、回归和闸门日志。删除前后分别逐文件核对 39 个输入，
目标副本与 Git HEAD 原路径字节全等，共 7,853,087 字节；删后旧根不存在，主索引清单精确覆盖这些文件，
每个旧路径实际解析到新副本且逻辑身份相同，归档及预检参考报告摘要与删除记录一致。
导出审批、完整文件与来源身份检查仍保留，通用预检没有把原 `fail` 改成通过。

恢复包早期缺真实 YAML、母机体和引用网格的阻塞已经补齐；最终删除前后两档均有 614 文件/130 历史路径、
完整离线消费者和 Blender 成功证据，当前四份生产源码摘要与相应执行日志一致。
缺映射与错摘要反例仍拒绝，正常消费者单独核旧 Python 读取为零；Blender 主文件路径另核新根，
每档 2 正例、31 负例和 73 工件摘要保持一致。实读删后 13/13、通用预检累计 329 断言、
删后离线 37/37 及提交前闸门通过。结论：本批当前输入迁移和旧根删除通过，未发现剩余 P1/P2。
审核未另行重采或重跑完整套件，不声称原生全部 I/O 已隔离、Kit 动态能力或资产已获批准；
本机证据、框架及历史对象前提仍适用，总事项继续在办。

## 证据引用

本机证据根：`rl_exp/out/runs/diagnostic-artifact-lifecycle/20261022-checkpoint-relocation/`。

- `inventory.json`：原根完整文件集合、摘要、大小及跟踪清单。
- `body-before.json`、`body-before.log`：迁移前真实 CLI 的完整原判词。
- `consumers-before.log`、`consumers-fixed.log`：三个读点修前失败、修后通过。
- `relocation-tests.log`、`body-regressions.log`：迁移和通用预检回归。
- `recovery-predelete*`：依赖缺失失败与完整恢复结果；成功必须同时核 checks 和真实 child/Blender 日志。
- `recovery-predelete-final/`：删前最终实现两档完整成功，含 `checks.json`、child 与 Blender 日志。
- `writer-before-delete.json`、`deletion.json`：刷新进程与摘要后的准确删除事实。
- `recovery-after/`、`relocation-after.log`：删除后同一实现的恢复与回归；`offline.log`：仓库闸门。
- `offline-after.log`、`precommit.log`：删除后的仓库闸门与暂存后检查。
- 消费入口说明：`rl_exp/docs/diagnostic_artifacts.md`；真实位置：`rl_exp/tools/diagnose/artifact_index.json`。

```text
<python> -B rl_exp/tools/verify/test_artifact_relocation.py --archive rl_exp/out/archive/palm-spatial/history-20261014.zip --proof_root rl_exp/out/runs/diagnostic-artifact-lifecycle/<new_recovery> --body_reference rl_exp/out/runs/diagnostic-artifact-lifecycle/20261022-checkpoint-relocation/body-before.json --blender E:/SteamLibrary/steamapps/common/Blender/blender.exe
<python> -B rl_exp/tools/verify/test_artifact_relocation.py
<python> -B rl_exp/tools/verify/test_body_precheck.py
```

## 未覆盖边界

实际运行时复制验证执行真实校验、目录创建、全部文件复制及摘要检查，在 AppLauncher 边界明确停止；
本批不启动 Kit/PhysX。注册准备/复验、导出校验、通用机体预检运行真实完整离线 CLI，
Blender 验证真实几何导出；这些不代表仿真、承重、PD、连续域或资产批准。

归档、原始运行样本及 `body-before.json` 仍为本机证据，不随 Git 检出，也未建立外部备份。
默认回归要求本机样本和绑定 FK 的历史 Git 对象 `d243b9e`；真实 Blender 破坏对照还需
`21a9260` 中两份旧导出源码。浅克隆缺这些对象会明确失败。
完整恢复依赖配置的 Python/Blender 及当前框架；这不是可脱离框架运行的跨机器安装包。
其它混合根、生产入口推广、外部备份和原生复制故障继续由原事项承接，事项保持 `in_progress`。
