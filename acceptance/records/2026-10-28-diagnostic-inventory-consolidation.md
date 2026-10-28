# 诊断历史盘点快照合并

## 适用范围

对应 `work/active/diagnostic-artifact-lifecycle.md`。只整理 2026-10-20 与 2026-10-21 的四份历史盘点快照；保留全部原始 JSON 字节及逻辑身份，不处理诊断报告、运行日志、失败现场或当前实验。

## 验收条件

- 固定四份快照的大小、SHA-256、Git 状态，核对记录与读取方；盘点只描述当时观察，不作为删除许可。
- 使用现有 manifest/blob 格式合包；隔离根解包逐项校验字节和 JSON 原读点，核对摘要及历史计数。
- 记录新的归档位置和显式恢复入口，刷新目标文件与 writer 状态后才处置旧副本；删除后复验。

## 结果

四份快照合计 168,834,490 字节，被 Git 忽略且未跟踪。逐项 SHA、原路径及大小见 ZIP 内 `manifest.json`。已有验收记录中的 final/handoff 摘要与原文件一致；`artifact_inventory.py` 是快照生产者，不读取旧快照。文档引用已指向归档与恢复入口，原目录保留供盘点命令指定新文件名。运行训练和其它会话未停止；进程快照不等于系统级写锁。

归档为 15,514,957 字节；在独立临时目录恢复四个原文件后，逐项大小和 SHA-256 与原件一致，并真实 JSON 解析、读出 `snapshot_only`、`approved_delete` 和 summary；原快照的 unknown 边界未改变。删除前再次核对归档与四份原文件摘要、精确位置、Git 跟踪及相关进程命令行；已删除四个旧副本，删后重新解包至隔离根并复核四份摘要和 JSON，临时目录已清理，净释放 153,319,533 字节。归档与日志仍是本机单副本，不是外部备份。

## 证据引用

归档：`rl_exp/out/archive/diagnostic-development/inventory-snapshots-20261028.zip`；SHA-256 `03e7798dcddedbf1d9c6281766d15c9c14dda3e6c8a1a44958aab5b769a81978`。`manifest.json` 的 `files` 将原仓库相对路径映射到 `size_bytes` 和 `sha256`；内容在 `blobs/<sha256>`。

四个逻辑身份：

- `rl_exp/out/runs/diagnostic-artifact-lifecycle/20261020-inventory/inventory.json`
- `rl_exp/out/runs/diagnostic-artifact-lifecycle/20261020-inventory/inventory-final.json`
- `rl_exp/out/runs/diagnostic-artifact-lifecycle/20261020-inventory/inventory-handoff.json`
- `rl_exp/out/runs/diagnostic-artifact-lifecycle/20261021-retention-continuation/inventory.json`

在仓根以配置解释器运行下列恢复命令。它先核对整个归档摘要与成员集合，再逐项写入新的系统临时目录，验证摘要并读取 JSON summary；记录输出的 `RESTORE_DIR`。不要恢复到原仓根或覆盖原件。核对完毕后手动清理命令生成的隔离临时目录。

```text
<python> -B -c "import json,zipfile,tempfile,shutil; from pathlib import Path; from rl_exp.tools.runrecord.binding import sha256_file; a=Path('rl_exp/out/archive/diagnostic-development/inventory-snapshots-20261028.zip'); expected='03e7798dcddedbf1d9c6281766d15c9c14dda3e6c8a1a44958aab5b769a81978'; sha256_file(a)==expected or (_ for _ in ()).throw(ValueError('archive digest')); z=zipfile.ZipFile(a); m=json.loads(z.read('manifest.json')); len(m['files'])==4 and len(z.namelist())==len(set(z.namelist())) and set(z.namelist())=={'manifest.json'}|{'blobs/'+v['sha256'] for v in m['files'].values()} or (_ for _ in ()).throw(ValueError('archive members')); t=Path(tempfile.mkdtemp(prefix='robot-inventory-')); print('RESTORE_DIR',t,flush=True); [(lambda p,v: (p.parent.mkdir(parents=True,exist_ok=True),shutil.copyfileobj(z.open('blobs/'+v['sha256']),p.open('xb')),p.stat().st_size==v['size_bytes'] and sha256_file(p)==v['sha256'] or (_ for _ in ()).throw(ValueError(str(p))),print('RESTORED',p,json.loads(p.read_bytes())['summary']['files'])))(t/k,v) for k,v in m['files'].items()]"
```

独立审核以新上下文实算整包、成员与四份 JSON，对照两份历史记录核摘要、盘点汇总及旧位置；结果一致。审核指出原复读命令仅校验且依赖 `assert`，已改为显式异常和实际隔离恢复；改后完整恢复四份，错误包摘要在 `-O` 下明确拒绝。另由新上下文实跑修改后的命令并逐项核验四份恢复内容、复测错误摘要优化模式拒绝，临时目录已清理。删除前原件与当时 writer 状态不能由当前包反证。

定向盘点回归 7/7、事项格式检查及项目离线套件 37/37 通过。

## 未覆盖边界

压缩包需显式读取或解包，不提供旧路径透明映射；本机归档不随 Git 检出，异机须取得同摘要包。未声称盘点时 writer 已停止或词法引用完整，不以归档证明诊断结果或整个事项关闭。其它存量、输出生产者接入和自动收尾仍由原事项承接。
