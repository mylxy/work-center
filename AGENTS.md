# Agent instructions

### 工作树与任务边界

开始任务时，先查看并记录项目主检出目录当前所在的分支，称为“起始分支”。起始分支同时是任务分支的创建来源和任务完成后的合并目标。如果主检出目录未处于命名分支，必须先明确起始分支，再创建任务。

1. 从起始分支创建任务分支和专用的 linked worktree。
2. 所有代码和文档修改都必须在该 worktree 中完成，禁止直接修改主检出目录。
3. 任务执行期间，即使主检出目录切换到其他分支，起始分支也不得改变。
4. 同一目标的补充要求继续使用原任务分支和 worktree；目标改变时，以新任务开始时主检出目录所在的分支作为新的起始分支，并创建新的任务分支和 worktree。
5. 任务完成后，必须合并回任务开始时记录的起始分支。

例如：任务从分支 `B` 开始，即使主检出目录后来切换到分支 `C`，该任务仍然从 `B` 签出并最终合并回 `B`。如果任务开始时位于 `master`，则从 `master` 签出并合并回 `master`。

### 提交与合并

提交使用中文 Conventional Commits：`<type>(<scope>): <中文描述>`，每个提交只处理一个主题。

任务分支可按完成单元主动提交；直接修改起始分支时，只有用户明确要求才可提交。不得擅自 amend、rebase、squash 或改写用户已有提交。

合并、推送和发布必须先获得用户明确授权。合并目标默认为起始分支；获授权后必须使用 `git merge --no-ff <任务分支>`，禁止快进或 squash。

合并信息：

```text
merge(<范围>): <中文任务摘要>

任务背景：...
主要改动：...
验证结果：...
影响范围：...
```

## Agent skills

### Issue tracker

Issues 与规格记录在本仓库的 GitHub Issues 中。详见 `docs/agents/issue-tracker.md`。

### Triage labels

使用五个默认 triage 标签：`needs-triage`、`needs-info`、`ready-for-agent`、`ready-for-human`、`wontfix`。详见 `docs/agents/triage-labels.md`。

### Domain docs

采用 single-context 领域文档布局。详见 `docs/agents/domain.md`。
