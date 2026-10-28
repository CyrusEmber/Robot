# 六组合日志与临时 Git index 归档：原件保留

## 适用范围

`work/active/diagnostic-artifact-lifecycle.md` 的单批处理：2026-10-21 六组受载组合七份日志及两个临时 Git index。不改实验结论、不处理其它输出，不提交或推送。

## 验收条件

保留原字节和失败日志；核查直接消费者、运行进程、Git 状态及原件摘要；按 manifest/blob 归档并在隔离目录真实恢复九文件，核对摘要及与原件字节一致；恢复 index 使用独立 `GIT_INDEX_FILE` 只读对照历史提交。只有消费者迁移或安全复验、临删除复核、删除后完整恢复复验均完成，才能删除九个原副本。

## 结果

本机归档已建立并完成删前隔离恢复，但 **九个原件均保留**。`rl_exp/out/record_calibrated_combinations.py:41`–43 直接读取两份原路径日志；脚本还会写 `force_channel_review.json`，之后检查验收记录不存在，因此不能在现有工作树直接执行作为消费者验证。尚未证明此读取点已退役或迁移，不以文本搜索、进程快照或既有记录推断无活跃消费者。其余原文件的潜在消费者和写者同样不能由快照排除。本批未删除、未做删除后重建，净减少顶层文件数及空间均为零，额外占用归档 136,826 字节。

在隔离临时根以原脚本仅替换 `root` 并使用真实 `write_json` 复验：先从归档恢复九件，再读取真实报告及两份日志、生成新记录。六组合表格及已记录全局指标一致，七项证据摘要中六项一致；生成的 `force_channel_review.json` 摘要不同，因脚本与历史记录中的第二条 finding 函数名不同，未修改历史文件或判词。镜像保留既有 force review 时真实写入口以 `FileExistsError` 拒绝覆盖，使用新副本才可执行。该验证不等于已迁移原脚本，也不排除其它消费者。

恢复测试实际向系统临时新目录写出全部九份，并逐项对照原文件字节、大小及 SHA-256；检查 ZIP 成员集合、重复成员和 CRC。恢复的两个 index 分别以独立 `GIT_INDEX_FILE` 运行 `git --no-optional-locks diff --cached --quiet --no-ext-diff --no-textconv <commit> --`，均返回 0；这是 index 树与提交树相同，不说明历史暂存状态的其它元数据可从提交重建。未对原 index 运行 Git，未修改 `.git/index`。隔离目录已清理。恢复命令随后去掉优化模式会绕过的断言；修订后实跑恢复九项，错误摘要在 `-O` 下拒绝。

核查期间命令行快照存在 Lizard2-Flat-v6 训练进程，未见组合实验脚本或 Git writer；快照不保证其它进程没有打开文件或将来不会打开。九项均在忽略范围，`git ls-files` 未列出。现存报告生成脚本依赖两份日志，且直接执行有写入副作用；不得删除后假设透明读取 ZIP。

## 证据引用

本机归档 `rl_exp/out/archive/diagnostic-development/calibrated-combinations-logs-index-20261021.zip`，SHA-256 `b83dc9bcf3e3d0526dc4dd09681e3c6cae0689227b00092f9518427e83130fb5`。`manifest.json` 的 `files` 使用原仓库相对路径映射 `size_bytes` 和 `sha256`；内容位于 `blobs/<sha256>`。本机单副本，不是外部备份。

| 原文件（均在 `rl_exp/out/`） | 字节 | SHA-256 |
|---|---:|---|
| `lizard2_b_combinations_20261021.log` | 14015 | `72762d4ba1f84c387e04168500a4fa23b02f6efcf3f20d41cabf0ae8a32b7a80` |
| `lizard2_b_combinations_preflight_20261021.log` | 39295 | `d335ff7e1a311d106b6d25a464554e9622258bf55ed03c574eac4dca973bdf15` |
| `lizard2_b_combinations_audit_20261021.log` | 4186 | `cc3e889653c3bc301c762cbed017518342b74b6ce5bfd96a929533334e392a88` |
| `lizard2_b_combinations_analysis_20261021.log` | 388 | `1b1a09323d4f3d3d68cba3907dc2925ff2e8fbe4c13de6618ab4734cea1c1363` |
| `lizard2_b_combinations_record_20261021.log` | 1333 | `5639db964d76b61fcb81bbabc57916c7fc540acd242ac34a8ba0fe1278741837` |
| `lizard2_b_combinations_offline_20261021.log`（失败现场） | 6089 | `8edf1bd4994a6f1410cb3fe85df369f13fdf31a1d13ce0f7c55f33b1ed501ca4` |
| `lizard2_b_combinations_offline_final_20261021.log` | 7221 | `c96ac84df9770b7e25f1eb707fe6922fa2fb3709adcbb0dbaf1795ac502db1f0` |
| `calibrated_combinations_code_20261021.index` | 141100 | `44be8e34d7b5300d8904922917f83ae180bd89a870aeeb40f693f7c330323e58` |
| `calibrated_combinations_docs_20261021.index` | 141228 | `41c77daf363bb4a8ebabe9a4d17a201f910552fc88b24092c842da15c87c1c2b` |

历史树分别为 `745976777fde50bf9e1911da944317d4ea18e357`、`2fbee92e849759beb701488822bbb5bb8e9accd1`。以下在仓根运行，向新系统临时目录恢复并逐项核验，打印目录供查看；不覆盖原件、不执行历史脚本。查看后由使用者删除打印的临时目录。随后仅对恢复副本使用 `GIT_INDEX_FILE` 只读 diff；索引与 Git 对象须来自可信本机仓库。

```cmd
python -B -c "import json,tempfile,zipfile; from pathlib import Path; from rl_exp.tools.runrecord.binding import sha256_bytes,sha256_file; a=Path('rl_exp/out/archive/diagnostic-development/calibrated-combinations-logs-index-20261021.zip'); sha256_file(a)=='b83dc9bcf3e3d0526dc4dd09681e3c6cae0689227b00092f9518427e83130fb5' or (_ for _ in ()).throw(ValueError('archive digest')); z=zipfile.ZipFile(a); m=json.loads(z.read('manifest.json')); len(m['files'])==9 and len(z.namelist())==len(set(z.namelist())) and set(z.namelist())=={'manifest.json'}|{'blobs/'+v['sha256'] for v in m['files'].values()} or (_ for _ in ()).throw(ValueError('archive members')); t=Path(tempfile.mkdtemp(prefix='robot-combinations-')); print('RESTORE_DIR',t,flush=True); exec('for k,v in m[\"files\"].items():\n p=t/k\n p.parent.mkdir(parents=True,exist_ok=True)\n b=z.read(\"blobs/\"+v[\"sha256\"])\n (len(b)==v[\"size_bytes\"] and sha256_bytes(b)==v[\"sha256\"]) or (_ for _ in ()).throw(ValueError(k))\n p.write_bytes(b)\n sha256_file(p)==v[\"sha256\"] or (_ for _ in ()).throw(ValueError(k))\n print(\"RESTORED\",p)')"
set "GIT_INDEX_FILE=<RESTORE_DIR>\rl_exp\out\calibrated_combinations_code_20261021.index"
git --no-optional-locks diff --cached --no-ext-diff --no-textconv --exit-code 745976777fde50bf9e1911da944317d4ea18e357 --
set "GIT_INDEX_FILE=<RESTORE_DIR>\rl_exp\out\calibrated_combinations_docs_20261021.index"
git --no-optional-locks diff --cached --no-ext-diff --no-textconv --exit-code 2fbee92e849759beb701488822bbb5bb8e9accd1 --
set "GIT_INDEX_FILE="
```

原实验结论和原日志路径见 `acceptance/records/2026-10-21-lizard2-calibrated-combinations.md`。

独立审核实核归档、九份原件、恢复入口和两个 Git 索引；当前不批准删除。审核发现 `sha256_file()` 对不可读文件返回 `None`，旧脚本可能将缺失日志写入证据而非明确报错；脚本的记录写入还依赖优化模式可跳过的 `assert`。现有工作树和历史记录不得用该脚本重跑覆盖，无法根据一次隔离复验推定其它消费者不存在。项目离线套件 37/37 通过，不替代删除条件或消费者迁移。

## 未覆盖边界

整理执行者须与消费者维护者确认 `record_calibrated_combinations.py` 是否仍需调用；隔离根已证明先显式恢复再读取，但原脚本仍直接读取旧路径，故不能当作已迁移。随后复核九文件实际绝对位置、内容、Git 状态、writer/消费者和归档，才可限定删除；删除后再从 ZIP 实际恢复九文件并重核摘要与两棵 Git 树。缺证继续保留。没有外部备份、独立审核或删除后复验；未运行物理或训练。
