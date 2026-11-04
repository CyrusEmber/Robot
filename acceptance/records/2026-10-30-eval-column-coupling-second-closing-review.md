# 套件列间耦合第二次关闭审核（2026-10-30）

## 适用范围

不带执笔历史的新上下文对照关闭条件、实际落点及真实原始数据重审 `work/active/eval-column-coupling.md`，包括旧初态记录的勘误；未修改数据、提交或启动仿真。

## 验收条件

核验单标量对照、候选机制、可复读入口与身份、比较器破坏测试、旧记录勘误、规则和工具承接；对实际落点不能兑现的能力拒绝通过。

## 结果

**不通过，退回执行。** 原初态记录已有醒目勘误并保留原文，上一轮相应缺口已处理。单标量数据、比较器及历史环境恢复的独立承接在已声明的边界内成立，但发现新的规则落点缺口及历史叙述问题：

- 无 `--group` 的 `run_ablation._summarize` 将各组行打印在同一张表，却只逐组检查条件；从 `coupling-probe` 与 `runtime-acceptance` 各选一条真实记录，`record.conditions_conflict` 判定 `suite.digest` 和 `suite.geometry_digest` 冲突，内存限定输入调用实际 `_summarize` 却返回 0。此为受控选行复现，不代表现有所有组的完整运行会返回 0。`ablation_harness/HARNESS.md` 对汇总表逐对检查的表述因此过强。
- `acceptance/records/2026-10-10-cross-protocol-suite-readings.md` 的 2026-10-10 勘误将 `success_rate` 称为逐环境二值且量化粒度为 0.125，实际是有效帧加权比例；`acceptance/records/2026-10-10-eval-column-coupling-review.md` 已指出。`acceptance/records/2026-10-10-eval-column-coupling-probes.md` 的“差异全部由地面产生”缺少通道与身份控制，不能作为排他因果结论。须保留原文并追记勘误。
- 诊断工具存在，但本次未找到其常驻维护接收的明确确认；工具去向须落实或保留待办。
- 单标量批次中只有 rough_b 的 `noise_range` 下限改变；同臂重复一致，stairs_20cm 八个环境在第 10 步分叉，所有臂均无记录的 done/reset。不能据此坐实 PhysX 内部、排除未记录状态或全局 RNG，亦不能定量解释策略指标。
- raw 摘要、脚本快照以及 metadata 所列源码和资产与本机一致；这不是完整环境或来源真实性证明。历史仿真环境恢复仍由 `work/active/eval-column-runtime-recovery.md` 承接，不冒称已恢复。

## 证据引用

- 事项与前次审核：`work/active/eval-column-coupling.md`、`acceptance/records/2026-10-30-eval-column-coupling-closing-review.md`；修订后的历史记录：`acceptance/records/2026-10-10-eval-column-coupling-initial-state.md`。
- 汇总实际调用：`ablation_harness/run_ablation.py` 的 `_summarize`；条件定义与比较器：`ablation_harness/record.py` 的 `conditions_conflict`；真实工件在 `ablation_harness/results/locomotion_eval_v3/coupling-probe/` 与 `ablation_harness/results/locomotion_eval_v3/runtime-acceptance/`。
- 本次只读复读 `acceptance/records/2026-10-28-eval-column-coupling-repair.md` 的四臂两批 `compare`、`selftest` 与 timeout 原始数据复读命令，均通过；将 `bits_differ` 在内存替换为恒无差异，自检拒绝。独立对账配置、raw 和文件摘要，结果与该记录相符。
- 历史策略工件按 `acceptance/records/2026-10-28-eval-column-coupling-independent-review.md` 所载命令对账通过；生成器摘要不证明 PhysX 烹饪后碰撞形状一致。

## 未覆盖边界

未跑物理仿真、policy、其他 seed/资产、完整离线套件或历史环境恢复。timeout 旁证不覆盖接触终止。需处理跨组缺陷并做修前红、修后绿的行为回归，追记历史勘误，落实工具去向；证据改变后重新独立审核。

## 2026-10-30 退回后的修复

- `_summarize` 在未指定组时检查同一输出表的跨组记录条件，使用路径区分重名 run；保留已声明资产替换的处理。同组原有检查保留；不完整或 legacy 记录不再被静默忽略。`--by-terrain` 仍不经过此检查。
- `test_summary_checks_conditions_across_groups` 使用真实入口及临时数据验证跨组地形冲突、重复 run_id、组过滤、条件相同、声明资产替换与不完整记录。内存恢复旧逻辑后该测试因跨组冲突未拒绝而失败；恢复修复后通过。不完整记录负例在加对应拒绝前失败、修后通过。
- 使用真实 `coupling-probe` 和 `runtime-acceptance` 各选一条完整记录，以内存限制实际汇总输入；修复后 `suite.digest` 冲突被报告并返回非零。该选择不代表所有组的完整汇总情况。
- 已在 `acceptance/records/2026-10-10-cross-protocol-suite-readings.md` 与 `acceptance/records/2026-10-10-eval-column-coupling-probes.md` 前追记勘误，旧原文保留；工具维护交接确认作为未完动作迁入 `work/active/eval-column-runtime-recovery.md`，尚未声称已接收。
- `test_eval_record.py` 的完整离线运行 36 项通过；`check_work_docs.py` 通过。主工作树 `check_suite_shape.py` 因另一会话在同一测试文件新增的解释器子进程未在 `SPAWN_ALLOWED` 声明而失败；本轮没有改其测试或绕过检查，完整仓库闸门未通过，不可称主工作树全绿。
