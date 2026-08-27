from pathlib import Path
import re
import unittest

from tests.run_yunxiao_behavior_eval import build_invocation_prompt
from tests.validate_yunxiao_skill import (
    CREDENTIAL_PATTERNS,
    load_package,
    load_yaml,
    validate_skill,
)


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "yunxiao-project"


class YunxiaoProjectPackageTests(unittest.TestCase):
    def test_host_adapter_injects_skill_only_for_explicit_invocation(self) -> None:
        skill_text = "ACTIVE SKILL BODY"
        profile_text = 'organization_id: "org-controlled"'

        ordinary = build_invocation_prompt(
            "读取 Work Item ID wi-controlled-123",
            skill_text,
            profile_text,
        )
        explicit = build_invocation_prompt(
            "$yunxiao-project 读取 Work Item ID wi-controlled-123",
            skill_text,
            profile_text,
        )

        self.assertNotIn(skill_text, ordinary)
        self.assertIn(skill_text, explicit)
        self.assertIn("$yunxiao-project", explicit)

    def test_declares_explicit_only_hosted_mcp_dependency(self) -> None:
        _, frontmatter, metadata = load_package(SKILL)

        self.assertEqual(frontmatter["name"], "yunxiao-project")
        self.assertTrue(frontmatter["disable-model-invocation"])
        self.assertFalse(metadata["policy"]["allow_implicit_invocation"])
        self.assertEqual(metadata["interface"]["display_name"], "YunXiaoProject")

        dependencies = metadata["dependencies"]["tools"]
        self.assertEqual(len(dependencies), 1)
        self.assertEqual(dependencies[0]["type"], "mcp")
        self.assertEqual(dependencies[0]["value"], "yunxiao")
        self.assertEqual(dependencies[0]["transport"], "streamable_http")
        self.assertEqual(
            dependencies[0]["url"],
            "https://openapi-rdc.aliyuncs.com/ai/mcp?toolsets=project-management",
        )

    def test_profile_is_non_secret_and_package_has_no_credentials(self) -> None:
        profile = load_yaml((SKILL / "profile.yaml").read_text())
        self.assertEqual(
            profile,
            {
                "mcp_endpoint": (
                    "https://openapi-rdc.aliyuncs.com/ai/mcp"
                    "?toolsets=project-management"
                ),
                "organization_id": None,
            },
        )

        package_text = "\n".join(
            path.read_text()
            for path in sorted(SKILL.rglob("*"))
            if path.is_file()
        )
        for credential_pattern in CREDENTIAL_PATTERNS:
            self.assertIsNone(re.search(credential_pattern, package_text))

    def test_metadata_and_frontmatter_are_structurally_complete(self) -> None:
        skill_text, frontmatter, metadata = load_package(SKILL)

        self.assertEqual(SKILL.name, frontmatter["name"])
        self.assertNotIn("[TODO:", skill_text)
        self.assertIn("$yunxiao-project", metadata["interface"]["default_prompt"])
        self.assertGreaterEqual(len(metadata["interface"]["short_description"]), 25)
        self.assertLessEqual(len(metadata["interface"]["short_description"]), 64)

    def test_package_passes_executable_validator(self) -> None:
        self.assertEqual(validate_skill(SKILL), [])


if __name__ == "__main__":
    unittest.main()
