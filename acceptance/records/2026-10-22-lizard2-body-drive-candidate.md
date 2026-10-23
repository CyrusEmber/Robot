# lizard2 候选训练前集成核对（D 自检）：动作、观测、接触测量与安全 reset

## 适用范围

执行 `work/active/lizard2-body-drive-candidate.md` 的 D 节第 1–4 条，对象为 `palm_spatial` 隔离候选（URDF SHA256 `e8896feb8b0dbdbeaa35e74a01c2ffcb4ab38d89b52f221831b3f287943edd00`）。本轮以离线复读与跨记录对账为主，另追加一次有界 `reset_check` 物理运行（见“回合重生关节残留复验”）；不训练、不改 PD/限速/资产/冻结 v3/配方锁；不新增数值判据。结论分三类：合格、拒绝、具名未判；缺预算或判据不记为通过。

这是 D 执行者自检，不是关闭事项所需的新上下文审核，也不批准 S5 接入、采用或开训。用户已定案的职责分工取[默认驱动与 RL 职责](2026-10-19-lizard2-chest-standing-pd.md#用户定案默认关节驱动与强化学习职责)：承重协调、抬腿、步态归 RL/S6，不作 D 判据。

**清单更新：2026-10-23。** 用户要求更新审核清单并准备训练接口方案。本次接入随后交付的 E 旧对象与开发接触选择修复，纠正重复要求对称复测的路由；原物理数据、失败判词及下文“本轮实际复读”的历史输出保持原样。此次新增复核只读已有制品和构建配置，未启动物理或训练。接口建议、逐列映射及复读边界见[训练接口方案](2026-10-23-lizard2-training-interface-plan.md)，其中建议值没有写入训练配置。

## 验收条件

- 同一候选绑定：A 的 URDF、E 的 manifest/USD、B/C 的驱动与速度/力矩报告须回溯到同一 URDF 身份；USD 差异须有已核来源。
- 动作：真实 action manager 的 30 通道逐关节所属、缩放、偏置、裁剪、保序，复读原始审核输入；冻结 v3 选择器对新关节集合的缺口须明示。
- 观测：七项 policy 拼接宽度、非零消费者语义，以及已知速度偏差对策略输入的影响分开报告。
- 接触测量：四足端精确集合、传感器/collider 归属及外来接触不被过滤的正反例有真实记录。
- 驱动：30 关节默认 PD、限位、effort/speed 设置读回，逐轴/组合/受载行为证据，有效限速须明确为已启用、明确不启用或未决。
- 安全 reset：reset 后默认位姿误差、首步、自由根重力下短时无 NaN/越界/异常接触；候选出生高度与正式配方声明一致。
- 复读须与原记录哈希字节一致，缺口回责任节，不以声明一致、源码、无重力或格式检查替代行为证据。

## 结果

### 本轮实际复读

以下入口均从原批准输入复读，输出换新目录 `rl_exp/out/lizard2_d_audit_20261022/`，全部退出 0，输出哈希与原记录逐字节相同：

| 入口 | 结果 | 输出 SHA256 |
|---|---|---|
| `palm_policy_channel_audit.py` | `POLICY_CHANNEL_AUDIT_OK 30 candidate, 22 frozen; missing with asset-only replacement: 20` | `34b8b031cb1ec05bfc42381024952f4c8467804494ed63bbb0d0191d6fbef7d9` |
| `palm_standing_force_audit.py` | `STANDING_FORCE_AUDIT_OK`，原静站判词 `standing_force_observation_standing_failed` 原样保留 | `619c825b212a9dabbe5d48380859b5a3b9c4e0cc869ea18c40d422081b04e340` |
| `palm_velocity_audit.py` | `VELOCITY_AUDIT_OK` | `a793755d8d4ed134da22b405f8b003bb5a87dab051920ccb47ddbf905185604c` |
| `palm_velocity_limit_audit.py` | `VELOCITY_LIMIT_READBACK_AUDIT_OK {4.0: 10, 10.0: 16, 6.0: 4}`，三类反例拒绝 | `d80389bc1bdf3cc7f5d6e7adfe1a7e4af7790e9602c4c739382159e93610926c` |
| `palm_speed_probe.py --replay`（低上限对照） | `SPEED_REPLAY_OK` | `79544cb1dbdb79d8ffd23da026b1de8e882b3af65e48f1f113b45119c237761d` |

另读各原始报告与 manifest 的身份字段：fresh reset 与承地两份 manifest 的 URDF 摘要均为 `e8896fb…`；跟踪、低上限、速度对照三份报告的 `target_binding` 均指向 fresh reset 目录的同一 `palm_spatial.urdf`（摘要同上）与 `palm_spatial.usda`。低上限与速度对照所引 B 探针 manifest 的文件哈希与报告所记一致；未展开该 manifest 内部字段。

### 逐项判定

| D 项 | 判定 | 依据与边界 |
|---|---|---|
| 同一候选绑定 | **合格** | 新 reset、承地静站、速度对照三个目录的 URDF 同为 `e8896fb…`。fresh reset USD `0c5ffd15…` 与承地/速度 USD `721e8a40…` 的差异是承地入口只关闭世界固定关节，已由[承地记录](2026-10-22-lizard2-standing-joint-force.md)的 USD 逐层规范化核验；限速/低上限对照复用 fresh reset USD。 |
| 动作通道 | **合格（诊断层）** | 候选 30 通道（腿 20、胸颈尾 10）逐关节唯一所属，scale=1、offset=0、clip=None、保序，默认目标全零，Kp/Kd 与最新承地读回逐项匹配；三类内存反例已由[通道记录](2026-10-22-lizard2-rl-coordination-handoff.md)拒绝。冻结 v3 选择器直接套新关节集合，腿部 20 个全不匹配，所以不能只换资产路径接入。 |
| 动作权限与可学性 | **方案已具名，S5 未实装** | [接口方案](2026-10-23-lizard2-training-interface-plan.md)建议全部角色可学，给出 30 列映射、逐轴初始缩放和目标裁剪；不是正式权限已开放。诊断 scale=1 不能照抄成训练范围。现有 `action_range_check.py` 只取注册任务及家族 URDF，未支持此隔离候选与逐轴增益字典；不能拿旧 v3 的输出代替候选复核。 |
| 观测宽度与消费者语义 | **合格（有限）** | 102 维；七类 consumer 用各列不同的非零夹具逐值相等；30 个关节各注入双符号 q/dq，六例排列破坏均被拒（[E 在线值记录](2026-10-22-lizard2-e-live-values-gait.md)）。该切片根速度为零、默认 q/dq 全零，根坐标变换和非零默认值扣除另取[速度观测记录](2026-10-22-lizard2-velocity-observation.md)的自由根夹具。 |
| 速度读数对策略输入的影响 | **具名保留（不判通过）** | 训练一致 `enable_external_forces_every_iteration=false` 下，固定根静置末段后端速度偏离差分约 0.0512 rad/s，且确实进入 `joint_vel` 观测；用户已定案保持 false，true 仅作归因。该偏置对策略的影响没有被验证，也没有被消除。 |
| 接触测量集合 | **合格（限定切片）** | 四足端精确为 `lf_wrist/rf_wrist/rl_ankle/rr_ankle`，近端承载 link 不计足端；跨腿 `lf_wrist↔rl_ankle` 外来接触 114.57 N 未被过滤；非空足端分支已在真实在线检查中执行。这些是初始切片，不覆盖稳态四足承重、长时策略或自然终止。 |
| 旧资产 cap/ownership 前提 | **修复及原对象对照已交付；待独立审核** | [旧对象记录](2026-10-22-lizard2-e-legacy-contact.md)已定位过期 cap 校准对象，保留原失败并补修复前后回归；三个原资产各有真实接触选择负/正对照。后续[开发选择修复](2026-10-22-lizard2-dev-contact-selection.md)只移除开发 YAML 的无 collider kfe，冻结 v3 原缺陷仍保留。本次核验两组摘要索引及实际地面力数组，旧“未真跑”阻塞撤销；没有据此关闭 E/D。 |
| 训练接触采样 | **具名接入缺口（S5）** | [首子步漏采修复](2026-10-22-lizard2-e-support-contact.md)只进入 ownership 诊断。当前候选构建配置仍为 lazy=True，实际 PhysX contact preset 历史长度 3、update_period=0；decimation=4。训练端需按接口方案迁移有效 preset 的采样设置并验证首子步，不把诊断正例冒称训练已经修好。 |
| 逐轴小幅与受载（30 关节） | **合格（原条件）** | [全部单轴标定](2026-10-21-lizard2-calibrated-loaded-pd.md)在固定根、自重、中立附近双向 ±0.02 rad 下 30 轴 60 方向全部通过。其后四个膝/肘按用户决定统一到 Kp=220、Kd≈14.95；其中只有左后膝另有当前 PD 的实际力矩/速度切片。 |
| 适度组合 | **部分有证，未测范围保留；不自动重开对称复测** | 旧六组合的四肢精度失败原样保留。四膝肘 Kp=220 后，[左后膝实际力矩记录](2026-10-21-lizard2-left-knee-joint-force.md)已做左后腿五轴组合及单膝，两例共 6800 步；不能再写“当前组合全未做”。其余腿当前组合和新增三轴精度没有因此通过。用户已明确不追加对称复测，按[对称定案](2026-10-21-lizard2-symmetric-knee-elbow-pd.md)保留未知，不重复索取同一授权、不自动扫描。 |
| 有效限速 | **未决（回 B）** | 30 轴设置读回合格（16 轴 10、四腕踝 6、胸颈尾 10 轴 4 rad/s）。行为只验证了左后膝一个轨迹：2 rad/s 低上限响应通过；其余关节、原 10 rad/s 附近触限、同条件有/无限速及速度—载荷—稳定包线均未验。按 D 规则，未决不能记为已启用或明确不启用。 |
| 有效限矩 | **不再要求（用户决定 2026-10-22）** | 用户明确不需要限矩验证。左后膝 5 N·m 对照的 5.118464 N·m 越界样本（超 5.1 判据 0.018464）与原 180 N·m 未触及的事实保持原判词，不改写为通过，也不再作 D 前置；不据此声称限矩已验证。 |
| 受载站姿样本 | **观测，非通过** | 承地 5 s、1000 步，无停止线、无 NaN，全部关节最大占 cap 41.46%（左肩外展），无 99% cap 样本。最后 1 s 的 `root_drop`（0.0350 m，门槛 0.02）与两前肘（约 0.122 rad，门槛 0.1）失败原样保留。依用户定案这不是驱动缺陷判据，也不据此继续加刚度。 |
| reset 复位与首步 | **合格（限定切片）** | 固定根、无重力、零增益：wrapper reset、中立首物理步及负例后 reset 的位置/速度默认误差为零。 |
| 自由根重力下 reset 样本 | **合格（限定切片）** | 承地样本按中立网格最低点加 0.001 m 间隙出生（根高 0.6038 m）；manifest 声明 `reset_base` 位姿/速度范围全零、`reset_robot_joints` 固定默认且速度为零；5 s 无 NaN、无停止线。该样本不是回合反复 reset，也不是正式配方出生高度。 |
| **出生高度与正式配方** | **方案具名，S5 待落地与同配置核验** | 开发配方的 `base_init_height: 1.1` 属旧机体；[接口方案](2026-10-23-lizard2-training-interface-plan.md)建议复用承地 manifest 的 0.6038 m、原姿态及零范围 reset。已有样本支持该初始条件，不能因此宣称尚未构建的正式配方已通过。改高出生或改默认姿态须重新核出生条件。 |
| 多次/分环境 reset | **合格（限定切片）** | 追加运行见下节“回合重生关节残留复验”：全量 reset 与子集 reset 后关节位置/速度回到默认，未点名的 env 逐位不变；删除 `reset_robot_joints` 的负例在 C/D 失败。 |
| reset 的根状态、动作缓存与 backend 目标 | **具名未判（S5 集成）** | 上述 reset_check 只断言关节 q/dq；根位置/姿态/速度、action/prev_action、处理后目标及 backend 位置/零速度目标、接触历史不能由该结果代证。方案要求在同一正式候选配置下按 env_ids 核验 reset 后和首步，保持未点名 env 不变；未执行不记通过。 |
| 网络接口迁移 | **方案已列，S5 待实现** | 冻结 v3 是 22 动作/94 维 policy；候选为 30/102，且关节观测后端顺序与动作列顺序不同。需具名列映射、新宽度锚点和新策略初始化；旧 checkpoint 不能直接续训或重解释。 |

### 回合重生关节残留复验

用户要求补验“回合重生后关节状态不残留上回合的值”。`rl_exp/tools/verify/reset_check.py` 原只能建注册任务，现加 `--target_config`（经 `obs_protocol.load_diagnostic_target` 绑定隔离候选）和 `--action_amplitude`（默认 1.0，旧调用不变）；A/B/C/D 四相与断言未改。

对象为承地 `standing_manifest.json`（SHA256 `2f39ca4e6268d90cee08600510f05a3eae78c1272fdbeebb811ba911405569f2`）：真实 PD、重力开启、自由根；`Lizard2-Flat-Play-v3`，4 env，每次激励 20 个控制步，动作幅度 0.3，子集 reset 2 个 env，一次物理进程。该 manifest 的 `events.reset_robot_joints` 固定默认位姿（position_range 1.0、velocity_range 0），`reset_base` 范围全零。

| 相 | 读数 |
|---|---|
| A 首次 reset | 位置、速度等于默认 |
| B 激励 | 4/4 env 偏离，最大 0.3313 rad，激励期间未发生自动重生；非空转 |
| C 全量 reset | 位置、速度回默认 |
| D 子集 reset | 被点名 env 回默认；未点名 env 事前已被激励，关节位置、速度逐位不变 |

总判词 `RESET_CHECK_OK`。负例：同一 manifest 删去 `reset_robot_joints`，A/B 仍过，C 位置残留最大 0.3021 rad、速度 9.5443 rad/s，D 子集残留 0.5245 rad，`RESET_CHECK_FAILED (3)`，证明该检查能抓到重生不写关节的缺陷。日志：`rl_exp/out/lizard2_d_audit_20261022/reset_check.log` SHA256 `e72fd5560d0c0bb69816fa3272f25b2c1e0851fb7fd1974eaaa2f92815446197`，负例 `reset_check_broken.log` SHA256 `5283298c8d063f1564f5f575bbc737b53cb6c7a3f4d9829a63d52e0227dbc392`；工具改后 SHA256 `5ddef4b66f132d9a625daafd9d3a7a64ce453217bda96644e00fabf874df1642`。

边界：此检查只读关节状态，根位姿与速度的重生靠 manifest 的 `reset_base` 零范围声明和承地样本，不是本检查的断言；这是 4 env、一次激励后的 reset，不是自然终止后的回合序列，也不代表正式配方出生高度。

### D 结论

不出具“合格交 S5”。已合格的部分：候选身份、30 通道诊断层映射、观测宽度与非零消费者、四足端集合、30 关节单轴小幅与设置读回、中立 reset 切片、承地短时样本无 NaN/越界。不能放行的部分按责任回交：

- **回 B**：限速的其它关节、10 rad/s 附近与有/无限速对照，决定有效限速“已启用/不启用/未决”；限矩按用户决定不再要求。
- **E 交审核**：旧资产 cap/ownership 与开发选择修复证据已经交付，不再要求重复真跑；E 完整出口与 D 仍需新上下文对照原制品审核。
- **保留组合边界**：左后膝当前单轴及五轴组合已有证据；其余未测范围继续具名保留，执行用户不追加对称复测的决定，不把未知写成通过，也不重新要求同一决定。
- **交 S5**：按[接口方案](2026-10-23-lizard2-training-interface-plan.md)落实动作权限/缩放/裁剪、三种列顺序、出生条件、接触采样以及 reset 根状态/缓存/后端目标核验；初始动作分布与策略性能判据另按原职责固定。方案存在不替代正式配置和运行核验。

事项状态保持 in_progress；`next` 同步到更新后的回交点。B 限速、S5 实装与独立审核仍未完成，未进入关闭；后续 E 证据不再沿用旧“未真跑”状态。

## 证据引用

- 复读输出：`rl_exp/out/lizard2_d_audit_20261022/`（`channel.json`、`standing.json`、`velocity.json`、`vlimit.json`、`cap.json` 及各 `.log`），哈希见上表；本机留存不承诺入仓。
- 原始输入：通道审核 `rl_exp/out/lizard2_e_fresh_tracking_20261020/report.json` SHA256 `6ae21d6db17a46f2431917c5488ace92b8cf6a57f4c87302ab36c8ca8937bb11` 与 `rl_exp/out/lizard2_b_standing_force_20261022_run02/report.json` SHA256 `5a4c6a3f4572ab8db566637c64c67933ee5aa3857092b1fe7ed1b102724453c6`；低上限对照 `rl_exp/out/lizard2_b_cap_physics_20261022/attempt01/report.json` SHA256 `1745e6eb56204a6b901c34371e6021192c123bdeecd9b24a6ba8ec5222f648f0`。
- 来源记录：[RL 通道对表](2026-10-22-lizard2-rl-coordination-handoff.md)、[承地静站力矩](2026-10-22-lizard2-standing-joint-force.md)、[速度/观测](2026-10-22-lizard2-velocity-observation.md)、[限速读回](2026-10-22-lizard2-velocity-limits.md)、[低上限对照](2026-10-22-lizard2-low-cap-comparison.md)、[驱动缺口与提案](2026-10-22-lizard2-drive-gaps-and-cap-plan.md)、[单轴标定](2026-10-21-lizard2-calibrated-loaded-pd.md)、[六组合](2026-10-21-lizard2-calibrated-combinations.md)、[E 在线值](2026-10-22-lizard2-e-live-values-gait.md)、[E 旧对象出口](2026-10-22-lizard2-e-legacy-exit.md)、[fresh 运行时接线](2026-10-15-lizard2-e-spatial-runtime-wiring.md#追加新正式导出身份接入隔离-usd-与真实消费者2026-10-20)。
- 出生高度依据：`rl_exp/versions/lizard2/main/main_params.yaml:6`、`rl_exp/tasks/lizard2_recipe.py:156`、旧机体落定高度见[预训练合理性](2026-10-09-lizard2-v3-pretrain-sanity.md)④，候选根高见承地 `standing_manifest.json` 的 `standing_adapter.root_height_m`。

复读命令（仓根，输出目录须不存在）：

```cmd
E:\IsaacLab\env_isaaclab\Scripts\python.exe -B rl_exp/tools/diagnose/palm_policy_channel_audit.py --tracking_report rl_exp/out/lizard2_e_fresh_tracking_20261020/report.json --approved_tracking_sha256 6ae21d6db17a46f2431917c5488ace92b8cf6a57f4c87302ab36c8ca8937bb11 --current_report rl_exp/out/lizard2_b_standing_force_20261022_run02/report.json --approved_current_sha256 5a4c6a3f4572ab8db566637c64c67933ee5aa3857092b1fe7ed1b102724453c6 --out rl_exp/out/lizard2_d_replay/channel.json
E:\IsaacLab\env_isaaclab\Scripts\python.exe -B rl_exp/tools/diagnose/palm_standing_force_audit.py --report rl_exp/out/lizard2_b_standing_force_20261022_run02/report.json --out rl_exp/out/lizard2_d_replay/standing.json
E:\IsaacLab\env_isaaclab\Scripts\python.exe -B rl_exp/tools/diagnose/palm_velocity_audit.py --legacy rl_exp/out/lizard2_velocity_legacy_20261022_run02/report.json --per_iteration rl_exp/out/lizard2_velocity_per_iteration_20261022/report.json --standing rl_exp/out/lizard2_velocity_standing_20261022/report.json --out rl_exp/out/lizard2_d_replay/velocity.json
E:\IsaacLab\env_isaaclab\Scripts\python.exe -B rl_exp/tools/diagnose/palm_velocity_limit_audit.py --out rl_exp/out/lizard2_d_replay/vlimit.json
E:\IsaacLab\env_isaaclab\Scripts\python.exe -B rl_exp/tools/diagnose/palm_speed_probe.py --replay rl_exp/out/lizard2_b_cap_physics_20261022/attempt01/report.json --approved_report_sha256 1745e6eb56204a6b901c34371e6021192c123bdeecd9b24a6ba8ec5222f648f0 --out rl_exp/out/lizard2_d_replay/cap.json
```

## 未覆盖边界

本机离线复读之外，仅追加一次 `reset_check.py` 候选运行（4 env、各激励 20 控制步，另一次负例），日志见上；没有重验任何驱动参数，也没有做下落出生或自然终止后的回合序列。没有判断学习策略性能、承重协调、抬腿或步态，也没有批准新资产采用、冻结或开训。限速只覆盖左后膝一条自重轨迹，不外推其它关节、额外负载、全姿态或硬件额定；限矩按用户决定不再要求。未审阅接触协议项（`lizard2-contact-protocol`）的关闭条件与 S5 判据，它们不是 D 判据，仍按各自事项承接。D 未得到新上下文独立审核，事项不关闭。
