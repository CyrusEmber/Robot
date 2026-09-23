# git 输出解码钉死在 UTF-8（第 2 步第四类，2026-09-23）

## 适用范围

- 落点：`rl_exp/tools/runrecord/binding.py` —— `git_run` 的子进程调用补 `encoding="utf-8", errors="replace"`，
  并把失败形态写进 docstring。属 `work/active/freeze-maintenance-simplification` 第 2 步第四类。
- **不覆盖**：仓内其它 7 处同形状调用（清单见末节）；也不覆盖第 2 步第三类（开训前协议绑定，blocked）。

## 验收条件

1. **反例先行**：在非 UTF-8 模式的宿主上，非 ASCII 的 git 输出必须崩，且崩的**样子**要写下来
   （崩得含糊本身就是这条要修的东西）。
2. 修后同一探针在两种模式下都返回原文。
3. 不得把失败改成静默 `""`：那会让"git 答不出来"与"解码失败"混为一谈，比崩更坏。
4. 套件入口数与 `MAX_CHECKS` 不增。

## 结果

**环境事实（决定了缺口为什么至今没被抓到）**：本机 `locale=cp936`、`sys.flags.utf8_mode=1`。
`text=True` 不带 `encoding` 时按 `locale.getencoding()` 解码（PEP 597：UTF-8 模式下才用 UTF-8），
所以缺口在**本机默认潜伏**，只在没有 UTF-8 模式的宿主上现形。

**反例**（临时探针：临时 git 仓 + 提交信息含 🦎，`python -X utf8=0`）：

```
UnicodeDecodeError: 'gbk' codec can't decode byte 0xa6 in position 14: illegal multibyte sequence
（异常抛在 subprocess 的读取线程里，只打到 stderr）
utf8_mode=0 locale=cp936
git_run raised: AttributeError 'NoneType' object has no attribute 'strip'
```

要害有两层：真正的起因**不进异常链**（线程里吞掉，只留 stderr 一行）；调用方拿到的是一个关于
`strip` 的 `AttributeError`，既没提 git 也没提编码，而 `except (OSError, CalledProcessError)` 也抓不到。

**对照**（同一探针、默认模式）：`utf8_mode=1 locale=cp936` → `git_run returned: 'twin probes 🦎 attach'`。

**修法**：按仓内既有惯例钉住解码 —— `declare_family.py:585`、`test_declare_family.py:80`、
`offline_suite.py:236-238` 等 7 处早就是这么写的（`encoding="utf-8", errors="replace"`）。
本次照抄该形状，**不改契约**（仍返回字符串或空串），并在 docstring 里写明"左给宿主 locale 就会崩成
一个不提编码的 AttributeError"。

**修后**：`python -X utf8=0` 与 `python` 两种模式都 `git_run returned: 'twin probes 🦎 attach'`。

**一个否定结果（写下来省后来人）**：**无法**用"非法 UTF-8 的提交信息"在本机默认模式下复现 ——
git 会把提交信息规范化成 UTF-8（写进去的 `\xa6` 出来是 `\xc2\xa6`），所以这条依赖的是
"宿主没有 UTF-8 模式"这一**环境属性**，不是输入字节的属性。

**没有留下永久回归测试**，理由与留给 owner 的选择：在本机复现必须起一个 `-X utf8=0` 的子解释器，
而套件形状闸门对"每个文件允许起几个解释器"有名单加理由（`check_suite_shape.py:58,74`）——
为一个编码 kwarg 去改那张名单会把它的含义稀释掉（它的理由栏问的是"把 falsifier 放最后为何不能保住覆盖"，与本因无关）。

## 证据引用

```
$ python -c "import locale,sys;print(locale.getencoding(), sys.getdefaultencoding(), sys.flags.utf8_mode)"
cp936 utf-8 1

$ python -X utf8=0 "%TEMP%\probe_git_encoding.py"          # 修前
Exception in thread Thread-7 (_readerthread):
UnicodeDecodeError: 'gbk' codec can't decode byte 0xa6 in position 14: illegal multibyte sequence
utf8_mode=0 locale=cp936
git_run raised: AttributeError 'NoneType' object has no attribute 'strip'

$ python "%TEMP%\probe_git_encoding.py"                     # 修前对照：潜伏
utf8_mode=1 locale=cp936
git_run returned: 'twin probes 🦎 attach'

$ python -X utf8=0 "%TEMP%\probe_git_encoding.py" && python "%TEMP%\probe_git_encoding.py"   # 修后
utf8_mode=0 locale=cp936
git_run returned: 'twin probes 🦎 attach'
utf8_mode=1 locale=cp936
git_run returned: 'twin probes 🦎 attach'

$ python "%TEMP%\probe_git_encoding_v2.py"                  # 否定结果：git 规范化了那对字节
byte check: b'twin probes \xc2\xa6 attach\n'
--- old shape (text=True, locale decides) ---
returned: 'twin probes ¦ attach\n'

$ rl_exp\tools\verify\run_offline_checks.bat
ALL_OFFLINE_CHECKS_PASSED (47/47 in 45.6s, wave 232s/informational, jobs=6)
```

两个探针脚本放在 `%TEMP%`，跑完即删（不进仓）。

## 未覆盖边界

- **同形状的其它调用点**（`findstr /s /c:"text=True"` 实数，逐处是否另有 `encoding=` 未核）：
  `rl_exp/tools/verify/check_version_docs.py:161`、`framework_pin_check.py:238/351/360`、
  `rl_exp/tools/verify/lifecycle_entry_run.py:54`（**这条跑训练**，输出里本来就有中文，风险最高）、
  `test_cfg_snapshot.py:170`、`test_dump_tb_sampling.py:76/88`、`_a0_layout_migration.py:97/236`。
  本类按计划只钉 `binding.git_run`；是否收敛到一处或统一补，由 owner 定（那会引入一处抽象，不在本类要求内）。
- 无永久回归测试（理由见上）；要加，最省的形状就是上面那张 spawn 名单加一条，并把理由写成"本因是宿主编码属性"。
- `errors="replace"` 会把无法解码的字节变成 U+FFFD：若某天真有非 UTF-8 文件名进入"changed paths"，
  它会与磁盘名失配。取此舍彼的理由是仓内惯例一致且 JSON 安全（`surrogateescape` 会带进无法编码的字符）。
- 第 2 步第三类（开训前协议绑定）仍 blocked：等形态拍板 + `baseline-eval-protocol-gap` 的 v2 首跑；
  且那两个事项互相 `depends_on`（环，闸门不查环，见 `work/active/freeze-maintenance-simplification.md`）。
