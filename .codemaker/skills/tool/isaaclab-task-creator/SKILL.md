---
name: isaaclab-task-creator
description: >
  在 E:\IsaacLab（Isaac Lab 3.0 fork）中新建/扩展强化学习训练任务（exp）与课程学习组件。
  当用户提到"新建一个exp"、"新建训练任务"、"加课程/curriculum"、"骨骼课程"、"速度课程"、
  "转向课程"、"StageCfg"、"staged curriculum"、"给 lizard/spider 加训练任务"、
  "注册新的 Lizard 任务"、"扩展现有平地任务"、"训练变体"、"PLAY 变体"、
  "teacher 环境"、"特权学习/特权 obs"、"Miki 两阶段/teacher-student"、"domain randomization"、
  "域随机化/物理随机化"、"随机质量/质心/摩擦/执行器参数/外力"、"加扰动"、"鲁棒性随机化"、
  "参数版本/versions/开新版本"、"冻结配方/快照环境"、"runner cfg/experiment_name"等需求时，
  务必使用此 skill。
  覆盖：manager-based env 配置继承、动作项拆分（保维度）、课程 term 编写、gym 任务注册、
  参数版本机制、DR 事件配置、快照纪律。
  URDF→USD 资产/站姿/转换用 isaaclab-asset-pipeline；评测消融用 isaaclab-eval-harness。
---

# IsaacLab Task Creator

在 `E:\IsaacLab`（Isaac Lab 3.0 fork）中新建训练任务与课程组件——方法论通用，适用于任何机器人。
已有通用课程组件 `StagedCurriculumTerm`，优先复用，不要重写。

## 目录约定与实例入口

**每个机器人一个 `<robot>_exp\` 目录**（E:\IsaacLab 根下），内含：

| 位置 | 内容 |
|---|---|
| `<robot>_params.yaml` | 参数 SSOT（开发态）：关节序/PD/action scale/命令范围/DR 段 |
| `FAMILY.md` | **家族总文档 = 实例事实唯一真源**：任务注册表（任务 id→参数版本）、版本历史、代码地图、验证脚本清单 |
| `PLAN.md` | 训练计划 SSOT（决策/挂账/验收） |
| `versions\vN\` | 冻结参数副本 + NOTES.md + tb_scalars.csv |
| `tasks\` | **完整任务包**（自有代码 100% 自包含）：`__init__.py`（gym 注册表）、env cfg 家族、`agents\`（runner cfg）、`staged_curriculum.py`（课程组件） |
| `convert_urdf.py` / `blender\` / 验证脚本 | 资产管线（见 isaaclab-asset-pipeline skill） |

**任务注册机制（自包含包模式）**：任务包住 `<robot>_exp\tasks\`，gym.register 的
entry_point 用 `lizard_exp.tasks.<模块>:<类>` 字符串。fork 源码树只留一个 shim
（`config\<robot>\__init__.py`：sys.path 插 IsaacLab 根 + `import <robot>_exp.tasks`），
`import isaaclab_tasks` 时自动触发注册。**import 可达性靠 venv site-packages 的
`<robot>_exp.pth`**（一行：IsaacLab 根路径）——新环境/新机器要重建。
脚本里 import 任务 cfg 用 `<robot>_exp.tasks.xxx`（包内互引可用相对 import）。

**动手前先读目标机器人的 FAMILY.md**——任务注册表、参数版本、验证脚本都在那里。
本项目实例：lizard → `E:\IsaacLab\lizard_exp\`。

框架侧路径（与机器人无关）：

| 路径 | 作用 |
|---|---|
| `E:\IsaacLab\env_isaaclab\Scripts\python.exe` | venv Python，py_compile/mock 测试用它 |
| `source/isaaclab_tasks/isaaclab_tasks/manager_based/locomotion/velocity/` | 速度跟踪任务包 |
| `.../velocity/velocity_env_cfg.py` | 基类 `LocomotionVelocityRoughEnvCfg`（勿改） |
| `.../velocity/config/<robot>/__init__.py` | fork 内唯一占用：10 行注册 shim |
| `scripts/reinforcement_learning/rsl_rl/train.py` | 训练入口 |

## 新建 exp 模式

新建 `<robot>_exp\tasks\<变体>_env_cfg.py` 继承该机器人的基座 env cfg，
注册进 `<robot>_exp\tasks\__init__.py`（gym.register）。**不要改框架基类**。
基座模式：直接继承 `LocomotionVelocityRoughEnvCfg`（换机器人 + 全量 DR + 按需平地化/粗糙化），
不经任何其他机器人的中间层。

## 参数版本机制（实例见各 FAMILY.md）

一个版本 = 一代训练配方；**跑 vN 只准读 `versions/vN/<robot>_params.yaml`**。

- `_load_params(version)`：None 读开发态 yaml；`"v0"` 读冻结副本
- 家族基座挂 `params_version = None` 类属性（无注解 → 纯类属性，非 configclass 字段）；
  版本化子类只改这一个属性 + 差异，注册新任务 id（`<Robot>-<Task>-v1`）
- 冻结配方（teacher 类）用模块常量钉死版本——开发态 yaml 的修改永不溯及
- 纪律：改参数 = 开新版本（复制目录）；换 seed 重跑不升版；纯参数变更不需要新任务 id
  （hydra override 即可），结构变更（reward/obs/actions）才建子类 + 新 id

## 代码规范（E:\IsaacLab\AGENTS.md）

- PEP 8、4 空格缩进、Google docstring、`snake_case`、PEP 604 联合（`x | None`）
- 新文件头部 SPDX：`# Copyright (c) 2022-2026, The Isaac Lab Project Developers ...` + `BSD-3-Clause`
- 物理量 docstring 带 SI 单位；改完用 venv python `py_compile` 检查

## 框架硬知识（验证过的事实，直接用）

1. **CurriculumManager 支持 class-based term**：`CurriculumTermCfg(func=类)`，类继承
   `ManagerTermBase`，框架以 `func(cfg=term_cfg, env=env)` 实例化；`__call__(self, env, env_ids)`
   每步被调，返回 dict 以 `Curriculum/<term>/<key>` 进 TB。无 `period` 字段，节流自己算。
2. **命令范围运行时可改**：`env.command_manager.get_term("base_velocity").cfg.ranges.lin_vel_x = (a, b)`；
   `_resample_command` 每次读 live cfg。
3. **门控指标现成**：命令 term `metrics["success_rate"]` 是按 env 的 episode 均值
   （阈值 `vel_xy_success_threshold=0.5`/`vel_yaw_success_threshold=0.4` 可配）。
4. **Action scale 运行时改**：`JointPositionAction` 在 `__init__` 拷贝 scale，必须同时写
   `term._scale = v` 和 `term.cfg.scale = v`。访问用 `env.action_manager.get_term(name)`。
5. **动作拆分保维度**：单 `joint_names=[".*"]` 拆成两组 term，声明顺序 = 拼接布局 =
   树序 → 网络/obs（含 `last_action`）维度不变。被锁组走 scale=0（见 6）。
6. **关节组锁定**：`use_default_offset=True` 下 target = default_pos + scale*action；
   `scale=0` → PD 锁 rest pose，物理上仍 attached，无动力学突变。
7. **跨课程依赖**：`env.curriculum_manager.cfg` 是公开对象，
   `getattr(cfg, "<term>").func.stage_idx` 读另一课程阶段号；格式 `"<term>>=<idx>"`。
8. **PLAY 变体**：`num_envs=50`、关 corruption、课程全置 None、命令范围设最终阶段值、
   所有 DR 事件置 None、地形网格缩到 5×5 且 `terrain_generator.curriculum=False`。
9. **替换 terrain_generator 会丢 curriculum 标志**：基类 `__post_init__` 末尾才置
   `curriculum=True`，super() **之后**替换生成器会回落默认 False（行序不按难度）——
   替换后显式重设。
10. **替换 height_scanner 会丢 update_period**：基类只给 stock 扫描器设了
    `decimation*dt`（50Hz），替换后落默认 0（200Hz，4 倍浪费）——替换后显式重设。
11. **configclass 单例安全**：详见 references/runtime_facts.md。

## Domain Randomization 事件（已验证签名）

term 全是类式 `ManagerTermBase`，定义在 `isaaclab/envs/mdp/events.py`（`mdp.<名字>` 直接用）。
范围值收进 `<robot>_params.yaml` 的 `domain_randomization` 段（SSOT），env cfg 里 `tuple()` 后写 params。

| term | 关键参数（已核实） | mode |
|---|---|---|
| `randomize_rigid_body_material` | `static/dynamic_friction_range`、`restitution_range`、`num_buckets`；`body_names=".*"` | startup |
| `randomize_rigid_body_mass` | `mass_distribution_params` + `operation="scale"` + `distribution="log_uniform"`（几何均值 1.0，跨体型不变） | startup |
| `randomize_rigid_body_com` | `com_range` dict；**必须**包 `preset(default=EventTerm(...), newton_mjwarp=None)` | startup |
| `randomize_rigid_body_inertia` | `inertia_distribution_params` + scale + log_uniform + `diagonal_only=True` | startup |
| `randomize_actuator_gains` | `stiffness/damping_distribution_params` + scale；implicit actuator 走 CPU tensor，**只能 startup** | startup |
| `randomize_joint_parameters` | `friction/armature_distribution_params` + add；CPU tensor，只能 startup | startup |
| `apply_external_force_torque` | `force_range`/`torque_range`，按质量放大（lizard 案例：72kg 用 ±40N） | interval |
| `push_by_setting_velocity` | `velocity_range` dict x/y/z | interval |

额外项：出生高度抖动 `reset_base.params["pose_range"]["z"]`；新 term 用
`setattr(self.events, "<name>", EventTerm(...))` 动态挂；OVPhysX 后端 material 随机化
是 no-op（只 warn，别当 bug 查）。

## 课程组件 API（staged_curriculum.py，直接复用）

```python
StageCfg(
    metric_threshold=0.8,          # success_rate 均值超此值开始计持续
    sustain_s=60.0,                # 持续时长 [s]
    command_ranges={"lin_vel_x": (0.0, 1.0)},   # 进入该阶段时写入命令 ranges
    action_scales={"joint_pos_spine": 0.0},     # 进入该阶段时写 action scale
    requires="speed_curriculum>=2",             # 前置课程须到达的阶段
)
StagedCurriculumTermCfg(func=StagedCurriculumTerm, stages=[...],
                        command_name="base_velocity", metric_name="success_rate")
```

语义：stage N 的 threshold/sustain 是**离开 N 进入 N+1 的门**；payload 在**进入该阶段时**
应用；stage 0 首次 compute 时应用。新增课程类型 = 新 stages 数据，不用新组件。

## 执行流程

### 第一步：需求解析

从用户描述提取（缺省给合理默认，列出让用户确认）：

| 信息 | 默认值 |
|---|---|
| 机器人/基础任务 | 目标机器人的基座 cfg（读其 FAMILY.md 确认） |
| 课程阶段表 | 每阶段的命令范围/scale/阈值逐阶段列出 |
| 阶段依赖关系 | 无 |
| 任务名 | `<Robot>-<变体>-<Terrain>-v0` 风格 |
| 是否要 PLAY 变体 | 要 |

**给用户展示阶段表（含假设值），确认后再写代码。**

### 第二步：写配置

1. 新建 `<robot>_exp\tasks\<变体>_env_cfg.py`：
   - 需要门控某组关节 → `ActionsCfg` 子类拆分动作项（被锁组 scale 声明为 0）
   - 用 `StageCfg` 列表组装课程（**可调参数全收进 StageCfg，不散落硬编码**）
   - `__post_init__`：super 后替换 actions、`self.curriculum.<旧课程> = None`、
     `setattr(self.curriculum, <新名>, cfg)`、初始命令范围镜像 stage 0
   - SSOT 纪律：scale/关节 pattern 从 `<robot>_exp/*.yaml` 读（`_load_params()` 模式），
     硬编码假设值必须在阶段表里向用户声明
2. `<robot>_exp\tasks\__init__.py` 追加 `gym.register`（训练 + PLAY 两个 id，entry_point
   用 `<robot>_exp.tasks.<模块>:<类>` 字符串）
3. rsl_rl runner cfg：维度没变就复用；新建必须**独立 `experiment_name`**（见坑列表）

### 第三步：验证

1. venv python `py_compile` 全过
2. mock 测试：仿照既有 exp 目录的 staged curriculum 测试脚本（lizard:
   `test_staged_curriculum.py`），假 env 驱动新 stages，断言 stage 0 首步应用 /
   sustain 后进阶 / 掉线清零 / 依赖不满足不进阶 / 非法 requires 抛错。
   mock 依赖项必须真继承 `StagedCurriculumTerm`
3. 冒烟：小脚本建 env 跑几步，验 obs 维度/有限性（注意裸 gym `env.step` 是 5 元组，
   见 references/runtime_facts.md；各 exp 目录有现成冒烟脚本，读 FAMILY.md 找）
4. **环境验证脚本速查**（改 env/资产/参数后跑哪个、输出怎么判读）：
   references/runtime_facts.md 文末速查表
5. 给用户训练命令：`python scripts\reinforcement_learning\rsl_rl\train.py --task <新任务id>`

## 已知坑（任务创建域；资产坑见 asset-pipeline skill）

- **冻结配方环境走快照纪律稳定的环境（teacher 类），只继承框架基类
  （`LocomotionVelocityRoughEnvCfg`），机器人/地形/扫描器/DR 抄入冻结（模块级常量快照），
  **不从活实验家族中间层继承**——家族演化会污染冻结配方（lizard 实测两起事故）。
  tasks/ 下访问 exp 目录：`pathlib.Path(__file__).resolve().parents[1]`。
- **runner experiment_name 按任务族隔离**：共用名字 → log 目录/checkpoint 互相污染
  （`get_checkpoint_path` 取最新 run 可能取错族）。同一 py 文件重复类名静默遮蔽，py_compile
  不报——建 runner cfg 后读一遍文件确认无重名。
- **`curriculum.<term> = None`** 是框架跳过 term 的标准方式；CurriculumManager 对
  dict/configclass 两种 cfg 都支持（读依赖时兼容，见 `_dependency_met`）。
- **yaml joint_order 是 URDF 树序的最好猜测**，USD 导入后实际顺序首跑才见分晓；对不上按
  运行时 warning 的实际序改 yaml。
- **3.0 importer 关节名加 `_joint` 后缀**（body 名不加）：关节正则带后缀、body 正则不带。
  失配报 `Not all regular expressions are matched!`，报错里列出可用名字。
- **startup 事件只随机一次**（env 创建时）：质量/CoM/PD/摩擦按 startup 是标准做法，
  每 reset 要重摇的量用 interval 或挂 reset。
- **换阶掉点是预期**：阶段切换 = 分布突变，value function 暂掉不是 bug；看
  `Curriculum/<term>/stage` 曲线 + 恢复速度判断阈值。速度阶段不重叠会分布跳变
  （如 (0,1)→(1,2) 忘掉低速），可建议重叠区间。未纳入课程的维度保持基类值，
  在阶段表里说明。
