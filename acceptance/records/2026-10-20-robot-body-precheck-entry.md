# 通用机体 precheck 最小采样入口

## 适用范围

用户于 2026-10-20 确认“开始最小通用入口”：在 A 的稳定切片上提取独立薄入口，普通数据声明真实链、任务与完整姿态，不重写 FK、不接管 A/E 共用核心，不等待 E/动力学全项完成。依据为 `acceptance/records/2026-10-19-lizard2-a-delivery-plan.md` 的正式 URDF 导出切片验收；本轮核对已审两个导出源码摘要仍一致。

本轮新增 `rl_exp/tools/diagnose/body_precheck.py`、`rl_exp/tools/verify/test_body_precheck.py` 和候选输入 `rl_exp/tools/diagnose/body_precheck_lizard2.json`；更新复用路由及原 work。候选输入选原批准 `checkpoint_v3`，不把新导出 URDF 与旧 USD 身份混接。本记录只验最小入口及其真实消费，不是 A/E、机体或整个 precheck 事项关闭审核。

## 验收条件

- 输入普通数据分需求、机体适配与身份；实际树沿显式根/链端读取，不按腿名前缀、固定腿数/轴数或关节位次选择。
- 全部可动关节有完整姿态及角色；共享上游状态唯一、角色无冲突；全部碰撞实体有检查或具名排除，过滤不继承直接连接或旧批准对。
- 同一完整关节姿态、根位姿与相位复验逐链端点及整机碰撞；结果保留覆盖与五态。必选缺参、不支持或预算耗尽不能汇总成功。地面、端点/源姿态只按需求选择，不普遍强制平掌或固定落点。
- 仅消费明确支持的树、关节、网格与变换，不删除旧拒错保护；输入摘要核批准值，报告禁止覆盖历史。源码中明确路径式消费的并发身份边界。
- 异名、四/六链、不同轴数及共享分叉经同一入口测试；真实缺陷/修正用同一回归确认修前红、修后绿。真实候选至少绑定源独立端点及完整整机姿态，失败保留原义。
- 不新增默认 CI 条目、依赖、求解器、手工步态或动力学；新上下文按实际代码、配置、产物与证据审核窄交付，未完工作继续在办。

## 结果

### 实现与支持边界

入口提供 `joint_limits`、`end_position`、`self_collision`、`ground`、`source_consistency` 五项。每 case 的采样几何基线为全链必选限位与整机碰撞；`coverage.whole_machine=pass` 只表示覆盖声明齐备，不能覆盖失败行，也不是任务或机体通过。地面只支持显式平面，端点指 link 原点，不自动推导掌心、接触材料点或自然步态。

支持有唯一根、全连通的 revolute/fixed 刚性树及显式串行需求链/共享分叉；不支持 mimic、闭链、其它关节类型、非零 joint rpy、碰撞偏置/旋转、非单位 scale、多碰撞体或非本地三角 OBJ。网格精确焊接重复顶点、删除重复索引退化面，保留严格共线面并核闭合/一致绕序；有限非零极小三角仍拒绝。闭合与绕序不证明无自交或物理实体正确，几何算法保留浮点容差。

独立首轮审核 `a8456462-446e-49e9-b57e-71d1fba891f5` 实际复现四项阻塞：批准哈希后路径变化仍通过、NaN 需求字段污染失败报告、共享关节角色冲突未拒绝、畸形 params 被忽略。已修复并留下可复读回退模式。另纠正全任务强制地面/端点的脆弱假设；真实 A 网格首次被非退化断言拒绝后，按既有已证 pole 语义补最小支持与回归，不改资产。

输入路径在共享消费者前后及判定前重哈希，拒绝普通并发漂移；**不保证严格不可变消费字节**，修改后在检查间恢复可能逃逸。配置摘要绑定一次实际读取的字节，复用 `binding.sha256_bytes`；外部批准文本是调用方前提，不是权限认证或源独立真值证明。

### 回归与仓库验证

- 终版独立测试退出 0：252 assertions，通过真实 CLI 和 `run()` 消费链；含四/六链、变轴数、共享上游与其它关节、解析 FK、穿透/包含、直接连接、正/零间隙、支持拒错、漏覆盖、完整 q、失败严格 JSON 与预算。
- 八种同一回归回退模式各退出 1，命中断言：`zero_aabb`、`binding`、`error_rows`、`roles`、`params`、`coverage`、`config_digest`、`mesh`。正常源码不改；回退只在测试进程内。`mesh` 还在实际修改前运行得到失败。
- 两源码 `compile(...)` 通过，不写仓内字节码。
- 完整离线套件退出 0：`ALL_OFFLINE_CHECKS_PASSED (37/37 in 93.5s, wave 441s/informational, jobs=6)`。波内慢项按原入口单独复核通过，未改变预算或清单。

### 真实候选消费

实际 CLI 输入原 `checkpoint_v3` 的批准 URDF 与 18 个碰撞网格，配置完整列 30 个可动关节、四条五轴链及 10 个其它关节；中立和组合姿态来自保存重开的 Blender 快照，不求解新动作。中立稀疏快照补零的依据是生成器每次采样先清零，终审直接核过该实际来源。八个端点期望均为源枢轴减基座原点，未由本入口 FK 自算自比。

CLI 退出 1，报告 `status=fail`：2 个完整姿态各检查 153 对，共 306 对，未排除任何实体或实体对。限位及端点均通过；两姿态最大端点误差分别 `9.97680641648527e-7 m`、`1.0450455417011123e-6 m`，低于既有源对照 `1e-5 m` 数值预算。限位只是实际 URDF 占位范围，不是机械 ROM 批准。

每姿态有 14 对表面相交/包含读数，恰为旧报告排除集合。来源包括机身—近端、肘膝—上下段/掌体及尾段连接；本轮**不将全部读数定性为禁止机械穿透或新增 A 缺陷**。共享交叉法可保守报告边界触碰，连接区域有自身语义；A/E 须按具体区域、任务及几何解释，不能因直连/旧白名单自动安全，也不为了入口变绿放宽过滤。样例特意保持无排除，作为真实拒绝/待解释输入，不是候选合格配置。

### 终版独立审查

新上下文 `9b5ed0d8-671b-4508-a96d-751c05f2a27b` 直接读代码、配置、文档与实际报告；实际运行 252 条绿回归及八种红回退，复算 URDF/18 网格、build、配置、报告及消费源码摘要，独立对照完整 q、源端点与 FK。批准最小采样入口，无本范围阻塞；不批准候选、完整任务或 work 关闭。审核未重复真实碰撞扫描，CLI 退出码来自执行者真跑，审核只独立核报告/身份与 FK。

| 绑定对象 | SHA256 |
|---|---|
| `rl_exp/tools/diagnose/body_precheck.py` | `7859f8135f1cabf131f98269abe66b6ddccbf6f7d5ee4bd7a92c2b2e120c786b` |
| `rl_exp/tools/verify/test_body_precheck.py` | `4d655dbf0418c18d7f756649e9ddd363bed06c6a12469b035584fea01481ef31` |
| `rl_exp/tools/diagnose/body_precheck_lizard2.json` | `ab4da5fbcd1c51034e065bc87305389471b91f22d6e0a3d240ffb4e12af15dc1` |
| 原 `checkpoint_v3/build.json` | `59473f8c345dce48e8ee379c0972c928184f768be85afca948ac812a666fa6f8` |
| 原 `checkpoint_v3/palm_spatial.urdf` | `2c78117020458d5e7934219a2064bf7241430b81c2a736acd8cc0761c7a1461f` |
| 本机 `rl_exp/out/body_precheck_lizard2_20261020.json` | `bd911fc65f3a196ff15d7dc8c92e7ce1021de3e6fbd799050793cb2867e3aeaa` |

## 证据引用

输入契约与支持矩阵唯一实现为 `rl_exp/tools/diagnose/body_precheck.py` 模块文档；实例需求/适配为同目录 `body_precheck_lizard2.json`。旧支持与过滤边界取 `rl_exp/docs/leg_geometry_reuse.md`；源批准及容差取 `acceptance/records/2026-10-14-lizard2-palm-spatial-trial-checkpoint.md`，稳定正式导出切片取 `acceptance/records/2026-10-19-lizard2-a-delivery-plan.md`。本机报告不承诺入仓，复读必须换不存在的输出文件。

仓根执行，解释器以 `python -B ablation_harness/host_paths.py --python` 的实际输出为准：

```cmd
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/verify/test_body_precheck.py
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/verify/test_body_precheck.py --break_zero_aabb
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/verify/test_body_precheck.py --break_fix binding
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/body_precheck.py --config rl_exp/tools/diagnose/body_precheck_lizard2.json --output rl_exp/out/body_precheck_lizard2_replay.json --max_cases 2
```

其余回退将 `binding` 替换为 `error_rows|roles|params|coverage|config_digest|mesh` 单个取值；破坏模式预期退出 1。真实无排除样例预期非通过，不能改成期待 0 的仓库默认闸门。安全/不可写输出退出 2，其它已写非通过报告退出 1。

## 未覆盖边界

第二真实不同构型、自身代表任务及至少一项需求差异合理判定仍未完成；四/六链解析模型只证明代码泛化。实际全实体独立随动/轴/pivot 反例、任意任务目标姿态、非平面环境、完整变化影响清单仍需按原 work 补覆盖；`source_consistency` 的真实全 link 姿态验收未在本轮执行。

不支持部分没有靠删除保护放行；离散几何不证明连续域、可达域、承重、动力学、驱动、稳定性、无滑移或能走。未执行新导出 USD/runtime、训练、正式采用、完整 A/E 或关闭审核；其它会话源码和产物不纳入本轮。原 `work/active/robot-body-precheck.md` 保持 `in_progress`，未完项继续在办。
