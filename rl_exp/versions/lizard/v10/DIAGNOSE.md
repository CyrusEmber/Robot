# v10 支撑异常诊断计划（固定 model_14999.pt，不训练，不改奖励）

- 目的：区分四类成因——异常支撑（头颈/腹承重）、动作失稳、台阶几何限制、
  belly 惩罚与越障冲突。产出一张诊断表 + 几段关键视频，回填本目录 NOTES.md。
- 输入：`E:\IsaacLab\logs\rsl_rl\lizard_rough_teacher_v10\2026-09-09_18-15-19\model_14999.pt`
- 已有先验（零成本，先入表）：
  - nominal eval flat 列：completion 0.566 / success 0.66——平地能走但位移打折
  - stairs_20cm：completion 0.83 / success 0.62——连续 20cm 金字塔台阶不是墙
  - gap_40cm：completion 0.11——真墙在 gap，不在台阶
  - 训练全程 belly_contact_force ≈ 0——训练分布内无仰面 hack

## Phase 1 站立闸（2 runs，5–10s）

| run | 做法 | 判定 |
|---|---|---|
| 1a | 平地，默认关节目标 5s（`eval.py` 无 checkpoint 的 zero-action 模式同款） | 倒 → 资产/出生/PD，停查 |
| 1b | ckpt 接管，零速度命令 10s | 倒 → 策略静态稳定问题 |

条件：训练同资产同 PD，DR 全关（nominal），固定出生姿态。

## Phase 2 平地直行（9 runs）

- 0.3 / 0.5 / 1.0 m/s 直行各 10s；**3 个 reset seed**（非朝向——平地各向同性，
  有信息量的是 reset 扰动抽样：关节缩放 0.5–1.5 + 出生速度随机）
- 50Hz 记录：base/胸段/头颈倾角与离地高度；各 link 接触力；四脚接触状态与
  承重比例；实际速度；tracking / belly / feet_slide 加权奖励（manager 每 step
  自带，直接读）
- 预定判据：**头颈承重 = 法向力 > 10% 体重且持续 > 0.5s**；时序上分清
  「先低头撑地」还是「先失稳后找支撑」
- 视频：侧视，每档至少 1 段

## Phase 3 单级台阶（≤ 24 runs，早停）

- 5 / 10 / 15 / 20 cm 孤立单级台阶，上/下分开测；平台 ≥ 5m（容 3.6m 身长）；
  0.3 m/s 正对接近；每档 3 次（不同 reset seed）；先低后高，明显失败即停
- 20cm 卡住 → 补 0.5 / 1.0 m/s 动量档（+4 runs）——准静态边界与动量边界分开报
- 记录：通过/卡住、卡住部位、腹接触时长、接触期间是否仍前进
- 判据：「短暂搭腹后通过」与「持续趴住不动」分开标记

## 诊断表（跑完回填）

| 观察 | 处理方向 |
|---|---|
| 1a 默认目标也站不稳 | 资产、出生或 PD |
| 头颈承重、脚悬空，belly≈0 且 tracking 高 | 接触覆盖与奖励漏洞 → 预注册反制（升 belly 权重 / 加头颈接触罚，走训练消融） |
| base 持续倒置但 eval 不报 fall | 评估盲区（tilt<40°+clearance>0.6 的支撑姿态躲过几何判据） |
| 平地正常，超过某高度才卡 | 地形尺度与课程 |
| 搭腹能通过但受明显惩罚 | 短暂越障接触与持续异常支撑分开处理 |

## 实现方式（复用，不新造轮子）

- 脚本：`rl_exp/tools/diagnose/diagnose_support.py` 单文件
- 照抄 `eval.py` 三件套：`apply_eval_mode` nominal 关 DR / 直写
  `term.vel_command_b` 注入命令 / 50Hz snapshot 时序
- 单级台阶：`suites.py` 模式（curriculum=True 等比例锁列 + 单值参数范围 +
  seed 钉死）写 `single_step(h)` 生成器；平地 = MeshPlaneTerrainCfg
- ContactSensor 扩 head/胸/颈 body 名单——诊断 cfg 内做，不动家族代码
- 产出：`rl_exp/tools/diagnose/out/<run>/` json + png + 视频；诊断表回填本文档

## 限制声明

eval 时把 belly 权重调零不会改变固定策略的动作，不能证明「去掉惩罚就能过」。
本轮只测实际接触与奖励账本；证实冲突后才值得做训练消融。

## 结果（2026-09-11，ckpt model_14999.pt，实现 rl_exp/tools/diagnose/diagnose_support.py）

有效数据：Phase 1 = out/smoke_p1c；Phase 2 = out/v10_run1（flat 各向同性，
随机出生朝向不影响）；Phase 3 = out/v10_run3（单级台阶 + 出生 yaw 钉 0）。
v10_run1（随机朝向）与 v10_run2（地形 bug=两级台阶）作废，仅留档。

### Phase 1 站立闸 —— 双闸通过

| case | max_tilt_deg | drift_m | max_belly_fz_n | fell |
|---|---|---|---|---|
| p1a 零动作 5s | 6.1 | 0.03 | 0.0 | 否 |
| p1b 策略零命令 10s | 13.2 | −0.42 | 0.0 | 否 |

→ 资产/出生/PD、策略静态稳定均排除。

### Phase 2 平地直行 —— 正常，无异常支撑

| 档速 | fwd_mean（cmd） | tilt_max | neck_frac | belly_frac | first_event |
|---|---|---|---|---|---|
| 0.3 | 0.45 | 11.1° | 0.0 | 0.0 | feet_lift |
| 0.5 | 0.62 | 11.9° | 0.0 | 0.0 | feet_lift |
| 1.0 | 1.06 | 13.3° | 0.0 | 0.0 | feet_lift |

tracking 账本 ≈1.45–1.49（上限 1.5），feet_slide 微负，belly 恒 0。脚载荷
后重前轻（约 42/25/7/7 %）——蜥蜴后肢主导步态，非异常。→ 「先低头」从未发生。

### Phase 3 单级台阶 5–20 cm 上/下（0.3 m/s 正对）—— 全档 3/3 通过

progress 一律 ~10 m、**腹/胸/颈接触全程为 0**、无卡住部位；up_20 攀爬期
feet 断续 + tilt 瞬态 ~12°，down_20 下落期 tilt 瞬态 15.9°，均数步内恢复。

### 诊断表回填

| 观察 | 结论 |
|---|---|
| 默认关节目标也站不稳 | **未见**（6.1° 稳站） |
| 头颈承重、脚悬空，belly≈0 且 tracking 高 | **未见**（neck/belly 全程 0） |
| base 持续倒置但 eval 不报 fall | 未复现 |
| 平地正常，超过某级高度才卡住 | **未见**（≤20cm 全过，无能力边界） |
| 搭腹能通过但受明显惩罚 | **未见**（无任何搭腹） |

**结论：在 0.3–1.0 m/s、nominal DR 关、单级 ≤20cm 台阶条件下，担忧的
异常支撑完全不出现。** 剩余未覆盖区：更高速度、robust 级扰动（4 m/s 踢 +
DR——即 robust eval 里穿透异常的那个 regime）、连续窄踏面（0.7m 金字塔
楼梯，eval 已知 completion 0.83）。若需继续，下一步应测踢后恢复行为而非
再扫台阶高度。

### 实现备注（坑与修法，防再踩）

1. `reset_base` 基类默认 yaw ±π 随机——体坐标命令导致各 env 往随机方向走，
   台阶列全部失真；诊断脚本钉 `pose_range["yaw"]=(0,0)`。
2. 单级台阶条件：`platform_width` 必须**严格大于** `size−2*border`；恰好相等
   时 floor 除法给 num_steps=1 = 两级台阶（离线 trimesh 校验抓出）。
3. rsl_rl wrapper 的 `reset()` 返回 `(obs, extras)` 元组，策略吃裸 obs。
4. 接触力/体重需先走若干物理步再读（reset 后首读为 0）。
