# Issue tracker：GitHub

本仓库的 Issues 和规格均记录在 GitHub Issues 中。所有操作使用 `gh` CLI。

## 约定

- **创建 Issue**：`gh issue create --title "..." --body "..."`。多行正文使用 heredoc。
- **读取 Issue**：`gh issue view <number> --comments`，同时获取标签，并按需使用 `jq` 过滤评论。
- **列出 Issues**：使用 `gh issue list --state open --json number,title,body,labels,comments --jq '[.[] | {number, title, body, labels: [.labels[].name], comments: [.comments[].body]}]'`，并按需添加 `--label` 和 `--state` 过滤条件。
- **评论 Issue**：`gh issue comment <number> --body "..."`
- **添加或移除标签**：`gh issue edit <number> --add-label "..."` / `--remove-label "..."`
- **关闭 Issue**：`gh issue close <number> --comment "..."`

通过 `git remote -v` 推断仓库；在克隆目录中运行时，`gh` 会自动识别仓库。

## 将 Pull Request 作为 triage 请求入口

**PRs as a request surface: no.**

将其改为 `yes` 后，外部 PR 会采用与 Issue 相同的标签和状态，相关操作使用对应的 `gh pr` 命令：

- **读取 PR**：使用 `gh pr view <number> --comments` 查看内容与评论，使用 `gh pr diff <number>` 查看差异。
- **列出等待 triage 的外部 PR**：运行 `gh pr list --state open --json number,title,body,labels,author,authorAssociation,comments`，只保留 `authorAssociation` 为 `CONTRIBUTOR`、`FIRST_TIME_CONTRIBUTOR` 或 `NONE` 的条目，排除 `OWNER`、`MEMBER` 和 `COLLABORATOR`。
- **评论、添加标签或关闭 PR**：使用 `gh pr comment`、`gh pr edit --add-label` / `--remove-label` 和 `gh pr close`。

GitHub 的 Issues 与 PRs 共用编号空间，因此单独的 `#42` 可能表示任意一种对象。先运行 `gh pr view 42`，失败后再运行 `gh issue view 42`。

## 当技能要求“发布到 issue tracker”时

创建一个 GitHub Issue。

## 当技能要求“获取相关 ticket”时

运行 `gh issue view <number> --comments`。

## Wayfinding 操作

供 `/wayfinder` 使用。**Map** 是单个 Issue，**child** Issues 是其 tickets。

- **Map**：使用带有 `wayfinder:map` 标签的单个 Issue 保存 Notes、Decisions-so-far 和 Fog。通过 `gh issue create --label wayfinder:map` 创建。
- **Child ticket**：通过 sub-issues API 将 Issue 关联为 Map 的 GitHub 子 Issue。如果未启用 sub-issues，则在 Map 正文的任务列表中加入 child，并在 child 正文顶部写入 `Part of #<map>`。标签为 `wayfinder:<type>`，其中类型为 `research`、`prototype`、`grilling` 或 `task`。ticket 被认领后，将其分配给负责实现的开发者。
- **Blocking**：以 GitHub 原生 Issue dependencies 作为规范且在 UI 中可见的表示。使用 `gh api --method POST repos/<owner>/<repo>/issues/<child>/dependencies/blocked_by -F issue_id=<blocker-db-id>` 添加依赖边。其中 `<blocker-db-id>` 是 blocker 的数字数据库 ID，可通过 `gh api repos/<owner>/<repo>/issues/<n> --jq .id` 获取；它不是 `#number` 或 `node_id`。GitHub 的 `issue_dependencies_summary.blocked_by` 表示仍处于打开状态的 blocker。如果 dependencies 不可用，则在 child 正文顶部使用 `Blocked by: #<n>, #<n>`。所有 blocker 关闭后，ticket 才解除阻塞。
- **Frontier query**：列出 Map 下仍打开的 child Issues；剔除存在打开 blocker 或已有 assignee 的条目，按 Map 中的顺序选择第一个。
- **Claim**：运行 `gh issue edit <n> --add-assignee @me`；这是会话中的第一次写操作。
- **Resolve**：运行 `gh issue comment <n> --body "<answer>"`，然后运行 `gh issue close <n>`，最后在 Map 的 Decisions-so-far 中追加上下文指针及链接。
