# lizard_migration

26 关节蜥蜴机器人（72 kg，16 腿关节 + 10 脊柱关节）Isaac Lab 强化学习
训练 + 评测 + 版本管理包。内容：

> **文件逐个说明见 [FILEMAP.md](FILEMAP.md)（新协作者/下一个 AI 必读）**

- `rl_exp/` — 任务包（gym 注册、env cfg、参数版本 versions/lizard/vN、
  Blender 资产管线、工具脚本）。入口文档：
  - `rl_exp/FAMILY.md` — 家族总文档（任务表 / 版本历史 / obs 布局）
  - `rl_exp/PLAN.md` — 训练计划与挂账
- `ablation_harness/` — 评测系统（固定地形套件、nominal/robust 双模式、
  版本化协议 Locomotion-Eval-v1、消融调度器）
- `.codemaker/skills/tool/` — 4 份 AI 辅助开发 skill（isaaclab-task-creator /
  isaaclab-asset-pipeline / isaaclab-eval-harness / git-auto-sync），
  方法论与项目约定；新机器接线方式见下文"AI 开发环境"节

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

```bat
git clone <本仓> <REPO>        :: 例 E:\lizard_migration
```

**1. venv .pth**（`import rl_exp` 全局可达；文件内容 = **git 仓目录 `<REPO>`**
一行，不是 `<ROOT>`；`env_isaaclab` 只是本仓示例 venv 名，路径跟着改即可）：

```bat
echo <REPO>> <ROOT>\env_isaaclab\Lib\site-packages\rl_exp.pth
```

**2. fork shim**（`<ROOT>` 源码树唯一常驻文件：`import isaaclab_tasks` 时
自动注册全部 lizard 任务；现成副本在 `<REPO>\rl_exp\fork_patches\`）：

```bat
copy <REPO>\rl_exp\fork_patches\config_lizard___init__.py ^
  <ROOT>\source\isaaclab_tasks\isaaclab_tasks\manager_based\locomotion\velocity\config\lizard\__init__.py
```

**3. play.py 键盘遥控补丁**（可选，仅遥控回放需要；含键盘接线 + 命令直写
回退，`fork_patches\play_keyboard.patch` 即完整差异，手工版本见补丁内容）：

```bat
git -C <ROOT> apply <REPO>\rl_exp\fork_patches\play_keyboard.patch
```

**4. harness 摆位（过渡期）**：`ablation_harness` 的 `_ISAAC_ROOT` 仍按
"从 `<ROOT>` 调用"推导——原机保留 junction：

```bat
mklink /J <ROOT>\ablation_harness <REPO>\ablation_harness
```

（Phase G3 `_ISAAC_ROOT` 参数化落地后此步取消，见
`rl_exp\versions\lizard\v3\PLAN.md` §7.5。）

**5. 验证链**（全部通过 = 摆位成功）：

```bat
cd /d <ROOT>
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
mklink /J <ROOT>\.codemaker\skills\tool\git-auto-sync <ROOT>\lizard_migration\.codemaker\skills\tool\git-auto-sync
:: 其余三份 isaaclab-* skill 同法；或直接 copy。不接不影响训练与评测
```

## 原机布局说明

原开发机上本包真身位于 `E:\lizard_migration`（本仓），Isaac Lab 树内
`E:\IsaacLab\rl_exp`、`E:\IsaacLab\ablation_harness` 是指向本仓的
目录 junction——venv 的 `.pth`、fork shim 全部经由 junction 工作，
路径不变。新机器无需 junction，按上文步骤摆位即可。
