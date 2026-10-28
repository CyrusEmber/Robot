# 指针提示降噪验证（2026-10-28）

## 适用范围

- `work-doc-hint-scan-scope` 独立复审后继续减少 HINT 噪声；本记录是执行者结果，不是复审结论。
- 不改写版本历史文档，不以退休或版本目录作为历史引用的可靠分类依据。

## 验收条件

- 同一文件、同一行、同一失效路径仅报告一次；不同文件、不同行或不同路径仍各自报告。
- 版本活文档仍扫描；记录目录豁免与同前缀目录的扫描边界保持。

## 结果

- 重复的 Markdown 链接文本与目标只生成一条 HINT。先加自测运行旧实现得到 `WORK_DOCS_SELF_TEST_DRIFT (1)`；修复后自测 `WORK_DOCS_SELF_TEST_OK`。夹具覆盖同一行不同路径、同路径不同行及不同文件。
- 当前实际检查由 9 条提示变为 8 条，消除的是同一行相同路径的重复；其他提示保留，`WORK_DOCS_OK (94 item file(s))`。数量是执行时工作树的读数，不是固定基线。
- 研究版本文档状态后未采用整条线、退休状态或整个版本目录豁免：版本树里既有活计划也有历史材料，NOTES 可以回填；退休线里也有未训练、可修订的计划。按上述信号统一排除会漏活路由。

## 证据引用

- 实现与持久回归夹具：`rl_exp/tools/verify/check_work_docs.py` 的 `_inbound_hints`、`self_test`；前次修复及独立复审分别见 `acceptance/records/2026-10-28-work-doc-hint-scope-repair.md` 和 `acceptance/records/2026-10-28-work-doc-hint-scope-repair-review.md`。
- 仓根复读：

```bat
:: 当前实现预期自测及实际检查通过
python -B rl_exp\tools\verify\check_work_docs.py --self-test
:: 去掉去重条件，自测应失败；只改变内存中的源码
python -B -c "import pathlib,sys;p=pathlib.Path('rl_exp/tools/verify/check_work_docs.py').resolve();s=p.read_text(encoding='utf-8').replace('if ref in seen or (_REPO / ref).exists():','if (_REPO / ref).exists():');n={'__file__':str(p),'__name__':'work_docs_duplicate_red'};exec(compile(s,str(p),'exec'),n);sys.exit(n['self_test']())"
```

## 未覆盖边界

- 去重不能判别历史引用；剩余版本树 HINT 仍含历史痕迹，不能自动改写。
- 尚未找到既排除所有冻结版本证据、又不漏活文档的可靠自动分类；原关闭条件尚未满足，继续查找可验证边界。
- 修改后须由不带执笔历史的新上下文复审；本记录不构成关闭结论。
