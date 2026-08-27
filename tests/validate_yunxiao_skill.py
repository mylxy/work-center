#!/usr/bin/env python3
"""Validate the YunXiaoProject package, including explicit-invocation metadata."""

import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


HOSTED_ENDPOINT = (
    "https://openapi-rdc.aliyuncs.com/ai/mcp?toolsets=project-management"
)
ALLOWED_FRONTMATTER = {"name", "description", "metadata"}
CREDENTIAL_PATTERNS = (
    r"(?i)Bearer\s+[A-Za-z0-9._~-]+",
    r"\bpt-[A-Za-z0-9_-]+",
    r"\boat-[A-Za-z0-9_-]+",
    r"\bort-[A-Za-z0-9_-]+",
    r"(?i)(?:access|refresh|oauth|yunxiao)[_-]?token\s*:",
)


def load_yaml(text: str) -> dict[str, Any]:
    """Use the system Ruby YAML parser so validation needs no Python packages."""
    completed = subprocess.run(
        [
            "ruby",
            "-ryaml",
            "-rjson",
            "-e",
            "puts JSON.generate(YAML.safe_load(STDIN.read))",
        ],
        check=True,
        capture_output=True,
        input=text,
        text=True,
    )
    loaded = json.loads(completed.stdout)
    if not isinstance(loaded, dict):
        raise ValueError("YAML root must be a mapping")
    return loaded


def load_package(skill_dir: Path) -> tuple[str, dict[str, Any], dict[str, Any]]:
    skill_text = (skill_dir / "SKILL.md").read_text()
    parts = skill_text.split("---", 2)
    if len(parts) != 3 or parts[0].strip():
        raise ValueError("SKILL.md must begin with YAML frontmatter")
    return (
        skill_text,
        load_yaml(parts[1]),
        load_yaml((skill_dir / "agents" / "openai.yaml").read_text()),
    )


def mapping_node(
    parent: dict[str, Any],
    key: str,
    errors: list[str],
) -> dict[str, Any]:
    value = parent.get(key)
    if not isinstance(value, dict):
        errors.append(f"{key} must be a mapping")
        return {}
    return value


def validate_skill(skill_dir: Path) -> list[str]:
    errors: list[str] = []
    if (
        skill_dir.parent.name != "skills"
        or skill_dir.parent.parent.name != ".agents"
    ):
        errors.append("skill must live under the repository .agents/skills directory")
    required_files = (
        skill_dir / "SKILL.md",
        skill_dir / "agents" / "openai.yaml",
        skill_dir / "profile.yaml",
    )
    missing = [
        str(path.relative_to(skill_dir))
        for path in required_files
        if not path.is_file()
    ]
    if missing:
        return [f"missing required file: {path}" for path in missing]

    try:
        skill_text, frontmatter, metadata = load_package(skill_dir)
        profile = load_yaml((skill_dir / "profile.yaml").read_text())
    except (OSError, ValueError, subprocess.CalledProcessError, json.JSONDecodeError) as error:
        return [f"invalid package YAML: {error}"]

    unexpected = set(frontmatter) - ALLOWED_FRONTMATTER
    if unexpected:
        errors.append(f"unsupported frontmatter keys: {sorted(unexpected)}")
    if frontmatter.get("name") != skill_dir.name:
        errors.append("frontmatter name must match the skill directory")
    description = frontmatter.get("description")
    if not isinstance(description, str) or not description.strip():
        errors.append("frontmatter description must be non-empty")
    elif "$yunxiao-project" not in description or "only" not in description.lower():
        errors.append("frontmatter description must require explicit invocation")
    frontmatter_metadata = mapping_node(frontmatter, "metadata", errors)
    if frontmatter_metadata.get("disable-model-invocation") is not True:
        errors.append("metadata.disable-model-invocation must be true")
    if "[TODO:" in skill_text:
        errors.append("SKILL.md contains unresolved TODO markers")

    interface = mapping_node(metadata, "interface", errors)
    if interface.get("display_name") != "YunXiaoProject":
        errors.append("interface.display_name must be YunXiaoProject")
    short_description = interface.get("short_description", "")
    if (
        not isinstance(short_description, str)
        or not 25 <= len(short_description) <= 64
    ):
        errors.append("interface.short_description must contain 25-64 characters")
    default_prompt = interface.get("default_prompt")
    if (
        not isinstance(default_prompt, str)
        or "$yunxiao-project" not in default_prompt
    ):
        errors.append("interface.default_prompt must show explicit invocation")
    policy = mapping_node(metadata, "policy", errors)
    if policy.get("allow_implicit_invocation") is not False:
        errors.append("policy.allow_implicit_invocation must be false")

    dependency_config = mapping_node(metadata, "dependencies", errors)
    dependencies = dependency_config.get("tools", [])
    expected_dependency = {
        "type": "mcp",
        "value": "yunxiao",
        "description": "阿里云官方托管的云效 MCP，仅启用项目管理工具集",
        "transport": "streamable_http",
        "url": HOSTED_ENDPOINT,
    }
    if dependencies != [expected_dependency]:
        errors.append("dependencies.tools must declare only the hosted Yunxiao MCP")
    if set(profile) != {"mcp_endpoint", "organization_id", "default_project_id"}:
        errors.append(
            "profile.yaml must contain only endpoint, organization ID, and default project ID"
        )
    if profile.get("mcp_endpoint") != HOSTED_ENDPOINT:
        errors.append("profile.yaml must use the hosted Yunxiao MCP endpoint")
    for key in ("organization_id", "default_project_id"):
        value = profile.get(key)
        if value is not None and (not isinstance(value, str) or not value.strip()):
            errors.append(f"profile.yaml {key} must be null or a non-empty string")

    package_text = "\n".join(
        path.read_text()
        for path in sorted(skill_dir.rglob("*"))
        if path.is_file()
    )
    for pattern in CREDENTIAL_PATTERNS:
        if re.search(pattern, package_text):
            errors.append(f"package contains a credential-like value matching {pattern!r}")
    return errors


def main() -> int:
    skill_dir = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else Path(".agents/skills/yunxiao-project")
    )
    errors = validate_skill(skill_dir.resolve())
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("Skill is valid!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
