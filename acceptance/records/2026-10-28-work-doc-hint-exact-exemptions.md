# 历史指针逐条核对与精确豁免（2026-10-28）

## 适用范围

- `work-doc-hint-scan-scope`：对本次扫描的八条版本文档 HINT 逐条核对；执行者记录，不是独立审核。
- 用户选择逐条精确豁免；不改写冻结版本文件，不以退休、目录或目标路径整体豁免。

## 验收条件

- 仅核准文件路径、行号、确切整行内容和引用路径全部匹配的历史引用；其他引用继续报 HINT。
- 回归自测先红后绿；验证文字变化、行移动、同目标不同文档及活文档，保留范围、去重和破坏测试。
- 新上下文根据实际实现、证据和改变后的事项条件独立审核。

## 结果

- 核准 `rl_exp/versions/lizard/baseline/v2/PLAN.md:51`：开训前方案要求探针复测，属该次训练前的历史上下文；探针实际上未做，不以豁免声称前置已完成。
- 核准 `rl_exp/versions/lizard/baseline/v2/PLAN.md:67`：冻结验收协议、不得开训的训练前约束；协议 v3 与训练结果见 NOTES 和闭项，不将该历史措辞作为当前路由。
- 保留 `rl_exp/versions/lizard/ACCEPTANCE.md:70`：明确指导经事项找记录，是导航。
- 保留 `rl_exp/versions/lizard/baseline/v1/NOTES.md:182`：下一次启动复验及事项入口，仍有导航成分。
- 保留 `rl_exp/versions/lizard/baseline/v2/NOTES.md:45`：记录缺口归属入口，有导航成分。
- 保留 `rl_exp/versions/lizard/main/v14/NOTES.md:3`：历史 run 影响核认入口，有导航成分。
- 保留 `rl_exp/versions/lizard/OBS.md:12`：待补事项入口，属于活文档导航。
- 保留 `rl_exp/versions/lizard2/main/v2/PLAN.md:91`：预注册风险但“处置见”可能仍是路由，不确定不豁免。
- 原条件要求冻结证据类不扫描；用户选定的折衷仅对经核准的两行静默，其他版本历史引用仍扫描，不声称实现了自动识别全部冻结证据。验收记录目录原有整类豁免不变。
- 先加完整夹具、未实现豁免运行 `--self-test`：`WORK_DOCS_SELF_TEST_DRIFT (2)`，两条核准行均未静默；加入实现后 `WORK_DOCS_SELF_TEST_OK`、实际扫描 `WORK_DOCS_OK`，八条变六条。执行时 94 事项，数量非固定基线。
- 内存撤销精确条目：`WORK_DOCS_SELF_TEST_DRIFT (2)`；还原旧范围及前缀匹配：`WORK_DOCS_SELF_TEST_DRIFT (11)`；撤销记录目录豁免：`WORK_DOCS_SELF_TEST_DRIFT (1)`；撤销去重：`WORK_DOCS_SELF_TEST_DRIFT (1)`。均为预期红灯，未修改文件。

## 证据引用

- `rl_exp/versions/lizard/baseline/v2/PLAN.md:44` 是开训前验收，`rl_exp/versions/lizard/baseline/v2/NOTES.md:22` 明说探针未做、协议已冻结，`:38` 记实跑、`:41` 记 manifest 缺口；`work/closed/2026/baseline-eval-protocol-gap.md` 记协议闭项及未覆盖项；`acceptance/records/2026-09-23-baseline-v2-first-run.md` 是首跑证据。
- `rl_exp/tools/verify/check_work_docs.py` 的 `_HISTORICAL_REFS`、`_inbound_hints`、`self_test`；前次范围及去重修复与破坏测试见 `acceptance/records/2026-10-28-work-doc-hint-scope-repair.md`、`acceptance/records/2026-10-28-work-doc-hint-noise-reduction.md`。
- 仓根 Windows CMD 复读（第一条绿，其余预期退出码 1）：

```bat
python -B rl_exp\tools\verify\check_work_docs.py --self-test
python -B -c "import sys;sys.path.insert(0,'rl_exp/tools/verify');import check_work_docs as w;w._HISTORICAL_REFS=set();sys.exit(w.self_test())"
python -B -c "import pathlib,sys;p=pathlib.Path('rl_exp/tools/verify/check_work_docs.py').resolve();s=p.read_text(encoding='utf-8').replace('_FROZEN_REFS = (\"acceptance/records\",)', '_FROZEN_REFS = (\"rl_exp/versions\", \"acceptance/records\")').replace('any(path.is_relative_to(_REPO / scope) for scope in _FROZEN_REFS)', 'rel.startswith(_FROZEN_REFS)');n={'__file__':str(p),'__name__':'work_docs_scope_red'};exec(compile(s,str(p),'exec'),n);sys.exit(n['self_test']())"
python -B -c "import sys;sys.path.insert(0,'rl_exp/tools/verify');import check_work_docs as w;w._FROZEN_REFS=();sys.exit(w.self_test())"
python -B -c "import pathlib,sys;p=pathlib.Path('rl_exp/tools/verify/check_work_docs.py').resolve();s=p.read_text(encoding='utf-8').replace('if ref in seen or (_REPO / ref).exists():','if (_REPO / ref).exists():');n={'__file__':str(p),'__name__':'work_docs_duplicate_red'};exec(compile(s,str(p),'exec'),n);sys.exit(n['self_test']())"
```

## 未覆盖边界

- 六条保留不等于已经判定均为活路由；不因提示修改冻结文件。其他未扫描、不可读、超过大小上限的文件及代码/配置不在此检查覆盖内。
- 行号漂移或内容改变恢复 HINT，是安全退化；人工核准可能过时，未来证据变化需重审。精确条目不会自动发现其他历史痕迹。
- 训练侧 manifest 不完整、开训前探针未做；本次不验证物理表现或补做实验。
- 新上下文独立审核尚未发生；本记录不构成审核通过或关闭结论。
