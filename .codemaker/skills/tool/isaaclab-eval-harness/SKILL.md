---
name: isaaclab-eval-harness
description: >
  在 E:\IsaacLab 中做 locomotion 消融实验与统一评测（ablation harness）。
  当用户提到"ablation/消融"、"对比实验"、"统一 eval"、"评测/评估/跑分 policy"、
  "eval protocol/评测协议"、"Locomotion-Eval"、"固定 seed 评估"、"checkpoint 评估"、
  "success rate / fall rate / velocity tracking / energy / terrain completion"、
  "recovery time/恢复时间"、"recovery push"、"fixed terrain suite/固定地形套件"、
  "nominal / robust eval"、"热插拔组件对比（CPG / terrain encoder / teacher-student / multi-expert）"、
  "跑消融"、"run_ablation/实验调度"等需求时，务必使用此 skill。
  覆盖：版本化评测协议（Locomotion-Eval-vN）、固定地形套件、nominal/robust 双模式评估、
  指标计算口径、实验调度与结果汇总。
---

# IsaacLab Eval Harness（消融与统一评测）

评测/消融代码在 `E:\IsaacLab\ablation_harness\`。本 skill 是设计契约与使用手册；
**协议唯一真源是 `ablation_harness\protocols\locomotion_eval_v1.yaml`，本 skill 只述要点
不复制全文（防漂移）**。改协议/指标口径前先读"版本纪律"节。

## 核心理念（为什么这么设计）

1. **协议是数据、具名、冻结**：`Locomotion-Eval-v1` = 一个 yaml 文件。语义改动 → 新建
   v2 文件；旧结果永远带旧协议标签，跨版本不比。
2. **训练诊断 ≠ 模型性能**：terrain curriculum level 只是训练诊断（TB 读终值进汇总表）；
   固定地形套件的 completion 才是模型性能指标。
3. **双模式**：Nominal（全 DR 关 → "理论能力多强"）/ Robust（固定 seed DR + recovery push
   → "真实水平 + 恢复力"）。
4. **组件复用 + 数据驱动**：命令时间线在协议 yaml 只写一处；command_player 按它发命令，
   metrics 按它自动切窗——命令脚本与指标窗口**永不分家**。

## 目录结构

```
E:\IsaacLab\ablation_harness\
├─ eval.py                 # runner: task + checkpoint + protocol + mode → 跑分
├─ run_ablation.py         # spec yaml → train+eval 调度, 断点续跑, 汇总表
├─ protocols\locomotion_eval_v1.yaml   # 协议契约（冻结只读，改动 = 新建 vN）
├─ suites\                # 地形套件（机器人尺度相关）：lizard_suite_v1.py；
│                         # 新机器人 = 新 suite 文件（照抄锁三件套：curriculum=True 等比例
│                         # 列分配 / 单值难度 / seed）+ 注册进 eval.py 的 _SUITE_REGISTRY
├─ components\             # command_player / dr_controller / recovery（纯函数，通用）
├─ metrics.py              # 指标纯函数库（按时间线分段自动切窗，通用）
├─ specs\example_baseline.yaml         # 消融 spec 示例
└─ results\<protocol>\<run_id>\eval.json + summary.csv
```

harness 与机器人无关；**机器人相关只有 suites\ 一个文件 + 协议里的 suite 引用**。

## 协议 v1 要点（全文见 protocols\locomotion_eval_v1.yaml；**v1 是 lizard 尺度实例**，
新机器人可另起协议或在同协议下换 suite——语义变了就要 vN）

- **命令时间线**（30s，6 段）：0-5s vx=0.5 → 5-10s vx=1.0 → 10-15s vx=1.5 →
  15-20s vx=1.0 wz=+0.5 → 20-25s vx=1.0 wz=-0.5 → 25-30s stop（停车超调段）
- **robust**：固定 seed DR + recovery push（t=12s，kick 4 m/s，方向 per-env 由 seed 定）
- **suite**：lizard_suite_v1，9 地形（flat / 坡5°/10° / 台阶10/20cm / 粗糙A/B / 沟20/40cm），
  1 行 × 9 列，每列一种地形，envs_per_terrain 8
- **latency**：v1 不支持（延迟注入未实现），rob N/A

## 指标定义（口径冻结在协议里，改口径 = 协议升版）

| 指标 | 口径 | 注意 |
|---|---|---|
| success_rate | **协议自算**：单步 \|v−cmd\|<0.5 m/s 且 \|wz−cmd_wz\|<0.4 rad/s（阈值在协议 metrics 段） | 不是命令 term 的 metrics——那是训练侧口径，阈值语义不同 |
| fall rate | **几何定义**：tilt > 40° 或 base 距地形高度 < 初始站高 60%，持续 0.5s | **绝不用终止项**——趴窝事故证明终止项有盲区（base_contact 只查 base_link） |
| velocity tracking | 逐段 \|v−v_cmd\| MAE（按时间线自动切窗） | 每段独立报，难度天然分层 |
| energy | 隐式 PD 精确反解 τ=K(q*−q)−D·q̇，Σ\|τ·ω\|dt / 位移 | **不含 effort limit 饱和**：饱和期间高估；同口径跨 run 对比有效，绝对值注意。不动机器人时该值无意义（位移 clamp 0.1m → 爆炸） |
| terrain completion | 每地形：位移/(命令速度×时长)，clip [0,1] + fall 标志 | 梯度值，不用二值——二值藏住部分能力 |
| recovery time | 冲击后 \|v−v_cmd\| < 0.25 m/s 持续 0.5s 的时刻 | 只算冲击时仍在第一局的 env；报 mean/median/p90 + spike + 冲击后 fall rate + measured_envs |
| 停车超调 | stop 段残余速度 | 命令服从性 |

## 使用方案

```bat
:: 单点评估（nominal / robust）
python ablation_harness\eval.py --task Lizard-Rough-v0 --checkpoint <model.pt> ^
  --protocol locomotion_eval_v1 --mode nominal --seed 123

:: 消融调度（spec yaml：N 个 run 顺序 train+eval，断点续跑）+ 汇总表
python ablation_harness\run_ablation.py --spec ablation_harness\specs\<name>.yaml
python ablation_harness\run_ablation.py --summarize
```

## 组件热插拔（spec 的组织方式，**永远不动家族代码**）

三级入口，从轻到重：

1. **hydra override 字符串**（train.py 透传，纯参数/事件开关）：
   `overrides: ["env_cfg.events.push_robot=null"]`
2. **新任务 id**（结构变更：CPG 换 ActionsCfg、obs ablation 换 ObservationsCfg）——
   新建小 cfg 文件 + gym.register，spec 里 `task:` 换成新 id
3. **agent cfg 覆盖**（换网络：teacher-student / multi-expert）

spec 示例（`specs\example_baseline.yaml`）：tag/task/seed/max_iterations/
eval_checkpoints/eval_modes/eval_seed/overrides。**tag 不可互为后缀**（调度器按
`endswith("_{tag}")` 匹配 log 目录）。

## 版本纪律（可比性优先）

- `protocols\*.yaml` 落库即冻结，**只读**；语义变（时间线/阈值/地形/DR 定义/指标口径）
  → 新建 vN 文件
- 加新指标也算升版——旧结果列里没这个指标，混在一起就是脏数据
- results 与 summary.csv 都带 protocol 列；查询/对比永远按协议版本过滤

## 实验设计纪律

- **多 checkpoint 比较**（如 1k/2k/4k）：固定单点比较会误杀慢收敛方案（CPG 典型起步慢）
- **seed 策略**：筛查 1 seed，结论性对照 ≥3 seed（locomotion 跨 seed 方差 ±0.1 常见）
- nominal 保留 reset 扰动（关节 0.5-1.5 缩放 + 出生位置/速度随机）——spawn 条件是
  reset 协议一部分，两种模式一致（协议 yaml 注释声明）

## 实现要点（已知坑，直接用）

- **本 fork data 属性返回 ProxyArray**：`robot.data.root_lin_vel_b.torch` 取张量，
  快照 `.torch.clone()`；传感器数据同理
- **suite 列分配机制（正确性关键）**：`TerrainGeneratorCfg(curriculum=True)` + 等比例
  sub-terrain → 按累计比例**确定性**分配，列 j 恰好 = 第 j 种地形（dict 插入序）。
  随机模式（curriculum=False）逐格采样会漏类型——suite 绝不能用。再叠
  `difficulty_range=(1.0,1.0)` + 单值参数范围（`slope_range=(θ,θ)` 等）双锁，seed 钉死实现
- **目录键用协议文件名**（`results/locomotion_eval_v1/`）；协议显示名只在 JSON/CSV
  元数据里。summarize 读 `results/<protocol>/summary.csv`（协议级单文件）
- 命令注入：直写 `term.vel_command_b`（play.py 键盘回退同款），并关 `heading_command`/
  resample（`resampling_time_range=(1e9,1e9)`），否则命令不精确
- robust DR：直接复用任务自带 DR event cfg（本来就是"固定 distribution"），eval seed
  钉死实现值；nominal 用 `enable_corruption=False` + DR 事件全置 None
- eval.py 不建新 gym 任务：`gym.spec(task).kwargs` 解析 env/agent cfg entry point →
  程序内换 `scene.terrain` 为 suite 网格 → `gym.make(task, cfg=改后cfg)`
- 逐地形指标：1 行 × N 列，`num_envs = k × N`，`terrain_types = env_idx // (num_envs/num_cols)`
- **数据冻结纪律**：env 首次 done 后数据全无效（auto-reset 属新 episode），
  `valid = step <= first_done`；`terrain_types` 等 scene 张量必须在 `gym_env.close()` 前取
- recovery push：`write_root_velocity_to_sim` 叠加水平 kick；**统计只算冲击时仍在第一局的
  env**（`first_done > push_step` 子集），`measured_envs` 记样本量
- **log 目录命名 `{timestamp}_{run_name}`**（train.py）——调度器后缀匹配取最新；
  中断重跑会从头训（--resume 未透传，已知限制）；train.py 自动 dump params/env.yaml
- 断点续跑：eval.json 存在即跳过；训练以最终 checkpoint 存在性判定

## 状态

- 设计定稿 2026-08-28（四轮收敛：suite → 双模式 → recovery push → 协议版本化）
- **实现完成并验证**：全链路冒烟通过（零动作策略 nominal+robust 双模式，指标自洽：
  stop 段 success=1.0、MAE 段段≈命令速度、kick 后 fall 检测生效）；**确定性实证**：
  同 seed 多次运行数值逐位一致（success 0.248 / fall 0.083 / recovery 13.15s）
- **代码审查完成**（review_report_isaac_session.html）：修复 2 🚨（glob 前缀 bug /
  训练失败杀 sweep）+ 3 ⚠️（协议默认单一真源 / recovery 子集 / 死参数）；
  configclass 单例疑点源码验证排除；dump_tb 实测 39237 点与历史吻合
- 待首个真实 checkpoint（teacher 训练完成后）跑基线数据
- 相关 SSOT：`lizard_exp\PLAN.md`（训练计划/挂账）、`lizard_exp\FAMILY.md`（家族版本管理）
