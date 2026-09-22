# 2026-09-22 启动探针：让它观测自己声称的东西（下压、复位前取样、终止集合、目视帧）

## 适用范围

- 被验对象：`rl_exp/tools/verify/baseline_probe.py`（启动探针）、它的任务侧期望来源
  `rl_exp/versions/lizard2/main/{,v1/}main_params.yaml`、以及随之重钉的
  `versions/lizard2/main/cfg_lock.json` + `versions/lizard2/main/v1/asset_lock.json`。
- 触发：评审指出探针"全绿"的覆盖面不成立——下压实验构造了动作却仍下发零动作；接触力在 `env.step`
  返回后读取（此时已复位）；"终止集合一致"只断言不该缺的没缺，多余的只打印不判否，且按 `_threshold`
  后缀推导覆盖不了别的参数形状。
- 不覆盖：评测协议冻结（①）、训练本身、以及"从下方穿过 1 N 阈值的温和下压"（见末节）。

## 验收条件

1. **下压必须真的下发**：压头用**部署动作接口**构造（含组 scale 与 default offset），并把它交给 `env.step`；
   构造了不用等于没测。
2. **力与终止项必须同一帧**：`env.step` 会在返回前复位已终止环境，复位清零接触传感器缓冲 ⇒ 返回后读到的
   是**下一回合**的力。读数取自 `_reset_idx` 包装（复位前最后时刻），并同时打印该步返回的
   `terminated`/`truncated`。
3. **对照必须在**：同一台仪器要给出"没接触不触发"与"真接触触发"两半，单跑任何一半都不能排除守卫接错部位。
4. **触发读数必须能被几何解释**：终止力要由**声明的连杆自己**贴地解释；力出现而该连杆网格仍在地面之上时，
   判红而不是判绿（评审口径：不能把解释不了的读数放行）。
5. **终止集合用等号判**：生效集合 == yaml `terminations.terms` 点名的集合 ∪ 框架自带 `time_out`；
   多与少都红。后缀推导（`*_threshold`）换成显式点名，以便 dwell / 速度闸等其它参数形状的终止项也被覆盖。
6. 静态截图不能证明动态稳定 ⇒ 出**多帧**画面供人看。

## 结果

- **压头**：`head_press_action()` 按动作项自己的 `_joint_names`/`_scale`/`use_default_offset` 反算动作，
  整批环境一起下发（旧版只写 `press_action[0]` 且从不传给 `env.step`）。
- **取样**：`unwrapped._reset_idx` 临时包装，在复位发生前抓 `head_contact_max(...)`（瞬时与 **传感器自身
  3 帧窗口**的最大值）、该帧的头部网格最低点、以及 `head_contact`/`base_contact` 的项值；循环里另打印
  `terminated`/`truncated`。
- **对照（同一台仪器，边界两半都在）**：站立不动 40 步 = 头部接触力峰 **0.00 N**、守卫不触发；压头则
  从**下巴离地 50 mm** 起降——**前 18 帧 0.00 N 静默**，到下巴触地那一帧力 **1108.12 N** 且**同帧**触发，
  该帧窗口最大同值、头部网格读数 0.3 mm 进入地面（几何能解释该力），返回 `terminated=True`、`truncated=False`、
  `base_contact` 不在其中。新增 `head/fires-only-on-contact` 要求前面确实有静默帧（否则这一跑没给出边界）。
- **下压必须钉住头链**：只下发动作时，驱动在下巴自重下饱和，机降 283 mm 的同时头链**回缩**（相对机体抬升约
  0.3 m）——"命令的姿势"不是"保持住的姿势"；改为每步写关节状态把链钉在极限位姿后，逼近才可控。
- **由此得到的结论强于"阈值待标定"**：接触是硬的，**1 N 约合 1 µm 穿透**（1108 N / 0.3 mm ⇒ 刚度 ≈ 4×10⁶ N/m），
  任何姿势斜坡下力都是从 0 直接跳到数百牛。故 `head_contact_threshold` 实为**"接触检测器"而非"力门限"**：
  决定判据的是"下巴有没有碰到地"。先前写的"温和下压穿过 1 N 仍欠着"**撤回**——斜坡给不出该读数，也不需要。
- **终止集合**：`declared: ['base_contact','head_contact'] + time_out | live: ['base_contact','head_contact','time_out']`；
  新增 `terminations/base_contact-declared-and-live`、`head_contact-...`、`time_out-...` 与
  `terminations/no-undeclared-term` 四项，等号判定。
- **无碰撞网格的死条目**：探针的 `head/no-collider-less-pattern` 报出 `chest_.*`/`neck_.*` 同时命中
  `chest_yaw`/`neck_yaw`（无碰撞网格 ⇒ 那半个模式永不触发）；yaml 已收窄为 `chest_pitch`/`neck_pitch`，
  该检查转绿。此项**单独一次提交**，不与取样修复混为一谈。
- **目视帧**：`--shot`（需 `--enable_cameras`）把零动作回合的 7 帧写到 `_tmp_zero_action_shots/`
  （`_tmp_*` 已在 `.gitignore`）。已看一眼末帧：8 台机器人平地站姿，四足平贴网格、无可见穿地，绿色箭头是
  命令可视化标记。**静态帧不能证明动态稳定**，动态侧仍以数值为准（base z 均值 0.937 m、tilt 均值 0.43°、
  载荷全在四足）。
- 同变更重钉：`cfg_lock.json` 差异**恰好 2 条路径 × 2 个 task**（`head_contact...body_names[0..1]`），
  `asset_lock.json` 重钉冻结 yaml 摘要；yaml 新增的 `terminations.terms` **不动任何 cfg 字段**（golden 里
  看不到它），因为它是给闸门读的声明而非配方字段。
- 离线套件 `ALL_OFFLINE_CHECKS_PASSED (47/47)`。

## 证据引用

- 复读：`env_isaaclab\Scripts\python.exe rl_exp\tools\verify\baseline_probe.py --task Lizard2-Flat-Play-v1
  --head-press --steps 40 --num_envs 8`（判据行见上）；`--enable_cameras --shot` 出帧。
- 重钉：`check_dr_parity.py --update-locks --family lizard2`、`check_cfg_lock.py --update --line lizard2/main --reason ...`。
- 落点：PLAN 硬前置 2 / 5、`work/active/lizard2-family-landing.md`。

## 未覆盖边界

- **不是阈值标定，且不可能成为标定**：机器人站在脚上时头够不到地（极限头姿仍高 0.478 m），下压是把鼻子
  朝下的机体送到地面；接触刚度 ≈ 4×10⁶ N/m ⇒ 1 N 只值约 1 µm 穿透，力在一帧内从 0 跳到数百牛。已证的边界是
  "**离地则静默、触地即触发**"，而"1 N 处翻转"这个读数**本身不存在**（撤回此前把它列为欠项）。
- 几何读数用的是资产自己的碰撞网格（USD 的碰撞 mesh 与 `meshes/collision/*.obj` 的 extent 一致：`chest_pitch`
  的 extent `0.0812..0.9886`、z `±0.3676` 两边相同；USD 上带 `physics:approximation = "convexHull"`）。
  **撤回**此前"碰撞体与网格可差到厘米级"的说法：那是我自己把 `-mesh_floor` 的符号读反、又用未步进的姿势读了一次
  深度造成的；本次触地帧的网格读数 0.3 mm 与刚度估算自洽。`head/fires-with-the-head-at-the-floor` 的容差
  仍按一次下压步长取，不做更细的深度断言。
- 该终止判据的期望现在**要求 yaml 点名生效集合**：未写 `terminations.terms` 的旧线跑本探针会红
  （信息即"这份 yaml 没点名它的终止集合"），改动属那条线的所有者。
- 渲染路径需要 `--enable_cameras`；无该开关时 `--shot` 直接拒绝而不是静默降级。
- 钉链用的是写关节状态（把链固定在极限位姿），因此**下压不是"策略或驱动器能维持的姿势"**：它只回答守卫本身
  的判据，不回答"训练中头链能否被压到地"。后者属训练期观测。
