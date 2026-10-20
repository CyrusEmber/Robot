# 诊断产物首批盘点与实施前置修复

## 适用范围

用户于 2026-10-20 选择“盘点＋前置缺陷修复”，不执行产物迁移、解除跟踪或删除。对应 [诊断整理事项](../../work/active/diagnostic-artifact-lifecycle.md)，本记录只交接首批实现与证据，不是全事项关闭审核。

## 验收条件

- 两个输出根均可复读盘点，记录字节、摘要、Git 状态、词法引用及传递依赖；未确认归属、价值和写入状态的条目保持 pending，不授予清理权限。
- `diagnose_support.main` 的真实报告与摘要写入路径同名重跑须在覆盖前拒绝，旧文件数量、字节和摘要不变。
- 本批保留链 `local_path_view` / `local_path_check` / `local_path_contact` 在普通模式拒绝错误身份；优化模式须在读取输入或写输出前明确拒绝，不允许断言失效后继续。
- 两输出根的 Git 忽略规则成立，已有 tracked 基准不丢失；目标 runs/archive 布局在 `core.autocrlf=true/false` 下真实 add、commit、重新检出后保持原字节。
- 修复前后使用同一行为检查对照；迁移定位、真实恢复消费者及其它诊断入口不因上述局部通过解除前置。

## 结果

### 实现落点与行为验证

1. **盘点**：新增 `artifact_inventory.py`，输出独占创建。复用 `runrecord.binding.sha256_file`；不遍历 symlink/junction，Git 状态批量取用。JSON 路径键及值纳入依赖，缺失明确路径记录有界 unresolved 审计；传递消费者明确为词法提及，不冒称活跃消费。全部条目 pending、owner 为 diagnostic-artifact-lifecycle executor、next 为核实际生产者/消费者/价值/写入状态。引用覆盖、runtime 与 writer 均 unknown。
2. **同 label 覆盖**：生产 `main` 改为独占 mkdir。回归执行完整生产 main/Case，仅替代仿真与采集数据，不替代 mkdir、open、JSON 和摘要写盘。修前 4 FAIL，修后 4 PASS；包含首次真实报告/摘要写入、预置旧字节、phase 0 和空目录重复拒绝。目录独占阻止同 label 重入，文件 writer 仍使用 `w`；本轮不是文件级 exclusive writer 改造。真实 CLI 仍先起 App，本轮不证明启动 App 前拒绝，也未验证仿真数值。
3. **优化模式**：`local_path_view` 在 NumPy 导入前模块级拒绝优化模式，直接导入 `_load` 与 check/contact 导入链同受保护。修前真实坏 build 摘要在优化模式被生产 `_load` 接受，回归 39 个失败；修后 3 项、49 个子场景通过。覆盖 normal、`-O`、`PYTHONOPTIMIZE=1/2`；两份原报告正常模式真实解析通过，优化模式连正确身份亦明确拒绝。CLI 禁写/禁渲染哨兵及读输入哨兵未被触达。view/check/contact self_check 通过，drive_identity 破坏对照失败。
4. **Git 边界**：根 `.gitignore` 覆盖两个输出根，明确忽略不是备份或删除许可；根 `.gitattributes` 为两根递归设置 `-text`。真实临时仓 CRLF JSON/URDF/OBJ 覆盖根目录、runs、archive，执行 add/commit、删除测试样本后重新检出和 clone；true/false 两档原始、blob、检出字节及 SHA256 一致。HEAD 基线同一回归 37 个失败，当前 3 项通过。已有 43 个 tracked 产物未解除跟踪，未搬迁或删除。
5. **盘点自身回归**：嵌套引用、循环、外部 JSON、Git 状态、exclusive output、哈希失败、枚举边界变化，以及 hash-map 路径键/缺失依赖/审计截断共 7 项通过；新增引用三项先在未修实现失败。额外词法字段和 stat 签名限制明确声明。方法自检不代表存量归属已判定。

### 快照与观察限制

- 初次快照 `inventory.json` 观察两个根合计 2,952 文件、1,243,721,271 bytes、43 tracked、350 ignored、154 顶级包。引用扫描 1,826 文本、14,891 条边，26 个跳过、3 个 UTF-8 解码失败。该快照不含自身。
- 加入新证据和修复后的 `inventory-final.json` 观察 3,038 文件、1,452,362,218 bytes、43 tracked、2,995 ignored、164 包、26,409 引用边；该次与本轮回归写日志/临时坏身份样本并行，`rl_exp/out` 边界变化已降级 unknown，不能用于迁移。SHA256 `53f8cc3e9e2a4f3cf21f0f0a30dc985fde1335573f199ea7c067573b642b2548`。
- 后续刷新 `inventory-handoff.json` 观察 3,041 文件、1,494,227,427 bytes、43 tracked、2,998 ignored、164 包、26,516 引用边；两根枚举边界未观察变化，unknown_entries=0，但 writer/runtime 仍 unknown。SHA256 `8fe8a7f2551e04b299af5f90510f567c837436d52659645702d36e41424942fa`。引用审计 28 跳过、3 解码失败、1,000 unresolved 保留、2,810 unresolved 截断；不会据快照称依赖齐全。该快照不含自身。
- 新增文件和体积包含其它在办实验与本轮盘点/验证材料，不是待删除体积；旧快照亦纳盘点，不以空间目标授权清理。仍是非原子观察，不据 unchanged stat 推定没有 writer。词法能力有大小/文件数/未解析路径预算；未解析路径可能包含协议标签而非文件，必须人工判别。
- 快照与日志本机单副本，默认忽略；未建立外部备份，不能删除。此前快照及失败日志亦保留，全部新产物归本事项，复核者沿下述路径读取。

### 审核与闸门

独立只读新上下文审核首批实现，未发现 blocking 缺陷，指出词法消费者、缺失路径审计、stat 签名及 tracked/ignored 解释限制。已补明确词法性质、JSON 键路径与未解析审计、stat 碰撞限制和 Git 语义；该次审核后证据及实现仍有修订，不作为最终独立关闭审核。

最终修订后另由全新只读上下文复核实现与记录，未发现 blocking，可交接首批；指出目录独占不等于文件级 exclusive writer、词法清单不等于消费者全集、按需回归不在默认套件。本记录已声明这些边界；该审核未运行命令，不替代全部事项关闭审核。

首轮完整离线闸门 36/37 通过，共享摘要闸发现两个测试重复文件哈希；盘点本体与测试均改为复用 binding，定向摘要闸及受影响 7+4 回归通过。完整复跑 `ALL_OFFLINE_CHECKS_PASSED (37/37 in 50.2s, jobs=4)`，未增加默认套件条目；本轮四组回归按需独立运行。

## 证据引用

本机产物父目录均为 `rl_exp/out/runs/diagnostic-artifact-lifecycle/`：

- `20261020-inventory/inventory.json`、`inventory-final.json`、`inventory-handoff.json`：盘点清单、逐文件摘要、Git 状态、引用边、待判定责任与扫描限制。
- `20261020-preflight/diagnose-support-red.log` / `diagnose-support-green.log` / `diagnose-support-bindings.log`。
- `20261020-preflight/optimization-red.log` / `optimization-green.log` / `optimization-selfcheck.log`。
- `20261020-preflight/git-boundary-red.log` / `git-boundary-green.log`。
- `20261020-preflight/inventory-reference-red.log` / `inventory-reference-green.log` / `inventory-binding-final.log`。
- `20261020-preflight/final-test_*.log`：四组整体验证日志；摘要复用改动后盘点与同名 writer 的补验按正文解释，不把旧日志冒称修订后运行。

从仓根，以 `python -B ablation_harness/host_paths.py --python` 解析配置解释器后：

```text
<配置解释器> -B rl_exp/tools/verify/test_artifact_inventory.py
<配置解释器> -B rl_exp/tools/verify/test_diagnose_support_output.py
<配置解释器> -B rl_exp/tools/verify/test_local_path_optimization.py
<配置解释器> -B rl_exp/tools/verify/test_diagnostic_git_boundary.py
<配置解释器> -B rl_exp/tools/diagnose/diagnose_support.py --self_check_bindings
<配置解释器> -B rl_exp/tools/diagnose/local_path_view.py --self_check
<配置解释器> -B rl_exp/tools/verify/offline_suite.py --jobs 4
```

盘点复跑选择**已存在目录下的全新文件名**，禁止覆盖快照：

```text
<配置解释器> -B rl_exp/tools/diagnose/artifact_inventory.py --output rl_exp/out/runs/diagnostic-artifact-lifecycle/20261020-inventory/inventory-recheck.json
```

`test_diagnostic_git_boundary.py --baseline` 取执行当时 HEAD 根规则，仅用于本轮未提交修复前对照；提交后 HEAD 已含修复，不能再把此开关当固定旧版本复现入口，原红日志保留。两份正常身份实读样本为 `lizard2_palm_local_path_20261015_v3/report.json`、`lizard2_a_contact_delivery_20261019/report.json`，均保持原位原字节。

## 未覆盖边界

- 迁移映射消费、原路径授权保持、旧根/链接不可用的真实消费者复读尚未实现；未迁移任何历史报告，未修改机器人/驱动/物理判据。
- Git 字节回归使用小 CRLF 样本，不代表完整 checkpoint 的迁移、真实消费者恢复或外部备份完成。
- 其它输出根发现、逐包实际生产者/消费者/保留理由、运行停止状态、长期索引和日常收尾机制均未完成；全部 pending 不授予任何删除权。
- 优化 guard 只保护已测导入链，其它独立 probes 身份断言仍须逐链审计，不称全诊断优化安全。
- 本机真实报告依赖未入库路径；优化回归需要这两份历史样本，未制作可跨机独立检出的最小真实样本包。
- 未起仿真、未验证 USD runtime、动画内容、动力学或已关闭原专项；本轮独立审核不是整个事项 pending_review/关闭审核。
