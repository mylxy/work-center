---
name: yunxiao-project
description: Use only when the user explicitly invokes $yunxiao-project; safely resolve one Yunxiao Work Item URL, ID, or project-scoped Number and return a read-only compact or full view through the official hosted MCP.
metadata:
  disable-model-invocation: true
---

# YunXiaoProject

通过阿里云官方托管的云效 MCP，以当前用户的 OAuth 身份精确定位并读取一个 Work Item。支持 Work Item URL、Work Item ID 和限定在一个明确项目内的 Work Item Number，并保持全程只读。

## 执行边界

- 仅使用 `agents/openai.yaml` 声明的 `yunxiao` MCP；运行时只接受中心版托管端点及 `project-management` toolset。
- 允许的项目管理能力只有 `search_workitems`、`get_work_item`、`list_work_item_comments` 和 `list_workitem_activities`。任何工具调用前先做能力门禁：ID/URL-ID 紧凑视图需要 `get_work_item` 与 `list_work_item_comments`；Number/URL-Number 还需要 `search_workitems`；完整视图还需要 `list_workitem_activities`。本次路径任一能力缺失时立即输出“缺少能力”并保持零工具调用，包括不得调用 `get_current_user` 等基础身份工具。只有能力门禁通过且 organization ID 仍缺失时，才可使用 MCP 自带的基础身份或组织发现工具确定当前身份与 organization ID。不得调用项目搜索或任何写工具。
- 以 MCP 运行时公布的工具名称和输入 schema 为准。缺少本次读取需要的精确工具时停止，不用相近工具猜测替代。
- 保持只读。不得更新 Status、创建评论或执行其他变更。
- MCP 是唯一后端。连接失败时按下方错误分类停止，不切换到 CLI、curl、直接 OpenAPI 或浏览器自动化。
- OAuth 凭证由宿主管理。不得索取、读取、显示或保存 PAT、OAuth token、Authorization header 或其他凭证。

## 读取配置

先读取同目录的 `profile.yaml`：

- `mcp_endpoint` 必须与声明的中心版托管端点一致。
- `organization_id` 是非敏感配置。值为空时，优先使用 MCP 的基础身份或组织发现能力；仍无法唯一确定时，只请求用户补充 organization ID，不猜测。
- `default_project_id` 是可选的非敏感配置，仅用于解析 Work Item Number。值为空且请求没有提供项目上下文时，只请求用户补充 project ID 或配置默认项目，不搜索、不猜测。

## 解析请求

只接受本次显式调用中用户指定的一个目标：

1. 明确标注为 Work Item ID 的值直接作为不透明 ID 使用；保留原文，不修剪内部字符、不补齐、不改写大小写。
2. URL 只做本地安全解析，不访问该网页。对路径中明确命名的 `organization/{值}`、`project/{值}`、`workitem/{值}`，以及查询参数 `organizationId`、`projectId`、`workItemId`、`serialNumber`，各自提取至多一个 URL 解码一次后的非空值。多个来源对同一概念给出冲突值时停止并请求用户澄清，不猜测。
3. URL 中的 organization、project 和 Work Item 线索优先于 profile 中对应的默认值。明确的 `workItemId` 或 `workitem/{值}` 作为不透明 Work Item ID 直接读取；`serialNumber` 按 Number 路径解析。URL 没有可用 Work Item 线索时停止。
4. Work Item Number 使用 URL 或用户明确给出的单个 project ID；否则只使用 profile 的 `default_project_id`。必须恰好得到一个 project ID。
5. 解析 Number 时只调用一次 `search_workitems`，参数必须同时包含 organization ID、这个 project ID 和原始 Work Item Number。不得省略项目范围或改为跨项目搜索。
6. 在返回集合中只以 `serialNumber` 与原始 Work Item Number 做精确、完整匹配。恰好一个精确匹配时采用该结果的 Work Item ID；零个或多个精确匹配时停止，不调用 `get_work_item`，也不选择近似项或第一个结果。
7. 用户没有明确提供 ID、Number 或可安全解析的 URL，或提供多个目标时，请求一个受支持的单一标识并停止。
8. 不通过试探多个 organization、project 或 Work Item 来推断目标。

## 读取 Work Item

确认 MCP、OAuth、本次需要的工具、organization ID 和唯一 Work Item ID 均可用后：

1. 按运行时 schema 将 organization ID 与 Work Item ID 传给 `get_work_item`。
2. 对同一个 Work Item ID 使用 `list_work_item_comments`。如果运行时 schema 和响应提供分页游标，完整视图必须以服务端返回的下一页游标继续读取，直到游标为空；每个游标最多使用一次，不能猜测游标。紧凑视图也必须取得足以按 `createdAt` 确定最近五条的数据。用户明确要求完整详情时，再对这个 ID 调用一次 `list_workitem_activities`；默认紧凑视图不得调用活动工具。ID 直接输入时，不调用 `search_workitems`；Number 输入时只能读取精确匹配得到的唯一 ID。
3. 不读取其他 Work Item，也不把错误结果转换为额外搜索请求。搜索结果集合绝不能成为批量读取或批量写入目标。

成功时默认返回紧凑视图，优先使用 MCP 返回的字段并包含：

- Work Item ID 与 Work Item Number（若返回）；
- 标题、项目、云效返回的原始类型；
- 当前 Status、优先级、负责人；
- 描述的简短原文摘要；
- 有值且与用户理解该 Work Item 有关的自定义字段；
- 按 `createdAt` 确定的最近五条评论，包含作者、时间和内容。即使服务端返回更多评论，也不要在紧凑视图展示更早的评论。

缺失字段标记为“未提供”，不推断值。紧凑视图不要声称读取了活动或工作流。

用户明确要求“完整详情”“全部字段”或同等含义时返回完整视图：

- 原样呈现 `get_work_item` 返回的全部可用字段，包括服务端返回的空值；
- 呈现 `list_work_item_comments` 返回的完整评论集合，不截断为五条；
- 呈现 `list_workitem_activities` 返回的最近活动，包括动作、详情和时间；
- 不把活动解释成未返回的工作流规则，也不因完整视图扩大到其他 Work Item。

## 区分错误

失败时保留云效返回的有用业务信息，必须以以下加粗分类名称作为标题，并明确指出下一步：

- **MCP 未配置或不可连接**：服务器未声明、初始化失败、工具发现请求本身失败，或运行时完全没有 `yunxiao` MCP 命名空间时使用。其他 MCP、内置工具或多代理工具的存在不能证明云效 MCP 已连接。指出需要安装或启用声明的 `yunxiao` 托管 MCP，并核对中心版 endpoint；停止。
- **未认证或认证过期**：要求通过宿主重新完成云效 OAuth 授权；不建议 PAT。
- **缺少能力**：至少一个属于 `yunxiao` MCP 命名空间的基础工具已暴露，证明云效 MCP 已连接，但本次路径缺少 `search_workitems`、`get_work_item`、`list_work_item_comments` 或 `list_workitem_activities` 中所需能力时使用；不得把其他命名空间的工具当作连接证据。点名缺少的工具，要求检查 `project-management` toolset 或服务端能力；停止。
- **配置不足**：点名缺少或无法唯一确定的 organization ID 或 project ID，并只请求该非敏感值。
- **目标不唯一**：Work Item Number 搜索出现多个 `serialNumber` 精确匹配时，报告匹配数量并要求用户核对项目或提供 Work Item ID；不得选择目标。
- **无权限**：返回云效的权限错误，并要求为当前 OAuth 身份授予目标 Work Item 的只读权限。
- **目标不存在或输入无效**：指出该 Work Item ID 未找到或不被接受，不搜索相似目标。

任何成功或失败路径都不得触发真实 Status 更新、评论写入或其他副作用。
