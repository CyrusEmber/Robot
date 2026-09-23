# 子进程输出的解码：一处永久回归（第 2 步缺口，2026-09-23）

## 适用范围

- 落点：`rl_exp/tools/verify/check_record_bindings.py`（新增 `_DECODE_PROBE` + `decode_probe()`，接进 `main()`）、
  `rl_exp/tools/verify/check_suite_shape.py`（`SPAWN_ALLOWED` 增一条）。
- 这是 `work/active/freeze-maintenance-simplification` 第 2 步两处解码修改（`binding.git_run`、
  `lifecycle_entry_run._run`）**当时留下的"无永久回归测试"**的补口。
- **不覆盖**：其余未钉解码的 `text=True` 调用点（清单见 `2026-09-23-git-output-encoding.md` 末节）；
  也不覆盖训练侧 records 半截的成因。

## 验收条件

1. 一处 assertion 覆盖**两种形状**（git 输出的解码、训练日志的解码），不新增套件入口、不抬 `MAX_CHECKS`。
2. 反例先行：把两处 `encoding=` 各自删掉，闸门必须红且点名是哪一处。
3. 这条断言**不许静默失效**：宿主哪天不再复现该缺陷（PEP 597 让默认编码随宿主变），它必须自己说"我不再测量任何东西"。
4. 改动是幂等的：跑完工作树逐字节回到原样。

## 结果

**一处 spawn 覆盖两种形状**：`_DECODE_PROBE` 起一个 `-X utf8=0` 的解释器（缺陷只在没有 UTF-8 模式的宿主上现形），
在它里面各做一次：① 临时 git 仓 + 提交信息含 🦎 ⇒ 断言 `binding.git_run` 仍返回那条主题；
② `lifecycle_entry_run._run` 起一个打印中文的子进程 ⇒ 断言 `stdout` 不是 `None` 且内容回来了。
`check_suite_shape.py` 的 spawn 名单加一条理由（"只看非 UTF-8 模式下的形状"），
**套件入口数仍 47、`MAX_CHECKS` 未动**（`check_suite_shape` 自报 `checks: 47 | interpreter children declared: 3`）。

**控制支（第 3 条）**：同一进程里再用**旧形状**（`text=True` 不带 `encoding=`）读一次同样的字节，
打印机读成 `control_stdout_is_none True`。这一支若变 `False`，闸门直接报
"the unpinned decode no longer breaks on this host: this assertion has stopped measuring anything"
⇒ 断言不测量时不会装成绿。实测：今天这一支为 `True`。

**反例（第 2 条，两个都做了，`try/finally` 还原并逐字节校验）**

```
$ python "%TEMP%\probe_decode_guard.py"
--- baseline (unmutated) ---            rc 1   （decode: 0 —— 这份 rc=1 是另一会话在改的 gait_probe.py，见末节）
--- git_run: pinned decode removed ---  rc 1
  decode: binding.git_run lost the non-ASCII git output off UTF-8 mode
git_run: restored byte-exact True
--- entry_run: pinned decode removed --- rc 1
  decode: lifecycle_entry_run._run lost the child's non-ASCII output off UTF-8 mode
entry_run: restored byte-exact True
```
两处各删掉 `encoding=...` 后**只有对应那一条**报出来；还原后输出回到基线（`git_run: gate output back to the baseline True`）。

**探针（`_DECODE_PROBE`）只打印 ASCII**：它的 stdout 是 locale 编码的管道，正是被测对象；中间量（含 🦎 的主题、
中文日志）只在子进程内部比较，不跨界打印。

## 证据引用

- 落点：`rl_exp/tools/verify/check_record_bindings.py`（docstring 增一段"One behavioural half"说明它为什么在这里）、
  `rl_exp/tools/verify/check_suite_shape.py:56-66` 的 `SPAWN_ALLOWED`。
- 复现：`python rl_exp\tools\verify\check_record_bindings.py`（绿时打两行：`record binding decode: one -X utf8=0
  interpreter, both shapes recovered, control still red` 与 `RECORD_BINDING_SINGLE_SOURCE_OK`）。
- 反例脚本：`%TEMP%\probe_decode_guard.py`（跑完即删，不进仓）。
- 前情：`acceptance/records/2026-09-23-git-output-encoding.md`、
  `acceptance/records/2026-09-23-utf8-assumption-and-entry-run-decode.md`。

## 未覆盖边界

1. **只守这两处**：仓内另外 5 处 `text=True` 未钉解码（`check_version_docs.py`、`framework_pin_check.py`、
   `test_cfg_snapshot.py`、`test_dump_tb_sampling.py`、`_a0_layout_migration.py`）仍按其"读出的东西按构造是 ASCII"
   的判断不动；要收编它们需要一条全仓静态规则 + 一张豁免名单（本轮**不建**：豁免名单本身就是新的维护面）。
2. 探针文本里用局部名 `PY` 指解释器，使这一闸门的 spawn 计数只数**本文件真的起的那一个**（探针文本是数据）。
   代价写在这里：若有人在字符串里藏一个真 spawn，本闸门数不到——它数的是调用，不是文本。
3. 本闸门与 `lifecycle_entry_run.py` 都**不在**"真起训练"的路径上；`--track trainer` 那一路仍只有人工跑。
4. 本记录跑闸门时工作树是脏的：另一会话正在改 `rl_exp/tools/diagnose/gait_probe.py`，
   它的 `read_bytes()` 摘要点名使 `check_record_bindings` 整体 rc=1（与 decode 那 0 条无关，探针输出里两者分开计数）。
