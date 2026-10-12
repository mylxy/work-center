# work-center

个人工作中心。目前包含显式调用的个人 skill `YunXiaoProject`，用于通过阿里云官方托管 MCP 读取单个 Work Item、流转 Status 或创建顶层评论。

## 安装 Codeup Flow

`codeup` skill 通过官方 `aliyun-cli-devops` 插件操作 Flow。入口为 `$codeup flow <需求>`，`flow` 是技能中的子流程关键词。技能覆盖当前插件全部 Flow 命令，直接调用 CLI，不维护 API 包装层。

```bash
aliyun plugin install --names aliyun-cli-devops
aliyun devops version
python3 skills/codeup/scripts/flow_catalog.py --check skills/codeup/references/flow-commands.md
python3 -m unittest discover -s tests -p 'test_codeup_skill.py' -v
python3 scripts/install_codeup_skill.py
```

安装器将技能复制到 `$HOME/.agents/skills/codeup`，相同内容重复安装无变化，遇到已有不同内容或符号链接会停止，保留用户文件。副本不依赖开发 worktree。升级时先审阅差异并备份已有安装，再移走旧目录重新运行安装器。

```text
$codeup flow 查询分组 111 下的所有流水线
$codeup flow 查看流水线 123 最近一次运行的失败任务日志
$codeup flow 按 ./pipeline.yaml 准备更新流水线 123，先展示变更
```

PAT 和组织配置只在本地环境中提供，详见 [Flow 操作指引](skills/codeup/references/flow.md)。缺凭证不影响本地帮助和命令草稿；不代表真实 API 已连通。默认验收仅检查版本、帮助、目录完整性和本地测试，不创建、删除或运行云端流水线。

插件升级后运行下列命令重新生成 [完整命令索引](skills/codeup/references/flow-commands.md)，审阅参数和能力变化，再更新安装副本：

```bash
python3 skills/codeup/scripts/flow_catalog.py --output skills/codeup/references/flow-commands.md
```

Codex 支持 `$skill-name` 显式调用和用户级技能目录；文件变化通常自动发现，若选择器未更新则重启 Codex。依据：[官方技能说明](https://developers.openai.com/codex/skills)。

## 安装 YunXiaoProject

安装器会先校验完整 skill 包，再复制到 `$HOME/.agents/skills/yunxiao-project`。它只接受官方中心版 `project-management` endpoint；已有个人 skill 内容不同、已有 `yunxiao` MCP 指向其他来源、使用静态凭证或安全策略冲突时会停止，不覆盖原配置。

```bash
python3 tests/validate_yunxiao_skill.py
python3 scripts/install_yunxiao_skill.py
```

MCP 客户端 allowlist 仅开放身份/组织发现、项目查找、Work Item 搜索与读取、工作流读取、评论读取与创建、活动读取和 Work Item 更新。两个写工具分别使用宿主 `prompt` 审批；skill 内的业务确认或“立即执行”不能绕过审批。

安装后由 Codex 发起 OAuth 授权，不使用 PAT：

```bash
codex mcp login yunxiao
```

这与 [OpenAI 的 MCP 配置说明](https://developers.openai.com/codex/mcp) 和 [云效官方 MCP OAuth / toolset 说明](https://help.aliyun.com/zh/yunxiao/developer-reference/cloud-effect-mcp-tool-instructions) 一致。

## 只读真实连接验收

默认验收读取当前 OAuth 身份与组织，并查找一个有权访问的项目。也可以传入一个明确的项目线索或 Work Item；任何写工具调用都会令验收失败，原始错误和疑似凭证内容不会回显。

```bash
python3 scripts/validate_yunxiao_install.py
python3 scripts/validate_yunxiao_install.py --project '<项目线索>'
python3 scripts/validate_yunxiao_install.py --work-item '<Work Item ID/Number/URL>'
```

## 自动化验收

快速测试与语法检查：

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
PYTHONPYCACHEPREFIX=/tmp/work-center-pycache python3 -m compileall -q scripts tests
```

受控 MCP 行为评估器覆盖 ID、Number、URL 查看、Status 流转、评论创建、宿主写审批和写后回读。它只连接临时受控 MCP，不会接触生产 Work Item：

```bash
python3 tests/run_yunxiao_behavior_eval.py --scenario success
python3 tests/run_yunxiao_behavior_eval.py --scenario number-compact
python3 tests/run_yunxiao_behavior_eval.py --scenario url-compact
python3 tests/run_yunxiao_behavior_eval.py --scenario status-direct-success
python3 tests/run_yunxiao_behavior_eval.py --scenario exact-comment
```

真实 Status 更新或评论创建不属于默认验收。只有另行指定单个安全 Work Item，并对该次具体写入明确授权后，才可执行真实写测试。
