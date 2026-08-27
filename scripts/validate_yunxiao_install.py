#!/usr/bin/env python3
"""Validate a personal YunXiaoProject installation without making live writes."""

from __future__ import annotations

from dataclasses import dataclass
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))
from scripts.install_yunxiao_skill import (
    ALLOWED_TOOLS,
    InstallationConflict,
    _check_skill,
    _plan_mcp,
    _validate_source,
)
from tests.validate_yunxiao_skill import CREDENTIAL_PATTERNS


WRITE_TOOLS = {"create_work_item_comment", "update_work_item"}
IDENTITY_TOOLS = {
    "get_current_organization_info",
    "get_user_organizations",
    "get_current_user",
}
RESOURCE_TOOLS = {"search_projects", "get_work_item"}
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "identity": {"type": "string"},
        "organization": {"type": "string"},
        "resource_kind": {"enum": ["project", "work_item"]},
        "resource": {"type": "string"},
        "tools_used": {
            "type": "array",
            "items": {"type": "string", "enum": list(ALLOWED_TOOLS)},
        },
        "diagnostic": {"type": ["string", "null"]},
    },
    "required": [
        "identity",
        "organization",
        "resource_kind",
        "resource",
        "tools_used",
        "diagnostic",
    ],
    "additionalProperties": False,
}


class ValidationFailure(RuntimeError):
    """Raised when an installation or read-only live check is not acceptable."""


@dataclass(frozen=True)
class LiveValidationResult:
    identity: str
    organization: str
    resource_kind: str
    resource: str
    tools_used: tuple[str, ...]


def _prompt(project_hint: str | None, work_item_hint: str | None) -> str:
    target = (
        f"读取明确指定的 Work Item {work_item_hint!r}。"
        if work_item_hint
        else (
            f"只在项目线索 {project_hint!r} 内查找一个有权访问的项目。"
            if project_hint
            else "用 search_projects 查找一个当前身份有权访问的项目。"
        )
    )
    return (
        "$yunxiao-project 执行只读安装验收。先用基础身份工具读取当前 OAuth "
        "身份和组织，再" + target + " "
        "仅可使用已配置的只读 Yunxiao MCP 工具；绝对不要调用 "
        "update_work_item 或 create_work_item_comment，也不要输出 token、"
        "Authorization header 或其他凭证。按给定 JSON schema 返回身份、组织、"
        "已验证的 project 或 work_item、实际使用的工具名；失败原因写入 diagnostic。"
    )


def _collect_tool_names(value) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"tool", "tool_name"} and isinstance(child, str):
                for tool_name in ALLOWED_TOOLS:
                    if child == tool_name or child.endswith(
                        (f"__{tool_name}", f".{tool_name}", f"/{tool_name}")
                    ):
                        found.add(tool_name)
            found.update(_collect_tool_names(child))
    elif isinstance(value, list):
        for child in value:
            found.update(_collect_tool_names(child))
    return found


def _event_tools(output: str) -> set[str]:
    found: set[str] = set()
    for line in output.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        found.update(_collect_tool_names(event))
    return found


def _credential_match_labels(text: str) -> tuple[str, ...]:
    patterns = (
        *((f"package-rule-{index + 1}", pattern) for index, pattern in enumerate(CREDENTIAL_PATTERNS)),
        (
            "yunxiao-query-token",
            r"(?i)yunxiao_access_token\s*[:=]\s*[^\s&]+",
        ),
    )
    return tuple(label for label, pattern in patterns if re.search(pattern, text))


def _contains_credential(text: str) -> bool:
    return bool(_credential_match_labels(text))


def scan_credential_files(root: Path) -> tuple[Path, ...]:
    """Return only relative file paths whose text resembles a credential value."""
    matches = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if ".git" in relative.parts or "__pycache__" in relative.parts:
            continue
        if path.suffix in {".pyc", ".pyo"} or path.stat().st_size > 2_000_000:
            continue
        try:
            text = path.read_text(errors="ignore")
        except OSError:
            continue
        if _contains_credential(text):
            matches.append(relative)
    return tuple(matches)


def _diagnose(
    text: str,
    observed_tools: set[str] | None = None,
    expose_detail: bool = False,
) -> ValidationFailure:
    lowered = text.lower()
    observed = ""
    if observed_tools:
        observed = " 已观察只读工具：" + ", ".join(sorted(observed_tools)) + "。"
    oauth_failure = re.search(
        r"oauth.{0,40}(?:missing|expired|failed|incomplete|未完成|过期|失败|缺失)",
        lowered,
    )
    if "unauthenticated" in lowered or "401" in lowered or oauth_failure:
        return ValidationFailure(
            "OAuth 未完成或已过期；请运行 `codex mcp login yunxiao` 后重试。"
            + observed
        )
    if (
        "permission_denied" in lowered
        or "permission denied by server" in lowered
        or "forbidden" in lowered
        or "403" in lowered
    ):
        return ValidationFailure(
            "当前 OAuth 身份权限不足；请确认其可读取组织以及目标项目或 Work Item。"
            + observed
        )
    if "tool" in lowered and (
        "missing" in lowered or "not found" in lowered or "unknown" in lowered
    ):
        return ValidationFailure(
            "Yunxiao MCP 缺少只读验收工具；请检查 project-management toolset 和工具 allowlist。"
            + observed
        )
    if any(word in lowered for word in ("connect", "initialize", "mcp server")):
        return ValidationFailure(
            "Yunxiao MCP 未配置或不可连接；请重新运行安装器并核对官方托管端点。"
            + observed
        )
    detail = ""
    if expose_detail:
        sanitized = re.sub(r"https?://\S+", "<URL>", text)
        sanitized = re.sub(r"[A-Za-z0-9_-]{24,}", "<redacted>", sanitized)
        sanitized = " ".join(sanitized.split())[:300]
        if sanitized:
            detail = f" 安全诊断：{sanitized}"
    return ValidationFailure(
        "只读连接验收失败；请检查 Yunxiao MCP 状态、OAuth 和目标读取权限。"
        + observed
        + detail
    )


def run_live_validation(
    codex_binary: Path,
    workspace: Path,
    project_hint: str | None = None,
    work_item_hint: str | None = None,
) -> LiveValidationResult:
    """Run one ephemeral, read-only Codex session and verify its MCP behavior."""
    with tempfile.TemporaryDirectory(prefix="yunxiao-live-", dir=workspace) as directory:
        temporary = Path(directory)
        schema_path = temporary / "result.schema.json"
        output_path = temporary / "result.json"
        schema_path.write_text(json.dumps(OUTPUT_SCHEMA, ensure_ascii=False))
        command = [
            str(codex_binary),
            "--ask-for-approval",
            "never",
            "exec",
            "--model",
            "gpt-5.5",
            "--ephemeral",
            "--skip-git-repo-check",
            "--sandbox",
            "read-only",
            "--output-schema",
            str(schema_path),
            "--output-last-message",
            str(output_path),
            "--json",
            _prompt(project_hint, work_item_hint),
        ]
        try:
            completed = subprocess.run(
                command,
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=180,
            )
        except subprocess.TimeoutExpired as error:
            raise ValidationFailure(
                "只读连接验收超时；请检查 Yunxiao MCP 网络连接和 OAuth 状态。"
            ) from error

        combined = "\n".join((completed.stdout, completed.stderr))
        event_tools = _event_tools(completed.stdout)
        if WRITE_TOOLS.intersection(event_tools):
            raise ValidationFailure("只读验收检测到写工具调用，已判定验收失败。")
        credential_labels = _credential_match_labels(combined)
        if credential_labels:
            labels = ", ".join(credential_labels)
            raise ValidationFailure(
                f"验收输出触发凭证规则 {labels}，已停止且不会显示原始输出。"
            )
        if completed.returncode != 0 or not output_path.is_file():
            raise _diagnose(combined, event_tools)

        final_text = output_path.read_text()
        credential_labels = _credential_match_labels(final_text)
        if credential_labels:
            labels = ", ".join(credential_labels)
            raise ValidationFailure(
                f"验收结果触发凭证规则 {labels}，已停止且不会显示原始结果。"
            )
        try:
            final = json.loads(final_text)
        except json.JSONDecodeError as error:
            raise ValidationFailure("只读验收未返回预期的结构化结果。") from error

        reported_tools = set(final.get("tools_used", ()))
        observed_tools = event_tools | reported_tools
        if WRITE_TOOLS.intersection(observed_tools):
            raise ValidationFailure("只读验收检测到写工具调用，已判定验收失败。")
        unexpected = observed_tools - set(ALLOWED_TOOLS)
        if unexpected:
            raise ValidationFailure("只读验收使用了 allowlist 之外的工具。")
        diagnostic = final.get("diagnostic")
        if diagnostic:
            raise _diagnose(str(diagnostic), observed_tools, expose_detail=True)
        if not IDENTITY_TOOLS.intersection(observed_tools):
            observed = ", ".join(sorted(observed_tools)) or "无"
            raise ValidationFailure(
                f"只读验收未验证当前 OAuth 身份或组织。已观察工具：{observed}。"
            )
        if not RESOURCE_TOOLS.intersection(observed_tools):
            observed = ", ".join(sorted(observed_tools)) or "无"
            raise ValidationFailure(
                "只读验收未验证任何有权限访问的项目或 Work Item。"
                f"已观察工具：{observed}。"
            )
        for key in ("identity", "organization", "resource_kind", "resource"):
            if not isinstance(final.get(key), str) or not final[key].strip():
                raise ValidationFailure(f"只读验收结果缺少 {key}。")
        return LiveValidationResult(
            identity=final["identity"],
            organization=final["organization"],
            resource_kind=final["resource_kind"],
            resource=final["resource"],
            tools_used=tuple(sorted(observed_tools)),
        )


def validate_local_install(source: Path, skill_root: Path, config_path: Path) -> None:
    """Check that the installed package and MCP policy exactly match this source."""
    try:
        _validate_source(source.resolve())
        status = _check_skill(
            source.resolve(),
            skill_root.resolve() / "yunxiao-project",
        )
        mcp_plan = _plan_mcp(config_path.resolve())
    except InstallationConflict as error:
        raise ValidationFailure(str(error)) from error
    if status != "unchanged":
        raise ValidationFailure("个人 YunXiaoProject skill 尚未安装。")
    if mcp_plan.status != "unchanged":
        raise ValidationFailure("Yunxiao MCP 安全策略不完整；请重新运行安装器。")


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description="Validate YunXiaoProject using read-only live MCP calls."
    )
    parser.add_argument("--source", type=Path, default=root / ".agents/skills/yunxiao-project")
    parser.add_argument("--skill-root", type=Path, default=Path.home() / ".agents/skills")
    parser.add_argument("--config", type=Path, default=Path.home() / ".codex/config.toml")
    parser.add_argument("--codex", type=Path, default=Path("codex"))
    parser.add_argument("--project")
    parser.add_argument("--work-item")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        credential_files = scan_credential_files(Path(__file__).resolve().parents[1])
        if credential_files:
            paths = ", ".join(path.as_posix() for path in credential_files)
            raise ValidationFailure(f"项目文件疑似包含凭证值：{paths}")
        validate_local_install(args.source, args.skill_root, args.config)
        result = run_live_validation(
            args.codex,
            Path.cwd(),
            project_hint=args.project,
            work_item_hint=args.work_item,
        )
    except ValidationFailure as error:
        print(f"验收失败：{error}")
        return 2
    print("只读验收通过。")
    print(f"身份：{result.identity}")
    print(f"组织：{result.organization}")
    print(f"已验证 {result.resource_kind}：{result.resource}")
    print("未执行 Status 更新或评论创建。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
