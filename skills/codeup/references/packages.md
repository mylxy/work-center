# 制品仓库

使用 `packages-*` 管理制品仓库中的软件包及版本；流水线运行生成的产物地址使用 Flow 指引。代码库 ID、流水线 ID 与制品仓库 `repo-id` 不能互换。

## 查询和操作

| 意图 | 当前插件命令与关键参数 |
| --- | --- |
| 列出仓库 | `packages-list-repositories`，可选 `--repo-types`、`--repo-categories`、`--page`、`--per-page` |
| 搜索包 | `packages-list-artifacts --repo-id <仓库ID> --repo-type <类型>`，可选 `--search`、分页与排序 |
| 包详情及版本 | `packages-get-artifact --repo-id <仓库ID> --repo-type <类型> --id <制品ID>` |
| 删除整个制品 | `packages-delete-artifact --repo-id <仓库ID> --repo-type <类型> --id <制品ID>` |
| 删除指定版本 | `packages-delete-artifact-version`，除上述 ID 外需要 `--version-id <版本ID>` |
| 查询异步任务 | `packages-get-task --id <任务ID>` |

先核对仓库名称、类型和 ID，再从实际列表取制品 ID，从详情取版本 ID。用户提供的版本字符串不是 `version-id`。每个命令读自身帮助：仓库列表和包查询允许的 `repo-type` 集合可能不同；分页上限不能套用 Flow 的 30 条。

“删除某版本”只删除指定版本；没有整个制品的授权不能升级为整包删除。删除返回任务 ID 时，用 `packages-get-task` 查询至实际终态，并回读制品/版本核实；无法取得终态就报告已提交但未验证完成。

当前 0.9.1 帮助暴露上述六个命令。后续版本先检索 `aliyun devops --help` 中的 `packages-*`；未发现创建、上传、下载命令时明确 CLI 的能力边界，再查官方对应包类型工具或 API，不构造不存在的命令。查询到元数据不等于已下载制品。

PAT 需要独立的制品仓库接口权限及资源访问权限。签名地址和仓库凭证不回显，不执行下载包中的脚本。

来源：当前 `aliyun devops packages-* --help` 与[云效新版 OpenAPI](https://help.aliyun.com/zh/yunxiao/developer-reference/api-reference-standard-proprietary/)。
