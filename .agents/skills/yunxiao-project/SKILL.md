---
name: yunxiao-project
description: Use only when the user explicitly invokes $yunxiao-project; safely resolve and view one Yunxiao Work Item, or create one verified top-level comment through the official hosted MCP.
metadata:
  disable-model-invocation: true
---

# YunXiaoProject

通过阿里云官方托管的云效 MCP，以当前用户的 OAuth 身份精确定位并读取一个 Work Item，或为它安全创建一条顶层评论。支持 Work Item URL、Work Item ID 和限定在一个明确项目内的 Work Item Number。

## 执行边界

- 仅使用 `agents/openai.yaml` 声明的 `yunxiao` MCP；运行时只接受中心版托管端点及 `project-management` toolset。
- 允许的项目管理能力只有 `search_workitems`、`get_work_item`、`list_work_item_comments`、`list_workitem_activities` 和 `create_work_item_comment`。任何工具调用前先做能力门禁：ID/URL-ID 紧凑视图需要 `get_work_item` 与 `list_work_item_comments`；Number/URL-Number 还需要 `search_workitems`；完整视图还需要 `list_workitem_activities`；评论创建需要 `get_work_item`、`create_work_item_comment` 与 `list_work_item_comments`。本次路径任一能力缺失时立即输出“缺少能力”并保持零工具调用，包括不得调用 `get_current_user` 等基础身份工具。只有能力门禁通过且 organization ID 仍缺失时，才可使用 MCP 自带的基础身份或组织发现工具确定当前身份与 organization ID。不得调用项目搜索、Status 更新或其他写工具。
- 以 MCP 运行时公布的工具名称和输入 schema 为准。缺少本次读取需要的精确工具时停止，不用相近工具猜测替代。
- 读取路径保持只读；评论路径只创建一条顶层评论。不得更新 Status 或执行其他变更。
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

## 创建顶层评论

评论请求沿用上述配置和目标解析规则，但每次只接受一个已精确解析的 Work Item。请求包含多个目标，或要求回复、编辑、删除、置顶既有评论时，说明第一版只支持为单个 Work Item 创建一条顶层评论并停止，不调用写工具。

1. 用户明确给出“评论原文”或等价的完整正文时，把该范围内的字符作为评论内容；保留空白、标点、大小写和换行，不润色，不添加签名、前后缀或时间戳。用户只描述评论意图时，根据意图生成一段可直接提交的完整评论草稿，不把“评论意图”等请求措辞写进正文。
2. 在能力门禁通过后，先用 `get_work_item` 确认唯一目标。普通请求以 **业务预览** 展示 Work Item 身份和 **评论草稿** 的完整逐字内容，请用户确认后停止；此时不调用 `create_work_item_comment`。
3. “直接评论”“立即执行”或“无需确认”等明确执行标记可以跳过业务预览。标记本身不是评论正文。Codex MCP 写工具审批和云效权限仍然生效；skill 不得声称或尝试绕过它们。
4. 业务预览被用户确认，或请求含明确执行标记时，先调用一次 `list_work_item_comments` 并保留返回的评论 ID 集合作为写前快照；既有同文评论不自动取消用户明确请求。然后按运行时 schema 调用 `create_work_item_comment` 恰好一次，只传 organization ID、Work Item ID 和完整评论内容；不传 parent/reply、编辑、删除或置顶参数。
5. 创建返回成功后，立即对同一 Work Item 再调用一次 `list_work_item_comments`。以创建响应中的评论 ID、作者身份和逐字内容确认该 ID 出现在回读结果中，且不属于写前快照。成功输出包含 Work Item、评论 ID、作者和完整内容；回读确认前不宣称成功。
6. 如果创建调用可能已到达服务端但传输结果不明确，仍按第 5 步回读，不再次调用创建工具。只有写后出现不在快照中的新评论 ID，且其作者身份和逐字内容与本次操作一致时，才确认成功。没有新增 ID、只有既有同文评论或证据不完整时，以 **结果不确定** 报告原始传输信息、已检查的 Work Item 和完整评论内容，明确说明不会自动重试，然后停止；不把这类写入结果归类为普通 MCP 连接失败，也不建议直接重新提交。

## 区分错误

失败时保留云效返回的有用业务信息，必须以以下加粗分类名称作为标题，并明确指出下一步：

- **MCP 未配置或不可连接**：服务器未声明、初始化失败、工具发现请求本身失败，或运行时完全没有 `yunxiao` MCP 命名空间时使用。其他 MCP、内置工具或多代理工具的存在不能证明云效 MCP 已连接。指出需要安装或启用声明的 `yunxiao` 托管 MCP，并核对中心版 endpoint；停止。
- **未认证或认证过期**：要求通过宿主重新完成云效 OAuth 授权；不建议 PAT。
- **缺少能力**：至少一个属于 `yunxiao` MCP 命名空间的基础工具已暴露，证明云效 MCP 已连接，但本次路径缺少 `search_workitems`、`get_work_item`、`list_work_item_comments`、`list_workitem_activities` 或 `create_work_item_comment` 中所需能力时使用；不得把其他命名空间的工具当作连接证据。点名缺少的工具，要求检查 `project-management` toolset 或服务端能力；停止。
- **配置不足**：点名缺少或无法唯一确定的 organization ID 或 project ID，并只请求该非敏感值。
- **目标不唯一**：Work Item Number 搜索出现多个 `serialNumber` 精确匹配时，报告匹配数量并要求用户核对项目或提供 Work Item ID；不得选择目标。
- **写入未获批准**：宿主返回用户取消或拒绝 `create_work_item_comment` 时使用。明确说明 Codex MCP 写工具审批未获批准、服务端调用没有执行；停止且不回读、不重试。
- **无权限**：返回云效的权限错误，并按当前操作要求为 OAuth 身份授予目标 Work Item 的只读或评论创建权限。
- **业务规则拒绝**：工具已执行且云效以业务校验、必填字段或项目规则明确拒绝当前操作时使用。保留错误码与消息，指出需要修改的评论内容或业务条件；停止且不自动重试。
- **目标不存在或输入无效**：解析或读取目标时指出该 Work Item ID 未找到或不被接受，不搜索相似目标。已确认目标后的评论正文校验失败属于“业务规则拒绝”，不归入本类。

除用户明确请求的单条顶层评论外，任何成功或失败路径都不得触发真实 Status 更新或其他副作用。
