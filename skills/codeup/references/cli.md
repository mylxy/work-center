# CLI 接入与命令发现

基线为 `aliyun-cli-devops 0.9.1`，实际版本与帮助优先。初次确认 `aliyun devops version` 和 `aliyun devops --help`；插件缺失且已有安装授权时运行 `aliyun plugin install --names aliyun-cli-devops`。

## 身份与目标

新版使用云效 PAT，与 `aliyun configure` 的 AK/SK profile、MCP OAuth 不互通。通过执行进程继承的环境变量接入：

| 环境变量 | 中心版 | Region 版 |
| --- | --- | --- |
| `ALIBABA_CLOUD_YUNXIAO_ACCESS_TOKEN` | 必需 | 必需 |
| `ALIBABA_CLOUD_YUNXIAO_ORGANIZATION_ID` | 必需 | 不需要 |
| `ALIBABA_CLOUD_YUNXIAO_API_BASE_URL` | 默认官方接入点 | 必需，实例 API 接入地址 |

只检查是否设置：

```bash
python3 - <<'PY'
import os
for suffix in ('ACCESS_TOKEN', 'ORGANIZATION_ID', 'API_BASE_URL'):
    key = 'ALIBABA_CLOUD_YUNXIAO_' + suffix
    print(key + ': ' + ('set' if os.environ.get(key) else 'missing'))
PY
```

两种目标配置同时存在时先明确接入点。缺配置时完成离线帮助与命令准备，说明应在本地配置的变量，不索要聊天中的令牌。权限不足时保留错误码和无秘密的错误信息；`Current token has no permission to api` 表示该接口的 PAT 权限不足，不是 CLI 未安装，也不意味着目标不存在。用户更新权限后重新调用原操作。

CLI 安装、模块能力、PAT 接口权限、账号资源权限分别核实；权限勾选数量不能证明每个接口都可访问。配置正确只代表可以尝试 API，不代表所有模块均已验证。

## 发现真实能力

以下命令列出四模块入口；实际操作时按目标缩小到一个前缀，只加载相关帮助：

```bash
aliyun devops --help | rg '^  (projex|codeup|flow|packages)-'
```

搜索具体操作后执行 `aliyun devops <实际命令> --help`。业务指引和已有 Flow 索引辅助检索，不复制全插件参数手册。名字相似的操作可能使用不同的 ID、枚举和分页上限；`--biz-body`、`--conditions` 等 JSON 按对应新版 API 文档构造。

文档选择 `/oapi/v1/` 和 `x-yunxiao-token` 的新版 API；不要混用 `api-devops-2021-06-25-*`。多行正文和 JSON 用参数数组传入 CLI，不拼成可执行 shell 文本。`--cli-dry-run` 可能打印凭证，仅在清除真实凭证的离线环境中配合虚构数据使用。

先检查响应形状再使用 `--cli-query`。分页需保留原始页大小；过滤后的结果条数不能用来判断结束。整页继续请求下一页，重复页、失败或异常结构报告部分结果；仅在确认接口支持后使用 `--all-pages`。

来源：[官方 CLI 指南](https://help.aliyun.com/zh/yunxiao/developer-reference/how-to-install-initialize-and-use-the-apsara-devops-cli)、[新版 OpenAPI](https://help.aliyun.com/zh/yunxiao/developer-reference/api-reference-standard-proprietary/)。
