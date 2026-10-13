# Flow CLI 命令索引（自动生成）

来源：`aliyun-cli-devops 0.9.1 (d34ed63bbd)` 的 `--help`；共 86 个 Flow 命令。

每条命令前加 `aliyun devops`。星号标记必填业务参数；类型、枚举、JSON 结构及全局参数以该命令当前 `--help` 和官方 OpenAPI 文档为准。
此表用于完整能力发现，不是静态 allowlist；插件新增命令后可直接按实际帮助使用。

更新：`python3 skills/codeup/scripts/flow_catalog.py --output skills/codeup/references/flow-commands.md`。
检查漂移：`python3 skills/codeup/scripts/flow_catalog.py --check skills/codeup/references/flow-commands.md`。

| 命令 | 能力与适用版本 | 业务参数（* 必填） |
| --- | --- | --- |
| `flow-add-pipeline-relations` | 添加流水线关联（可用版本：中心版、Region版） | `--pipeline-id`*, `--rel-object-ids`*, `--rel-object-type`* |
| `flow-add-to-pipeline-group` | 将流水线加入流水线分组（可用版本：中心版、Region版） | `--group-id`*, `--pipeline-ids`* |
| `flow-create-build-group` | 创建托管VPC构建集群（可用版本：中心版、Region版） | `--machine-group-str`* |
| `flow-create-flow-tag` | 创建标签（可用版本：中心版、Region版） | `--color`*, `--flow-tag-group-id`*, `--name`* |
| `flow-create-flow-tag-group` | 创建标签分类（可用版本：中心版、Region版） | `--name`* |
| `flow-create-host-group` | 创建主机组（可用版本：中心版、Region版） | `--name`*, `--service-connection-id`*, `--type`*, `--aliyun-region`, `--ecs-label-key`, `--ecs-label-value`, `--ecs-type`, `--env-id`, `--machine-infos`, `--tag-ids` |
| `flow-create-pipeline` | 创建流水线（可用版本：中心版、Region版） | `--content`*, `--name`* |
| `flow-create-pipeline-group` | 创建流水线分组（可用版本：中心版、Region版） | `--name`* |
| `flow-create-pipeline-run` | 运行流水线（可用版本：中心版、Region版） | `--pipeline-id`*, `--params` |
| `flow-create-resource-member` | 插入资源成员（可用版本：中心版、Region版） | `--resource-id`*, `--resource-type`*, `--role-name`*, `--user-id`* |
| `flow-create-service-auth` | 创建服务授权（可用版本：中心版） | `--service-auth-type`* |
| `flow-create-service-connection` | 创建服务连接（可用版本：中心版、Region版） | `--auth-id`, `--auth-type`, `--connection-name`, `--connection-type`, `--scope` |
| `flow-create-service-credential` | 创建服务证书（可用版本：中心版、Region版） | `--name`*, `--password`*, `--type`*, `--username`*, `--scope` |
| `flow-create-ssh-key` | 创建企业公钥（可用版本：中心版） | — |
| `flow-create-variable-group` | 创建变量组（可用版本：中心版、Region版） | `--name`*, `--variables`*, `--description` |
| `flow-delete-flow-tag` | 删除标签（可用版本：中心版、Region版） | `--id`* |
| `flow-delete-flow-tag-group` | 删除标签分类（可用版本：中心版、Region版） | `--id`* |
| `flow-delete-host-group` | 删除主机组（可用版本：中心版、Region版） | `--id`* |
| `flow-delete-machine-group-machines` | 删除主机组的机器（可用版本：中心版、Region版） | `--id`*, `--machine-sns`* |
| `flow-delete-pipeline` | 删除流水线（可用版本：中心版、Region版） | `--pipeline-id`* |
| `flow-delete-pipeline-group` | 删除流水线分组（可用版本：中心版、Region版） | `--group-id`* |
| `flow-delete-pipeline-relations` | 删除流水线关联（可用版本：中心版、Region版） | `--pipeline-id`*, `--rel-object-id`*, `--rel-object-type`* |
| `flow-delete-resource-member` | 删除资源成员（可用版本：中心版、Region版） | `--resource-id`*, `--resource-type`*, `--user-id`* |
| `flow-delete-variable-group` | 删除变量组（可用版本：中心版、Region版） | `--id`* |
| `flow-execute-pipeline-job-action` | 运行流水线任务后续action（可用版本：中心版、Region版） | `--action-id`*, `--job-id`*, `--pipeline-id`*, `--pipeline-run-id`* |
| `flow-execute-pipeline-job-run` | 手动运行流水线任务（可用版本：中心版、Region版） | `--job-id`*, `--pipeline-id`*, `--pipeline-run-id`* |
| `flow-get-build-resource-network-status` | 检查VPC构建资源与网络（可用版本：中心版、Region版） | `--aliyun-region-id`*, `--biz-endpoint-type`*, `--service-connection-id`*, `--vpc-id`*, `--vswitch-ids`*, `--zone-ids`* |
| `flow-get-flow-tag-group` | 获取标签分类（可用版本：中心版、Region版） | `--id`* |
| `flow-get-host-group` | 获取主机组（可用版本：中心版、Region版） | `--id`* |
| `flow-get-latest-pipeline-run` | 获取最近一次流水线运行信息（可用版本：中心版、Region版） | `--pipeline-id`* |
| `flow-get-pipeline` | 获取流水线详情（可用版本：中心版、Region版） | `--pipeline-id`* |
| `flow-get-pipeline-artifact-url` | 获取流水线构建产物下载地址（可用版本：中心版） | `--file-name`*, `--file-path`* |
| `flow-get-pipeline-debug-websocket-url` | 获取流水线任务调试地址（可用版本：中心版、Region版） | `--build-id`*, `--job-id`*, `--pipeline-id`*, `--pipeline-run-id`* |
| `flow-get-pipeline-emas-artifact-url` | 获取流水线emas构建产物临时下载地址（可用版本：中心版） | `--emas-job-instance-id`*, `--md5`*, `--pipeline-id`*, `--pipeline-run-id`*, `--service-connection-id`* |
| `flow-get-pipeline-group` | 获取流水线分组（可用版本：中心版、Region版） | `--group-id`* |
| `flow-get-pipeline-job-run-log` | 查询任务运行日志（可用版本：中心版、Region版） | `--job-id`*, `--pipeline-id`*, `--pipeline-run-id`* |
| `flow-get-pipeline-job-step-log` | 获取流水线任务步骤日志（可用版本：中心版、Region版） | `--build-id`*, `--job-id`*, `--limit`*, `--offset`*, `--pipeline-id`*, `--pipeline-run-id`*, `--step-index`* |
| `flow-get-pipeline-job-step-log-url` | 获取流水线任务步骤日志下载地址（可用版本：中心版、Region版） | `--build-id`*, `--job-id`*, `--pipeline-id`*, `--pipeline-run-id`*, `--step-index`* |
| `flow-get-pipeline-job-steps` | 获取流水线任务步骤列表（可用版本：中心版、Region版） | `--job-id`*, `--pipeline-id`*, `--pipeline-run-id`* |
| `flow-get-pipeline-run` | 获取流水线运行实例（可用版本：中心版、Region版） | `--pipeline-id`*, `--pipeline-run-id`* |
| `flow-get-pipeline-scan-report-url` | 获取扫描报告下载链接（可用版本：中心版、Region版） | `--report-path`* |
| `flow-get-variable-group` | 获取变量组（可用版本：中心版、Region版） | `--id`* |
| `flow-get-vm-deploy-machine-log` | 查询机器部署日志（可用版本：中心版、Region版） | `--deploy-order-id`*, `--machine-sn`*, `--pipeline-id`* |
| `flow-get-vm-deploy-order` | 获取部署单详情（可用版本：中心版、Region版） | `--deploy-order-id`*, `--pipeline-id`* |
| `flow-list-build-usage-details` | 分页查询组织构建用量明细（可用版本：中心版、Region版） | `--from-date`*, `--to-date`*, `--page-size`, `--page-start` |
| `flow-list-flow-tag-groups` | 获取标签分类列表（可用版本：中心版、Region版） | — |
| `flow-list-host-groups` | 获取主机组列表（可用版本：中心版、Region版） | `--create-end-time`, `--create-start-time`, `--creator-account-ids`, `--ids`, `--name`, `--page`, `--page-order`, `--page-sort`, `--per-page` |
| `flow-list-pipeline-group-pipelines` | 获取流水线分组下流水线列表（可用版本：中心版、Region版） | `--group-id`*, `--create-end-time`, `--create-start-time`, `--execute-end-time`, `--execute-start-time`, `--page`, `--per-page`, `--pipeline-name`, `--status-list` |
| `flow-list-pipeline-groups` | 获取流水线分组列表（可用版本：中心版、Region版） | `--page`, `--per-page` |
| `flow-list-pipeline-job-historys` | 获取流水线任务的执行历史（可用版本：中心版、Region版） | `--category`*, `--identifier`*, `--pipeline-id`*, `--page`, `--per-page` |
| `flow-list-pipeline-jobs` | 按任务分类获取流水线执行的任务（可用版本：中心版、Region版） | `--category`*, `--pipeline-id`* |
| `flow-list-pipeline-relations` | 获取流水线关联列表（可用版本：中心版、Region版） | `--pipeline-id`*, `--rel-object-type`* |
| `flow-list-pipeline-runs` | 获取流水线运行实例列表（可用版本：中心版、Region版） | `--pipeline-id`*, `--end-time`, `--page`, `--per-page`, `--start-time`, `--status`, `--trigger-mode` |
| `flow-list-pipelines` | 获取流水线列表（可用版本：中心版、Region版） | `--create-end-time`, `--create-start-time`, `--execute-end-time`, `--execute-start-time`, `--page`, `--per-page`, `--pipeline-name`, `--status-list` |
| `flow-list-resource-members` | 获取资源成员列表（可用版本：中心版、Region版） | `--resource-id`*, `--resource-type`* |
| `flow-list-security-groups` | 查询安全组列表（可用版本：中心版、Region版） | `--aliyun-region-id`*, `--service-connection-id`*, `--vpc-id`*, `--security-group-name` |
| `flow-list-service-auths` | 获取服务授权列表（可用版本：中心版、Region版） | `--service-auth-type`* |
| `flow-list-service-connections` | 获取服务连接列表（可用版本：中心版、Region版） | `--service-connection-type`*, `--serice-connection-type` |
| `flow-list-service-credentials` | 获取服务证书列表（可用版本：中心版、Region版） | `--service-credential-type`* |
| `flow-list-variable-groups` | 获取变量组列表（可用版本：中心版、Region版） | `--page`, `--page-order`, `--page-sort`, `--per-page` |
| `flow-list-vpc-regions` | 查询支持的VPC地域列表（可用版本：中心版、Region版） | — |
| `flow-list-vpc-zones` | 查询可用区列表（可用版本：中心版、Region版） | `--aliyun-region-id`*, `--service-connection-id`* |
| `flow-list-vpcs` | 查询VPC列表（可用版本：中心版、Region版） | `--aliyun-region-id`*, `--service-connection-id`*, `--vpc-name` |
| `flow-list-vswitchs` | 查询交换机列表（可用版本：中心版、Region版） | `--aliyun-region-id`*, `--service-connection-id`*, `--vpc-id`*, `--zone-id`*, `--vswitch-name` |
| `flow-pass-pipeline-validate` | 通过人工卡点（可用版本：中心版、Region版） | `--job-id`*, `--pipeline-id`*, `--pipeline-run-id`* |
| `flow-refuse-pipeline-validate` | 拒绝人工卡点（可用版本：中心版、Region版） | `--job-id`*, `--pipeline-id`*, `--pipeline-run-id`* |
| `flow-rerun-pipeline-job-run` | 重新运行流水线任务（可用版本：中心版、Region版） | `--job-id`*, `--pipeline-id`*, `--pipeline-run-id`* |
| `flow-resume-vm-deploy-order` | 继续部署单运行（可用版本：中心版、Region版） | `--deploy-order-id`*, `--pipeline-id`* |
| `flow-retry-pipeline-job-run` | 重试流水线任务运行（可用版本：中心版、Region版） | `--job-id`*, `--pipeline-id`*, `--pipeline-run-id`* |
| `flow-retry-vm-deploy-machine` | 重试机器部署（可用版本：中心版、Region版） | `--deploy-order-id`*, `--machine-sn`*, `--pipeline-id`* |
| `flow-skip-pipeline-job-run` | 跳过流水线任务运行（可用版本：中心版、Region版） | `--job-id`*, `--pipeline-id`*, `--pipeline-run-id`* |
| `flow-skip-vm-deploy-machine` | 跳过机器部署（可用版本：中心版、Region版） | `--deploy-order-id`*, `--machine-sn`*, `--pipeline-id`* |
| `flow-stop-pipeline-job-run` | 终止流水线任务运行（可用版本：中心版、Region版） | `--job-id`*, `--pipeline-id`*, `--pipeline-run-id`* |
| `flow-stop-vm-deploy-order` | 终止机器部署（可用版本：中心版、Region版） | `--deploy-order-id`*, `--pipeline-id`* |
| `flow-update-flow-tag` | 更新标签（可用版本：中心版、Region版） | `--color`*, `--flow-tag-group-id`*, `--id`*, `--name`* |
| `flow-update-flow-tag-group` | 更新标签分类（可用版本：中心版、Region版） | `--id`*, `--name`* |
| `flow-update-host-group` | 更新主机组（可用版本：中心版、Region版） | `--id`*, `--name`*, `--service-connection-id`*, `--type`*, `--aliyun-region`, `--ecs-label-key`, `--ecs-label-value`, `--ecs-type`, `--env-id`, `--machine-infos`, `--tag-ids` |
| `flow-update-kubernetes-kube-config` | 更新kubernetes集群集群名称，配置文件（可用版本：中心版、Region版） | `--id`*, `--kube-config`*, `--name`* |
| `flow-update-pipeline` | 更新流水线（可用版本：中心版、Region版） | `--content`*, `--name`*, `--pipeline-id`* |
| `flow-update-pipeline-base-info` | 更新流水线基本信息（可用版本：中心版、Region版） | `--pipeline-id`*, `--pipeline-name`*, `--env-id`, `--tag-list` |
| `flow-update-pipeline-group` | 更新流水线分组（可用版本：中心版、Region版） | `--group-id`*, `--name`* |
| `flow-update-pipeline-run` | 终止流水线运行（可用版本：中心版、Region版） | `--pipeline-id`*, `--pipeline-run-id`* |
| `flow-update-resource-member` | 更新资源成员（可用版本：中心版、Region版） | `--resource-id`*, `--resource-type`*, `--role-name`*, `--user-id`* |
| `flow-update-resource-owner` | 移交资源对象拥有者（可用版本：中心版、Region版） | `--new-owner-id`*, `--resource-id`*, `--resource-type`* |
| `flow-update-ssh-key` | 重置企业公钥（可用版本：中心版） | — |
| `flow-update-variable-group` | 更新变量组（可用版本：中心版、Region版） | `--id`*, `--name`*, `--variables`*, `--description` |
