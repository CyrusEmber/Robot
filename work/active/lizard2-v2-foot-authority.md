---
id: lizard2-v2-foot-authority
title: lizard2 v2 配方：取消脚板策略动作（脚板保留固定平放参考的 PD）
scope: rl_exp/tasks, rl_exp/versions/lizard2, ablation_harness/protocols, rl_exp/versions
status: open
landing: rl_exp/tasks/lizard2_recipe.py, rl_exp/versions/lizard2/main/main_params.yaml, rl_exp/versions/recipes.json, rl_exp/tasks/agents/rsl_rl_ppo_cfg.py
next: ① 建版（§A 五步）：`copy versions/lizard2/main/v1 → v2`；v2 的 yaml **只**加 `action.joints`（legs 去掉那个脚板 pattern ⇒ 网络动作维度随之减少），脚板执行器、奖励、终止、命令、sim **逐字不动**；`base.json` 母本 = v1；PLAN 范式由"唯一变化"是否成立决定（两个变量同时改 ⇒ 多变量 PLAN，并预先写明改善不可归因于单项）；NOTES 留骨架；`diff.json` 由 `emit_diff_declaration` 生成后逐项写 `why`。② 注册：`LIZARD2_RECIPES["v2"]`（elements 与 v1 相同，差异全在 yaml）+ 两个新任务 id + `versions/recipes.json` 两行 + 新 runner（独立 `experiment_name`，一版本一日志目录，禁共用）。③ **动作维度的连带（易漏）**：`last_action` 宽度随动作维数变 ⇒ `obs_protocols.json` 要建 v2 声明并给两个新 id 记 `{protocol, version, line}`，`check_obs_protocol` / `check_obs_layout` 必须绿；宽度与布局的**判据形状**写进 PLAN，读数归记录。④ 启动契约（用户第 2 条）：`baseline_probe.py --task <v2 训练 id> --random-actions` 已覆盖"每关节恰一个通道 / 维度=映射 / 终止集合 / obs 宽度等于已批准记录 / reset 误差"；**要补两条断言**：随机激励下脚板四个关节的**目标恒等于默认平放位**、逐关节实读增益与限幅；证据另立记录（探针不是读数，是把读数挡在门外的闸）。⑤ `cfg_lock --update --line lizard2/main --reason "<what moved and why>"`（新任务 id 必须配 golden；同一变更内证明 v1 的两项 golden **逐项未变**）+ FAMILY 任务注册表与版本史各加一行。⑥ **训练参数待定，且要等掩蔽组**：脚板沿用 v1 既有增益还是换候选弱增益，取决于 `feet-drive-candidate-probe`——未掩蔽的候选组已给出**否定结果**（记录 ⑬：未适配的策略下 1–3 秒终止、饱和由**目标误差量级**而非增益常数决定），所以参数选择只能等"目标被钉在默认平放位"那一组（记录 ⑭）。附带价值：掩蔽组正是本项在**动作接口层**要面对的配置，它的读数可作 v2 训练前的行为预览。若最终两个变量一起进训练，按 §A 用多变量 PLAN 并预先写明改善不可归因于单项。⑦ 对照与评测（用户第 3/4 条）：对照臂 = **当前资产上的 v1 重训**（2026-09-28 用户拍板：现有 checkpoint 是修 hull 前的几何，只能作背景），两臂配对 seed、同预算、同一份 eval 协议与同一承重门/过渡剔除/滑移口径，窗口长度按"每档每只脚的稳态承重周期下限"定（下限写进协议，不足即标样本不足）；报告含请求 vs 交付力矩与饱和占比、承重分配、脚板姿态、速度跟踪、存活。⑧ 开训前工作树必须干净（硬拒），冻结打 tag；⑨ 结论按计划里预先写好的判据收口——"滑移下降但变慢或更易倒"不算改善。
close_when: (a) 两个新任务 id 在 v2 冻结参数上通过启动契约探针（含"脚板目标恒等默认平放位"与新 obs 宽度两项新断言），且旧断言在 v1 上仍绿；(b) 两臂按同一协议产出评测报告并回填 `v2/NOTES.md`，按 PLAN 预写的判据给出结论——正负都关；(c) 若结论只能到"机制"层（对照臂的几何混淆未消），在 NOTES 与记录里写明并把它作为后续动作的输入，不得写作因果结论。三件齐了才关
depends_on: feet-drive-candidate-probe
evidence: acceptance/records/2026-09-23-lizard2-v1-gait-skate
---

## 问题与本次范围

问题：脚板的策略动作权限是否在拖累步态。v1 是"脚板有动作权限"的那一臂，v2 去掉权限、保留固定平放参考的
PD，其余配方逐字不动，作为**动作权限**这一个变量的实验。

范围：配方版本、任务注册、启动契约、评测协议与两臂对照。**不含**脚板增益本身是否合理的判断（见
`feet-drive-candidate-probe`）；不含资产改造；不含奖励变更。

## 当前状态

方案与判据待落 `v2/PLAN.md`（v2 目录尚未建立，故本项的 `landing` 只列现有落点，新目录与该版文档在
同一变更里补进来）。三条已知的边界先说在这里：**v2 不等于"脚板被动"**（去掉通道只去掉调制，PD 仍在，
承重期脚板可能仍整段饱和）；**对照臂带几何混淆**（现有 checkpoint 训练用的脚板 hull 与当前树不同）；
**交付力矩只能给上界**。

## 未覆盖边界

- 两臂若不配对 seed、或不共用同一份 eval 协议，滑移差异不可归因 —— 协议一旦需要新字段，就新开一份协议
  版本并锚定，**两臂共用**。
- 动作维度改变即改变部署接口：接与不接在仓外（UE 侧），本项只把接口变化递过去。
- 训练预算与命令窗口沿用 v1；本项不评估"更长训练是否更好"。
