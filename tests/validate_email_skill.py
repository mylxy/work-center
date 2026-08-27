#!/usr/bin/env python3
"""Validate the explicit email skill package without external Python packages."""

from pathlib import Path
import re
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.validate_yunxiao_skill import load_yaml, mapping_node


ALLOWED_FRONTMATTER = {"name", "description", "metadata"}
CREDENTIAL_PATTERNS = (
    r"(?i)(?:password|secret|token)\s*[:=]\s*['\"][^'\"]{8,}['\"]",
    r"(?i)Bearer\s+[A-Za-z0-9._~-]+",
)
REQUIRED_INSTRUCTIONS = (
    "发送 <draft-id>",
    ".mailctl/tmp/",
    "Mail Content",
    "scripts/mailctl",
    "不得在准备草稿的同一轮调用 `send`",
    "不得重试发送",
)


def validate_skill(skill_dir: Path) -> list[str]:
    errors: list[str] = []
    required = (
        skill_dir / "SKILL.md",
        skill_dir / "agents" / "openai.yaml",
        skill_dir / "scripts" / "mailctl",
    )
    missing = [str(path.relative_to(skill_dir)) for path in required if not path.is_file()]
    if missing:
        return [f"missing required file: {path}" for path in missing]

    skill_text = (skill_dir / "SKILL.md").read_text()
    parts = skill_text.split("---", 2)
    if len(parts) != 3 or parts[0].strip():
        return ["SKILL.md must begin with YAML frontmatter"]

    try:
        frontmatter = load_yaml(parts[1])
        metadata = load_yaml((skill_dir / "agents" / "openai.yaml").read_text())
    except Exception as error:  # validator reports malformed package data
        return [f"invalid package YAML: {error}"]

    unexpected = set(frontmatter) - ALLOWED_FRONTMATTER
    if unexpected:
        errors.append(f"unsupported frontmatter keys: {sorted(unexpected)}")
    if frontmatter.get("name") != "email":
        errors.append("frontmatter name must be email")
    description = frontmatter.get("description")
    if not isinstance(description, str) or "$email" not in description or "only" not in description.lower():
        errors.append("frontmatter description must require explicit $email invocation")
    frontmatter_metadata = mapping_node(frontmatter, "metadata", errors)
    if frontmatter_metadata.get("disable-model-invocation") is not True:
        errors.append("metadata.disable-model-invocation must be true")

    interface = mapping_node(metadata, "interface", errors)
    if interface.get("display_name") != "Email":
        errors.append("interface.display_name must be Email")
    short_description = interface.get("short_description", "")
    if not isinstance(short_description, str) or not 25 <= len(short_description) <= 64:
        errors.append("interface.short_description must contain 25-64 characters")
    if "$email" not in str(interface.get("default_prompt", "")):
        errors.append("interface.default_prompt must show explicit invocation")
    policy = mapping_node(metadata, "policy", errors)
    if policy.get("allow_implicit_invocation") is not False:
        errors.append("policy.allow_implicit_invocation must be false")
    if "dependencies" in metadata:
        errors.append("email skill must not declare an MCP dependency")

    launcher = skill_dir / "scripts" / "mailctl"
    if not launcher.stat().st_mode & 0o111:
        errors.append("scripts/mailctl must be executable")
    if "python3.12" not in launcher.read_text():
        errors.append("scripts/mailctl must require Python 3.12")

    for instruction in REQUIRED_INSTRUCTIONS:
        if instruction not in skill_text:
            errors.append(f"SKILL.md is missing required instruction: {instruction}")

    package_text = "\n".join(
        path.read_text(errors="replace")
        for path in sorted(skill_dir.rglob("*"))
        if path.is_file()
    )
    if "[TODO:" in package_text:
        errors.append("skill package contains unresolved TODO markers")
    for pattern in CREDENTIAL_PATTERNS:
        if re.search(pattern, package_text):
            errors.append(f"package contains a credential-like value matching {pattern!r}")
    return errors


def main() -> int:
    skill_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "skills/email").resolve()
    errors = validate_skill(skill_dir)
    for error in errors:
        print(f"ERROR: {error}")
    if errors:
        return 1
    print("Email skill is valid!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
