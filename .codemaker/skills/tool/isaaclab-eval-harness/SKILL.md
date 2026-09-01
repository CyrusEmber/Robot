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
├─ suites.py              # 地形套件（机器人尺度相关，单文件）：lizard_suite_v1()；
│                         # 新机器人 = 新 suite 函数+名字表（照抄锁三件套：curriculum=True
│                         # 等比例列分配 / 单值难度 / seed）+ 注册进 eval.py 的 _SUITE_REGISTRY
├─ components\             # command_player / dr_controller / recovery（纯函数，通用）
│                          # 注：dr_controller 的 DR 事件清单与 rl_exp\tasks\play_utils.py
│                          # 互为同步镜像（PLAY 变体用同一份）——改一边即红：
│                          # check_dr_parity.py --strict 机器看守，别靠人记
├─ metrics.py              # 指标纯函数库（按时间线分段自动切窗，通用）
├─ plot_eval.py            # 评测可视化（读 eval.json → 趋势图 + 逐地形热力图，不起仿真）
├─ specs\example_baseline.yaml         # 消融 spec 示例
└─ results\<protocol>\<run_id>\eval.json + summary.csv
                           # 一次 campaign 可用 --group 单独成目录：
                           # results\<protocol>\<group>\<run_id>\ + 组内 summary.csv
                           # + terrains.csv（--by-terrain 反向生成：run × terrain 长表）
```

harness 与机器人无关；**机器人相关只有 suites.py 一个文件 + 协议里的 suite 引用**。

## 协议 v1 要点

**本 skill 不复制协议数值——复制处即漂移处**（曾有文档抄 266 维 obs 被 v2 打脸）。
全文即契约，30 秒读完：`protocols\locomotion_eval_v1.yaml`（命令时间线、robust push、
suite 布局、指标口径全在里面）。**v1 是 lizard 尺度实例**，新机器人可另起协议或在
同协议下换 suite——语义变了就要 vN。latency 注入未实现（PLAN 挂账），rob 记 N/A。

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

**数值纪律（energy 教训）**：协议口径 → 实现 → 输出数值要三级对表。energy 实现曾漏乘
dt（功率当能耗裸累加，虚高 ~50×，`energy_per_m_j=196155` 这种量级荒谬值没人拦）。
跑分出来先做量级 sanity check（物理上合理吗），修口径后历史数据必须标失效
（FILEMAP 历史包袱节记录了 2026-08-28 两行无效 energy）。

**Provenance 纪律**：eval.json/summary.csv 每行自带 `git_rev_lizard` +
`git_rev_isaaclab`（eval.py 自动采集，junction 布局下两仓分别定位；新机树内
lizard rev 记 unknown）。引用数字先看 rev——**无 rev 或 rev 对不上的数字不引用**；
比较跨 rev 的行必须声明代码已变。

## 使用方案

**task 必须传 TRAIN id（非 `-Play`）**：harness 自己控 DR（nominal 关 / robust 固定
seed 保住），`-Play` 的 DR 预先全关，robust 会静默退化成 nominal——eval.py 已硬拦。

```bat
:: 单点评估（nominal / robust）；--group 让一次 campaign 单独成目录 + 专属 summary.csv
python ablation_harness\eval.py --task Lizard-Rough-v2 --checkpoint <model.pt> ^
  --protocol locomotion_eval_v1 --mode nominal --seed 123 --group v1

:: 消融调度（spec yaml：N 个 run 顺序 train+eval，断点续跑；spec 顶层 group: 透传 --group）+ 汇总表
python ablation_harness\run_ablation.py --spec ablation_harness\specs\<name>.yaml
python ablation_harness\run_ablation.py --summarize
python ablation_harness\run_ablation.py --summarize --group v1
:: 逐地形：组内 terrains.csv（长表）+ 三张「地形 × ckpt」pivot
python ablation_harness\run_ablation.py --by-terrain --group v1
:: 出图（纯读盘，不起仿真）；训练侧曲线用 rl_exp\tools\trainlog\plot_tb.py
python ablation_harness\plot_eval.py --protocol locomotion_eval_v1 --group v1 ^
  --out_dir rl_exp\versions\lizard\v1\plots --prefix v1_eval_
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

- **多 checkpoint 比较**（如 1k/2k/4k）：固定单点比较会误杀慢收敛方案（CPG 典型起步慢）。
  **趋势判断要 ≥5 点**：teacher v1 实证——3 点（4k/8k/14k）读出"fall 随迭代上升"，补到
  6 点（2k~14k）发现是 .15~.33 的抖动带，结论撤回（`versions\lizard\v1\NOTES.md` A2）
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
  元数据里。`--group <name>` 再套一层 campaign 目录，**行只落该组的 `summary.csv`**
  （协议根表不混装）；summarize 缺省汇总"协议根 + 各组"，`--summarize --group v1` 只看一组
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
- 断点续跑：由 `run_ablation.py` 判（eval.json 存在即跳过该 eval；训练以最终 checkpoint
  存在性判定）——单独手跑 `eval.py` 不查旧结果，重跑即覆盖

## 状态

- 设计定稿 2026-08-28（四轮收敛：suite → 双模式 → recovery push → 协议版本化）
- **实现完成并验证**：全链路冒烟通过（零动作策略 nominal+robust 双模式，指标自洽：
  stop 段 success=1.0、MAE 段段≈命令速度、kick 后 fall 检测生效）；**确定性实证**：
  同 seed 多次运行数值逐位一致（success 0.248 / fall 0.083 / recovery 13.15s）
- **代码审查完成**（三轮修复归档于 git 历史：b6098c9 / f22f43f）：修复 2 🚨（glob 前缀 bug /
  训练失败杀 sweep）+ 3 ⚠️（协议默认单一真源 / recovery 子集 / 死参数）；
  configclass 单例疑点源码验证排除；dump_tb 实测 39237 点与历史吻合
- 待首个真实 checkpoint（teacher 训练完成后）跑基线数据 → **已了结 2026-09-01**：
  teacher v1 六行基线（3 ckpt × 双模式）在 `results/locomotion_eval_v1/v1/`，
  判读见 `rl_exp\versions\lizard\v1\NOTES.md`
- 相关 SSOT：`rl_exp\PLAN.md`（训练计划/挂账）、`rl_exp\FAMILY.md`（家族版本管理）
