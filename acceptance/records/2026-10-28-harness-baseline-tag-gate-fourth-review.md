# Harness 基线声明解析第四次独立审核（2026-10-28）

## 适用范围

- 不带执笔历史的新上下文审核 `harness-baseline-tag-gate` 的声明解析与隔离 CLI。
- 本闸只检查本地标签名称与声明，不证明标签指向、远端推送或测量能力。

## 验收条件

- 歧义语法不得导致实际声明被静默吞掉；原破坏测试红、恢复绿，回归测试可复读。

## 结果

**不通过。** 声明之后追加单个 Tab 缩进的围栏、ASCII 冒号第二条声明及结束围栏，隔离默认 CLI 与 `--self-test` 均错误退出 0，第二条声明被吞掉。这违反执行记录所述的“缩进围栏拒绝”边界；单个 Tab 未被按四个空格的缩进处理。

- 执行记录中两组隔离测试退出 0、`failures: []`；原缺标签与删冒号两模式均退出 1，恢复后退出 0。
- 真实仓自测退出 0、64 fixtures；默认检查退出 0、`VERSION_DOCS_OK`。Git 不可执行、空标签、自测夹具破坏与隔离 suite 失败传播符合已有测试预期。
- 以下命令在执行记录的第二组临时隔离 CLI 测试中插入 Tab 缩进反例；本次测试进程退出 1，两个 CLI 子进程均错误退出 0：

```bat
python -B -c "import pathlib; p=pathlib.Path('acceptance/records/2026-10-28-harness-baseline-tag-gate-execution.md'); q=chr(96)*3; s=p.read_text(encoding='utf-8').split(q+'python')[2].split(q,1)[0]; marker=\"('ASCII colon',\"; extra=\"('tab-indented fence hides duplicate', text + chr(10) + chr(9) + chr(96)*3 + chr(10) + needle.replace(chr(65306), ':') + chr(10) + chr(96)*3 + chr(10), 1, ('ambiguous',)),\" + chr(10) + '            '; assert s.count(marker)==1; exec(compile(s.replace(marker,extra+marker), 'indented-fence-cli', 'exec'))"
```

## 证据引用

- 落点：`rl_exp/tools/verify/check_version_docs.py` 的声明扫描、缩进围栏判别与 `baseline_tag_problem`。
- 前次独立审核：`acceptance/records/2026-10-28-harness-baseline-tag-gate-third-review.md`；当前执行与隔离复读：`acceptance/records/2026-10-28-harness-baseline-tag-gate-execution.md`。

## 未覆盖边界

- 须修复 Tab 缩进并补修前失败、修后通过的持久与隔离 CLI 测试；证据变化后须独立复审。也须重新评估声明解析复杂度，避免为单条声明无限扩写 Markdown 解析器。
- 本次未独立回退第三轮修复重跑历史红灯；只能引用执行者记录。完整离线套件及外部调用方未验证。
