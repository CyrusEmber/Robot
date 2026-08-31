# lizard_migration

26 关节蜥蜴机器人（72 kg，16 腿关节 + 10 脊柱关节）Isaac Lab 强化学习
训练 + 评测 + 版本管理包。内容：

> **文件逐个说明见 [FILEMAP.md](FILEMAP.md)（新协作者/下一个 AI 必读）**

- `lizard_exp/` — 任务包（gym 注册、env cfg、参数版本 versions/vN、
  Blender 资产管线、工具脚本）。入口文档：
  - `lizard_exp/FAMILY.md` — 家族总文档（任务表 / 版本历史 / obs 布局 / 代码地图）
  - `lizard_exp/PLAN.md` — 训练计划与挂账
- `ablation_harness/` — 评测系统（固定地形套件、nominal/robust 双模式、
  版本化协议 Locomotion-Eval-v1、消融调度器）
- `.codemaker/skills/tool/` — 4 份 AI 辅助开发 skill（isaaclab-task-creator /
  isaaclab-asset-pipeline / isaaclab-eval-harness / git-auto-sync），
  方法论与项目约定；新机器接线方式见下文"AI 开发环境"节

## 环境要求（自备）

本仓**不含 Isaac Lab**。自行安装 Isaac Lab 源码树（3.x manager-based 框架）
与 Python venv（`isaaclab` / `isaaclab_tasks` / `rsl_rl` / `gymnasium` 等），
然后把本仓两个目录放进 IsaacLab 根（`<ROOT>`）下同名同层级：

```bat
git clone <本仓> <ROOT>\lizard_migration
xcopy <ROOT>\lizard_migration\lizard_exp      <ROOT>\lizard_exp\ /E /I
xcopy <ROOT>\lizard_migration\ablation_harness <ROOT>\ablation_harness\ /E /I
```

**1. venv .pth**（`import lizard_exp` 全局可达；在 `<ROOT>` 下执行，
文件内容 = `<ROOT>` 绝对路径一行）：

```bat
echo %CD%> <ROOT>\env_isaaclab\Lib\site-packages\lizard_exp.pth
```

**2. fork shim**（IsaacLab 源码树唯一占用之一：`import isaaclab_tasks` 时
自动注册全部 lizard 任务；现成副本在 `lizard_exp\fork_patches\`）：

```bat
copy <ROOT>\lizard_exp\fork_patches\config_lizard___init__.py ^
  <ROOT>\source\isaaclab_tasks\isaaclab_tasks\manager_based\locomotion\velocity\config\lizard\__init__.py
```

**3. play.py 键盘遥控补丁**（可选，仅遥控回放需要）：
`<ROOT>\scripts\reinforcement_learning\rsl_rl\play.py` 中把
`base_env.unwrapped.set_command(command)` 替换为：

```python
if hasattr(base_env.unwrapped, "set_command"):
    base_env.unwrapped.set_command(command)
else:
    term = base_env.unwrapped.command_manager.get_term("base_velocity")
    cmd = command.to(term.vel_command_b.device)
    if cmd.dim() == 1:
        cmd = cmd.unsqueeze(0)
    term.vel_command_b[:] = cmd
```

**4. 验证链**（全部通过 = 摆位成功）：

```bat
cd /d <ROOT>
:: 预期: OBS_SHAPE (2, 308) / ACTION_DIM 26 / MASS_SUM ≈ 72
python lizard_exp\teacher_smoke.py --headless
:: 预期: JOINT_COUNT 26 / 四脚 force_z 合计 ≈ 700N
python lizard_exp\position_check.py --headless --rough
:: 预期: 跑分输出 + eval.json 落盘
python ablation_harness\eval.py --task Lizard-Rough-Play-v2 --mode nominal --seed 123 --headless
```

注意：`versions\v2\` 是 teacher 运行时依赖（冻结参数），不是备份文档——
漏拷 teacher 起不来。目录层级是硬约束（cfg 内 `parents[1]` 路径计算依赖）。

## 训练

```bat
python scripts\reinforcement_learning\rsl_rl\train.py --task Lizard-Rough-v2 --max_iterations 4000 --seed 42
```

历史版本复现：任务 id 常驻注册（如 `Lizard-Rough-v1` = v1 配方 obs 266），
机制见 `lizard_exp/FAMILY.md`。

## AI 开发环境（可选）

codemaker 工作区在 `<ROOT>` 时，把仓内 skill 目录接到工作区技能目录：

```bat
mklink /J <ROOT>\.codemaker\skills\tool\git-auto-sync <ROOT>\lizard_migration\.codemaker\skills\tool\git-auto-sync
:: 其余三份 isaaclab-* skill 同法；或直接 copy。不接不影响训练与评测
```

## 原机布局说明

原开发机上本包真身位于 `E:\lizard_migration`（本仓），Isaac Lab 树内
`E:\IsaacLab\lizard_exp`、`E:\IsaacLab\ablation_harness` 是指向本仓的
目录 junction——venv 的 `.pth`、fork shim 全部经由 junction 工作，
路径不变。新机器无需 junction，按上文步骤摆位即可。
