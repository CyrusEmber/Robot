# 空间导出历史合并与当前输入迁移

## 适用范围

事项：`work/active/diagnostic-artifact-lifecycle.md`。承接检查点旧混合根删除，
本批处理空间导出目录及相邻实验日志；固定清单、真实读取接线、换根恢复后再删除旧副本。
原逻辑身份、报告字节、独立批准摘要、源输入与结构检查均保留，不新增资产批准。

## 验收条件

- 固定清单与依赖闭包，刷新原字节、writer、Git 状态和准确删除范围。
- 当前导出走既有映射，独立批准及谱系约束保留；同组真实回归修前失败、修后通过。
- 历史数据显式恢复、日志原字节保留，正反例按实际消费者判定。
- 代码与输入共同换根，两档真实检出及 Blender 通过，删除旧副本后复验并独立审核。

## 结果

### 实现与修前对照

`palm_spatial_runtime.py` 在实际读取前解析导出位置；运行时输入报告复制、自检与 reset
新鲜导出谱系核验使用同一身份映射。谱系相同仍须独立核报告、URDF、完整源文件和配置。
批准校验在读取导出 JSON 内容前进行；测试只拦截实际被拒绝报告的读取，不能误拦合法索引。

修前同一组真实消费者回归三项失败：换根后的导出校验与复制准备因未解析位置被隔离根约束拒绝，
reset 在相同批准字节映射到新位置时误报 `fresh export lineage mismatch`。
修后同三项通过；reset 还用未映射的同名同字节外来副本证明谱系仍拒绝，且无新输出。
reset 正例执行原注册清单、真实资产、目标及配置预检与复制，到 AppLauncher 边界停止。

### 固定清单与恢复

固定清单涵盖 8 个目录和 6 份日志，共 599 文件、73,200,690 字节，均未被 Git 跟踪。
当前实际依赖 `lizard2_spatial_export_cli_verified_20261019/` 的 74 文件逐字节迁至
`rl_exp/out/archive/palm-spatial/approved-export-20261019/`，通过既有索引兼容原逻辑路径。
报告 SHA256 为 `1f69bcd41330df40c9034c68973e687049f1294697924940cbef264bafe0e36a`，
URDF 为 `e8896feb8b0dbdbeaa35e74a01c2ffcb4ab38d89b52f221831b3f287943edd00`。

其余 525 个历史文件及 39 个检查点依赖保存于
`rl_exp/out/archive/palm-spatial/exports-20261019.zip`；564 个清单路径按 SHA 合并为
124 个数据块，压缩包 3,939,873 字节，SHA256：
`a1cdb566192cc9c9f56baf896e388470229e9a76918610c266e2f9c9371def0a`。
检查点依赖包含实际字节，恢复时从新归档读取；先核其与保留基准一致。
ZIP 不注册透明路径映射，只提供显式按清单恢复，当前输入另行保留。

两档 `core.autocrlf=true/false` 真实 add/commit/clone，移除临时源仓，原仓 Python 文件读取被阻断。
每档核对 1140 个原始/blob/检出文件，恢复两归档合计 655 个历史路径，其中新包 564 路径。
真实几何正反例、完整机体预检、导出批准/破坏对照、注册准备/复验 CLI 和 Blender 空间导出均复验。
旧逻辑导出放入冲突副本时消费者仍读映射位置；缺映射或损坏当前批准报告须拒绝。

历史导出经真实 `check_export` 复读为 6 正例及 1 个惯性张量反例；反例准确拒绝
`export full inertia differs: base_link`。测试使用归档固定报告和 URDF 摘要供结构核对，
不将它们授予生产批准。名含 `negative_missingaxis` 的历史目录实际为正例，保留原字节与名称，
不能按目录名伪称缺轴反例成立。6 份日志逐字节恢复，不宣称重跑其记录的旧实验。

归档破坏回归覆盖丢失唯一张量 URDF、改写日志且重新生成有效 ZIP CRC、重复数据块、
清单路径越界及删除张量反例元数据，5 项均被拒绝。

### 删除与复验

最终删前两档恢复均退出成功，每档 1140 文件、655 历史路径，child 与真实 Blender 通过；
默认回归 15/15 通过（78.655 s）。删除前再次核所有原文件及当前副本大小、SHA，
确认目标为输出根下固定 14 个直接子项、无 reparse point、无 Git 跟踪，CIM 快照未见选定根进程。
准确删除 8 个目录和 6 份日志；`deletion.json` 逐项记录绝对路径与完成事实，14 处旧位置已不存在。
当前 74 个输入在新目录，525 个历史文件及检查点依赖在归档，主索引由既有锁保护定稿。

删除后完整恢复再次退出 0，两档均保持 1140 文件、655 历史路径及 564 新包路径，
真实 child 和 Blender 全部通过。默认迁移回归再次 15/15 通过（104.922 s），
两档独立重检出也确认旧仓 Python 读取为零、身份与几何反例仍拒绝。

首轮删后离线闸门因本记录标题格式不符而失败，已改为规定五节；随后功能检查通过，
但并行负载下 obs 声明和绑定单源检查分别单独测得 38.3 s、25.9 s，超过原 25 s 预算。
未改预算，完整恢复结束后串行重跑 37/37 通过（220.4 s，jobs=1）；
绑定单源检查回到 14.8 s，acceptance metrics 的 26.3 s 另复测为 16.2 s，均在原预算内。
总事项继续 `in_progress`，未覆盖入口、其它存量、外部备份与底层原生复制故障仍归原事项。

独立审核（`independent_artifact_review`，2026-10-22）：未参与本批实现或删除。删除前逐项核实
599 个原文件与固定清单一致，564 路径/124 数据块归档无额外或重复成员，74 文件副本原字节相同；
删后再逐项核实 14 个准确落点不存在，599 文件全部由固定 ZIP 或活动副本按原大小和摘要覆盖，
主映射保留完整逻辑身份，删除记录绑定的删前恢复证明摘要一致。

实读生产与验证改动、归档破坏用例及删前后两档 checks、child、Blender 和回归日志：
1140 文件、655 历史路径、564 新包路径对应真实恢复，6 个历史正例及张量精确拒绝与记录一致，
冲突旧副本被忽略，缺映射、错摘要、同名外来谱系及五类归档破坏仍拒绝；原机体 `fail` 未被升级。
删后 15/15 与最终串行 37/37（220.4 s，jobs=1）日志已核，记录格式缺口已经修正。
结论：本批合并、迁移与准确范围删除通过，未发现剩余 P1/P2。审核未另行重采或重跑完整套件，
不将 reset 原代码根的输入迁位验证扩称整链换根，不外推原生全部 I/O 隔离、Kit/物理能力或资产批准；
本机产物与外部备份边界保留，总事项继续在办。

## 证据引用

本机证据根：`rl_exp/out/runs/diagnostic-artifact-lifecycle/20261022-export-consolidation/`。
`inventory.json`、`prepared.json` 固定文件集合与归档；`consumers-before.log`、
`consumers-fixed.log` 保留同组修前失败和修后通过；`archive-damage-tests.log` 为真实包破坏对照。
完整恢复读取 `recovery-predelete-final/` 和后续 `recovery-after/` 的 checks、child、Blender 日志。
`writer-before-delete.json`、`deletion.json` 保存执行前刷新及逐项删除事实；
`relocation-final.log`、`relocation-after.log` 为默认回归；`offline-after.log` 保留格式失败，
`offline-after-final.log` 保留功能通过但成本超限，`offline-after-serial.log` 为后续串行仓库闸门。

```text
<python> -B rl_exp/tools/verify/test_artifact_relocation.py --archive rl_exp/out/archive/palm-spatial/history-20261014.zip --export_archive rl_exp/out/archive/palm-spatial/exports-20261019.zip --proof_root rl_exp/out/runs/diagnostic-artifact-lifecycle/<new_recovery> --body_reference rl_exp/out/runs/diagnostic-artifact-lifecycle/20261022-checkpoint-relocation/body-before.json --blender E:/SteamLibrary/steamapps/common/Blender/blender.exe
<python> -B rl_exp/tools/verify/test_artifact_relocation.py
```

## 未覆盖边界

迁移前机体预检原本失败；恢复比较保留其完整判词与缺证，不称机体或物理验收通过。
Python audit 不覆盖原生全部 I/O；Blender 主 Blend 另核实际从新根加载。
运行时复制和 reset 只验证至应用启动边界，不启动 Kit/PhysX。
reset 本批验证在原代码根将导出输入迁位，使用原新鲜注册清单；不外推为该清单整链换根能力。

归档和当前批准导出仍仅本机保留，未建立外部备份；它们被 Git 忽略，源码与记录推送不备份产物。
复验需要本机原注册输入、框架、Python/Blender 和历史 Git 对象 `d243b9e`、`21a9260`。
缺依赖明确失败，不能从仅含源码的浅克隆声称恢复完成。
