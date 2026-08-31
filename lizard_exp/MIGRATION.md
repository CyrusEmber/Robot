# Lizard 项目移植清单（Migration Kit）

> 打包: 2026-08-28 · 包含 `lizard_exp\`（全项目自包含）+ `ablation_harness\`（评测系统）
> 移植前先读本文档全文，路径层级是硬约束。

## 包内容

| 项 | 作用 |
|---|---|
| `lizard_exp\` | 参数 SSOT（lizard_params.yaml）/ versions 冻结版 / 任务包 tasks\ / 资产（URDF+meshes+USD）/ Blender 管线（含 `blender\lizard_stance.blend` 站姿 SSOT）/ 工具脚本 / FAMILY.md / PLAN.md / fork_patches\ |
| `ablation_harness\` | 消融评测系统：eval.py / run_ablation.py / 协议 / 地形套件 / 组件 / 指标库 |
| `.codemaker\skills\tool\` | 4 份 AI 辅助开发 skill（task-creator / asset-pipeline / eval-harness / git-auto-sync），方法论与项目约定 |

## 目标环境前提

- Isaac Lab 3.0 fork（同源版本）+ venv（`env_isaaclab\`）
- GPU + PhysX（训练）；Blender 仅改站姿时需要
- 后续详见：`lizard_exp\FAMILY.md`（家族文档）、`lizard_exp\PLAN.md`（训练计划/挂账）

## 移植步骤（按序执行）

以下 `<ROOT>` 指 IsaacLab fork 根目录（例 `E:\IsaacLab`）。

**1. 拷贝两个目录到 fork 根下（必须同名同层级——cfg 内路径计算依赖此结构）**

```bat
xcopy lizard_exp <ROOT>\lizard_exp\ /E /I
xcopy ablation_harness <ROOT>\ablation_harness\ /E /I
```

**2. 安装 fork shim（fork 源码树唯一占用之一）**

```bat
copy <ROOT>\lizard_exp\fork_patches\config_lizard___init__.py ^
  <ROOT>\source\isaaclab_tasks\isaaclab_tasks\manager_based\locomotion\velocity\config\lizard\__init__.py
```

**3. venv .pth（`import lizard_exp` 全局可达）**

```bat
echo %CD%> <ROOT>\env_isaaclab\Lib\site-packages\lizard_exp.pth
```

（在 `<ROOT>` 目录下执行；文件内容必须是 fork 根的绝对路径一行。）

**4. play.py 键盘遥控补丁（可选，仅遥控回放需要）**

`<ROOT>\scripts\reinforcement_learning\rsl_rl\play.py` 中找到：

```python
base_env.unwrapped.set_command(command)
```

替换为回退版：

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

**5. 验证链（全部通过 = 移植成功）**

```bat
cd /d <ROOT>

:: 预期: OBS_SHAPE (2, 266) / ACTION_DIM 26 / MASS_SUM ≈ 72
python lizard_exp\teacher_smoke.py --headless

:: 预期: JOINT_COUNT 26 / 四脚 force_z 合计 ≈ 700N
python lizard_exp\position_check.py --headless --rough

:: 预期: 跑分输出 + eval.json 落盘
python ablation_harness\eval.py --task Lizard-Rough-Play-v1 --mode nominal --seed 123 --headless
```

**6. skill 接线（可选，AI 辅助开发环境）**

```bat
:: codemaker 工作区在 fork 根时，把仓内 skill 目录接/拷到工作区技能目录
mklink /J <ROOT>\.codemaker\skills\tool\git-auto-sync <仓>\.codemaker\skills\tool\git-auto-sync
```

（其余三份 isaaclab-* skill 同法；或直接 copy。不接不影响训练与评测。）

## 关键机制（为什么必须做步骤 2/3）

- 任务包在 `lizard_exp\tasks\`，gym 注册 entry_point 指向 `lizard_exp.tasks.*`
  ——import 需要 fork 根在 sys.path（.pth 常驻 + shim 内置插入，双保险）
- shim 触发链：`import isaaclab_tasks` → `config\lizard\__init__.py` →
  `import lizard_exp.tasks` → 注册全部 10 个任务 id
- `versions\v1\` 是 **teacher 运行时依赖**（`TEACHER_PARAMS_VERSION="v1"` 读冻结副本），
  不是备份文档——漏拷 teacher 起不来

## 不在包里（按需另拷）

| 项 | 何时需要 |
|---|---|
| `logs\rsl_rl\` | resume 训练 / 评估已训 checkpoint / TB 曲线历史 |

## 常见坑

- 目录层级错位 → `_LIZARD_EXP_DIR`（`parents[1]`）与 shim（`parents[8]`）双双失配
- 忘 .pth → 工具脚本 `import lizard_exp.tasks` 直接 ModuleNotFoundError
- fork 里残留旧版 `config\lizard\*.py`（非 shim）→ 注册表被旧路径覆盖，务必只留 shim
