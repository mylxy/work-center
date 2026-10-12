# Flow 操作指引

## 配置与离线验证

基线：aliyun 3.4.11，aliyun-cli-devops 0.9.1（d34ed63bbd），帮助中的 API 版本 2026-05-25。实际安装版本优先。

新版云效使用 PAT，与 `aliyun configure` 的 AK/SK profile、YunXiaoProject MCP OAuth 不互通。按[官方 CLI 配置](https://help.aliyun.com/zh/yunxiao/developer-reference/how-to-install-initialize-and-use-the-apsara-devops-cli)在本机安全配置，让 Codex 执行命令的进程继承环境变量：

| 配置 | 中心版 | Region 版 |
| --- | --- | --- |
| `ALIBABA_CLOUD_YUNXIAO_ACCESS_TOKEN` | 必需 | 必需 |
| `ALIBABA_CLOUD_YUNXIAO_ORGANIZATION_ID` | 必需 | 不需要 |
| `ALIBABA_CLOUD_YUNXIAO_API_BASE_URL` | 默认官方中心接入点，不需要自定义 | 必需，取组织实际接入地址 |

两种目标配置同时存在时明确目标，避免调用错误组织/接入点。不要把 PAT 放入命令参数、仓库或 skill。只检查是否设置：

```bash
python3 - <<'PY'
import os
for name in ('ACCESS_TOKEN', 'ORGANIZATION_ID', 'API_BASE_URL'):
    key = 'ALIBABA_CLOUD_YUNXIAO_' + name
    print(key + ': ' + ('set' if os.environ.get(key) else 'missing'))
PY
```

`version`、`--help` 和 `scripts/flow_catalog.py` 无需凭证，不访问云端资源。插件帮助正常不证明认证有效；配置完整后可用一页 `flow-list-pipeline-groups` 做只读验证。安装验收不创建、删除或运行流水线。`--cli-dry-run` 会打印请求细节；本地验证只使用虚构凭证和虚构数据，不输出真实 token、证书或变量。

## 命令发现与参数依据

运行 `aliyun devops --help`，用 `rg '^  flow-'` 筛出当前完整命令。按 [flow-commands.md](flow-commands.md) 找候选，再读 `aliyun devops <实际命令> --help`。未列出的能力先检查当前版本，不虚构操作或承诺 Region 支持中心版专用 API。

CLI 帮助决定参数拼写/类型/必填项；涉及 JSON 内部结构、枚举、权限、分页及返回结构时，查[新版 OpenAPI](https://help.aliyun.com/zh/yunxiao/developer-reference/api-reference-standard-proprietary/)中的对应操作。选择 `/oapi/v1/flow`、`x-yunxiao-token` 的文档，避免混用旧的 `api-devops-2021-06-25-*` AK/SK 接口。帮助与文档不一致时说明差异并核实，不能猜字段。

## 查询与分页

以下为配置好环境后的命令形状，ID 是示例；调用前替换为用户指定或实际查询出的对象。

```bash
aliyun devops flow-list-pipeline-groups --page 1 --per-page 30
aliyun devops flow-list-pipeline-group-pipelines --group-id 111 --page 1 --per-page 30
aliyun devops flow-list-pipelines --pipeline-name '目标名称' --page 1 --per-page 30
aliyun devops flow-get-pipeline --pipeline-id 123
aliyun devops flow-list-pipeline-runs --pipeline-id 123 --page 1 --per-page 30
aliyun devops flow-get-pipeline-run --pipeline-id 123 --pipeline-run-id 1
```

[ListPipelineGroups](https://help.aliyun.com/zh/yunxiao/developer-reference/listpipelinegroups) 和 [ListPipelineGroupPipelines](https://help.aliyun.com/zh/yunxiao/developer-reference/listpipelinegrouppipelines)：`page` 默认 1，`perPage` 默认 10、最大 30；后者 `groupId` 必填。按分组名查询时，先完整列出分组并确定唯一 ID。

这两个 OpenAPI 的响应体是顶层数组：分组元素包含 `id`/`name`，分组下流水线元素包含 `pipelineId`/`pipelineName`/`gmtCreate`。这是官方 API 结构，实际 CLI 是否额外包装须检查首个响应；不预设 `result[]` 或 `data[]`。

“所有”需要保持筛选条件逐页递增 `--page`，依据响应分页头（若 CLI 暴露）或数组长度小于请求页大小结束；整页时继续请求下一页，包括最后一个空页。检查实际返回结构后再做 JMESPath 过滤，保留用于判断完整性的原始页大小。页失败、返回结构异常或重复页时停止并报告部分结果。全局 `--pager` 是否支持该 API 须另行确认，不凭全局帮助承诺自动分页。其他资源可能使用不同分页参数，如构建用量采用 `--page-start`/`--page-size`。

## 创建、更新与运行

| 意图 | 实际命令及要点 |
| --- | --- |
| 创建定义 | `flow-create-pipeline --name <名称> --content <YAML文本>` |
| 更新定义 | `flow-update-pipeline --pipeline-id <ID> --name <名称> --content <YAML文本>` |
| 更新名称/环境/标签 | `flow-update-pipeline-base-info`，参数名与更新定义不同，读 help |
| 删除定义 | `flow-delete-pipeline --pipeline-id <ID>` |
| 运行 | `flow-create-pipeline-run --pipeline-id <ID> [--params <JSON字符串>]` |
| 最新运行/指定运行/历史列表 | `flow-get-latest-pipeline-run` / `flow-get-pipeline-run` / `flow-list-pipeline-runs` |
| 终止运行 | `flow-update-pipeline-run --pipeline-id <ID> --pipeline-run-id <运行ID>`，没有 `--status` 参数 |

[UpdatePipeline](https://help.aliyun.com/zh/yunxiao/developer-reference/updatepipeline-update-pipeline) 需要名称和 YAML 内容，不能把文件路径当内容。先回读当前定义，比较完整 YAML，再提交用户指定修改。多行内容用 `subprocess.run` 参数数组和 `Path(...).read_text()` 直接传入，避免插值进 shell；不假设 `@file` 语法受支持。

[CreatePipelineRun](https://help.aliyun.com/zh/yunxiao/developer-reference/createpipelinerun) 的 `--params` 是 JSON 字符串；字段如 `envs`、`runningBranchs`、`runningTags` 以文档和实际源配置为准，分支映射使用仓库地址作为 key。返回运行 ID 后回读状态。[UpdatePipelineRun](https://help.aliyun.com/zh/yunxiao/developer-reference/updatepipelinerun) 的含义是终止，不能当成任意运行属性更新。

## 任务、人工卡点、日志与产物

先从运行详情定位 `jobId`，从 `flow-get-pipeline-job-steps` 定位 `buildId` 和 `stepIndex`；不要用 YAML job 标识代替运行任务 ID。

| 意图 | 实际命令 |
| --- | --- |
| 手动运行/重试/重新运行任务 | `flow-execute-pipeline-job-run` / `flow-retry-pipeline-job-run` / `flow-rerun-pipeline-job-run` |
| 跳过/终止任务 | `flow-skip-pipeline-job-run` / `flow-stop-pipeline-job-run` |
| 后续 action | `flow-execute-pipeline-job-action`，额外需要 `--action-id` |
| 通过/拒绝人工卡点 | `flow-pass-pipeline-validate` / `flow-refuse-pipeline-validate` |
| 任务日志/步骤 | `flow-get-pipeline-job-run-log` / `flow-get-pipeline-job-steps` |
| 步骤日志/下载地址 | `flow-get-pipeline-job-step-log` / `flow-get-pipeline-job-step-log-url` |
| 调试连接 | `flow-get-pipeline-debug-websocket-url` |
| 产物/EMAS产物/扫描报告 | `flow-get-pipeline-artifact-url` / `flow-get-pipeline-emas-artifact-url` / `flow-get-pipeline-scan-report-url` |

任务控制和人工卡点命令均需要 `--pipeline-id`、`--pipeline-run-id`、`--job-id`。用实际状态和可用 action 区分重试、重新运行、手动运行；[RetryPipelineJobRun](https://help.aliyun.com/zh/yunxiao/developer-reference/retrypipelinejobrun) 与 [PassPipelineValidate](https://help.aliyun.com/zh/yunxiao/developer-reference/passpipelinevalidate) 的作用不同，不能把通过卡点当查询。

步骤日志还需要 `--build-id`、`--step-index`、`--offset`、`--limit`；分段读取只按服务端实际响应推进。获取 WebSocket URL 不等于授权执行交互式调试命令。

[GetPipelineArtifactUrl](https://help.aliyun.com/zh/yunxiao/developer-reference/getpipelineartifacturl) 需要 `--file-path` 和 `--file-name`，只支持中心版，地址有效期一小时。先在运行详情/产物 action 中获取实际文件信息；EMAS 和扫描报告各读自身帮助，不能照搬普通产物参数。取得地址不表示已下载；下载必须使用用户允许的目标目录，不自动执行下载产物。

[GetPipelineRun](https://help.aliyun.com/zh/yunxiao/developer-reference/getpipelinerun) 的任务位于 `stages[].stageInfo.jobs[]`，运行任务 ID 是任务的 `id`；在该任务的 `actions[]` 中选择对应产物类型。按 [Action 说明](https://help.aliyun.com/zh/yunxiao/developer-reference/getpipelinerun-action-description-1)，`type=GetPipelineArtifactUrl` 的 `params.files[]` 提供 `filePath` 和 `fileName`。只使用实际返回且允许调用的 action；多个文件按用户要求选择，未返回 action 时明确说明，不构造文件路径。

## 相关资源

在命令索引中按关键词检索：`pipeline-group`（分组及加入分组）、`flow-tag`、`variable-group` 与 `pipeline-relations`、`resource-member`/`resource-owner`、`service-auth`/`service-connection`/`service-credential`/`ssh-key`、`host-group`/`machine-group`、`build-group`/`build-usage`、`vpc`/`vswitch`/`security-group`、`kubernetes`、`vm-deploy`。完整索引包含这些资源的全部已暴露操作与必填/可选参数。

成员/拥有者、主机、部署单、集群和服务凭证分别使用各自 ID；读帮助确认关联字段与角色枚举。变量组更新须保留非目标变量并检查加密标记；资源或授权更新前明确影响范围，按现有授权执行。证书/变量/kubeconfig 的值只在本地安全输入与目标服务之间传递，不写入技能或回显。若 CLI 仅提供会暴露秘密的参数方式且无法安全执行，说明该限制并保留命令结构供本地操作。
