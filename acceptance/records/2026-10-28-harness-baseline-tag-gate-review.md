# Harness 基线标签闸门独立审核（2026-10-28）

## 适用范围

- 不带执笔历史的新上下文，对 `harness-baseline-tag-gate` 的实际落点、关闭条件、默认检查与破坏测试进行审核。
- 本闸检查本地标签名称与文档声明的一致性，不证明标签指向、远端状态或测量能力。

## 验收条件

- 自测末行为自测判词，默认检查末行为 `VERSION_DOCS_OK`；缺失标签和读不到基线行的两条破坏测试均红，恢复后均绿。

## 结果

**不通过原关闭条件。** 两条破坏测试均红、恢复后均绿，但 `--self-test` 首行才是自测判词，随后继续默认检查，末行为 `VERSION_DOCS_OK`。自测打印的 `13 fixtures` 也没有计入五条基线夹具。

- 真实工作树 `python -B rl_exp/tools/verify/check_version_docs.py --self-test` 退出 0，首行 `check_version_docs: self-test OK (13 fixtures)`，末行 `VERSION_DOCS_OK (coverage docs scanned: 6)`；默认检查退出 0，末行同为 `VERSION_DOCS_OK`。
- 在系统临时目录的隔离仓中，通过真实默认 CLI、复制的实际文档和本地标签名称集合验证：原样退出 0；基线号改为 `v9.9.9` 退出 1，报缺少 `harness-v9.9.9`；恢复退出 0；移除基线全角冒号退出 1，报 `matched 0 time(s)`；再次恢复退出 0。
- 临时仓标签指向临时空提交，只复现标签名称，不证明真实标签指向或远端存在。临时目录已清理，真实 `HARNESS.md` 测试前后内容未改；破坏测试后真实默认检查再次退出 0。
- `0c3ec25` 的基线更新记录缺锚点，`3a86d2e` 标明闸门来源及声明一致类别；这不是行为能力验证。

## 证据引用

- 事项关闭条件：`work/active/harness-baseline-tag-gate.md`；实现与基线夹具：`rl_exp/tools/verify/check_version_docs.py` 的 `baseline_tag_problem`、`baseline_cases` 和 `main`。
- 常规检查复读：

```bat
python -B rl_exp\tools\verify\check_version_docs.py --self-test
python -B rl_exp\tools\verify\check_version_docs.py
```

- 隔离破坏测试复制检查器及其依赖、版本目录、相关文档，并复制真实本地标签名称到临时 Git 仓；每次通过 `python rl_exp/tools/verify/check_version_docs.py` 运行真实入口，恢复文档后逐字节断言并重新运行。
- 远端锚点属于 `work/active/harness-version-anchor-missing.md`，与本地名称检查不等价。

## 未覆盖边界

- 未核验远端标签、真实标签指向或测量语义；家族标签 WARN 不影响本项判定。
- 修正输出和夹具计数后必须由不带执笔历史的新上下文复审；本审核不构成关闭结论。
