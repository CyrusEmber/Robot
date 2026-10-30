# 闸门准入判据：既有检查扩展的观察证据（2026-10-30）

## 适用范围

`work/active/gate-admission-rule.md`。用户选择修改关闭条件，以提交 `3420339` 对既有离线检查的扩展作为观察对象，不再等待首个新增套件条目。本记录不是独立审核结论。

## 验收条件

- `AGENTS.md` 和 `rl_exp/tools/verify/OFFLINE_CHECKS.md` 可读到来源缺陷、破坏测试和声明一致与行为成立的区别。
- 独立审核者对照提交及真实缺陷证据，核对选定扩展的来源、类别和反证，区分模拟调度行为与真实仿真能力。

## 结果

- 规则采纳后的可见历史中未发现新的 `CHECKS` 进程条目。`3420339` 改写已有 `test_eval_record.py` 的标签与受保护产物，新增断言但没有增加套件项；不能当作原关闭条件的首条新增项。
- `3420339` 的提交信息引用 `acceptance/records/2026-10-10-isaac-root-parameterisation.md` 的新训探针一，类别写为 behavior，描述还原完成凭据和 eval 相对入口的两条破坏测试；声称仍为 37 项、该检查约 0.5 秒。该数是扩展后单项耗时，不是增量成本。
- 上述记录保留旧探针缺陷、修复时红绿结果以及后续独立审核；原探针二产物已删除。2026-10-28 的复核和补证对原新训链证据作了限定，不可把替身成功等同于真实仿真成功。
- 是否通过由新上下文审核，不凭记录存在判通过。

## 证据引用

- 规则：`AGENTS.md` 的实现与验证红线；`rl_exp/tools/verify/OFFLINE_CHECKS.md` §4、§6。
- 变更和提交信息：`git show 3420339 -- rl_exp/tools/verify/offline_suite.py rl_exp/tools/verify/test_eval_record.py ablation_harness/run_ablation.py`。
- 来源与原始反证记录：`acceptance/records/2026-10-10-isaac-root-parameterisation.md` 的探针一、闸门裁定、补证及其后独立审核。
- 可见历史复读：`git log --all --full-history --reverse --format="%h %cI %P %s" a7fff168.. -- rl_exp/tools/verify/offline_suite.py`，逐提交核对 `CHECKS` 实际差异；规则提交 `a7fff168` 之前发生的套件变更不能据提交时间认作规则之后。

## 未覆盖边界

- 首条新增套件项未观察到，未来新增条目仍须按 §4 审查；既有项扩展不验证新增进程准入的实际执行。
- 准入无机器看守；本次未回溯存量。命中史统计另由 `work/active/gate-hit-history.md` 跟进。
- 当时测试替换了仿真子进程及共享路径，不能发现未来训练器保存契约漂移；本记录未重新运行仿真，也不声称所有策略及评测成立。
