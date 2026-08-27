# YunXiaoProject Skill Specification

## Problem Statement

用户需要在 Codex 中通过云效项目的 Defect 标识快速读取 Work Item、理解当前 Status、查看评论、修改 Status 和添加评论。目前这些操作需要切换到云效页面并手工定位项目、解析状态和完成写入；用户也不确定云效现有接口是否足以安全地自动化这些操作。

用户希望获得一个仅在手动调用时生效的个人 skill。它必须区分 Work Item ID 与 Work Item Number，遵循云效实际工作流和权限，避免错误状态流转、重复评论、跨项目误匹配及凭证泄露。

## Solution

创建显示名为 `YunXiaoProject`、调用名为 `$yunxiao-project` 的个人 Codex skill。该 skill 只依赖阿里云官方托管的云效 MCP，通过 OAuth 使用用户身份，并把工具范围限制在项目、Work Item、工作流、活动和评论所需的最小集合。

skill 接受 Work Item URL、Work Item Number 或 Work Item ID。它将输入解析为唯一 Work Item ID，读取目标 Work Item 及其工作流，以唯一匹配的 Status ID 完成状态更新，并在每次写入后回读验证。普通写入请求先展示业务预览；明确包含“立即执行”“直接修改”“直接评论”或“无需确认”等标记时可以跳过业务预览，但仍受 Codex MCP 写工具审批和云效权限控制。

## User Stories

1. As a Yunxiao user, I want to invoke `$yunxiao-project` manually, so that ordinary conversations about defects do not activate external tools.
2. As a Yunxiao user, I want to provide a Work Item URL, so that the skill can locate the intended Work Item without asking me to copy an internal identifier.
3. As a Yunxiao user, I want to provide a human-visible Work Item Number, so that I can use the identifier shown in the Yunxiao UI.
4. As a Yunxiao user, I want to provide an opaque Work Item ID, so that the skill can retrieve an already-resolved Work Item directly.
5. As a Yunxiao user, I want Work Item Number resolution to be limited to one known project, so that a similarly named item in another project is never selected by guesswork.
6. As a Yunxiao user, I want the skill to stop when a Work Item Number cannot be resolved uniquely, so that no read or write targets the wrong Work Item.
7. As a Yunxiao user, I want a compact Work Item view by default, so that I can quickly understand its title, project, type, Status, priority, assignee, description, relevant custom fields, and recent comments.
8. As a Yunxiao user, I want to request full details, so that I can inspect all available fields, comments, and recent activities when diagnosing a complex Defect.
9. As a Yunxiao user, I want to view the current Status and available workflow states, so that I can make an informed transition request.
10. As a Yunxiao user, I want to name a target Status using its display name, so that I do not need to know an opaque Status ID.
11. As a Yunxiao user, I want the skill to resolve a Status display name to exactly one Status ID, so that ambiguous or unknown labels never cause a write.
12. As a Yunxiao user, I want the skill to respect Yunxiao workflow restrictions, role restrictions, and required-field gates, so that it does not claim an invalid transition is possible.
13. As a Yunxiao user, I want rejected status transitions to return the relevant Yunxiao business error, so that I know whether the failure concerns permissions, workflow rules, or missing fields.
14. As a Yunxiao user, I want a proposed status change to show the Work Item, current Status, target Status, and acting identity, so that I can review ordinary writes before execution.
15. As a Yunxiao user, I want explicit execution phrases to skip the skill-level preview, so that deliberate one-step actions remain efficient.
16. As a Yunxiao user, I want Codex's MCP write approval to remain authoritative, so that skill wording cannot bypass host security controls.
17. As a Yunxiao user, I want to list recent Work Item comments, so that I can understand the latest discussion without opening Yunxiao.
18. As a Yunxiao user, I want exact comment text to be preserved, so that the skill does not change wording, add signatures, or append timestamps.
19. As a Yunxiao user, I want the skill to draft a comment when I provide only an intent, so that I can review an appropriate message before it is posted.
20. As a Yunxiao user, I want an explicit direct-comment instruction to post the drafted comment without a separate business preview, so that deliberate comments can be added quickly.
21. As a Yunxiao user, I want comments to be top-level in the first version, so that reply-thread semantics are not guessed.
22. As a Yunxiao user, I want writes to affect exactly one Work Item, so that search results or lists cannot accidentally become batch operations.
23. As a Yunxiao user, I want every status update to be verified by rereading the Work Item, so that I receive the observed final Status rather than an assumed success.
24. As a Yunxiao user, I want every comment creation to be verified against the comment list, so that I know whether the comment exists.
25. As a Yunxiao user, I want uncertain write outcomes to stop without automatic retries, so that transient failures cannot create duplicate comments or repeated side effects.
26. As a Yunxiao user, I want authentication to use OAuth, so that a personal access token is not stored in the skill or project.
27. As a Yunxiao user, I want the skill to use the official hosted MCP endpoint, so that I do not need to install or maintain a local server.
28. As a Yunxiao user, I want the skill to declare its MCP dependency, so that missing execution capabilities are visible during setup.
29. As a Yunxiao user, I want only project-management tools exposed, so that unrelated repository, pipeline, deployment, package, and test-management actions are unavailable.
30. As a Yunxiao user, I want non-sensitive organization and default-project information saved separately from credentials, so that Work Item Numbers can be resolved consistently without exposing secrets.
31. As a Yunxiao user, I want missing organization or project configuration to produce a focused setup request, so that the skill never invents identifiers.
32. As a Yunxiao user, I want MCP connection, authentication, capability, and permission errors to be distinguished, so that I know which layer needs attention.
33. As a Yunxiao user, I want the skill to stop when MCP is unavailable, so that it never silently switches to a less visible CLI, curl, or browser automation path.
34. As a Yunxiao user, I want read-only connectivity validation during installation, so that setup can be checked without modifying production Work Items.
35. As a Yunxiao user, I want live write tests to require a separately identified safe Work Item and explicit authorization, so that installation does not produce real project changes.

## Implementation Decisions

- The canonical Work Item vocabulary comes from the project glossary. A Defect is a Work Item whose Yunxiao category is `Bug`; Work Item ID and Work Item Number are distinct concepts.
- The skill machine name and invocation are `yunxiao-project` and `$yunxiao-project`. The human-facing display name is `YunXiaoProject`.
- Invocation is explicit-only. Both the skill frontmatter and UI policy disable implicit/model invocation.
- The first version is a personal skill rather than a team-shared repository capability.
- The only execution backend is Alibaba Cloud's officially hosted Yunxiao MCP. Yunxiao CLI, direct OpenAPI calls, curl, and browser automation are not runtime fallbacks.
- The deployment target is the Yunxiao central edition. The MCP endpoint is the official central Streamable HTTP endpoint with only the `project-management` toolset requested.
- Authentication uses the MCP server's OAuth authorization-code flow with PKCE. The skill and repository never store access tokens, refresh tokens, Authorization headers, or PAT values.
- The skill declares the Yunxiao MCP as a required tool dependency. If the dependency is missing or unavailable, execution stops with setup guidance.
- The MCP capability surface is allowlisted to project lookup, Work Item search and retrieval, workflow retrieval, comment listing and creation, activity listing, and Work Item update. Base identity tools supplied by the server may be used for organization and acting-user discovery.
- The intended tool set consists of `search_projects`, `search_workitems`, `get_work_item`, `get_work_item_workflow`, `list_work_item_comments`, `list_workitem_activities`, `update_work_item`, and `create_work_item_comment`, subject to capability discovery from the current hosted server.
- The hosted MCP's reported capabilities are the source of truth at runtime. The skill does not depend on a fixed total tool count or a client-pinned server version.
- Non-sensitive profile data records the central endpoint, organization ID, and optional default project ID. Credential material is not part of the profile.
- A URL is parsed for available organization, project, and Work Item identity. An opaque Work Item ID is used directly. A Work Item Number is resolved through `search_workitems` within one known project, followed by exact `serialNumber` comparison.
- `search_workitems` is never treated as a cross-project unique lookup. If the project is unknown, the skill requests or resolves one project before searching. Zero or multiple exact matches stop the operation.
- Compact view returns identity, project, type, Status, priority, assignee, description, relevant custom fields, and the five most recent comments. Full-detail view additionally returns all available fields, complete comments, and recent activities.
- A requested Status display name is compared only with workflow states returned for the Work Item's project and type. Exactly one match is required. The update payload uses the matched Status ID.
- Workflow-state presence does not imply that every transition is legal. Backend workflow, role, permission, and required-field errors are surfaced without claiming that arbitrary state jumps are supported.
- A normal status mutation presents a semantic preview containing target Work Item, current Status, target Status, and acting identity. A normal generated comment presents its complete text.
- Explicit phrases such as “立即执行”, “直接修改”, “直接评论”, and “无需确认” may skip the skill's semantic preview. They do not override Codex approval policy or Yunxiao authorization.
- MCP write tools use the host's write-approval mode. Security approval is independent from conversational confirmation.
- User-supplied comment content is passed unchanged. When only intent is supplied, the skill drafts the content. The first version creates top-level comments only.
- Mutations are single-Work-Item operations. A search may show multiple candidates for user selection, but the skill never turns a result set into batch updates.
- After a status update, the skill rereads the Work Item and may consult activities to verify the observed Status. After comment creation, it rereads comments to verify the new comment.
- An ambiguous transport result triggers verification before any retry. If verification cannot establish success or failure, the skill reports an uncertain outcome and stops. Comment creation is never automatically retried.
- Missing tools, authentication, organization context, project context, permissions, or workflow requirements produce distinct actionable errors. There is no silent backend substitution.
- The skill package contains concise agent instructions, product metadata and invocation policy, MCP dependency metadata, and a non-secret profile. No wrapper script is required.
- The MCP-only architecture is intentionally easy to extend later. CLI can be added as a separately approved diagnostic workflow if observed hosted-MCP limitations justify the added maintenance cost.

## Testing Decisions

- The primary behavioral seam is a single high-level boundary: manual skill invocation against a controlled MCP implementation, observing requested MCP tools, arguments, confirmation behavior, and user-visible output. Tests should assert externally visible behavior rather than instruction wording or internal prompt structure.
- The controlled MCP should model successful reads, ambiguous Work Item Number searches, zero and multiple Status matches, permission failures, workflow failures, transport ambiguity, successful write verification, and failed verification.
- Input-contract coverage includes Work Item URL, Work Item Number, Work Item ID, missing project context, wrong project context, and exact candidate selection.
- Read behavior coverage includes compact detail, full detail, recent-comment limits, complete comments, and activities.
- Status behavior coverage includes unique display-name resolution, Status ID submission, rejected transitions, ordinary preview, explicit execution phrases, and post-write reread.
- Comment behavior coverage includes exact-content preservation, drafted-content preview, explicit direct comment, top-level-only behavior, duplicate-risk handling, and post-write verification.
- Safety coverage asserts that multiple search results cannot cause batch writes, missing MCP tools cannot trigger CLI or curl, and uncertain comment outcomes cannot auto-retry.
- Configuration coverage checks explicit-only invocation, MCP dependency metadata, central hosted endpoint, project-management toolset restriction, tool allowlist, write approval policy, and absence of credential values.
- Structural validation uses the skill validator to check frontmatter, naming, UI metadata, invocation policy, and unfinished scaffold content.
- Installation validation performs OAuth authentication and read-only calls for current identity/organization and one authorized project or Work Item. It does not perform a live mutation.
- Live status or comment tests require a separately supplied safe Work Item and explicit authorization for the exact mutation.
- No existing automated test seam or comparable skill test suite was found in the current project. The controlled-MCP invocation seam is therefore a new high-level seam, while existing skill-validator behavior is reused for package validation.

## Out of Scope

- Automatic or natural-language invocation without explicitly naming `$yunxiao-project`.
- Batch status changes, batch comments, or mutations across multiple Work Items.
- Creating, deleting, archiving, or changing the type of a Work Item.
- Editing title, description, assignee, priority, project, iteration, attachments, estimates, or time records.
- Replying to an existing comment, editing comments, deleting comments, or pinning comments.
- Modifying Yunxiao workflow configuration, Status definitions, permissions, users, roles, or project settings.
- Repository, merge-request, pipeline, deployment, package, and test-management operations.
- Yunxiao CLI installation or use, direct OpenAPI/curl calls, and browser automation fallback.
- Local or self-hosted MCP deployment, Node.js runtime management, and hosted-server version pinning.
- Storing PATs, OAuth tokens, secrets, or static Authorization headers in skill files or project files.
- Live mutation during ordinary installation validation.

## Further Notes

- Official Yunxiao MCP documentation states that the hosted server supports project management, Work Items, Work Item fields, comments, OAuth, and toolset filtering.
- Official Yunxiao APIs distinguish opaque Work Item IDs from human-visible Work Item Numbers. Number resolution remains project-scoped.
- Status updates require a Status ID. Workflow configuration may constrain transitions by current Status, role, user, or required fields.
- Hosted MCP improves installation simplicity but limits client-side access to server logs and server-version control. Capability discovery, actionable error reporting, and write-after-read verification compensate for those constraints.
- This specification is published as GitHub Issue #1 with the `ready-for-agent` label: https://github.com/mylxy/work-center/issues/1
