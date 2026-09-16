# FILEMAP —— 全仓文件地图（给下一个 AI / 新协作者）

> 读图顺序：`README.md`（仓定位 + 新机器摆位）→ 本文件（每个文件干啥）→
> `rl_exp\versions\lizard\PLAN.md`（训练计划与挂账，当前进度）→
> `rl_exp\versions\lizard\FAMILY.md`（任务注册表/版本历史/obs 布局/记录体系）。
> AI 开发守则见 `AGENTS.md`（IsaacLab 上游）+ `.codemaker\skills\tool\`（本项目 5 份 skill）。

## 仓根

| 文件 | 作用 |
|---|---|
| `README.md` | 仓说明：内容物 + 自装 Isaac Lab 要求 + 新机器摆位（`setup.bat` 一键版 + 手工五步；含 `paths.yaml` 主机路径登记） |
| `setup.bat` | **新机器摆位一键脚本**（README 五步的自动化 + 幂等版）：写 venv `.pth`、建 `config\lizard\` 并拷入 fork shim、逐个应用 `fork_patches\*.patch`（`git apply --check --reverse` 判已打则跳过，否则打；打不上 `[FAIL]` 非零退出——补丁漏打/坏掉不再静默）、按本机生成 `paths.yaml`、设 `core.hooksPath`。成功判定看**结果**（文件在不在 / git 退出码）不看残留 ERRORLEVEL；纯 ASCII（`.bat` 按控制台代码页读，非 ASCII 会带崩解析） |
| `AGENTS.md` | agent 工作守则（对抗性审查四问 / 先计划后动手 / 沟通语气）+ IsaacLab 官方守则（API 命名/工具链/commit 规范）；与 `ponytail.mdc` 重复的条目刻意不写 |
| `FILEMAP.md` | 本文件 |
| `paths.example.yaml` | **主机路径模板**：`isaac_root`（IsaacLab 源码树，持 `scripts/` 与 `logs/`）+ `python`（装了 isaaclab/rsl_rl 的 venv 解释器）。每台机器 copy 成 `paths.yaml`（已进 `.gitignore`，机器本地事实不入库），由 `ablation_harness\host_paths.py` 单点读取。优先级：命令行 > `RL_ISAAC_ROOT`/`RL_PYTHON` > `paths.yaml` > 向上探测 |

## rl_exp\ —— 任务包（自包含核心）

### 文档与参数 SSOT（2026-09-01 迁移：家族级文件入 `versions\lizard\`）

| 文件 | 作用 |
|---|---|
| `versions\lizard\lizard_params.yaml` | **参数 SSOT（开发态）**：执行器 PD/动作缩放/命令范围/DR 范围。冻结版在 `versions\lizard\vN\`，跑冻结版永远不读这份 |
| `versions\lizard\lizard.urdf` | 机器人几何 SSOT（Blender 生成）：26 关节、质量、限位 |
| `versions\lizard\PLAN.md` | **纯意图文档（路线/备选路径/挂账清单）**：跨版本路线 + 决策记录 + 反趴窝备选升级表；时态纪律见 versioning.mdc（已成立事实归 FAMILY，方案细节归各 vN\PLAN.md） |
| `versions\lizard\FAMILY.md` | 家族事实总文档（现在时）：任务注册表 / 版本历史（含教训列）/ 当前状态 / 机体几何 / 四层记录体系（代码地图归本文件，开新版本流程归 `.codemaker/rules/versioning.mdc` §A） |
| `versions\lizard\OBS.md` | **obs 契约 SSOT（家族级）**：v1–v5 布局演进、论文对应、偏差声明（决策 B/v3 有意偏差）、`TEACHER_PRIVILEGED_SPEC` 版本差异机制（数值真源仍是代码 + check_obs_layout.py） |
| `versions\lizard\REWARDS.md` | **奖励用途总表（家族级）**：每 term 买什么行为/收什么税、公式+权重镜像、c_k 课程归属、v3 划脚事故的奖励经济学读法、版本差异摘要（数值真源仍是代码+各 vN yaml） |

### tasks\ —— gym 任务包（训练代码本体）

| 文件 | 作用 |
|---|---|
| `__init__.py` | 全部 gym 注册（家族 8 + teacher v1–v12 各 train/play，空号版本不注册） |
| `lizard_env_cfg.py` | 家族平地基座：机器人装配 + DR 接线 + `_load_params`（版本参数机制） |
| `rough_env_cfg.py` | 家族粗糙地形（蜥蜴尺度化地形 + 高度扫描 obs） |
| `curriculum_env_cfg.py` | 三课程平地变体（骨骼/速度/转向，spine 可被课程锁放） |
| `curriculum_rough_env_cfg.py` | 三课程粗糙变体 |
| `teacher_env_cfg.py` | **teacher 独立快照**（只继承框架基类，零家族 import；`params_version` 类属性 + `TEACHER_PRIVILEGED_SPEC` 版本差异表，v1–v13 子类常驻可复现；v3 = 三组 obs + 4×脚环 RayCaster + D 包接线，`RingPatternCfg` 环形 pattern 在此；spine scale 由 yaml `spine_scale` 控制——v6.1 起解锁 0.25；v11 = param-grid 地形 + `JointSIRTerrainCurriculum` 接线，term 名走 `teacher_mdp.JOINT_SIR_TERM` 常量；v12 = Miki S8 鲁棒性包——关节 offset 型复位三件 + 基座范围 yaml 化 + 摩擦 dip + 4 个环 term 换 `NoisyFootRing` func；v13 = Miki 对称跟踪核接线——EP 线性核置 None，挂 `track_lin_vel_xy_miki`（yaml v13 段驱动）） |
| `teacher_networks.py` | **v3 teacher 网络**：`SplitEncoderModel`（MLPModel 子类：g_e 每脚共享 {80,60}→24 / g_p {64,32}→24 / f_π {256,160,128}，三流各自 EmpiricalNormalization，f_π 段序冻结 [proprio\|l_e\|l_priv]）+ `DecayingLrPPO`（lr 0.9999/iter）；经 `class_name` 点路径注册，零 rsl_rl 改动 |
| `student_networks.py` | **Phase 2 接口锁**：`BeliefEncoder` GRU 2×50（b'=100）、`AttentionGate`/`BeliefMapper` {64,64}、`StudentPolicy`（f_π 输入 210 与 teacher 恒等）、`BeliefDecoder`（208+24）、`load_from_teacher`（g_e/f_π 权重 + o_p 归一化统计迁移 + 段序恒等断言） |
| `teacher_mdp.py` | 特权 obs term：真值速度/接触布尔/**力矢量/接触法线（warp 射线）/每脚摩擦/大小腿接触/持续外力**/air time/逐 body 质量（只增不改纪律）；v3 段 = D 包（c_k 纯函数课程 + tilt 终止 + `FootClearanceReward` 防拖脚 + reset 化 c_k 锚点缩放 DR 包装）；v5 段 = `SpawnWeightSIRTerrainCurriculum` 行 SIR（v5–v10 冻结）+ EP 线性跟踪核 `track_lin_vel_xy_lin`（v5–v12 冻结）；v11 段 = `ParticleVelocityCommand`（Eq.2 标签 + 桶命令）+ `JointSIRTerrainCurriculum`（联合粒子 SIR，逐步 Tr，跨块累积结算），模块常量 `JOINT_SIR_TERM`；v12 段 = `sample_ring_noise`（工况 60/30/10 抽样）+ `NoisyFootRing`（w/ε_f/ε_p 三层 + outlier + 中途重抽 + c_k 缩放）+ `FootFrictionDipTerm`（p_dip 摩擦重抽 + 特权 obs 缓存直写）；v13 段 = `track_lin_vel_xy_miki`（Miki 2022 对称核，全 2D 误差 + yaw 帧 + 无 min_speed，闭合超速/横向/停车三账本盲区） |
| `curriculum_state.py` | **真续训状态层**（2026-09-11 起，2026-09-15 按 `ARCH_PLAN.md` 1.3a 改为注册表 + v2 载荷；挂账 `versions/lizard/PLAN.md` #11）：**载荷 v2** = 公共 header（`version`/`task`/`num_envs`/`written_at_iter`）+ `clock`（`common_step_counter` + `ck` 指纹 `{version, static:{c0, decay, steps_per_iteration}}`，无 c_k 时显式 `None`）+ `terms` **按实际 term 实例名索引**，每 slot 带 `adapter`/`adapter_version`/`term_type` 与自己的 `static`/`runtime`。**注册表两个 adapter**：`joint_sir`（v11/v12，粒子/权重/episodes/in_band/tr_sum/回放池/env_pair/desired_vel/env_type）与 `row_sir`（v5–v10、v13/v14 行 SIR，particles/weights/episodes/successes/history/env_type/next_eval_step；**不虚构** joint 专有字段）；**c_k 与 term 解耦**——只要任务跑了 `init_ck` 就回填 counter（v3/v4 线），空 `terms` 合法。恢复流程：识别版本（v1 显式迁移为唯一 joint slot，缺证据列 `missing_evidence`、**不以当前值补造**）→ 核验 task/env 数 → 逐 slot 核验 adapter/类型/`adapter_version`/静态指纹/张量（有限性、非负、索引 dtype、范围、计数关系、评估时点）→ **全部通过才原子回填**（半恢复禁止）；未知版本、缺/多 slot、名字变更（改名必须显式迁移，不猜对应）一律报错。**静态指纹**：joint = types/n_levels/n_pairs/n_v/velocity/combo_cols/cfg(10 项)；row = 有序类型名/num_rows/num_types/type_cols/`terrain_config_sha256`（列分配不变但等占比类型换序或改地形参数也抓得住）/cfg(**9 项**)；yaml 改网格会让索引重编号而计数可能不变，只比计数抓不住。**硬失败边界**：任务声明 `REQUIRES_CURRICULUM_STATE`（`ClassVar[bool]`；V5 声明、v6–v14 继承、每个 `*_PLAY` 显式 False；快照格式 2 排除 ClassVar，故改声明不动配方 golden 与 run manifest 的 cfg 摘要）时，缺载荷/缺 slot/未覆盖 stateful term/调用侧导入失败/保存 hook 未装均**训练前终止**，其它任务只透传并报告。**开关**：`--drop_curriculum_state`（旧 `--weights_only` = 别名 + 弃用提示，Python 入口同；显式 drop 之外的两参数冲突报错）。**多 GPU 不在保证范围**：状态只从 rank 0 写，非 0 rank 拒绝恢复且不装 hook，manifest 记真实 rank 与 `multi_gpu_resume_verified: false`。**时序契约**：apply 必须在 `RslRlVecEnvWrapper` 首次 reset **之前**（fork `train.py` 接入；**补丁存档 `fork_patches\train_curriculum_resume.patch`**，`setup.bat` 幂等重打）。不存 per-episode 瞬态与地形 spawn 状态；不存 RNG（统计连续，刻意非逐位复现）。离线门 `[15]` 27/27（S01–S10 + B 层分支级与 c_k 迭代边界；A 层证载荷无损，"状态→更新映射"由 B 层证，**接线时序由 C 层真跑证**，见 `tools\verify\cstate_observer.py` + `tools\verify\check_c_layer.py` 与 `ACCEPTANCE.md` §1.4b）。**2026-09-15 C 层执行时修复一处闸门缺陷**：`_check_eval_clock` 旧规则要求 `next_eval_step > counter` 严格成立，把"已过块沿、term 尚未被调用"的**挂起**调度（真跑实测：块沿 240 的更新落在带 reset 的 247 步）判为不一致 ⇒ v12 源 ckpt（counter=960、`next_eval_step=960`）被硬拒恢复，而 v14 同迭代数侥幸通过；新规则 `next_eval_step % block == 0 and next_eval_step > counter − block`（接受挂起/已到期，拒绝落后整块及以上），用例 `test_eval_clock_accepts_a_pending_edge_and_rejects_a_stale_one` + 反证 |
| `param_grid_terrain.py` | v11 参数组合地形网格构建器：yaml 难度等级表 → 每 combo 一个 sub-terrain（单值 range，插值 no-op），名称编码 `<type>\|<lvl>_<lvl>...`；列饥饿守卫 |
| `play_utils.py` | **PLAY 共享工具**：`DR_EVENT_NAMES` + `disable_dr_events()`——全部 PLAY 变体的 DR 置空单一真源（与 harness 的 dr_controller 同步清单互指）；corruption 关闭遍历全部现存 obs 组（v3 无 policy 组） |
| `staged_curriculum.py` | 通用阶段课程组件（度量阈值+持续时长+依赖门控） |
| `agents\rsl_rl_ppo_cfg.py` | PPO runner 配置（experiment_name 按任务族隔离；`LizardTeacherV3PPORunnerCfg` = S1 超参 + obs_groups 三组 + SplitEncoderModel + DecayingLrPPO） |

### versions\ —— 参数版本冻结（**家族分层：`versions\<family>\vN\`，当前家族 = `lizard`**）

| 目录 | 作用 |
|---|---|
| `lizard\v0\` | 全量 DR 原始配方。**未训练即被 v1 取代**，存档作对照基准（复现走 git 历史） |
| `lizard\v1\` | v0 仅 DR 段收窄。**已训练 14000 iters 并出评测分**（2026-09-01，NOTES 回填）；任务 id `Lizard-Rough-v1` 常驻注册可复现（obs 266） |
| `lizard\v2\` | v1 参数 + 特权 obs 论文对齐补全（266→308）。NOTES.md 含验收线与判死刑信号 |
| `lizard\v3\` | **首跑完成，结果待回填**（2026-09-01 启动，2048 env × 4999 iter）：三编码器 + 脚环 extero 208 + tilt/r_fc/c_k/DR-reset 趴窝修复包 + **Miki 地形 v3.4**（`TEACHER_TERRAINS_CFG_V3`：台阶顶 0.55m + stepping stones，仅 v3 换用）+ v3.6 回放诊断三修。`PLAN.md` v3.6.2 + `NOTES.md`（含训练命令与装配验证记录）+ yaml（v2 全量 + `v3:` 段）+ asset_lock 齐备 |
| `lizard\v4\` | **已批准开工，未训练**（2026-09-02）：碎石地重定标——实测脚掌 0.46×0.51 m（v3.6 误用 kfe→foot 骨长 0.131），`TEACHER_TERRAINS_CFG_V4` random_rough 间距 0.3→0.5 m + 噪声 (0.10,0.35)/step 0.02；v3.6.1 collision stack 补丁回 stock。**启动前警示（先看地形）见 v4\NOTES.md**。yaml 与 v3 逐字相同 |
| `lizard\v5\` | **已训首跑判废**（2026-09-07 横行——资产长轴 Y vs 任务 +X 前向错配；奖励包本身有效，证据与判废归因见 `v6\NOTES.md`）：反划脚奖励包——r_fc 符号修正（+0.003→-0.003，v3 首跑收敛到"只有脚动身不动"划脚最优的根因之一）、r_slip（`feet_slide_ck` 接触脚滑速 ×c_k）、肚皮受力罚（防御项，`belly_contact_force` 连续 ‖F‖/706 恒权）、EP 线性跟踪（`track_lin_vel_xy_lin` 站立 0 分/倒退负分）替换 exp 核、命令 (0,3) 纯前进无速度课程。地形/obs/网络与 v4 相同。PLAN.md 含根因证据链与 F3 偏差声明 |
| `lizard\v6\` | **已训判废**（2026-09-08 停训 8950/15000：**倒走**——rig 骨命名与解剖学 180° 装反，"+Y→+X"转的是命名头=解剖学尾；探针/归因见 `v6\NOTES.md`）：资产前向轴转正（blend R_z(-90°)、AXIS_MAP 轴同步、锁全版本刷新）+ v6.1 脊柱/尾动作解锁（`joint_pos_spine` 0.0→0.25）；yaml/reward/obs 逐字同 v5，动作 26 维布局不变——关节专项（`check_joints_v6.py`/`check_skeleton_equivalence.py`）与装配验证记录见 `v6\NOTES.md` |
| `lizard\v8\` | **提案待训**（2026-09-08，v6 判废根因根治）：资产**解剖学**转正（blend 再转 R_z(+180°)，对 pre-v6 净 +90°，**球头**→+X、天线尾→−X）+ 全关节重命名（rear→chest、tail→neck（球头颈）、neck1-3→tail1-3（天线尾）、腿 rl↔rf/lf↔rr 换正）+ 全版本 yaml 机械迁移；reward/obs/动作布局逐字同 v6.2。布局硬闸（球头必 +X）入 `check_joints_v8.py`。SSOT = `v8\NOTES.md` |
| `lizard\v7\` | **提案（代码未实施，2026-09-08）**：ghost 断腿鲁棒性——截肢近似 DR（p=0.3，整腿 stiffness→0 + link 质量 ×0.001，拓扑/obs-joint/action 26 维契约不变）+ `damage_flags` 4 维 one-hot 进 actor obs（90→94，UE 游戏逻辑断腿事件直填）+ 断腿 hfe/kfe 接触罚豁免 + **v8** ckpt 微调（前提已随 v6 判废修正，PITW"加地形→继续微调"配方）；limp 档/损伤分级/多腿同断/mid-episode 拍板不做。方案 SSOT = `v7\PLAN.md` |
| `lizard\v9\` | **提案（代码未实施）**：ghost 断腿鲁棒性（自 v7 迁入重基 v8，用户拍板按顺序开 v9）——同 v7 方案，前置 = v8 已训。方案 SSOT = `v9\PLAN.md` |
| `lizard\v10\` | **已训完 15000 iter，判决半通过**（2026-09-11，`v10\NOTES.md` 验收 1–5 对账 + `DIAGNOSE.md` 支撑/移动诊断）；PLAN/NOTES/yaml/asset_lock 齐 |
| `lizard\v11\` | **实施完成待开训**（开训门 = v10 判决）：联合粒子地形课程——`param_grid_terrain.py` 参数组合网格 + `JointSIRTerrainCurriculum`（Lee 2020 逐步 Tr，挂账 #15 候选 a）+ `ParticleVelocityCommand` 桶命令 + PLAY 变体 + `test_joint_sir.py`；v11.1 审查四修（stairs 顶档 0.45 / SIR 结算式清零 / joint_sir 常量化 / PLAN 勘误）见 `v11\PLAN.md` 修订记录 |
| `lizard\v12\` | **提案**（2026-09-10 代码实施同日，未冻结）：Miki S8 鲁棒性包——关节 offset 复位随机 + 基座范围 yaml 化 + 摩擦偶发调低 + teacher 侧高度环噪声（`test_v12_noise.py`）+ r_slip 回 −0.003；方案见 `v12\PLAN.md` |
| `lizard\v13\` | **实施完成待训**（2026-09-14，单变量，base = v10）：换回 Miki 对称跟踪核 `track_lin_vel_xy_miki` = `exp(−‖v_cmd−v_yaw‖²/0.25)`（全 2D 误差，闭超速/横向/停车三账本盲区；weight 保 1.5）；静态闸 `check_reward_v13.py`；**v13.1 验收三修**（abs 双向 + 逐时刻 MAE、固定场景对比弃 `terrain_levels`、`feet_slide` 降观察项）；风险预注册（v3/v4 趴窝病历）见 `v13\NOTES.md` |
| `lizard\v14\` | **实施完成待训**（base = v13；2026-09-15 两次判据改形 → v14.3/v14.4）：终止项只剩**翻覆**——`teacher_mdp.roll_over_trigger`（基座四元数 ZYX roll，`\|roll\| > 70°`，单调覆盖整圈含肚朝上；`\|pitch\| > 80°` 护栏）+ `RollOverTerm`（per-env dwell 0.5 s + reset 钩子），yaml `v14.roll_over`；**头承重 = 惩罚** `head_load_penalty`（头链 contact_forces 竖向力 relu 求和 / 706 N，权重 -1.0，无阈值/无姿态门控/无足部卸载条件），yaml `v14.head_load`。前栽不收局（代价走惩罚）、趴地/base 接触不管（v3.6 起是惩罚）；闸 `check_terminations_v14.py`（姿态用例 + 护栏窗 + `闸⇒tilt≥70°` 网格扫描 + 惩罚算术 + 接线 + v13 冻结），预注册闸见 `v14\NOTES.md`；评测用 Locomotion-Eval-v2 |
| `lizard\v15\` | **起草（提案态，未冻结未实施）**（2026-09-16，base = v14）：地形课程换 **joint SIR**（v5 行 SIR → v11 机制的联合粒子 SIR，参数格 combo × 速度桶）——`build_param_grid_terrain_cfg`（58 combos / 4×120）+ `ParticleVelocityCommand`（buckets 0.5…3.0 + jitter 0.1）+ `Curriculum/joint_sir/{tr_mean, frontier_max_v, particle_entropy}`；obs/动作/奖励/终止/DR/资产逐字段同 v14（含 roll_over 闸 + head_load 惩罚）。方案 SSOT = `v15\PLAN.md`；预注册闸与首跑声明见 `v15\NOTES.md`。**并行迁移前置门**：开训前打 tag、进程不得重启、训练结束前不得 `cfg_lock --update` |
| `lizard\parkour\` | **支线 route 层**（2026-09-04，分支 `paper/parkour-in-the-wild`，训练未启动）：Parkour in the Wild（跑/爬/跳多专家蒸馏+RL 微调）。`PLAN.md` = 路线层（组件映射/偏差声明/决策记录）；`parkour_params.yaml` = 支线开发态参数 |
| `lizard\parkour\v1\` | 支线版本包：`v1\PLAN.md` = 版本方案 SSOT（位置任务/probe gate/专家表/蒸馏微调方案），`v1\NOTES.md` = 结果回填，`v1\base.json` = 支线血统根（null），`v1\parkour_params.yaml` = 冻结副本（未冻结，训练启动时定稿），`v1\asset_lock.json` = 资产锁 |
| `vN\PLAN.md` | 版本级计划存档（目的/假设/决策点/验收线/结论一句话；v3 原生，v0–v2 为 2026-09-01 追溯补录；结果回填仍走 NOTES） |
| `vN\NOTES.md` | 版本文档：目的/参数 diff/训练命令/结果回填 |
| `vN\tb_scalars.csv` | 训练后经 dump_tb.py 导出的逐迭代曲线，**抽样入库**（`--max_points 150`，150 点/tag ≈ 210 KB：全量 15k 点/tag ≈ 20 MB/版本，60 MB 三份，不值当）；全量留机器本地 `vN\tb_scalars.full.csv`（`.gitignore`），入库记录由它抽样得到（不需 tensorboard、不需 tfevents） |
| `vN\asset_lock.json` | 冻结时资产 sha256（`lizard.urdf` + `lizard.usda`）。冻结 yaml 只钉路径不钉内容，此锁补这个洞：资产原地换代 → 常驻任务 id 复现被破坏 → 闸门⑥报警。有意换代在同一 commit 里 `--update-locks` |
| `versions\cfg_baselines.json` | **框架组合基线（全仓唯一一份，闸门产物）**：`baselines[框架组合]`（isaaclab/rsl_rl/python + `reason`/`created_rev`/`created_dirty`）。组合是框架事实、不属于任何一条线，所以只存一份；各线锁文件都指向它（`check_cfg_lock.py:BASELINES_PATH`）。框架升级 = 在此新增一块，不改既有 |
| `<线>\cfg_lock.json` | **配方 golden（路线级，闸门产物）**：只有 `entries[框架组合\|任务 id]`（env+agent 解析后字段树 + 摘要 + `params_version`）。主线落在 `versions\lizard\cfg_lock.json`，支线落在 `versions\lizard\parkour\cfg_lock.json`。**一条线一个文件**：`--update --line <线>` 只能写自己那份，物理上改不到别条线的 golden（改前是全量写、会把其它线的漂移一并吞掉）。**跑 run 不增长**，只在框架组合变化时新增条目。不写进 `vN\`（冻结目录只读，`check_version_docs.py` 看守 vN 五件套）。`created_dirty` 为真表示该基线不干净（提交后重生成）；改配置而未 `--update --line <线> --reason ...` 重生成即红；漏 `--line` 直接拒写 |
| `tools\verify\recipe_lines.py` | **发现规则唯一入口**（stdlib-only）：线 = 主线的家族目录，或含 `v<N>\` 的下一层子目录；约定 `versions\<family>\<line>\<line>_params.yaml`（开发态）与 `vN\<line>_params.yaml`（冻结）、`<line>\cfg_lock.json`（锁）。零份/多份/名字不符/父目录非 `vN` → **抛错不跳过**（返回半张表 = 下游每个数字都无意义）。`check_dr_parity` / `check_cfg_lock` / `check_version_docs` / `check_recipe_registry` 全走它，四个闸门不再各说各话 |
| `versions\lines.json` | **实验线生命周期索引（ARCH_PLAN 2.1，SSOT）**：`format`/`revision`/`lines`，键 = `recipe_lines.discover()` 的线句柄（`lizard`、`lizard/parkour`），每条 `status`（只许 `active`/`retired`）+ `successor`/`retired_at`/`reason` + 可选 `deprecation`（`notice`/`declared_at`/`retire_not_before`）。**二值生命期**：权限只看 `status`；`retire_not_before` = 允许正式退休的最早条件（`date` 或 `registry_revision`，必须机器可判定），**不承诺到点阻断** —— 阻断只在显式改 `status` 后生效。索引变化不改写历史 run 记录 |
| `tools\verify\test_recipe_lines.py` | 上者负测试：零份/多份 `*_params.yaml`、基名与线名不符、父目录非 `vN`、线不可发现等拒绝路径必须全部触发 |
| `tools\verify\check_recipe_registry.py` | **实验线生命周期闸门（ARCH_PLAN 2.1/2.2 离线半，L01+L05/L06 离线半边）**：`validate()` 是纯函数，合成索引即可驱动。查：发现到的线 ⊆ 索引（缺即红 —— 缺失不得读作 `active`）、索引条目必须对应真实线（悬空/拼错即红）、条目键白名单（夹带 per-run 字段即红）、`status` 只许二值、`retired` 必带日期与原因而 `active` 不许留退休证据、`successor` 必须存在且为 active 的另一条线、`deprecation` 键齐全且条件必须是 `date`/`registry_revision` 且机器可判定（自由文本即红）、`declared_at` 晚于生效日即红、**提前退休**与**条件已满足但仍 `active`** 即红。时钟只在这个闸门里出现（`--now` 指定日期）；运行期按启动时读到的 `status` 放行 |
| `tools\verify\test_recipe_registry_gate.py` | 上者负测试（23 例 + 1 例时钟无关性）：合成 `versions\` 树 + 合成索引驱动每条拒绝；含两例正向（提示期判绿、条件已满足后显式 `retired` 判绿）与"同一索引在两个不同日期判据一致"（`registry_revision` 型条件无时钟依赖） |
| `versions\recipes.json` | **配方身份映射（ARCH_PLAN 2.1，SSOT）**：`recipes["<id>@<修订>"]` = `line`/`env_cfg_entry`/`agent_entry`/`legacy_task_version`，`tasks[任务 id]` → 配方键。**身份是写出来的、不是从名字推的**：修订在键里（内容变更必须新修订，不许复用键）、配置入口逐字声明、旧任务仍映射原配置类、禁止静默重定向。`legacy_task_version` 只能是 `null` 或 `v<N>`（v0 家族 8 个任务声明 `null` —— 它们的 `params_version` 实测就是 `None`，id 后缀 `v0` 不是配方声明） |
| `tools\verify\check_recipe_map.py` | **配方身份闸门（ARCH_PLAN 2.1 离线，身份半边）**：`validate()` 纯函数。用 `ast` 解析 `rl_exp\tasks\__init__.py` 的 `gym.register` 调用（**不 import registry** ⇒ 不被树里半成品拖红；`[24]` 走真注册表，两者不一致本身可查）。查：任务键集 == 注册键集（缺/多即红）、映射指向的配方存在、配方键形如 `<id>@<正修订>`、`line` 必须是已发现线、配方字段白名单（夹带 per-run 即红）、**`env_cfg_entry`/`agent_entry` 与注册逐字一致**（抓静默重定向）、声明的 `legacy_task_version` 必须是任务 id 的 dash 分词（`v1` 不被 `Lizard-Rough-v14` 满足）。**两半**：结构半（`ast`，stdlib 可跑）+ 配置半（`--bind-config`：按声明的 `env_cfg_entry` 导入并**构造**实例读 `params_version`，与声明值双向比对；类属性读不到，1.0 已证 —— 构造失败记红、不记跳过）。套件以 `--bind-config` 跑（`%PY%` 是 venv 解释器） |
| `tools\verify\test_recipe_map_gate.py` | 上者负测试（16 例 + 6 例绑定 + 真注册表解析）：未登记/多出映射、悬空配方、env/agent 重定向、悬空线、键缺修订或修订为 0、缺字段、per-run 夹带、非 `v<N>` 声明、`v1` vs `v14` 子串陷阱、非 `module:qualname`、format 漂移；绑定侧：版本不符（含"声明 null 而类里有值"反向）、构造失败、入口非字符串交回结构半。另钉死"从真实 `tasks\__init__.py` 读出 34 个任务"（首版漏读 `id=` 关键字参数 ⇒ 空注册表让闸门静默通过） |

### 资产与管线（Blender → URDF → USD，工具在 `tools\` 下按类分目录）

| 文件 | 作用 |
|---|---|
| `blender\lizard_stance.blend` | **站姿 SSOT**（232KB）：自然站姿摆好、骨位已 fix |
| `blender\fix_bones.py` | Blender：把骨骼 head/tail 对齐到关节球网格（v6 起世界↔臂架显式转换 + foot 桩外展轴 Y） |
| `blender\rotate_rig.py` | Blender（v6，一次性）：整体刚体旋转 R_z(-90°) 头 +Y→+X（27 骨 + 36 锚点 1e-6 自检；不烘焙——transform_apply 过 bone-roll 有浮点漂移，旋转保留为臂架对象变换） |
| `blender\rename_flip_v8.py` | Blender（v8，一次性）：**再转 R_z(+180°)（净 +90°，球头→+X）+ 26 骨解剖学重命名**（rear→chest、tail→neck、neck1-3→tail1-3、腿 rl↔rf/lf↔rr 两阶段防撞名）+ mesh parent_bone 显式重挂 + 末态布局断言（球头 +X/天线 −X/腿序）——v6 倒走判废的根因修复 |
| `blender\generate_urdf.py` | Blender：从站姿 blend 导出 URDF + STL（限位/力矩在 AXIS_MAP 硬编码；v6 起骨位读世界系，v8 起 AXIS_MAP 为净 +90° 转正后的世界功能轴——X/Y 分量对 v6 取反） |
| `blender\build_rig.py` | 历史一次性绑骨实验（硬编码桌面输出路径），已被上面两脚本取代 |
| `tools\pipeline\convert_urdf.py` | URDF → USD（Isaac Lab 训练用资产，输出 `assets\lizard\lizard.usda`） |
| `tools\pipeline\flatten_usd.py` | 压平 URDF-importer-3.0 层级（IsaacLab issue #5126 workaround） |
| `tools\pipeline\convert_stl_to_obj.py` | STL → OBJ 转换并重写 URDF 引用 |
| `tools\pipeline\migrate_joint_names_v8.py` | 一次性：v8 关节重命名对全部版本 yaml 的机械迁移（joint_order 改名 + 脊柱正则 `rear_.*`→`chest_.*`、`tail_.*`→`tail[0-9]_.*`；root/v8 yaml 的 joint_order 置为新 URDF 实际序，满足 export_ue 序列断言）——冻结目录改动的可审计出处 |
| `tools\pipeline\export_ue.py` | SSOT → UE 工件（关节映射/参数打包，盲部署前置） |
| `tools\archive\patch_kfe_axis.py` | URDF 手术：kfe 轴 Z→Y + 对称限位（旧版一次性脚本，仅考古） |
| `tools\archive\patch_stance.py` | URDF 手术：把自然站姿烘进零位（旧版一次性脚本，仅考古） |
| `tools\diagnose\inspect_blend.py` / `inspect_glb.py` | 无头 Blender：dump blend 骨架层级 / glb 零件包围盒 |
| `tools\diagnose\dump_all_parts.py` | dump blend 全部散件 bbox + 球形度（关节球定位用） |
| `assets\lizard\lizard.usda` | 训练用 USD 资产（cfg 引用） |
| `meshes\` | URDF 用的 visual/collision 网格 |

### 环境验证与诊断（跑环境不训练）

| 文件 | 作用 |
|---|---|
| `tools\verify\teacher_smoke.py` | teacher 冒烟（v2）：obs 308 维 + 全特权段判读（MASS_SUM≈72 / 力矢量 / 法线 / 摩擦 / wrench=0）；per-term 布局从 observation_manager 现场推导，无魔数切片 |
| `tools\verify\teacher_smoke_runner.py` | 冒烟 runner：唯一协议 + SMOKE_SPEC 版本表（同 TEACHER_PRIVILEGED_SPEC 形态，代码级真源）。开新版本 = 加表行 + 建薄壳，复制整文件违规（versioning.mdc A-3） |
| `tools\verify\teacher_smoke_v3.py` | 薄壳 = runner SMOKE_SPEC["v3"]：三组 90/208/83 + extero 顺序 lf/rf/rl/rr + tilt/foot_clearance 活性 + feet_air_time 已替换 + 有限性（PLAY-only） |
| `tools\verify\teacher_smoke_v5.py` | 薄壳 = SMOKE_SPEC["v5"]：PLAY（90/208/83 + v5 反塌缩奖励集合 + 无速度课程 + 无 SIR）+ TRAIN 2env（SIR 在真 TerrainImporter 上实例化、origin 重指落 10×20 格内、terrain_levels 有限） |
| `tools\verify\teacher_smoke_v6.py` | 薄壳 = SMOKE_SPEC["v6"]：v5 契约在轴改正资产上 + v6.1 spine_scale 0.25 解锁 |
| `tools\verify\teacher_smoke_v8.py` | 薄壳 = SMOKE_SPEC["v8"]：v6 契约在解剖学资产上（v6.2 参数、rebase of v6） |
| `tools\verify\teacher_smoke_v11.py` | 薄壳 = SMOKE_SPEC["v11"]：PLAY 无 tilt 只剩 time_out + ParticleVelocityCommand 回落 (0,3) + spine 0.25；TRAIN 4×120 param-grid + joint_sir 活性 + 桶±抖动命令（train_extras）+ frontier_max_v 键；开训前跑 |
| `tools\verify\check_joints_v8.py` | 关节功能检查（v8 解剖学资产）：**布局硬闸**（neck_pitch 球头必 +X、tail3_pitch 天线必 −X、前腿在前/左右各就位——v6"信骨名不信造型"教训条目化）+ 单关节注入驱动读数（头侧 pitch 关节欠阻尼读数注意事项在档） |
| `tools\verify\test_v5_rewards.py` | v5 奖励离线单测（mock env）：线性核 8 case（站立 0/倒退负/超速封顶/min_speed clamp）/ feet_slide ×c_k / 肚皮罚不随 c_k 退火 / undesired_contacts ×c_k |
| `tools\verify\test_v5_terrain_sir.py` | v5.3 SIR 地形课程离线单测（mock env）：TerrainGenerator 列→类型映射复刻 / 初始 reset 跳过 + origin 重指一致 / 成功三态判定（存活×位移×命令距离）/ 双侧软边带 / 带内重采样 / 流量不足保权 / 游走 clamp / replay 全历史池 / 块评估节流（240 步量化推进）。（v5.4 进度分制版 10/10 随弃案保全于 git `3ef2aa0`，复活见家族挂账 #15） |
| `tools\verify\test_joint_sir.py` | v11 联合 SIR 离线单测（mock env，10 项）：param-grid combo 展开 / Eq.2 标签 / 桶命令（含 0.0 桶 + 回落 + 抖动带）/ 兜底三分支 / 初始 spawn / Eq.7 权重 + 保旧权 / **跨块累积**（v11.1：未结算 pair 计数器跨块保留，旧代码必红）/ radix 编解码 / replay / 单轴游走 clamp |
| `tools\verify\test_v12_noise.py` | v12 高度环噪声离线单测（mock env）：工况比率 60/30/10 / offset 恒偏置 + foot_index 列选 / σ_p·c_k 幅度缩放 / outlier 全替换带 clamp / **中途重抽**（过半触发一次，reset 重臂）/ 无事件干净回退（PLAY/nominal 语义） |
| `tools\verify\test_resume_state.py` | 真续训状态层离线单测（mock env，复用 `test_joint_sir`/`test_v5_terrain_sir` 夹具，**27 项** = A 层 S01–S10 + B 层）：逐位往返 + **c_k 连续**（不回热）/ 静态指纹抓"地形网格改动而 n_pairs 不变"的静默错位 / 速度桶与任务身份不符拒恢复 / **评估时钟闸门（挂起块沿接受、落后整块拒绝；2026-09-15 由 C 层真跑发现的缺陷修复后新增）** / 无 joint SIR 任务透传 / 有 term 无状态**硬中断** + `--drop_curriculum_state` 显式降级（旧 `--weights_only` 别名）/ save hook 注入 + 参数透传 + `wraps` 保名 / `env_type` 漂移告警并还原 / 未覆盖课程 term 绊线 / 行 SIR 与 joint SIR 的**分支级 B 层**（测量更新、`n_traj_min` 以下、全带外回退、游走、replay：先断言分支签名，再走生产入口 `term(env, ids)`，原对象与恢复对象逐位一致）/ c_k-only 的迭代边界比对（按载荷保存参数独立重算 float64，误差 ≤1e-12）/ joint 槽字段集回归（少一字段即失败）。**注**：只证载荷往返与"状态→更新映射"；接线时序由 §1.4b 的真跑覆盖 |
| `tools\verify\cstate_observer.py` | **C 层观察器（真跑用，`ARCH_PLAN` 1.4b）**：经 3 行 `sitecustomize`（`%TEMP%\obs`，`PYTHONPATH` 注入，不入仓）在**真实 trainer 进程**内 `install()`，**只包装读取、不改参数/返回值/RNG**——`apply_resume_state`（P0 前 / P1 后 `collect()`）、`OnPolicyRunner.load`（与 ckpt 逐项比 actor/critic 参数与 optimizer `param_groups`/`state`，含 step/动量）、`learn`（记 `run_dir`/注册 term/请求长度/入口 counter+c_k；**单次调用跑满**，不循环 `learn(1)`）、`env.step`（逐 step `Δcounter`、P2 在首次 reset 后首 step 前、obs/reward 有限性）、`alg.update`（次数、Adam `step` 增量、参数摘要、loss 有限）、两个 SIR 的 `_resample`/`_resample_all`（**真实更新事件**：counter、`next_eval` 前后、更新后合法性与 P3）。每臂落 `observe_<pid>.json`（事件即写，**不依赖 `atexit`**：Omniverse 收尾会跳过它；另对 `set VAR=value &&` 的尾随空格做了 strip）。 |
| `tools\verify\check_c_layer.py` | **C 层判据（`ARCH_PLAN` 1.4b，需真跑证据）**：按臂名（`s_`/`p_`/`t_` + `-resume`/`-drop`）判——源 fixture（实际更新 ≥2、逐 step Δcounter==1、optimizer 更新数与 Adam 步增量一致、参数每次变化、loss 有限、`--source-checkpoint` 读载荷：counter>0 且 ≥1 持久字段 ≠ **同任务 drop 臂的 P1 冷样本**）；短路径（P0/P1/P2、`P1 == 源 counter`、模型/optimizer 与 ckpt 逐项相等、1 次更新、P1→P2 **持久集位级保持 + 出生集只查合法**）；主证据（单次 `learn(84)`、≥2000 步、`resume: final−source == 84×24`、`drop: final−0 == 84×24`、更新事件 ≥2 且 `clock ≥ 边沿`/`next_eval` 精确 +B/状态合法、`--resave` 校验最终 ckpt 可加载且载荷 counter 与调度前进）；c_k-only 线免 schedule 判据、改判 c_k 连续（入口 == 源出口、与独立 float64 重算 ≤1e-12、drop 回热到 `c0`）。出口 `C_LAYER_OK` / `C_LAYER_FAILED`；未判项记 `UNKNOWN` 不冒充通过。 |
| `tools\verify\check_obs_layout.py` | **obs 布局静态门**（离线）：v1/v2/v3 组名 + 组内 term 顺序 + extero 脚序 + 环形总点数 + c_k steps_per_iteration 与 runner num_steps_per_env 一致性（静默错位在 env 加载前炸出） |
| `tools\verify\check_reward_v13.py` | v13 跟踪核静态门（离线）：V13/PLAY 挂 `track_lin_vel_xy_miki`（weight/sigma_sq 对 yaml）+ EP 核移除；V5/V10 冻结不动（EP 核在、miki 不泄漏）；v13 yaml 记录齐 + v13.1 预注册静止值表（1.047/0.552/0.027 → 增益 0.453/0.948/1.473，由 weight/sigma_sq 推出） |
| `tools\verify\check_terminations_v14.py` | v14 摔倒闸静态门（离线 + torch，不起仿真）：判据单测（直立/头平放不触发 / **鼻朝下 80° 但无头接触不触发** = v14.1 合取 / 20° 前倾 + 400 N 不触发 / 60° 前栽 + 50 N 触发 / **鼻朝上 90° 不触发** = v3 假阳病根 / 双侧 roll 80° 触发 / 26° 斜坡 + 40° 鼻朝上不触发）+ dwell 累积-清零-reset 语义（stub env，25 步 @0.02 s 触发；轻接触永不累积）+ V14/PLAY 接线与 v10 `tilt` 删除共存 + V13 冻结不动 + yaml 记录 |
| `tools\verify\test_teacher_networks.py` | SplitEncoderModel 离线单测：前向 shape / 梯度 / 三组归一化更新 / 命名子模块摘取 / JIT-ONNX 导出 / 契约违约 |
| `tools\verify\test_student_networks.py` | student belief 栈离线单测：GRU 步进 / α∈[0,1] / 门控槽对齐 / 解码器维数 / load_from_teacher 等价 + 段序失配 raise |
| `tools\verify\test_v3_curriculum.py` | v3 课程/几何离线单测：c_k 方向与热身长度 / 无参退化 1.0 / DR 锚点缩放 / tilt 判据 / 环形 pattern 几何（52 点逐环） |
| `tools\verify\time_foot_rings.py` | C3 性能风险项：v3 脚环 vs v2 网格在目标 env 数下的 ms/step + 显存（实测 4096 env +15%，预算内） |
| `tools\verify\smoke_test.py` | 家族平地冒烟：建环境 + obs 维度 + 10 步 |
| `tools\verify\position_check.py` | 落地检查：base 高度轨迹 + 四脚接触力（≈700N=全重）+ NaN 扫描，`--rough` 切粗糙 |
| `tools\verify\pose_check.py` | 静态几何打印：各 body 相对 base 坐标（头/四脚/尾） |
| `tools\verify\view_terrain.py` | Isaac Sim GUI 看机器人站**指定版本真实地形**（改名重写自 view_lizard：--task 任意注册任务、零动作保持、--steps headless 冒烟）；每 env 悬浮红色**头向箭头**；挂 robot-vs-terrain 接触点探针，逐步打印接触点数 vs 碰撞栈预算（v4 stock 2**26 重验） |
| `tools\verify\terrain_preflight.py` | **开训前地形预检**（skill `isaaclab-pretrain-check`）：离线生成全部子地形 + 粗糙度统计（foot-plate relief 核心指标）+ PNG 渲染到 `_tmp_terrain_previews\` |
| `tools\verify\joint_check.py` | reset 后打印关节角（验证默认位姿加载） |
| `tools\verify\check_dr_parity.py` | **契约漂移闸门（--strict 即 CI）**：① teacher vs 家族 DR wiring 行静态对比；② `play_utils.DR_EVENT_NAMES` 与 `dr_controller._DR_EVENT_NAMES` 两份列表同步；③ 全部 `*_PLAY` 类必须调 `apply_play_wiring`；④ 两侧 `ArticulationCfg` 字面块行比对；⑤ 资产结构契约（usda 文本 vs 各 yaml：joint_order/Geometry scope/base_link/body 模式，资产换代改名即报警）；⑥ 资产锁比对（见 `asset_lock.json`）。`--update-locks` 仅在有意换代资产的同一 commit 里跑 |
| `tools\verify\framework_pin_check.py` | **框架 pin 检查**：grep IsaacLab 源码树里我们依赖的内部符号（cfg.func 替换 / RayCaster.meshes / live PD 增益 / warp kernel 等）+ 比对已验证 commit `28a37ce`（perf-2026-06-24）；升级 IsaacLab 后第一件事。**另含补丁存档校验**（2026-09-15）：把 `fork_patches\*.patch` 按序应用到 `git show HEAD:` 的 pristine 副本再与 fork 树逐字节比（行尾归一），并报每份存档"已应用／未应用／不可反向"——`setup.bat` 只看树侧，存档与树分叉会让它照样打印 `[ok]` 而静默丢一个 hunk。存档行尾由 `.gitattributes` 钉 `*.patch text eol=lf` |
| `tools\verify\test_recovery_parity.py` | recovery 向量化 vs 朴素参考实现等价性（纯 torch，随机+6 组边界） |
| `tools\verify\test_staged_curriculum.py` | 课程组件离线单测（mock managers，不起仿真） |
| `tools\verify\run_offline_checks.bat` | **离线全套一键**（32 项：pin/parity/recovery/staged 课程/teacher 网络/student 网络/v3 课程+环形/obs 布局/v5 奖励/v5 SIR/v11 联合 SIR/版本文档/v12 噪声模型/pxr 泄漏闸/续训状态/tb 抽样/v13 跟踪核/v14 摔倒闸/验收量测（同帧+abs 侧滑）/eval 帧契约 v2/configclass 字段面 + 其负测试/配置序列化器/**配方 golden 锁 + 其负测试/运行记录/配方线发现 + 其负测试/生命周期闸门 + 其负测试/配方身份映射 + 其负测试**，秒级不起仿真）；改 tasks 或 harness 后、commit 前必跑 |
| `tools\verify\check_pxr_leak.py` | **P001/P003 闸门**：import 任务 cfg 链（teacher/lizard/agents）断言 `pxr` 不进 sys.modules——防 hydra compose 期 pip usd-core pxr 毒化 Kit 启动（omni.physx "No to_python converter" 崩）；改 env cfg/mdp 顶层 import 后必跑 |
| `tools\verify\check_version_docs.py` | **版本文档完备闸 + 血统闸**（stdlib，pre-commit 也跑）：每版本目录四件套（PLAN/NOTES/`*_params.yaml`/asset_lock 锁自身，**支线 `versions/<family>/<line>/vN/` 递归覆盖**）+ `base.json` 血统边合法（母本存在且自身有 base.json；`--tree` 打血缘树）+ FAMILY 版本史行（线前缀键 `parkour/v1`）+ FILEMAP 行，缺即红——v10/v11 记录欠两版的根因（纯约定无闸门）的机器对策；tag 缺失仅 WARN（遗留前缀不一） |
| `tools\verify\check_configclass_fields.py` | **configclass 字段面闸门（ARCH_PLAN 1.0，离线）**：扫 `rl_exp\tasks` 全部带 `params_version` 的配置类（34/34 实测**是** dataclass 字段），打印 `__dataclass_fields__`/`to_dict()`/`__configclass_own_fields__`/类属性可读性；抓"声明字段未序列化""家族内字段/非字段混杂""类属性可读性不一致""字段不在 to_dict 而日志会丢"；`--env-yaml` 比真实 dump，`--json` 落完整面 |
| `tools\verify\test_configclass_fields_gate.py` | 上者负测试：注入 6 种漂移（to_dict 丢失/实例缺失/字段未序列化/类属性变可读/字段面混杂/分支契约不一致）必须全部触发 |
| `tools\verify\cfg_snapshot.py` | **配置快照序列化器（ARCH_PLAN 1.1）**：顺序敏感（映射与序列保插入序并纳入摘要）、浮点 `repr` 位级往返、callable→`module:qualname`、**MISSING 按类型判定**（构造期深拷贝会破坏 `is MISSING` 身份）、repo/Isaac 路径相对化、**对象地址不进文本**（否则摘要跟分配器走）；输出 canonical JSON + sha256 |
| `tools\verify\test_cfg_snapshot.py` | 上者离线验证：obs 组次序/摘要覆盖顺序（倒序必变）/浮点位级（1e-320、-0.0）/无地址/agent 树 MISSING 标签/路径相对化/**跨进程摘要一致**（两个 `PYTHONHASHSEED`） |
| `tools\verify\check_cfg_lock.py` | **配方 golden 闸门（ARCH_PLAN 1.1b/1.1c，离线）**：从 gym registry 取全部 rl_exp 注册任务（34 个，含 PLAY 与 parkour 线），按 `env_cfg_entry_point` **只构造不 `gym.make`**。lock v2 结构 `baselines[框架组合] → entries[任务 id]`，组合键 = `isaaclab rev / rsl_rl(editable rev 或发行版) / python`（**跑 run 永不增行**，只在框架组合变化时新增独立 block，旧 block 保留）。另查：条目自洽（摘要 vs 自带快照，防手改）、`params_version` 与任务 id 声明一致、条目不许夹带 per-run 字段、条目与注册任务一一对应、快照格式版本。**`--update` 必须带 `--reason`**，先打印逐字段差异，无 reason 拒绝且不写文件；组合无 baseline ⇒ 报失败要求另建基线（不就地重写）。其余：`--diff` 打字段路径差、`--vs-upstream` 与框架默认比值并按 MRO 归因到"最后改值的版本"、`--tasks` 收窄 |
| `tools\verify\test_cfg_lock_gate.py` | 上者负测试（22 项）：摘要漂移/手改 lock/版本不符/任务 id 与配方不符/条目对不上/夹带 per-run 字段/组合无基线/快照格式/格式版本与缺件/**无 reason 拒绝更新且不写文件**/**改一叶子只动一行 + 重复落盘字节一致**，全部必须触发 |
| `tools\runrecord\provenance.py` | **代码来源规则（单一实现）**：闸门与运行记录共用。git 树 = rev + `diff HEAD` 摘要 + porcelain 摘要 + 未跟踪文件清单（标注"需归档"）；editable 包 = 源码树，发行版 = 版本号（两者不可互换）；`rsl_rl_id()` 给出组合键用的短标识；`now()` 统一时间戳格式；路径经 `cfg_snapshot.relativize` |
| `tools\runrecord\manifest.py` | **运行记录（ARCH_PLAN 1.2，训练路径实际调用）**：T0 `pre_make`（配方/资产锁/代码来源/请求的 resume，落盘即写）+ 环境构造后核验（声明 vs 实际 num_envs/dt/seed/params_version + 实况 obs 组维度，不一致记失败）+ T1 `ready_to_learn`（解析后的算法/策略类、恢复后**实际生效 lr**、obs 组、resume 源哈希、课程状态证据）并在 `learn` 前冻结 → ckpt `infos` 只带 run id + T1 摘要 + 迭代 + 载荷摘要；**文件哈希另存 `checkpoints.json`**（不回写、不自引用）。整个 manifest 走 `cfg_snapshot` 落盘（MISSING/浮点/路径/地址同规则）；代码来源取 `provenance.py`。`--verify` 出两维度（记录完整/可重建/已验证重建 × 通过/失败/未知）：重算 T1 摘要、重校验声明-实际对儿、代码 rev+diff、资产 83 文件、配方再推导、ckpt 文件哈希；任一失败阻塞 |
| `tools\verify\test_run_manifest.py` | 上者离线验证（stub env/runner，29 项）：四调用点记录 + ckpt infos/index + 两维度报告，负例含**改过声明/连摘要一起伪造**（由记录内自洽性抓）、缺 T1、代码移动、资产变更、配方漂移、T1 前存档的 ckpt、ckpt 文件消失、声明-实际不符 |
| `tools\runrecord\rebuild.py` | **恢复演练工具（ARCH_PLAN 1.5，按需，非所有 run 的强制入口）**：`--capture <run_dir> <dest>` 按 T1 声明取材（干净代码按 rev 可取回、脏树 diff 与未跟踪代码**必须**有 `--archive` 落点，否则**拒采且不写材料**，只留拒采记录 —— `PLAN.md` #18 变成闸门）+ ckpt 与 run 记录拷贝并逐文件摘要；`--check <dest> --root <重建位置>` 查：scope（重建了什么 / 复用了哪些依赖，`--root` 落在原树内 ⇒ "只换配置"不算材料恢复演练）、材料摘要、**只对 `--rebuilt-module` 声明为重建的材料**做来源判定（默认 `rl_exp`；落回 `--original` 原树或落在重建位置与 `--dep` 之外即失败；声明复用的依赖只记录不断言）、资产锁解析位置、配方从重建代码再推导、ckpt `infos` 回指本记录 T1、原目录可读性只作信息行（不做系统级访问切断）；`--maintest` 删一个必需载荷必须失败、还原必须通过。不起仿真，只到"配置与加载级" |
| `tools\verify\test_rebuild_gate.py` | 上者离线验证（31 项，复用 `test_run_manifest._record` 造 run 记录）：漂移脏树拒采、无归档拒采、带归档落盘且摘要一致、未跟踪代码内容缺失拒采、材料完好/来源/载荷绑定三行、落回原树或未声明位置判失败、复用依赖不断言而 `--rebuilt-module` 声明后必判、未给 `--original` 记未知、原目录可读只作信息、只换配置不算演练、删载荷必失败+还原必通过、被改载荷与冻结后被改记录均不得通过、拒采记未知（退 2）而失败记阻塞（退 1） |
| `fork_patches\train_run_manifest.patch` | 训练侧四个调用点（T0 在 `gym.make` 前 / 构造后核验 / runner 后装 save 钩子 / `learn` 前冻结）。**依赖 `train_curriculum_resume.patch` 先应用**：其 save 钩子装在课程钩子之后（外层写文件哈希），且 T1 的 `resume` 段直接记录该补丁产出的 `drop_curriculum_state` 与 `curriculum_resume` 结果（S10：manifest 不自行反推恢复结果）。两个补丁的插入点互不重叠，`git apply --check --reverse` 各自幂等，setup.bat 按文件名顺序应用 |
| `tools\diagnose\debug_pose.py` | reset 后立即 dump 全部腿关节轴心世界坐标 |
| `tools\diagnose\diag_metrics.py` | **验收量测纯函数**（no sim，torch）：`yaw_frame_lin_vel`（= 奖励核同帧）、`forward_error`（签名/abs 均值误差 + 逐帧 MAE）、`sideslip_abs_mean`（`mean|vel_yaw_y|`）；诊断工具与离线闸共用，防"验收与奖励不同坐标系"复发 |
| `tools\verify\test_acceptance_metrics.py` | 验收量测离线闸（no sim，5 例）：核满分/超速/欠速/侧滑降分、yaw 不变性（同相对运动同奖励）、**混俯仰不误报欠速**（体坐标在 45° 俯仰下假阴 −29% → 旧实现必失败，作回归证据）、**左右交替侧滑必判不通过**（签名均值 ≈0 会放行）、快慢交替由逐帧 MAE 暴露 |
| `tools\diagnose\diagnose_nan.py` | Flat 任务 NaN obs 诊断（历史问题排查用） |
| `tools\diagnose\direction_probe.py` | **方向探针**（v6 倒走归因工具，默认指 v8 最新 run）：强制前进窗口下量 disp_head——世界位移在头方向投影，负值+正命令=真倒走；训后验收复用 |
| `tools\diagnose\play_fast_task.py` | 注册 `Lizard-Rough-Play-v8-fast`（前进窗口钉 1–3 m/s）——play.py `--external_callback` 挂钩，GUI 目视用 |
| `tools\diagnose\play_keyboard_task.py` | **键盘遥控**（play.py `--external_callback`）：把任意 `Lizard-*-Play-vN` 的 `commands.base_velocity.class_type` 换成 `KeyboardVelocityCommand`（`_resample_command` 空操作 + `_update_command` 直写 `vel_command_b` 读 `Se2Keyboard`）——不改 IsaacLab 树，stock `UniformVelocityCommand` 的 heading/resample 覆盖问题从源头消失；`python -m` 跑离线自检。备选路线是 `fork_patches\play_keyboard.patch`（改 `<ROOT>` 的 play.py，任意带 `base_velocity` 的任务通用；已在 `gym.make` 前关掉命令 term 的自主变更，否则被 `CommandManager.compute` 覆盖） |

### 训练工具与 UE 导出

| 文件 | 作用 |
|---|---|
| `tools\trainlog\dump_tb.py` | TB 事件文件 → CSV（版本记录用：`--log_dir <run目录> --out versions\lizard\vN\tb_scalars.csv`）。`--max_points N` 按 tag 自适应抽样、**保首尾**（首尾必须留：`plot_tb` 标的就是末值；同长 tag 抽样后仍同长，否则墙上时间图会静默消失）；`--csv_in` 可对已有 CSV 重抽样，**不需 tensorboard** |
| `tools\trainlog\probe_run.py` | **训练中巡检探针**（skill `isaaclab-train-probe`，取代 read_curriculum）：`--exp v4`/`--run <目录>`/默认最活跃 run，只读 tfevents 出健康快照——进度+ETA（max_iterations 读 params/agent.yaml）、各 tag last/窗口均值/Δ% 趋势、终止计数、课程值、NaN/骤降/事件停更/ckpt 落后告警；秒级不起仿真 |
| `tools\trainlog\plot_tb.py` | tb_scalars.csv → 训练曲线 PNG（reward/终止/局长/课程/墙上时间五张，`--mark` 标已评测 ckpt，默认 200 DPI）；墙上时间由 `Train/mean_reward/time` 的 step 轴（引擎自记秒数）派生，不靠累加估计；`figure`/`series_to_figs` 供 `ablation_harness\plot_eval.py` 的 HTML 报告共用。**产物不入库**（可再生） |
| `ue\build_lizard_ue.py` | UE 编辑器脚本：按 `ue\lizard_ue.json` 组装蜥蜴物理 Actor |
| `fork_patches\config_lizard___init__.py` | fork shim 现成副本（装到 IsaacLab 树注册任务用） |
| `__init__.py` | 包声明（`import rl_exp` 入口，经 venv .pth 可达） |

## ablation_harness\ —— 评测系统（Locomotion-Eval-v2 当前；v1 封存）

| 文件 | 作用 |
|---|---|
| `host_paths.py` | **机器本地路径的唯一读者**：解析 `isaac_root` / `python`，供 `eval.py`、`run_ablation.py`、`run_offline_checks.bat`、`hooks\pre-commit`、`framework_pin_check.py` 共用（此前五处各自硬推，junction 布局一死就全错位）。纯 stdlib、不 import `rl_exp`——被裸解释器调问"venv 在哪"时也得能答；**无 PATH 兜底**，宁缺不猜。`--root/--python/--check` 给 shell 用，取不到 exit 1 |
| `eval.py` | 统一评测 runner：task + checkpoint + 协议 + 模式 → eval.json |
| `run_ablation.py` | 消融调度器：spec yaml → 串行 train+eval → 汇总表，断点续跑；`--by-terrain` 出逐地形长表+pivot |
| `plot_eval.py` | 评测可视化（读组目录 eval.json，不起仿真）：`--report <版本目录>` → 单文件 HTML 汇总报告（训练曲线+评测图+summary 表+rev 溯源，**默认选它**）；`--out_dir` → 散图 PNG（只需贴图进工单时用）。两者均不入库 |
| `metrics.py` | 指标库：tracking/success/energy（PD 反解 τ）/fall 几何判定/completion |
| `suites.py` | 固定地形套件（9 地形确定性三锁：curriculum+等比例+单值难度+seed） |
| `components\command_player.py` | 命令时间线播放器（协议 yaml 是唯一真源） |
| `components\dr_controller.py` | nominal/robust 模式的 DR 开关变换 |
| `components\recovery.py` | recovery push：冲击注入 + 恢复计时（只统计冲击时仍在第一局的 env） |
| `protocols\locomotion_eval_v1.yaml` | **评测协议契约（冻结封存）**：早于 v2 的采样帧口径（step 前 = obs 帧，终止帧丢失） |
| `protocols\locomotion_eval_v2.yaml` | **评测协议契约（当前）**：时间线/阈值/suite/DR 同 v1，唯一变更 = 帧定义（step 后 = reward 帧，含 hook 抓到的终止帧）。改动 = 新建 v3；**v1/v2 结果不得混表** |
| `specs\example_baseline.yaml` | 消融 spec 示例 |
| `results\locomotion_eval_v1\` | v1 跑分落盘（记录即数据，随仓提交；**冻结不迁移**，不与 v2 混表）。campaign 分组：`--group v1` → `locomotion_eval_v1\v1\<run_id>\` + 组内专属 `summary.csv`（全局指标）+ `terrains.csv`（逐地形长表，`--by-terrain` 生成）；`--summarize [--group v1]` 看单组或汇总。v2 结果同构落 `results\locomotion_eval_v2\` |

## .codemaker\skills\tool\ —— AI 开发技能（方法论）

| 技能 | 作用 |
|---|---|
| `isaaclab-task-creator` | Isaac Lab 任务创建方法论 + 运行时事实（log 命名/五元组/configclass 单例/ProxyArray） |
| `isaaclab-asset-pipeline` | 资产管线方法论（URDF→USD 坑/验证链/症状表） |
| `isaaclab-eval-harness` | 评测协议要点 + 指标口径 + 调度用法 |
| `isaaclab-train-probe` | 训练中巡检方法论（probe_run 用法 + 对照版本 NOTES 判读 + 汇报纪律） |
| `git-auto-sync` | 迭代完成自动 commit+push 云端（本项目 git 纪律） |

## 历史包袱提示（下一个 AI 注意）

- `smoke_test.py` / `pose_check.py` 2026-08-31 刚修过陈旧 bug（动作维度/旧命名），跑挂先查命名是否又变了
- `blender\build_rig.py`、`patch_*.py` 是管线早期一次性脚本，仅考古价值
- **`ablation_harness\results\...\summary.csv` 里 2026-08-28 两行的 `energy_per_m_j` 数值无效**（energy 修复前少乘 step_dt，虚高 ~50×）；其余列有效，energy 列重跑后才有意义
- 旧趴窝 checkpoint：`E:\IsaacLab\logs\rsl_rl\lizard_rough\2026-08-28_14-08-22`（15000 iters，家族 run，不在仓里）
