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
