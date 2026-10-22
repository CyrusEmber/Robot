# 支撑诊断多环境路径与 Phase 3 摘要修复

## 适用范围

承接 `diagnostic-artifact-lifecycle` 的 support 多环境复验。修复 Phase 3 高度列表断链及独立审核发现的 Phase 2 摘要错列；支撑入口改用框架已有的逐环境 USD 复制与独立物理解析路径，保留完整诊断网格。操作入口归 `rl_exp/docs/diagnostic_artifacts.md`。

改动仅在诊断入口覆盖 `scene.replicate_physics=False`，没有修改 IsaacLab 源码、冻结配方、目标资产、checkpoint、物理参数或指标阈值。这是支撑诊断对原生复制故障的规避，不是底层 C++ 故障的根因修复。

## 验收条件

- Phase 3 的高度列表从解析处显式传入会话，两个高度的上下台阶摘要均生成；case 各列、时序各列、完成清单及环境关闭同时验证。回归须在旧实现失败。
- Phase 2 的表头和数据行列数一致，使用不同哨兵值逐列核对语义；真实摘要每列与同次 case JSON 对照，不能只检查文件存在或列名。
- 在环境构造前选定独立解析模式，配置快照保存实际模式，环境数量与全部地形列保留。原生优化路径不稳定时，不能缩成单环境或将崩溃改写为成功。
- 默认高度网格真实运行 Phase 0–3，形成全部 case、原始下采样时序、摘要及完成记录，检查实际文件与输入/源码绑定。同 label 复跑不得改变原文件或索引。
- 保留真实摘要失败与原生崩溃现场；本轮一次插桩失误可在核清归属与无独立产物后删除，索引同步清理。相关回归、仓库闸门和提交前检查通过。

## 结果

旧实现的九环境运行通过原生复制并完成全部采样，随后在 `_run_session` 的 `for h in heights` 抛出 `NameError`；四份 case 和 Phase 0 报告保留，摘要缺失，运行记录为 `failed`，进程返回 1。新增 Phase 3 回归在旧实现同点失败，传入高度列表后通过。

高度修复后，另一九环境运行再次在 `physx_replicate.py:102` 原生调用中访问冲突，尚未生成采样报告。该进程长时间留在崩溃处理阶段，经命令行精确确认后仅终止本轮专属进程，现场继续保持 `running`，没有补成成功。另有原生三环境和插桩环境 ID 对照能够完成；这表明故障不稳定，不能用单次通过宣称解决，环境 ID 假设也未被充分证明。

独立审核首次拒绝四阶段摘要完整性：Phase 2 表头 25 列，数据行只有 23 列，漏写 `yaw_drift_deg` 与 `turn_rate_deg_s`，后续列全部错位。首次 USD 运行把位移 `2.88` 标成 yaw 漂移，真实 yaw 为 `-3.3`。补齐两个字段后，新增不同哨兵值的 25 列语义映射回归；修前明确失败为 `23 != 25`，修后通过。旧目录 `lifecycle-v3-nineenv-usd-20261022` 与独立反例保留，不能作为最终摘要证据。

入口现采用独立 USD 复制与物理解析，避免注册原生复制回调，保留所有地形列。新增回归均有修前失败证明，与既有入口行为回归合计 18/18 通过；同时检查传入环境数量、多列输出、模式快照及环境关闭。最终夹具也对 Git 中 `1143b45` 的旧生产源码重验前两项反例，仍分别出现高度断链和复制模式断言失败，未改当前落盘源码。

最终目录 `lifecycle-v3-nineenv-summary-20261022` 的真实九环境 Phase 0–3 运行返回 0，六份必要输出及 `run.json` 均保留，完整性检查为 `completed`。四份 case 的统计和时序均覆盖九列，每列分别保存 50/100/100/300 个时序采样；Phase 2 全部 25 列及 Phase 3 八行逐字段匹配同次 JSON。输入 49 项、仓内源码 23 项均绑定。与真实旧实现相比，输入和目标绑定完全相同，环境/agent 配置唯一差异为 `env.scene.replicate_physics: true -> false`。Phase 0 与四份 case JSON 均与最初原生复制成功、随后摘要报错的基线逐字节一致；该观察仅覆盖本次诊断工况与保存精度。

真实同名 CLI 重跑返回 1 并在覆盖前报 `FileExistsError`，七个文件的数量与全部摘要、索引摘要均不变，随后完整性检查仍通过。没有向旧目录追加或重写成功记录。

最终源码的仓库离线闸门 37/37 通过（71.9 s，jobs=4），未放宽闸门。命名/接触绑定自检通过，旧过滤器破坏对照仍为 RED=8；提交前静态钩子通过。

清理仅删除本轮首次插桩导入冲突产生的无采样失败目录 `lifecycle-v3-native-trace-20261022`（仅一份 99,214 B 运行记录），在索引锁内同步删除其唯一登记，清理凭据保留。原生参数轨迹、实际失败对照及修复后运行保留；未删除其它事项的输入或证据。

### 独立复核

不参与实现的独立上下文在首次复核中发现并拒绝 Phase 2 错列；本次对修复后的最终源码和新运行重新审核，结论为**本轮 support 增量通过，无本次范围待修 P1/P2，总事项不能关闭**。最终审查代码为 `f74a48e`，`diagnose_support.py` 实际字节摘要为 `77e4e86fdd01d26dd94ab897002ca4b2519754624ef69b7c5a120b47d9ca89f1`。原错列表格及其反例保持有效历史，不改写为已通过。

独立运行轻量回归 18/18 通过（6.726 s）；核读 Phase 2 修前 `23 != 25`、Phase 3 高度断链和复制模式的修前失败证据。实际读取最终七文件并执行完整性检查，确认 completed、六份产物及 49 输入/23 源码绑定成立；检查前后七文件和索引均未变。逐项核对最终 Phase 2 的全部 25 列，yaw 漂移为 `-3.3`、转向速率为 `-0.33`，位移 `2.88/-0.18` 已回到各自列，后续载荷和账本字段也与 JSON 相符；四档台阶的上下八行全部逐字段匹配。四份 case 的统计/时序各有九列，16 类时序每列分别为 50/100/100/300 点；Phase 0 和四份 case JSON 与原生复制基线五文件逐字节一致。独立比较输入和 target_binding 完全相同，有效 env/agent 配置仅 `scene.replicate_physics` 一项变化，没有通过缩减环境或替换资产掩盖故障。

另外核对了本机框架源码：关闭该开关使 `clone_environments(copy_from_source=True)` 跳过原生物理复制回调，场景的碰撞过滤仍执行；本轮诊断改动没有另调物理参数或判据。读取真实同名 CLI 的错误日志及 `repeat-proof-final.json`，拒写后七文件和索引保持不变，保留运行仍可检查。原 NameError 现场 failed+五产物、原生崩溃现场 running+零采样产物均保留归属和下一步，并被独立只读检查拒绝。上述独立日志在本证据根的 `independent-review/`：`support-final.log`、`production-final.log`、较早的 `production.log` 和 `phase2-summary-misalignment.log`。本上下文未重跑重型全仓套件或另起 Kit，也未重演进程终止/删除操作；核读执行者最终 37/37 闸门及真实同名运行证据。报告字节一致只支持本次工况及保存精度，**不证明底层原生复制故障已根治，也不批准物理表现或关闭整体事项**。

## 证据引用

- 实现：`rl_exp/tools/diagnose/diagnose_support.py`；回归：`rl_exp/tools/verify/test_diagnose_support_output.py`。
- 本机证据根：`rl_exp/out/runs/diagnostic-artifact-lifecycle/20261022-support-multienv/`。`phase3-red.log`、`parse-mode-red.log`、`phase2-red.log`、`final-baseline-red.log`、`support-green-final.log`、`self-check.log`、`offline-final.log`、`production-proof-final.json`、`native-vs-usd-report-comparison.json`、`repeat-summary.log`、`cleanup.json` 保存修复前后与闸门证据。`native-trace2.log` 与 `nineenv-envids.log` 只用于原生调用调查，插桩代码 `native_probe.py` 在同一证据根保留；该对照改变了调用方式，不能充当生产入口验证。
- 真实旧实现：`rl_exp/tools/diagnose/out/runs/support/lifecycle-v3-nineenv-allphases-20261022/`，日志 `nineenv-allphases.log`。
- 高度修复后仍出现的原生崩溃：`rl_exp/tools/diagnose/out/runs/support/lifecycle-v3-nineenv-fixed-20261022/`，日志 `nineenv-fixed.log`。
- 首次独立复核的表格反例：旧 `lifecycle-v3-nineenv-usd-20261022/` 与 `independent-review/phase2-summary-misalignment.log`。最终独立解析生产复验：`rl_exp/tools/diagnose/out/runs/support/lifecycle-v3-nineenv-summary-20261022/`，日志 `nineenv-summary.log`。
- 框架机制对照：本机 `E:/IsaacLab/source/isaaclab/isaaclab/scene/interactive_scene_cfg.py` 的 `replicate_physics` 说明、`interactive_scene.py` 的 `clone_environments()`；关闭优化选择独立复制/解析，代价是初始化时间。原生接口约定另由本机 `_physx.pyi` 与 Isaac Sim Cloner 源码核对。

仓根复读（`<python>` 为配置解释器；真实运行 label 必须全新）：

```text
<python> -B rl_exp/tools/verify/test_diagnose_support_output.py
<python> -B rl_exp/tools/diagnose/diagnose_support.py --self_check_bindings
<python> -B rl_exp/tools/diagnose/diagnose_support.py --headless --task Lizard2-Flat-v3 --checkpoint E:/IsaacLab/logs/rsl_rl/lizard2_v3/2026-10-10_10-14-50/model_5999.pt --phases 0,1,2,3 --speeds 0.3 --reps 1 --label runs/support/<new_run> --work_id diagnostic-artifact-lifecycle --owner codex --retention_reason "support multi-environment reproduction"
<python> -B rl_exp/tools/diagnose/artifact_run.py --inspect_run rl_exp/tools/diagnose/out/runs/support/lifecycle-v3-nineenv-summary-20261022
<python> -B rl_exp/tools/verify/offline_suite.py --jobs 4
```

## 未覆盖边界

底层原生复制的访问冲突仍待定位；本次不修补 IsaacLab 或宣称训练入口的原生优化路径已恢复。独立解析路径增加初始化成本。本轮诊断输出完整性不代表机体、策略表现或台阶通过率达到实验验收阈值。

其它生产入口的推广、存量批次与整体恢复/交接尚未完成。总事项保持 `in_progress`；本轮执行记录不替代独立审核，也不扩展上轮独立审核的适用范围。日志、完整运行目录与外部 checkpoint 仍是本机证据，源码及索引入仓不等于异地备份。
