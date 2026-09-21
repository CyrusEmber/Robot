# obs 协议声明与双源闸门：离线契约、live 实测、宽度批准（2026-09-16 → 2026-09-18）

## 适用范围

本记录搬运 `rl_exp/versions/lizard/ACCEPTANCE.md` 的以下旧节：

| 旧节 | 主题 |
|---|---|
| §3.1 | obs 协议声明与双源闸门（离线，2026-09-16）+ 结构性风险处置（review 后，第 8–11 条） |
| §3.1e | 真跑：live obs 契约（2026-09-17，**部分完成**）+ 两个发现的处置 |
| §3.1e 补账 | 家族 8 条协议的宽度实测与批准（2026-09-18） |
| §3.1a 追加 | 批准的宽度必须交代"谁断言的"（2026-09-18） |

**本记录内部的前后作废关系（读结论以此为准，被作废的旧句保留作留痕）**：

- **§3.1e 补账 的边界①（"协议 `digest` 只覆盖 `groups`，宽度靠 `dims_digest` 自钉" 被列为敞口）
  被 §3.1a 追加 纠正为"不是洞，是分工"**（协议身份只该由布局决定，否则"同布局不同宽度"无法表达；
  且反证在跑）。那条边界里的 ②（"生成 + 人工审批"仍是社会控制）**不变**。
- **§3.1e 的两次"部分完成 / 未通过"读数被后续补账逐步关掉**：家族宽度（当时"v0 家族宽度仍无人量过"）
  由 §3.1e 补账 关掉；joint 序判据由用户拍板定为"live == 已钉实测序"；parkour 退役线的构造失败
  **不是**本主题的修复（处置是标记退役）。
- **§3.1 的"声明不参与 cfg 构造 / 三张手抄表与声明是同一身份的两处"在本记录内一直未合口**：
  用户已定"要合"，合口的身份与代价见 §3.1 第 11 条；**落地须在 builder 改动静下来之后、一次落**
  —— 该动作归 `acceptance/records/2026-09-16-lizard-layout-migration-lifecycle.md` 之后的入口批次，
  本记录内始终是开项。
- **§3.1 第 9 条（退役）的第一版结论被判"证据越界"并重写**：上一版只证明了"声明里没有该任务时聚合门
  不崩"，却写成"退役已验证"；现按端到端反证重写（见该条）。

**读本记录须知的通读口径**：历史记录里的 `[N]` 是**当次运行编号**，不是闸门身份，套件总条目数受
`MAX_CHECKS` 棘轮管（本记录横跨 42 → 45 条条目）⇒ 各节的成功行读数**只在当日 commit 上成立**；
「已修」与「仍是缺口」并存时，作废句一律从作废它的那节读。

## 验收条件

### §3.1 前提与范围

依 `ARCH_PLAN.md` v0.21「Step 3 施工件表」。本片**只做离线段**：几何一致性、导出校验、蒸馏不在内
（记未执行）。全程不碰并行批次的写点，提交按路径限定。

### 闸门的判据形状（跨节一致）

| 层 | 判据 |
|---|---|
| 静态闸 | `check_obs_protocol.py`：声明的协议身份（key = 自身 `groups` 摘要前 12 位）与**冻结 golden** 双向覆盖 |
| live 闸 | `check_obs_protocol.py --live`：同一个声明对**实构的** cfg / 真 env manager |
| 宽度 | 协议 `digest` **只覆盖 `groups`**；宽度由 `dims_digest` 自钉，并在 `check_anchors` 里要求**每条带已批宽度的协议带非空 `evidence`**（指明那次实测/那条记录） |
| 人工面 | 锚点文件**闸门只读不写**：*a new or edited protocol stays red until a human writes its digest here* |

## 结果

### §3.1 落地（件号 → 产物 → 提交）

| 件 | 产物 | 提交 |
|---|---|---|
| 3.1a | `versions/obs_protocols.json`：36 任务 → 11 协议身份，**key = 自身 `groups` 摘要前 12 位** | `6742a64` |
| 3.1a′ | `versions/lizard/obs_protocol_anchors.json`：已审 `digest`/`label`/`dims`/`purpose`，闸门只读不写 | `6742a64`、`5d4cb38` |
| 3.1a 读者 | `tasks/obs_protocol.py`（纯 stdlib；脚序由 extero 项名派生） | `6742a64` |
| 3.1b | `tools/verify/check_obs_protocol.py` + `test_obs_protocol_gate.py`（20 例反证） | `f20a568` |
| 3.1c | `check_obs_layout.py`／`test_cfg_snapshot.py`／`teacher_smoke_runner.py`／`teacher_smoke.py`／`parkour_smoke.py` 改读声明 | `6ccfe2f`、`5d4cb38` |
| 3.1d | `manifest.py::recipe_ref` 记协议身份 + 已审摘要 + 宽度（与实构 `obs_layout_digest` 分开命名） | `38d80a6` |
| 3.1f（离线半） | `test_teacher_networks.py` 脚序标记输入 | `be89bc5` |
| 3.1g | clip/scale/噪声**数值**入声明（非"有无"） | `6742a64` |
| 3.1h | `OBS.md` 补 v13/v14/v15 行与真源注记 | `53c0d42` |
| 套件挂载 | `[42]/[43]`（离线半区；`--live` 归真跑窗口） | `a7e2b27` |

### §3.1 检查与结果（本机实跑）

```
check_obs_protocol.py             11 protocols | 36 tasks | golden 36 | live 0   → 与 golden 一致
check_obs_protocol.py --live      golden 36 | live 36                          → 两来源一致
test_obs_protocol_gate.py         OBS_PROTOCOL_GATE_OK（20/20）
check_obs_layout.py               OBS_LAYOUT_OK（顺序/脚序来自声明）
test_cfg_snapshot.py              CFG_SNAPSHOT_OK（脚序来自声明）
pytest test_teacher_networks.py   8 passed
test_run_manifest.py              RUN_MANIFEST_TEST_OK
check_suite_shape.py              SUITE_SHAPE_OK（改套件后）
```

**关键反证（每条都真红）**：交换两个 term（报 `same members, different order`）／交换两个组（报组序）／
翻转 `enable_corruption`／`dropped_terms` 加一项／未审锚点／key 与内容脱钩／golden↔声明双向覆盖缺失／
`--only` 过滤不掩盖范围内问题。

**3.1f 的能力证明**：把 `teacher_networks` 的 reshape 临时改成 point-major，测试报
`AssertionError: marking foot 0 (lf) moved latent segments [0, 1, 2, 3]`（1 failed）；改回后 8 passed，
且该文件 `git diff` 为空。这正是"维度全对、语义全错"的错法。

**已装事实**（声明不再是 stand-in）：v14 teacher cfg 实测 `obs_protocol=6cd53ec273dc`、
`obs_protocol_dims={proprio:90, extero:208, priv:83}`，与本次会话实构的 `obs_layout_digest` 并列记录。

### §3.1 本片修正（均由反证或实测抓到）

1. **"有无"不是事实**：首版把噪声/clip 记成存在性，"改一个 sigma"仍为真 ⇒ 改为记**值**（11 个 key 全变，锚点重批）。
2. **重批必须先自证是表示变化**：重批锚点前对新旧声明做结构对比（`tasks 36/36，structural drift: none`），确认无 term/顺序/dropped/flag 变化，才写新摘要；理由写进锚点注记。
3. **未测宽度必须抛错**：`dims_for` 对未批协议直接 `ProtocolError`。写 parkour 时当场被拦（PLAY 身份单独成身份、未批宽度），而非给出 0 或默默跳过。
4. **无向声明补造入口**：v7/v9/v15 目录存在但无注册入口，闸门按"有历史目录、无注册入口"登记，缺号不补造。
5. **套件提交不卷走并行批次**：工作树含他人的在飞重写 ⇒ 只提交索引（`hash-object -w` + `update-index --cacheinfo`），实测 `1 file changed, 3 insertions(+)`，其重写保持未暂存。
6. **宽度原先没有任何完整性保护**（自查）：协议 `digest` 只覆盖 `groups`，而 `dims` 存在锚点里 ⇒ 原地改一个宽度既不红也无人断言（smoke 只在真跑时读它）。现宽度由 `dims_digest` 自钉，并加结构性规则（组名必须真实存在且 live、值为正整数、同一协议**要么全填要么全空**）；补 6 例反证：原地改宽度、缺 `dims_digest`、未知组名、`True` 当宽度、半填、以及"是否存在多组协议可供该规则测试"的存在性检查（否则规则会静默不被测）。
7. **假红地雷**（自查）：`check_obs_layout` 的 v3/v4/v5 段原共用一份从 **v12** 取的顺序常量 ⇒ 只改 v12 的布局会误红 v3/v4/v5，而该文件在 pre-commit 里。实测证据：`v12-only change: constant still == v3 terms → False`，而 `v3 own declaration unchanged → True`。现各段按自己的 task id 取（v3/v4/v5/v12 各一份），脚序也改为 `feet_for` 派生。

### §3.1 边界（**不得**据本节宣称）

- **真 env 未跑**：3.1e（实际 manager 的逐 term 维度、最终张量维度、实际 joint/body 名与索引序）与 3.1f 真跑半、以及 `--live` 入套件 —— 全部**未知**。（3.1e 后为部分完成，见下。）
- **v0 家族（flat/rough/curriculum）宽度为空**：无真跑量过，无人断言。（后由 §3.1e 补账关掉。）
- **声明不参与 cfg 构造**（与并行批次写点隔离的取舍）：装配事实仍在代码，`components.observations` 的三张表与声明是同一身份的两处，现由 `[8]` + `[42]` 互钉。**用户已定"要合"**，合口的身份与代价见第 11 条（不需要新加身份参数；合口后 `--live` 退化为"声明 → 配置"的转换一致性检查，3.1e 变承重）—— 落地须在 B 的 builder 改动静下来之后、且一次落。
- 几何一致性、导出前协议校验、蒸馏数据 manifest = **未执行**。
- `OBS.md` 的 v15 行只声明"有目录、无入口"，不声明其布局。
- 本节为**离线段**通过，**不得**称为"Step 3 全部通过"。

### §3.1 结构性风险处置（review 后，2026-09-16）

评审列出三条结构性风险，当场修两条、第三条记敞口：

8. **锚点路径写死家族名**（已修，`415a8bf`）：声明是**全仓**的（闸门 glob 所有线的 golden），锚点却放在 `versions/lizard/` 下 ⇒ 第二个机器人家族落地时要么改代码、要么把别家的协议塞进蜥蜴目录。现移到 `versions/obs_protocol_anchors.json`，与它钉的文件同层，也与 `recipes.json`/`lines.json`/`cfg_baselines.json` 一致（"钉与被钉同层"）。重生成声明只动了 note 一行，**key 与全部已审摘要不变**，两半区仍 36/36。

9. **退役：前版结论越界，现按端到端反证重写**（首版 `ef47d0c`；完整反证与读者修复随本节同批提交）：上一版只证明了"声明里没有该任务时聚合门不崩"，却写成"退役已验证"—— **证据越界**。真正的退役形状是：保留历史声明与锚点 + `lines.json` 标 retired + 撤掉注册 + live 配置不可用。
   **完整反证（跑真实聚合入口，非注入答案）**：`lines.json` 把 `lizard/main` 标 retired、注册表去掉 `Lizard-Rough-v3` 与 `-Play-v3`、从 `teacher_env_cfg` 删除 `LizardRoughTeacherEnvCfg_V3`，然后：

```
aggregate layout gate   exit 1   SEGMENTS_OBSOLETE: ['LizardRoughTeacherEnvCfg_V3']
                                 "a deleted recipe class means the segment covering it must be
                                  removed or re-pointed; no segment was run, so nothing here
                                  has been checked"
protocol gate（离线半）  exit 0   golden 36 | live 0
protocol gate（--live）  exit 0   golden 36 | live 34（退役的两个任务按历史留存、不再构造）
声明与锚点              退役任务仍在册；其协议仍有已审摘要
```

   为此聚合门改两处：类名导入改 `_resolve`（删类不再拖垮整个模块的导入），并加 `SEGMENTS_OBSOLETE` 前置 —— **具名拒绝**而非 traceback，且明说"什么都没检查"（不许把未跑的段当成通过）。
   **反证当场抓到的真缺陷**：`retired_lines()` 的 `path` 原是**默认参数**，导入时绑定 `LINES`，补丁对它无效 ⇒ `--live` 仍红。根因是单测**直接注入** `retired` 集合、从没走过读者。已改为调用时解析，并补两例直接喂临时 `lines.json` 的反证（读者读索引、读者驱动覆盖规则）。
   **仍未覆盖（不得据此宣称）**：退役后**要不要删掉该段的代码**是维护动作，闸门只能具名提醒、无法验证；本反证也无法模拟"段代码已删"的状态。单配方 smoke 与网络单测仍依赖其配方存在 —— 那对它们是依赖，不是缺陷。

10. **"生成 + 人工审批"仍是社会控制**（敞口，未修）：闸门能查的全是**自洽**（key=内容摘要、digest=锚点、dims=dims_digest），三件事同一条命令都算得出来 ⇒ 重新生成 + 重批可以不留"有人看过"的痕迹。既有先例是 golden 的 `--update --reason`。
   **判据更正（评审）**：`approved_rev` 只能提供**追溯**，不能证明审核发生。更稳的判据是**"审批绑定的内容摘要是否仍等于当前受审内容"**（相等即未被改写）；`rev` 用来定位来源，`purpose` 用来解释改动原因。仅凭"HEAD 已前进 + golden 有变动"发警告会混入无关变化，也可能漏掉审批范围之外的实际影响。故将来动作 = 锚点记 `approved_rev`（追溯）+ `purpose` 必填（原因），**硬红判据仍是摘要相等**。

11. **合口的身份问题：先查再断**（评审纠正上一版的越界结论）：上一版断言"必须新增身份参数"，依据是 TRAIN/PLAY 是两个身份、v0 家族 `version` 全为 `null`。查过后这两条都**不足以**推出该结论：
    - `components.observations` 只有**一个**调用点（`teacher_env_cfg.py:730`，传 `params_version`），**v0 家族根本不走它**（走 `lizard_env_cfg`/`rough_env_cfg`/`curriculum_*`）⇒ `version=null` 与组件寻址无关；
    - v1/v2 的 TRAIN/PLAY 差异（corruption/噪声）由**其后的 play 接线**施加（`play_utils`），不在组件里 ⇒ 组件按 `params_version` 寻址时两者形状相同，只有在**协议身份**层面才分家。
    ⇒ 合口**不需要**新造身份参数；需要的是把既有的"版本 → 该版本 TRAIN 侧布局"映射讲清（声明有 `tasks[t]["version"]`，`recipes.json` 有 `legacy_task_version`），并保证 **play 接线仍是唯一施加 PLAY 噪声/corruption 的地方**（否则"版本 → 布局"不再良定义）。
    措辞更正：合口后 `--live` 不是"自己比自己"，准确说是**退化为"声明 → 配置"的转换一致性检查**，不再提供独立正确性证据；届时唯一独立来源是冻结 golden，**3.1e 真 env 变为承重**。

### §3.1e 真跑：live obs 契约（2026-09-17，**部分完成**）

命令（本机实跑，headless）：

```
python rl_exp/tools/verify/obs_protocol_live.py --headless \
  --tasks Lizard-Rough-v14 Lizard-Rough-Play-v14 Lizard-Parkour-Climb-v1 Lizard-Velocity-Flat-v0
```

结果：`OBS_PROTOCOL_LIVE_FAILED (1 problem(s), 3 warning(s))`

**通过的部分**（读的是 live manager，不是构造物）：

```
v14 TRAIN / PLAY   proprio=90 extero=208 priv=83，组序与逐 term 序与声明一致，张量 (2, width) 一致，4 只脚的 <foot>_foot body 都在
Velocity-Flat-v0   policy=90（宽度**未批**，按未批标记，不冒充通过）
```

**发现 1（WARN，判据未定）**：live articulation 的关节**序列**与配方文档的 `joint_order` 不同（同一 26 个关节）：

```
live     chest_yaw, tail1_yaw, rr_haa, rl_haa, chest_pitch, tail1_pitch, rr_hfe, rl_hfe, …
declared chest_yaw, chest_pitch, neck_yaw, neck_pitch, rf_haa, rf_hfe, rf_kfe, rf_foot, lf_haa, …
```

训练侧 obs/action 走的是 **live articulation 序**；文档里的 `joint_order` 是 **URDF 树序**
（`export_ue.py` 拿它比对 URDF，且它进 `ue/lizard_ue.json`）。既有闸门只把文档与 usda 关节的**集合**
比对（`check_dr_parity.py:277` 用 `set(...)`），**没人比过顺序**。故：要么文档顺序只是部署侧约定
（则须写明 UE 按名装配，且把 live 序钉成训练契约），要么两者本应相等（则是部署契约的真错）。
**判据待用户定，本轮不判通过也不判失败**。

**发现 2（FAIL，非本批文件）**：`Lizard-Parkour-Climb-v1`（`lines.json` 里 `status: active`）**根本构造不出 env**：

```
ValueError: Not all regular expressions are matched!
  rear_.*: []   tail_.*: []        （.*_haa_joint / .*_foot_joint / neck.*_.* 均有匹配）
```

原因：`versions/lizard/parkour/v1/parkour_params.yaml` 的 `actuators.spine.joint_patterns`（:46-47）与
`default_joint_pos`（:21-22）仍用 **v8 之前的命名** `rear_.*` / `tail_.*`，而当前资产已改名 `tail1_yaw` 等
⇒ 该 actuator 组没有任何关节，IsaacLab 直接抛错。**这与 Step 3 无关**，但它是真跑的产物：
**离线闸门全绿，而一个 active 线的任务连 env 都建不起来**（`parkour_smoke.py` 能抓，但它不在套件里、需手跑）。

**边界（不得据本节宣称）**

- 3.1e **未通过**：只跑了 4 个任务；parkour 因构造不出 env 已退役（见下）；joint 序判据已定为"live == 已钉实测序"（见下）；v0 家族宽度仍无人量过。
- 只跑了 4 个任务，**不代表其余 32 个**；一次真跑不覆盖其他协议。
- 本节证据只到"live manager 与声明一致 + 上述差异"，不含推理等价。

**发现 2 的处置（用户拍板 2026-09-17）**：**parkour 标记退役**（`versions/lines.json` → `revision: 3`）：
`status: retired` + `retired_at: 2026-09-17` + 原因（v8 改名后 `joint_patterns`/`default_joint_pos` 失配，
无法构造 env）+ `successor: null`。
复核（本机实跑，全绿）：`check_recipe_registry` `lifecycle consistent`（`revision=3 entries=3`）·
`test_lifecycle_gate` `LIFECYCLE_STARTUP_OK`（退休线拒绝新训练：`refused to start: retired line: refusing new_train`）·
`test_launcher` `LAUNCHER_OK` · `check_recipe_map --bind-config` 36/36 ·
`check_cfg_lock` `CFG_LOCK_OK (36 tasks, 3 line(s))` · `check_obs_protocol --live` 36/36 ·
`check_obs_layout` `OBS_LAYOUT_OK`。

> **2026-09-17 收缩**：上面提到的 `revision: 3` 这个字段已在同轮删除（无行为读者，身份由内容摘要给出，
> 详见 `acceptance/records/2026-09-17-lizard-entry-switch-and-declaration-gap.md` 的「生命周期收缩」节）；
> 当时把 parkour 标为 retired 这件事本身不变，`status`/`retired_at`/`reason` 三项就是它的全部证据。

**边界**：退役是**权限事实，不删内容** —— parkour 的任务仍在注册表、golden 与冻结目录保留
（"已发布内容不改写"）。要连注册一起撤掉是另一次动作，本轮**未做**，也不影响上述通过项。

**发现 1 的处置（用户拍板 A，2026-09-17）**：**钉住运行序**，判据改成"不该断言 live == 配方文档"。

- **落点**：新文件 `versions/lizard/joint_order_runtime.json`，**按资产键**（`assets["assets/lizard/lizard.usda"]`），记实测关节序 + 测量任务 + 日期 + 理由。写它只能由 `obs_protocol_live.py --pin --reason '<why>'`（刻意行为，不是刷新）；读它只有 `rl_exp.tasks.obs_protocol` 一处（`runtime_joint_order` / `joint_order_digest`），避免检查与写入各读一份。
- **判据**：live 序 == **已钉实测序** ⇒ 硬红（不等就 FAIL 并列出两个序列）。**配方 `joint_order` 与它不等只出 WARN** —— 两者服务不同事（URDF/部署序 vs 训练 I/O 序），相等是巧合不是义务，断相等会逼人改坏部署契约。
- **覆盖**：`--all-tasks` 只读文件、不起 sim，实测 `OBS_PROTOCOL_LIVE_OK (36 declared task(s), all pinned)`（36 个声明任务全部落在同一资产上，故一处实测覆盖全部）。
- **run 记录**：`manifest.recipe_ref` 增 `runtime_joint_order_digest`（v14 实测 `416640b4d16af072…`）⇒ ckpt 可追到"它在哪个关节序下训练"。
- **反证（本机实跑）**：把钉住值里 `chest_yaw` 与 `tail1_yaw` 互换 ⇒

```
FAIL Lizard-Rough-v14: live joint order differs from the measured one for 'assets/lizard/lizard.usda'
OBS_PROTOCOL_LIVE_FAILED (1 problem(s), 1 warning(s))
```

　换回后 `OBS_PROTOCOL_LIVE_OK`。即：钉住值是承重的，不是装饰。
- **导出侧已闭合（2026-09-17）**：`lizard_ue.json` 现在同时带**两种序**并写明用途 —— `joint_order`（URDF 树序，保留 + `joint_order_note` 标注它不是装配序）与 `joint_order_runtime`（实测运行序）+ `joint_order_runtime_digest`，`meta.obs_assembly` 写明"装配必须按关节**名**，或用 `joint_order_runtime`"。**导出器没有实测序就拒绝导出**（不写任何文件）：实测 `exit code 1` + `ValueError: no measured runtime joint order for 'assets/lizard/lizard.usda'`，且导出产物逐字节未动。
  导出器**不 import** `rl_exp.tasks`（它在部署机上跑，不该拖进训练栈），因此它是直读数据文件的第二处读取 —— 这一处重复由闸门机器核对：`check_obs_protocol` 增 `check_export_agreement`，比对导出产物与实测序及其摘要（4 例反证：序过期、摘要过期、缺 `meta.asset`、干净）。

### §3.1e 补账 · 家族 8 条协议的宽度实测与批准（2026-09-18）

**性质**：§3.1e 的边界行留了一条旧账 ——"v0 家族宽度仍无人量过"；本条把它关掉。

| 项 | 内容 |
|---|---|
| 缺口（先说清是什么） | `versions/obs_protocols.json` 里 8 条家族任务**都已声明**（协议摘要 + `line`），但 train/play 共 4 个协议在 `versions/obs_protocol_anchors.json` 里是 **`"dims": {}` 且无 `dims_digest`** —— 该文件自己的口径：**"empty = no real run has asserted them yet"**。别的协议都非空 ⇒ 缺的是**一次真跑断言**，不是推导 |
| 实测 | `obs_protocol_live.py --headless --tasks`（8 条家族任务，2 envs）⇒ `OBS_PROTOCOL_LIVE_OK (8 task(s), 8 warning(s))`、**0 problem**。宽度：flat / curriculum-flat 两族（train 与 play 各有自己的协议）= `policy=90`；rough / curriculum-rough 两族 = `policy=225`。当时四行都带 `(unapproved)` 标记 |
| 批准（人工面） | 按该文件的规矩（闸门只读不写：*a new or edited protocol stays red until a human writes its digest here*）：写入 4 个协议的 `dims` + `dims_digest`，后者由**闸门自己的** `check_obs_protocol.dims_digest` 算出、不手抄。写入前先证**序列化不动点**（整文件重排不动一个字节），以免"批个宽度"顺手改动别的字节 |
| 事后复核 | 静态闸门 `OBS_PROTOCOL_GATE_OK`（declaration matches the goldens）；其反证 **38 例全 `ok`**（含 `dims/*` 五例：原地改宽度、缺 `dims_digest`、未知组名、`True` 当宽度、半填）；**复跑实测**：同 4 条任务显示 `policy=90 / 225` 且**不再带 `(unapproved)`** ⇒ 批准值 == 实测值 |
| 改动面 | `versions/obs_protocol_anchors.json` 4 条（`git diff --numstat` = `16 4`，全是这 4 条的 `dims`/`dims_digest`）+ 本条 |
| 旁证 | 全量套件 `ALL_OFFLINE_CHECKS_PASSED (44/44)` |

**边界**：本条只关"家族宽度未实测"这一项。§3.1a 的两条敞口**不变**：① 协议 `digest` 只覆盖 `groups`，
宽度靠 `dims_digest` 自钉；② "生成 + 人工审批"仍是社会控制（重生成 + 重批可以不留"有人看过"的痕迹，
既有先例 = golden 的 `--update --reason`）。家族 4 条仍**无 `diff.json`**（硬 A only）。
→ 上面 ① 的措辞由下面「§3.1a 追加」纠正；② 不变。

### §3.1a 追加（2026-09-18）：批准的宽度必须交代"谁断言的"

**性质**：处理 §3.1 第 10 条敞口（原文："生成 + 人工审批仍是社会控制（敞口，未修）……重新生成 + 重批可以不留'有人看过'的痕迹。既有先例是 golden 的 `--update --reason`"）。

| 项 | 内容 |
|---|---|
| 先纠正上一条的措辞 | 该节列的两条里，① "`digest` 只覆盖 `groups`" **不是洞**：宽度由 `dims_digest` 自钉，且反证在跑（`dims/in-place-edit` 原地改宽度 ⇒ 红、`dims/no-approved-digest` 缺摘要 ⇒ 红）。它是**分工**——协议身份只该由布局决定（否则"同布局不同宽度"无法表达）。本条只修 ② |
| 修法（对齐先例，不假装能证明"有人看过"） | 每条**带已批宽度**的协议必须带非空 `evidence`：**指明**那次实测/那条记录；带 `evidence` 而无宽度 = 红（与"要么全填要么全空"同精神）。规则落在 `check_obs_protocol.check_anchors`；反证 **6 → 8 例**（新增 `dims/no-evidence`、`dims/evidence-without-widths`，两者皆 FIRES）；文件 `note` 同步写明该义务 |
| 数据 | 11 条带宽度协议全部补 `evidence`（无一条可省）：4 条家族引 2026-09-18 那次真跑（`OBS_PROTOCOL_LIVE_OK`、8 任务 0 problem）+ 本节；7 条教师侧引该文件 note 的 2026-09-16 重批（"diff 仅表示形式"）——**只引仓里已有的记录，不补造历史**。家族 4 条原为空的 `label` 顺带补齐 |
| 证据 | `OBS_PROTOCOL_GATE_OK`（`protocols: 11 | tasks: 36`）· 反证 8/8 FIRES · 全量套件 `ALL_OFFLINE_CHECKS_PASSED (45/45)` |

**边界**：这是"**留下可跟的痕迹**"，不是"证明有人看过"——机制上仍可自洽地重生成 + 重批。它把 golden
先例（`--update --reason`）的**强度**搬到这一面，并在文件里写明义务；更强的东西（签名/审批人身份）本轮不做。

## 证据引用

- 声明与锚点：`rl_exp/versions/obs_protocols.json`、`rl_exp/versions/obs_protocol_anchors.json`、
  `rl_exp/versions/lizard/joint_order_runtime.json`、`rl_exp/tasks/obs_protocol.py`。
- 闸门：`rl_exp/tools/verify/check_obs_protocol.py`（含 `--live` / `check_anchors` / `check_export_agreement`）、
  `test_obs_protocol_gate.py`、`check_obs_layout.py`、`test_cfg_snapshot.py`、
  `obs_protocol_live.py`（`--pin` / `--all-tasks`）、`check_dr_parity.py:277`（集合比对）、
  套件挂载 `[42]/[43]`。
- 真跑命令：`python rl_exp/tools/verify/obs_protocol_live.py --headless --tasks …`
  → `OBS_PROTOCOL_LIVE_FAILED (1 problem(s), 3 warning(s))`（2026-09-17）／
  `OBS_PROTOCOL_LIVE_OK (8 task(s), 8 warning(s))`（2026-09-18 家族）；
  反证：把钉住值里 `chest_yaw` 与 `tail1_yaw` 互换 → `OBS_PROTOCOL_LIVE_FAILED (1 problem(s), 1 warning(s))`。
- 导出侧：`ue/lizard_ue.json`（两种序 + `meta.obs_assembly`）、导出器 `export_ue.py`。
- 相关记录：合口条件（三张手抄表 vs `obs_protocols.json`）落点在
  `acceptance/records/2026-09-16-lizard-builder-hard-a.md` 与
  `acceptance/records/2026-09-17-lizard-entry-switch-and-declaration-gap.md`；
  parkour 退役线的生命周期字段变化在后者。

## 未覆盖边界

- **未闭合项（跨节保留，仍是开项）**：
  - **社会控制**（§3.1 第 10 条，敞口**未修**）：闸门能查的全是**自洽** —— key=内容摘要、digest=锚点、
    dims=dims_digest 三件事同一条命令都算得出来 ⇒ **重新生成 + 重批可以不留"有人看过"的痕迹**。
    §3.1a 追加 只把它变成"**留下可跟的痕迹**"（`evidence` 必填 + 摘要相等为硬红），
    **不是**"证明有人看过"；签名/审批人身份本轮不做。
  - **合口未做**：`components.observations` 的三张手抄表与声明是同一身份的两处（现由 `[8]` + `[42]` 互钉）；
    用户已定"要合"，落地须在 builder 改动静下来之后、一次落，且合口后 `--live` **退化为转换一致性检查**，
    **3.1e 真 env 变为承重**。
  - **几何一致性、导出前协议校验、蒸馏数据 manifest = 未执行**。
  - **退役后要不要删掉该段的代码是维护动作**，闸门只能具名提醒、无法验证；反证也无法模拟"段代码已删"的状态。
- **真跑覆盖的边界**：
  - 3.1e 只跑了 4 个任务（后加家族 8 条），**不代表其余**；一次真跑不覆盖其他协议。
  - **`--live` 当时不入套件**（归真跑窗口）；`--all-tasks` 只读文件、不起 sim（那**不是** live 证据）。
  - joint 序：**配方 `joint_order` 与实测序不等只出 WARN**（URDF/部署序 vs 训练 I/O 序，相等是巧合不是义务）。
  - parkour 退役线：**退役是权限事实，不删内容** —— 任务仍在注册表、golden 与冻结目录保留；
    要连注册一起撤掉是另一次动作，本轮未做。
- **闸门能力的边界**：闸门能查的全是**自洽**；`OBS.md` 的 v15 行只声明"有目录、无入口"，不声明其布局；
  本节为**离线段**通过，**不得**称为"Step 3 全部通过"。
- **口径边界**：历史 `[N]` 是当次运行编号而非闸门身份；反证例数（20 → 38 → 8）与套件条目数
  （42 → 45）只在**当日 commit** 上成立。
