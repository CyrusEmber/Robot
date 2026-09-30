# 换代机制验收：换代检查、资产锁只写一次、退休语义（2026-09-30）

## 适用范围

本条机制的四侧落地与它的拒绝面：**换代检查**（非当前机体的冻结版本必须退休）、**资产锁只写一次**（`--update-locks --version` 只创建）、**退休语义**（退出验收、删锁、不承诺复现）、**身份读法**（线状态 + 版本例外，唯一实现）。

**本文档分三段**：第一段是 2026-09-30 当天的落地与自测（当时读作"全绿"，但**未覆盖**下文四条边界）；第二段是同日补齐那四条边界之后的复核与**完整换代演练**；第三段是第三轮发现的两处**实际漏检**（URDF 引用解析漏网格、新布局家族绕过隔离检查）及其反证与修复。每一段的"全绿"都只能按它自己覆盖到的范围读。

**不覆盖**：v1 的既成缺口（另见 `2026-09-30-lizard2-v1-body-gap.md`）；真实家族的第一次换代；资产清理与两具身体并行训练的设计。

## 验收条件

1. 四侧落地且 `run_offline_checks.bat` 全绿。
2. 每条新增拒绝都有破坏测试，且测试是夹具驱动（不是"读起来像会报"）。
3. **存量零改动**：既有的 31 份 `asset_lock.json` 与全部冻结 yaml 逐字节不变——本机制不允许为了让新判据通过而改动历史记录。
4. **（第二段补）边界必须先在当前实现上失败**：每条此前未覆盖的路径，先写回归用例、确认它在修复前是红的，再修到绿。四条边界见下。

## 结果

### 一、四个落点（2026-09-30 当天）

| 落点 | 形态 |
|---|---|
| 规则 | `.codemaker/rules/versioning.mdc` 越级段：换家族只留给"明确另立、长期独立维护的机器人设计"；本体/构型迭代 = 同家族**机体换代**，采用新机体时旧机体上所有冻结版本同变更退休；两条边界；退休语义；**锁只写一次** |
| 身份 | `versions/lines.json` 线条目内 `versions` 子映射 + `check_recipe_registry.effective_status` 唯一读法；`runrecord/lifecycle.py` 消费它决定放行 |
| 锁 | `_lock_files` 改**引用驱动**（配方声明的 `usd_path` → 机体资产），`update_asset_locks(version)` 只创建、已有锁与退休版一律拒绝 |
| 检查 | `check_asset_locks` 双集合（全部已登记版本供身份/孤儿锁，活跃版本供资产验收；退休版跳过）；`check_asset_isolation` 改用"当前机体"；`check_version_docs` 四件套按状态豁免退休版的锁；新增 `check_body_swap` 换代检查 |

### 二、当天自测（第一段的读数，口径见上）

`ALL_OFFLINE_CHECKS_PASSED (47/47)`、`PARITY_OK`（`versions locked: 2 active, 19 retired (skipped)`、`body swap: 2 version(s) … 0 still on a replaced body`）、`VERSION_DOCS_OK`（`retired versions (19, asset_lock.json not required)`）。九条破坏测试夹具实测。存量零改动。

**当时未发现**：下面四条路径在同一批夹具下一路是绿的，因为夹具从未走到它们。

### 三、第二段补的四条边界（先红后修）

| # | 边界 | 修复前的失败证据（回归用例） | 修法 |
|---|---|---|---|
| 1 | 活跃线内**单个版本**退休，其旧资产已清理 | `gamma/main/v1: usd_path missing on disk` —— 资产契约仍要求那份已随退休删除的 USD | `_version_yamls` 经 `effective_status` 排除**版本级**退休项（原先只按整条线过滤） |
| 2 | 整条线退休、该族已无活跃消费者，资产已清理 | `delta: declared mesh tree … is not a directory`、`delta: urdf has 1 mesh reference(s) that do not resolve` —— 隔离检查仍在读旧固定资产路径 | `check_asset_isolation` 只检查**仍有活跃消费者**的家族，取消固定资产路径回退（无活跃消费者即跳过） |
| 3 | 新布局缺同目录 URDF，但旧家族 URDF 存在 | `a new-layout usd without its own urdf fell back to the family's` —— 新 USD 会被配上旧 URDF | 解析归一：`obs_protocol.resolve_urdf/resolve_body/urdf_refs`，三个调用方复用；**兼容只对已声明的旧布局 `assets/<family>/<family>.usda` 成立** |
| 4 | 锁内**额外**文件（旧规则留下的条目）内容被改 | `a recorded file whose CONTENT changed was not reported` —— 只验存在，离线闸门放行而 run 侧 `asset_digest` 会拒 | 锁内**每条**路径验存在**与摘要**；"必需集合 ⊆ 锁内"另算一个判断；退休版不进入这两项 |
| 5 | 显式 `active` 版本例外被放行；`versions` 类型非法时继承线状态 | `effective_status -> 'active', expected None` ×2 | 版本例外**只接受 `retired`**；`versions` 非法类型返回未知；另修 `_active_lines` 的顶层键 bug（`load()` 把 `_missing`/`_unreadable` 放在顶层，原先在子字典里找 ⇒ 索引不可读被当成"没有活跃线"） |

同一轮还收紧了两件事：
- **统一拒绝语义**：状态必须**明确 active** 才允许创建锁；`--update-locks` 用 `O_CREAT|O_EXCL` **独占创建**（消除"检查不存在→写入"之间的竞争覆盖）；写失败即删除半成品，报错消息写明 **nothing was written**。实测：退休线 / 不存在的版本 / 已有锁 三条全部拒绝，`git status rl_exp/versions` 零字节改动。
- **兼容不等于"缺文件就找旧的"**：这是本轮最中间的取舍，写在解析器的文档里，也写进了 `_self_test_urdf_resolution` 的拒绝用例。

### 四、完整换代演练（可重跑夹具 `_self_test_swap_rehearsal`）

在一个临时家族上按真实顺序走一遍，逐阶段断言（既断言必须出现的报错，也断言处理后的安静）：

| 阶段 | 动作 | 断言 |
|---|---|---|
| 1 | v1 冻结在 b1，落锁 | 全部检查干净 |
| 2 | dev 改用 b2（新路径、自带 URDF） | `check_body_swap` 报出 v1 仍加载被替换机体 |
| 3 | v1 退休（版本例外）+ 删除其锁 | 全部检查重新干净 |
| 4 | 删除 b1 的资产 | 仍干净——没有检查再要求它们 |
| 5 | 新版本 v2 落在 b2 | 无锁时**红**；`--update-locks --version <v2>` 后**绿**，且只有 v2 的锁被创建、退休版的锁没有被重新造出 |

### 五、夹具自身的三处缺陷（后来者注意）

1. **无活跃消费者的家族会被跳过** ⇒ 只注册资产不注册活跃线的夹具会**真空通过**。（隔离夹具已补 `lines.json` + `<family>/main/main_params.yaml`。）
2. 开发 yaml 放在**家族目录**会触发真实约定 `parameters outside any line`（家族目录只放资产与记录）⇒ 整树发现失败、契约检查看到 0 份 yaml。
3. 局部变量重名（`bodies` 既是"当前机体"又是碰撞体列表）⇒ 循环第二圈 `AttributeError`。

**六、最终读数**（第二段）

```
rl_exp\tools\verify\run_offline_checks.bat                      -> ALL_OFFLINE_CHECKS_PASSED (47/47 in 61.1s)
E:\IsaacLab\env_isaaclab\Scripts\python.exe rl_exp\tools\verify\check_dr_parity.py --strict --self-test
   （六个夹具：locks / lock content / body swap / retired versions / urdf resolution / isolation / swap rehearsal）-> PARITY_OK
python rl_exp\tools\verify\check_recipe_registry.py --self-test  -> RECIPE_REGISTRY_GATE_OK（25 拒绝 + 10 条状态读法）
python rl_exp\tools\verify\check_version_docs.py                 -> VERSION_DOCS_OK
python rl_exp\tools\verify\check_work_docs.py                    -> WORK_DOCS_OK
```

### 七、第三段：两处实际漏检（先复现、先反证，再修）

| # | 漏检 | 修复前的复现 | 修法 |
|---|---|---|---|
| 1 | [P1] `obs_protocol.urdf_refs` 用正则 `<mesh filename="…"` 匹配：**单引号或属性顺序一变，网格就不在锁里**，改网格也不报红 | 夹具 URDF 写成 `<mesh name='m' filename='…'/>` 后：`the lock does not cover the mesh the urdf names: [...]`、`changing a mesh the urdf names was not reported`、`a single-quoted mesh reference was not parsed: []`、`an unparseable URDF was answered with an empty reference list` | 改用标准库 XML 解析（按 localname 找 `mesh`，与引号/属性顺序/命名空间无关）；文件存在但解析失败 ⇒ `ProtocolError`——"没解析到"不得被写成"这具身体没有网格" |
| 2 | [P2] 隔离检查用 `_VERSIONS.glob("*/*.urdf")`（旧位置）发现"有 urdf 但无声明"的家族 ⇒ **机体在自己的目录里的家族整族漏检** | 退回旧扫描后夹具报 `an active family whose tree declaration is missing was not reported`（gamma 的机体在 `assets/gamma/b2/`、没有 `versions/gamma/gamma.urdf`，旧扫描看不见它） | 改为**从活跃配方发现家族**（活跃线的 dev yaml），要求每个这样的家族存在 `versions/<family>/assets.json` |

**反证方式**：修好之后把每处修复**临时回退**（P1 连 `re` 导入一并恢复、P2 退回旧扫描），确认上表每条断言都会失败，再恢复修复。两处反证均实测成立——这也是本轮把事项从 `done` 退回 `open` 的原因：主体实现通过，不代表这两条路径被覆盖。

## 证据引用

- 代码落点：`rl_exp/tools/verify/check_dr_parity.py`（`_lock_files`/`_current_body`/`check_asset_locks`/`check_asset_isolation`/`check_body_swap` + 六个 `_self_test_*`）、`rl_exp/tasks/obs_protocol.py`（`urdf_refs`/`resolve_urdf`/`resolve_body`/`body_for_task`）、`rl_exp/tools/verify/check_recipe_registry.py`（`versions` 形状 + `effective_status`）、`rl_exp/tools/verify/test_recipe_registry_gate.py`、`rl_exp/versions/lines.json`、`rl_exp/tools/runrecord/lifecycle.py`、`rl_exp/tools/verify/check_version_docs.py`、`rl_exp/tools/verify/check_joint_layout.py`、`rl_exp/tools/verify/check_contact_ownership.py`、`rl_exp/tools/pipeline/declare_family.py`。
- 规则：`.codemaker/rules/versioning.mdc` 越级段。
- 相关记录：`2026-09-28-lizard2-foot-hull-and-asset-isolation.md`（触发本项的换代事实）、`2026-09-30-lizard2-v1-body-gap.md`（v1 缺口）。
- 事项：`work/` 下的 `body-swap-and-version-retire`（活跃或已关闭；关闭时其 `outcome` 记录最终状态）。

## 未覆盖边界

1. **演练是夹具内的，真实家族的换代仍未发生**：第一次真做时按本文档第四节与事项 `outcome` 的顺序走，并把读数回填本节。
2. **两个需要仿真器的调用方未实跑**：`check_joint_layout.py` 与 `check_contact_ownership.py` 已改为共用 `obs_protocol` 的解析器、通过语法编译，但本轮只做离线检查，**没有在仿真里跑过**（它们需要 IsaacLab 应用与资产）。
3. **活跃锁的手工伪造仍无自动判据**：离线闸门做的是摘要比对与必需集合覆盖；已训版本可另在 run 侧用 `asset_digest` 比对。
4. **无活跃消费者的家族整族跳过隔离检查**：旧家族 `lizard` 的 URDF/消费树分歧不再被打印，其处置归 `work/active/asset-tree-per-family.md`。
5. 不覆盖资产清理的时机与授权（删锁 ≠ 删资产），也不覆盖两具身体并行训练的隔离方案。
