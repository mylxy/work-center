# 代码管理

Codeup 使用 `codeup-*` 命令；用户入口仍为 `$codeup <需求>`。代码管理中的代码库不是 Projex 项目，其 ID 不可互换。普通本地 Git 提交、分支和差异检查用 Git；云端仓库、合并请求和策略操作用 CLI。

## 定位与查询

先根据用户给出的仓库 URL、路径或 ID 定位唯一代码库：

- `codeup-list-repositories --search <路径关键词> --page 1 --per-page 100`：查询列表并核对完整路径，继续分页至完成；不要把模糊匹配的第一条当唯一结果。
- `codeup-get-repository --repository-id <ID或URL编码全路径>`：核对详情。
- `codeup-list-change-requests --project-ids <代码库ID> --state opened --page 1 --per-page 20`：查询开放合并请求。此命令使用复数 `--project-ids`，不是 `--repository-id`。
- `codeup-get-change-request --repository-id <代码库ID> --local-id <库内编号>`：读取单个合并请求。`local-id` 是代码库内的合并请求编号，不能替换为全局 ID。

代码组、成员、分支、标签、提交、文件、比较、评论、CI 检查、保护规则、Webhook、检测与评审等操作，从当前 `codeup-*` 帮助按关键词发现。优先当前 `change-request` 系列；标为“旧”的 `merge-request` 接口仅在确有需要时使用。文件路径、分支 ref、内容编码及提交消息依各自帮助，不套用其他操作的参数。

## 写操作

创建合并请求前确定源/目标代码库和分支。`codeup-create-change-request` 必需 `--repository-id`、`--source-project-id`、`--source-branch`、`--target-project-id`、`--target-branch`、`--title`；跨库时不能把两端库 ID 当成同一个。创建后回读核对并返回实际链接；不要仅为了写技能而提交演示合并请求。

合并需要用户对目标合并请求的合并授权；创建、查看或评审不自动授权合并。回读目标分支、最新源提交、CI 与可合并状态，并遵守仓库规则。`codeup-merge-change-request` 的 `--merge-type` 必填，取值以帮助为准；按用户/仓库约定选择，未确定时先澄清。删除源分支是独立选项，不擅自开启。结果不明时先回读，不重复合并。

远程文件更新/多文件提交会直接生成提交，应核对目标分支和改动范围。删除、归档、转移仓库及修改权限/保护规则按用户指定目标执行；API 权限错误不通过改用本地 push 绕过。

## 权限与验证

PAT 的项目协作、流水线权限不包含代码管理。403 时说明具体接口所需的代码管理权限；无法读取不表示代码库或合并请求不存在。写后查询对应对象或目标 ref 验证；合并请求返回已合并才能报告合并完成。

来源：当前 `aliyun devops codeup-* --help` 与[云效新版 OpenAPI](https://help.aliyun.com/zh/yunxiao/developer-reference/api-reference-standard-proprietary/)。
