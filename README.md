# robot

26 关节蜥蜴机器人（72 kg，16 腿关节 + 10 脊柱关节）Isaac Lab 强化学习
训练 + 评测 + 版本管理包。内容：

> **文件逐个说明见 [FILEMAP.md](FILEMAP.md)（新协作者/下一个 AI 必读）**

- `rl_exp/` — 任务包（gym 注册、env cfg、参数版本 versions/lizard/vN、
  Blender 资产管线、工具脚本）。入口文档（家族之家 `rl_exp/versions/lizard/`）：
  - `rl_exp/versions/lizard/FAMILY.md` — 家族总文档（任务表 / 版本历史 / obs 布局）
  - `rl_exp/versions/lizard/PLAN.md` — 训练计划与挂账
- `ablation_harness/` — 评测系统（固定地形套件、nominal/robust 双模式、
  版本化协议 Locomotion-Eval-v1、消融调度器）
- `.codemaker/skills/tool/` — 5 份 AI 辅助开发 skill（isaaclab-task-creator /
  isaaclab-asset-pipeline / isaaclab-eval-harness / isaaclab-train-probe /
  git-auto-sync），方法论与项目约定；新机器接线方式见下文"AI 开发环境"节

## 环境要求（自备）

本仓**不含 Isaac Lab**。自行安装 Isaac Lab 源码树（3.x manager-based 框架）
与 Python venv（`isaaclab` / `isaaclab_tasks` / `rsl_rl` / `gymnasium` 等）。
代码**不复制进 IsaacLab 根（`<ROOT>`）**：git 仓（`<REPO>`，位置随意）是唯一
代码家，`<ROOT>` 里常驻的只有 1 个注册 shim 文件（2026-09-01 布局迁移，
旧 xcopy/junction 摆位作废）。

> **已验证的 IsaacLab 版本：`28a37ce`（tag `perf-2026-06-24`，2026-08-31 全链
> 验证）。** 本栈依赖多处 IsaacLab 内部件（`cfg.func` 实例替换、
> `RayCaster.meshes` 注册表、live PD 增益读回、rsl_rl `resolve_callable`
> 点路径注册等），换版本先跑
> `rl_exp\tools\verify\framework_pin_check.py`。
>
> **升级触发**（满足其一才动 pin，"当前版本停止维护"本身不构成阻塞）：
> 安全公告影响本栈 / 需要上游新特性 / 上游内部件重构导致 pin_check 报警。
> **升级流程首步固定**：跑 `framework_pin_check.py` 记录断裂清单 → 逐项适配
> （本仓 fork shim 与 `fork_patches\` 只认已验证 SHA，随升级同步）→ 全链验证
> → 更新本行的 SHA 与日期。

```bat
git clone <本仓> <REPO>        :: 例 E:\robot
```

**一步到位（推荐）**：下面 5 步有现成脚本，幂等，可重复跑：

```bat
<REPO>\setup.bat <ROOT>
:: venv 名不是 env_isaaclab 时：第三个参数给出 venv 目录
<REPO>\setup.bat <ROOT> <ROOT>\<你的 venv>
```

它写 venv `.pth`、建目录并拷入 fork shim、**逐个应用 `fork_patches\*.patch`
（已打则跳过并写明）**、按本机生成 `paths.yaml`、接上 pre-commit。任一步失败都打
`[FAIL]` 并以非零码退出——**漏打补丁不会再静默失效**。脚本纯 ASCII（`.bat` 按控制台
代码页读，非 ASCII 注释会把解析带崩），只改 `.pth` / shim / 补丁 / `paths.yaml`。

以下是同样 5 步的手工版本（脚本失效、或想逐步确认时用）。

**1. venv .pth**（`import rl_exp` 全局可达；文件内容 = **git 仓目录 `<REPO>`**
一行，不是 `<ROOT>`；`env_isaaclab` 只是本仓示例 venv 名，路径跟着改即可）：

```bat
echo <REPO>> <ROOT>\env_isaaclab\Lib\site-packages\rl_exp.pth
```

**2. fork shim**（`<ROOT>` 源码树唯一常驻文件：`import isaaclab_tasks` 时
自动注册全部 lizard 任务；现成副本在 `<REPO>\rl_exp\fork_patches\`。**stock 树里
没有 `config\lizard\` 目录，要先建**——`import_packages` 用 `pkgutil` 自动发现带
`__init__.py` 的目录，父级 `config\__init__.py` 不用动）：

```bat
mkdir <ROOT>\source\isaaclab_tasks\isaaclab_tasks\manager_based\locomotion\velocity\config\lizard
copy <REPO>\rl_exp\fork_patches\config_lizard___init__.py ^
  <ROOT>\source\isaaclab_tasks\isaaclab_tasks\manager_based\locomotion\velocity\config\lizard\__init__.py
```

**3. 遥控回放（可选）**：键盘遥控两条路，按任务范围选。两条都要求
`--viz kit`（键盘是 Kit 窗口设备，没窗口收不到按键）和 `--real-time`
（按墙钟走，按键才落得进去）。键位：小键盘/方向键前后左右，`Z`/`X` 转向，`L` 清零。
**按住才动、松开即停**（设备是 press/release 增量配平，不会滑行）；Alt+Tab 失焦会丢
release、命令卡住不归零，按 `L` 兜底。按一次的量级在 `play_keyboard_task.KEY_SENSITIVITY`
（默认 x=3.0 m/s、y=0.4、yaw=1.0 rad/s；v8 训练范围 x(-1,3)、y(±0.5)、yaw(±1)——stock
`Se2KeyboardCfg` 默认 x 只有 0.8，相对上限太慢，故覆盖）。

**A. 仓内变体（推荐，不改 `<ROOT>`）**——覆盖有 `commands.base_velocity` 的
Lizard `-Play` 任务，`<ROOT>` 重装/换版本不失效：

```bat
<ROOT>\env_isaaclab\Scripts\python.exe <ROOT>\scripts\reinforcement_learning\rsl_rl\play.py ^
  --task Lizard-Rough-Play-v8-keyboard ^
  --external_callback rl_exp.tools.diagnose.play_keyboard_task.register ^
  --viz kit --real-time --num_envs 1
```

离线自检 `python -m rl_exp.tools.diagnose.play_keyboard_task`。

**B. play.py 补丁**（任意带 `base_velocity` 的任务通用，代价是随 `<ROOT>` 走、
重装要重打；`setup.bat` 第 3 步已自动处理，含"已打则跳过"）：

```bat
git -C <ROOT> apply <REPO>\rl_exp\fork_patches\play_keyboard.patch
```

两者同时开不冲突（写的是同一个键盘值，只是冗余）。区别在**怎么防覆盖**：
A 换掉命令 term（`_resample_command` 空操作）；B 保持 stock term，但在
`gym.make` **之前**关掉它的自主变更——`heading_command` / `rel_standing_envs` /
`rel_heading_envs` / `resampling_time_range`。B 漏掉这一步就是坏的：`env.step`
内的 `CommandManager.compute` 会在同一步把键盘命令覆盖回去（转向键全失效、
每 10 s 重采样），键盘输入活不过第一次 compute。

**4. 主机路径登记**（`<ROOT>` 与 venv python 的唯一真源。评测台
`eval.py`/`run_ablation.py`、离线闸门 `run_offline_checks.bat`、`hooks\pre-commit`
都只问 `ablation_harness\host_paths.py`，不再各自从调用路径猜——旧的
`<ROOT>\ablation_harness` junction 摆位因此作废）：

```bat
copy <REPO>\paths.example.yaml <REPO>\paths.yaml
:: 编辑 paths.yaml：isaac_root = <ROOT>，python = <ROOT> 的 venv 解释器
```

`paths.yaml` 是机器本地文件，不入库。解析优先级：命令行 > 环境变量
`RL_ISAAC_ROOT`/`RL_PYTHON` > `paths.yaml` > 向上探测 `source/isaaclab`。原机若还
挂着 junction，`rmdir <ROOT>\ablation_harness` 摘链接即可（**只准 rmdir**，递归
del 会穿透删真身）。

**5. 验证链**（全部通过 = 摆位成功）：

```bat
cd /d <REPO>
:: 主机路径是否登记成功（打印 isaac_root / python / 配置来源）
python ablation_harness\host_paths.py --check
:: 离线闸门（秒级，不起仿真）：框架 pin / DR parity / recovery 等价 / 课程单测
rl_exp\tools\verify\run_offline_checks.bat
:: 预期: OBS_SHAPE (2, 308) / ACTION_DIM 26 / MASS_SUM ≈ 72
python rl_exp\tools\verify\teacher_smoke.py --headless
:: 预期: JOINT_COUNT 26 / 四脚 force_z 合计 ≈ 700N
python rl_exp\tools\verify\position_check.py --headless --rough
:: 预期: 跑分输出 + eval.json 落盘（注意 TRAIN id，不是 -Play：
:: harness 自己控制 DR，Play 变体会让 robust 静默退化成 nominal）
python ablation_harness\eval.py --task Lizard-Rough-v2 --mode nominal --seed 123 --headless
```

**pre-commit 静态闸门**：`hooks\pre-commit` 随仓携带（staged 命中
`rl_exp\`/`ablation_harness\` 代码时自动跑 `check_dr_parity --strict` +
`check_obs_layout`，文档 commit 豁免）。首次 clone 后执行一次
`git config core.hooksPath hooks` 接线（本地配置不随仓走）；全套离线闸门
仍走 `run_offline_checks.bat`，hook 只是最后防线不是替代。

注意：`versions\lizard\v2\` 是 teacher 运行时依赖（冻结参数），不是备份文档——
漏拷 teacher 起不来。目录层级是硬约束（cfg 内 `parents[1]` 路径计算依赖）。

## 训练

```bat
python scripts\reinforcement_learning\rsl_rl\train.py --task Lizard-Rough-v2 --max_iterations 4000 --seed 42
```

历史版本复现：任务 id 常驻注册（如 `Lizard-Rough-v1` = v1 配方 obs 266），
机制见 `rl_exp/FAMILY.md`。

## AI 开发环境（可选）

codemaker 工作区在 `<ROOT>` 时，把仓内 skill 目录接到工作区技能目录：

```bat
mklink /J <ROOT>\.codemaker\skills\tool\git-auto-sync <REPO>\.codemaker\skills\tool\git-auto-sync
:: 其余三份 isaaclab-* skill 同法；或直接 copy。不接不影响训练与评测
```

## 原机布局说明

原开发机上本仓真身位于 `E:\robot`（2026-09-01 由 `lizard_migration` 更名），
venv `.pth` 直指该目录（Phase G1，rl_exp junction 已删）；仅
`E:\IsaacLab\ablation_harness` 仍是仓内 junction 的过渡摆位
（G3 `_ISAAC_ROOT` 参数化落地后取消，见步骤 4）。新机器无需任何
rl_exp junction，按上文步骤摆位即可。
