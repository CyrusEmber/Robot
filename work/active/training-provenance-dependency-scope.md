---
id: training-provenance-dependency-scope
title: 训练来源闸门按实际依赖划定阻塞范围
scope: rl_exp/tools/runrecord, rl_exp/tools/verify/test_run_manifest.py, rl_exp/tools/verify/test_rebuild_gate.py, README.md
status: open
landing: rl_exp/tools/runrecord/provenance.py, rl_exp/tools/runrecord/manifest.py, rl_exp/tools/runrecord/rebuild.py
next: 执行者先用临时 git 仓复现散文分歧与 eval 阻塞，再实现文件级专属路径声明。
close_when: 不带执笔历史的新上下文按正文判据审核实现与验收证据后决定关闭。
---

## 当前范围

修复未落地，eval 误拦截尚待端到端复现。本项**扩展** [原散文豁免](../../acceptance/records/2026-09-22-dirty-tree-refusal-scoped-to-code.md)，保留启动时 `.md` 已豁免的行为；原记录关于“rebuild 本来就是代码根口径”的表述不能作为已跟踪 `.md` 的依据，后续验收记录须明确纠正，不改写历史证据。

先复现现有分歧：启动看 `changed_non_prose`；`manifest._verify_code` 看整仓 `diff_sha256` 与 `untracked_in_code_root`；`rebuild._code_item` 遇 `dirty` 要求归档 diff。因此仅修改已跟踪 `.md` 时启动放行，capture 仍要求 `--archive`，文档 diff 再变化还会影响离线复核。未跟踪分类不能解释已跟踪文件。

本项先实现并审核文件级豁免及其 T0 记录，`work/active/verified-rebuild-rating.md` 再据此验收归档内容与评级；旧记录沿旧口径严格读取。两项不同时改共享判据；本项不接管历史材料补全或评级。文档落点为仓根 `README.md`。

## 下一步

1. 用临时 git 仓走真实采集器及三处判定，先复现已跟踪 `.md` 分歧。复现在临时仓内造同名 `ablation_harness/eval.py`、`record.py`、`run_ablation.py` 并各自单独改动（真实脏树提交后样本即失效，不作证据），沿 `code_sources → git_state/_changed_paths → manifest.begin/dirty_tree_refusal` 验证阻塞；排除无关生命周期拒绝，不以混合脏树证明独立。
2. 在 runrecord 中维护一个 eval 专属路径常量，粒度固定为文件，禁止目录或通配符豁免；只有正向声明可新增放行。初始清单及每次增删，均在 `acceptance/records/` 逐条写明导入方检查：训练侧（`rl_exp/tasks`、`rl_exp/tools/runrecord`、`launch_recipe.py`、`cfg_snapshot.py`）无人导入才可列入；检查范围含 `importlib` 与字符串引用，且声明其覆盖不到的路径。2026-11-03 搜索时 `eval.py`、`record.py`、`run_ablation.py` 无训练侧静态导入，仅作起点，动手时重查。声明文件自身是训练依赖，其改动不得享受豁免。`provenance.isaac_root` 与 `cfg_snapshot` 均导入 `ablation_harness.host_paths`，该共享文件继续受保护；其他未声明代码、配置、资产和未知用途不新增豁免。
3. T0、拒绝判定前保存当次采用的专属路径清单，避免当前声明改变历史分类；不新增范围版本、完整依赖集合、集合摘要或逐路径依据。启动、离线复核、重建材料共用该记录，`rebuild._code_item.keep` 保留新字段；旧记录缺字段严格回退既有口径，不用当前声明或 import 图补历史。保留整仓事实，分类与存储使用全量路径，展示截断不得参与判定。
4. 在现有测试中加入独立子进程测试，入口为 `rl_exp/tools/launch_recipe.py` 的真实启动路径与 fork 训练器调用的 `manifest.begin`（二者均走 runrecord，未列入口不宣称覆盖）；导入专属文件即失败，并注入此引用证明测试有效。运行期在已有 `after_env`（`manifest.py:499`，已 `ctx.flush`/`ctx.fail`）检查 `sys.modules` 中模块的实际文件路径，命中专属清单就将 run 记为范围违例，复核不得忽略该违例；验收记录补一次真 run 读数，不只靠单元测试。模块记录仅称“已观察依赖”，只作反证、不作放行依据；未命中不代表完整独立，不承诺学习前识别后续延迟导入。
5. 真实路径采集使用 `git diff --name-only --no-renames -z HEAD`，让重命名两端以删除/新增纳入判定；删除训练依赖仍阻塞。临时 git 仓覆盖跟踪、未跟踪、删除、重命名、超过展示上限、声明文件自改、共享 `host_paths.py`、配置/资产、旧字段缺失、材料往返及事后修改声明。覆盖 `RL_ALLOW_DIRTY_TREE` 有无理由：仅显式理由放行并记偏差，不改变分类、不免除归档责任或范围违例。回归必须修复前失败、修复后通过，不能只构造 provenance 字典。
6. 限定拒绝措辞为当前依赖追溯缺口（`manifest.py:482`、`README.md` “开训前置”段的“永远无法证明”），同步仓根 `README.md` 该段；运行相关仓库闸门。复读命令、结果及边界唯一归 `acceptance/records/`，同次更新 evidence 指针。明确 after_env 之后的延迟导入、未进入 `sys.modules` 的动态加载及被 `.gitignore` 忽略却实际读取的配置仍未覆盖。完成后置 pending_review，交不带执笔历史的新上下文审核。

## 关闭条件

- **审核者与输入**：新上下文核对实现、临时仓测试、子进程及运行期反证；审核专属声明，不以未观察到引用或格式通过证明独立。
- **可观察验收**：上述用例可复读；散文和获准 eval 的三处判定一致，声明及共享文件不被豁免，范围违例被记录并影响复核，截断不丢判据，历史分类不被当前文件改写，override 不冒充可重建。
- **交付与边界**：向评级事项交付已审专属声明、T0 清单读法及旧格式规则；保留观察盲区与未完动作，不宣称依赖完整、训练成功或评级完成。剩余动作迁移须同次建立承接项。
- **结果处理**：通过审核后关闭；可修缺口退 in_progress，仅用户能解决的缺口置 blocked。
