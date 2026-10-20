# 机体 precheck：独立源几何样本接入与复用

## 适用范围

用户于 2026-10-20 明确：本地只有一种机体，也应继续推进 precheck 并记录复用落点，避免后续 AI 造轮子。本轮在原 `work/active/robot-body-precheck.md` 继续做可独立推进切片，不将另一真实构型缺席视为所有施工前置，不新建 work、下载资产或复制改名机体冒充第二构型。

接入既有保存重开的 Blender 枢轴/视觉样点，复用 `palm_spatial_probe.py:check_blender` 的测量方法，未导入其求解器，未重写 FK/碰撞或修改 A/E 共用核心。输入仍绑定原 `checkpoint_v3`，不混用正式新导出和旧证据。接口与完整源姿态、角色、连接判据保持独立。

## 验收条件

- `source_geometry` 在现有通用入口消费具名源快照，不固定腿数/轴数；完整 q/根工况与源快照一致，稀疏 q 只有显式零复位来源才展开。
- 源 JSON 按一次实际读取 bytes 核批准摘要；候选 URDF、保存 blend、实际消费视觉网格均核同身份，路径式消费者前后重核。源枢轴覆盖全部 link，源对象样点覆盖实际视觉资产，保留逐 link/对象读数及失败类别。
- 视觉格式只支持单个零变换、单位 scale 的三角 OBJ；拒绝重复 origin/geometry、顶点尾部非法字段，不能靠共享 reader 忽略不支持输入取得通过。
- 源样点通过不替代完整朝向、角色、真实实体归属、连接区域、可达域或动力学；必需缺证仍未判，失败碰撞不通过排除转绿。
- 同一反例修前失败/修后通过，真实原候选执行全已采快照；支持矩阵和格式归模块，拒错归现有测试，路由/接线顺序归复用指南，读数唯一归本记录。另一真实构型继续留作关闭前置。

## 结果

### 接入与真实消费

新增方法唯一落点为 `rl_exp/tools/diagnose/body_precheck.py` 的 `source_geometry_prepare` / `source_geometry_evaluate`。普通配置只绑定原源报告并映射工况，不复制生成全姿态“真值”。源 q 缺项依据原生成器每样本清空 `matrix_basis`，配置显式提供 `sparse_zero_reset` 与来源；不从未知样本自动补零。

同目录 `body_precheck_lizard2.json` 覆盖原全部 10 个快照：中立、四腿 twist 各 ±10°、组合。各例完整列 30 个可动关节；源每例 31 枢轴、36 对象对应 18 视觉资产、每对象 32 样点，共 11520 个样点。对象数不等于导出资产数，源索引不强制等于合并后的导出顶点索引；最近顶点比较不能证明一对一对应。

真实 CLI 写 `rl_exp/out/body_precheck_source_samples_checked_20261020.json`，退出 1、整体 `fail`。52 行中 22 pass、10 fail、20 not_evaluated：源几何 10 行通过，限位 10 行与两例源端点通过；自碰撞 10 行失败，角色和完整源姿态各 10 行仍必需/未判。共检查 1530 个实体对，未增加过滤。

源几何最大枢轴误差 `1.2280823e-6 m`、视觉样点误差 `1.9623268e-6 m`，低于原获准 `1e-5 m` 数值对照预算；不据读数倒推新阈值。39 项实际绑定为 build、URDF、blend、18 collision meshes 与 18 visual meshes。原 build 摘要实测仍为 `59473f8c…6f8`，探索摘要曾称漂移，已通过实际摘要纠正，未变更身份。

### 行为修复与验证

- 新需求 `--plan_gap source_geometry` 在实现前返回未知方法，回归退出 1；实现后源样点回归通过，`--break_fix source_geometry` 使同一错误样点断言重新失败。
- 首轮独立审核 `b6d31012-72c0-43b7-8dd3-908c009ea7f0` 实际复现两项假通过：重复视觉 origin/geometry 只读首项，视觉 OBJ 顶点多余字段被丢弃。新增 XML/OBJ 真实 `run()` 反例，先在修前源码运行分别红，再补数量保护与复用 `validate_obj()`。
- 修后完整回归退出 0：329 assertions，保留原 280 条；`--source_format xml`、`--source_format obj` 各 10 条通过。`--break_fix source_format` 配对应模式，两组同一断言均重新红；编译及 `git diff --check` 通过。
- 首次完整离线套件退出 1：work 新证据指针在记录创建前不存在，同时活跃总量 `180059/180000`；1 failed、28 skipped。没有把此跑改称通过，也未提高预算、取消或关闭事项。补记录后只精简本事项重复范围说明再复跑：退出 0，`ALL_OFFLINE_CHECKS_PASSED (37/37 in 39.0s, wave 180s/informational, jobs=6)`，活跃总量 `179422/180000`。文档一致性新上下文 `cb648a0a-a239-499c-b748-d8f33a888bbf` 核记录与 work，确认未丢未完动作；该审查仅读文档，不替代前述代码/证据审核。

### 独立审查

新上下文 `dd01b49d-82be-43dd-be2f-0d8531bd3e7f` 直接核当前代码、配置、报告和复用指南，实际跑 329 条回归、XML/OBJ 绿及保护撤回红；核 39 项身份、完整 q 与显式零复位、源对象/枢轴覆盖及 producer 保存重开行为。接受源几何与复用窄切片，无本范围阻塞；不批准机体、完整 precheck 或 work 关闭。审核未重跑真实碰撞扫描或全仓套件。原记录与本记录分别保留各自身份。

| 对象 | SHA256 |
|---|---|
| `rl_exp/tools/diagnose/body_precheck.py` | `4cb66406372a210c8dea92f795c97e8c44f0f4266d37746c995dca6037473248` |
| `rl_exp/tools/verify/test_body_precheck.py` | `b550122e9fa076f4cf5061bb60be0626d1ab11f02d8c475b038f9c18fa93fa94` |
| `rl_exp/tools/diagnose/body_precheck_lizard2.json` | `58902070d88fd8c9e764f83edb6cc9e2e283294f1335e5b31804c27e07ed6222` |
| 本机最终报告 | `9c751ff915bd4e291bd59433f60184c809b287aea419b3df0e90ec336a50b002` |
| 原 build | `59473f8c345dce48e8ee379c0972c928184f768be85afca948ac812a666fa6f8` |

## 证据引用

- 入口契约/源格式/支持范围：`rl_exp/tools/diagnose/body_precheck.py` 模块文档；样例接线同目录 `body_precheck_lizard2.json`。
- 方法拒错与破坏模式：`rl_exp/tools/verify/test_body_precheck.py`。
- 接入/复验顺序：`rl_exp/docs/leg_geometry_reuse.md`“通用 precheck 接入与复用”；`FILEMAP.md` 只指路，不复制实现或读数。
- 原源批准及容差：`acceptance/records/2026-10-14-lizard2-palm-spatial-trial-checkpoint.md`；历史入口/接触角色修订分别见 `2026-10-20-robot-body-precheck-entry.md`、`2026-10-20-robot-body-precheck-plan-fixes.md`。

仓根执行，解释器按 `ablation_harness/host_paths.py --python` 的本机输出选择；真实报告必须是不存在的新文件，本机产物引用不承诺入仓：

```text
E:\IsaacLab\env_isaaclab\Scripts\python.exe -B rl_exp/tools/verify/test_body_precheck.py
E:\IsaacLab\env_isaaclab\Scripts\python.exe -B rl_exp/tools/verify/test_body_precheck.py --break_fix source_geometry
E:\IsaacLab\env_isaaclab\Scripts\python.exe -B rl_exp/tools/verify/test_body_precheck.py --source_format xml --break_fix source_format
E:\IsaacLab\env_isaaclab\Scripts\python.exe -B rl_exp/tools/verify/test_body_precheck.py --source_format obj --break_fix source_format
E:\IsaacLab\env_isaaclab\Scripts\python.exe -B rl_exp/tools/diagnose/body_precheck.py --config rl_exp/tools/diagnose/body_precheck_lizard2.json --output rl_exp/out/body_precheck_source_geometry_replay.json
```

正常测试预期 0，破坏模式及本真实缺证/碰撞样例预期 1；不把真实失败样例加成默认必须绿色 CI。未知源格式/变换具名不支持，缺证/预算保持未判。

## 未覆盖边界

独立角色批准资料、完整源 link 朝向/全实体归属、全部物理轴与源随动覆盖、设计连接重叠区域判据仍缺，不靠样点覆盖声明解决。现方法约定原 exporter 的 world-neutral 坐标，非任意源模型/URDF 轴系泛化；最近视觉顶点也不证明完整表面、碰撞几何与实物一致。

没有第二真实不同构型及其自身不同任务判定；用户确认本地只有一机体，不取消关闭前置。没有执行新正式导出 USD/runtime、重采 Blender、动力学、训练、可达域或连续保证。重哈希只检普通并发漂移，不保证严格不可变消费字节；角色/源独立性仍由人审。原 work 保持 `in_progress`，责任、方法与未完动作继续在原项。
