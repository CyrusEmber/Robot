 # v1 —— teacher 首跑配方（DR 收窄版）

- 目的/假设: teacher Phase 1 首次实际训练。v0 未跑即被取代：全量 DR 对
  尚未学会走路的 26 关节蜥蜴门槛过高（家族 run flat 实证 10000 iters 才走、
  rough 15000 iters 趴窝），首跑先收窄扰动验证"特权 + 锁脊柱 + 轻扰动"
  能否出步态。特权 obs + 轻扰动仍趴 → 激励逃生舱坐实；走起来 → 门槛是
  扰动/形态，v2 再逐档加回 DR
- 参数: 与 v0 逐字相同，仅 domain_randomization 段全部收窄（无一归零）：
  friction [0.4,1.2]/[0.3,1.0] → [0.7,1.0]/[0.6,0.9]；
  mass_scale [0.87,1.15] → [0.95,1.05]；mass_scale_limbs [0.7,1.43] → [0.9,1.11]；
  com ±0.05/±0.02 → ±0.02/±0.01；stiffness/damping_scale [0.8,1.2] → [0.9,1.1]；
  joint_friction_add [0,0.05] → [0,0.01]；joint_armature_add [0,0.02] → [0,0.005]；
  external_force [-40,40] → [-15,15]；external_torque [-5,5] → [-2,2]；
  push_velocity ±1.5/±1.5/±0.3 → ±0.5/±0.5/±0.1。
  不变：inertia_scale、reset_height_range、friction_num_buckets、
  奖励/动作/命令/仿真参数（命令仍为论文值 [-1,1]/[-0.5,0.5]/[-1,1]）
- 相对上版: v0 仅 DR 段收窄，其余零改动（纯参数变更）
- 训练命令:
  ```bat
  python scripts\reinforcement_learning\rsl_rl\train.py --task Lizard-Rough-v1 --max_iterations 4000 --seed 42
  ```
- log 目录: logs/rsl_rl/lizard_rough_teacher/
- 验收线（按本机 flat 实证 10000 iters + 特权 2~3x 加速估）:
  ~1000 iters 内 feet_air_time 持续 >0、base 位移；~3000-5000 慢速命令成型。
  1000 iters reward 仍平 + feet_air_time≈0 = 判死刑信号（配方问题，非迭代数）
- 训练实况（2026-09-01 回填）: 实际 14000 iters（非本文件原写的 4000），
  `--max_iterations 14000 --seed 42`，run = `logs/rsl_rl/lizard_rough_teacher/2026-08-31_11-12-20`
  （08-31 11:12 启动 → 09-01 13:04 落 final `model_13999.pt`）。
  ckpt obs 266 → 确认 v1 配方（env.yaml 无 v2 增量 term）
- 逐迭代曲线: 已导出 `tb_scalars.csv`（406000 点 / 29 tags）。
  关键读数（iteration: value）: mean_reward -2.47→1.53(1k)→4.73(4k)→7.49(8k)→8.09(12k)→7.12(14k)；
  track_lin_vel_xy_exp 0.63(4k)→0.72(14k)；terrain_levels 0.32→0.63（仅训练诊断）
- eval 结果（2026-09-01，协议 Locomotion-Eval-v1，seed 123，task `Lizard-Rough-v1`，
  **6 ckpt × 双模式 = 12 行**，campaign 文件夹 `ablation_harness\results\locomotion_eval_v1\v1\`
  ——12 个 run 目录 + 专属 `v1\summary.csv`（全 16 列）+ `v1\terrains.csv`（108 行长表））:

  | ckpt | nom succ | nom fall | rob succ | rob fall | rob lin_mae | rob recov [s] | rob never_rec | energy nom/rob [J/m] |
  |---|---|---|---|---|---|---|---|---|
  | 零动作 | 0.254 | 0.000 | 0.261 | 0.014 | 0.859 | 13.01 | 0.000 | 1219 / 2800 |
  | 2k | 0.511 | 0.042 | 0.516 | 0.500 | 0.624 | 11.83 | 0.472 | 1751 / 1896 |
  | 4k | 0.581 | 0.028 | 0.511 | 0.278 | 2.244 | 11.57 | 0.239 | 1569 / 1648 |
  | 6k | 0.569 | 0.264 | 0.539 | 0.500 | 3.132 | 9.87 | 0.403 | 2102 / 1529 |
  | 8k | 0.593 | 0.278 | 0.602 | 0.389 | 1.872 | 7.06 | 0.125 | 2274 / 1432 |
  | 10k | 0.610 | 0.153 | 0.633 | 0.236 | 0.987 | 7.45 | 0.183 | 1530 / 1370 |
  | 14k | 0.635 | 0.333 | 0.610 | 0.417 | 1.958 | 5.86 | 0.097 | 1591 / 1536 |

  零动作基线 = 08-31 的 `Lizard-Rough-v2` 冒烟两行（未分组，仍在协议根 `summary.csv`），
  口径同协议但 task 不同（v2 obs 308），只作 success 下限参照，不参与 v1 趋势。
- 逐地形（数据 = `v1\terrains.csv`；看表 `run_ablation.py --by-terrain --group v1`，
  出 completion / fall_rate / success_rate 三张「地形 × ckpt」pivot）:
  - 涨的是**难地形通过率**：nominal `stairs_20cm` .22→.55、`gap_20cm` .08→.52、
    `rough_b` .59→.77、`stairs_10cm` .49→.67
  - 不动的是**平地/斜坡**：`flat` .61~.65、`slope_10deg` .73 上下（命令速度协议钉死，
    速度没变快，变的是"能不能过去"）
  - `gap_40cm` 六档全线 .08~.21、nominal fall 恒 0 → 见分析 A8（预期内）
- 图（**视图不入库**，`plots\` 与 `report.html` 已在 `.gitignore`；记录只有数据，图随时可再生）:
  一条命令出单文件汇总报告（训练 4 图 + 评测 2 图 + summary 表 + rev 溯源，矢量可放大）：
  `python ablation_harness\plot_eval.py --protocol locomotion_eval_v1 --group v1 --report rl_exp\versions\lizard\v1`
  → `rl_exp\versions\lizard\v1\report.html`。只有要贴图进工单/PPT 时才用 `--out_dir` 出散 PNG
  （训练侧 `v1_reward/termination/episode_length/progress`，评测侧 `v1_eval_trend`（success/fall/recovery
  vs ckpt，nominal+robust）｜`v1_eval_terrains`（completion×fall 热力，地形 × ckpt））
- 分析（编号 A，每条挂证据；数据 = 上面表 + `terrains.csv`，图 = `plots\`）:
  - **A1 特权救活趴窝成立**（§4.6 对照判出）：零动作 success 0.254 → v1 nominal 0.51~0.64，
    2k 就 0.511。激励逃生舱（家族 PLAN 挂账 #7）不再是 Phase 1 阻塞项。
  - **A2 勘误（本文件先前写的"fall 随迭代上升"撤回）**：那是 3 点采样的假象。补到 6 点后
    nominal fall = .042/.028/.264/.278/.153/.333、robust = .500/.278/.500/.389/.236/.417
    ——**6k 起 fall 跳进 .15~.33（nominal）/.24~.50（robust）带内抖动，无单调趋势**。
    单 seed × 72 env，±0.1 抖动属正常（harness 纪律：结论性对照要 ≥3 seed）。
    真正可下结论的是"6k 之后 fall 稳定不为零"，不是"越训越摔"。
  - **A3 真趋势在 recovery**：robust recovery mean 11.83→11.57→9.87→7.06→7.45→5.86 s，
    never_recovered .472→.239→.403→.125→.183→.097 单调改善（除 6k 回抽）。
    4k 前"摔了就爬不起来"（2k never_rec .47），14k 只剩 .10 → **抗扰恢复力是本次训练最硬的增益**。
  - **A4 robust 成熟更晚但终点不低**：robust success 到 8k 才追平 nominal（.602 vs .593），
    10k 反超（.633 vs .610）；2k/4k 的 robust 几乎零进步（.516/.511）。
    → 用 nominal 判"训好了没"会**早判**，DR 下的能力要到 8k+ 才显形。
  - **A5 增益来源是难地形通过率而非速度**：见上「逐地形」——`stairs_20cm`/.`gap_20cm`/`rough_b`
    明显上涨，`flat`/`slope_10deg` 全程不动。协议命令时间线钉死（vx≤1.5），
    所以涨的不是跑得快，是"过不去的地方能过去了"。
  - **A6 平地摔是本轮最该盯的数**：nominal `flat` fall 从 2k/4k 的 0.00 涨到 8k/14k 的 0.50
    （robust flat 14k .62）。平地都不稳 → 稳态裕度小，是"敢动"的代价。
    这条比 success 更该进 v2/v3 的验收线。
  - **A7 lin_mae / stop 超调被摔倒滑行污染，不可判收敛**：14k nominal 分段 lin_mae
    .104/.265/.444/.987/**3.760**/**8.594**（命令 vx 只有 1.0→0.0）。协议 valid 掩码
    只在 episode 终止处截断，摔倒后顺坡滑行的 env 仍计入均值 → MAE 与 stop 超调
    必须与 fall 同读（6k/8k nominal 的 4~5 m/s MAE、14~17 m/s 超调全由此来）。
  - **A8 gap_40cm 是预期内不会，不是缺陷（显式预期线）**：六档 completion .08~.21、
    nominal fall 恒 0（站沟前不动不摔）。Phase 1 配方无起跳激励、无越障课程、
    命令时间线无跳 → **v1/v2 阶段判 gap_40cm 为"不该会"**；要它变成指标，
    得等带越障意图的版本（v3+），届时再回填预期线。
  - **A9 能耗量级合理但只可同口径互比**：1370~2274 J/m（72 kg 级），峰值 8k nominal 2274
    与该档 fall/滑行最多同步。协议 energy 为隐式 PD 精确反解、不含 effort 饱和，
    绝对值别引用于硬件选型。
- 可比性声明（provenance）：12 行 rev 跨 c2d5d03 / 026358d / 3a8399d / edba705。
  逐 diff 核对：`teacher_env_cfg.py` 只**增** v3 类与 `TEACHER_PRIVILEGED_SPEC["v3"]`；
  `lizard_env_cfg.py` 只改 dev yaml 路径（v1 走 `versions\lizard\v1\` 冻结件，不受影响）；
  `play_utils.py` 只影响 PLAY 变体（本评测用 TRAIN id）；v0~v2 `asset_lock` 未报漂移
  （资产未变）→ **v1 环境语义在 12 行之间未变，可互比**。obs 恒 266（ckpt 载入未报形状错）。
- 复现（一次 campaign 的全套命令，`--group v1` 决定落盘位置）:
  ```bat
  :: 12 次评测（每次约 4~8 分钟，含 Isaac 启动）
  E:\IsaacLab\env_isaaclab\Scripts\python.exe ablation_harness\eval.py ^
    --task Lizard-Rough-v1 --checkpoint <run>\model_<it>.pt --protocol locomotion_eval_v1 ^
    --mode nominal|robust --seed 123 --tag v1_<it> --group v1 --headless
  :: 逐地形长表 + pivot
  python ablation_harness\run_ablation.py --by-terrain --group v1
  :: 曲线数据导出（入库）+ 汇总报告（不入库，可再生）
  python rl_exp\tools\trainlog\dump_tb.py --log_dir <run> --out rl_exp\versions\lizard\v1\tb_scalars.csv
  python ablation_harness\plot_eval.py --protocol locomotion_eval_v1 --group v1 ^
    --report rl_exp\versions\lizard\v1
  :: 仅当需要贴图（工单/PPT）时再出散 PNG（ckpt 迭代号需手传 --mark）
  python rl_exp\tools\trainlog\plot_tb.py --csv rl_exp\versions\lizard\v1\tb_scalars.csv ^
    --out_dir rl_exp\versions\lizard\v1\plots --prefix v1_ --mark 2000,4000,6000,8000,10000,13999
  python ablation_harness\plot_eval.py --protocol locomotion_eval_v1 --group v1 ^
    --out_dir rl_exp\versions\lizard\v1\plots --prefix v1_eval_
  ```
- 结论/下一步:
  1. 复现：任务 id `Lizard-Rough-v1` 常驻注册（`LizardRoughTeacherEnvCfg_V1`，obs 266，
     spec 剥离 v2 增量 term），或 `git checkout lizard-v1` 整树快照。
  2. **v2 同 6 点 × 双模式对照**（判特权补全的净增益），直接复用上面复现块。
  3. 要下"fall/recovery 是否真变"的结论 → **≥3 seed**（A2/A3 目前单 seed，趋势可信度有限）。
  4. A6 平地摔要不要触发挂账 #7（激励补丁）：等 v2 对照出来再判，别在单配方上下结论。
- 基础设施坑（评测台，非配方）: `eval.py` 缺 train.py 的
  `handle_deprecated_rsl_rl_cfg` 迁移，rsl-rl 5.4.2 拒绝 legacy `stochastic` 字段
  → checkpoint 路径直接 `TypeError`（08-31 冒烟是零动作策略，从未走过该路径）。
  已修 `ablation_harness\eval.py` `_prepare_env`（harness v1.1）。
