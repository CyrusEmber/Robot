# lizard2 main/v4 正式训练配置

## 适用范围

用户要求“落实正式训练配置”，本轮将已审 palm 草案采用为正式 main/v4，冻结新身份、稳定资产和实际接口，不启动训练。此前已授权提交推送 `CyrusEmber/Robot` 的 main。此要求按采用已审草案执行；没有额外改动身体、增益、奖励或学习目标。

实施入口为 `rl_exp/tasks/lizard2_recipe.py:lizard2_palm_interface`、`versions/lizard2/main/v4/main_params.yaml` 和正式任务 `Lizard2-Flat-v4` / `Lizard2-Flat-Play-v4`。母本 main/v3 随机体换代退休，仅删除旧资产锁，原 YAML/PLAN/NOTES、已发布元素、任务及 tag 保留。生命周期拒绝旧机体新训/续训；这是正式资产采用的版本规则，不抹去历史结果。

## 验收条件

- 正式资产与已审来源逐字节相同，全部 URDF 网格引用落入新稳定树；正式构造器落实同一物理、动作、驱动与采样/reset。
- 新任务无诊断 override 即能建场、reset，具有实际动作/观测宽度、运行顺序及正确掌部命名；旧配方快照不变。
- 动作逐名覆盖实际关节且顺序明确；不把 runtime 关节顺序和动作顺序误称同序。命名与差异归属的真实缺陷有修前失败/修后通过。
- 新资产锁、golden、注册/观测登记和版本文档一致，经不带当前执笔历史的上下文审核；配置通过不等于已训或策略性能通过。

## 结果

### 配置采用与证据复用

源为 `rl_exp/out/lizard2_b_standing_force_20261022_run02/` 的 `palm_spatial.usda`、同目录 URDF 和全部引用 OBJ。目标 `rl_exp/lizard2_palm_spatial/` 共 38 文件（USD、URDF、36 OBJ），没有重新生成 USD。`.gitattributes` 对该子树设 `-text` 保留绑定的原始换行字节。USD SHA256 `721e8a4053c2a6114b5c4607e57ed34f287fe317f8f9abb47a5e857b845e9c0e`，URDF `e8896feb8b0dbdbeaa35e74a01c2ffcb4ab38d89b52f221831b3f287943edd00`。

已审草案 `rl_exp/out/lizard2_bc_handoff_20261023/training_interface_draft.json` SHA256 `a120b8907601852e5ca7bf1190f675d75ea7a8ae0fa79e970d887628ed7e8b19`，驱动承地输入 `report.json` SHA256 `5a4c6a3f4572ab8db566637c64c67933ee5aa3857092b1fe7ed1b102724453c6`。正式配置采用其全部逐轴 Kp/Kd、effort/speed、默认姿态、出生姿态、自由根/重力/自碰撞及过滤和惯量产物。四肘膝 Kp=220、Kd 继承已审值；胸 pitch effort=280 N·m 显式覆盖 URDF 80 N·m，保留既有审查边界，不伪称与 URDF 相同。

动作 20 腿 +10 胸颈尾，全部位置参考，offset=0、默认 q=0、明确 preserve_order、逐轴 scale/硬限位 clip；速度参考恒零，不增加 RL 速度输出、差分前馈或滤波。policy 七项共 102 维，其中 joint_pos/joint_vel 取 runtime 顺序，last_action 取动作顺序，各自按消费者解释。接触 dt=0.005 s 每子步更新，history=4、lazy=false；TGS=1 / external-forces-every-iteration=false。七项奖励、终止、命令范围、PPO、无 DR/课程继承母本；未引入新滑移或滚动判分。

独立初审直接按固定草案的 71 个配置字段归一化 list/tuple 对照正式 Play 构造器，唯一值差为环境数 1→50（正式 Play 默认）；资产内容另按逐字节比较。传感器选择由草案显式全部 body union 表达为正式 `Robot/.*`，实际均覆盖 31 bodies；不减少接触覆盖。已有[真实接口运行](2026-10-23-lizard2-interface-runtime.md)及其[独立审核](2026-10-23-lizard2-interface-runtime-review.md)在上述相同输入/物理设置范围复用；真实动作处理/后端零速度、非零观测、首子步接触历史、完整/子集/接触自动 reset 的有限证据不改判。尤其 reset 即时 processed/backend 目标可能残留，下一 env.step 先写新动作才推进物理，原语义保留，不写作所有缓存即时清零。

### 正式运行与缺陷回归

正式 `obs_protocol_live.py --tasks Lizard2-Flat-Play-v4 --envs 1 --pin` 无 target_config，实际建场/reset，读到 30 joints、31 bodies、102 policy；新稳定资产的运行顺序已登记。日志 `rl_exp/out/lizard2_v4_obs_live.log`，`OBS_PROTOCOL_LIVE_OK`。此次没有 commanded rollout 或训练，不将初始化内部步当作策略运行。日志保留已知 TGS/false startup 警告和 disabled world-fixed-joint 提示；不消除已知速度观测偏差。

正式 target reader 原硬编码 shared，拒绝正确掌部关节；现从新 YAML 的 `robot.naming` 读取，旧配置默认 shared 不变。差异覆盖 helper 原只认点后代，遗漏列表 `[]`/`[0]`；现补数组边界，不匹配兄弟键或反向路径。两条修前失败日志分别为 `lizard2_v4_regression_before.log`、`lizard2_v4_list_coverage_before.log`，均由独立审核在 HEAD 旧函数上重新复现。

完整检查又暴露差异生成器的父块归属缺陷：它选择最终写入者后，未标注同一父块下其它实际写入者，与既有 hard B 的全作者集要求冲突。新增持续回归先报五条归属失败（`lizard2_v4_emitter_before.log`），随后只修生成器按实际 replay 集合命名，保留闸门规则。v4 差异重新生成，路径数不变，两个组成为组合作者；未重新生成任何旧版声明。最终配置回归共 8 项通过（`lizard2_v4_config_tests_final.log`）。

旧检查绑定一并按实际身份修正：速度字段闸门仍检查旧版 inert scalar，v4 则检查已审逐关节显式 caps，并用丢失/改值/外来键三类破坏必拒；manifest fixture 改绑有资产锁的 v4，原记录/漂移/dirty/resume 负例保留。旧 sole 数值标定和 FK/反曲算术控制明确绑定 v3 网格、URDF 和冻结参数，保留原阈值与负例，不把旧数字改成新机体判据；正常几何诊断仍按当前资产/命名，增益 reader 可读逐关节字典，新增回归核当前掌部输入。dev 接触检查从真实 URDF 的近端碰撞链 owner 核选择，而非硬编码旧 hfe 名；保留空选、错名、全选负例。首次套件因 review 文件尚未落盘停止，第二次记录上述旧夹具失败，第三次继续发现 dev 负例错名抛异常和生成器归属失败；全部日志保留，不作为通过。

golden 原工具更新仅新增两个 v4 task，旧任务快照零变化；差异声明为 65 env paths +1 agent leaf，由四个 owner 归属。首次资产锁通过原工具限定 v4 写入，未刷新任何旧锁。line golden 摘要由 `8b7e7a139500407b866945446e4feeea787d51904a1c96ce53705d030af47cf7` 变为 `ea7bf0f4b45c23d99217c310ae84171f2ad0511f0ff90a3081b13ce6d650eba4`，既有摘要闸门先报 `GOLDEN_FROZEN_DRIFT`（`golden_pin_before.log`），随后同次更新 digest 看守与 B0 记录指针；配置锁正文只由原工具写。完整离线套件 `37/37`、63.2 s 通过（`lizard2_v4_offline_suite_release.log`），独立审核另记[审核记录](2026-10-23-lizard2-v4-configuration-review.md)。

发布前发现新 YAML 的工作副本是 CRLF，而仓库规定普通文本检出为 LF；若直接冻结，参数摘要会在新检出失配。仅本轮文本规范 LF，38 个资产仍保留原字节；未发布 v4 的早期资产锁留在本地 `lizard2_v4_asset_lock_before_lf.json`，由原工具对不存在的 v4 锁重新生成（`asset_lock_lf.log`）。参数值、序列化配置和 golden 不变，不刷新任何已发布锁。最终 LF 参数 SHA256 `db3291e93688426d3251db837f352982c5764865486112d279b52a1475036abc`，v4 资产锁 `274bbc2268dad07b39692a836837f8830ae4708035b3d34ed22590dabff79b6b`。`check_dr_parity --strict --self-test`（按套件 UTF-8 输出环境，`lf_parity_utf8.log`）、8 项配置回归（`lf_config_tests.log`）、提交前静态钩子（`precommit.log`）和实际暂存 diff 空白检查通过。单独 parity 早期调用未设套件的 UTF-8 输出环境，子夹具输出中断，失败日志 `lf_parity.log` 保留，不作通过。源 URDF 原有空白行和 USD 末尾空行属于已审字节，`.gitattributes` 仅对这两个资产限定原格式空白规则，其余文本/检查保持。正式冻结提交 `9465f9f60dee2eed9b0ab310e40d0ba853fedb09`，tag `lizard2-main-v4` 指向该提交；正常 commit 的静态钩子通过（`commit_freeze.log`）。配置 tag 与训练启动是独立状态，本轮没有启动训练。审核、事项指针、路线与 README 同组单独文档提交；远端身份以实际 refs 核验为准，不改写旧 tag。

## 证据引用

- 正式版本 [PLAN](../../rl_exp/versions/lizard2/main/v4/PLAN.md)、[参数](../../rl_exp/versions/lizard2/main/v4/main_params.yaml)、[差异](../../rl_exp/versions/lizard2/main/v4/diff.json)、[NOTES](../../rl_exp/versions/lizard2/main/v4/NOTES.md)。
- 原生接触样本与其边界见[记录](2026-10-23-lizard2-contact-native.md)；训练优先、取消独立阶段见[计划修订](2026-10-23-lizard2-training-priority-plan.md)。
- 本地过程日志前缀 `rl_exp/out/lizard2_v4_`；`golden.log`、`asset_lock.log`、`emit_diff_verified.log`、`tests_verified.log`、`obs_live.log` 保留。失败/中间日志未覆盖，不作通过证据。原始运行制品在本机，未承诺全部入仓。

从仓根使用项目 Python，以下不启动训练：

```powershell
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/verify/test_lizard2_v4.py
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/verify/check_recipe_build.py
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/verify/check_dr_parity.py --strict --self-test
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/launch_recipe.py --task Lizard2-Flat-v4 --max_iterations 6000 --seed 42 --record rl_exp/out/lizard2_v4_launch_plan.json
```

需要重建实际场景时，单独运行 `obs_protocol_live.py --headless --tasks Lizard2-Flat-Play-v4 --envs 1`，不加 `--pin`，不训练。旧接口运行的复读入口留在对应记录；宽度/声明检查不能替代其真实数组。

## 未覆盖边界

本轮不启动 6000 迭代训练，无新 run/checkpoint 或策略表现。正式启动前的必要地形预检和 GUI 目视继续归原训练事项；没有恢复独立 S5/S6、完整新接触协议、限速/限矩、对称复测、手工抬腿或行走前置。已审有限 reset 证据不外推所有地形/状态/终止组合；原 timeout 到期、普通自然终止、全域精度、硬件力矩包线、动态滑移/滚动分类及新策略性能仍未证明。整体事项继续 in_progress，不因配置交付关闭。
