# 机体 precheck：接触语义、角色证据与计划缺口修复

## 适用范围

用户在独立复核 `robot-body-precheck.md` 的实现与计划后要求“修复计划缺口”。本轮修复相切判定随共同根位姿变化的问题，新增接触权限与外部角色证据消费，显式挂出蜥蜴样例的角色/全实体缺证项，并把 work 的责任、方法与变化复验路由具体化。不接管 A/E 共用 FK、三角算法或生成器，不修改正式资产、配方、默认驱动或 CI 清单。

原最小入口记录 `2026-10-20-robot-body-precheck-entry.md` 保留其绑定版本与历史判定；本记录只覆盖当前修订，不覆盖完整机体、第二真实构型或整个 work 关闭。

## 验收条件

- 相同相切几何施加共同根平移/旋转，及由上游关节旋转整个相切实体对，零余量结果保持一致；真实重合/穿透仍失败，正工程余量不被全局豁免。
- `self_collision.params.contact_pairs` 仅免该对的正工程间隙，仍检查实体相交；和整对排除冲突时拒绝。保留旧 `body.allowed_pairs` 兼容行为，同时明确它是完整排除，不是接触验收。
- `role_consistency` 消费有 SHA256 和 URDF 身份的外部批准角色映射；同关节名但错误角色须失败，缺证、错源、漏关节、证据漂移不得通过。角色一致与物理实体随动分开报告。
- 真实蜥蜴实例显式列必需角色与源全实体姿态需求，缺证保留未判；不自行伪造证据、修改过滤或阈值来转绿。
- 既有回归与本轮真实反例通过；新反例先在修复前源码实跑失败，再在修后通过，并有可复读的同断言回退。work 保留全部真实验收未完动作。

## 结果

### 实现与数值边界

自碰撞改在机器人根坐标下消费真实 FK，地面、端点和源姿态仍消费世界坐标。零工程间隙增加实际网格面法向的分离平面证据：检查两个实体的全部顶点投影是否分离，不用凸包重叠推定穿透，也不靠放宽几何过滤修相切。

数值包络固定为 `64 × float64 epsilon × pair extent`，投影前将两实体共同减去首实体的首顶点以重定原点；它是浮点归一化/点积的分辨率说明，不是获准机械穿透 allowance。低于该数值尺度的特征不承诺区分。凹形或边缘接触若没有可找到的分离面法向，仍保留共用相交算法的保守结果；本轮不声称已实现任意非凸连接区域判定。新的触碰证据不改变正工程间隙的测量方法。

新增角色证据格式和支持契约唯一归 `body_precheck.py` 模块文档；角色文件一次读取，以已消费 bytes 核摘要并在后续绑定检查中重核路径。报告独立列 `role_semantics` 与 `source_pose_consistency`。外部角色映射只能证明适配与批准语义一致，不能证明真实轴/pivot 或网格随动；批准与独立来源仍须人审，不能复制适配到另一文件充当真值。

### 行为验证

- 修改测试后、修改实现前，`--plan_gap rotation/contact/roles` 各退出 1：分别命中共同变换相切误报、缺接触策略、缺具名角色证据消费。没有先改实现再假称“修前失败”。
- 修后完整测试退出 0，共 280 条断言：原有 252 条保持通过，新增共同根变换/上游关节旋转、接触不免穿透、其它实体对正余量、接触与排除冲突、错角色/错 URDF/漏角色/证据漂移及真实 CLI 消费反例。
- `--break_fix touching/contact_policy/role_semantics` 各退出 1，分别命中上游旋转后的相切、接触权限无法豁免正间隙、错角色被接受的同一断言；`--break_zero_aabb` 退出 1，原重合实体误放行反例仍有效。回退只改测试进程中的代码，不改正常源码。
- 完整离线套件退出 0：`ALL_OFFLINE_CHECKS_PASSED (37/37 in 49.7s, wave 229s/informational, jobs=6)`；含 work 格式、版本文档、输入绑定单一来源与原仓库检查，未增清单条目或改预算。`git diff --check` 通过。
- 首次提交前钩子在共享树 work 总量处拒绝：`180013/180000` 字节。仅去重本事项开头已被后方方法表与动作覆盖的说明，未删除未完动作、修改预算或关闭事项。重跑 `git hook run pre-commit` 退出 0，`static gates passed`；当时活跃总量 `179512/180000` 字节。两次日志分别为 `precommit.log`、`precommit_final.log`，不把首次失败改写为通过。

### 新上下文独立审查

不带执笔历史的 `/root/precheck_review` 对照实际差异、代码、配置、报告及日志审查，接受本次接口与计划切片，无本范围阻塞。审核者自行复跑完整测试，280 条断言通过；另将 `git show HEAD:rl_exp/tools/diagnose/body_precheck.py` 的修前源码加载到内存，运行同一 rotation/contact/roles 测试，三组均失败，未修改工作树。源码/配置/报告摘要均与下表匹配，实际报告的碰撞失败与新增必需缺证未被覆盖声明掩盖。

审核明确保留浮点分辨率、非凸接触保守判词、旧整对排除依赖人审、角色证据外部独立性，以及旧检查点不能替代新导出等限制。不批准完整机体、第二真实构型或 work 关闭；当前 work 继续 `in_progress`。同一只读审核上下文另核过收尾的 work 说明去重，确认全部动作、方法与判据仍保留，源码/测试/配置摘要未变，切片结论不变。后续仅回填验证和审查记录。

### 真实候选消费

实际 CLI 继续绑定原 `checkpoint_v3`，不混用 A/E 新正式导出。配置新增必需 `independent_role_semantics` 与 `full_source_entity_poses`，未填写并不存在的独立角色文件或全 link 源姿态。

CLI 退出 1，`status=fail`。中立与组合两姿态共检查 306 对，各保留 14 对相交/包含失败；限位与源端点通过。两姿态各新增两行 `not_evaluated`，独立角色与完整源实体姿态覆盖均为 `not_evaluated`。采样声明的 `whole_machine=pass` 不覆盖这些失败/未判，不是任务通过。连接相交仍须 A/E 按真实区域和需求解释，不能自动改为禁止机械穿透或全部排除。

### 输入与产物绑定

| 对象 | SHA256 |
|---|---|
| `rl_exp/tools/diagnose/body_precheck.py` | `7f0549f7c85f0cf165035cc7cf8d44d3072db78c5b0e45adc20a2dbff1adaeb3` |
| `rl_exp/tools/verify/test_body_precheck.py` | `43664e8ad50f3ab12720a3e3551736a11ab4f34275c11bbdcaff567821b2b122` |
| `rl_exp/tools/diagnose/body_precheck_lizard2.json` | `4e0485501ee5e277ab0e292e3974f5942d1ead287a245de5338828ce3a0ae1f5` |
| 本机 `rl_exp/out/body_precheck_plan_fix_20261020/lizard2.json` | `1c7039fbf0408e95b22203ac5e16e49c7c312d22b5fcfb70ae1bdb71d72eb868` |

报告保留实际 URDF/网格与共用消费者摘要；未改共用 FK/三角算法。本机日志与报告不承诺入仓。

## 证据引用

- 工作计划：`work/active/robot-body-precheck.md` 的方法映射、变化影响表与关闭条件。
- 原入口及旧报告：`acceptance/records/2026-10-20-robot-body-precheck-entry.md`。
- 本机日志：`rl_exp/out/body_precheck_plan_fix_20261020/` 下 `regression.log`、`lizard2.log`、`red_*.log`、`offline.log`、`precommit*.log`。

仓根执行，解释器由 `ablation_harness/host_paths.py --python` 解析；复验真实样例须使用不存在的报告路径：

```text
E:\IsaacLab\env_isaaclab\Scripts\python.exe -B rl_exp/tools/verify/test_body_precheck.py
E:\IsaacLab\env_isaaclab\Scripts\python.exe -B rl_exp/tools/verify/test_body_precheck.py --plan_gap rotation
E:\IsaacLab\env_isaaclab\Scripts\python.exe -B rl_exp/tools/verify/test_body_precheck.py --plan_gap contact
E:\IsaacLab\env_isaaclab\Scripts\python.exe -B rl_exp/tools/verify/test_body_precheck.py --plan_gap roles
E:\IsaacLab\env_isaaclab\Scripts\python.exe -B rl_exp/tools/verify/test_body_precheck.py --break_fix touching
E:\IsaacLab\env_isaaclab\Scripts\python.exe -B rl_exp/tools/verify/test_body_precheck.py --break_fix contact_policy
E:\IsaacLab\env_isaaclab\Scripts\python.exe -B rl_exp/tools/verify/test_body_precheck.py --break_fix role_semantics
E:\IsaacLab\env_isaaclab\Scripts\python.exe -B rl_exp/tools/verify/test_body_precheck.py --break_zero_aabb
E:\IsaacLab\env_isaaclab\Scripts\python.exe -B rl_exp/tools/diagnose/body_precheck.py --config rl_exp/tools/diagnose/body_precheck_lizard2.json --output rl_exp/out/body_precheck_plan_fixes_replay.json --max_cases 2
```

正常测试预期退出 0，回退模式预期退出 1，真实蜥蜴缺证/失败样例预期退出 1。原八种回退入口保留。

## 未覆盖边界

第二真实构型与自身任务、蜥蜴独立角色批准资料、逐轴/全实体源姿态、设计连接重叠区域判据及目标姿态/可达性方法仍未交付。当前样例不验证 A/E 新正式导出，不代表默认驱动、动力学、运行时、连续域、承重或行走合格。

原 `allowed_pairs` 保留既有整对排除行为，不能靠弃用提示阻止调用方误用；新接触声明与它冲突时会拒绝，真正任务验收仍须人审排除依据。数值分离面只解决其支持范围的接触，不提供工程穿透深度或局部连接区域裁剪。本轮计划缺口修订不关闭 work，也不恢复手工步态前置。
