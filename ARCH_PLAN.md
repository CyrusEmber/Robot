# ARCH_PLAN —— 实验可复现性与配置组织重整（提案，待审核）

> 意图文档，非 SSOT。事实侧见 `FAMILY.md` / `OBS.md` / `HARNESS.md` / `FILEMAP.md`。
> 落地后挂账归 `PLAN.md` #14。修订：v0.10（2026-09-15，1.2a 运行记录落地 + 训练侧补丁已应用）
>
> **读法**：只看 §速读 §详案 §不做。附录 A/B 是证据与审计留痕，审完即可不看。

## 速读

**目标**：一次实验绑定明确的**代码版本、输入数据与资产版本、最终运行配置**；恢复训练**延续已声明覆盖的学习与课程状态**；新实验用**显式配方**表达变化。

**总判据**：宁可承认"某项条件不可证"，也不要"全绿却仍不能证明实验条件一致"。

**不变量**

1. 已发布任务 ID 与公开入口保持兼容（命令、类名、`class_name` 点路径可加载）。
2. **在指定代码 + 框架 + 资产版本组合下**，历史配置构造语义不变。任务 ID 未变 ≠ 实验可复现。
3. checkpoint 加载兼容性**单独验证**（载荷键、协议 id、状态格式版本）。
4. 历史实验的重建能力**按证据等级声明**，不默认宣称"可复现"。
5. teacher 零家族 import；已发布 term 不改语义；冻结目录只读。
6. 不新造训练框架；上游补丁只减不增（现 3 个）。

**三阶段一览**

| 步 | 做什么 | 出口 |
|---|---|---|
| 1.0 | `params_version` 字段性质实测 | **已完成**：是字段、类属性读不到；整改形态 = 提成显式入参并保字段与日志面 |
| 1.1 | 配置快照（recipe/run）+ 值差异报告 + golden + 闸门 | **已完成 1.1a/1.1b**：序列化器 + 家族级 golden 覆盖 34 个注册任务/PLAY（套件 `[23][24][25]`）；待定 2 = golden 体积 |
| 1.2 | 会话记录 T0–T3 + 外部 ckpt 索引 + 两维度 `--verify` | **1.2a 已落地**（套件 `[26]`，补丁已应用）；**1.2b 运行时验收待真跑**（起仿真，需专门安排） |
| 1.3 | 状态注册表（joint SIR + 行 SIR + c_k）+ 边界收紧 | 三条线续训连续可证 |
| 1.4 | 恢复验收三层（A/B/C） | A/B 自动化，C 含冷启动负对照 |
| 1.5 | 隔离重建（一个新 run，原源码/资产不可访问） | 来源断言与缺件负测试通过，至少一条达"已验证重建：配置与加载级" |
| 2 | v15 配方化 | 硬 A/B/C 全过 |
| 3 | 协议对象 + eval 四项绑定 + 地形映射 A→B + 导出校验 | 协议摘要进 manifest 与 eval |

**六条硬约束**（易被绕过的都在这里）

1. **两维度**：证据等级（记录完整/可重建/已验证重建）× 检查结果（通过/**失败**/未知）。失败阻塞验收；未知允许推进不依赖它的工作但**不计通过**；**必需硬验收项未知 ⇒ 该步不得宣告通过**；历史非必需追溯项未知不阻塞。
2. **"已验证重建"要写范围**：隔离目录与依赖（见 1.5）+ 验证项清单 + 环境 + 比较方法 + 容差；不推导未验证的行为等价。关键重建检查失败 ⇒ 不得再标当前"已验证"（旧通过记录保留 + 注明时间与对象）。
3. **无自引用哈希**：文件哈希不写进文件自身；`infos` 只放 run id + T1 manifest 摘要 + 迭代号 + 载荷摘要（声明非文件哈希）。
4. **不用豁免掩盖字段面变化**：硬 A 基线 = 整改前 golden；确需改字段面 → 逐**字段路径**白名单（旧值/新值/转换规则/语义无影响验证），**禁止整字段或整子树豁免**。
5. **manifest 不可变**：T0 启动证据 → 环境构造阶段快照 → **runner 构造、恢复与实际来源核验完成，`learn` 前** T1 最终 manifest 冻结 → T2 引用 T1 的 SHA-256；索引与验证结果另存不回写；T1 前任一步失败均保留已有证据并标注未完成 T1。
6. **不补造历史**：不改写原始记录；历史结论只有"按证据判失败/未知"两种，且追加说明。

**待定 2 项**：① 归档位置（NAS / 对象存储 / 工单附件）；② golden 体积 2.7 MiB 是否可接受（见 1.1b）。均不阻塞 1.2 开工。

## 详案

### Step 1 —— 保护当前结果

**1.0 实测 `params_version`**（已完成 2026-09-15；闸门 `rl_exp/tools/verify/check_configclass_fields.py`，已入离线套件 `[21]`）

扫描 `rl_exp/tasks` 全部 34 个带 `params_version` 的配置类，实测结论：

- **是 dataclass 字段（34/34）**。机制：装饰器先补齐注解（`configclass.py:99`），每个成员被换成 `field(default_factory=...)`（`:475`），`dataclass()` 包装（`:115`）时类属性被删除。
- **因此类属性读不到**：`getattr(Cfg, "params_version")` 抛 `AttributeError`，值只存在于实例上。源码注释（`teacher_env_cfg.py:490` 称"普通类属性、非字段"）与实测不符，按实测记。
- 字段进入 `to_dict()`（34/34），`from_dict()` 往返后取值不变 ⇒ 日志面与从日志回放不受影响。
- `None` 不是漏配：`_load_params(None)` 读家族 live dev yaml（`lizard_env_cfg.py:53-54`），非 teacher 家族基线类如此。
- `env.yaml` 等价性：`train.py:273` → `dump_yaml` → `class_to_dict`（`utils/io/yaml.py:53`），而 `to_dict` 即 `class_to_dict`（`configclass.py:109`）⇒ **实例 dump 与 `to_dict()` 键集相同**。本机未见 `params/env.yaml` 样本（已搜本仓与 `e:\`），闸门留 `--env-yaml` 供样本出现后实测。

**整改形态（Step 2 依据，走"提成显式入参"分支）**：优先保留字段、默认值与序列化兼容性（CLI 覆盖、`from_dict` 回放、日志读取均不受损）；禁止任何 `getattr(cls, 'params_version')` 式读取（类上不存在）；不得借整改删字段或改子树；确需改字段面 → 走 §2 硬 A 白名单。

**1.1 配置快照**（产物 `versions/lizard/vN/cfg_lock.json`，闸门 `check_cfg_lock.py` 入离线套件）

三类产物分开，**离线 cfg 工具不得被迫实例化环境**：

| 产物 | 内容 | 时机 | 需环境？ |
|---|---|---|---|
| ① 配置快照（recipe / run 两份） | env/agent cfg 字段树；run 另记录实际解析的模型、算法与恢复后生效值 | recipe：`gym.make` **前**；run：T1；环境构造后留阶段快照 | recipe 否；run 需环境与 runner |
| ② 生成结果映射 | 列 → sub-terrain 名（`<type>\|<levels>`）→ 参数 | 地形生成后 | 需生成 |
| ③ 课程状态 | `_n_levels`/`_combo_cols`/particles/权重/时钟/env_pair/desired_vel | 运行时 collect | 需 manager |

①的序列化规则（不排序语义序是重点）：

- 顺序有语义（obs 组/term 序、action 序、joint/foot 序、地形列→combo 序、`sub_terrains` 键序）→ **有序条目并纳入摘要**。
- 浮点无损往返（`float.hex()`/`repr`），禁定长截断。
- callable → 稳定标识（模块路径 + qualname + 类名），代码版本单独绑定；不存地址/`repr`。
- 缺失 ≠ None（哨兵 `__MISSING__`）。
- 路径相对化（`<ISAAC_ROOT>`/仓根）；资产走内容哈希。
- 构造后被替换的 `cfg.func`（`gym.make` 时被换成实例）→ run 快照只记类型 + qualname。

**1.1a 小范围验证（已完成 2026-09-15；`cfg_snapshot.py` + `test_cfg_snapshot.py`，入套件 `[23]`）**：规则在真实 v14 树上落地并逐条可失败。实测要点：

- **必须遍历实例命名空间，不能遍历声明字段**：`V3.__post_init__` 用赋值建 obs 组（`self.observations.extero = ...`，`teacher_env_cfg.py:976`），这些组不在 `__dataclass_fields__` 里 —— 按声明字段遍历会**静默丢掉 proprio/extero/priv**，正好是本方案要防的失效模式。现已按 `vars()` 序遍历，并把"声明了但实例上没有"的字段写成缺失哨兵。
- **规则 4 的真实来源是 agent cfg**：env cfg 装不下 `MISSING`（默认值在装饰期就报错，`configclass.py:304`），但 `RslRlOnPolicyRunnerCfg` 的 `stochastic`/`init_noise_std`/`obs_groups` 等字段就是未设值、待 runner 填。**且必须按类型判定**：构造期深拷贝会造出新的 `_MISSING_TYPE` 实例，`value is dataclasses.MISSING` 对这些字段全为 False（1.1b 实测：整个 agent 树因此退到兜底分支，把对象地址写进摘要）。
- **摘要必须跨进程稳定**（同进程重复构造相等不足以证明）：兜底分支不得输出含 `0x...` 的文本；已加双进程（不同 `PYTHONHASHSEED`）比对。
- 浮点按 `repr` 往返（含 1e-320/5e-324/-0.0/1e308 位级一致）；非有限值走标签（裸 `NaN` 在 `allow_nan=False` 下本就非法）。
- 顺序纳入摘要：把 extero 组倒序后摘要必变。
- 摘要可跨机：v14 摘要 49.9 KB，仅剩外部内容 URL（`omniverse-...s3...`），无遗留绝对路径；外部 URL 原样保留。
- `class_type` 等已是 `ResolvableString`（`module:qualname`）⇒ 原样作字符串，不再包标签；`slice`/tuple 等真实数据确实走到标签分支（非死代码）。

**1.1b golden 注册表（已完成 2026-09-15；`check_cfg_lock.py` 入套件 `[24]`，负测试 `[25]`）**

- **落点改为家族级单文件 `versions/lizard/cfg_lock.json`**（原计划写 `versions/lizard/vN/cfg_lock.json`）：`versioning.mdc` 红线"冻结目录只读"且 `check_version_docs.py` 看守 vN 的五件套，而 golden 是随树变化重生成的闸门产物，不该写进冻结目录。条目按 gym 任务 id 索引，每条自带 `version`。
- 覆盖 **34 个注册任务**（含全部 `*_PLAY`、parkour 线）；条目含 env+agent 解析后的字段树、摘要、`params_version`、类引用。**2.7 MiB**。→ 见下方"待定 2"。
- **离线**：从 `gym` registry 取任务，按 `env_cfg_entry_point` 解析类并**只构造**，绝不 `gym.make`（不碰 sim）。
- 校验项：摘要一致 / golden 条目自洽（摘要与自带快照必须匹配，防手改）/ `params_version` 与条目一致 / **任务 id 声明的版本与 cfg 实际加载的 yaml 一致**（`Lizard-Rough-vN` ⇒ `params_version == vN`）/ 条目与注册任务一一对应 / 快照格式版本一致。
- **值差异报告**：`--vs-upstream` 对 `LocomotionVelocityRoughEnvCfg` 默认逐字段比值，并**按 MRO 归因到"最后改这个值的版本"**（`__configclass_own_fields__` 只说明字段声明处，说明不了值来源，故不用它当来源列）。v14 实测 121 处差异，归因 base 66 / V3 24 / V5 22 / V4 3 / V14 3 / V13 2 / V10 1，且 V11/V12 不出现（与 `V14←V13←V10` 绕开 V11/V12 一致）。
- 实测发现（已修）：上述 MISSING 深拷贝与地址泄漏两条；另外**首版摘要跨进程不稳定**导致 34 个任务全报漂移——没有跨进程比对就发现不了。
- 生成时记录 `locked_at_rev` / `locked_dirty` / `locked_isaaclab_rev`：dirty 树生成的 golden **不是干净基线**（首版即 dirty，提交后需重生成）。

**待定 2**：golden 体积 2.7 MiB（全字段树，review 友好的逐行 diff）。备选：只存摘要 + **差异对上游的子集**（约 50 KB，仍能检出漂移并解释大多数变化），代价是"框架默认值变化而本地未显式设置"的路径可能只报摘要变化而 diff 为空——该情形可由 `locked_isaaclab_rev` 变化解释，但会牺牲"红必能说清原因"。**不擅自减树**（等于整子树豁免，违反硬约束 4）。

**1.2 会话记录（启动声明 + 构造证据 + 训练就绪核验）**

**1.2a 已落地 2026-09-15（`rl_exp/tools/runrecord/manifest.py`，套件 `[26]`，训练侧补丁 `fork_patches/train_run_manifest.patch` 已应用）**：四个调用点（T0 在 `gym.make` 前 / 环境构造后核验 / runner 后装 save 钩子 / `learn` 前冻结）＋ ImportError 仅告警，逻辑全在仓内模块（补丁只留调用）。要点：

- **manifest 自身走 `cfg_snapshot` 落盘**：agent cfg 的 `MISSING`（`stochastic`/`init_noise_std`/`obs_groups` 就是未设值）首版直接 `json.dumps` 就抛 `TypeError`；改为一处序列化，MISSING/浮点/路径/地址全按同一套规则。
- **T0 立即落盘**（`gym.make` 中途挂掉也要留启动证据）；**T1 摘要可重算**：`t1_digest(manifest)` 在冻结与校验两侧共用，手改 manifest 无法留下匹配摘要。
- **校验不信记录自称**：`verify` 自己重算 T1 摘要、自己重比构造期"声明 vs 实际"对儿 —— 只改一侧、甚至连摘要一起伪造（把 `t1_sha256` 重算过）都能抓出来。
- **见证物分开**：ckpt `infos` 只带 run id + T1 摘要 + 迭代 + 载荷摘要；文件 sha256 落外部 `checkpoints.json`（写完才哈希，不回写 T1）；T1 未冻结时存档的 ckpt 标 `incomplete` 且不指向摘要。
- 资产按该版本 `asset_lock.json` 逐文件哈希（**allow-list，非依赖闭包**，已在记录里写明）；与锁不符即记失败。
- `--verify` 两维度：记录完整 / 可重建 / 已验证重建 × 通过 / 失败 / 未知；"已验证重建"在 1.5 未做前恒为**未知**，不冒充。

**1.2b 待做（运行时验收，需真跑，未做）**：验收 ①（T1 记录仅在 runner 阶段动态导入的模型类）、②（配方 lr ≠ ckpt lr 时记录恢复后实际生效值）、③（构造/恢复失败时无 T1）、④（引用漂移或冻结后出现未声明来源即失败）**在离线侧已按 stub 覆盖**，但仍需一次真跑落到实物记录上（另有 resume 一次形成对照）。这一步会起仿真、写日志与 ckpt，需专门安排。

| 时点 | 动作 | 内容 |
|---|---|---|
| **T0 `gym.make` 前** | 启动清单（`stage=pre_make`，立即落盘） | 引用清单（recipe/asset/terrain/obs_protocol 的 id + 摘要）+ 代码来源证据 + 资产闭包哈希 + seed/num_envs/sim dt/控制频率 |
| 环境构造后（T0 与 T1 之间） | 阶段快照（`stage=env_constructed`） | env cfg + 各 term `func` 类型与 qualname + 实际 num_envs；核验配方、资产、协议的实际读取内容；尚不宣称最终训练条件已确定 |
| **T1 runner 构造、恢复与核验完成，`learn` 前** | **最终 manifest 并冻结**（`stage=ready_to_learn`） | env/agent 配置 + 实际解析的算法、actor、critic 类型与代码来源 + 实际 obs 分组/归一化配置 + 恢复后生效的学习率等学习设置；绑定 resume 源文件哈希、加载选项及已恢复/显式丢弃的状态范围 |
| T2 保存 checkpoint | `infos` 只写 | run id + **T1 manifest SHA-256** + 迭代号 + 载荷摘要（非文件哈希） |
| T3 保存完成 | 外部 ckpt 索引（另存） | 文件 SHA-256 落 `checkpoints.json`，不回写 T1 |

**代码来源按实际加载记录**（`importlib` 解析模块所属仓根，新增依赖自动纳入）：Robot（本仓）与 IsaacLab fork 各记 rev + `status --porcelain=v2` + `diff HEAD`；RSL-RL **editable** 记源码树 rev + staged/unstaged + 未跟踪源码归档，**普通安装**记包版本 + 可取回安装产物。**未跟踪文件仅哈希不足重建 ⇒ 归档内容。**

**冻结规则**：T0 记录启动时已加载来源，T1 补齐 wrapper、runner 与恢复阶段实际加载的来源；不能把 T0 的模块枚举当完整代码清单。训练所需的动态组件须在冻结前解析并核验。若训练中才出现未声明的代码来源，另记失败证据并阻塞该 run 的完整性验收，不回写 T1 或继续宣称来源完整。T1 前的构造、恢复或核验失败保留 T0/阶段快照及失败原因，禁止写出 `ready_to_learn` 或绑定一个未完成的 T1 保存正式 checkpoint。

**核验对象分开**：配方/资产/协议等被引用内容与启动声明的摘要不符 ⇒ 失败；CLI 覆盖与 checkpoint 恢复引起的合法生效值变化，记录声明值、实际值及来源，不把不同阶段配置的摘要直接要求相等。resume 源内容哈希与加载选项进入冻结清单；学习状态摘要另指向 checkpoint，避免把完整张量载荷塞进配置快照。

**1.2 必需验收**：① 使用仅在 runner 构造时动态导入的模型，确认 T1 包含其实际来源与可取回内容；② 配方学习率与 checkpoint 学习率不同，确认记录的是恢复后算法/optimizer 实际生效值，并标明来源；③ 构造或恢复失败时无最终 T1；④ 引用文件漂移或冻结后出现未声明代码来源时，完整性检查必须失败。此处验收只证明记录与生效条件一致，不证明学习状态的后续演算等价。

其余：manifest 不做参数源（参数只从配方读）；入库只放小型索引，补丁与资产进归档（不能只留哈希）；`--verify` 输出两维度 + 缺失清单 + 已验证重建的范围。

**1.3 状态恢复**（组件表 + 三条边界）

| 线 | 组件 | 现状 | 方案 |
|---|---|---|---|
| v11/v12 | `JointSIRTerrainCurriculum` 粒子/权重/episodes/in_band/tr/回放池/env_pair/desired_vel/env_type | 已有 collect/apply/校验 | 纳入注册表 |
| **v5–v10** | **`SpawnWeightSIRTerrainCurriculum`** | 未覆盖 → 时钟恢复、SIR 冷启动 ≠ 连续 | 新增独立 collect/apply + 指纹 |
| 全部带 c_k | `common_step_counter` | 仅 joint SIR 路径回填 | 解耦：有 c_k 就恢复 |
| 其它课程 term | 任何 `ManagerTermBase` | 仅 WARN | 注册表未登记 **且任务声明要求恢复 ⇒ 硬失败** |

1. **补丁 ImportError** 现 WARN 后继续 → 对声明要求课程恢复的任务改硬失败（声明放任务 cfg 侧，如 `REQUIRES_CURRICULUM_STATE`），其它任务透传。
2. **`--weights_only` 正名**：实测只丢课程状态，rsl_rl **仍加载 model + optimizer**（`_peek_lr` 读 optimizer 学习率即证）→ 新增 `--drop_curriculum_state`，旧名保留为别名 + 弃用提示（不改公开行为）；`PLAN.md` #11 措辞同步。
3. **多 GPU 不在保证范围**：状态只从 rank 0 写；manifest 记 `distributed`/rank；README 与本文各写一句。

**1.4 恢复验收三层**

| 层 | 验收 | 证明 |
|---|---|---|
| A 对象级 | 保存前 `collect()` 与恢复后、首次 reset 前 `collect()` 逐位一致 | 载荷无损 |
| B 演算级 | 给两者相同 episode 统计 + 受控随机数，下一次课程更新输出一致 | 状态→更新映射一致 |
| C 集成级 | 恢复后跑 N 步：时钟推进、课程分布合理、有限值、训练正常；**冷启动作负对照** | 接线时序正确，非"复现" |

不要求冷热前 N 步逐位一致（RNG、出生、per-episode 瞬态刻意不存）。负测试保留：有 term 无状态 → 硬失败 + 显式放行参数。

**1.5 隔离重建**（依赖 1.2 的新 run 证据与可取回归档）

选一个新 run，仅使用其声明的代码、安装产物、配方、checkpoint 与资产，在独立目录和隔离环境重建。**换工作目录不足以通过验收**：原源码树、原资产路径与未声明缓存须对重建进程不可访问；使用隔离环境或访问控制实现，不移动或删除原工作树。

- **环境边界**：不继承指向原仓库的 `.pth`、editable 安装、`PYTHONPATH` 或资产搜索路径；缓存使用独立空目录，所需预置缓存必须作为声明产物核验。预装框架、解释器、二进制运行时等依赖逐项记录版本/来源与验证边界；不能核验的必需依赖记未知，不计通过。
- **来源断言**：记录并检查实际导入模块与 USD/mesh 等资产解析后的真实路径（解析链接），只能落在重建目录或显式声明且已核验的依赖位置；原路径仍可访问即隔离验收失败。
- **正向验收**：核验代码与资产内容摘要、完整 env/agent 配置及 T1 生效值、模型加载；配置中的运行目录/设备重定位逐项记录映射，不整树忽略。保存验证对象、环境、方法、容差和实际来源清单。
- **缺件负测试**：在可丢弃的重建副本中移除一个必需归档文件（如引用 mesh 或动态模型源码），重建必须明确失败，不得从原目录、共享缓存或未声明下载回退补齐；恢复该文件后重建通过。
- **出口**：正向验收、来源断言和缺件负测试均通过，方可标"已验证重建：配置与加载级"。不承诺推理或训练结果等价；若某项隔离条件不可验证，列出缺口并不得宣告 1.5 通过。

### Step 2 —— 替换配置组织（起点 = v15）

- **前置**：按 1.0 实测定整改形态。
- **单写者**：结构级 5 类（`terrain_generator`/`height_scanner`/`commands`/obs 组/`terminations`）各一个写入点；逐版本重复 `_load_params` 收敛为一次；构建路径固定：读取校验 → 构建组件 → 组合 → 兼容检查 → 落快照。
- **起点**：不在已训线（v13/v14）动刀——开 v15 或重构后新开家族。

**验收**

| 项 | 内容 |
|---|---|
| 硬 A | 新构建器先表达一个既有配方（如 v14），与**整改前 golden** 逐字段一致（前提：仍输出兼容配置）；旧入口不动 |
| 硬 B | v15 相对基准**只允许一份显式差异清单**（写入 `v15/PLAN.md`）；清单外变化即失败 |
| 硬 C | **全部注册任务 + PLAY** 的 golden 全过；"代表版本"只减重型仿真成本，不减 golden 覆盖 |
| 软 | 同 seed 200 iter **非硬门槛**；若用须声明误差口径与确定性前提（同 seed/env 数/设备/`--deterministic`/单卡），前提不满足只记录 |

硬 A 字段面白名单：逐条给**字段路径** + 旧值 + 新值 + 转换规则 + **不影响运行语义的验证**（CLI 覆盖仍生效、`params/env.yaml`/日志读取不受损、其余 golden 不变）；禁整字段/整子树豁免。

**上游升级**：旧框架组合基线保留，新组合另建基线（按 `framework=<isaaclab rev>` 分组）；不得把"更新 golden"当常规消警。

### Step 3 —— 闭环

**3.1 协议对象**（`tasks/` 下独立模块，历史协议显式版本化）：版本串、组名/term 序/维度、单位、坐标系、缩放裁剪、joint/foot 序、噪声归一化、部署可获取性；`check_obs_layout.py` 改为消费它。teacher/student 可不同协议，但转换关系显式定义 + 断言预处理后的实际张量（维度同 ≠ 语义通）。

**3.2 eval 绑定四项**：被评估 ckpt 内容哈希 / 应用 suite·mode·命令·扰动后的**实际评估配置** / 协议内容哈希 + 代码版本 / 资产与运行环境。hash 只**识别差异**，允许比较与否由协议声明判断。

**3.3 地形映射**（责任模块 `tasks/terrain_map.py` 为唯一真源）

- **步骤 A（先验证，不承诺）**：在**实际生成调用处**记录列、所选 sub-terrain、参数（sub-terrain 名即 `<type>|<levels>`；须同时绑定 levels 对应的参数表摘要），与课程现算法逐列比对。该记录证明类型/参数分配，不证明实际几何相同。
- **不一致的后果**：**当前 ⇒ 映射验收失败并阻塞**；**历史 ⇒ 对有代码/配置/生成证据的 run 逐 run 判**，证明不一致记失败、证据不足记未知，均保留原记录追加说明；不得由当前失败推导所有历史 run 都错。
- **步骤 B**：课程改为消费该记录，删除重算副本与测试复刻件；比对器只做"声明 vs 实际"，**测试不得复制生产算法**。
- **按保证需求保存**：只存参数 + seed ⇒ 只能声明"可重新生成"；列→combo 及参数表一致 ⇒ 只证明类型/参数分配一致。要声明**地形产物一致**，须归档并核验实际生成的 mesh/heightfield，以及影响实际使用的网格原点、变换和物理材质/碰撞配置；记录文件清单、内容摘要与可取回位置。映射一致不能替代几何证据，也不推导 PhysX 内部状态一致。
- **必需负测试**：同配方用不同 seed 生成含随机噪声的地形，构造"列映射相同、几何不同"案例；映射比较可以通过，产物一致性比较必须失败。相同归档往返加载应通过；缺失实际几何时该项判未知，不能凭映射提升为产物一致。
- 不从原点/网格几何反解参数组合；若记录不可得 → 降级为"生成前声明 + 反查到网格级"并写明敞口。

**3.4 蒸馏与导出**：student 输入契约 + ONNX 导出前用同一协议对象校验；蒸馏数据按"数据集 manifest + 分片哈希"（Phase 2 建）。

## 数据版本 §0.2（决定训练输入与实验条件的非代码内容）

| 对象 | 版本包含 | 方式 |
|---|---|---|
| 实验配方 | YAML 参数、组件选择、协议引用 | Git；发布后冻结 |
| 机器人资产 | USD 及引用的 mesh、材质、物理配置 | 文件清单 + 每文件哈希 + 可取回归档；**按依赖闭包**（只哈希顶层 USD ⇒ 引用文件可悄悄变） |
| 地形输入 | 生成参数、生成器代码版本、seed；必要时存实际结果 | 配方版本 + 生成结果清单 |
| 评估数据 | suite、命令序列、扰动、种子集合 | 独立协议版本 + 内容摘要 |
| 蒸馏数据 | teacher ckpt、采集配置、轨迹分片、预处理协议 | 数据集 manifest + 分片哈希 |
| checkpoint | 模型与训练状态 | 保存后算文件哈希，绑定来源 run |

**两层标识**：语义版本（`lizard_v15`、`lizard_anatomy_v3`）+ 内容摘要（manifest SHA-256）；同名内容变 ⇒ 摘要必变。

```yaml
recipe: {id: lizard_v15, sha256: "..."}
asset: {id: lizard_anatomy_v3, manifest_sha256: "...", archive_uri: "..."}
terrain: {config_sha256: "...", generator_code_revision: "...", seed: 42}
observation_protocol: {id: teacher_obs_v3, sha256: "..."}
```

**四条落地规则**：① 发布过的版本不可覆盖，改动即新修订，旧版仍可取回；② 小文件进 Git（清单也进），大文件进持久化归档，无需新平台；③ 哈希证明"是不是同一份"，归档地址解决"能不能找回来"；④ 生成数据按保证需求保存。

**这是引用清单，不是参数源**：参数仍从配方读，启动时核验实际读取内容再记摘要。

## 不做

搬目录 · 合并 teacher 与家族基类 · 序列化 PhysX 内部状态 / 逐位复现 RNG · 给每个实验复制代码树 · 新造训练框架 · 文件哈希写进文件自身 · `--verify` 失败降级为 WARN · 运行时结构塞进离线 cfg 快照 · 用当前工作树补造历史事实 · 把 manifest 当参数源 · 给每一步仿真数据做版本。

## 附录 A · 现状与证据（file:line）

| 项 | 现状 | 缺口 |
|---|---|---|
| 配方 | 冻结版本目录 + yaml SSOT + 逐版本子类 | `terrain_generator` 6 处写入（`velocity_env_cfg.py:93` → `teacher_env_cfg.py:574/881/1081/1158/1392`）；`height_scanner`/`commands`/obs 组/`terminations` 各 3–6 处；`params_version` 决定基类加载哪份 yaml（`:490-499`、`:508`）；逐版本重复 `_load_params`（`:920/1142/1264/1344/1386/1497/1619/1676`） |
| 继承 | `V14 ← V13 ← V10`（`:1646`、`:1586`） | **V13/V14 线路绕过 V11/V12**；配方化的对象是"线" |
| configclass | 装饰器先补注解（`configclass.py:99`）再包 dataclass（`:115`） | **实测（1.0，34/34）：`params_version` 是 dataclass 字段**——`_skippable_class_member`（`:524`）不跳字符串成员；成员被换成 `field(default_factory=...)`（`:475`）后由 `dataclass()`（`:115`）删掉类属性 ⇒ 类上读不到、实例上有、进 `to_dict()`；源码注释（`teacher_env_cfg.py:490`）称"非字段"已证伪 |
| 快照 | 训练侧 `params/env.yaml`+`agent.yaml`（`train.py:273-274`），落 IsaacLab 树内 | 仓内零处 golden；无值差异/来源视图；与配方/run 无绑定（1.1a 已有序列化器 `cfg_snapshot.py`，尚未落 golden） |
| run 记录 | `git_rev_lizard`/`git_rev_isaaclab`（`eval.py:370-371`）、seed/num_envs（`:365-366`） | 缺 rsl_rl 版本、sim dt/控制频率（`eval.py:454` 用过即弃）、协议串、资产绑定、resume 源、dirty；本仓脏树不记（`logger.py:44`/`train.py:265`） |
| 最终冻结时点 | runner 构造在 `scripts/reinforcement_learning/rsl_rl/train.py:247-249`，恢复在 `:270`（IsaacLab 树） | RSL-RL `algorithms/ppo.py:416-424` 构造时解析模型类与 obs 分组，`:390-391` 恢复 optimizer 与学习率；环境构造后尚未确定最终训练条件 |
| 资产锁 | `asset_lock.json` = urdf + usda + `meshes/**`（`check_dr_parity.py:278-288`） | **allow-list，非依赖闭包**；当前 usda 无外部引用（本次检索无命中）⇒ 缺口潜在 |
| 状态 | `curriculum_state.py` 覆盖 joint SIR + c_k | 只认 `JointSIRTerrainCurriculum`（`:90-99`）；行 SIR 未覆盖（`teacher_mdp.py:726`，`:364-369` 仅 WARN）；`common_step_counter` 仅在 joint SIR 路径回填（`:290`）；补丁 ImportError 仅 WARN（`patch:28-38`）；多 GPU 仅 rank 0（`:385-388`） |
| 地形 | 课程**重算**生成时公式 | 生成侧 cumsum + `0.001` 偏置 + dict 插入序（`terrain_generator.py:241-247`、`:249`、`:264-266`）↔ 课程侧（`teacher_mdp.py:1078-1149`）；`TerrainImporter` 只导入单个 mesh（`terrain_importer.py:92`）、`terrain_names` 是 mesh 名（`:143`）、生成器实例即弃（`:89-99`）⇒ 无法事后反解 |
| 地形产物 | `rl_exp/tasks/param_grid_terrain.py:14-17` 明确各行是随机地形的独立噪声实例 | 同列映射可对应不同几何；映射证据不能替代实际产物 |
| 隔离重建 | `README.md:57-61` 的安装步骤通过 `.pth` 将仓库加入导入路径 | 仅换工作目录仍可能加载原源码与资产；须验证真实来源并禁止未声明回退 |
| 评测 | harness 已有协议版本化 + 固定 suites | eval 从 registry 重算 cfg（`eval.py:144-166`）且不落快照；`*_PLAY` 逐版本繁殖 |

## 附录 B · 来源分级与修订留痕

**决策来源分级**：`用户明示`（直接指令）/ `审核建议`（三轮审核，是建议非拍板）/ `提案选择`（作者选择，无授权）。~~待默认通过~~ 不作授权依据（v0.1 用错，已删）。

**本轮（v0.10）**：1.2a 落地——运行记录模块 `rl_exp/tools/runrecord/manifest.py`（套件 `[26]`，29 项离线验证）＋训练侧补丁 `fork_patches/train_run_manifest.patch` 已应用到 fork 树且幂等；实测修掉两处："agent cfg 的 MISSING 进不了 JSON"（改为一处序列化）与"校验只信记录自称"（改为重算 T1 摘要 + 重比声明/实际对儿，连摘要一起伪造也能抓）。1.2b 运行时验收（需真跑一次训练）待安排。**v0.9**：1.1b 落地——`check_cfg_lock.py`（套件 `[24]`）+ 负测试 `[25]` + 家族级 `versions/lizard/cfg_lock.json`，覆盖 34 个注册任务与 PLAY；落点由 `vN/` 改为家族级（冻结目录只读）；`--vs-upstream` 改为按 MRO 归因到"最后改值的版本"。实测修掉 MISSING 深拷贝 + 兜底地址泄漏两处摘要不稳定源。**v0.8**：1.1a 小范围验证落地——`cfg_snapshot.py` 序列化器 + `test_cfg_snapshot.py`（套件 `[23]`），实测抓出"按声明字段遍历会静默丢掉 post_init 建的 obs 组"，并确认 MISSING 判定必须按类型。**v0.7**：1.0 实测落地——新增离线闸门 `check_configclass_fields.py`（入套件 `[21]`）与其负测试 `[22]`，实测 34/34 为字段并推翻 `teacher_env_cfg.py:490` 的注释结论；整改形态定为"提成显式入参 + 保字段与日志面"；附录 A configclass 行按实测改写。**v0.6**：用户要求补齐本次审查的三项缺口：T1 延后到 runner/恢复/核验完成且 `learn` 前；映射与实际地形产物分开举证；独立重建增加依赖隔离、真实来源断言与缺件负测试。该授权覆盖计划补齐，新增验收尚待实现与执行。

**v0.5** 无新决策，仅重排为速读、详案与附录并合并重复表述。

**v0.4 及以前**（保留，压缩）：

| 版本 | 变更 | 来源 |
|---|---|---|
| v0 | 初稿：现状对账 + 三阶段 | 提案选择 |
| v0.1 | 恢复验收改三层 + 冷启动负对照；200 iter 降为软证据；序列化规则；三态；组件表列旧 SIR；eval 四项；golden 全量覆盖；地形补责任模块 | 审核建议 + 2 项事实校正 |
| v0.2 | ckpt 自引用哈希改外部索引；地形撤回原点反解、先做生成处记录验证；v15 构建器硬 A/B；两维度；措辞：来源分级/三类产物/启动记录前移 | 审核建议 |
| v0.3 | §0 目标改写 + 不变量拆四条；未知范围限定；已验证重建范围；§0.2 数据版本 + 两层标识 + 四条规则；校正 4（资产锁非闭包） | 用户明示 |
| v0.4 | 硬 A 精确差异白名单（禁整树豁免）；代码来源按实际加载记录 + 未跟踪归档；manifest T1 冻结；地形不一致后果；硬 C 澄清；新增 1.5 重建出口 | 用户明示 |
