# 离线闸门历史命中调查：最终独立审核（2026-10-30）

## 适用范围

新上下文对 `gate-hit-history` 的关闭条件、调查记录及两轮审核缺口进行独立复核，范围固定为基线 `657924efe102a5156c3f9279c19756b053ed82bd`。本记录适用于本次审核的调查快照。

## 验收条件

对照 37 项清单与原始历史核实命中、未知和人为反例；复核方法、复读入口、前次审核缺口与未完动作。

## 结果

**通过。** 固定基线和调查表均为 37 项，按脚本名无漏重；2 项有记录支持的真实命中、35 项未知，属定向检索下限，不是命中率。首次审核要求的分类、时间、候选和检索入口均已处理；二审所指配置锁证据冲突已明确披露并归未知。未发现必须另立的持续统计或治理动作。

- `check_dr_parity.py --strict`：`7acc84f` 的原记录记载干净 checkout 中资产锁因 EOL 不一致而漂移、既有检查报红；其父提交已有对应套件项和字节摘要检查，基线承接。不同 checkout 的漂移数不构成独立缺陷。原始红测 stdout 未确认入库。
- `check_golden_frozen.py`：`bbedd96` 的原记录记载重锚脚本误用 LF 文本视图计算摘要，既有检查报 `GOLDEN_FROZEN_DRIFT`；其父提交已有套件项和字节摘要比较，基线承接。记录标题为 9 月 17 日、相关提交为 9 月 18 日，确切报红日期未独立确认。原始红测 stdout 未确认入库。
- `check_cfg_lock.py`：原始记录称训练范围误写，拆分记录摘要又称夹具或断言写错；历史套件身份与单项执行虽有支持，缺陷性质仍无法消解，归未知。
- `check_work_docs.py` 尚待落盘记录及 `check_recipe_build.py` 同次迁移未完成重锚的真实报红，不能据此认定最终交付遗留缺陷。抽查发现绑定扫描误报、地形测试自身编码崩溃和 P005 之后补门也均不应计入真实命中。
- 实际执行调查记录的完整基线 AST 提取及三路检索，外层退出 0、`COUNT 37`；分别核三路退出均为 0，得到名称 629 行、失败词 1068 行、检查路径历史 226 行。命令本身不汇总子进程失败码，未来复读仍需分别核查。

## 证据引用

- `acceptance/records/2026-10-30-gate-hit-history.md`；`acceptance/records/2026-10-30-gate-hit-history-review.md`；`acceptance/records/2026-10-30-gate-hit-history-second-review.md`。
- `git show 7acc84f^:rl_exp/tools/verify/offline_suite.py`；`git show bbedd96^:rl_exp/tools/verify/check_golden_frozen.py`；`git show fb788ba:rl_exp/versions/lizard/ACCEPTANCE.md`；`git blame -L 30,33 657924e -- acceptance/records/2026-09-16-lizard-component-library-b1.md`；`git show 657924e:rl_exp/docs/pitfalls.md`。
- 固定清单和全部名称、失败词及历史检索的可运行复读命令见调查记录的「证据引用」。审核者以计数器比较其清单与报告两表，单项核对两次审核缺口及相关入库记录。
- 本机只读日志 `rl_exp/out/lizard2_v4_offline_suite.log` 与 `rl_exp/out/lizard2_dev_contact_20261022/offline_suite.log` 支持对应中间态与误报；不承诺入仓。

## 未覆盖边界

调查和本次抽查均未穷尽历史或仓外日志。原始红测 stdout 未确认入库，记录叙述不能等同原样回放；未知不等于从未命中或没有价值，不作为删除依据。本次未运行仿真或离线套件。
