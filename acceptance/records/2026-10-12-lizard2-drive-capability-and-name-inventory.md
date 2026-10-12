# lizard2 驱动能力、名表存量与接触通道的勘察证据（2026-10-12）

## 适用范围

**这是勘察证据：不是阶段评审，不是设计通过，也不是任何落地决定。** 它固定 2026-10-12 一轮**源码通读**（读文件、不起仿真、不改仓库任何文件）的三份读数，
交给三个在办事项当输入：`work/active/lizard2-body-drive-candidate.md` 的 B 节（驱动能力）与 E 节（名表单点化）、
`work/active/lizard2-contact-protocol.md` 的动作 1（引擎能给的接触通道）。

本记录只把**源码事实与坐标**钉下来，不从读数推出取舍：能力上限怎么绕、名表落哪里、协议收窄到什么程度，归上述事项。
除明写"未验证"的条目外，每条都带 `文件:行`。被测仓为 `E:\Robot`；框架源码在 `E:\IsaacLab\source\`（首次给全路径，之后用唯一文件名坐标准）。

**读数取自工作副本，而工作副本在本轮读取期间正被另一处改写。** 在途（未入库）的名表重构动的是同一批文件：
新建 `rl_exp/tasks/joint_names.py`，并把 `rl_exp/tools/diagnose/*`、`rl_exp/tools/verify/*`、`ablation_harness/baseline_eval.py`、`ablation_harness/baseline_metrics.py` 里那些表换成对它的引用。
B/C 两节的行号取自各次读取的快照，与 **HEAD `494fe73`** 相差 0–8 行（在途重构落了 2–8 行的位移；B1 给的是重构**前**的存量，因为那正是 E 节要消掉的对象）
⇒ **判定依据是"符号↔文件"的对应，行号只作定位线索**；复读命令与 `git diff` 见"证据引用"。

## 验收条件

1. 每条读数必须带可打开的 `文件:行`，且是**源码**而不是文档或注释里的说法（注释与文档串只作为佐证并标明）。
2. 与既有清单相矛盾的条目，必须给出**复读命令**，让下一个人能在同一棵树上重跑，而不是用一句"实测"覆盖。
3. 本轮**不产生**运行读数、不改配方/锁/资产/阈值、不新增闸门；能力上限与缺口只写具名，不修。
4. 不确定的必须留在"未覆盖边界"里具名，不许用"看起来可行"顶替。

## 结果

### A. 驱动能力（B 节输入）

**A1 位置→力矩通路按构造就是线性的。**

- `E:\IsaacLab\source\isaaclab\isaaclab\actuators\actuator_pd.py:137-141`（`ImplicitActuator.compute`）只有一行力矩：`:139`
  `stiffness * error_pos + damping * error_vel + control_action.joint_efforts`（该行只存"近似力矩"给奖励，控制量原样返回求解器）。
- 同一式子在下发的显式模型里再出现一次：`actuator_pd.py:190-195`，核心 `:193`。

⇒ 两条通路都是 `k·(q*−q) + d·(q̇*−q̇) + τ_ff`。**非线性无处可写**：既没有"位置→力矩"的钩子，也没有可插的恢复力函数。

**A2 唯一的表驱动模型也只用表截力矩。**`RemotizedPDActuator`（`actuator_pd.py:370`）持角度→传动比→最大力矩的查表
（`:415-450`；cfg 字段 `actuator_pd_cfg.py:79` `joint_parameter_lookup`），但 `compute` 先调父类拿到**线性 PD** 的力矩（`:443`），
再用查表插值出的上限做 `clamp`（`:445-449`）⇒ 表改的是**幅值**，不是**形状**。

**A3 模型清单（修正任务描述里的枚举）。**`actuator_pd.py` 下只有 `ImplicitActuator:36`、`IdealPDActuator:150`、`DCMotor:203`、
`DelayedPDActuator:310`、`RemotizedPDActuator:370`。**另有** `actuator_net.py:31,101` 的 `ActuatorNetLSTM` / `ActuatorNetMLP`（都是 `DCMotor` 子类）——
两者都是**显式**模型（网络输出力矩），所以不改变 A4 的判词，但"只有这 5 个模型"的说法不完整。
`rl_exp` 与 `ablation_harness` 下**没有**任何自定义 `ActuatorBase` 子类：grep `ActuatorBase` 只命中 `rl_exp/tools/verify/check_configclass_fields.py:302` 的类型判断。

**A4 判词：今天无法表达渐硬/渐变的趾端恢复力。** 两条路都不便宜，且都不是"配一下"：

- (a) 新增 Python `ActuatorBase` 子类覆写 `compute`：纯 Python、可写，但**只对显式执行器生效**，等于放弃本线特意选的物理步长 implicit PD
  （选择理由在 `rl_exp/tasks/lizard2_recipe.py:120-122` 的文档串里：spine 上 50 Hz 显式力矩 PD 不稳定）。
- (b) 走动作通路每子步加外力：**可达性未验证**（见"未覆盖边界"）。

**A5 分组与增益。** 三组全部实例化为 `ImplicitActuatorCfg`（`rl_exp/tasks/lizard2_recipe.py:126-135`），数值来自
`rl_exp/versions/lizard2/main/main_params.yaml:48-78`（腿 `800/40/180/10`、足 `200/12/70/6`、脊 `400/20/80/4`）。

**A6 时间步。** `sim.dt` 0.005、`decimation` 4、`num_substeps: 1` ⇒ 策略 50 Hz / 物理 200 Hz
（`rl_exp/tasks/lizard2_recipe.py:200-203`；`rl_exp/versions/lizard2/main/cfg_lock.json:98`）。

**A7 具名缺口（另立一笔真缺陷）：`velocity_limit` 被静默作废。**

- `actuator_pd.py:81-91`：当 `velocity_limit_sim is None and velocity_limit is not None` 时，先打警告
  （"it was not getting used by implicit actuators … we continue to not use it"），随后 **`cfg.velocity_limit = None`（`:91`）**。
- 而本仓正在设它：`rl_exp/tasks/lizard2_recipe.py:131` 把 yaml 的 `velocity_limit` 传进 `ImplicitActuatorCfg`；
  `rl_exp/versions/lizard2/main/main_params.yaml:58,66,77` 给的是腿 10、足 6、脊 4 rad/s。
- ⇒ **这三组速度上限到不了求解器**。USD 关节 prim 自己是否另带速度上限：**未验证**。

本记录**不改任何配方**（`lizard2_recipe.py` 一行都不动）：A7 是账，不是修复；修不修、怎么修归 B 节决定。

**A8 限位与裁切。** 限位是物理限位（USD/PhysX）加一条 0.95 软带（`rl_exp/tasks/lizard2_recipe.py:161` `soft_joint_pos_limit_factor=0.95`）；
动作侧**不裁切**——用的是 `JointPositionActionCfg`（`rl_exp/tasks/lizard2_env_cfg.py:102-107`），不是 `ToLimits` 变体。

### B. 名表存量（E 节输入，修正旧清单）

**B1 真正的硬编码表：7 个符号 / 6 张表**（"表"按内容去重：前两张字面量相同）。**坐标 = HEAD `494fe73` 的存量**——
先给存量，因为"同一份事实被抄 7 遍"正是 E 节要消掉的对象；工作副本上这份清单正被在途重构逐条换成对共享模块的引用。

| # | 落点 | 符号 | 形态 |
|---|---|---|---|
| 1 | `rl_exp/tools/verify/check_joint_layout.py:193` | `_LEG_TOKENS` | 裸词根 `("hip","haa","hfe","kfe","foot")`；`:204` 又用 `f"{prefix}_foot"` 找链端点 link |
| 2 | `rl_exp/tools/verify/check_self_collision.py:59` | `_LEG_TOKENS` | 同上（裸词根，内容与 #1 重复） |
| 3 | `rl_exp/tools/verify/check_leg_reachability.py:121` | `CHAIN` | 裸词根；`:124` `HINGES = CHAIN[1:4]` 由它派生 |
| 4 | `rl_exp/tools/diagnose/plot_joints.py:36` | `JOINTS` | 只有 3 个词根 `("hip","hfe","foot")` |
| 5 | `rl_exp/tools/diagnose/gait_probe.py:102` | `LEG_SUFFIXES` | 带后缀 `"_hip_joint"` 等 |
| 6 | `ablation_harness/baseline_metrics.py:866` | `_LEG_TOKENS` | 带后缀；`:894` 用 `name.endswith(_LEG_TOKENS)` |
| 7 | `ablation_harness/baseline_eval.py:54` | 函数内本地 `tokens` | 带后缀，**不是**模块级符号 |

另有 `rl_exp/tasks/obs_protocol.py:32` `_FOOT_SUFFIX = "_foot_ring"` 一处同类但不同种的表（观测协议的分组后缀）。

**B2 旧清单里被证伪的四条。**复读命令见"证据引用"。

| 旧说法 | 实测 |
|---|---|
| `gait_probe.py` 有 `_LEG_TOKENS` | 错：它叫 `LEG_SUFFIXES`（`:102`） |
| `baseline_eval.py` 有 `_LEG_TOKENS` 符号 | 错：是函数内的本地元组 `tokens`（`:54`） |
| `_LEG_TOKENS` 只出现在 2 个文件 | 错：**3 个**（`check_joint_layout.py:193`、`check_self_collision.py:59`、`baseline_metrics.py:866`）——本轮清单的符号枚举里它自己就出现了 3 次，与同一清单"只在 2 个文件"一条互相矛盾；以 grep 为准 |
| 旧清单已穷尽 / "约 25 个文件"是要守的上限 | 数量随**拼写口径**变：窄口径（`_x_joint`/`_x`）22 个 `.py`，词级口径 49 个 ⇒ "≥30" 只在词级口径下成立，窄口径下不成立。**真正错的是枚举（符号名与漏项），不是量级**；量级不该被当成可守的读数 |

**B3 旧清单漏掉的落点**（按 B2 的窄口径也扫得到，但旧清单只列到"任务 / 诊断 / 校验 / 评测"四类的一般项）：

- Blender：`rl_exp/blender/build_rig.py`、`rl_exp/blender/generate_urdf.py`（`AXIS_MAP` / `leg_pivots`）。
- 任务：`rl_exp/tasks/lizard2_env_cfg.py:104`；`rl_exp/tasks/teacher_mdp.py:185,1570,1635`；`rl_exp/tasks/obs_protocol.py`（`_FOOT_SUFFIX`）。
- 校验：`rl_exp/tools/verify/check_actuator_budget.py:645-646`、`check_dr_parity.py:845-868`、`obs_protocol_live.py:51`、
  `test_baseline_contract.py:48,516,564`。
- 诊断：`rl_exp/tools/diagnose/stance_step_probe.py:166-167`、`diag_metrics.py:287`。
- 评测：`ablation_harness/baseline_frames.py:69-90`。
- 数据面：`rl_exp/ue/lizard_ue.json`、`rl_exp/versions/joint_order_runtime.json`。

**B4 三种方言并存**：裸词根（#1/#2/#3/#4）、`_x_joint` 后缀（#5/#6/#7）、`.*_x_joint` 正则（配置与动作接口）。
它们不是同一张表的三种写法：裸词根要能匹配"关节名、link 名、正则片段"，后缀版只匹配关节名 ⇒ 一张表统一它们必须**先定口径**，否则是把三件不同的事压成一个符号。

**B5 `.*_foot` 是超载的，改名会静默改语义。** `.*_foot` 同时匹配**关节** `*_foot_joint` 和**刚体/link** `*_foot`
（`rl_exp/tasks/teacher_mdp.py:185` `self.robot.find_bodies(".*_foot")`），而链端点也是按 `f"{prefix}_foot"` 找的
（`check_joint_layout.py:204`）⇒ 拆成前肢 `finger` / 后肢 `toe` 会同时改掉**接触体集合**与**链端点查找**，两处都不报错、只是少/多匹配。
这是 E 节动作 2"旧名机体上全部自测保持绿"要专门覆盖的一格。

**B6 规模边界（必须写进 E 节动作）**：`rl_exp/versions/**` 下还有约 40 个 yaml 与 100+ 个 json 的硬编码点，被
`rl_exp/tools/verify/check_cfg_lock.py` 与 `/check_golden_frozen.py` 钉住
（后者按文件摘要钉 `rl_exp/versions/*/*/cfg_lock.json`：`check_golden_frozen.py:75-144,191`）⇒ **改那里=版本行为**（`.codemaker/rules/versioning.mdc` §A），
不是查找替换；E 节的动作范围必须把这条写在门外。

**B7 落点先例。** `rl_exp/tasks/obs_protocol.py` 就是本仓已有的"纯标准库、单一家的名表"：
模块头写明"Stdlib only and no isaaclab import"（`:14-15`），导入只有 `functools/hashlib/json/pathlib/xml.etree`（`:24-28`），
消费它的是 `rl_exp/tools/verify/check_obs_protocol.py`。名表照这个先例放 `rl_exp/tasks/`。
另外 `rl_exp/blender/*` 跑在 Blender 自带解释器里，不能 import isaaclab/torch——这条约束决定名表必须是纯标准库。

### C. 接触通道缺口（接触协议输入）

**C1 今天能拿到的**：

| 通道 | 落点 |
|---|---|
| `foot_lowest_point`（最深网格顶点，每帧） | 采集 `ablation_harness/baseline_eval.py:235-237`；实现 `rl_exp/tools/diagnose/diag_metrics.py:215-237` |
| `foot_com_pos` / `foot_lin_vel` / `foot_ang_vel` | `ablation_harness/baseline_eval.py:238-240`（注释 `:230-233` 说明为何用 COM 而非 link 原点） |
| 重建的 `foot_point_velocity`（`v_com + ω × (p − p_com)`） | `ablation_harness/baseline_metrics.py:563-574`，实现在 `rl_exp/tools/diagnose/diag_metrics.py:398-420`（`ponytail:` 上限写在 `:415-418`） |
| body 级法向力 | `ablation_harness/baseline_eval.py:211-212`（`sensor.data.net_forces_w`，取 `[:, :, 2]`） |

**C2 具名缺口（协议动作 1 需要的"通道存在性"答案）**：

- **逐接触对的接触点位置**：`force_matrix_w` 在本仓**一次都没被读过**——只在 `diag_metrics.py:415-418` 的 `ponytail:` 注释里被点名为升级路径。
  ⇒ 现在脚尖位置是"最深网格顶点"这个**几何猜测**，不是引擎给的接触点。
- **逐接触对的材料点速度**、**逐对法向力**：无通道，也没有替代（最低顶点跳变不算材料点速度）。
- **足端相对机身的摆幅**：没有报告项。
- **运行期接触面法向**：现在**假定**来自 `meta.ground_source.normal`（`ablation_harness/baseline_metrics.py:585-587`），不是当帧读出的。

**C3 滚动 vs 有效阶段：现有通道分不开。** `foot_slip_v1`（`baseline_metrics.py:633-651`）用切向速度阈值判滑移，
载荷期滚动与真滑动在它眼里**同一种**读数（它只问"切向速度超阈值"）。

**C4 报告项的依赖列检查是无条件跑的，但**对没有 `REPORT_ITEMS` 声明的名字会 `continue`：
`ablation_harness/baseline_metrics.py:1094-1101`（`:1096-1097` 就是那个 `continue`）。
而 `foot_yaw_deg`、`dof_torque_frac_of_limit` 被 v5 协议声明进 `report_only`
（`ablation_harness/protocols/lizard2_flat_v5.json:165,167`），却**不在** `REPORT_ITEMS`（`ablation_harness/baseline_metrics.py:107-166`）
⇒ 这两个报告项**被静默不检查**。这正是接触协议动作 4 要消掉的东西。

**C5 `no_non_foot_carrier` 的 dwell 幅值无法按"异常承重体"标定**：`non_foot_fraction` 是逐体聚合，在时间之前被
`any(dim=-1)` 压掉（`ablation_harness/baseline_metrics.py:300-310` 及其文档串：这个顺序**就是判据本身**——
"轮流扛"会累加成一次持续读数，想读"某一个体单独扛住"是另一个观测）。

**C6 采集器丢掉引擎已经给的历史**：`net_forces_w_history` 在别处被用（`rl_exp/tasks/teacher_mdp.py:631`、
`rl_exp/tools/verify/baseline_probe.py:133,380`、`baseline_runtime.py:69`、`check_contact_ownership.py:204`），
但 `ablation_harness/baseline_eval.py:211` 每帧只取当帧 `net_forces_w`。

## 证据引用

- 需求来源：2026-10-12 用户要求"驱动能力表 + 名表盘点 + 接触通道"三份勘察输入，不改仓库。
- 上游事项：`work/active/lizard2-body-drive-candidate.md`（B/E 节）、`work/active/lizard2-contact-protocol.md`（动作 1）；
  名表口径的上游决定在同事项"骨骼改名"节（2026-10-10 用户拍板）。
- 框架源码：`E:\IsaacLab\source\isaaclab\isaaclab\actuators\actuator_pd.py`、`actuator_pd_cfg.py`、`actuator_net.py`；
  `E:\IsaacLab\source\isaaclab_physx\isaaclab_physx\sim\schemas\schemas_cfg.py`（`:287-303`，`PhysxJointDrivePropertiesCfg`
  文档串自述 "Currently empty after the consumption-gated split"，留作旧名的弃用别名目标）。
- 本仓配方/版本：`rl_exp/tasks/lizard2_recipe.py`、`rl_exp/tasks/lizard2_env_cfg.py`、
  `rl_exp/versions/lizard2/main/main_params.yaml`、`rl_exp/versions/lizard2/main/cfg_lock.json`。
- **行号漂移的来源**（不是本轮的成果，也不在本轮评估范围内）：工作副本上有另一处未入库的名表重构在跑 ——
  `rl_exp/tasks/joint_names.py` 新建，并把上列几个工具里抄写的表换成 `joint_names.CHAIN_ROOTS` / `JOINT_SUFFIXES`。
  复读：

```bat
git log --oneline -1                      :: 本记录的锚点
git status --short                        :: 在途文件清单
git diff -U2 -- rl_exp/tools ablation_harness   :: 在途重构把哪几行表换成了引用
```

- 名表复读（B2/B3 的复读命令，在 `E:\Robot` 下跑）：

```bat
:: 符号在哪几个文件里（B2 第 3 行）
rg -n "_LEG_TOKENS" -g "*.py" rl_exp ablation_harness
:: 窄口径：带 _x_joint / _x 词根的文件数（本轮 = 22，已排除 versions/.git/__pycache__）
python -B -c "import pathlib;toks=('_hip_joint','_haa_joint','_hfe_joint','_kfe_joint','_foot_joint','_hip','_haa','_hfe','_kfe');files=[p for p in pathlib.Path('.').rglob('*.py') if '.git' not in p.parts and '__pycache__' not in p.parts and 'versions' not in p.parts];print(len([p for p in files if any(t in p.read_text(encoding='utf-8',errors='replace') for t in toks)]))"
:: 词级口径（本轮 = 49）
python -B -c "import pathlib,re;pat=re.compile(r'\b(hip|haa|hfe|kfe|foot)\w*\b');files=[p for p in pathlib.Path('.').rglob('*.py') if '.git' not in p.parts and '__pycache__' not in p.parts and 'versions' not in p.parts and 'archive/2026' not in p.as_posix()];print(len([p for p in files if pat.search(p.read_text(encoding='utf-8',errors='replace'))]))"
:: 接触通道（C2/C6 的复读）
rg -n "force_matrix_w|net_forces_w_history" rl_exp ablation_harness
:: 报告项声明与实现（C4）
rg -n "foot_yaw_deg|dof_torque_frac_of_limit" ablation_harness/protocols/lizard2_flat_v5.json ablation_harness/baseline_metrics.py
```

- 相关既有记录（口径归属，本轮不改写）：`acceptance/records/2026-10-10-lizard2-v3-joint-velocity-limits.md`（速度上限话题的既有读数在那边）、
  `acceptance/records/2026-10-10-lizard2-carrier-dwell-calibration.md`（`no_non_foot_carrier` 的 dwell 标定与缺口）。

## 未覆盖边界

**A 侧（驱动）**

1. **没有 API 吃 `tau(q)`**：本轮只能证"现有通路是线性 PD + 截幅"，不能证"框架里绝对没有别的插入点"——`Articulation` 的动作/物理包装层（含 `_physics_handles_decimation`）
   没读；**lizard2 的 `_physics_handles_decimation` 是否为真未验证**，而它决定"显式执行器是否真的每子步都算"。
2. **每子步加外力的扩展点没追**：动作通路上能不能每物理子步施加外力，**未验证**（A4(b) 的可达性就是这条）。
3. **A7 的 USD 侧未查**：`*_foot_joint` 的 prim 上是否另有 `physxJoint:maxJointVelocity` 之类的限速，未验证
   （`PhysxJointDrivePropertiesCfg` 本身现在是空的，见证据引用）。
4. **不对训练影响出结论**：A7 没跑，速度上限"丢掉"对已训 v3 与后续训练的影响量级是**未知**，只是账。
5. **`ActuatorNet*` 只是出现在清单里**：它的 cfg 与显式力矩链没读，能否表达渐硬恢复力未判（本轮不判）。

**B 侧（名表）**

6. **计数不是判据**：22 / 49 两个数都只是同一把尺子的两个口径，且没有逐个确认命中是"表"还是散文/注释；**别把计数写成目标**。
7. **yaml/json 侧的完整清单没做**：B6 只给了边界（约 40 yaml + 100+ json 在 `versions/**`），没有逐点枚举；`rl_exp/ue/lizard_ue.json`、`joint_order_runtime.json` 只作为点名前两个。
8. **没有验证"新名表能同时服务新旧两套名"**：B7 只给先例与约束（纯标准库、Blender 可导入），接口形状、链顺序表达、接触体集合接口都还没设计。
9. **`.*_foot` 之外是否还有别的超载正则**（例如 `.*_hip`、`chest_.*` 同时匹配关节与 link）没有逐条核。

**C 侧（接触）**

10. **没有起仿真**：C 全部是"代码里有没有这个通道"，不是"这个通道在 lizard2 上读数合理"。
11. **`force_matrix_w` 能不能在本线加上**：配方不能动（会改冻结的 cfg 摘要，`work/active/floor-contact-attribution.md` 已记同一结论），
    所以在诊断器自建 cfg 里建它是否可行、成本多少，未测。
12. **滚动/有效阶段的区分口径**没有给出——C3 只说现有通道分不开，替代口径要接触协议事项自己定。
13. **C4 只证"这两个项不被检查"**，没有穷举还有哪些协议声明项同样落在 `REPORT_ITEMS` 之外（本轮只按 v5 的两个点核）。

## 追加：E 名表单点化落地（2026-10-12 同日）

本节写于落地之后，**不改上面任何读数**：那些是读取当时的快照。但 **B 节的行号是重构前的存量**，重构已入库，复读时按符号名定位，不按行号。

- 落点 `rl_exp/tasks/joint_names.py`：B1 的 7 处拷贝改读 `CHAIN_ROOTS`/`JOINT_SUFFIXES`；同文件里的第二份全链（`check_joint_layout.py` 的 `_LEG_ORDER`）、`check_self_collision.py` 的三个铰、`check_leg_reachability.py` 的 `HINGES` 与 `("hfe","kfe")`、`gait_probe.py`/`plot_joints.py` 的三列、`stance_step_probe.py` 的两条后缀串、`lizard2_env_cfg.py` 的动作正则表 → 一律表。
- 表新增（B5 那格要求的接口）：`HINGE_ROOTS`、`REPORT_ROOTS`（位次推导，非字面词）、`CONTACT_BODY_PATTERNS` + `is_contact_body()`。`end_link()` 从此有消费者：`check_joint_layout.py` 的链端点、`check_leg_reachability.py` 的链走查与 pad 网格。
- 读数：
  ```bat
  python -B rl_exp/tasks/joint_names.py        :: 四组断言：三方言 x 5 x 4、派生选择 + 接触体模式、计划名形状、stdlib 导入面
  rl_exp\tools\verify\run_offline_checks.bat   :: 37/37 绿（含 [30] 配方逐字段 golden、[31] obs 协议声明、[37] 链口径）
  ```
- 破坏测试（确认新断言咬得住，不是摆设）：把 `CONTACT_BODY_PATTERNS` 的末根换成首根 ⇒ (b) 段以 `{'rr_foot', ...}` 失败；把前肢末端计划名 `finger` 改成 `toe` ⇒ (c) 段的跨组重名断言先命中。⇒ 为此**删掉**了一版"计划侧模式一分为二"的新断言：它只能在前一条已失败的状态下触发，即死代码。
- 未迁站点，**归机体换代那一次变更**（本记录上游事项的用词就是"接触体名随名表同变更迁移"），静默与会报错的分开记：
  - 静默（改名后不报错、只是少匹配）：按后缀找接触体 —— `rl_exp/tools/diagnose/diag_metrics.py:141`、`diagnose_support.py:427,447,817,822`、`rl_exp/tools/verify/baseline_probe.py:270-271`、`check_contact_ownership.py:209`、`obs_protocol_live.py:141`；按单词取值 —— `check_self_collision.py:278,288`（`limits.get("hip"/"hfe")`）、`gait_probe.py:878-879`（`group_effort` 的键）；CLI 默认值与显示过滤 —— `check_joint_layout.py:116,123`、`check_actuator_budget.py:528`。
  - 会报错（迁移时自然暴露，不必先改）：`check_leg_reachability.py:816,1250`（`tokens.index("hfe")`）、`fit_gait_target.py:118-119`。
  - 门外不计入：`rl_exp/versions/**`（B6）、`rl_exp/blender/*`（A 节候选，走计划名）、v8 一次性迁移脚本、测试里故意钉死的字面名。

## 追加二：本次勘察两个未交项的读数（同日）

subagent 2 的交付里，yaml/json/md 全量清单与"必须保持绿的既有自测"清单没交。这里只补**读数与缺席的代价**，不补做枚举（理由见下）。

**A. 声明面（口径：`_` 与 `.` 也算分隔符，故 `lf_foot`、`.*_hip_joint` 计入；本记录 B 节用的 `\b` 口径抓不到它们）**

| 面 | 文件 / 命中 | 处置 |
|---|---|---|
| `rl_exp/versions/**` 的 yaml+json | 62 / 3887 | **门外**（改=版本行为，见 B6）⇒ 只需边界行，不是清单 |
| `versions/` 之外的声明面 | **2 / 94**（`rl_exp/ue/lizard_ue.json` 92、`rl_exp/tools/verify/gait_targets/lizard2_low_speed_v0.json` 2） | 可动全集，就这么点 |
| `rl_exp/tools/diagnose/out/**` 等生成读数 | ~91 / ~19.6k | 探针输出的列名，是**读数不是声明** |
| `.md` 全仓 | 130 / 1434，几乎全在 `acceptance/records/**` | 历史读数，改写=伪造历史 ⇒ 不入册 |

⇒ "逐点枚举"的原形状会产出上万行里 0 行可执行；该补的是上表（三行边界 + 一行全集）。

复读（口径同表头）：
```bat
python -B -c "import pathlib,re;pat=re.compile(r'(?<![A-Za-z0-9])(hip|haa|hfe|kfe|foot)(?![A-Za-z0-9])');f=[p for p in pathlib.Path('rl_exp').rglob('*') if p.suffix in ('.yaml','.yml','.json')];h={p.as_posix():len(pat.findall(p.read_text(encoding='utf-8',errors='replace'))) for p in f};n={k:v for k,v in h.items() if v};print(len(n),sum(n.values()))"
```

**B. 既有自测（本轮改动碰过的 6 个工具）**

| 工具 | 离线入口 | 本轮真跑 |
|---|---|---|
| `check_leg_reachability.py` | 套件 [37] | 绿 |
| `plot_joints.py` | 自带 `--self-check`（不在套件里） | 绿 |
| `gait_probe.py` | 自带 `--self-check`（不在套件里） | **红（既存）** |
| `check_joint_layout.py`、`check_self_collision.py`、`stance_step_probe.py` | 无（sim-only） | 未验 |

`offline_suite.py:145` 只挂了 `check_leg_reachability --self-check`，其余自检无机器入口 ⇒ 上游事项"旧名机体上全部现有自测与闸门必须保持绿"本轮**只对 3/6 成立**，另 3 个只有 `py_compile` 与"值未变"的推断。

**C. `gait_probe --self-check` 的既存红（与本次改名无关）**

- 读数：`python rl_exp/tools/diagnose/gait_probe.py --self-check` ⇒ `gait_probe.py:426` 家族隔离断言失败
  `('lizard2', rl_exp/lizard2_candidate/meshes/collision, 0.11928214877843857, 0.013352)`（该块 `:416-428`）。
- 对拍：`git show HEAD:rl_exp/tools/diagnose/gait_probe.py` 的同一自检**同样红、同一组数** ⇒ 既存，非本轮引入。
- 两家族网格非同一文件（md5 `032544db` vs `80145e27`，树也不同），但形状一致：都 48 面、0.16423 m²、2 mm 带 cap 均 0.1192821，仅 z 偏移差 ~4.4 mm（接地归一化后消失）。
- 本脚本分不清两种解释：常数过期（候选掌面有意重做，钉的仍是旧 lizard2 机体的值）或候选声明树里的 `rl_foot_collision.obj` 退化成旧平底壳。判据在源 obj 与 `.blend`，归 A 节。

### 判定（同日，只读）

两种解释都不对。**这是一条前提已死的陈旧钉值**，与本次改名、与"候选壳被换错"都无关：

- 钉值测的是"两家族、两棵树、两种形状"。`versions/lizard2/assets.json` 自己写着家族在 main/v3（提交 `4928ced`，2026-10-08）采用新机体、`meshes_dir` 换成 `lizard2_candidate/meshes`、旧机体版本退休 ⇒ **2026-09-28 那次读数量的旧机体树已被退休**，钉值随即失效，没人发现。
- 今天盘上**三个** rl 壳读同一个值 0.119282（面积 0.16423、48 面）：退役 lizard 家族（`rl_exp/meshes/collision`，自 `91a876a` lizard-v8 未再动）、本地构建树 `rl_exp/lizard2_urdf/meshes`、采用机体 `rl_exp/lizard2_candidate/meshes`（sha256 `c3a4aa71…` == v3 `asset_lock.json` 的摘要 ⇒ 采用后未再动）。
- ⇒ "修好的圆顶 0.013352"在盘上**任何树里都不存在**；断言的前提（两家族形状不同）没了，所以它今天无论隔离好坏都只能报错。

**未决（归 A 节，git 查不出）**：圆顶是被有意放弃（新机体掌面另设计）还是换代时丢了。产生它的树是 `.git/info/exclude:7` 排除的本地构建树（`rl_exp/*_urdf/`），无 git 记录；钉值那次读数也没有记录文件。

**这条自检的处置建议**（不动资产）：它今天已不能测它声称的东西 —— 要么改判成"两家族解析到不同目录、各自 usda 引用落在自己树里"（`check_dr_parity` 的 asset isolation 已在看这件事），要么改成对采用机体的读数、丢掉"两家族不同形状"的前提。它没有机器入口（`offline_suite.py:145` 只挂 `check_leg_reachability`），所以这类"前提死了"的红只能靠人偶然跑到。

### 追加四：勘误 —— 追加三的判定错了（同日）

追加三判成"前提已死的陈旧钉值、那个圆顶盘上任何树里都不存在"。**两点都错**。逐脚实测（2 mm 带 cap，m²）：

| 树 | lf | rf | rl | rr |
|---|---|---|---|---|
| `rl_exp/lizard2_candidate/meshes`（**家族声明树**，即 v3 锁锁住的机体） | 0.013352 | 0.013352 | **0.119282** | **0.119282** |
| `rl_exp/lizard2_urdf/meshes`（`.git/info/exclude:7` 的本地构建树） | 0.013352 | 0.013353 | **0.119282** | 0.013352 |

- 穹面**存在**：lf/rf 两树都是 0.013352，构建树的 rr 也是。追加三只量了 rl 一只就下了"不存在"的结论 —— 错。
- 钉值是 **rl 专属**的。rl 今天在两棵树里都读 0.119282（= 另三只的 9 倍），正是 `acceptance/records/2026-09-28-lizard2-foot-hull-and-asset-isolation.md` 的**修前**读数。
- 那份记录自己的验收口径是"**四只全同形**（0.013352/0.013353）"（`:56,:58`），且这条 `gait_probe --self-check` 断言是**同一次变更**加的（`:60`）。今天采用机体是 **2 平 2 穹**（rl+rr 平）⇒ **当时验收过的几何修复没有留在家族声明的机体里**。
- 采用机体的 rl 摘要 == v3 `asset_lock.json` 值 ⇒ 采用（2026-10-08）当时它就是平的，不是之后被改。
- ⇒ **分类改判：不是陈旧钉值，是"已验收的修复没留在采用机体里"**（回归或跨树丢失）。归属从"归 A 节"改为 **`work/active/floor-contact-attribution.md` 的 ⑤/⑪ 资产前提**。未决仍是"有意换设计 vs 修复丢失"，git 判不了：产生/承载它的构建树被排除在版本控制外。
- 追加三保留不删（记录不改写），判定以本节为准。

## 追加五：E 出口复核与方案回写（2026-10-12）

### 适用范围

复核 `work/active/lizard2-body-drive-candidate.md` E 节的完成口径与下一步契约。本次只改该事项及本记录，不改 Python、配方或资产，不启动 Blender/仿真；源码观察不是行为验证。此前“追加：E 名表单点化落地”保留作当时记录，其完成含义按本节收窄。

### 验收条件

第一波由 B 的必要前置约束明确与 E 的双机体接口消费验证共同构成。E 须让同一消费者显式处理旧机体与新命名目标，入口绑定来源明确，URDF/运行时名称验真，接触体、动作选择和报告读取贯通；仅导入名表、名表自检或离线套件通过不满足此出口。完整施工与后续验收形状唯一归事项 E1–E4，不在本记录复制。

### 结果

- **E 未达到第一波出口**。源码中的 `CHAIN_ROOTS`、`JOINT_SUFFIXES`、`end_link()`、`CONTACT_BODY_PATTERNS` 与 `is_contact_body()` 仍回答旧名；`PLANNED_RENAMES` / `planned_root()` 是独立映射，没有目标机体绑定。此前自检的新名部分验证映射形状，不能证明真实消费者能用新名。
- **具体可失败路径，不是运行读数**：`check_joint_layout.py` 在导入模块后把 `joint_names` 赋成运行时 list，随后访问 `.CHAIN_ROOTS` / `.end_link()`；`gait_probe.py` 的 `main()` 在读取 `joint_names.JOINT_SUFFIXES` / `.is_contact_body()` 后又赋同名局部 list。这是实际消费者需要就地修复的名称遮蔽；本轮未执行该路径，不以 py_compile 代替验证。
- **多下划线风险**：`check_joint_layout.py` 用 `rpartition('_')` 从 link 拆词根；`shoulder_swing` / `shoulder_abduct` 不能按旧单词根方式解析。方案要求生成完整名称映射或剥已知前后缀，不靠猜名选机体。
- **用户拍板：2026-10-12**：工具入口绑定目标及其命名方案，内部传递；不在每层手选 `legacy/candidate`，不用会随采用改变含义的标签。声明错配实际 URDF/运行时名称时拒绝，不自动回退。
- **方案回写**：事项 E 节区分入口绑定、真实树结构、接触体/关节、消费者接线、双样本负例与正式采用边界；`next` 改为先做 E，不再把已有名表当作完整交付。B 的约束与有效限速欠账保留，既有资产前提仍交 `floor-contact-attribution`，不借 E 改资产。
- **方案交叉检查**：新上下文指出绑定数据形状与全局 active 说明仍可误读，已把待实现绑定明确为目标路径、声明来源、每 leg 的角色→词根映射及末端角色，并禁止 E/S6 靠翻转 `PLANNED_ACTIVE` 选机体。该检查中“前后肢共享 hip_swing/hip_abduct”与源码不符，未采纳；“接口尚不存在因此方案不可成立”不作为实现判据。这里是方案复核，不是 D 的关闭审核，也不宣称消费者已验证。
- **本轮文档验证**：`python -B rl_exp/tools/verify/check_work_docs.py` 返回 `WORK_DOCS_OK (85 item file(s))`；`git diff --check` 无差异格式错误；`rl_exp\tools\verify\run_offline_checks.bat` 返回 `ALL_OFFLINE_CHECKS_PASSED (37/37 in 43.1s)`，退出码 0。套件覆盖既有仓库约束，不运行 E 的双机体/Blender/仿真验收，不能据此改判 E 完成。

### 证据引用

本节源码坐标对应方案复核时工作树，后续按符号定位：

- `rl_exp/tasks/joint_names.py:51,105-111,123-133,150-175,230-262`：旧名派生接口、独立计划映射与自检边界。
- `rl_exp/tools/verify/check_joint_layout.py:143,153,194,204-208`：模块遮蔽及单词根拆法。
- `rl_exp/tools/diagnose/gait_probe.py:817,826,831,849-853`：作用域遮蔽、旧链端后缀及 shank 名旁路。
- `rl_exp/tasks/obs_protocol.py:363-409`：已有目标路径解析接口；采用实际 cfg 覆盖时调用 `resolve_body()`，不拿默认任务路径代替覆盖目标。
- `rl_exp/tools/verify/check_leg_reachability.py:219-269`：实际 URDF 链走查与 load_chain 消费点。
- `rl_exp/blender/generate_urdf.py:65-75`：已有构建目标声明入口。
- `rl_exp/tools/diagnose/plot_joints.py:46,54-70`：报告 reader 的全局旧词根与列名消费点。
- 事项修订验真：`python -B rl_exp/tools/verify/check_work_docs.py`；仅文档形状检查，执行状态以本次命令输出为准，不是 E 行为复读命令。

### 未覆盖边界

本次没有实现入口绑定，没有运行双机体消费者、破坏测试、Blender 导出或仿真，没有验证候选几何/动力学；E 保持未交付，不关闭事项、不置 pending_review。已有红项不豁免后续必需消费者的验证；真实候选未就绪时，完整改名的同几何临时样本只能证明双命名接线。文档形状通过不等于接口能力通过。

## 追加六：E 第一切片落地（2026-10-12 同日）

### 适用范围

E 的“绑定 + 首个真实消费者”切片：名表两套命名、`check_leg_reachability.py` 的入口绑定与链命名核对、同几何改名孪生的正负例。读数为离线（无仿真、无 Blender、无运行时）；其余消费者（Blender 构建入口、`check_self_collision`、`check_joint_layout`、站姿/步态诊断、接触诊断与在线协议核对、报告 reader）与 E4.4 的运行时/报告验真不在本次。

### 验收条件

同一套读者要能显式服务旧机体和新命名机体，绑定与实际 URDF 不符必须拒绝，且拒绝本身要被负例咬住；读数、破坏测试与复读命令可复现。

### 结果

- **绑定落点**：`rl_exp/tasks/joint_names.py` 新增 `LEGACY_NAMING`/`SPLIT_NAMING`/`NAMINGS`（`shared`/`split`，`split` 由 `PLANNED_ROOTS` 派生，不是第二张表）、`naming_for`、`roots_of`，并把 `end_link`、`contact_body_patterns`、`is_contact_body` 改为按绑定求值（默认仍是旧名，现有调用者行为不变；`CONTACT_BODY_PATTERNS` 值不变）。模块自检新增 (d) 段：两套命名同形、`split` 即计划改名逐 leg、末端 link 与接触模式按肢组移动、未列命名与未列 leg 一律拒绝。
- **消费者落点**：`rl_exp/tools/verify/check_leg_reachability.py` 入口加 `--naming`/`--compare-naming`（声明，不从关节名猜），绑定沿 `chain_joint_names`/`load_chain`/`downstream_links`/`pad_mesh`/`pad_vertices`/`pad_faces`/`pad_normal_in_link`/`_candidate_read`/`compare`/`fold_reading` 传递；`_verify_chain` 在产品路径上核对“链必须终于声明命名的末端词根、且命名自带的词根按序出现”，不符即 `SystemExit` 并打印差异；`--compare` 的两个机体各自绑定。
- **同几何孪生（真消费者，非模块自检）**：`--self-check` 内建 `_naming_twin_check`，用 `_renamed_twin` 临时生成只改名（`link/@name`、`joint/@name`、parent/child；mesh 引用改绝对路径以便落临时目录）的孪生，经真实 reader 比对：链 token == 绑定词根、逐关节 origin/rpy/axis/limits 全等、pad 网格解析到同一文件、pad 顶点与 `foot_pose` 全等；负例三条——孪生按 `shared` 读、原机体按 `split` 读、以及只改关节不改 link 的混合体按 `shared` 读——必须全被拒绝。
- **咬合验证**：停掉 `_verify_chain` 后自检在混合体那条转红（`AssertionError: a body whose joints were renamed and its links not`），说明该核对不是装饰；孪生首次实现只改 link 未改 joint 时，正例断言当场失败（token 仍旧名），说明等值断言能发现半改名。
- **既有口径不退化**：`check_leg_reachability.py --break-test` 九条扰动全部被咬住；`check_leg_reachability.py --self-check` 与插入关节夹具（`..._fem.urdf`）都通过——`_verify_chain` 只钉“末端词根 + 自带词根有序”，机体自插的关节仍按树读取（该天花板已用 `ponytail:` 注释标出：中途半改名的机体不在拦截内，因改名按肢组原子发生）。

**复读命令与实测**（工作树 HEAD 变更，`<PY>` = `python ablation_harness/host_paths.py --python` 给出的解释器）：

- `<PY> rl_exp/tasks/joint_names.py` → `[SELF-CHECK] ... the two namings answer per leg with one shape -- the split one being that same rename, moving the end link per limb group -- and an unlisted naming or leg is refused rather than defaulted into the old words`（纯标准库，PATH python 亦可）
- `<PY> rl_exp\tools\verify\check_leg_reachability.py --self-check` → `[NAMING-TWIN] a renamed twin loads through the same consumer under its own binding (split on lf/rl): chain tokens, origins, rpy, axes, limits, pad mesh and pad pose all identical to the original, and each body refuses the other's naming`
- `<PY> rl_exp\tools\verify\check_leg_reachability.py --break-test` → `BREAK_TEST_OK (9 perturbation(s), every one caught)`
- 破坏 `_verify_chain` 后重跑自检 → `AssertionError: a body whose joints were renamed and its links not: it read a chain that naming does not describe`
- `rl_exp\tools\verify\run_offline_checks.bat` → `ALL_OFFLINE_CHECKS_PASSED (37/37 in 39.0s)`，含 `[37/37] leg chain caliber` 与 `[9/37] WORK_DOCS_OK`

### 证据引用

- 绑定：`rl_exp/tasks/joint_names.py` 的 `LEGACY_NAMING` / `roots_of` / `end_link` / `contact_body_patterns` / `is_contact_body` / `SPLIT_NAMING` / `NAMINGS` / `naming_for` 及自检 (d) 段。
- 消费者与核对：`rl_exp/tools/verify/check_leg_reachability.py` 的 `_verify_chain` / `chain_joint_names` / `_naming_id` / `_renamed_twin` / `_naming_twin_check` / `main` 的 `--naming`、`--compare-naming`。
- 路由：`FILEMAP.md` 该工具行（`--naming` 与孪生是选中它的判别点）。
- 事项与证据同变更落地：`work/active/lizard2-body-drive-candidate.md` 的 E1/E2.1/E3 接线现状与 `next`。

### 未覆盖边界

- 只验证了离线 URDF→几何读者这一条链；**Blender、运行时（IsaacLab 的 robot/传感器/action manager 实际名字）与报告 reader 尚未接线**，E4.4 的运行时验真与 E4.5 的旧基线记录未做，故 E 仍未达第一波出口。
- 孪生是**同几何改名**样本，不是候选几何/动力学证据，也不证明新命名已在任何真实资产上采用。
- `_verify_chain` 的天花板：中途半改名（保留旧末端词根、改中间词根）的机体不会被拦，理由与升级路径写在函数内 `ponytail:` 注释。
- `fold_reading` 的记录列名仍按旧词根取值（`{leg}_haa_joint` 等）——报告 reader 属 E3 未接线行，本次只把它的链与网格读取接入绑定，未改其列口径。

## 追加七：E 第二切片 —— 碰撞扫描接入同一绑定（2026-10-12 同日）

### 适用范围

`check_self_collision.py`（家族腿可达集的网格级自碰撞扫描）接入绑定：按命名选角色、入口声明命名、错配即拒。读数为离线真跑（凸包 + FK + 包含判定，无仿真），主体是采用机体与其**同几何改名孪生**；不是候选几何/动力学结论。

### 验收条件

同一扫描在旧名机体与其改名孪生上给出同一组数（只有词汇不同），错配命名必须拒绝而不是扫出空集。

### 结果

- **接线**：`leg_joints`/`sweep_poses` 接收绑定，角色按**位次**取（根轴 = `roots[0]`、三铰 = `roots[1:4]`、膝 = `roots[2]`），不再按 `hip`/`hfe` 等词取；`_LEG_TOKENS` 常量删除；入口加 `--naming`（`shared`/`split`）并在首行印出绑定。
- **绑定核对（新增）**：扫描前先核每条腿的命名末端关节存在，否则 `SystemExit` 并指出期望关节名——缺这一步时，错配命名找不到任何关节可扫，`leg_joints` 返回空、`sweep_poses` 出 0 个姿态，报告成"无边距/无穿透"的干净读数（实测：孪生按 `shared` 扫出 0 个姿态）。
- **真跑对照**：采用机体按 `shared`、其改名孪生按 `split`，两条扫描的 `136` 对 link、`132` 个姿态、最小余量 `-222.86 mm`、穿透判词 `40` 条完全相同；差异只在词汇（`lf_foot` → `lf_finger`、`lf_hip_joint` → `lf_shoulder_swing_joint`）。这正是"同一套读者显式服务两套名"的读数形态。
- **负例**：孪生按 `shared`、采用机体按 `split` 都在扫描前被拒，报出期望关节名（`no lf_foot_joint in the tree ...` / `no lf_finger_joint in the tree ...`）。
- 顺带就地修了同文件的角色选择：`load_case_angles` 的折叠用例原按 `HINGE_ROOTS[-2:]` 词取，改为按命名位次（`roots[-3:-1]`），自检读数不变。

**复读命令与实测**（`<PY>` = `python ablation_harness/host_paths.py --python` 给出的解释器；孪生由 `check_leg_reachability._renamed_twin(DEFAULT_URDF, naming_for('split'), <临时目录>)` 生成，与追加六同一构造）：

- `<PY> rl_exp\tools\verify\check_self_collision.py --family lizard2` → `link pairs checked: 136 | poses: 132`；`minimum margin over all poses: -222.86 mm (['chest_pitch', 'lf_foot'], combined, {...-0.6, 0.6, 1.2, 1.6})`；`penetrating judgements: 40`
- `<PY> rl_exp\tools\verify\check_self_collision.py --family lizard2 --naming split --urdf <孪生>.urdf` → 同 `136`/`132`/`-222.86 mm`/`40`，词汇为 `lf_finger`、`lf_shoulder_swing_joint`
- 两条负例 → `no lf_foot_joint in the tree -- this body does not carry the naming 'shared'`（孪生）/ `no lf_finger_joint in the tree -- this body does not carry the naming 'split'`（采用机体）
- 缺核对时的对照 → `poses the twin would sweep under the wrong naming: 0`（即"干净读数"的来源）
- `rl_exp\tools\verify\run_offline_checks.bat` → `ALL_OFFLINE_CHECKS_PASSED (37/37 in 39.6s)`；`python rl_exp/tasks/joint_names.py` 通过

### 证据引用

- `rl_exp/tools/verify/check_self_collision.py` 的 `leg_joints` / `sweep_poses` / `main`（`--naming` + 末端关节核对）。
- `rl_exp/tools/verify/check_leg_reachability.py` 的 `load_case_angles`（按命名位次选折叠对）与 `_renamed_twin`（孪生构造，追加六已记）。

### 未覆盖边界

- 该工具**不在离线清单**（采用机体当前是红的），故这一条只有人工复读，没有常驻机器入口；孪生对照是本次人工真跑。
- 仍未接线：Blender 构建入口、`check_joint_layout`、站姿/步态诊断、接触诊断与在线协议核对、报告 reader；E4.4 的运行时与报告验真未做，E 仍未达第一波出口。
- 扫描结论（-222.86 mm 与 40 条穿透）是**采用机体既存红项**的复读，不是本次改动引入或修复的问题；归 `floor-contact-attribution` 的资产前提。

## 追加八：E 第三切片 —— 运行时消费者接入同一绑定（2026-10-12 同日）

### 适用范围

运行时侧两个消费者接入绑定并真跑：`rl_exp/tools/diagnose/stance_step_probe.py`（PLAY 任务、1 env、无策略）与 `rl_exp/tools/verify/check_joint_layout.py`（布局硬闸 + 注入读数）。读数为起 IsaacLab 的实测；E4.5 的旧基线同条件复跑与 E4.4 的两套命名运行时对照均未做（原因见下）。

### 验收条件

同一绑定在运行时解析关节名 / 接触体 / 动作列；错配命名在**测量之前**被拒；两处错配（声明与所造资产、声明与标定 URDF）都要报出具体缺失名。

### 结果

- **`stance_step_probe.py`**：加 `--naming`（声明所造资产词根），绑定在入口解析后携带到底——`--joint` 缺省取该命名根轴且必须属于该 leg 的词根、`--drop-joints` 缺省取末两位词根、足底标定与网格读取、接触体模式、被扫关节名全部走绑定。新增运行时核对：每条 leg 的**命名末端关节**必须出现在所造资产的关节表里，且接触模式选出的脚必须正好是四条 leg 的命名末端 link；任一不满足即 `SystemExit`（缺这两条时，错配命名只表现为"零只脚/无边距"的干净读数）。
- **`check_joint_layout.py`**：先修掉一处**既存崩溃**——脚本用 `joint_names` 保存资产自己的关节名列表，把同名模块遮蔽掉，于是 `leg_probes()` 在 `joint_names.CHAIN_ROOTS` 上崩（复现读数见下）。模块改别名 `leg_names`；`--naming` 声明词根并在造出资产后核末端 link；`leg_probes`、排序键、解剖硬闸（原字面 `lf_haa` 等）、`--sweep-a/-b` 缺省与校验、`_FOOT_LINK` 一律按命名位次取；`leg_of`/`token_of` 取代 `rpartition('_')`（`shoulder_swing` 这类带下划线的词根不会被切半）。工具第一次跑到 `=== DONE ===`。
- **运行时错配**：孪生 URDF（`split`）配所造旧名 USD 时，在测量前被拒：`spawned asset ...\lizard2\lizard2.usda has no lf_finger_joint, so it does not carry the naming 'split' -- declare the naming of the asset it spawns`。
- **一条与 E 出口直接相关的结构发现**：运行时的**关节名来自配方**（动作项 `joint_names`、`joint_order`、默认位姿都写字面名），只有 link/体名来自 USD。因此"同一进程服务两套名"在运行时**不可能只靠工具绑定达成**——改名必须与配方/机体的采用同一次变更落地（版本 §A 的迁移条款、E3 表"正式声明归 S6"）。这条同时说明：E 的运行时双命名验证只在采用后才能做，今天只能验"绑定被核对、错配被拒"。

**复读命令与实测**（`<PY>` = `python ablation_harness/host_paths.py --python` 给出的解释器；孪生 URDF = `check_leg_reachability._renamed_twin(DEFAULT_URDF, naming_for('split'), <临时目录>)`，见追加六）：

- `<PY> rl_exp\tools\diagnose\stance_step_probe.py --headless --settle 100 --steps 40 --naming shared` → 跑完并打印 `CARRIED leg joints`（按绑定后缀）/`UNCOMMANDED ...`/`=== SETTLE ===`/`=== RAMP lf_hip_joint ... ===`/`=== VERDICT ===`（四脚受力、base 高、足底倾角、接触点速度、非足体受力、被扫关节力矩各一行）
- `<PY> rl_exp\tools\diagnose\stance_step_probe.py --headless --settle 20 --steps 10 --naming split --urdf <孪生>.urdf` → `spawned asset ... has no lf_finger_joint, so it does not carry the naming 'split' ...`（退出码 1）
- 修复前：`<PY> rl_exp\tools\verify\check_joint_layout.py --headless` → `AttributeError: 'list' object has no attribute 'CHAIN_ROOTS'`
- 修复后同命令 → `BODY lf_hip / lf_haa / lf_hfe / lf_kfe / lf_foot`（链序取自绑定）、`LAYOUT_GATES PASSED`、`=== COMPOSITE hfe x kfe ... ===`、`=== ACTUATION ... ===`、`ACTION COVERAGE 22 of 30 joints channelled`、`=== DONE ===`

### 证据引用

- `rl_exp/tools/diagnose/stance_step_probe.py`：`--naming` 解析与绑定携带、运行时末端关节/接触体核对、`--drop-joints` 缺省。
- `rl_exp/tools/verify/check_joint_layout.py`：模块别名与 `leg_names` 绑定、`leg_of`/`token_of`、`leg_probes`、解剖硬闸、sweep 缺省与校验。

### 未覆盖边界

- 未做"两套命名的运行时对照"：需要一份**prim 名字已改**的 USD 且配方关节名同变更（采用动作，归 S6）；也正因如此，E 的第一波出口在运行时侧只能到"绑定被核对、错配被拒"。
- 未做 E4.5 的旧基线同条件复跑（本轮两次运行用的步数/时长与历史记录不同），故只有"跑通且各段打印"的读数，不是与历史读数的逐项对照。
- 起仿真两次，均为 1 env、无策略；未验证策略行为、承重动力学或候选几何。
- 本轮改动**未提交**：另一会话正在把 `rl_exp/blender/*.py` 搬到 `rl_exp/blender/scripts/`，`check_work_docs` 因此报 9 条 `landing` 路径漂移（含本项两条），pre-commit 会拒；本项不代改他项路径、不跳过钩子。（同日补记：对方已把台账路径补齐，本切片随 `d5246ae` 入库。）

## 追加九：E 第四切片 —— 报告 reader 接入同一绑定（2026-10-12 同日）

### 适用范围

两个报告 reader 接入绑定并真跑：`rl_exp/tools/diagnose/plot_joints.py`（读 gait_probe 报告出图，不起仿真）与 `ablation_harness/baseline_metrics.py`（离线复判 `baseline-frames` 记录）。读数取**本机已存在的真实产物**（报告 `out/gait_probe/gait_v3.json`；记录 `results/lizard2_flat_v5/v3/.../eval.frames.pt`）与其**同数据改名样本**。未覆盖 writer 侧（见末尾）。

### 验收条件

同一份报告/记录在旧名与新名两套词根下读出**同一组数、同一组键名**；错配命名必须拒绝而不是画出空行 / 让声明项静默缺席。

### 结果

- **`plot_joints.py`**：加 `--naming`；被画的三条关节改为按**链位次**从绑定取（`REPORT_POSITIONS = (0, 2, -1)`），且**逐 leg** 取（前后肢两套词），列标题随行自己的词；画之前核对报告的脚体与键名（每条 leg 的末端 link、`{body}_{token}_actual/_target`、`{token}_limits_rad`），缺任一项即拒绝并指出缺的那个键；索引 JSON 记下 `naming`。真跑：真实报告 `shared` 出图（0.5/1.5/2.8 m/s 三档）；把同一报告改成 `split` 词（数值不动）后 `split` 出图，**逐档逐角色对齐后 36 格读数与键集合完全相同**（`unmapped []`、`value differences []`）；两处错配各被拒（报出报告里实际的脚体：`['lf_finger','rf_finger','rl_toe','rr_toe']` / `['lf_foot',...]`）。
- **`baseline_metrics.py`**：`_LEG_TOKENS = JOINT_SUFFIXES` 常量改为 `leg_suffixes(naming)` + `judge(artifact, naming=LEGACY)` / `_score` / `_gait_shape_readings` 一路带绑定，`--naming` 上 CLI；新增 `_record_naming()`：记录的关节列里**一格都不属于该命名**即拒（列名给前三条），否则空读数会被当成"这只机体没什么可报"。
- **一处真发现的耦合**：步幅归因的两条 item 名 `stride_hip_corr` / `stride_knee_corr` 原先是**按词根拼**出来的（`f"{leg}_{token}_joint"`，token 固定 `hip`/`hfe`），而这两个名字同时写在**协议**的 `report_only` 里（`protocols/lizard2_flat_v4/v5.json`）⇒ 改名后 item 名会跟着变、协议声明项静默缺席。改法：**item 名保持协议不变**，只把要找的关节改为按位次（位次 0 = 步幅根、2 = 膝）逐 leg 取。改后两套命名的 `diagnostics` **键集合与取值完全一致**（改前差两个键：`stride_hip_corr`/`stride_knee_corr` 只在 `shared` 出现）。
- 既有复判行为不变：真实 v3 记录 `shared` → `verdict: pass`；改名副本身份照旧 `pass`，`invalid_reasons: []`；负例（改名记录按 `shared`）→ `ValueError: record Lizard2-Flat-Play-v3 carries 30 joint column(s) and none is a leg joint of the naming 'shared' (... rr_hip_swing_joint)`。
- `python -m pytest rl_exp\tools\verify\test_baseline_contract.py -q` → `68 passed`（复判契约未破）。

**复读命令**（`<PY>` = `python ablation_harness/host_paths.py --python` 给出的解释器；报告/记录改名样本由 `%TEMP%` 下一次性脚本按“解析体名+词根+字段”生成，不入仓）：

- `<PY> rl_exp\tools\diagnose\plot_joints.py --report rl_exp\tools\diagnose\out\gait_probe\gait_v3.json --naming shared --out_dir <tmp>` → `JOINT_PLOT_OK (shared)`；同报告改名副本 `--naming split` → `JOINT_PLOT_OK (split)`，两份 `*_index.json` 按角色对齐后逐格相同
- `<PY> -m ablation_harness.baseline_metrics ablation_harness\results\lizard2_flat_v5\v3\Lizard2-Flat-v3_5999_deterministic_seed123\eval.frames.pt --protocol ablation_harness\protocols\lizard2_flat_v5.json` → `"verdict": "pass"`、`"naming": "shared"`
- 同一记录改名关节列后 `--naming split` → `"verdict": "pass"`、`"invalid_reasons": []`；按 `shared` 读 → 上面那条 `ValueError`

### 证据引用

- `rl_exp/tools/diagnose/plot_joints.py`：`REPORT_POSITIONS` / `report_tokens` / `draw_band` 的键核对与逐行标题 / `main` 的脚体核对与 `--naming`。
- `ablation_harness/baseline_metrics.py`：`leg_suffixes` / `_record_naming` / `_gait_shape_readings` 的位次取关节 / `judge` 与 CLI 的 `--naming`。
- `rl_exp/tasks/joint_names.py`：新增 `naming_id()`（id 反向查，`check_leg_reachability` 与 `plot_joints` 共用，避免第二份 id 表）。

### 未覆盖边界

- **writer 侧未接线**：`ablation_harness/baseline_eval.py` 的 `_gait_shape_joints`（决定**新记录带哪些关节列**）与 `gait_probe.py` 的报告写出（报告尚不携带 `naming` 字段）都没动 —— 前者改的是"记录里有什么列"，属评测协议面，须先核协议边界并交 `lizard2-contact-protocol`；后者受资产前提阻塞（`gait_probe --self-check` 现树既存红），其报告今天只能按 `shared` 读。
- 样本是"同数据改名"，不是候选机体上的新读数；`plot_joints` 的图只比了索引 JSON 的数值与键，没有逐像素比图。
- E4.5 的旧基线同条件复跑仍未做；E 的第一波出口仍未达（Blender 构建入口、`gait_probe`、接触诊断与在线协议核对未接线）。

## 追加十：E 第五切片 —— 接触面接入同一绑定（2026-10-12 同日）

### 适用范围

接触相关三处消费者接线：`diag_metrics.foot_ids`、`check_contact_ownership.py`、`obs_protocol_live.py`。读数 = 离线足端选择（两套命名 + 两处拒绝）与两次起仿真的真跑（各一次共享命名、一次错配拒绝）。`baseline_probe.py` 与 `diagnose_support.py` 的同类字面后缀未接线，见末尾。

### 验收条件

同一足端选择在旧名与新名两套词根下选中同一组 body；错配命名在**测量前**被拒；空匹配不得被当成"没有足端"的零读数。

### 结果

- **`diag_metrics.foot_ids(body_names, naming)`**：字面 `_foot` → `joint_names.is_contact_body`；**匹配不到即 `ValueError`**，报出命名与它找的模式。名表按**文件**导入（`sys.path` + `import joint_names`），因为本模块也被纯离线检查导入，不该为此付 `rl_exp.tasks` 的 gym 注册。
- **`check_contact_ownership.py`**：`--naming`；足端集合走 `is_contact_body`；新增核对：每条 leg 的命名末端 link 必须出现在所造 body 里，否则 `SystemExit`——缺它时足端集合为空，"无未受罚体"这条会因无可比对而通过。
- **`obs_protocol_live.py`**：`--naming`；`f"{foot}_foot"` → `joint_names.end_link(foot, naming)`（声明的 ring 项名是协议自己的词汇，足端 body 名才是机体的词）。导入位置提到 parser 之前（`--naming` 的 choices 要用表）。
- **一处可达性事实**：`Lizard2-Flat-v3` 的协议只声明 `policy` 组（`terms_for` 见下），`feet_for(task, "extero")` 抛 `ProtocolError` ⇒ 该文件的"声明足端必须有对应 body"那段循环**今天不执行**（`feet` 为空元组）。声明文件里确有带 `extero` 的协议（`versions/obs_protocols.json` 一份，四个 `*_foot_ring`），但本次能跑的任务里没有它 ⇒ 这次改动**按共享命名与既有行为逐字等价（无行为变化），但未取得真跑验证**，记为未验，不当作已验。

**复读命令与实测**（`<PY>` = `python ablation_harness/host_paths.py --python`；改名样本是临时目录里的一次性脚本，不入仓）：

- 离线：`foot_ids` 在 shared/split 下都返回 `[1, 2, 3, 4]`；两处错配各拒：
  `6 body name(s), none a .*_finger/.*_toe body of the naming 'split': ['base_link', 'lf_foot', 'rf_foot', 'rl_foot']` 与 `none a .*_foot body of the naming 'shared': ['base_link', 'lf_finger', 'rf_finger', 'rl_toe']`
- `<PY> rl_exp\tools\verify\check_contact_ownership.py --task Lizard2-Flat-v3 --num_envs 2 --steps 20` → 跑完并打 `CONTACT_OWNERSHIP_FAILED (1)`，唯一 FAIL 是既存的 `every penalty body carries a collider  colliders missing: ['lf_kfe','rf_kfe','rl_kfe','rr_kfe']`（膝链无 collider，与命名无关）
- 同命令 `--naming split` → `task Lizard2-Flat-v3 has no lf_finger body, so it does not carry the naming 'split' -- declare the naming of the body it spawns`
- `<PY> rl_exp\tools\verify\obs_protocol_live.py --headless --tasks Lizard2-Flat-v3` → `OBS_PROTOCOL_LIVE_OK (1 task(s), 1 warning(s))`；`--naming split` 同结果（该段今天不执行，见上）
- `<PY> -c "from rl_exp.tasks import obs_protocol as P; P.terms_for('Lizard2-Flat-v3','extero')"` → `ProtocolError: ... protocol declares no group 'extero'; has ['policy']`

### 证据引用

- `rl_exp/tools/diagnose/diag_metrics.py`：`foot_ids` 的绑定与拒绝、文件导入名表。
- `rl_exp/tools/verify/check_contact_ownership.py`：`--naming`、末端 link 核对、`feet` 集合。
- `rl_exp/tools/verify/obs_protocol_live.py`：`--naming`、`check_task(..., naming)` 与 `end_link` 解析。
- `FILEMAP.md` 的 `diag_metrics` 行（`foot_ids` 的拒绝是调用方要知道的契约）。

### 未覆盖边界

- `baseline_probe.py`（head press 用的足端集合，`:270-271`）与 `diagnose_support.py`（非足端排名与 `find_bodies/find_sensors([".*_foot"])`，`:428/447/817/822`）**未接线**：各需一次自己的仿真真跑，留下一片做；未接线前不得用它们读新名机体。
- `obs_protocol_live.py` 的那条改动**未验证**（上文的可达性事实）——只做等价对齐。
- 两次仿真各 1–2 env、20 步：只证"接通 + 拒绝"，不是承重或接触读数；`check_contact_ownership` 的既存 FAIL 归资产/collider 事项，不借 E 改资产。
- E4.5 的旧基线同条件复跑仍未做；E 的第一波出口仍未达。

## 追加十一：E 第六切片 —— `baseline_probe` 接入，`diagnose_support` 归位（2026-10-12 同日）

### 适用范围

`rl_exp/tools/verify/baseline_probe.py`（零点基线探针，含 `--head-press` 的头部压地对照）接入绑定。同行的 `rl_exp/tools/diagnose/diagnose_support.py` **不代改**：它是 `floor-contact-attribution` 的 landing，改名所需的四处字面后缀（`:427/447` 非足端过滤、`:817` `find_bodies([".*_foot"])`、`:822` `find_sensors([".*_foot"])`；后者匹配的是**配方里的传感器名**，属 S6 迁移面）由那项在自己的工作里接。

### 验收条件

探针在自己的任务上按声明命名取足端并跑通；错配命名在测量前被拒（不是"足端集合为空、承重读数照样打印"）。

### 结果

- `run_head_press` 增加 `naming` 参数（缺省 `None` → 旧命名），足端由 `is_contact_body` 取，并在用之前核对**每条 leg 的命名末端 link 在所造 body 里**，缺则 `SystemExit`；`main` 的站立承重段把 `foot_ids(body_names, naming)` 传下去（该调用点原来会用空足端集合打印 `feet only 0.0000`）。CLI 加 `--naming`；名表以 `leg_names` 别名在 parser **之前**导入（`--naming` 的 choices 要用它，而本文件多个函数参数已叫 `joint_names`）。
- 真跑（共享命名，全部跑完）：承重行列出四只脚（`load per body [N] (>1 N): lf_foot 197.0, rf_foot 193.4, rl_foot 146.4, rr_foot 143.6`）、`ok load/no-non-foot-carrier`、`ok head/press-bodies-resolved`、末行 `BASELINE_PROBE_OK` —— 足端集合非空即绑定生效。
- 错配负例（`--naming split`）**本次未取得读数**：该次运行到提交时仍在跑，未观察到就不写结论；返回后补记（同一条拒绝在 `check_contact_ownership`/`foot_ids` 上已实测，但那是别的消费者，不替代本工具的读数）。

**复读命令与实测**（`<PY>` = `python ablation_harness/host_paths.py --python`）：

- `<PY> rl_exp\tools\verify\baseline_probe.py --headless --task Lizard2-Flat-v3 --num_envs 4 --steps 20 --head-press` → 上述四行读数，末行 `BASELINE_PROBE_OK`
- `<PY> rl_exp\tools\verify\baseline_probe.py --headless --task Lizard2-Flat-v3 --num_envs 2 --steps 5 --head-press --naming split` → 提交时仍在跑，读数待补（预期拒绝：末端 link 不存在）

### 证据引用

- `rl_exp/tools/verify/baseline_probe.py`：`--naming` 与 `leg_names` 别名、`run_head_press` 的 naming/末端核对、`main` 的 `foot_ids(..., naming)`。
- 归位依据：`work/active/floor-contact-attribution.md` 的 `landing:` 含 `rl_exp/tools/diagnose/diagnose_support.py`。

### 未覆盖边界

- `diagnose_support.py` 四处未接线（归 `floor-contact-attribution`，见上）；未接线前不得用该诊断器读新名机体。
- 一次真跑用 4 env / 20 步（head-press 含两个对照段），只证"接通 + 足端非空"，不是承重结论；读数里的 `lf_foot 197.0` 等属该次运行的即时值，不作阈值。
- `obs_protocol_live.py` 那条仍为**未验**（追加十），E4.5 旧基线同条件复跑仍未做；E 的第一波出口仍未达（Blender 构建入口、`gait_probe`、报告 writer 侧未做）。
