# 指针扫描的信道被冻结证据占满：按类排除冻结证据（2026-10-10）

## 适用范围

- **被验的缺陷**：`check_work_docs.py` 的指针扫描只按路径豁免 `rl_exp/versions`，`acceptance/records/` 仍在扫描范围内 ⇒ 每关闭一件事就往 HINT 信道里加一条恒噪。真实一次：`34c4917`（关闭 `runtime-acceptance-v3`）之后，全仓 HINT 全部出自该目录。
- **改动**：`_FROZEN_REFS` 增 `acceptance/records`；自测补一条"冻结记录里带过时指针"的 fixture 与其反向断言（活文档一侧的 fixture 早就在）。
- **条件**：仓根 `python rl_exp/tools/verify/check_work_docs.py`（默认检查）与 `--self-test`；纯 stdlib、不起仿真、秒级。
- **不覆盖**：不改冻结证据里已写下的路径；不把 HINT 升级成红闸；不含 `work/closed/**` 散文的同类豁免（当前无命中）。

## 验收条件

1. **基线归零**：改动后全仓 HINT 数为 0，而改动前每一条都出自 `acceptance/records/`。
2. **活文档不受影响**：活文档里出现过时指针仍须出 HINT（自测 `notes/pointers.md` 一侧钉住）。
3. **破坏测试咬住**：把 `acceptance/records` 从 `_FROZEN_REFS` 撤掉，自测必须红在"读了日期证据记录"那条断言上，而不是仍然全绿。

## 结果

| 项 | 改动前 | 改动后 |
|---|---|---|
| 全仓 HINT | 31（`acceptance/records` 31 / 其他 0） | 0 |
| `--self-test` | OK（17 item + 3 record + 3 pointer fixtures） | OK（17 item + 3 record + 4 pointer fixtures） |
| 破坏测试（撤掉 `acceptance/records`） | — | `FALSIFIER: the pointer scan read a dated evidence record` → `WORK_DOCS_SELF_TEST_DRIFT (1)`，exit 1 |

默认检查改动前后都 `WORK_DOCS_OK`（80 个事项文件）。该豁免在离线套件里按 `--self-test` 跑，故破坏测试不是一次性手跑。

## 证据引用

```bat
:: 计数：0 = 基线归零
python -c "import subprocess,sys;out=subprocess.run([sys.executable,'rl_exp/tools/verify/check_work_docs.py'],capture_output=True,text=True).stdout;print('HINT',sum('HINT: ' in l for l in out.splitlines()))"

:: 两侧行为
python rl_exp\tools\verify\check_work_docs.py --self-test

:: 破坏测试：撤掉豁免后自测必须红
python -c "import sys;sys.path.insert(0,'rl_exp/tools/verify');import check_work_docs as w;w._FROZEN_REFS=('rl_exp/versions',);print('exit',w.self_test())"
```

落点：`rl_exp/tools/verify/check_work_docs.py` 的 `_FROZEN_REFS` 与自测指针段；套件登记在 `rl_exp/tools/verify/offline_suite.py`。

## 未覆盖边界

- **不判"剩下的过时引用都该改"**：本次只让扫描不读冻结证据；活文档一侧仍靠人判，这条边界不变。
- **不含 `work/closed/**` 的同类豁免**：那里当前没有命中，要豁免是另一次判断。
- **不改历史**：那批冻结记录里的路径保持原样（改 = 无痕回写证据）。
- 本项钉的是**闸门自身行为**（行为成立类），不是"声明一致"；它不证明任何被扫文档的内容正确。
