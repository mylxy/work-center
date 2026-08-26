# 领域文档

工程技能探索代码库时，应按以下规则使用本仓库的领域文档。

## 探索前读取

- 读取仓库根目录的 `CONTEXT.md`。
- 如果根目录存在 `CONTEXT-MAP.md`，则由它定位各上下文的 `CONTEXT.md`，并读取与当前主题有关的文件。
- 读取 `docs/adr/` 中与即将处理区域有关的 ADR。在 multi-context 仓库中，还应检查 `src/<context>/docs/adr/` 下的上下文级决策。

如果这些文件不存在，直接继续，不要报告缺失，也不要预先建议创建。`/domain-modeling` 技能会在术语或决策真正得到确认时按需创建它们。

## 文件结构

本仓库采用 single-context 布局：

```text
/
├── CONTEXT.md
├── docs/adr/
│   ├── 0001-event-sourced-orders.md
│   └── 0002-postgres-for-write-model.md
└── src/
```

若仓库以后演化为 multi-context 布局，则在根目录使用 `CONTEXT-MAP.md`：

```text
/
├── CONTEXT-MAP.md
├── docs/adr/                          ← 系统级决策
└── src/
    ├── ordering/
    │   ├── CONTEXT.md
    │   └── docs/adr/                  ← 上下文级决策
    └── billing/
        ├── CONTEXT.md
        └── docs/adr/
```

## 使用术语表中的词汇

当输出内容提及领域概念时——例如 Issue 标题、重构建议、假设或测试名称——应采用 `CONTEXT.md` 定义的术语，不要改用术语表明确回避的同义词。

如果所需概念尚未出现在术语表中，应重新判断它是否是项目实际使用的语言；若确实存在领域空缺，则记录下来，交由 `/domain-modeling` 处理。

## 标记 ADR 冲突

如果输出与现有 ADR 冲突，应明确指出，而不是静默覆盖。例如：

> 与 ADR-0007（事件溯源订单）冲突，但由于……值得重新讨论。
