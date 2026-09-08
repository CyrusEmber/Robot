# v7 —— ghost 断腿鲁棒性（截肢近似 DR + damage flag obs + v8 ckpt 微调）

- 修订历史：v7.0（2026-09-08 初稿——用户拍板"只练 ghost 和普通的，来当 v7"；
  limp 档/损伤分级/多腿同断/mid-episode 断腿全部不做）→ **v7.1（同日：
  归档，不再实施**——提案未启动，"v6 ckpt 微调"前提随 v6 判废失效，
  ghost 线重基 v8 按序迁 v9，用户拍板"按顺序开 v9"；实施见 `..\v9\`）。
- 目的/假设: UE 战斗断腿事件后怪物不宕机，瘸法生物学合理（三足 + 躯干/尾
  代偿——代偿通道 = v6.1 解锁的 10 脊柱/尾关节）。同时验证 PITW
  "加地形→继续微调"配方（旧技能不掉点）。假设：ghost（stiffness→0 +
  整腿质量 ×0.001）在固定拓扑/维度契约内近似截肢足够好；damage flag 直喂
  obs 后单策略 DR 混训即可同时保住健康步态与三足代偿，无需蒸馏。
- 相对 v6 的变更（yaml = v6 逐字 + `v7:` 段；obs/DR/reward/资产如下）:
  - DR 新组 `v7.broken_leg`：p=0.3/每 reset，均匀选一腿，整腿 4 关节
    stiffness→0、damping→1.0、link 质量 ×0.001（reset 事件，代码待实施）
  - obs：`damage_flags` 4 维 one-hot 进 actor 本体组（90→94，全 0 = 健康；
    UE 侧游戏逻辑断腿事件直填——部署端白送）
  - reward 豁免（V7 子类，不回改 v1–v6 类）：断腿 env 豁免断腿 hfe/kfe 的
    r_co 罚（残肢拖蹭不可避）；`.*_foot` 不豁免（被动撑地合法）
  - 训练源：**v8** checkpoint 微调（前提修正 2026-09-08：v6 已训判废——倒走，
    见 `v6\NOTES.md`；微调基座改指 v8。obs 90→94 需 weight surgery：输入层
    新 4 列零初始化，起步行为=v8 逐位；新 optimizer + 降 LR；防遗忘：健康
    样本占大头 + DR 不收窄 + 冻 policy 预热 critic）；v8 不可用则从零（fallback）
  - 资产零变更：ghost 是运行时 DR，不动 URDF/USD（asset_lock 与 v8 同代——
    2026-09-08 解剖学重命名换代锁已随 v8 commit 刷新，本目录建稿时未手写锁）
- 版本纪律: obs 结构变更 + DR 范围变更 → 开 v7 非 v6.M；v6 处提案态，但
  用户明示开 vN+1（前置门豁免，versioning.mdc §A）。
- 装配验证: （开工后补：V7 smoke + check_obs_layout（94 维组）+ offline
  闸门 + broken_leg DR 事件单测——抽签分布/断腿关节力矩=0/质量缩放生效）
- 训练命令:
  ```bat
  python scripts\reinforcement_learning\rsl_rl\train.py --task Lizard-Rough-v7 --max_iterations 5000 --seed 42
  ```
  （微调入口 = resume v8 checkpoint，iters 开工时定；从零模式同命令改
  `--max_iterations 15000`）
- log 目录: logs/rsl_rl/lizard_rough_teacher_v7/
- 验收: 同 v7\PLAN.md 验收节（继承 v8 KPI + 断腿 suite ≥60% 健康档 +
  GUI 肉眼代偿/无代偿）
- 结果回填: （训练后补：reward 曲线读数 / 健康 vs 断腿 KPI 对照表 /
  eval 跑分表 / 结论）
- 结论: （一句话，训练后补）
