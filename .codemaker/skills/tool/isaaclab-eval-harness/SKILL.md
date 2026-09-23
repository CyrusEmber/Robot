---
name: isaaclab-eval-harness
description: >
  在机器人仓（<REPO>，本机 E:\Robot）的 ablation_harness 中做 locomotion 消融实验与统一评测。
  当用户提到"ablation/消融"、"对比实验"、"统一 eval"、"评测/评估/跑分 policy"、
  "eval protocol/评测协议"、"Locomotion-Eval"、"固定 seed 评估"、"checkpoint 评估"、
  "success rate / fall rate / velocity tracking / energy / terrain completion"、
  "recovery time/恢复时间"、"recovery push"、"fixed terrain suite/固定地形套件"、
  "nominal / robust eval"、"热插拔组件对比（CPG / terrain encoder / teacher-student / multi-expert）"、
  "跑消融"、"run_ablation/实验调度"等需求时，务必使用此 skill。
---

# IsaacLab Eval Harness（消融与统一评测）

评测/消融代码在 `<REPO>\ablation_harness\`（真身就在本仓，IsaacLab 树内不放副本、
不挂 junction）。机器本地路径（IsaacLab 源码树、venv 解释器）登记在仓根 `paths.yaml`，
唯一读者 `ablation_harness\host_paths.py`；换机器只改这一个文件，自检
`python ablation_harness\host_paths.py --check`。

**协议唯一真源是 `ablation_harness\protocols\locomotion_eval_vN.yaml`**，
本 skill 只述要点、不复制协议数值 —— 复制处即漂移处。改协议/指标口径前先读"版本纪律"。

## 核心理念

1. **协议是数据、具名、冻结**：`Locomotion-Eval-vN` = 一个 yaml。语义改动 → 新建 vN+1；
   旧结果永远带旧协议标签，**跨版本不比**
2. **训练诊断 ≠ 模型性能**：terrain curriculum level 只是训练诊断；固定地形套件的
   completion 才是模型性能指标
3. **双模式**：Nominal（全 DR 关 → 理论上限）/ Robust（固定 seed DR + recovery push
   → 真实水平 + 恢复力）
4. **组件复用 + 数据驱动**：命令时间线在协议 yaml 只写一处；command_player 按它发命令、
   metrics 按它自动切窗 —— 命令脚本与指标窗口永不分家

## 目录结构

```
<REPO>\ablation_harness\
├─ host_paths.py      # 机器本地路径唯一读者（isaac_root + venv python）
│                     # eval / run_ablation / 离线闸门 / pre-commit / framework_pin_check 共用
│                     # 优先级：CLI 参数 > 环境变量 > paths.yaml > 向上探测
├─ eval.py            # runner: task + checkpoint + protocol + mode → 跑分
├─ run_ablation.py    # spec yaml → train+eval 调度、断点续跑、汇总表
├─ protocols\         # 协议契约（当前版本冻结只读；语义改动 = 新建 vN）
├─ suites.py          # 地形套件（机器人尺度相关，单文件）：新机器人 = 新 suite 函数
│                     # + 注册进 eval.py 的 _SUITE_REGISTRY
├─ components\        # command_player / dr_controller / recovery（纯函数，通用）
│                     # dr_controller 的事件清单与 play_utils.py 互为镜像
│                     # ⇒ check_dr_parity.py --strict 机器看守
├─ metrics.py         # 指标纯函数库（按时间线自动切窗）
├─ plot_eval.py       # 可视化（读 eval.json，不起仿真）
└─ results\<protocol>\<run_id>\  # eval.json + summary.csv；--group 加一层 campaign 目录
```

harness 与机器人无关；**机器人相关只有 suites.py 一个文件 + 协议里的 suite 引用**。

## 指标口径（口径冻结在协议里，改口径 = 协议升版）

| 指标 | 口径 | 注意 |
|---|---|---|
| success_rate | **协议自算**（阈值在协议 metrics 段） | 不是命令 term 的 metrics —— 那是训练侧口径，阈值语义不同 |
| fall rate | **几何定义**（tilt / 贴地双判据 + 持续时间，阈值在协议） | **绝不用终止项** —— 终止项有盲区（base_contact 只查 base_link） |
| velocity tracking | 逐段 \|v−v_cmd\| MAE（按时间线自动切窗） | 每段独立报，难度天然分层 |
| energy | 隐式 PD 精确反解 τ=K(q*−q)−D·q̇，Σ\|τ·ω\|dt / 位移 | **不含 effort limit 饱和**：饱和期间高估；同口径跨 run 可比，绝对值注意。位移 clamp 下限 ⇒ 机器人不动时该值爆炸 |
| terrain completion | 每地形：位移/(命令速度×时长)，clip [0,1] + fall 标志 | 用梯度值不用二值 —— 二值藏住部分能力 |
| recovery time | 冲击后恢复达标时刻（阈值在协议） | 只算冲击时仍在第一局的 env；报 mean/median/p90 + spike + 冲击后 fall rate + measured_envs |
| 停车超调 | stop 段残余速度 | 命令服从性 |

**数值纪律**：协议口径 → 实现 → 输出数值要三级对表；跑分出来先做量级 sanity check
（物理上合理吗）；修口径后历史数据必须标失效。

**Provenance 纪律**：eval.json / summary.csv 每行自带 `git_rev_<robot>` +
`git_rev_isaaclab`（eval.py 自动采集，junction 布局下两仓分别定位；新机树内记 unknown）。
**无 rev 或 rev 对不上的数字不引用**；跨 rev 比较必须声明代码已变。

## 使用方案

**task 必须传 TRAIN id（非 `-Play`）**：harness 自己控 DR（nominal 关 / robust 固定 seed），
`-Play` 的 DR 预先全关，robust 会静默退化成 nominal（eval.py 已硬拦）。

```bat
:: 单点评估；--group 让一次 campaign 单独成目录 + 专属 summary.csv
python ablation_harness\eval.py --task <Robot>-<Task>-vN --checkpoint <model.pt> ^
  --protocol locomotion_eval_vN --mode nominal --seed 123 --group <标签>

:: 消融调度（spec yaml 内 N 个 run 顺序 train+eval，断点续跑）+ 汇总表
python ablation_harness\run_ablation.py --spec ablation_harness\specs\<name>.yaml
python ablation_harness\run_ablation.py --summarize [--group <标签>]
python ablation_harness\run_ablation.py --by-terrain --group <标签>   :: 逐地形长表 + pivot

:: 可视化产物一律不入库（gitignore 已挡 plots/ 与 report.html）：记录只有数据
:: （eval.json / summary.csv / terrains.csv / tb_scalars.csv），图与 HTML 秒级可再生
python ablation_harness\plot_eval.py --protocol locomotion_eval_vN --group <标签> ^
  --report <robot>_exp\versions\<family>\<vN>            :: 单文件 HTML 汇总报告
```

**录像看策略怎么走（相机，不是判分）**：`ablation_harness\video_matrix.py` —— 不同速度挡 ×
不同地形挡各录一段 mp4，用来"看"；**不产 verdict、不写 `results/<协议>/`**，其位移数字只作
自查、不得引用进验收表。相机默认跟随机器人（`--no-follow` 才是固定世界点，固定机位下高速
机器人几秒出画）；产物落 `ablation_harness\videos\`（gitignore）。

## 组件热插拔（spec 的组织方式，**永远不动家族代码**）

三级入口，从轻到重：

1. **hydra override 字符串**（train.py 透传，纯参数/事件开关）
2. **新任务 id**（结构变更：换 ActionsCfg / ObservationsCfg）——新建小 cfg + gym.register，
   spec 里 `task:` 换新 id
3. **agent cfg 覆盖**（换网络：teacher-student / multi-expert）

spec 字段：tag / task / seed / max_iterations / eval_checkpoints / eval_modes /
eval_seed / overrides。**tag 不可互为后缀**（调度器按后缀匹配 log 目录）。

## 版本纪律（可比性优先）

- `protocols\*.yaml` 落库即冻结、**只读**；语义变（时间线/阈值/地形/DR 定义/指标口径/
  采样帧）→ 新建 vN 文件
- 加新指标也算升版 —— 旧结果列里没这个指标
- results 与 summary.csv 都带 protocol 列；查询/对比永远按协议版本过滤

## 实验设计纪律

- **多 checkpoint 比较**：固定单点会误杀慢收敛方案。**趋势判断要 ≥5 点**（点太少会把抖动
  带读成趋势）
- **seed 策略**：筛查 1 seed，结论性对照 ≥3 seed（locomotion 跨 seed 方差常见 ±0.1）
- nominal 保留 reset 扰动（关节缩放 + 出生位置/速度随机）—— spawn 条件是 reset 协议
  一部分，两种模式一致

## 实现要点（已知坑，直接用）

- **本 fork data 属性返回 ProxyArray**：取张量走 `.torch`，快照用 `.torch.clone()`；
  传感器数据同理
- **suite 列分配（正确性关键）**：`TerrainGeneratorCfg(curriculum=True)` + 等比例
  sub-terrain → 按累计比例**确定性**分配，列 j 恰好 = 第 j 种地形（dict 插入序）。
  随机模式逐格采样会漏类型，**suite 绝不能用**；再叠 `difficulty_range=(1.0,1.0)` +
  单值参数范围双锁，seed 钉死实现
- **目录键用协议文件名**；协议显示名只在 JSON/CSV 元数据里。`--group` 再套一层 campaign
  目录，**行只落该组的 summary.csv**；summarize 缺省汇总协议根 + 各组
- **命令注入**：直写 `term.vel_command_b`，并关 `heading_command` / resample
  （`resampling_time_range=(1e9,1e9)`），否则命令不精确
- **robust DR** 直接复用任务自带 DR event cfg（本就是固定 distribution），eval seed 钉死；
  nominal 用 `enable_corruption=False` + DR 事件全置 None
- eval.py 不建新 gym 任务：`gym.spec(task).kwargs` 解析 env/agent cfg entry point →
  程序内换 `scene.terrain` 为 suite 网格 → `gym.make(task, cfg=改后cfg)`
- **逐地形指标**：1 行 × N 列，`num_envs = k × N`，
  `terrain_types = env_idx // (num_envs/num_cols)`
- **数据冻结纪律**：env 首次 done 后数据全无效（auto-reset 属新 episode），
  `valid = step <= first_done`；`terrain_types` 等 scene 张量必须在 `gym_env.close()` 前取
- **采样帧**：帧 = `step()` 之后、auto-reset 之前（reward/终止帧），故首 done 那行即终止帧；
  终止帧由 hook `mbenv._reset_idx` 在 reset 覆盖数据前抓下（`scene.update()` 与
  `_reset_idx()` 之间是唯一可读窗口，IsaacLab 无公开回调）。每次运行打印的
  `terminal frames captured=N` 是 hook 存活证据 —— **为 0 即私有 API 失配，fall 会偏低**
- **recovery push**：`write_root_velocity_to_sim` 叠加水平 kick；统计只算冲击时仍在第一局
  的 env（`first_done > push_step` 子集），`measured_envs` 记样本量
- **log 目录命名 `{timestamp}_{run_name}`**，调度器后缀匹配取最新；中断重跑会从头训
  （`--resume` 未透传，已知限制）；train.py 自动 dump params/env.yaml
- **断点续跑**由 `run_ablation.py` 判（eval.json 存在即跳过该 eval；训练看最终 checkpoint
  是否存在）—— 单独手跑 `eval.py` 不查旧结果，重跑即覆盖

## 状态

设计定稿 / 实现验证 / 版本历史与挂账 → `ablation_harness\HARNESS.md`（本子系统 SSOT）；
训练计划 / 家族版本 → 各家族 `PLAN.md` / `FAMILY.md`。
