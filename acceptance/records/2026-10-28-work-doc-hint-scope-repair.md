# 指针扫描范围修复验证（2026-10-28）

## 适用范围

- `work-doc-hint-scan-scope` 的扫描范围修复及独立审核发现的反例；这是执行者记录，不是复审结论。
- 原始缺陷与审核过程分别见 `acceptance/records/2026-10-10-work-doc-hint-scope.md`、`acceptance/records/2026-10-28-work-doc-hint-scope-review.md`；历史记录不改写。

## 验收条件

- 记录目录及其后代排除，普通文档、相邻同名前缀目录和版本树文档仍扫描；前后对照与破坏测试均可复读。
- 冻结版本文档和回填 NOTES 的历史引用不被当作可自动修正的活引用；HINT 不改变检查退出码。

## 结果

- `_FROZEN_REFS` 仅排除 `acceptance/records/` 及后代，按路径组件判断，不排除 `acceptance/records-live/`。版本树不按路径、锁、tag 或退休状态豁免：家族/线根/提案版本 PLAN、已冻结版本 PLAN、版本 NOTES 均扫描；`rl_exp/versions-live/` 也扫描。
- 先加夹具、旧实现实跑自测红：七个预期命中缺失，`WORK_DOCS_SELF_TEST_DRIFT (7)`。修复后自测绿；记录目录含嵌套夹具不命中，普通活指针仍命中。以下内存还原旧实现的命令可在现有代码上重现同样七处红，不改仓库文件。
- 内存撤掉记录目录豁免后，`FALSIFIER: the pointer scan read a dated evidence record`，`WORK_DOCS_SELF_TEST_DRIFT (1)`，退出码 1。保留原缺陷的破坏测试。
- 修复后 `--self-test` 落入实际检查，`WORK_DOCS_SELF_TEST_OK`、`WORK_DOCS_OK (93 item file(s))`；输出 9 条版本树 HINT，其中同一 Markdown 链接的可见文本和目标各命中一次。它们不是自动改写清单；部分是历史引用，是否为活路由须人工判断。

## 证据引用

- 落点与持久夹具：`rl_exp/tools/verify/check_work_docs.py` 的 `_FROZEN_REFS`、`_inbound_hints`、`self_test`；目录与生命周期参见 `.codemaker/rules/versioning.mdc`、`rl_exp/tools/verify/_a0_paths.py`。
- 仓根执行（Windows CMD；红灯和破坏测试预期退出码 1，绿灯预期 0）：

```bat
:: 内存还原旧版扫描范围，夹具应红
python -B -c "import pathlib,sys; p=pathlib.Path('rl_exp/tools/verify/check_work_docs.py').resolve(); s=p.read_text(encoding='utf-8').replace('_FROZEN_REFS = (\"acceptance/records\",)', '_FROZEN_REFS = (\"rl_exp/versions\", \"acceptance/records\")').replace('any(path.is_relative_to(_REPO / scope) for scope in _FROZEN_REFS)', 'rel.startswith(_FROZEN_REFS)'); n={'__file__':str(p),'__name__':'work_docs_red'}; exec(compile(s,str(p),'exec'),n); rc=n['self_test'](); print('EXIT',rc); sys.exit(rc)"
:: 自测及实际检查应绿
python -B rl_exp\tools\verify\check_work_docs.py --self-test
:: 破坏记录豁免，夹具应红
python -B -c "import sys;sys.path.insert(0,'rl_exp/tools/verify');import check_work_docs as w;w._FROZEN_REFS=();sys.exit(w.self_test())"
```

## 未覆盖边界

- 版本树 HINT 可含历史痕迹；冻结 PLAN 与历史证据不可因提示而改写。工具不判文档生命周期，也不判某一条引用是否活路由。
- 仅扫描可读取、大小不超过阈值的 Markdown；不扩至代码或配置，`work/closed/` 散文仍扫描。
- 原始全仓 HINT 归零结论不适用于扩大扫描后的现状；误报噪声和缺失活路由须人工核实，不声称所有引用均被自动判别。
- 复审尚未发生；新上下文须对照落点、证据与事项关闭条件复核。
