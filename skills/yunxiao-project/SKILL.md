---
name: yunxiao-project
description: Use only when the user explicitly invokes $yunxiao-project; safely resolve one Yunxiao Work Item, then read it, transition its Status, or create one verified top-level comment through the official hosted MCP.
metadata:
  disable-model-invocation: true
---

# YunXiaoProject

通过阿里云官方托管的云效 MCP，以当前用户的 OAuth 身份精确定位一个 Work Item，读取其详情、安全流转其 Status，或创建一条经验证的顶层评论。支持 Work Item URL、Work Item ID 和限定在一个明确项目内的 Work Item Number。

## 完成门禁

发送成功响应前，逐项核对当前分支；缺一项就继续完成所需读取，或输出下方定义的错误分类，不能发送部分成功：

- **紧凑读取**：已调用 `get_work_item` 和 `list_work_item_comments`；输出明确标注的 Work Item ID、Work Item Number、标题、项目、类型、Status、优先级、负责人、描述、相关非空自定义字段，以及按 `createdAt` 排序的最近五条评论。每条评论都输出作者、原始时间和完整内容。紧凑读取的调用和输出都不包含活动或工作流。
- **Status 成功**：写后 `get_work_item` 已验证目标 Status；输出明确标注的 Work Item ID、Work Item Number、标题、原 Status、最终 Status 和实际操作身份。
- **评论成功**：写后评论列表已验证创建响应对应的新评论；输出明确标注的 Work Item ID、Work Item Number、评论 ID、作者，并在 `text` 代码块中逐字输出完整正文，使首尾空白与换行可见且保持不变。

必须使用上述明确字段标签；一句“已读取”“已更新”或“已评论”不满足完成门禁。

## 执行边界

- 仅使用 `agents/openai.yaml` 声明的 `yunxiao` MCP；运行时只接受中心版托管端点及 `project-management` toolset。
- 客户端 allowlist 只包含基础身份与组织发现工具 `get_current_organization_info`、`get_user_organizations`、`get_current_user`，项目查找 `search_projects`，以及 `search_workitems`、`get_work_item`、`get_work_item_workflow`、`list_work_item_comments`、`list_workitem_activities`、`update_work_item` 和 `create_work_item_comment`。任何工具调用前先做路径级能力门禁：安装只读验收需要身份/组织能力，并用 `search_projects` 或明确目标的 `get_work_item` 验证一个可访问资源；ID/URL-ID 紧凑视图需要 `get_work_item` 与 `list_work_item_comments`；Number/URL-Number 还需要 `search_workitems`；完整视图还需要 `list_workitem_activities`；Status 流转需要 `get_work_item`、`get_work_item_workflow`、`update_work_item` 和当前身份能力；评论创建需要 `get_work_item`、`create_work_item_comment` 与 `list_work_item_comments`。任一必需能力缺失时立即输出“缺少能力”并保持零工具调用。只有能力门禁通过后，才可使用基础身份或组织发现工具确定当前 OAuth 身份与 organization ID。除显式安装验收或用户明确要求查找项目外，不调用 `search_projects`；不得调用本次路径不需要的写工具。
- 以 MCP 运行时公布的工具名称和输入 schema 为准。缺少本次操作需要的精确工具时停止，不用相近工具猜测替代。
- 读取路径保持只读；Status 流转路径只允许按 [Status 流转](references/status-transition.md) 更新一个 Work Item 的 Status；评论路径只创建一条顶层评论。任何写路径都不得修改其他字段或执行另一类写入。
- MCP 是唯一后端。连接失败时按下方错误分类停止，不切换到 CLI、curl、直接 OpenAPI 或浏览器自动化。
- OAuth 凭证由宿主管理。不得索取、读取、显示或保存 PAT、OAuth token、Authorization header 或其他凭证。

## 读取配置

先读取同目录的 `profile.yaml`：

- `mcp_endpoint` 必须与声明的中心版托管端点一致。
- `organization_id` 是非敏感配置。值非空时，普通读取、Number 解析和评论创建直接使用该值，不额外调用基础身份或组织发现工具；只有 Status 流转为了展示实际操作身份才读取当前用户。值为空时，优先使用 MCP 的基础身份或组织发现能力；仍无法唯一确定时，只请求用户补充 organization ID，不猜测。
- `default_project_id` 是可选的非敏感配置，仅用于解析 Work Item Number。值为空且请求没有提供项目上下文时，只请求用户补充 project ID 或配置默认项目，不搜索、不猜测。

## 安装与只读验收

- 个人安装必须保留同目录完整包，并使用 `$HOME/.agents/skills/yunxiao-project`；目标已存在但内容不完全相同时停止，不覆盖或合并。
- `yunxiao` MCP 必须只配置中心版托管 endpoint、OAuth、上述工具 allowlist 和宿主写审批。`update_work_item` 与 `create_work_item_comment` 必须逐项设为宿主 `prompt`；skill 的“确认”“立即执行”等业务措辞不能改变这项策略。
- OAuth 登录由宿主完成。不得把 PAT、token、Authorization header 或其他凭证写入 skill、profile、项目、日志或用户输出。
- 默认安装验收只调用基础身份/组织工具，并用 `search_projects` 或用户明确给出的单个 Work Item 做一次读取。不得在该验收中调用 `update_work_item` 或 `create_work_item_comment`。
- MCP 未配置或不可连接时要求重新运行安全安装并核对 endpoint；OAuth 未完成时要求运行宿主的 Yunxiao MCP OAuth 登录；工具缺失时点名缺少项并检查 `project-management` toolset/allowlist；权限不足时说明需要的组织、项目或 Work Item 只读权限。所有情况都停止，不改用 CLI、curl、直接 OpenAPI 或浏览器自动化访问云效。
- 真实 Status 更新或评论创建不属于默认安装验收。只有用户另行提供单个安全 Work Item，并对本次具体写操作明确授权后，才按下方受控写流程执行；不得把该授权扩展到其他 Work Item 或另一类写入。

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

## 选择操作

- 用户请求修改 Status 时，读取并严格执行 [Status 流转](references/status-transition.md)。该分支自行读取当前 Work Item；不要先走下方详情读取流程。
- 用户请求创建评论时，执行下方“创建顶层评论”流程；不要先走详情读取流程。
- 其他受支持请求走下方只读流程。

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
5. 创建返回成功后，立即对同一 Work Item 再调用一次 `list_work_item_comments`。以创建响应中的评论 ID、作者身份和逐字内容确认该 ID 出现在回读结果中，且不属于写前快照。回读确认后按“完成门禁”的评论成功契约输出；确认前不宣称成功。
6. 如果创建调用可能已到达服务端但传输结果不明确，仍按第 5 步回读，不再次调用创建工具。缺少可信的创建响应时，即使写后出现不在快照中的同文评论 ID 和作者，也不能排除并发评论，不能满足“创建响应身份 + 回读”的成功证据；以 **结果不确定** 报告原始传输信息、写前/写后差异（包括任何新增匹配 ID）、已检查的 Work Item 和完整评论内容，明确说明不会自动重试，然后停止。只有既有同文评论时同样报告不确定。不要把这类写入结果归类为普通 MCP 连接失败，也不要建议直接重新提交。

## 区分错误

失败时保留云效返回的有用业务信息，必须以以下加粗分类名称作为标题，并明确指出下一步：

- **MCP 未配置或不可连接**：服务器未声明、初始化失败、工具发现请求本身失败，或运行时完全没有 `yunxiao` MCP 命名空间时使用。其他 MCP、内置工具或多代理工具的存在不能证明云效 MCP 已连接。指出需要安装或启用声明的 `yunxiao` 托管 MCP，并核对中心版 endpoint；停止。
- **未认证或认证过期**：要求通过宿主重新完成云效 OAuth 授权；不建议 PAT。
- **缺少能力**：至少一个属于 `yunxiao` MCP 命名空间的基础工具已暴露，证明云效 MCP 已连接，但本次路径缺少所需能力时使用；不得把其他命名空间的工具当作连接证据。点名缺少的工具，要求检查 `project-management` toolset 或服务端能力；停止。
- **配置不足**：点名缺少或无法唯一确定的 organization ID 或 project ID，并只请求该非敏感值。
- **目标不唯一**：Work Item Number 搜索出现多个 `serialNumber` 精确匹配时，报告匹配数量并要求用户核对项目或提供 Work Item ID；不得选择目标。
- **写入未获批准**：宿主取消或拒绝 `update_work_item` 或 `create_work_item_comment` 时使用。明确说明 Codex MCP 写工具审批未获批准、服务端调用没有执行；停止且不回读、不重试。
- **无权限**：返回云效的权限错误。读取路径要求只读权限；评论路径要求评论创建权限；Status 流转路径使用其 reference 中的更新权限指引。
- **业务规则拒绝**：评论工具已执行且云效以业务校验、必填字段或项目规则明确拒绝时使用。保留错误码与消息，指出需要修改的评论内容或业务条件；Status 流转路径使用其 reference 中更具体的业务错误分类。停止且不自动重试。
- **目标不存在或输入无效**：解析或读取目标时指出该 Work Item ID 未找到或不被接受，不搜索相似目标。已确认目标后的评论正文校验失败属于“业务规则拒绝”，不归入本类。

只读路径不得触发副作用。Status 流转路径最多提交一次 Status 更新；评论路径最多创建一条顶层评论；任何路径都不得执行另一类写入或修改其他字段。
