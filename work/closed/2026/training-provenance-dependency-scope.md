---
id: training-provenance-dependency-scope
title: 训练来源闸门按实际依赖划定阻塞范围
scope: rl_exp/tools/runrecord, rl_exp/tools/verify, README.md
status: done
landing: rl_exp/tools/runrecord/provenance.py, rl_exp/tools/runrecord/manifest.py, rl_exp/tools/runrecord/rebuild.py
close_when: 不带执笔历史的新上下文按正文判据审核实现与验收证据后决定关闭。
evidence: acceptance/records/2026-11-04-training-provenance-dependency-scope.md
outcome: 独立复审通过训练来源范围；评测、短训缺口及重建评级由现有事项承接。
---

## 当前范围

文件级分类与回归已落地，结果和历史散文口径纠正在 [验收记录](../../acceptance/records/2026-11-04-training-provenance-dependency-scope.md)。本项先审核文件级豁免及 T0 记录；`work/active/verified-rebuild-rating.md` 再据此验收归档内容与评级，本项不接管历史材料补全。

## 承接

- eval 命令与策略观测的时序缺陷由 `work/active/eval-command-observation-timing.md` 承接。
- 短训画面同步、停车恢复零样本和支撑/摆动缺口由 `work/active/v7-short-run-post-train-evidence.md` 承接；材料归档拒绝和未跟踪同源风险由 `work/active/verified-rebuild-rating.md` 承接，不补造 T0。
- 重建回归按用户决定退出默认套件，训练配方打 tag 前单独执行。

## 关闭条件

- **审核者与输入**：新上下文核对实现、临时仓测试、子进程及运行期反证；审核专属声明，不以未观察到引用或格式通过证明独立。
- **可观察验收**：真实 Git 临时仓单独修改每个声明文件及已跟踪散文，依次走真实采集、启动、复核和材料采集；声明与共享 `host_paths.py`、未知代码、配置和资产仍受保护。覆盖未跟踪、删除、双向重命名、超展示上限、声明自改、声明事后变更、旧字段缺失及材料往返；全量路径而非截断展示决定判定。无理由 override 拒绝，有理由记录偏差但不免除受保护内容归档或范围违例。
- **声明与运行期反证**：仅正向声明具体文件，不得用目录或通配符；声明本身受保护。初始清单及每次增删在验收记录逐条检查训练侧（`rl_exp/tasks`、`rl_exp/tools/runrecord`、`launch_recipe.py`、`cfg_snapshot.py`）静态导入、`importlib` 和字符串引用，声明搜索盲区。独立进程运行 launcher 真正交接及 fork 训练器调用的 `manifest.begin`；导入任一声明文件须失败，注入引用证明守卫有效。`after_env` 按 T0 声明与 `sys.modules` 文件路径记录已观察依赖、违例影响复核；补一次真实 run 读数。未观察不作为依赖独立性证明。
- **交付与边界**：向评级事项交付已审专属声明、T0 清单读法及旧格式规则；不新增范围版本、完整依赖集合或摘要，保留整仓事实。保留 `after_env` 后延迟导入、不进 `sys.modules` 的动态加载、被 `.gitignore` 忽略但实际读取配置等观察盲区；不宣称依赖完整、训练成功或评级完成。剩余动作迁移须同次建立承接项。
- **结果处理**：通过审核后关闭；可修缺口退 in_progress，仅用户能解决的缺口置 blocked。
