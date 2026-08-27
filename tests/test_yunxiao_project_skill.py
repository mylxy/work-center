import json
from pathlib import Path
import re
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "yunxiao-project"


def load_yaml(text: str) -> dict:
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
    return json.loads(completed.stdout)


class YunxiaoProjectPackageTests(unittest.TestCase):
    def test_declares_explicit_only_hosted_mcp_dependency(self) -> None:
        skill_text = (SKILL / "SKILL.md").read_text()
        frontmatter = load_yaml(skill_text.split("---", 2)[1])
        metadata = load_yaml((SKILL / "agents" / "openai.yaml").read_text())

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
        for credential_pattern in (
            r"(?i)Bearer\s+[A-Za-z0-9._~-]+",
            r"\bpt-[A-Za-z0-9_-]+",
            r"\boat-[A-Za-z0-9_-]+",
            r"\bort-[A-Za-z0-9_-]+",
            r"(?i)(?:access|refresh|oauth|yunxiao)[_-]?token\s*:",
        ):
            self.assertIsNone(re.search(credential_pattern, package_text))

    def test_metadata_and_frontmatter_are_structurally_complete(self) -> None:
        skill_text = (SKILL / "SKILL.md").read_text()
        frontmatter = load_yaml(skill_text.split("---", 2)[1])
        metadata = load_yaml((SKILL / "agents" / "openai.yaml").read_text())

        self.assertEqual(SKILL.name, frontmatter["name"])
        self.assertNotIn("[TODO:", skill_text)
        self.assertIn("$yunxiao-project", metadata["interface"]["default_prompt"])
        self.assertGreaterEqual(len(metadata["interface"]["short_description"]), 25)
        self.assertLessEqual(len(metadata["interface"]["short_description"]), 64)


if __name__ == "__main__":
    unittest.main()
