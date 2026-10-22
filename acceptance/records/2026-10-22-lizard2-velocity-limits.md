# 当前候选的速度上限配置与后端读回

## 适用范围

承接机体总项 B3 和限位 PD 专项的有效限速前置，离线复读既有固定根自重跟踪、自由根静站以及训练一致 TGS/false 速度探针。当前对象为 `palm_spatial` 隔离候选，不是冻结 v3 机体。没有新增物理激励、改 PD、改限速、改正式配方或运行 true 工况，也没有启动训练。

用户已要求保持训练的 `enable_external_forces_every_iteration=False`；此前 true 试验只作历史归因，边界归[速度观测记录](2026-10-22-lizard2-velocity-observation.md)。本轮限速读取器不消费 true 报告。

## 验收条件

三个原始报告及其 manifest、USD/URDF 身份可核；按实际关节名解析执行器选择器，两个速度字段均须精确覆盖所属关节，分别对照 URDF 的 rad/s 与实际 backend `get_dof_max_velocities()` 数组。同名关节在三工况的设置须一致。缺 `_sim` 字段、后端错值、跨不同 cap 的错列必须拒绝。配置读回不能作为触限行为或速度—载荷包线通过。

## 结果

`palm_velocity_limit_audit.py` 退出 0，三个具名原始报告的 30 轴均逐名一致：

| 关节集合 | 轴数 | 后端速度上限（rad/s） |
|---|---:|---:|
| 四肢 swing、abduct、twist、elbow/knee | 16 | 10 |
| 四腕/踝 | 4 | 6 |
| 胸、颈、三节尾的 yaw/pitch | 10 | 4 |

三个 manifest 都显式设置 `velocity_limit` 与 `velocity_limit_sim`，两者同值；不是只填旧字段。固定根与自由根 USD 身份各自核对，不要求两个 USD 相同；共同 URDF 身份一致。上述数值确已进入已采候选的后端限速属性，不能继续把“当前候选有没有写入上限”记为完全未知，也不能把它写成“未启用”。这仍不代表限速功能已完成行为验收或这些数值已获正式采用。

离线内存反例三项均拒绝：删腿组 `velocity_limit_sim`；改变一项 backend cap；交换 cap 不同的两项关节名。原始记录字节未变。该负例只证明读取器能识别这些不一致，不证明等 cap 关节之间的映射或真实限速约束能力。

本机实际源码链已核：

- `isaaclab/actuators/actuator_pd.py:81–104`：implicit 仅填旧 `velocity_limit` 时发警告并清除它；显式 `_sim` 不走该忽略分支。两字段不相等则报错。
- `isaaclab/actuators/actuator_base.py:176–210`：`velocity_limit_sim` 为 None 时继承传入的 USD/后端默认值；有显式值时解析执行器配置。故旧字段被忽略不等于后端无限速。
- `isaaclab_physx/assets/articulation/articulation.py:4110–4134`：构建执行器后，将 `actuator.velocity_limit_sim` 交给速度上限写入入口；该入口在 1578 行调用 `root_view.set_dof_max_velocities()`。
- 仓内 `rl_exp/tasks/lizard2_recipe.py:124–134` 的冻结配方构造仍只传旧 `velocity_limit`。此处是旧正式对象的缺口，不能用当前诊断 manifest 覆盖它，也不能据此说当前新候选设置被作废。本轮没有改它。

源码核查是配置来源解释；运行证据只证明上述已采对象的属性读回。真实触边、同条件有/无限速对照及速度—载荷—跟踪/稳定包线仍未测。TGS/false 已知速度偏差也限制了用 `joint_vel` 单独判断触限的可信度；本轮没有据低速读数推算真实速度余量或更换策略观测。

## 证据引用

本机原始工件不承诺入仓；新读取器与本记录入仓。三个输入报告的路径/摘要、各 manifest 和逐轴 cap 全量保存于本轮 JSON，其输入摘要也固定在读取器 `REFERENCES`：

| 工件（相对仓根） | SHA256 |
|---|---|
| `rl_exp/out/lizard2_b_velocity_limits_20261022/report.json` | `d80389bc1bdf3cc7f5d6e7adfe1a7e4af7790e9602c4c739382159e93610926c` |
| 同目录 `report.json.source.py` / 本轮读取器 | `08b067c2d804c719407b09dc1ad2f68a82552f2dc51b79e1cb0223c9aa440b8a` |
| 共同 URDF | `e8896feb8b0dbdbeaa35e74a01c2ffcb4ab38d89b52f221831b3f287943edd00` |

本机框架源码以 `E:/IsaacLab/source/` 为根；核查时 SHA256：`isaaclab/isaaclab/actuators/actuator_pd.py` 为 `6a29a2e47128e6c758ea787c08a713fc5d067a42e707970b07ed660bb401826a`，`actuator_base.py` 为 `1106d8e31f17a01ec4af4b09e4134b5fa8f002385bcc69cfcdc800a18a093810`，`isaaclab_physx/isaaclab_physx/assets/articulation/articulation.py` 为 `378945cc535e5e42e4fbdc37dd444330481736e3525ac24e6dbb5249b00a449a`。仓内 `lizard2_recipe.py` 为 `e9bfc5ac52a6396adea5eb74d8a070076d5b39d85db6e353a3ee75b1dfee0fe2`。后续源码移动后按文件身份解释本次结论，不能把行号当永久接口。

从仓根复读，只读原始工件，输出须换新路径：

```powershell
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/diagnose/palm_velocity_limit_audit.py --out rl_exp/out/lizard2_b_velocity_limits_replay/report.json
```

运行日志为 `rl_exp/out/lizard2_b_velocity_limits_20261022.log`，输出 `VELOCITY_LIMIT_READBACK_AUDIT_OK`，包含三项反例。完整仓库套件退出 0：`ALL_OFFLINE_CHECKS_PASSED (37/37 in 57.3s, jobs=6)`，日志 `rl_exp/out/lizard2_b_velocity_limits_offline_20261022.log`。默认套件未增加条目；本轮归属路径 diff 格式检查通过。提交前显式钩子及正常 commit 钩子分别保留在 `lizard2_b_velocity_limits_precommit_code_20261022.log` / `lizard2_b_velocity_limits_commit_code_20261022.log`，文档组为同前缀 `precommit_docs` / `commit_docs`；结果按实际收尾核对，不把源码核查升级成行为证明。

代码提交 `a12e0c0` 时，预备的独立索引因另一会话推进 HEAD 而过期，意外回退了三个支撑诊断文档路径；`6b77fd9` 已恢复这些路径。逐路径比较它们与原 `2b10882` 提交完全一致，本轮读取器仍在，未改写历史。文档组改用实际 staged tree、显式 pre-commit 以及带预期父提交的原子 ref 更新；若检查期间 HEAD 再变化则拒绝更新。此为本轮提交操作缺陷及恢复记录，不归因于机器人配置，也不把他人的支撑修复计为本轮结果。

## 未覆盖边界

B 的速度行为出口继续未决：没有在 4/6/10 rad/s 附近进行负载试验，没有同条件取消 cap 的对照，不证明极限速度、极限负载或全位置精度。追加物理测试仍先按总项 B 的原流程确定速度、载荷、预算及停止条件；本轮没有自行扩到高速工况或关闭限速。

旧冻结 v3 的 USD/default cap 来源及其实际后端值仍未测，不能以候选 manifest 代替。E 的终止采集由 `lizard2-candidate-wiring` 当前执行者维护，本轮不另建第二套正式终止工具；独立局部诊断工件保留于 `rl_exp/out/lizard2_e_baseline_terminal_20261022/attempt01/`，不用于关闭 B 或 E。D/S5 的集成审核、正式采用和 S6 学习策略性能仍分别在办；本记录是执行者自检，不是关闭审核。
