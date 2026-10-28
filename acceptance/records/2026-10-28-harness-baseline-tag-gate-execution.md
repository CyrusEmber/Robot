# Harness 基线标签闸门修正执行记录（2026-10-28）

## 适用范围

执行者修正 `work/active/harness-baseline-tag-gate.md` 的独立审核问题；本记录不是独立复审。上一轮审核见 `acceptance/records/2026-10-28-harness-baseline-tag-gate-review.md`。

## 验收条件

自测成功末行为自测判词，默认检查成功末行为 `VERSION_DOCS_OK`；自测仍执行真实默认检查，任何失败均非零；真实 CLI 在隔离副本缺标签和基线行时失败、恢复后通过。

## 结果

- 自测实际夹具：覆盖判词 4、正文状态 3、标题状态 4、文件件套 2、基线与 tag 5，共 **18**。此前 13 漏了基线 5。自测在默认检查前执行，成功输出暂存，默认检查成功后再输出；自测失败立即报告并返回 1，默认检查失败仍报告 `VERSION_DOCS_DRIFT` 并返回 1。
- 红绿：先写下方隔离测试并运行，修复前测试脚本退出 1：`self-test` 和 `line-restored-self-test` 两项末行仍为 `VERSION_DOCS_OK`，而非 18 夹具自测判词。修复后退出 0；扩展 tree 和自测失败反证后再次退出 0。红测时这两项均实际执行了真实默认检查并退出 0，失败的是测试断言。
- 破坏测试：临时仓复制真实 `HARNESS.md`、版本目录、检查器依赖、覆盖文档和 **24 个真实本地 tag 名**；当次实际基线 `v1.11.0`。删除临时仓 `harness-v1.11.0` 后，默认与 `--self-test` CLI 都退出 1，包含缺标签提示，末行为 `VERSION_DOCS_DRIFT (1)`；恢复 tag 后默认退出 0。删除临时文档基线行的全角冒号后，两种 CLI 均退出 1，包含 `matched 0 time(s)`，末行为 `VERSION_DOCS_DRIFT (1)`；逐字节恢复后默认和自测均退出 0。临时修改基线夹具预期，自测退出 1，输出 `check_version_docs: FAIL`。
- 副本中默认、`--tree`、`--self-test`、`--tree --self-test` 均退出 0；两种自测均有 `VERSION_DOCS_OK` 行且末行为 `check_version_docs: self-test OK (18 fixtures)`；另外两种末行为 `VERSION_DOCS_OK`。真实仓 `python -B rl_exp/tools/verify/check_version_docs.py --self-test` 和不带参数各退出 0，末行分别为对应判词。历史家族标签 WARN 仍存在。
- 临时仓的 tag 指向临时空提交，只复制名称，不验证实际 tag 指向和远端。测试比较真实 HARNESS 起止字节相等，未写入真实文档。临时目录由 `TemporaryDirectory` 清理；测试脚本放系统临时目录并在执行后删除。
- 范围检查：`python -B rl_exp/tools/verify/check_work_docs.py`、`python -B rl_exp/tools/verify/check_suite_shape.py`、`python -B rl_exp/tools/verify/check_suite_banners.py` 及 `git diff --check -- rl_exp/tools/verify/check_version_docs.py work/active/harness-baseline-tag-gate.md acceptance/records/2026-10-28-harness-baseline-tag-gate-execution.md` 均退出 0。工作台账有既有历史路径 HINT；Git 提示检查器工作副本 CRLF 将转 LF。未运行完整离线套件。
- 调用者：`offline_suite.py` 以 `--self-test` 调用，成功摘要取末行、失败依退出码并回放输出；pre-commit 调默认模式；家族文档提及 `--tree`。成功的 suite 摘要由原 `VERSION_DOCS_OK` 变为自测判词；未知外部调用方若依赖旧顺序或末行有兼容风险。公开 `self_test()` 自身签名和直接调用输出未更改。未搜索到仓内导入 `main()` 或 `self_test()` 的调用者。

### 复审缺陷修复（本轮，执行者记录）

- 差异：基线先提取完整令牌再校验版本，防止点、连字符等后缀被截断；允许中文句读、ASCII 逗号和句末点。重复非法声明仍计入声明条数。Git 未知时仍校验声明，但不推断标签缺失；空集合仍确报缺标签。前轮自测末行修复保留。
- 红测：先加持久夹具及 Git `None` 的 `main()` 回归，再运行 `python -B rl_exp/tools/verify/check_version_docs.py --self-test`，退出 1，报告 `git unavailable`、`dotted suffix`、`hyphen suffix`；随后字母后缀夹具也报红。修复后同命令退出 0，末行 `check_version_docs: self-test OK (30 fixtures)`；默认命令末行 `VERSION_DOCS_OK`。红测使用原实现和同一调用路径，未撤销前轮输出修复。
- 隔离代码块复读退出 0：默认及 tree 绿，自测与 tree 自测末行均为 30 夹具；临时删除 tag 和冒号两项原真实 CLI 破坏在默认及自测均退出 1，恢复后退出 0；点、连字符后缀两模式均退出 1；真实空 tag 集退出 1 并报缺标签。自测夹具反向破坏退出 1。套件 `run_checks` 实际启动其 `CHECKS` 中该检查，非法后缀使子进程退出 1、套件记录 `FAIL rc=1`；封装进程退出 1。Git `None` 由自测在真实 `main()` 路径注入并断言非零、未知诊断且没有缺标签文字；不是操作系统 Git 启动失败端到端测试。
- 临时仓复制 24 个真实本地 tag 名称，原始 HARNESS 字节测试前后相同；临时目录自动清理。只验证本地声明与标签名，不验证 tag 指向、远端、其他调用方或行为能力；完整离线套件未运行。
- `python -B rl_exp/tools/verify/check_work_docs.py`、`check_suite_shape.py`、`check_suite_banners.py` 和本轮已跟踪代码及事项的 `git diff --check` 均退出 0；工作台账报告既有历史路径 HINT，Git 提示检查器 CRLF 转 LF。记录文件未跟踪，`git diff --check` 不覆盖它。

## 证据引用

- 实现：`rl_exp/tools/verify/check_version_docs.py`；调度：`rl_exp/tools/verify/offline_suite.py` 的 `CHECKS`、`_run_one` 和 `_verdict`。
- 测试复读：运行 `acceptance/records/2026-10-28-harness-baseline-tag-gate-repair-review.md` 的命令直接执行下方代码块；系统临时目录建立并清理隔离仓，不改真实 HARNESS 或真实 tag。此代码块已扩展为本轮测试；前轮红测使用当时的主体。需复现红测时应在独立源码副本回退相应实现，不能回退真实工作树。

```python
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

root = pathlib.Path.cwd()
script = pathlib.Path('rl_exp/tools/verify/check_version_docs.py')
tags = subprocess.check_output(['git', 'tag', '--list'], cwd=root, text=True).splitlines()
original = (root / 'ablation_harness/HARNESS.md').read_bytes()
failures = []
with tempfile.TemporaryDirectory(prefix='harness-gate-contract-') as tmp:
    copy = pathlib.Path(tmp)
    for rel in ('rl_exp/versions', 'rl_exp/tools/verify'):
        shutil.copytree(root / rel, copy / rel, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    for rel in ('FILEMAP.md', 'ARCH_PLAN.md', 'ablation_harness/HARNESS.md'):
        (copy / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / rel, copy / rel)
    def git(*args):
        return subprocess.run(['git', *args], cwd=copy, check=True, capture_output=True, text=True)
    git('init', '-q')
    git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '--allow-empty', '-qm', 'test')
    for tag in tags:
        git('tag', tag)
    assert git('tag', '--list').stdout.splitlines() == tags
    doc = copy / 'ablation_harness/HARNESS.md'
    assert doc.read_bytes() == original
    def run(label, args, code, last, contains=()):
        proc = subprocess.run([sys.executable, '-B', str(script), *args], cwd=copy,
                              capture_output=True, text=True, encoding='utf-8', errors='replace',
                              env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
        lines = proc.stdout.splitlines()
        ok = proc.returncode == code and bool(lines) and last in lines[-1] and all(x in proc.stdout for x in contains)
        print(f'{label}: rc={proc.returncode}, last={lines[-1] if lines else proc.stderr!r}, expected_rc={code}, ok={ok}')
        if not ok:
            failures.append(label)
    run('default', [], 0, 'VERSION_DOCS_OK')
    run('tree', ['--tree'], 0, 'VERSION_DOCS_OK', ('lineage tree',))
    run('self-test', ['--self-test'], 0, 'check_version_docs: self-test OK', ('VERSION_DOCS_OK',))
    run('tree-self-test', ['--tree', '--self-test'], 0, 'check_version_docs: self-test OK', ('VERSION_DOCS_OK', 'lineage tree'))
    gate = copy / script
    gate_bytes = gate.read_bytes()
    gate_text = gate_bytes.decode('utf-8')
    fixture = '("the same line before the tag existed", "**代码基线**：v1.9.0 —— 几何测量", set(), False)'
    assert gate_text.count(fixture) == 1
    gate.write_bytes(gate_text.replace(fixture, fixture[:-6] + 'True)', 1).encode('utf-8'))
    run('self-test-failure', ['--self-test'], 1, 'check_version_docs: FAIL', ('the same line before the tag existed',))
    gate.write_bytes(gate_bytes)
    text = original.decode('utf-8')
    import re
    found = re.findall(r'\*\*代码基线\*\*：v(\d+\.\d+\.\d+)', text)
    assert len(found) == 1
    baseline_tag = 'harness-v' + found[0]
    assert baseline_tag in tags
    git('tag', '-d', baseline_tag)
    for args in ([], ['--self-test']):
        run('missing-tag ' + str(args), args, 1, 'VERSION_DOCS_DRIFT', ('has no tag ' + baseline_tag,))
    git('tag', baseline_tag)
    assert git('tag', '--list').stdout.splitlines() == tags
    run('tag-restored', [], 0, 'VERSION_DOCS_OK')
    needle = '**代码基线**：v' + found[0]
    assert text.count(needle) == 1
    doc.write_bytes(text.replace(needle, '**代码基线**v' + found[0], 1).encode('utf-8'))
    for args in ([], ['--self-test']):
        run('missing-line ' + str(args), args, 1, 'VERSION_DOCS_DRIFT', ('invalid harness baseline version',))
    doc.write_bytes(original)
    assert doc.read_bytes() == original
    run('line-restored', [], 0, 'VERSION_DOCS_OK')
    run('line-restored-self-test', ['--self-test'], 0, 'check_version_docs: self-test OK', ('VERSION_DOCS_OK',))
    for suffix in ('.1', '-invalid'):
        doc.write_bytes(text.replace(needle, needle + suffix, 1).encode('utf-8'))
        for args in ([], ['--self-test']):
            run('invalid-suffix ' + suffix + str(args), args, 1, 'VERSION_DOCS_DRIFT', ('invalid harness baseline version',))
    doc.write_bytes(original)
    # Run the suite scheduler on its actual check, in this isolated repo, with a bad declaration.
    doc.write_bytes(text.replace(needle, needle + '.1', 1).encode('utf-8'))
    suite_code = """import sys
sys.path.insert(0, 'rl_exp/tools/verify')
import offline_suite as suite
check = next(c for c in suite.CHECKS if c.argv[0].endswith('/check_version_docs.py'))
failures, _, skipped, _ = suite.run_checks(sys.executable, 1, [check])
assert len(failures) == 1 and failures[0][2] == 1 and 'invalid harness baseline version' in failures[0][3] and skipped == 0
raise SystemExit(bool(failures))
"""
    proc = subprocess.run([sys.executable, '-B', '-c', suite_code], cwd=copy, capture_output=True, text=True,
                          encoding='utf-8', errors='replace', env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
    ok = proc.returncode == 1 and 'FAIL rc=1' in proc.stdout and 'VERSION_DOCS_DRIFT' in proc.stdout
    print(f'suite-failure: rc={proc.returncode}, output={proc.stdout.strip()!r}, ok={ok}')
    if not ok:
        failures.append('suite-failure')
    doc.write_bytes(original)
    for tag in tags:
        git('tag', '-d', tag)
    run('empty-tags', [], 1, 'VERSION_DOCS_DRIFT', ('has no tag ' + baseline_tag,))
    for tag in tags:
        git('tag', tag)
    assert git('tag', '--list').stdout.splitlines() == tags
    run('all-restored', [], 0, 'VERSION_DOCS_OK')
    assert (root / 'ablation_harness/HARNESS.md').read_bytes() == original
    print('baseline tag:', baseline_tag, 'copied tags:', len(tags), 'real HARNESS unchanged: yes')
print('failures:', failures)
sys.exit(bool(failures))
```

## 第二次复审修复（执行者记录，非独立审核）

- 真实格式为列表项 `- **代码基线**：v1.11.0 —— ...`。声明限可见行首的粗体标签，可有 Markdown 列表标记；标签后只接受全角冒号与 ASCII 三段版本。正文须以空白加 `——`、列举的句读或结束行分隔；方括号和圆括号不作版本分隔，正文需要先加约定分隔符。代码行内跨度、围栏块和 HTML 注释不计数；同一声明行额外可见标签也计数。不是通用 Markdown 解析器，任意改写标签或在散文中声明不属于此语法。
- 红灯：先加自测及下方隔离 CLI；旧实现自测报 ASCII 冒号重复、两种方括号、示例误判与注释掩盖等 7 例。隔离默认 CLI 中重复 ASCII、两种方括号、注释掩盖错误返回 0；示例误判；单条 ASCII 和缺冒号虽然非零但诊断为 0 条而非非法声明。由于新增自测自身失败，旧实现的 `--self-test` 提前退出，无法据此声称其默认检查分支已被这些变异覆盖。
- Git 解码风险：注入 `UnicodeDecodeError` 的持久自测先失败，再将解码异常与 Git 读取失败一样返回 `None`；未复现真实 Git 标签触发。调用方搜索仅发现仓内套件和 hook；外部调用方不可穷尽，末行兼容风险仍存在。
- 绿灯：下方隔离回归默认和 `--self-test` 两模式均通过，含注释掩盖、误判、重复有效/异常、后缀、缺 tag、真实 Git 不可执行、空 tag、自测破坏与恢复。真实 HARNESS 起止字节相同；隔离仓仅复制本地 tag 名称。
- 最终真实仓自测 45 fixtures；`check_work_docs.py`、`check_suite_shape.py`、`check_suite_banners.py` 与已跟踪代码及事项 `git diff --check` 均通过；台账有既有历史路径 HINT，Git 提示 CRLF 转 LF。执行记录未跟踪，`git diff --check` 不覆盖它。未运行完整离线套件。
- 原隔离闭环代码块已更新夹具数量的期望及缺冒号诊断，复跑默认、tree、自测、缺 tag、无冒号、后缀、空 tag、套件传播和恢复均通过；历史数字仍是当次结果。跨平台复读原代码块命令：

```bat
python -B -c "import pathlib; p=pathlib.Path('acceptance/records/2026-10-28-harness-baseline-tag-gate-execution.md'); q=chr(96)*3; exec(compile(p.read_text(encoding='utf-8').split(q+'python')[1].split(q,1)[0], 'original-cli-regression', 'exec'))"
```

## 第三次复审修复（执行者记录，非独立审核）

- 修复前先添加持久自测和下列隔离 CLI 变异，运行下列第二条复读命令：测试退出 1。默认 CLI 中，单反引号和双反引号示例置于基线前均误报 0 条、置于基线后均吞掉第二条 ASCII 冒号异常声明并退出 0；末尾注释误报非法。自测报告这五项失败；`--self-test` 因自测失败提前退出，不能声称其修前默认路径已覆盖变异。第一次运行命令因代码块中包含围栏定界符触发 `SyntaxError`，修正测试代码后获得上述红灯。
- 按源序识别 HTML 注释与等长反引号代码跨度；验证声明时将注释替换为空格，计数时额外屏蔽代码。声明末尾允许 HTML 注释，包括跨行注释；注释不替代版本字符或正文所需的分隔符。真实跨行注释中的声明不计数，结束后第二条异常声明仍计数。真实 `ablation_harness/HARNESS.md` 未更改。
- 边界：不是完整 Markdown 解析器；未闭合注释、代码跨度或围栏、跨度外转义反引号、嵌套或缩进围栏，以及反引号围栏信息字符串中的反引号均拒绝。代码跨度可跨行，围栏只支持顶层形式；其他 Markdown 构造不保证与渲染一致，基线必须使用源码中约定的行首声明。仅本地 tag 名称，不验证指向或远端。
- 修复后依次复跑下列第二条及上文第一条复读命令，均退出 0、`failures: []`；隔离真实默认与 `--self-test` 的新增场景及缺标签、缺冒号、非法后缀、不可执行 Git、空标签、自测破坏与恢复均符合预期；原测试的 `--tree`、失败末行和 suite `FAIL rc=1` 传播保持。自测 64 fixtures，包含 `Git None` 的真实 `main()` 注入与 Git 解码异常注入。隔离仓复制 24 个 tag 名，原测试比较真实 HARNESS 起止字节一致。此前红绿证据仍保留上文。
- 范围检查：`python -B rl_exp/tools/verify/check_work_docs.py`、`python -B rl_exp/tools/verify/check_suite_shape.py`、`python -B rl_exp/tools/verify/check_suite_banners.py` 和 `git diff --check -- rl_exp/tools/verify/check_version_docs.py work/active/harness-baseline-tag-gate.md` 均退出 0；台账有四条既有历史路径 HINT；Git 提示检查器 CRLF 转 LF。未跟踪的本执行记录不在 `git diff --check` 覆盖内。
- 未验证完整离线套件、外部调用方和真实 Git 解码失败；须由无执笔历史的新上下文独立复审，不以本记录代替审核。

## 本轮隔离 CLI 回归（复读入口）

```bat
python -B -c "import pathlib; p=pathlib.Path('acceptance/records/2026-10-28-harness-baseline-tag-gate-execution.md'); q=chr(96)*3; exec(compile(p.read_text(encoding='utf-8').split(q+'python')[2].split(q,1)[0], 'baseline-cli-regression', 'exec'))"
```

```python
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

root = pathlib.Path.cwd()
script = pathlib.Path('rl_exp/tools/verify/check_version_docs.py')
original = (root / 'ablation_harness/HARNESS.md').read_bytes()
text = original.decode('utf-8')
tags = subprocess.check_output(['git', 'tag', '--list'], cwd=root, text=True).splitlines()
needle = re.search(r'\*\*代码基线\*\*：v[0-9]+\.[0-9]+\.[0-9]+', text).group()
tag = 'harness-' + needle.split('：')[1]
assert text.count(needle) == 1 and tag in tags
failures = []
with tempfile.TemporaryDirectory(prefix='baseline-cli-regression-') as tmp:
    repo = pathlib.Path(tmp)
    for rel in ('rl_exp/versions', 'rl_exp/tools/verify'):
        shutil.copytree(root / rel, repo / rel, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    for rel in ('FILEMAP.md', 'ARCH_PLAN.md', 'ablation_harness/HARNESS.md'):
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / rel, repo / rel)
    def git(*args):
        return subprocess.run(['git', *args], cwd=repo, check=True, capture_output=True, text=True)
    git('init', '-q')
    git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '--allow-empty', '-qm', 'test')
    for item in tags:
        git('tag', item)
    doc = repo / 'ablation_harness/HARNESS.md'
    def run(name, args, rc, expected, env=None, absent=()):
        proc = subprocess.run([sys.executable, '-B', str(script), *args], cwd=repo,
                              capture_output=True, text=True, encoding='utf-8', errors='replace',
                              env={**os.environ, 'PYTHONIOENCODING': 'utf-8', **(env or {})})
        output = proc.stdout + proc.stderr
        ok = proc.returncode == rc and all(s in output for s in expected) and all(s not in output for s in absent)
        print(f'{name}: rc={proc.returncode}, ok={ok}' + ('' if ok else f'\n{output}'))
        if not ok:
            failures.append(name)
    for args in ([], ['--self-test']):
        mode = 'self-test' if args else 'default'
        for name, changed, rc, expected in (
            ('original', text, 0, ('VERSION_DOCS_OK',)),
            ('ASCII colon', text.replace(needle, needle.replace('：', ':')), 1, ('invalid harness baseline',)),
            ('duplicate ASCII', text + '\n- **代码基线**:v9.9.9\n', 1, ('matched 2 time(s)',)),
            ('duplicate valid', text + '\n- **代码基线**：v9.9.9\n', 1, ('matched 2 time(s)',)),
            ('bracket', text.replace(needle, needle + '[invalid]'), 1, ('invalid harness baseline',)),
            ('spaced bracket', text.replace(needle, needle + ' [invalid]'), 1, ('invalid harness baseline',)),
            ('suffix', text.replace(needle, needle + '.1'), 1, ('invalid harness baseline',)),
            ('no colon', text.replace(needle, needle.replace('：', '')), 1, ('invalid harness baseline',)),
            ('comment mask', text.replace(needle, needle.replace('：', '')) + '\n<!-- ' + needle + ' -->\n', 1, ('invalid harness baseline',)),
            ('inline prose', text + '\n说明 `' + needle + '` 的格式。\n', 0, ('VERSION_DOCS_OK',)),
            ('fenced example', text + '\n' + chr(96)*3 + 'python\n' + needle + '\n' + chr(96)*3 + '\n', 0, ('VERSION_DOCS_OK',)),
            ('inline opener before', '示例 `<!--`\n' + text, 0, ('VERSION_DOCS_OK',)),
            ('inline opener after duplicate', text.replace(needle, needle + ' —— `<!--`') + '\n**代码基线**:v9.9.9\n', 1, ('matched 2 time(s)',)),
            ('double backticks before', '示例 `` `<!--` ``\n' + text, 0, ('VERSION_DOCS_OK',)),
            ('double backticks after duplicate', text.replace(needle, needle + ' —— `` `<!--` ``') + '\n**代码基线**:v9.9.9\n', 1, ('matched 2 time(s)',)),
            ('trailing comment', text.replace(needle, needle + ' <!-- note -->'), 0, ('VERSION_DOCS_OK',)),
            ('trailing comment duplicate', text.replace(needle, needle + ' <!-- note -->') + '\n**代码基线**:v9.9.9\n', 1, ('matched 2 time(s)',)),
            ('multiline comment duplicate', text + '\n<!--\n**代码基线**:v8.8.8\n-->\n**代码基线**:v9.9.9\n', 1, ('matched 2 time(s)',)),
            ('fenced opener duplicate', text + '\n' + chr(96)*3 + '\n<!-- `\n' + chr(96)*3 + '\n**代码基线**:v9.9.9\n', 1, ('matched 2 time(s)',)),
            ('unclosed inline code', '示例 `<!--\n' + text, 1, ('ambiguous',)),
        ):
            doc.write_bytes(changed.encode('utf-8'))
            run(mode + ' ' + name, args, rc, expected)
        doc.write_bytes(original)
        git('tag', '-d', tag)
        run(mode + ' missing tag', args, 1, ('has no tag ' + tag, 'VERSION_DOCS_DRIFT'))
        git('tag', tag)
        run(mode + ' unavailable git', args, 1, ('git tag --list could not be read', 'VERSION_DOCS_DRIFT'),
            env={'PATH': ''}, absent=('has no tag', 'no git tag'))
    for item in tags:
        git('tag', '-d', item)
    for args in ([], ['--self-test']):
        run('empty tags ' + str(args), args, 1, ('has no tag ' + tag, 'VERSION_DOCS_DRIFT'))
    for item in tags:
        git('tag', item)
    gate = repo / script
    saved = gate.read_bytes()
    source = saved.decode('utf-8')
    fixture = '("the same line before the tag existed", "**代码基线**：v1.9.0 —— 几何测量", set(), False)'
    assert source.count(fixture) == 1
    gate.write_bytes(source.replace(fixture, fixture[:-6] + 'True)', 1).encode('utf-8'))
    run('self-test fixture failure', ['--self-test'], 1, ('check_version_docs: FAIL', 'the same line before the tag existed'))
    gate.write_bytes(saved)
    run('restored default', [], 0, ('VERSION_DOCS_OK',))
    run('restored self-test', ['--self-test'], 0, ('VERSION_DOCS_OK', 'check_version_docs: self-test OK'))
    assert (root / 'ablation_harness/HARNESS.md').read_bytes() == original
print('failures:', failures)
sys.exit(bool(failures))
```

## 第四次复审修复（执行者记录，非独立审核）

- 先加入 Tab、混合空格 Tab、四空格及更深缩进的反例和正常围栏、注释、代码跨度夹具；修复前自测实际报四项失败，Tab 缩进围栏吞掉异常声明。审查复现命令及当次隔离 CLI 错误成功的证据见 `acceptance/records/2026-10-28-harness-baseline-tag-gate-fourth-review.md`。
- 围栏歧义检查前按四列制表位展开 Tab，其余解析和实际文档不改；修复后自测通过，共 83 个夹具（包括 14 个缩进与围栏组合）。正常顶层围栏及注释、代码跨度中的示例仍通过。
- 修复后复跑第四次审核记录中的隔离 CLI 反例：默认和 `--self-test` 均退出 1 并报告歧义，正常文档退出 0；完整隔离回归 `failures: []`。上文第一组隔离回归重新运行并通过，缺标签和缺冒号均退出 1，恢复退出 0；真实 HARNESS 字节保持不变。
- 现有解析器并非通用 Markdown 解析器，此次只修正既有拒绝缩进围栏规则，不新增解析分支；其他 Markdown 构造仍受第三次修复中的明确边界限制。

## 未覆盖边界

仅验证本地标签名称和文档声明一致，不验证 tag 指向、推送或任何测量能力；远端锚点另属 `work/active/harness-version-anchor-missing.md`。尚需不带执笔历史的新上下文独立复审本次实际落点、执行证据和关闭条件；本记录不代替审核。
