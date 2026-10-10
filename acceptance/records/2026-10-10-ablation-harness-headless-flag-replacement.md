# 评测台两处 `--headless` 透传改 `--viz none`（2026-10-10）

## 适用范围

本轮只做一件事：把 `ablation_harness/run_ablation.py` train / eval 两处透传的弃用旗标 `--headless`
改成 `--viz none`，并同步 README 与 skill 里的命令示例。**不训练、不起仿真、不改配方 / 资产 / 闸门 /
协议**。事项本体的判据与关闭动作见 `work/closed/2026/headless-flag-deprecation.md`。

`rl_exp/versions/**`（冻结目录）只读，未动——含 v3 `NOTES.md` 里带 `--headless` 的命令示例：那是当次
实跑记录，不是活文档，按冻结红线与"历史不改写"两条都不动。

## 验收条件

- ① 被调用 task 的**整条 cfg 继承链**是否声明 visualizer——只查本仓会得到假结论，必须走到框架基类；
- ② 该声明在配置解析后是否真的启用；
- ③ `--viz none` 在本仓这条调用链上是否与 `--headless` 等价；
- 终局判据：等价 ⇒ 改掉透传，两处命令里不再出现 `--headless`，且目标脚本接受新旗标、命令仍能起训。

## 结果

### ① 继承链：零声明

`Lizard2-Flat-v3` 的 env cfg 入口 = `rl_exp.tasks.recipe_tasks:Lizard2FlatV3EnvCfg`，
链条 `Lizard2FlatV3EnvCfg -> Lizard2WiringCfg -> LocomotionVelocityRoughEnvCfg -> ManagerBasedRLEnvCfg`。
本仓 `rl_exp/tasks/**` 零 `visualizer` 命中；框架侧唯一声明点是 `SimulationCfg.visualizer_cfgs` 的基类
默认值 `[]`（`E:\IsaacLab\source\isaaclab\isaaclab\sim\simulation_cfg.py:336`），
`velocity_env_cfg.py:348` 只写 `sim = SimulationCfg(physics=RoughPhysicsCfg())`。
全 `isaaclab_tasks` 里 `visualizer_cfgs` 只出现在 `sim_launcher.py` 的读取侧与框架自测。

### ② 解析后：不启用

离线构造该 cfg（走 gym registry 的 entry point，与 `check_cfg_lock.py` 同一条"构造类、不 make env"的
路径），实得 `sim.visualizer_cfgs == []`，`_compute_visualizer_intent(cfg)` =
`{'has_any_visualizers': False, 'has_kit_visualizer': False}`。

### ③ 三种旗标形态走真 launcher 解析

用 `AppLauncher.__new__` + `_resolve_visualizer_settings` / `_resolve_headless_settings`（框架自测
`test_kwarg_launch.py:126` 的同款手法，不需要 Kit），两半分别注入真 cfg intent（train 走
`launch_simulation`）与不注入（eval 直接 `AppLauncher(args_cli)`）：

| 调用链 | 旗标 | `_headless` | viz_explicit | disable_all | 弃用告警 |
|---|---|---|---|---|---|
| train.py（带 cfg intent） | 无（删掉透传的形态） | True | False | False | 0 |
| train.py | `--headless`（现状） | True | False | True | **1** |
| train.py | `--viz none`（采用） | True | True | True | 0 |
| eval.py（无 intent） | 无 | True | False | False | 0 |
| eval.py | `--headless` | True | False | True | **1** |
| eval.py | `--viz none` | True | True | True | 0 |

visualizer 集合三形态同为 `[]`：无旗标走 `cfg.visualizer_cfgs`（空列表）；两处强制形态由 `disable_all`
在 `SimulationContext._resolve_visualizer_cfgs` 开头直接短路返空（`simulation_context.py:549`）。
experience 文件与 `hide_ui` / `_render_viewport` / `_offscreen_render` 只依赖 `_headless` /
`_livestream` / `_video_enabled`（`app_launcher.py:986-992`、`:951`），三形态同值。
差别只有一条弃用告警（`app_launcher.py:825-829` 起的 warning 分支）。

### 采用形态：替换，不是删除

不删的原因是**依赖方向**：删掉后 headless 变成"cfg 未声明 visualizer"的推论，于是评测台的 headless
押在框架 cfg 链保持不含 visualizer 上——一棵本仓不拥有的树。将来某条配方为调试加一个
`KitVisualizerCfg`，扫参会中途弹 GUI（或挂在无显示机器上），且没有任何闸门会红。
`--viz none` 把这条保证留回本仓命令里，代价两个 token，也正是弃用提示自己指的替代写法。

### 落点与核对

- `ablation_harness/run_ablation.py:88` / `:122`：`--headless` → `--viz none`，各带一行理由注释。
  实建命令（把 `subprocess.run` 换成打印、不启动）train / eval 两半均只出现 `--viz none`。
- 目标脚本接受新旗标：`train.py --help` 与 `eval.py --task <id> --help` 都列出
  `--visualizer VISUALIZER, --viz VISUALIZER`（两半都经 `AppLauncher.add_app_launcher_args`）。
- 文档示例同步：`README.md`（评测示例、训练示例、以及"launcher 不转发旗标"那段）、skill
  `references/runtime_facts.md` 环境验证脚本节的导语。示例一律用**不带旗标的默认形态**，
  散文给出显式强制形态与场合——两者不同写会互相打脸。
- README 那段原文称"从 launcher 交棒会起 GUI"。该结论随框架改默认值已不成立：`launch_recipe.py`
  构造的是 `train.py --task <id>` + PASSTHROUGH（不含任何 viz 旗标）⇒ 落回 cfg intent ⇒ 默认 headless。
  按现状改写，其 `ponytail:` 挂注（"补转发即可撤掉本注"）的前提消失，随之删除；理由记在本记录。

## 证据引用

- 事项（判据与终局）：`work/closed/2026/headless-flag-deprecation.md`
- 框架侧可复查路径：`app_launcher.py:488-496`（旗标定义与弃用文案）、`:811-894`（headless / visualizer
  解析）、`:85-119`（视觉化 CLI 选择写入 settings）、`sim_launcher.py:157-168`（cfg intent）、
  `simulation_context.py:518-530`（视觉化集合解析）、`velocity_env_cfg.py:348`、`simulation_cfg.py:336`
- 本记录里的两张表由一次性脚本产生，脚本未留仓（读数照抄在上）；**本轮不新增闸门**——这是弃用告警的
  旗标/文档漂移，不是一次真实失败，按 `rl_exp/tools/verify/OFFLINE_CHECKS.md` §4 没有准入理由。
- `rl_exp\tools\verify\run_offline_checks.bat`：本轮改动后全量离线闸门 **37/37 绿**（55.3s），含
  `check_work_docs`（73 项形状 + 落点/证据存在性）、`check_cfg_lock`（golden 未动）、
  `framework_pin_check`、`check_recipe_registry`

## 未覆盖边界

- **未起仿真、未起训**：观测止于配置解析与命令构造（离线）。`close_when` 里"带与不带各起一次同 task
  训练命令、比对启动日志"那半没有做——判据落在 ① 的继承链读数上（用户 2026-10-10 决定只做离线核对）。
  因此本记录**不能**证明"命令仍能起训"（那需要真跑），只能证明命令形态与旗标契约正确。
- 本仓其它仍教 `--headless` 的地方不在本轮：`rl_exp/tools/verify/cstate_observer.py:20`（docstring 里的
  训练命令示例）、`rl_exp/tools/verify/lifecycle_entry_run.py:298`（真透传给 train.py；该文件当时带着
  另一会话未提交的 WIP，未动）、各 diagnose / verify 脚本**自己**的 `--headless` CLI 旗标。要收须另立
  事项，逐处判"脚本自己的 CLI"还是"透传到训练器"。
- 弃用的 `--headless` 在 IsaacLab 侧何时移除不在本仓可控范围；本仓只是不再使用它。
- launcher（`rl_exp\tools\launch_recipe.py`）的 PASSTHROUGH 仍不含 viz 类旗标：在"默认 headless"下
  这不再是缺陷（它构造的命令与手打命令同形），故未补转发；若将来需要"从 launcher 也能显式强制"，
  那是新需求，另立事项。
