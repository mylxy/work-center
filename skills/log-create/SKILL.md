---
name: log-create
description: Create and symlink a project-local SLS log-query skill from the LogIotHubV3 template using a requested skill name, project, and logstore.
disable-model-invocation: true
---

# LogCreate

在 `/Users/seven/work/work-center` 中，根据现有 LogIotHubV3 模板创建新的 SLS 日志查询技能，并通过软链接安装到 Codex。

所有用户可见的进度、问题、错误和完成说明都使用中文。

## 解析输入

接受形如 `/LogCreate 创建 LogExample project=example-project logstore=example-logstore` 的请求，并取得以下三个必填值：

- 技能展示名，例如 `LogExample`。
- `project`。
- `logstore`。

缺少任一值时，指出缺少的字段并等待用户补充。保留 `project` 和 `logstore` 的原始值，不猜测或改写。

将技能展示名转换为符合技能规范的小写连字符目录名，例如 `LogIotHubV4` 转为 `log-iot-hub-v4`。展示名本身保持用户输入的大小写。若无法得到只含小写字母、数字和连字符的非空名称，要求用户提供有效名称。

## 创建技能

固定使用以下位置：

- 模板：`/Users/seven/work/work-center/skills/log-iot-hub-v3`
- 输出：`/Users/seven/work/work-center/skills/{skill-slug}`
- 安装链接：`/Users/seven/.codex/skills/{skill-slug}`

开始前完整读取模板中的 `SKILL.md` 和 `agents/openai.yaml`，以当前文件内容为准。模板目录必须存在且可读。目标技能目录已存在时停止创建并说明冲突；只有用户明确要求更新或覆盖时才进入相应操作。

复制模板结构和内容后，只修改下列配置点：

| 文件 | 配置点 | 新值 |
|---|---|---|
| `SKILL.md` | frontmatter `name` | `{skill-slug}` |
| `SKILL.md` | frontmatter `description` 中的模板产品名 | 用户提供的展示名 |
| `SKILL.md` | 一级标题 | `# {display-name}` |
| `SKILL.md` | 固定 Project | 用户提供的 `project` |
| `SKILL.md` | 固定 Logstore | 用户提供的 `logstore` |
| `agents/openai.yaml` | `interface.display_name` | `{display-name}` |
| `agents/openai.yaml` | `interface.short_description` 中的模板产品名 | 用户提供的展示名 |
| `agents/openai.yaml` | `interface.default_prompt` 中的调用标识 | `${skill-slug}` |

保留模板中的查询参数、可选 traceId、时间范围、默认级别、条数限制、SQL、`get-logs-v2` 命令、只返回单个 JSON 代码块的规则、JSON 字段顺序、中文输出规则以及其他行为。采用字段级或精确文本修改；不得对 `v2`、`v3`、`project`、`logstore` 等短字符串执行全局替换，避免改坏 API 名称或说明文本。不得修改源模板。

新技能保持显式调用策略：`agents/openai.yaml` 中设置 `policy.allow_implicit_invocation: false`，默认提示必须使用 `$skill-slug` 格式引用新技能。

## 校验与安装

创建完成后检查：

1. frontmatter 和 `agents/openai.yaml` 均可被 YAML 解析，技能目录名与 frontmatter `name` 一致。
2. 目标说明中的 `project` 和 `logstore` 与用户输入一致。
3. 模板查询逻辑和 JSON 示例仍然有效，`get-logs-v2` 等固定命令未被名称替换影响。
4. 除技能名称、Project、Logstore 和 UI 元数据外，目标技能与当前模板行为一致。

优先运行 `skill-creator` 提供的 `quick_validate.py`；若其依赖在本机不可用，执行等价的 YAML、命名和未完成占位符检查并明确记录结果。

校验通过后创建软链接，不复制安装：

- 安装路径不存在时，将其链接到项目中的目标技能目录。
- 已是指向同一目标的软链接时保持不变。
- 安装路径是普通文件、普通目录或指向其他位置的软链接时停止，不覆盖，并向用户说明冲突。

若写入 `/Users/seven/.codex/skills` 需要授权，在真正创建链接前请求授权。只有技能文件校验通过且软链接正确指向目标目录时才算完成。

## 返回

用中文简洁返回：技能展示名、调用标识、项目内绝对路径、固定 Project、固定 Logstore、校验结果和软链接状态。不要执行新建技能的日志查询。
