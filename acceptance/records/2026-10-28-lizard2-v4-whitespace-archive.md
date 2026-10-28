# v4 staged whitespace 失败日志归档

## 适用范围

`work/active/diagnostic-artifact-lifecycle.md` 阶段 3；仅处理 `rl_exp/out/lizard2_v4_staged_whitespace.log`。保留完整原字节，未重跑原检查，不改变配置验收及其历史判词。

## 验收条件

固定原件、归档和 Git 身份；核查包括忽略临时文件在内的消费者及写者；隔离恢复与原件逐字节比较并实际解析 URDF、USD、OBJ 失败行；复核历史报告身份；限定旧路径，删除后独立恢复复验。任何条件缺失均保留原件。

## 结果

原件 34,354,206 字节，SHA-256 `8b9dbaf9ccb1b02bc0cc7001a3712b3b882e856a4f108e28998bbf513fd83fdc`，由 `.gitignore:39` 忽略且未被 Git 跟踪。文件非重解析点，`fsutil hardlink list` 只列本路径；独占读写打开成功后释放。命令行快照未发现目标日志的写者；快照和释放后的独占测试不能排除未来写入。未停止训练或其他进程。

含忽略文件的本机仓库文本扫描覆盖 Python、脚本、JSON、YAML、Markdown 等 2,924 文件，无读取错误；未见目标完整文件名或相关直接通配符读取代码。该扫描不覆盖二进制、归档内文件、仓库外路径或动态构造名称，不能证明所有消费者不存在。历史配置记录以 `rl_exp/out/lizard2_v4_` 前缀笼统引用失败/中间日志；应先按下方入口显式恢复，再读取，不提供旧路径透明映射。

删前在全新系统临时根按 manifest 实际恢复，与原件完整逐字节相同；验证 ZIP 成员、CRC、摘要及大小。实际解析 38 个资产路径：URDF 635 条、USDA 1,678 条、OBJ 223,268 条 `trailing whitespace.`，以及 USDA 1 条 `new blank line at EOF.`。日志行保留 CRLF；这些是原日志中的失败诊断，不代表检查通过或日志可由今天的工作树重跑。历史记录 `acceptance/records/2026-10-23-lizard2-v4-configuration.md` 当前 SHA-256 为 `32bbd02d74b6582bebd64a19a6cacf8a103d0bb3dc78ce52f956f9e6c2d985a9`，与其独立审核记录所绑定摘要一致；原文未改。

删除前再次确认绝对路径及全部父路径无重解析点、单硬链接、未跟踪，并将原件与归档 blob 完整逐字节比较、重算两者摘要；只删除 `E:\Robot\rl_exp\out\lizard2_v4_staged_whitespace.log`，确认旧位置不存在。删后独立执行下方记录内的恢复命令，实际写入新系统临时根并复核完整摘要及失败语义。归档较原件小，输出根净减少 31,662,995 字节。两次复读结果一致；不以删后哈希声称再次与已删除原件直接比较。成功恢复的三处临时目录已清理。事项格式检查通过，定位器加载索引通过。

## 证据引用

本机归档 `rl_exp/out/archive/diagnostic-development/lizard2-v4-staged-whitespace-20261023.zip`，2,691,211 字节，SHA-256 `a99a1baeec11fd9129f80e479a190d9d95b8e11eb57ade8fa9b456f0fb9edd94`。`manifest.json` 的 `files` 映射逻辑路径至 `size_bytes` 和 `sha256`；内容位于 `blobs/<sha256>`。归档被 Git 忽略、未随 Git 分发；未建立或核实外部备份。

在仓根以 Python 运行以下命令，核对整包和成员、在全新临时根恢复真实文件并解析失败行；打印恢复路径，查看后自行清理。异常时保留该路径作为失败现场。

```cmd
python -B -c "import pathlib,tempfile,hashlib,zipfile,json,re,collections; a=pathlib.Path('rl_exp/out/archive/diagnostic-development/lizard2-v4-staged-whitespace-20261023.zip'); h='8b9dbaf9ccb1b02bc0cc7001a3712b3b882e856a4f108e28998bbf513fd83fdc'; rel='rl_exp/out/lizard2_v4_staged_whitespace.log'; hashlib.sha256(a.read_bytes()).hexdigest()=='a99a1baeec11fd9129f80e479a190d9d95b8e11eb57ade8fa9b456f0fb9edd94' or (_ for _ in ()).throw(ValueError('archive digest')); z=zipfile.ZipFile(a); m=json.loads(z.read('manifest.json')); m['files']=={rel:{'size_bytes':34354206,'sha256':h}} and sorted(z.namelist())==sorted(['manifest.json','blobs/'+h]) and z.testzip() is None or (_ for _ in ()).throw(ValueError('manifest')); t=pathlib.Path(tempfile.mkdtemp(prefix='robot-v4-whitespace-')); print('RESTORE_DIR',t,flush=True); p=t/rel; p.parent.mkdir(parents=True); p.write_bytes(z.read('blobs/'+h)); b=p.read_bytes(); len(b)==34354206 and hashlib.sha256(b).hexdigest()==h or (_ for _ in ()).throw(ValueError('restored bytes')); pat=re.compile(rb'^([^\r\n]+\.(?:urdf|usda|obj)):(\d+): (trailing whitespace\.|new blank line at EOF\.)\r?\n$',re.I); rows=[(i,m.group(1),m.group(2),m.group(3),line) for i,line in enumerate(b.splitlines(keepends=True),1) if (m:=pat.match(line))]; counts=collections.Counter((pathlib.PurePosixPath(x[1].decode()).suffix,x[3].decode()) for x in rows); print('COUNTS',counts,'PATHS',len(set(x[1] for x in rows))); print('SAMPLES',*[repr(next(x for x in rows if x[1].endswith(s))) for s in (b'.urdf',b'.usda',b'.obj')]); counts=={('.urdf','trailing whitespace.'):635,('.usda','trailing whitespace.'):1678,('.usda','new blank line at EOF.'):1,('.obj','trailing whitespace.'):223268} and len(set(x[1] for x in rows))==38 or (_ for _ in ()).throw(ValueError('semantic mismatch'))"
```

独立审核重新核算 ZIP、成员和原始摘要，按上述命令恢复并解析 URDF、USDA、OBJ 失败行，确认旧路径不存在；错误摘要在 `-O` 下明确拒绝。审核指出从原配置记录难发现恢复入口，已在 `rl_exp/docs/diagnostic_artifacts.md` 增加路由；旧路径不透明解析。审核不能重证删前原件、写者及独占打开状态，也未完成总事项审核。

## 未覆盖边界

本机归档不是异地备份。只覆盖此日志，不扩大到其他日志或资产；不证明未来无消费者，不证明原始命令退出码，也不对正式资产或配置重新验收。原历史配置与审核记录未改。
