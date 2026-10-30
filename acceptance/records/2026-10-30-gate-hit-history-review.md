# 离线闸门历史命中调查：独立审核（2026-10-30）

## 适用范围

对 `work/active/gate-hit-history.md` 在待审时的关闭条件、基线 `657924efe102a5156c3f9279c19756b053ed82bd` 及首版 `acceptance/records/2026-10-30-gate-hit-history.md` 作新上下文独立审核。后续调查记录修订须另行重审；本记录不代表修订后的审核结果。

## 验收条件

核对基线清单是否全覆盖、真实命中定义及原始证据；抽查命中和未知分类、可复读方法、人工反例及未完成动作。

## 结果

**拒绝关闭，退回补证。** 基线有 37 项，首版列出 4 项命中、33 项未知，名称无遗漏或重复；但统计口径与证据不足，不能采纳该计数。

- `check_dr_parity.py` 的 EOL 导致资产锁漂移有当时记录，支持真实命中；原始失败 stdout 未定位，不能声称已验原日志。
- `check_work_docs.py` 实际对缺失记录报错，基线承接该检查；但它可能是同次交付期间的临时状态，需明确是否将这类状态计为缺陷，不能当作已交付悬空指针。
- `check_golden_frozen.py` 的错误摘要有当时记录，区别于合法重锚；记录标题标 9 月 17 日，相关提交 `bbedd96` 日期为 9 月 18 日，需澄清事件时间而非混为一谈。
- `check_recipe_build.py` 对入口与 golden 不一致确实报红，但现有证据称这是合法迁移及同次重锚过程；未证明完成后遗留非预期缺陷，不能据此计作真实缺陷命中。
- `check_cfg_lock.py` 的未知项需要定向复核：`acceptance/records/2026-09-16-lizard-component-library-b1.md` 的「切片 4 · commands」记录既有配置锁发现训练速度范围误写并修复；需核当时执行、套件身份及当前承接。
- P003/P004、P005 是来源而非既有检查命中；`check_record_bindings.py` 的真实报错是误扫历史源码快照；`test_terrain_geometry.py` 的编码异常是检查自身失败。抽查支持首版对这些例子的排除。
- 原复读命令只列少数名称，不足以复读声称的全清单定向检索；需提供覆盖全部 37 项及候选失败词的只读入口和人工分类方法。审查不要求穷尽所有历史。

## 证据引用

- 基线清单：`git show 657924e:rl_exp/tools/verify/offline_suite.py`；对应历史通过 `git show`、`git log`、`git grep` 核对。
- `acceptance/records/2026-09-20-lizard-baseline-line-eol-and-fixed-window-eval.md` 的「摘要对 EOL 敏感」；`acceptance/records/2026-10-10-pending-review-before-close.md` 的结果条件 4；`acceptance/records/2026-09-16-lizard-frozen-baseline-reanchors.md` 的「B0 追加②」「B0 追加③」。
- 审核者只读核过本机 `rl_exp/out/lizard2_v4_offline_suite.log` 中缺失审核记录的实际套件失败、`rl_exp/out/lizard2_v4_golden_pin_before.log` 中合法重锚的预期漂移；这些本机产物未承诺入仓。
- 基线实现：`git show 657924e:rl_exp/tools/verify/check_dr_parity.py`、`check_work_docs.py`、`check_golden_frozen.py`、`check_recipe_build.py`；`git show --stat a526276 -- rl_exp/tools/verify/check_recipe_build.py`、`git show --stat 27ca424`。
- 排除证据：`rl_exp/docs/pitfalls.md` P003–P005；`acceptance/records/2026-10-22-record-binding-source-scope.md`；`acceptance/records/2026-10-30-lizard2-foot-control-tiprise-review.md`。

## 未覆盖边界

未运行仿真或离线套件；未穷尽全部可达历史与仓外日志。记录叙述不等于原始日志可复读；声明一致的有效检查也不证明训练或物理行为成立。修订证据后的结论必须重审。
