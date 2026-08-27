#!/usr/bin/env python3
"""Safely install YunXiaoProject as a personal skill and restricted MCP."""

from __future__ import annotations

from dataclasses import dataclass
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))
from tests.validate_yunxiao_skill import validate_skill  # noqa: E402


HOSTED_ENDPOINT = (
    "https://openapi-rdc.aliyuncs.com/ai/mcp?toolsets=project-management"
)
ALLOWED_TOOLS = (
    "get_current_organization_info",
    "get_user_organizations",
    "get_current_user",
    "search_projects",
    "search_workitems",
    "get_work_item",
    "get_work_item_workflow",
    "list_work_item_comments",
    "create_work_item_comment",
    "list_workitem_activities",
    "update_work_item",
)
WRITE_TOOLS = ("create_work_item_comment", "update_work_item")
READ_TOOLS = tuple(name for name in ALLOWED_TOOLS if name not in WRITE_TOOLS)
TOOL_APPROVALS = (
    *((name, "approve") for name in READ_TOOLS),
    *((name, "prompt") for name in WRITE_TOOLS),
)
SERVER_HEADER = re.compile(
    r'^\s*\[\s*mcp_servers\.(?:yunxiao|"yunxiao")\s*\]\s*(?:#.*)?$'
)
ANY_HEADER = re.compile(r"^\s*\[.*\]\s*(?:#.*)?$")
ASSIGNMENT = re.compile(r"^\s*([A-Za-z0-9_-]+)\s*=\s*(.*?)\s*(?:#.*)?$")
MCP_SERVERS_KEY = r'(?:mcp_servers|"mcp_servers"|\'mcp_servers\')'
YUNXIAO_KEY = r'(?:yunxiao|"yunxiao"|\'yunxiao\')'
TOOLS_KEY = r'(?:tools|"tools"|\'tools\')'
YUNXIAO_TABLE_HEADER = re.compile(
    rf'^\s*\[\s*{MCP_SERVERS_KEY}\s*\.\s*{YUNXIAO_KEY}(?:\s*\.|\s*\])'
)
YUNXIAO_DOTTED_KEY = re.compile(
    rf'^\s*{MCP_SERVERS_KEY}\s*\.\s*{YUNXIAO_KEY}\s*\.'
)
TOOLS_DOTTED_KEY = re.compile(rf'^\s*{TOOLS_KEY}\s*\.')
UNSAFE_AUTH_KEYS = {
    "bearer_token_env_var",
    "http_headers",
    "env_http_headers",
    "command",
    "args",
}
UNSAFE_AUTH_SECTION = re.compile(
    rf'^\s*\[\s*{MCP_SERVERS_KEY}\s*\.\s*{YUNXIAO_KEY}\s*\.\s*'
    r'(?:http_headers|"http_headers"|env_http_headers|"env_http_headers")'
    r'(?:\.|\s*\])'
)


class InstallationConflict(RuntimeError):
    """Raised when an existing personal resource cannot be safely attributed."""


@dataclass(frozen=True)
class InstallationResult:
    skill: str
    mcp: str


@dataclass(frozen=True)
class McpPlan:
    text: str
    status: str


def _file_manifest(directory: Path) -> dict[str, str]:
    manifest: dict[str, str] = {}
    for path in sorted(directory.rglob("*")):
        if path.is_symlink():
            raise InstallationConflict(
                "personal skill source or destination contains a symbolic link"
            )
        if path.is_file():
            relative = path.relative_to(directory).as_posix()
            manifest[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return manifest


def _manifest_digest(manifest: dict[str, str]) -> str:
    serialized = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode()).hexdigest()


def _load_receipt(receipt_path: Path) -> dict[str, str] | None:
    if not receipt_path.is_file():
        return None
    try:
        receipt = json.loads(receipt_path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise InstallationConflict("personal skill installation receipt is invalid") from error
    if not isinstance(receipt, dict):
        raise InstallationConflict("personal skill installation receipt is invalid")
    return receipt


def _validate_source(source: Path) -> None:
    errors = validate_skill(source.resolve())
    if errors:
        raise InstallationConflict(
            "source skill failed validation: " + "; ".join(errors)
        )


def _check_skill(source: Path, target: Path, receipt_path: Path | None = None) -> str:
    if not target.exists():
        return "installed"
    if not target.is_dir():
        raise InstallationConflict(
            "personal skill already exists with different content; refusing to overwrite it"
        )
    source_manifest = _file_manifest(source)
    target_manifest = _file_manifest(target)
    if source_manifest == target_manifest:
        return "unchanged"
    receipt = _load_receipt(receipt_path) if receipt_path else None
    if (
        receipt
        and receipt.get("source") == str(source)
        and receipt.get("installed_digest") == _manifest_digest(target_manifest)
    ):
        return "updated"
    raise InstallationConflict(
        "personal skill already exists with different content; refusing to overwrite it"
    )


def _parse_value(raw: str):
    normalized = re.sub(r"\btrue\b", "True", raw)
    normalized = re.sub(r"\bfalse\b", "False", normalized)
    try:
        return ast.literal_eval(normalized)
    except (SyntaxError, ValueError) as error:
        raise InstallationConflict(
            "existing Yunxiao MCP configuration uses unsupported TOML syntax"
        ) from error


def _server_section(lines: list[str]) -> tuple[int, int] | None:
    start = next((index for index, line in enumerate(lines) if SERVER_HEADER.match(line)), None)
    if start is None:
        return None
    end = next(
        (
            index
            for index in range(start + 1, len(lines))
            if ANY_HEADER.match(lines[index])
        ),
        len(lines),
    )
    return start, end


def _desired_assignments() -> tuple[tuple[str, str], ...]:
    rendered_tools = ", ".join(f'"{name}"' for name in ALLOWED_TOOLS)
    return (
        ("url", f'"{HOSTED_ENDPOINT}"'),
        ("auth", '"oauth"'),
        ("enabled_tools", f"[{rendered_tools}]"),
        ("default_tools_approval_mode", '"auto"'),
        ("required", "true"),
    )


def _tool_policy_block(tool_name: str, approval_mode: str) -> list[str]:
    return [
        f"[mcp_servers.yunxiao.tools.{tool_name}]",
        f'approval_mode = "{approval_mode}"',
    ]


def _tool_policy_header(tool_name: str) -> re.Pattern:
    return re.compile(
        rf'^\s*\[\s*mcp_servers\.(?:yunxiao|"yunxiao")\.tools\.'
        rf'(?:{re.escape(tool_name)}|"{re.escape(tool_name)}")\s*\]\s*(?:#.*)?$'
    )


def _validate_tool_policies(original: str) -> tuple[tuple[str, str], ...]:
    missing = []
    lines = original.splitlines()
    for tool_name, approval_mode in TOOL_APPROVALS:
        header = _tool_policy_header(tool_name)
        matches = [index for index, line in enumerate(lines) if header.match(line)]
        if not matches:
            missing.append((tool_name, approval_mode))
            continue
        if len(matches) != 1:
            raise InstallationConflict(
                f"existing Yunxiao MCP has duplicate {tool_name} approval policies"
            )
        start = matches[0]
        end = next(
            (
                index
                for index in range(start + 1, len(lines))
                if ANY_HEADER.match(lines[index])
            ),
            len(lines),
        )
        values = {}
        for line in lines[start + 1 : end]:
            match = ASSIGNMENT.match(line)
            if match:
                values[match.group(1)] = _parse_value(match.group(2))
        if values != {"approval_mode": approval_mode}:
            raise InstallationConflict(
                f"existing Yunxiao MCP has a conflicting {tool_name} approval policy"
            )
    return tuple(missing)


def _inspect_mcp_config(config_path: Path) -> dict | None:
    """Use Codex's TOML parser to locate the logical Yunxiao MCP entry."""
    if not config_path.exists():
        return None
    codex = shutil.which("codex")
    if codex is None:
        raise InstallationConflict(
            "Codex CLI is required to inspect the existing MCP configuration"
        )
    with tempfile.TemporaryDirectory(prefix="yunxiao-config-inspect-") as directory:
        temporary_home = Path(directory)
        (temporary_home / "config.toml").symlink_to(config_path)
        completed = subprocess.run(
            [codex, "mcp", "get", "yunxiao", "--json"],
            capture_output=True,
            env={**os.environ, "CODEX_HOME": str(temporary_home)},
            text=True,
        )
    if completed.returncode == 0:
        try:
            server = json.loads(completed.stdout)
        except json.JSONDecodeError as error:
            raise InstallationConflict(
                "Codex returned an invalid MCP configuration inspection result"
            ) from error
        if not isinstance(server, dict):
            raise InstallationConflict(
                "Codex returned an invalid MCP configuration inspection result"
            )
        return server
    if "No MCP server named 'yunxiao' found" in completed.stderr:
        return None
    raise InstallationConflict(
        "existing Codex configuration could not be parsed safely; refusing to modify it"
    )


def _plan_mcp(config_path: Path) -> McpPlan:
    original = config_path.read_text() if config_path.exists() else ""
    lines = original.splitlines()
    inspected_server = _inspect_mcp_config(config_path)
    if any(UNSAFE_AUTH_SECTION.match(line) for line in lines):
        raise InstallationConflict(
            "existing Yunxiao MCP uses a non-OAuth transport or credential source"
        )
    supported_tool_headers = tuple(
        _tool_policy_header(tool_name) for tool_name, _ in TOOL_APPROVALS
    )
    if any(
        YUNXIAO_TABLE_HEADER.match(line)
        and not SERVER_HEADER.match(line)
        and not any(header.match(line) for header in supported_tool_headers)
        for line in lines
    ) or any(YUNXIAO_DOTTED_KEY.match(line) for line in lines):
        raise InstallationConflict(
            "existing Yunxiao MCP configuration has an unsupported structure"
        )
    section = _server_section(lines)
    if section is None:
        if inspected_server is not None:
            raise InstallationConflict(
                "existing Yunxiao MCP configuration has an unsupported structure"
            )
        block = ["[mcp_servers.yunxiao]"]
        block.extend(f"{key} = {value}" for key, value in _desired_assignments())
        for tool_name, approval_mode in TOOL_APPROVALS:
            block.extend(["", *_tool_policy_block(tool_name, approval_mode)])
        prefix = original
        if prefix and not prefix.endswith("\n"):
            prefix += "\n"
        if prefix and not prefix.endswith("\n\n"):
            prefix += "\n"
        return McpPlan(prefix + "\n".join(block) + "\n", "configured")

    start, end = section
    if any(TOOLS_DOTTED_KEY.match(line) for line in lines[start + 1 : end]):
        raise InstallationConflict(
            "existing Yunxiao MCP configuration has an unsupported tool policy structure"
        )
    if inspected_server is None:
        raise InstallationConflict(
            "existing Yunxiao MCP configuration could not be inspected safely"
        )
    transport = inspected_server.get("transport")
    if not isinstance(transport, dict):
        raise InstallationConflict("existing Yunxiao MCP transport is invalid")
    if (
        transport.get("type") != "streamable_http"
        or transport.get("url") != HOSTED_ENDPOINT
    ):
        raise InstallationConflict(
            "existing Yunxiao MCP points to a different endpoint; refusing to overwrite it"
        )
    if any(
        transport.get(key) is not None
        for key in ("bearer_token_env_var", "http_headers", "env_http_headers")
    ):
        raise InstallationConflict(
            "existing Yunxiao MCP uses a non-OAuth transport or credential source"
        )
    inspected_tools = inspected_server.get("enabled_tools")
    if inspected_tools is not None and inspected_tools != list(ALLOWED_TOOLS):
        raise InstallationConflict(
            "existing Yunxiao MCP has a conflicting enabled_tools policy"
        )
    values = {}
    for line in lines[start + 1 : end]:
        match = ASSIGNMENT.match(line)
        if match:
            values[match.group(1)] = _parse_value(match.group(2))

    if UNSAFE_AUTH_KEYS.intersection(values):
        raise InstallationConflict(
            "existing Yunxiao MCP uses a non-OAuth transport or credential source"
        )
    if values.get("url") != HOSTED_ENDPOINT:
        raise InstallationConflict(
            "existing Yunxiao MCP points to a different endpoint; refusing to overwrite it"
        )
    expected_values = {
        "auth": "oauth",
        "enabled_tools": list(ALLOWED_TOOLS),
        "default_tools_approval_mode": "auto",
        "required": True,
    }
    for key, expected in expected_values.items():
        if key in values and values[key] != expected:
            raise InstallationConflict(
                f"existing Yunxiao MCP has a conflicting {key} policy"
            )

    missing = [
        (key, rendered)
        for key, rendered in _desired_assignments()
        if key not in values
    ]
    missing_tool_policies = _validate_tool_policies(original)
    if not missing and not missing_tool_policies:
        return McpPlan(original, "unchanged")

    insertion = [f"{key} = {value}" for key, value in missing]
    updated = [*lines[:end], *insertion, *lines[end:]]
    for tool_name, approval_mode in missing_tool_policies:
        updated.extend(["", *_tool_policy_block(tool_name, approval_mode)])
    return McpPlan("\n".join(updated) + "\n", "configured")


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o600
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".yunxiao-config-",
        dir=path.parent,
        text=True,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w") as stream:
            stream.write(text)
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _copy_skill(source: Path, target: Path, replace: bool = False) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    staging_root = Path(
        tempfile.mkdtemp(prefix=".yunxiao-skill-", dir=target.parent)
    )
    staged = staging_root / target.name
    backup = staging_root / "previous"
    try:
        shutil.copytree(source, staged)
        if replace:
            os.replace(target, backup)
        os.replace(staged, target)
        if backup.exists():
            shutil.rmtree(backup)
    except Exception:
        if backup.exists() and not target.exists():
            os.replace(backup, target)
        raise
    finally:
        shutil.rmtree(staging_root)


def _write_receipt(receipt_path: Path, source: Path, target: Path) -> None:
    receipt = {
        "source": str(source),
        "installed_digest": _manifest_digest(_file_manifest(target)),
    }
    _atomic_write_text(
        receipt_path,
        json.dumps(receipt, ensure_ascii=False, sort_keys=True) + "\n",
    )


def install(source: Path, skill_root: Path, config_path: Path) -> InstallationResult:
    """Install only when both the personal skill and MCP config are conflict-free."""
    source = source.resolve()
    skill_root = skill_root.resolve()
    target = skill_root / "yunxiao-project"
    receipt_path = skill_root / ".yunxiao-project-install.json"
    config_path = config_path.resolve()
    _validate_source(source)
    skill_status = _check_skill(source, target, receipt_path)
    mcp_plan = _plan_mcp(config_path)

    original_config = config_path.read_bytes() if config_path.exists() else None
    try:
        if mcp_plan.status == "configured":
            _atomic_write_text(config_path, mcp_plan.text)
        if skill_status in {"installed", "updated"}:
            _copy_skill(source, target, replace=skill_status == "updated")
        _write_receipt(receipt_path, source, target)
    except Exception:
        if original_config is None:
            if config_path.exists():
                config_path.unlink()
        else:
            _atomic_write_text(config_path, original_config.decode())
        raise
    return InstallationResult(skill=skill_status, mcp=mcp_plan.status)


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description="Install YunXiaoProject without replacing conflicting personal resources."
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=root / ".agents" / "skills" / "yunxiao-project",
    )
    parser.add_argument(
        "--skill-root",
        type=Path,
        default=Path.home() / ".agents" / "skills",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path.home() / ".codex" / "config.toml",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = install(args.source, args.skill_root, args.config)
    except InstallationConflict as error:
        print(f"安装停止：{error}")
        return 2
    print(f"个人 skill：{result.skill}；Yunxiao MCP：{result.mcp}")
    print("下一步：运行 `codex mcp login yunxiao` 完成 OAuth。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
