# 离线闸门历史命中调查：修订后独立重审（2026-10-30）

## 适用范围

对 `work/active/gate-hit-history.md` 修订后的调查、首次审核缺口及固定提交 `657924efe102a5156c3f9279c19756b053ed82bd` 进行新上下文重审。结果仅针对重审时快照；后续修改须再审。

## 验收条件

独立复核全部基线条目、真实命中分类与原始证据、首次审核缺口、可运行的检索入口及未完成动作。

## 结果

**拒绝关闭，退回补证。** 基线有 37 项，调查表 3 项命中、34 项未知，逐项无遗漏、重复或额外项；但 `check_cfg_lock.py` 命中的缺陷性质仍有冲突。

- `check_dr_parity.py` 的 EOL 资产锁漂移、`check_golden_frozen.py` 重锚时误写字节摘要均有历史记载，历史检查先存在且基线仍承接对应比较；原始红测 stdout 均未定位。后者记录标题与相关提交日期不同，修订记录已披露确切报红时间未独立确认。
- `check_cfg_lock.py` 的历史套件身份、实际单项执行与基线同类比较机制有支持，但 `acceptance/records/2026-09-16-lizard-component-library-b1.md` 第 32 行称切片 4 为夹具/断言写错，161、167 行却称组件训练范围首版误写。原始提交 `fb788ba` 保留后一叙述，第 32 行由 `37e5df6` 加入；缺陷性质不能不解释矛盾而定论。若无法消解，应归未知并重算。
- `check_work_docs.py` 与 `check_recipe_build.py` 的同次变更中间红态按修订口径不计，合理；抽查绑定扫描误报、腿链单项先于入套件和地形测试自身编码失败，未知分类合理。
- 全清单检索入口已实际执行：`COUNT 37`，名称检索、失败词检索和路径历史查询均退出 0，分别 629、1068、226 行；人工分类仍非穷举。未发现需要另建持续统计事项。

## 证据引用

- 调查记录 `acceptance/records/2026-10-30-gate-hit-history.md`；首次审核 `acceptance/records/2026-10-30-gate-hit-history-review.md`。
- `git show 657924e:rl_exp/tools/verify/offline_suite.py`；调查记录中的 AST 提取和检索命令；`git show fb788ba:rl_exp/versions/lizard/ACCEPTANCE.md`；`git log` 与 `git blame` 对照记录拆分提交 `37e5df6`。
- `acceptance/records/2026-09-16-lizard-component-library-b1.md` 的内部作废关系及「切片 4 · commands」；`acceptance/records/2026-09-20-lizard-baseline-line-eol-and-fixed-window-eval.md`；`acceptance/records/2026-09-16-lizard-frozen-baseline-reanchors.md`。
- 审核者只读本机 `rl_exp/out/lizard2_v4_offline_suite.log` 和 `rl_exp/out/lizard2_dev_contact_20261022/offline_suite.log`，两者均不承诺入仓。

## 未覆盖边界

未运行离线套件或仿真；未穷尽历史及仓外日志。已有记录叙述不等于原始日志可复读，未知不等于无用；不能根据本调查删除检查。
