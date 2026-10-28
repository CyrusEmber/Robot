# 输出根一次性提交脚本归档

## 适用范围

对应 `work/active/diagnostic-artifact-lifecycle.md`。首批处置输出根中已执行的提交、文档修正和事项路由去重辅助脚本；续批仅处置下列五份对应已完成提交的临时 Git 索引，不涉及诊断样本、活动复读入口或其它索引。

## 验收条件

- 固定文件、摘要和 Git 状态；核对真实用途、引用与正在执行的进程。
- 用既有 manifest/blob 格式归档，隔离目录逐文件恢复核对后再移除原副本。
- 索引登记本机归档和恢复入口；归档不冒称远端备份。

## 结果

候选是 6 个提交脚本、1 个训练条件文档修正脚本和 1 个事项证据路由去重脚本，均非诊断生产或复读入口。对应六个提交已在 Git 历史中；训练条件修正和证据路由去重后的文档已在现行记录中。8 个脚本共 13,924 字节，均被忽略、未被 Git 跟踪。进程命令行快照未发现实际执行候选脚本的进程；快照不是写入锁。

原文件以逐路径大小和 SHA-256 写入归档 manifest，8 个 blob 在独立临时根逐文件解包，与原文件字节相等；删除前重新核对归档摘要、全部原件、实际绝对位置和 Git 跟踪状态。已删除 8 个原副本，删后确认旧位置均不存在，并再次解包核验 8 个文件的大小和 SHA-256；两次临时恢复目录均已清理。归档是本机单副本，不能代表已建立外部备份。

## 证据引用

本机归档：`rl_exp/out/archive/diagnostic-development/commit-scratch-20261028.zip`，9,212 字节，SHA-256 `d5b7c1d45723f981482015477ef0063f7ebbb276c89a7779673a47ed26cab4f9`。`manifest.json` 的 `files` 按原仓库相对路径映射 `size_bytes`、`sha256`；字节位于 `blobs/<sha256>`。本批仅含：

- `rl_exp/out/commit_joint_force_code_20261021.py`、`rl_exp/out/commit_joint_force_docs_20261021.py`
- `rl_exp/out/commit_standing_force_code_20261022.py`、`rl_exp/out/commit_standing_force_docs_20261022.py`
- `rl_exp/out/commit_symmetric_pd_20261021.py`、`rl_exp/out/commit_training_consistency_20261022.py`
- `rl_exp/out/correct_training_consistency_20261022.py`、`rl_exp/out/dedup_left_knee_work_routes.py`

由标准库 `zipfile` 读 manifest，在隔离临时根恢复并重新计算摘要；不要在工作树恢复或执行这些改文档和提交脚本。现有同格式恢复说明见 `acceptance/records/2026-10-21-diagnostic-artifact-decoupling-cleanup.md`。

独立只读复核：新上下文重新计算整包 SHA-256，在内存逐项解压核对 8 个 blob 的大小及摘要，确认 manifest 与本记录路径一致、无重复或额外成员、8 个原路径均不存在，索引指向一致。复核不能反证删除前原件、进程状态和临时恢复过程，以上删前事实仍依执行者记录。

检查：事项格式通过；产物定位器成功加载索引；项目解释器运行离线闸门 37/37 通过。系统默认 Python 因缺少 `gymnasium` 无法运行完整离线套件，后改用项目环境。

## 临时 Git 索引续批

2026-10-28 续批归档并删除以下五份输出根副本，原始共 712,972 字节；新包 299,859 字节，净减少 413,113 字节。原件均为未跟踪、受 `.gitignore` 忽略的 Git index，路径、大小、原始 SHA-256 和对应已完成提交如下：

| 原路径 | 字节 | SHA-256 | 提交 |
|---|---:|---|---|
| `rl_exp/out/joint_force_code_20261021.index` | 142316 | `f2f30596bce9f9c7137ef08f46611d26dfc06aaf006732efccace8e93ac715a2` | `dd4bbc0897e8215c4d347b82e721809aa403c8a8` |
| `rl_exp/out/joint_force_docs_20261021.index` | 142444 | `69d3560fcf6d8d22305f825aebe48612a5dee42c52feddf3ea76d29e39369cc2` | `b8b4d400268dd1267b0f8968456d4d8f42da208b` |
| `rl_exp/out/standing_force_code_20261022.index` | 143004 | `ef7e6774724b97f28d5a1e24a7ac4c927072f198eb4836a026188dbe040b88b6` | `2a91a60a4b900fce1103a104812d7c84b8b9d085` |
| `rl_exp/out/standing_force_docs_20261022.index` | 143132 | `cfb1c256f889ae3979681118736c118d2bd44310e5c75379a93c1b624d29f4d0` | `ac8575f7cd4574dbf269ac9dc720ec6a7b957015` |
| `rl_exp/out/symmetric_pd_code_20261021.index` | 142076 | `534998af0df8a71361fcbc3216e80ba713bc829dcbaa7ad56b804cdcbf42a9a1` | `6e685b1e99434797a78fc7c61a226e549cb7aeed` |

新包 `rl_exp/out/archive/diagnostic-development/commit-index-20261028.zip`，SHA-256 `c4603d077f513fff2585ae1b94247febb7d67bfc89553c4e555691ed3361cf91`；复用 `manifest.json` 的原路径、长度和 SHA-256 与 `blobs/<sha256>` 格式。源脚本包仍是上文 `commit-scratch-20261028.zip`，摘要未变。五份实际脚本从源包 blob 恢复到系统临时目录、逐字节核对，只读核实脚本各自指定上述 `GIT_INDEX_FILE`；它们是这些临时索引的历史写入/消费方，未执行脚本。五份实际提交日志分别为 `rl_exp/out/lizard2_joint_force_code_commit_20261021.log`、`rl_exp/out/lizard2_joint_force_docs_commit_20261021.log`、`rl_exp/out/lizard2_standing_force_code_commit_20261022.log`、`rl_exp/out/lizard2_standing_force_docs_commit_20261022.log`、`rl_exp/out/lizard2_symmetric_pd_code_commit_20261021.log`；日志记录对应提交成功，五个 commit 对象均存在且是当前 HEAD 祖先。跟踪文件文本搜索无索引路径引用，输出根 467 个顶层文本文件无精确引用；不等于证明所有忽略目录及二进制没有隐藏消费者。

删前确认五个绝对路径及父链无 reparse、各单硬链接、没有同名 `.lock`，`git ls-files` 无跟踪、`git check-ignore` 成功。使用 Windows `CreateFileW` 以 `GENERIC_READ`、共享读/删除但不共享写打开并保持句柄至删除完成：阻止普通兼容共享规则下的新 writer，同时让隔离验证读取，不能排除内核级或绕过该机制的操作。实际进程命令行两次快照未匹配五个文件或旧脚本；其他训练进程存在，未操作。文件、路径、摘要、Git 状态、锁文件与进程在删除前重核。独立 `GIT_INDEX_FILE` 对各自提交运行 `git diff --cached --quiet <commit> --` 均为 0；新包落盘并 `fsync` 后，在隔离目录逐字节恢复、与原件比较并用独立 index 重跑 diff，再仅删除五个精确路径。删除后确认五路径不存在，再从新包另行恢复五份、校验长度与摘要并逐个 diff，均通过。没有执行 `git commit`、旧写脚本或操作 `.git/index`。首次进程快照因 Windows 输出编码引发 `UnicodeDecodeError`，发生在建包及删除之前；指定 UTF-8 后重新执行成功。

可在仓根用下面的 Windows PowerShell 命令实际恢复至新建隔离目录并验证，不执行历史写脚本；需保留本机 Git 对象和两份 ZIP。命令不覆盖旧路径；若检查失败，保留包及临时恢复目录供排查，不继续删除或修改其他文件：

```powershell
$env:PYTHONUTF8='1'
@'
import hashlib, json, os, pathlib, subprocess, tempfile, zipfile
root = pathlib.Path.cwd()
items = [('joint_force_code_20261021.index','dd4bbc0','commit_joint_force_code_20261021.py'), ('joint_force_docs_20261021.index','b8b4d40','commit_joint_force_docs_20261021.py'), ('standing_force_code_20261022.index','2a91a60','commit_standing_force_code_20261022.py'), ('standing_force_docs_20261022.index','ac8575f','commit_standing_force_docs_20261022.py'), ('symmetric_pd_code_20261021.index','6e685b1','commit_symmetric_pd_20261021.py')]
archives = [(root/'rl_exp/out/archive/diagnostic-development/commit-index-20261028.zip','c4603d077f513fff2585ae1b94247febb7d67bfc89553c4e555691ed3361cf91'), (root/'rl_exp/out/archive/diagnostic-development/commit-scratch-20261028.zip','d5b7c1d45723f981482015477ef0063f7ebbb276c89a7779673a47ed26cab4f9')]
tmp = pathlib.Path(tempfile.mkdtemp(prefix='robot-index-recovery-')); print('recovery:', tmp, flush=True)
for path, digest in archives:
    if hashlib.sha256(path.read_bytes()).hexdigest() != digest: raise ValueError(f'archive mismatch: {path}')
with zipfile.ZipFile(archives[0][0]) as iz, zipfile.ZipFile(archives[1][0]) as sz:
    im, sm = json.loads(iz.read('manifest.json')), json.loads(sz.read('manifest.json'))
    for name, commit, script in items:
        for z, manifest, filename in [(iz, im, name), (sz, sm, script)]:
            row = manifest['files']['rl_exp/out/'+filename]; data = z.read('blobs/'+row['sha256'])
            if len(data) != row['size_bytes'] or hashlib.sha256(data).hexdigest() != row['sha256']: raise ValueError(filename)
            (tmp/filename).write_bytes(data)
            if (tmp/filename).read_bytes() != data: raise ValueError(filename)
        text = (tmp/script).read_text(encoding='utf-8')
        if 'GIT_INDEX_FILE' not in text or name not in text: raise ValueError(script)
        env = os.environ.copy(); env['GIT_INDEX_FILE'] = str(tmp/name); env['GIT_OPTIONAL_LOCKS'] = '0'
        subprocess.run(['git','diff','--cached','--quiet',commit,'--'], cwd=root, env=env, check=True)
        print('OK', name, commit)
'@ | python -B -
```

成功后人工确认临时目录仅含上述恢复材料，再删除该临时目录；失败保留现场。本批索引指向本机归档。续批执行会话中断后，主会话另从两份 ZIP 恢复五份索引与脚本、核对摘要和五个提交树，并确认五个旧路径不存在。

独立审核以新上下文实际运行上述恢复入口，核对两包摘要、CRC、清单及五个旧路径；五份恢复索引分别匹配记录的提交树，五个脚本与提交日志一致且未执行。错误整包摘要、修改 blob 后重建 ZIP CRC 和压缩内容损坏均被拒绝。审核无法独立重证删前原件、文件锁及进程状态，也不排除动态消费者；仅审核本批，不代表总事项关闭。

## 未覆盖边界

本批不移动有消费者的代码快照、诊断样本、进度文件、其它散文件或其余 Git 暂存索引；不改变实验结果。归档仅为本机可恢复副本，外部备份未核实；磁盘故障仍会丢失。输出目录存量与新增生产入口仍由原事项继续承接。
