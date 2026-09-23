# 入口 harness 的解码，与 "PYTHONUTF8 依赖" 的实测（2026-09-23）

## 适用范围

- 落点：`rl_exp/tools/verify/lifecycle_entry_run.py` 的 `_run`（补 `encoding="utf-8", errors="replace"` + docstring 写明失败形态）。
- 同一次取证包含两个**被测否的假设**：① "仓依赖未写下的 `PYTHONUTF8=1`，所以入口要钉它" —— 实测**否**，因此**不加**；
  ② "只有 `binding.git_run` 一处会读非 ASCII" —— 实测**否**，另有一处会读非 ASCII，见下。
- **不覆盖**：其余 5 处 `text=True` 未钉解码的点（`check_version_docs.py:161`、`framework_pin_check.py:238/351/360`、
  `test_cfg_snapshot.py:170`、`test_dump_tb_sampling.py:76/88`、`_a0_layout_migration.py:97/236`）——它们读出的东西按构造是 ASCII 或被 git 转义，本次不动。

## 验收条件

1. 反例先行：在非 UTF-8 模式的宿主上，`_run` 必须**丢证据**或崩，且形态要写下来。
2. 修后两种模式都拿到原文。
3. 不为"没有反例的假设"加改动：入口是否要钉 `PYTHONUTF8`，先测再定（测否 ⇒ 不加）。
4. 套件入口数与 `MAX_CHECKS` 不增。

## 结果

**一、入口钉 `PYTHONUTF8`：测否，不加。**
`set "PYTHONUTF8=" && rl_exp\tools\verify\run_offline_checks.bat` ⇒ `ALL_OFFLINE_CHECKS_PASSED (47/47 in 67.5s)`。
即：没有该环境变量时套件照样全绿（慢 22s，属冷缓存/IO 波动范围），因为套件的判词是 ASCII、且它在需要处已显式钉了解码
（`offline_suite.py:236-238`、`:491`）。按本项第 4 步纪律"凭反例定去留"，**不为未观测的失败加改动**：`run_offline_checks.bat`
与 `hooks/pre-commit` 均**不动**。仓对一个未写下的环境变量的依赖是**事实**，记在本记录里；要在仓里写死它，正确的形态是散文声明（`FILEMAP`/`OFFLINE_CHECKS.md`），不是给入口加一行 env。

**二、`lifecycle_entry_run._run`：这会丢证据，已修。**
反例（`python -X utf8=0`，探针用 `_run` 的真实调用形状 + 一个打印中文的子进程）：

```
[entry-run] ... python.exe -c print('[run-manifest] 训练启动：中文日志') ... (cwd e:\Robot)
Exception in thread Thread-1 (_readerthread):
UnicodeDecodeError: 'gbk' codec can't decode byte 0xad in position 17: illegal multibyte sequence
rc = 0
stdout is None: True
```

要害不是崩，而是**静默失去证据**：`stdout` 变 `None`、`rc` 仍是 0，而这个 harness 的 docstring 自己写着
"the judgement reads it, so it has to be here" —— 它正是靠读输出判"拒绝/放行"的。真起因只在 stderr 的线程栈里一闪而过。
它是这套里**唯一读真实训练日志**的点（`lifecycle_entry_run.py --track trainer` 会真起训练），而它的用法就是"人直接跑一次"，
没有人会先 `set PYTHONUTF8`。

修法：照仓内惯例钉 `encoding="utf-8", errors="replace"`。修后两种模式 ⇒ `stdout is None: False`、`stdout: '[run-manifest] 训练启动：中文日志\n'`。

**三、可复现的取数命令**（两条都由本节与 `evidence` 给出）：
`set "PYTHONUTF8=" && rl_exp\tools\verify\run_offline_checks.bat`；`python -X utf8=0 <探针>`。

## 证据引用

```
$ set | findstr /i python
PYTHONIOENCODING=utf-8
PYTHONUTF8=1                       # 机器上的环境变量；仓内 grep 不到任何地方钉它

$ python -c "import locale,sys;print(locale.getencoding(), sys.flags.utf8_mode)"
cp936 1

$ set "PYTHONUTF8=" && rl_exp\tools\verify\run_offline_checks.bat
ALL_OFFLINE_CHECKS_PASSED (47/47 in 67.5s, wave 349s/informational, jobs=6)

$ python -X utf8=0 "%TEMP%\probe_entry_run.py"        # 修前
rc = 0
stdout is None: True
（另有 Thread-1 的 UnicodeDecodeError: 'gbk' codec can't decode byte 0xad ... 打在上面）

$ python -X utf8=0 "%TEMP%\probe_entry_run.py" && python "%TEMP%\probe_entry_run.py"   # 修后
rc = 0
stdout is None: False
stdout: '[run-manifest] 训练启动：中文日志\n'
（两种模式输出相同）

$ rl_exp\tools\verify\run_offline_checks.bat          # 改动后复跑
ALL_OFFLINE_CHECKS_PASSED (47/47 in 46.1s, wave 229s/informational, jobs=6)
```

## 未覆盖边界

- **无永久回归测试**，与 `binding.git_run` 那次同一个障碍：本机复现要求"非 UTF-8 模式"，得动套件形状闸门那张
  "每文件允许几个 spawn" 的名单（`check_suite_shape.py:58,74`），而它的理由栏问的是"把 falsifier 放最后为何不能保住覆盖"，
  与本因无关。若 owner 要 guard，**一处** allowlisted spawn 就能覆盖两种形状（起一个 `-X utf8=0` 的子解释器，
  断言 `binding.git_run` 与 `lifecycle_entry_run._run` 都不返回 `None`）——两处的记录里各写了一次，这是第二次。
- `lifecycle_entry_run.py` **不在套件里**（手工 harness，`--track trainer` 会真起训练），所以这次改动只由本节自证 + 复跑套件旁证。
- 其余 5 处未钉点只在"读出的东西按构造是 ASCII"这一判断下不动，**未逐处实测**（`framework_pin_check.py:238` 的通用包装尤其未逐调用核）。
- 仓对 `PYTHONUTF8=1` 的依赖是**环境事实**而非仓内声明；将来若新增会打印非 ASCII 的检查，这条假设会重新浮上来，届时按"是否有反例"再判。
