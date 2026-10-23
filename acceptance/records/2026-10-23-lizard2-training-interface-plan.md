# lizard2 审核清单更新与训练接口方案

## 适用范围

用户要求“更新审核清单、准备训练接口方案”。对象为当前 `palm_spatial` 隔离候选，URDF SHA256 `e8896feb8b0dbdbeaa35e74a01c2ffcb4ab38d89b52f221831b3f287943edd00`；配置依据为承地 `standing_manifest.json`（SHA256 `2f39ca4e6268d90cee08600510f05a3eae78c1272fdbeebb811ba911405569f2`）。本轮更新 [D 自检清单](2026-10-22-lizard2-body-drive-candidate.md)，提出可审阅的 S5 接口方案；只读复核制品、构建配置及计算初始动作分布，不运行物理或训练。

以下明确区分已有事实、建议和待验项。开放角色、逐轴 scale、目标 clip 与训练采样迁移是本轮建议，尚未采用。没有新建版本、修改开发/冻结 YAML、锁、资产、PD、奖励或任务注册。S5/S6 仍由 `work/active/lizard2-family-landing.md` 承接；本记录不是 S5 已实装或 D 独立放行证明。

**后续修订（2026-10-23）**：用户明确“完全不做了，先训练”，取消剩余限速边界试验；随后要求先记录并盘点整个计划。本方案不再将该试验列为接入/开训前置，配置设置和已有未验事实保持。具体范围见[决定与盘点](2026-10-23-lizard2-plan-inventory.md)；本修订没有采用其余建议参数或启动训练。

## 验收条件

- 接入后续 E 证据，撤销过期“未真跑”阻塞，保持冻结 v3 已知缺陷和原物理失败不变；不重开用户明确不做的对称复测。
- 给出真实关节名称、动作列、后端关节列、policy 切片、权限、位置目标公式、缩放/裁剪、驱动继承、接触采样及 reset 落点。
- 目标速度恒为零；不增加速度动作、目标差分前馈或手工平衡/步态控制器。小动作精度不外推全姿态保证。
- 指明实现与运行缺口、验证方法和停止/回交路径；建议值的数学核对不冒充运行时安全或学习性能通过。

## 结果

### 用户确定首轮训练预算

2026-10-23，用户回复首轮新候选、从头初始化的预算问题：“沿用现有 6000 迭代预算”。据此，当前新候选首轮训练预算确定为 **6000 迭代**，从头初始化，不续训旧 v3 checkpoint；此前盘点中“不能把旧 v3 的 6000 自动当新预算”的未定状态由本次明确答复解除，不重复询问同一预算。

开训前继续完成正式训练配置、协议、版本与实际工况接入；已有[隔离草案运行证据](2026-10-23-lizard2-interface-runtime.md)及[独立复核](2026-10-23-lizard2-interface-runtime-review.md)按其范围复用。不恢复限速边界试验，也不将预算确认写成正式配置/资产已采用、其余集成已完成或训练已启动；环境数、启动命令及真实 run 随实际接入产物记录，本次不凭迭代数推定这些取值。

### 审核清单更新

| 项目 | 当前处理 | 保留边界 |
|---|---|---|
| 旧对象 cap/ownership | 消费[原对象修复](2026-10-22-lizard2-e-legacy-contact.md)及[开发选择修复](2026-10-22-lizard2-dev-contact-selection.md)，本轮再次核验摘要和原始接触数组 | 旧“只静态核对、未真跑”撤销；冻结 v3 的空处罚选择没有被修改；E/D 独立审核仍未做 |
| 膝肘组合 | 补回四膝肘 220 后已做的[左后膝单轴和五轴组合](2026-10-21-lizard2-left-knee-joint-force.md) | 其余当前组合/右侧精度仍未知；执行[不追加对称复测决定](2026-10-21-lizard2-symmetric-knee-elbow-pd.md)，不自动扩测 |
| 限矩 | 沿用 D 记录中用户“不再要求”的范围决定 | 低 cap 原越界不改写为通过，不宣称精确限矩已验证 |
| 限速、速度观测 | 剩余限速边界试验按用户决定取消；速度观测偏差另行保留 | 限速设置不删除、未验不称通过；TGS/false 不变，取消试验不等于消除速度读数偏差 |
| 接触采样 | 新列明训练配置与诊断修复之间的差异 | 训练端尚未证明能捕获首子步；迁移与验证归 S5 |
| reset | 保留真实关节残留正反例；单列根状态、缓存、后端目标及接触历史 | 关节 q/dq 通过不代证这些量已复位 |

本轮 `palm_policy_channel_audit.py` 正常退出，得到 30 个候选动作、22 个冻结动作；只替换资产时，旧腿部选择器遗漏候选全部 20 个腿关节。新输出 SHA256 与原通道复读逐字节相同。两组接触摘要分别核验 111 输出/101 输入、29 输出/71 输入；各真实窗口 240 个 physics 样本的精确地面过滤力与具名原生净力一致，修复前 FAIL、修复后 PASS，前后完整物理数组及初末 q 相同。本轮新增物理步数为零。

### 推荐动作接口

**建议从首次训练开放全部 30 个位置动作**：每腿 swing、abduct、twist、elbow/knee、wrist/ankle 各一列，另加胸颈尾 10 列；无固定角色、零 scale 或阶段门控。理由是用户要求由 RL 学习卸载、移重、平衡及躯尾协调；把所需关节固定在零位会限制可学性。此为正式权限建议，诊断全可达不能自动批准它。

沿用现有 `JointPositionAction`，不是逐帧累加到当前位置：

```text
q_ref[j] = clamp(q_default[j] + scale[j] * action[j], lower[j], upper[j])
dq_ref[j] = 0 rad/s
```

`use_default_offset=True`，默认 q/dq 均为零；`offset` 不再叠加额外姿态。沿用两组名称 `joint_pos_legs`、`joint_pos_spine`，用显式名称和 `preserve_order=True` 固定下表动作顺序。没有全局 `[-1,1]` raw-action 裁剪，也不额外增加动作滤波/插值。现有 action term 的 clip 在 scale/offset **之后**执行，单位为 rad；须使用逐关节 hard-limit 字典，不能把这里的区间误当成 raw action 的区间。

**初始 scale 建议**：保留旧 runner 的 Gaussian 初始标准差 1.0 作为比较依据，令 `scale[j] = min(旧分组scale, min(q_default-lower, upper-q_default)/3)`；旧分组为腿 0.5、胸颈尾 0.25。当前全部零默认、对称限位，因此均取各自半范围的三分之一。数值见下表；这是让初始零均值下约三倍标准差落在该轴限位内的起点，不是已验证的运动幅度、精度或安全窗口。实现时从精确 URDF 值计算，不能使用表中六位小数作为新限位。

列号从零开始。`r` 为已有真实后端 joint order 的索引；policy 的该关节 q/dq 分别在 `12+r`、`42+r`，上一 raw action 在 `72+a`。表内对称 ± 范围只约束该轴，不证明多轴联合姿态无碰撞。

| 动作列 a | 真实关节 | 后端列 r | hard limit rad | 建议 scale rad/action |
|---:|---|---:|---:|---:|
| 0 | `lf_shoulder_swing_joint` | 9 | ±0.600000 | 0.200000 |
| 1 | `lf_shoulder_abduct_joint` | 15 | ±0.600000 | 0.200000 |
| 2 | `lf_shoulder_twist_joint` | 20 | ±0.523599 | 0.174533 |
| 3 | `lf_elbow_joint` | 25 | ±1.200000 | 0.400000 |
| 4 | `lf_wrist_joint` | 28 | ±0.523599 | 0.174533 |
| 5 | `rf_shoulder_swing_joint` | 10 | ±0.600000 | 0.200000 |
| 6 | `rf_shoulder_abduct_joint` | 16 | ±0.600000 | 0.200000 |
| 7 | `rf_shoulder_twist_joint` | 21 | ±0.523599 | 0.174533 |
| 8 | `rf_elbow_joint` | 26 | ±1.200000 | 0.400000 |
| 9 | `rf_wrist_joint` | 29 | ±0.523599 | 0.174533 |
| 10 | `rl_hip_swing_joint` | 2 | ±0.600000 | 0.200000 |
| 11 | `rl_hip_abduct_joint` | 6 | ±0.600000 | 0.200000 |
| 12 | `rl_hip_twist_joint` | 12 | ±0.523599 | 0.174533 |
| 13 | `rl_knee_joint` | 18 | ±1.200000 | 0.400000 |
| 14 | `rl_ankle_joint` | 23 | ±0.523599 | 0.174533 |
| 15 | `rr_hip_swing_joint` | 3 | ±0.600000 | 0.200000 |
| 16 | `rr_hip_abduct_joint` | 7 | ±0.600000 | 0.200000 |
| 17 | `rr_hip_twist_joint` | 13 | ±0.523599 | 0.174533 |
| 18 | `rr_knee_joint` | 19 | ±1.200000 | 0.400000 |
| 19 | `rr_ankle_joint` | 24 | ±0.523599 | 0.174533 |
| 20 | `chest_yaw_joint` | 0 | ±0.600000 | 0.200000 |
| 21 | `chest_pitch_joint` | 4 | ±0.500000 | 0.166667 |
| 22 | `neck_yaw_joint` | 8 | ±0.600000 | 0.200000 |
| 23 | `neck_pitch_joint` | 14 | ±0.500000 | 0.166667 |
| 24 | `tail1_yaw_joint` | 1 | ±0.600000 | 0.200000 |
| 25 | `tail1_pitch_joint` | 5 | ±0.500000 | 0.166667 |
| 26 | `tail2_yaw_joint` | 11 | ±0.600000 | 0.200000 |
| 27 | `tail2_pitch_joint` | 17 | ±0.500000 | 0.166667 |
| 28 | `tail3_yaw_joint` | 22 | ±0.600000 | 0.200000 |
| 29 | `tail3_pitch_joint` | 27 | ±0.500000 | 0.166667 |

原腿 scale=0.5、sigma=1 时，最窄轴初始目标越限的双侧理论概率约 29.50%；建议 scale 下单轴约 0.270%，随后还有目标 clip。概率仅是零均值独立 Gaussian 的静态计算；30 轴至少一轴越限约 7.79%，不能写成“每帧只有 0.270%”。网络初始均值并非保证恰为零，学习后均值和标准差也会改变。须记录 raw action、clip 后目标和 clip 占比，不能将降低探索幅度称为学习性能改进。若将来采用非零默认姿态、不对称限位或不同 sigma，必须重新计算本方案。

动作缩放不改变 PD。全部 Kp/Kd、力矩及速度设置按承地 manifest 的**逐关节名称**迁移，四膝肘仍为 220/各自约 14.95，其余轴不统一刚度。当前 cap 为腿部近端及膝肘 180 N·m、腕踝 70、胸俯仰 280、其余胸颈尾 80；速度设置为腿部 10、腕踝 6、胸颈尾 4 rad/s。这些是设置/有限工况证据，不是全域边界保证。新配方须走明确的 `effort_limit_sim`/`velocity_limit_sim` 机制，不能照抄旧 factory 只传被隐式执行器忽略的 `velocity_limit`；当前设置保持，接入核实际写入，不再为剩余边界试验回 B 扩测。

### 观测、命令与网络边界

保持已测七项 policy、无噪声、无 history/modifier、无额外观测 scale/clip，宽度 102。区间按 Python 半开切片：

| 切片 | 内容 | 顺序与单位 |
|---|---|---|
| `[0:3]` | `base_lin_vel` | 按现有 consumer 的根机体坐标速度，m/s |
| `[3:6]` | `base_ang_vel` | 按现有 consumer 的根机体坐标角速度，rad/s |
| `[6:9]` | `projected_gravity` | 机体坐标下重力方向 |
| `[9:12]` | `velocity_commands` | `base_velocity` 的 vx、vy、wz；m/s、m/s、rad/s |
| `[12:42]` | `joint_pos` | 后端顺序，q−default_q，rad |
| `[42:72]` | `joint_vel` | 后端顺序，dq−default_dq，rad/s |
| `[72:102]` | `actions` | 上表动作顺序，上一 raw action；不是 clip 后目标角 |

**根速度命令与关节速度目标是两个接口。** 保留 `base_velocity` 命令通道不违反全部关节 dq_ref=0 的定案；本轮不决定训练命令范围、奖励权重或步态/恢复性能阈值。TGS/false 下已有约 0.0512 rad/s 的关节速度读数偏差仍可能进入 joint_vel，不能通过重排/缩放冒称消除。

当前 q/dq 采用已有后端顺序，action 用显式动作顺序；不为视觉对齐暗中重排观测。将 URDF 顺序、实际 backend 顺序、action 顺序及映射摘要随新资产/接口一起绑定，部署必须消费同一映射。冻结 v3 已锚定 policy=94、action=22；不得把旧 checkpoint 直接续训到 102/30 或覆盖旧宽度锚点。新策略从新接口初始化；正式资产采用、旧版本退休和新版本身份仍走既有 S5/S6 流程。

### 接触采样与 reset 方案

四足端精确集合为 `lf_wrist/rf_wrist/rl_ankle/rr_ankle`，按 `lf/rf/rl/rr` 解释；每个 consumer 都按自身 sensor body_names 解析索引，不能复用 articulation 的 body 下标。保留全 body 测量以识别腹部、头胸、近端肢体和尾；尾允许触地与异常主承重的区分归新接触协议，不把所有非足端一概处罚。

当前候选具名 undesired 集合为四个 shoulder/hip_twist 加四个 elbow/knee，腹部为 base_link，head contact 为 chest_pitch/neck_pitch。旧资产开发文件的 hfe-only 修复只消除了旧空选择；不能把这四个旧名称直接搬给新候选，或删掉当前确有 collider 的肘膝。逐项核实际 collider 与消费者归属，不能只要求正则非空。

采样建议：在**实际 PhysX contact preset** 设置 update_period=0.005 s、history_length=4，并令 scene.lazy_sensor_update=False，使一次控制步四个 physics 子步均进入可读窗口。当前构建配置是 lazy=True、preset update_period=0、history_length=3；给 preset 容器写同名字段不保证改到生效实例。实现需复用诊断已验的 preset 解析方式，并对实际建场配置/首子步力做核验。净力不是 ground pair 证明；地面归属诊断继续用精确 body→ground 过滤列。接触点滑移/滚动、摩擦与承重阶段口径仍回协议项。

reset 建议完整复用承地初始条件：自由根、重力开启、根高 0.6038 m、四元数按本栈 xyzw `(0,0,0,1)`、根速度零、q_default/dq_default 全零；`reset_base` 的全部 pose/velocity 随机范围为零；保留 `reset_robot_joints` 的 position_range=(1,1)、velocity_range=(0,0)。姿态或地形变化后，出生间隙须重核。当前候选自碰撞为 True，既有连接过滤沿原资产绑定继承，不能沿用旧正式机体的 False 偷换工况。

必须按 env_ids 核：根状态、关节 q/dq、raw action/prev_action、处理后目标、backend 位置/零速度目标、接触历史及 episode 状态。分别观察 reset 返回、首个零动作步，以及子集 reset 的未点名 env。当前 `reset_check.py` 只验关节状态；`JointAction.reset` 源码只清 raw action，不能据此断言 processed target/backend target 已清。这里记录验证要求，尚未诊断为实际残留缺陷；若运行发现旧目标影响首步，再按责任层修复并做修复前失败/修复后通过。自然终止后的自动 reset 与 terminal snapshot 也要在正式候选配置中核，不把已有合成 timeout 切片外推自然终止。

物理时序保持 dt=0.005 s、decimation=4，即 50 Hz 位置目标，TGS/`enable_external_forces_every_iteration=False`。改传感器更新不是先检测未来的力或改变外力施加时序；是在每个已完成的 physics 子步读取测量。没有增加前馈、关节速度动作或额外物理步。

### 实现落点与验证顺序

| 顺序 | 落点 | 应交付与失败处理 |
|---|---|---|
| 1 接口取值定案 | 本方案、`lizard2-family-landing` S5 | 确定开放角色、scale/clip 和采样建议；接触测量协议及策略判据按原项交付；剩余限速边界试验已取消，不再列依赖 |
| 2 未冻结候选配置 | 新版本参数/差异声明、`lizard2_recipe.py` 的新增机制 | 显式 30 关节、逐轴驱动/scale/clip、出生和实际 preset；旧已发布 term/v3 不改语义，暂不在本轮创建版本或改资产声明 |
| 3 离线对表 | `palm_policy_channel_audit.py`、`action_range_check.py`、配方/obs 检查 | 复用现有解析；范围检查须支持绑定候选、逐轴字典与实际 clip，当前入口没有 `--target_config`，不能编造命令或用旧 v3 替代。源码/配置对表不称行为通过 |
| 4 真实接口与 reset | `obs_protocol_live.py`、`reset_check.py`、ownership/baseline writer-reader | 在最终同一配置核逐列目标/零速度、102 维非零值、采样首子步、根及缓存 reset、terminal/子集边界。原 value probe 限定固定根零增益；要覆盖真实 PD/free base 须先做有界设计，不能直接移除保护或称历史切片已覆盖 |
| 5 审核与训练前出口 | D/E 新上下文、S5、S6 | 证据与配置同身份后审核；运行失败按来源回交。另定必要物理预算，不自动扫四肢、全 ROM 或追加运动性能试验；采用、冻结、训练预算与开训仍需各自授权 |

本轮交付到方案与清单。没有把实现表中的后续动作标为已完成，没有把独立审核或新协议创建为文件即视作通过。

### 后续继续：隔离配置草案已实际构建

用户要求继续 B/C 交付后，以同一承地 manifest 派生 `rl_exp/out/lizard2_bc_handoff_20261023/training_interface_draft.json`，使用现有注册构造器和 `obs_protocol.load_diagnostic_target` 完成真实配置对象构建。这是隔离配置草案，仍未写入正式/开发配方、版本目录或任务注册，没有建立环境、执行物理或训练。

相对源 manifest，仅将动作 scale/clip 按上文精确公式写入，将已有实测后端 joint order 显式绑定，并将 default/physx contact preset 的 update_period/history_length 和 scene.lazy_sensor_update 写成上文建议。没有改资产、全部 PD/caps、初始位姿、重力、自由根、自碰撞和连接过滤。构建后逐名确认 30 动作唯一覆盖、scale 非零、clip 等于实际 URDF 限位，全部 Kp/Kd/effort_limit_sim/velocity_limit_sim 与承地后端读回按 float32 精确匹配；实际 PhysX preset 与 contact preset 的字段也核对一致。

构建输出 `training_interface_build.json` 状态为 `constructed_isolated_draft_not_adopted_or_runtime_verified`。其中 30 动作/102 policy 是接口预期，不能称本轮重新测得 observation manager 输出宽度；先前真实消费者证据仍按其原条件引用。第一次构建因未先导入任务注册而在配置解析阶段拒绝，补 `import rl_exp.tasks` 后同一草案构建通过；没有借失败增开物理进程。

草案 SHA256 `a120b8907601852e5ca7bf1190f675d75ea7a8ae0fa79e970d887628ed7e8b19`；构建输出 SHA256 `e07829666b578dccd052b4a9b4fb8b95328dea093239496ac1d3c71ee4d4f301`。本机制品不承诺入仓。离线重建配置对象可在仓根的项目 Python 中运行下列代码；读取草案不执行其中的代码，也不启动 Kit：

```python
from pathlib import Path
import rl_exp.tasks
from rl_exp.tasks import obs_protocol
from rl_exp.tools.verify.baseline_runtime import resolve_task_cfg
task = 'Lizard2-Flat-Play-v3'
cfg = resolve_task_cfg(task)
bound = obs_protocol.load_diagnostic_target(
    Path('rl_exp/out/lizard2_bc_handoff_20261023/training_interface_draft.json'), cfg, task)
assert len(cfg.actions.joint_pos_legs.joint_names) == 20
assert len(cfg.actions.joint_pos_spine.joint_names) == 10
assert cfg.scene.contact_forces.physx.history_length == 4
assert cfg.scene.lazy_sensor_update is False
print('ISOLATED_TRAINING_INTERFACE_CONFIG_BUILT', bound['source'])
```

胸部上限须保留显式覆盖：`chest_pitch_joint` 的 manifest/backend effort cap 为 280 N·m，URDF 为 80 N·m；本草案取 manifest 驱动上限，URDF 只用于关节位置裁剪。该差异已列入 [B/C 独立审核](2026-10-23-lizard2-bc-independent-review.md)，不可在正式接入时静默改回。

后续仍须实例化最终候选环境，核实际动作 manager 的 affine/clip 与 backend 零速度目标、102 维非零值、接触首子步和完整 reset。构建成功不替代这些检查，不升级为 S5 完整实装或开训放行。

## 证据引用

- 本地输出 `rl_exp/out/lizard2_interface_plan_20261023/`：`channel.json` SHA256 `34b8b031cb1ec05bfc42381024952f4c8467804494ed63bbb0d0191d6fbef7d9`，`design_table.json` SHA256 `5fd4347b9b20b308bfccb3213af67498c2ee381169a736dbac68389c2ea7a808`，`mechanisms.json` SHA256 `e3b49e27ce58943bf99ab4e5da313969b4c834be734b2bb1796d71af493e81db`。本机制品不承诺入仓；持久动作复读入口与批准输入见[通道记录](2026-10-22-lizard2-rl-coordination-handoff.md)。
- 接触索引：`rl_exp/out/lizard2_e_legacy_contact_20261022/artifact_digests.json` SHA256 `378cee72ef841ea02862926f566ab9d1537943ad3d44d63184dec92da7160548`；`rl_exp/out/lizard2_dev_contact_20261022/artifact_digests.json` SHA256 `c77a647699c75bf34be53f42176c86e56b3c97c71d85f0992a62862061e963ef`。原记录含完整只读复读说明。本轮执行的是明确的摘要/数组核验，不是执行文档文本；自动审批拒绝过动态执行文档代码的方式，未绕过或运行该方式。
- 列与观测取 `standing` 报告 joint_names、`channel.json` 的分组、[非零消费者记录](2026-10-22-lizard2-e-live-values-gait.md)；根坐标/非零默认另取[速度观测记录](2026-10-22-lizard2-velocity-observation.md)。冻结 v3 宽度取 `rl_exp/versions/obs_protocol_anchors.json` 的既有任务锚点，不读配方锁正文。
- 实现核对：`rl_exp/tasks/lizard2_recipe.py` 的 actions/no_dr；`rl_exp/tasks/agents/rsl_rl_ppo_cfg.py` 的 Gaussian init_std；`rl_exp/tools/verify/action_range_check.py` 的 rows_for/main；本机 IsaacLab `envs/mdp/actions/joint_actions.py` 的 process_actions/reset/apply_actions；velocity 场景的 PhysX/Contact preset 与 `scene/interactive_scene_cfg.py`。本机构建时先后遇到旧版 `sim.physx` 字段和 preset 容器直接字段访问错误，均在配置读取阶段退出，未启动物理；最终按实际 `.default` preset 读取，未把失败读数用于结论。

以下在仓根的 IsaacLab Python 中执行，只读既有报告即可重算列映射与 scale；无需本轮临时脚本、Kit、checkpoint 或新物理预算：

```python
from pathlib import Path
import hashlib, json, math, xml.etree.ElementTree as ET
root = Path('rl_exp/out')
rp = root / 'lizard2_b_standing_force_20261022_run02/report.json'
assert hashlib.sha256(rp.read_bytes()).hexdigest() == '5a4c6a3f4572ab8db566637c64c67933ee5aa3857092b1fe7ed1b102724453c6'
r = json.loads(rp.read_text(encoding='utf-8'))
mp = Path(r['manifest'])
assert hashlib.sha256(mp.read_bytes()).hexdigest() == r['manifest_sha256'] == '2f39ca4e6268d90cee08600510f05a3eae78c1272fdbeebb811ba911405569f2'
m = json.loads(mp.read_text(encoding='utf-8'))
urdf = Path(m['target_binding']['urdf'])
assert hashlib.sha256(urdf.read_bytes()).hexdigest() == 'e8896feb8b0dbdbeaa35e74a01c2ffcb4ab38d89b52f221831b3f287943edd00'
cp = root / 'lizard2_interface_plan_20261023/channel.json'
assert hashlib.sha256(cp.read_bytes()).hexdigest() == '34b8b031cb1ec05bfc42381024952f4c8467804494ed63bbb0d0191d6fbef7d9'
c = json.loads(cp.read_text(encoding='utf-8'))
js = {j.get('name'): j for j in ET.parse(urdf).getroot().findall('joint') if j.get('type') != 'fixed'}
a = 0
for group in c['candidate_channels']:
    for name in group['resolved']:
        limit = js[name].find('limit')
        lo, hi = float(limit.get('lower')), float(limit.get('upper'))
        assert lo < 0 < hi and abs(lo + hi) < 1e-6
        scale = min(0.5 if group['term'] == 'joint_pos_legs' else 0.25, min(-lo, hi) / 3)
        print(a, name, r['joint_names'].index(name), lo, hi, scale)
        assert abs(math.erfc(hi / scale / math.sqrt(2)) - 0.0026997960632601918) < 1e-12
        a += 1
assert a == 30
```

提交前检查：30 列表与原制品的关节名/后端索引、六位小数 scale/限位、Gaussian 概率、文档链接及产物摘要核对通过（`INTERFACE_PLAN_TABLE_AND_LINKS_OK`）。完整离线套件 `37/37`、56.0 s，通过；`git hook run pre-commit` 的静态闸门全部通过，事项为 30 active/61 closed、179118/180000 bytes，未关闭或迁移事项。日志在上述本地目录：`offline_suite.log` SHA256 `e7011088875831e022d00c1cb9d46e3eade54b36020e1826d221e90b85ec7ba8`；`precommit.log` SHA256 `c0f98c5d77d89b0408743d49d96733b152dd0a33aa7490296a3e6eab5394534d`。这些检查证明本轮文档/既有闸门一致，不是方案已实装或独立审核通过。

## 未覆盖边界

**后续运行证据：2026-10-23。** 用户要求继续的隔离草案动作、子步接触与完整/子集/接触自动 reset 核验已实际采集，结果及即时目标残留语义取[运行记录](2026-10-23-lizard2-interface-runtime.md)。上文“尚未在线核验”保留为方案制定时状态；本次运行不升级为正式配置采用、S5 完整交付或开训放行。

正式训练配置尚未实装，隔离草案已有上述构建和具名在线证据，开放/scale/clip/采样建议未被正式采用；普通姿态自然终止、原 timeout 到期、训练采样和策略性能仍未验证。限速边界试验已取消，未测范围仅保留为证据边界；速度观测偏差、新接触协议及整体独立审核继续具名保留。硬限位裁剪不保证联合构姿无碰撞、无瞬时大力矩或全域 0.002 rad 精度；RL 学习承担协调，不承担掩盖接线或 reset 缺陷。原不追加对称复测、不再要求限矩验证以及抬腿/行走归 RL 的用户决定保持执行。
