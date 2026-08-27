---
name: yunxiao-project
description: Read one Yunxiao Work Item by its Work Item ID through the official hosted MCP.
disable-model-invocation: true
---

# YunXiaoProject

通过阿里云官方托管的云效 MCP，以当前用户的 OAuth 身份读取一个 Work Item。这个版本只支持用户明确提供的 Work Item ID，并保持全程只读。

## 执行边界

- 仅使用 `agents/openai.yaml` 声明的 `yunxiao` MCP；运行时只接受中心版托管端点及 `project-management` toolset。
- 所需项目管理能力只有 `get_work_item`。先从工具发现结果确认该能力存在；缺少时不调用任何 MCP 工具。只有能力存在且 organization ID 仍缺失时，才可使用 MCP 自带的基础身份或组织发现工具确定当前身份与 organization ID。不得调用项目搜索、Work Item 搜索、活动、评论或任何写工具。
- 以 MCP 运行时公布的工具名称和输入 schema 为准。缺少 `get_work_item` 时停止，不用相近工具猜测替代。
- 保持只读。不得更新 Status、创建评论或执行其他变更。
- MCP 是唯一后端。连接失败时按下方错误分类停止，不切换到 CLI、curl、直接 OpenAPI 或浏览器自动化。
- OAuth 凭证由宿主管理。不得索取、读取、显示或保存 PAT、OAuth token、Authorization header 或其他凭证。

## 读取配置

先读取同目录的 `profile.yaml`：

- `mcp_endpoint` 必须与声明的中心版托管端点一致。
- `organization_id` 是非敏感配置。值为空时，优先使用 MCP 的基础身份或组织发现能力；仍无法唯一确定时，只请求用户补充 organization ID，不猜测。

## 解析请求

只接受本次显式调用中用户指定的一个 Work Item ID：

1. 保留 ID 原文，不修剪内部字符、不补齐、不改写大小写。
2. 用户没有明确标注或提供 Work Item ID 时，请求补充。
3. 用户提供 URL、Work Item Number、多个候选或要求搜索时，说明当前纵切只支持一个 Work Item ID，然后停止。
4. 不通过试探多个 organization 或 Work Item 来推断目标。

## 读取 Work Item

确认 MCP、OAuth、`get_work_item`、organization ID 和一个 Work Item ID 均可用后：

1. 按运行时 schema 将 organization ID 与 Work Item ID 传给 `get_work_item`。
2. 只调用一次 `get_work_item`，且目标必须是用户给出的原始 Work Item ID。
3. 不读取其他 Work Item，也不把错误结果转换为搜索请求。

成功时返回紧凑的基础摘要，优先使用 MCP 返回的字段并包含：

- Work Item ID 与 Work Item Number（若返回）；
- 标题、项目、云效返回的原始类型；
- 当前 Status、优先级、负责人；
- 描述的简短原文摘要。

缺失字段标记为“未提供”，不推断值。不要声称读取了评论、活动或工作流。

## 区分错误

失败时保留云效返回的有用业务信息，必须以以下加粗分类名称作为标题，并明确指出下一步：

- **MCP 未配置或不可连接**：服务器未声明、初始化失败、工具发现请求本身失败，或运行时完全没有 `yunxiao` MCP 命名空间时使用。其他 MCP、内置工具或多代理工具的存在不能证明云效 MCP 已连接。指出需要安装或启用声明的 `yunxiao` 托管 MCP，并核对中心版 endpoint；停止。
- **未认证或认证过期**：要求通过宿主重新完成云效 OAuth 授权；不建议 PAT。
- **缺少能力**：至少一个属于 `yunxiao` MCP 命名空间的基础工具已暴露，证明云效 MCP 已连接，但列表中没有 `get_work_item` 时使用；不得把其他命名空间的工具当作连接证据。点名缺少 `get_work_item`，要求检查 `project-management` toolset 或服务端能力；停止。
- **配置不足**：点名缺少或无法唯一确定的 organization ID；请求该非敏感值。
- **无权限**：返回云效的权限错误，并要求为当前 OAuth 身份授予目标 Work Item 的只读权限。
- **目标不存在或输入无效**：指出该 Work Item ID 未找到或不被接受，不搜索相似目标。

任何失败都不得触发真实 Status 更新、评论写入或其他副作用。
