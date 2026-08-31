# lizard_migration

26 关节蜥蜴机器人（72 kg，16 腿关节 + 10 脊柱关节）Isaac Lab 强化学习
训练 + 评测 + 版本管理包。内容：

- `lizard_exp/` — 任务包（gym 注册、env cfg、参数版本 versions/vN、
  Blender 资产管线、工具脚本）。入口文档：
  - `lizard_exp/FAMILY.md` — 家族总文档（任务表 / 版本历史 / 代码地图）
  - `lizard_exp/MIGRATION.md` — 移植清单（新机器 5 步摆位）
  - `lizard_exp/PLAN.md` — 训练计划与挂账
- `ablation_harness/` — 评测系统（固定地形套件、nominal/robust 双模式、
  版本化协议 Locomotion-Eval-v1、消融调度器）

## 环境要求（自备）

本仓**不含 Isaac Lab**。自行安装：

1. Isaac Lab 源码树（本包基于 Isaac Lab 3.x manager-based 框架开发）
2. Python venv（`isaaclab` / `isaaclab_tasks` / `rsl_rl` / `gymnasium` 等）
3. 按 `lizard_exp/MIGRATION.md` 执行 5 步移植（.pth、fork shim、
   play.py 补丁），然后即可训练：

```bat
python scripts\reinforcement_learning\rsl_rl\train.py --task Lizard-Rough-v1 --max_iterations 4000 --seed 42
```

## 原机布局说明

原开发机上本包真身位于 `E:\lizard_migration`（本仓），Isaac Lab 树内
`E:\IsaacLab\lizard_exp`、`E:\IsaacLab\ablation_harness` 是指向本仓的
目录 junction——venv 的 `.pth`、fork shim 全部经由 junction 工作，
路径不变。新机器无需 junction，直接按 MIGRATION.md 摆位即可。
