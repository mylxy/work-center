# 项目协作

## 查找和阅读工作项

`projex-*` 覆盖项目、项目集、工作项、迭代、版本、里程碑、成员、角色、工时、评论、附件和关联项。完整能力从当前帮助检索。

用户给出工作项编号时，可以先用 `projex-get-workitem --id <编号>` 只读查询；当前中心版已观察到支持编号，但官方参数定义为唯一标识，不假设所有版本都支持。成功后核对 `serialNumber`，保存返回的内部 `id`，后续写操作使用内部 ID。若接口明确不接受编号或查无此项，再按用户项目定位并搜索；403 应处理权限，不改用宽泛搜索绕过。

| 意图 | 已核实的命令 |
| --- | --- |
| 查询项目 | `projex-search-projects` / `projex-get-project` |
| 搜索缺陷 | `projex-search-workitems --space-id <项目ID> --category Bug` |
| 读取工作项 | `projex-get-workitem --id <工作项ID>` |
| 评论、动态、附件 | `projex-list-workitem-comments` / `projex-list-workitem-activities` / `projex-list-workitem-attachments` |
| 创建工作项 | `projex-create-workitem` |
| 添加评论 | `projex-create-workitem-comment --id <工作项ID> --content <正文>` |
| 更新字段 | `projex-update-workitem --id <工作项ID> --biz-body <JSON>` |
| 查询工作流状态 | `projex-get-workitem-workflow --project-id <项目ID> --id <工作项类型ID>` |

这些是检索入口；其他项目协作操作仍按当前 `projex-*` 帮助发现。工作项编号与内部 ID、`Bug` 分类与工作项类型 ID 均不同。读取缺陷时查看描述和相关评论，区分事实、讨论意见和原因推测，不把评论中的建议当成已修复。

`projex-search-workitems` 必需 `--space-id`、`--category`；`--conditions` 是 JSON 字符串，字段结构以 [SearchWorkitems](https://help.aliyun.com/zh/yunxiao/developer-reference/searchworkitems) 为准。默认每页 20，最多 200；`page * perPage` 不得超过 10000，接近上限时缩小筛选范围而不是宣称取全。项目搜索结果需核对名称和 ID；不要对模糊匹配集合直接写入。

## 创建、评论和字段变更

创建工作项前，从目标项目读取工作项类型与字段配置，解析负责人；实际必填项由 `projex-create-workitem --help` 和项目配置共同决定。不能把显示名称填入 ID 字段。正文按 `--format-type` 区分 Markdown 与富文本。

修改状态时回读当前工作项，用其 `space.id` 和 `workitemType.id` 查询工作流，完整匹配目标显示名并取对应状态 ID。提交最小请求体 `{"status":"<实际状态ID>"}`，不能直接传“已解决”或复用别的项目的状态 ID。状态在列表中不代表一定允许流转；服务端的流转限制、角色要求和必填字段仍须满足，不擅自经中间状态跳转。

用户明确要求添加评论或更新状态时，定位唯一目标后直接执行；无需固定的“先预览再确认”。只改指定字段。回读状态 ID 或新评论 ID 确认成功；写请求结果不明时先查询，不能重复创建评论。操作人按实际 PAT 身份，`operatorId` 在个人 token 场景无效。

## 缺陷创建监听

“可以监听吗”是能力咨询，不创建自动化。用户要求建立监听时明确项目、过滤条件、接收位置与实时/轮询要求。优先核实云效自动化的工作项创建事件；通过 `aliyun devops --help` 检索 `base-.*automation`，从 `base-list-automation-event-types --app projex` 获取实际事件类型，再用 `base-get-automation-event-type-fields --type <实际事件类型>` 查字段。事件任务的创建参数和渠道支持以实际帮助及官方文档为准，不猜事件名或承诺所有实例支持。

云效自动化也可在项目设置中配置群通知或 Webhook。CLI 搜索可作为定时轮询的数据源，但技能本身不持续运行；需要实际调度器、首次基线、重叠时间窗、分页与工作项 ID 去重。接收人、渠道和调度器未配置前，不声称已开始监听。无新增保持安静，查询失败不推进游标；首次查询到的历史缺陷不自动算新增。

来源：[GetWorkitem](https://help.aliyun.com/zh/yunxiao/developer-reference/getworkitem)、[UpdateWorkitem](https://help.aliyun.com/zh/yunxiao/developer-reference/updateworkitem)、[群通知](https://help.aliyun.com/zh/yunxiao/user-guide/dingtalk-group-notification-configuration-guide)、[Webhook](https://help.aliyun.com/zh/yunxiao/user-guide/webhook-configuration-guide)。
