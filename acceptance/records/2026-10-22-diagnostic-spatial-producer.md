# 空间几何探针的运行归属、失败收尾与映射复读

## 适用范围

事项：`work/active/diagnostic-artifact-lifecycle.md`。本轮将
`rl_exp/tools/diagnose/palm_spatial_probe.py` 的历史对照、静态切片、边界加密、局部路径四种写入路径
接入既有 `ArtifactRun` 和 `artifact_index.json`，保留原 CLI、几何口径和报告结构。
复用说明归 `rl_exp/docs/diagnostic_artifacts.md`；不修改机器人、配方、驱动、碰撞过滤或求解预算。
使用 `lean-build` 收敛到同一创建与收尾入口，没有新增依赖、位置库或默认闸门。

输入为既有 `rl_exp/out/lizard2_palm_spatial_20261014/checkpoint_v3/build.json` 及其绑定候选。
新输出均放在 `rl_exp/out/runs/diagnostic-artifact-lifecycle/20261022-spatial-producer/`（以下称证据根）。
旧混合目录的存量处置仍由原事项承接，本轮不把正在使用或未核清的目录自动视为可删除。

## 验收条件

- 四种生产模式都在采集和第一份图像/报告写入前登记，成功必须满足完整输入、源码与必需输出校验。
  `--self_check` 不生产运行目录。
- 同名调用在重采前拒绝，原目录全部字节、数量、摘要及索引不变；写图或报告失败留具名 `failed` 记录和已有产物。
- 现代模式只重读实际消费的候选和报告；build 中原始源文件摘要继续作为溯源，不引入不必要的旧源依赖。
  历史对照模式仍核源机体及原输入；所有模式绑定实际仓内辅助源码与被导入的资产声明。
- 输入的逻辑身份与当前位置分开，映射后计算摘要并真实读取当前字节；旧路径不可读时从当前映射位置执行完整加密入口。
  错身份、错依赖摘要必须拒绝，不能以同名文件放行。
- 保留修前失败与修后通过，核对真实原版/修后数值和图片，实际消费者能读新报告；仓库检查通过。

## 结果

生产入口统一由 `_run_probe` 包住四种实际采集函数；创建使用现有排他目录与索引锁，收尾复用既有输入/代码/输出校验。
新增可选 `--work_id`、`--owner`、`--retention_reason`，缺省归本事项及本机执行者；原有调用仍可用。
历史与静态模式分别要求 `comparison.png`、`static_slices.png`（锁轴历史对照不要求图），四种模式都要求 `report.json`。
结果不合格导致原历史入口退出时，报告保留且运行记失败；局部探索的几何失败仍按原报告表达，不改成能力通过。

未改版源码的四种真实运行和接入生命周期后的四种真实运行均退出 0。后者四份父记录完成，
输入数依次为静态 40、加密 41、局部路径 40、历史 79，各绑定 15 个仓内源码。
去掉执行源码身份及加密报告的来源位置/摘要后，四份完整报告逐字段一致；
`static_slices.png` 与 `comparison.png` 均逐字节一致。比较不删除几何数据、判词、过滤、预算或失败姿态。
已有消费者 `local_path_view._load` 真实读取新局部路径报告，lf/rr 两条轨迹通过其身份和 FK/网格读点检查。

上述四模式对照使用 `probe-lifecycle-v1.py` 所存精确源码。随后发现并修复加密输入的映射别名问题；
该增量只改变逻辑身份比较及模块说明，最终源码另经真实映射加密及负例验证，不把前一源码摘要冒称最终执行字节。
四份已完成运行及两份失败现场的源码位置已指向核同摘要的归档副本，保留执行身份、摘要、命令及原报告字节。
通用运行记录不是不可变执行快照，后续源码变化不能通过改旧摘要冒充原执行。

真实失败对照由 `test_palm_spatial_output.py --real_build ... --proof_dir ...` 驱动原采集与写入函数：

| 注入位置 | 保留产物 | 终态及重跑 |
|---|---|---|
| 静态报告写入失败 | 实际生成的 `static_slices.png` | `failed`，保留执行者、错误和下一步；同名拒绝且所有字节与索引不变 |
| 历史报告写出后绘图失败 | 实际 `report.json` | 同上，不因 JSON 完整而冒称完成 |

初版缺少运行记录的反例与优化模式反例，在实现修改前跑出两个测试、五个失败断言。
优化进程原先已越过身份断言进入 XML 读取；现 `-O`、`-OO`、`PYTHONOPTIMIZE=1/2` 均在依赖导入和输入读取前明确拒绝。
最终七项轻量回归覆盖四模式登记、写入失败、同名拒绝、登记失败停止采集、采集中输入变化拒绝完成、
现代模式不重读溯源旧源、不一致候选摘要以及四档优化拒绝。

独立审核定位了真实 P2：加密原先逐字比较 `identity.build_report`，从新存储位置调用会被拒绝，
尽管映射的逻辑身份和字节都正确；源码依赖绝对 key 也存在同类问题。
最终使用 `ArtifactPaths.same_identity` 比较完整逻辑路径并保持摘要检查，依赖须逐一唯一匹配，
仅保留原先允许本 probe 自身版本变化的例外，不用 basename 或后缀放行。

真实迁移反例先复制现有候选和静态报告到临时恢复根，使用同一索引格式的隔离测试映射，
通过 `builtins.open`、`Path.open`、`os.open` 阻断原候选根和原静态报告根，先逐通道直接读旧根确认阻断有效。
从两个当前映射位置运行完整加密，修前确实失败于 `source identity mismatch: build_report`；修后完成 9 个加密括号，
终态、摘要和登记通过。最终又验证同名不同完整路径的 build、同名不同完整路径的 FK 依赖、错误 FK 摘要均拒绝，
留下失败记录且没有报告；还原测试源后原成功运行完整性再次通过。
测试候选副本、索引和临时运行随后一起清理，主索引没有悬空测试登记，原产物未移动或删除。

最终离线闸门 37/37 通过（49.9 秒，jobs=6），原几何/求解自检三部分通过，提交前静态闸门及
事项格式检查通过（`WORK_DOCS_OK`）。这些检查不替代以下实际产物审核；总事项保持 `in_progress`。

独立复核（`independent_artifact_review`，2026-10-22）：审核上下文未参与实现，核对本轮生产源码、
测试及真实四模式落点，独立运行七项轻量回归（7/7，5.946 秒），逐项复读四份完成记录的输入、源码、
输出绑定与两份失败现场。四份完整报告仅排除执行 probe 自身身份及加密来源位置/摘要后与原版一致，
其余依赖摘要和全部几何字段仍参与比较，两张 PNG 逐字节一致；消费者真实读回 lf/rr 各 65 帧及 18 个网格。
四模式及失败现场绑定的归档源码摘要正确，未把归档版本误作最终版本执行证据，复读前后原文件及主索引未变。

原 P2 的最终修复使用完整映射身份逐一唯一匹配并保留非 probe 依赖摘要检查。复核最终验证脚本及
`relocation-verified` 实际结果：三通道旧根拒读后从当前位置完成 9 个括号，同名异族 build、同名异族 FK、
错误 FK 摘要均留下失败记录且无报告；反例同时同步隔离磁盘索引，恢复源及索引后原成功检查再次通过，
临时恢复根已清理。最终生产源码 SHA-256 为
`25666388cba10c303d071df1da60f5e4fe3c9cdfdb1f3a978c31b1cff3c6ce2b`。
结论：本轮四模式产物生命周期与映射修复切片通过，未发现剩余 P1/P2；审核未重采四模式或重跑重型套件，
不将局部映射验证扩称完整 Git 换根、异机恢复或物理能力验证，不关闭总事项。

## 证据引用

- 新实现：`rl_exp/tools/diagnose/palm_spatial_probe.py`；可重复验证入口：`rl_exp/tools/verify/test_palm_spatial_output.py`。
- 主索引新增四份成功与两份失败运行指针；状态与输出摘要以相邻 `run.json` 为准。
- 证据根 `before-static/`、`before-refine/`、`before-local/`、`before-historical/` 是原版控制输出，
  故不冒称已由旧版自动登记；`baseline.json` 与 `probe-before.py` 保存实际命令和源码。
- `after-static/`、`after-refine/`、`after-local/`、`after-historical/`：四份实际产物与完成记录。
  `comparison.json`、`comparison.log`：完整报告数值及 PNG 字节比较、消费者读回与四份检查。
- `real-failures/static/`、`real-failures/historical/`：真实失败现场；`real-failures/checks.json` 与 `real-failures.log`：同名拒绝、字节和索引保护。
- `probe-lifecycle-v1.py` 与 `test-failures-v1.py`：分别为四模式对照及两份失败现场绑定的精确执行源。
  源码 SHA-256 分别为 `e2eeb3f243b47267d1fc1fa8b04cb07947a15d22d9ff0664842ea3d98118f9e4`、
  `b843120570baf90c00957024144b32824ef8d81e58b56ebcf542e2d56d86af60`。
- `red.log` / `green.log`：生命周期和优化反例修前失败、接入后轻量回归通过。
- `relocation-red.log`：完整加密在真实旧根隔离下修前失败；`relocation-verified.log` 和 `relocation-verified/checks.json`：
  最终七项回归、当前映射位置成功及三类错身份/摘要反例。
- `independent-review/tests.log`、`independent-review/evidence.log`、`independent-review/consumer.log`：
  独立轻量回归、四模式和失败现场绑定/原版完整报告及图片对照、消费者实际读回。
- `self-check.log`：原几何/求解自检；`offline.log`、`precommit.log`、`work-docs.log`：仓库、提交前及事项检查。

在仓根使用配置解释器，新输出目录必须不存在：

```text
<python> -B rl_exp/tools/verify/test_palm_spatial_output.py
<python> -B rl_exp/tools/verify/test_palm_spatial_output.py --real_build rl_exp/out/lizard2_palm_spatial_20261014/checkpoint_v3/build.json --proof_dir rl_exp/out/runs/diagnostic-artifact-lifecycle/<new_failures>
<python> -B rl_exp/tools/verify/test_palm_spatial_output.py --real_build rl_exp/out/lizard2_palm_spatial_20261014/checkpoint_v3/build.json --relocation_source rl_exp/out/runs/diagnostic-artifact-lifecycle/20261022-spatial-producer/after-static/report.json --proof_dir rl_exp/out/runs/diagnostic-artifact-lifecycle/<new_relocation>
<python> -B rl_exp/tools/diagnose/artifact_run.py --inspect_run rl_exp/out/runs/diagnostic-artifact-lifecycle/20261022-spatial-producer/after-static
```

## 未覆盖边界

- 原有混合目录仍有其它消费者与历史证据；本轮完成新生产入口的维护切片，不代替全量存量处置、外部备份或事项关闭。
- 迁移验证覆盖本次真实候选、静态源报告、三种读取通道和完整加密入口；不是操作系统级所有 I/O 的隔离，
  也未完整复制代码仓后在另一主机检出执行。完整逻辑路径校验不等于所有其它工具已有换根能力。
- 源码及索引、验收记录入 Git；运行原字节只在本机保留，没有承诺外部备份。
- 图像逐字节一致及报告数值一致证明这次接入保持已有样本结果，不证明连续域安全、机构能力、限位、步态、PD 或动力学合格。
- 原生物理复制故障及其它生产入口推广保持原事项待办，本轮不运行 Kit 或修改规避模式。
