from pathlib import Path
import shutil
import tempfile
import unittest

from tests.validate_yunxiao_skill import validate_skill


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".agents" / "skills" / "yunxiao-project"


class YunxiaoProjectPackageTests(unittest.TestCase):
    def test_package_passes_executable_validator(self) -> None:
        self.assertEqual(validate_skill(SKILL), [])

    def test_validator_reports_malformed_nested_metadata(self) -> None:
        with tempfile.TemporaryDirectory(prefix="yunxiao-validator-") as directory:
            candidate = Path(directory) / ".agents" / "skills" / "yunxiao-project"
            candidate.parent.mkdir(parents=True)
            shutil.copytree(SKILL, candidate)
            (candidate / "agents" / "openai.yaml").write_text(
                "interface: []\npolicy: []\ndependencies: []\n"
            )

            errors = validate_skill(candidate)

        self.assertIn("interface must be a mapping", errors)
        self.assertIn("policy must be a mapping", errors)
        self.assertIn("dependencies must be a mapping", errors)

    def test_validator_rejects_credential_like_values(self) -> None:
        with tempfile.TemporaryDirectory(prefix="yunxiao-validator-") as directory:
            candidate = Path(directory) / "yunxiao-project"
            shutil.copytree(SKILL, candidate)
            with (candidate / "profile.yaml").open("a") as profile:
                profile.write("oauth_token: leaked-value\n")

            errors = validate_skill(candidate)

        self.assertTrue(
            any("credential-like value" in error for error in errors),
            errors,
        )

    def test_profile_accepts_optional_default_project_id(self) -> None:
        with tempfile.TemporaryDirectory(prefix="yunxiao-validator-") as directory:
            candidate = Path(directory) / ".agents" / "skills" / "yunxiao-project"
            candidate.parent.mkdir(parents=True)
            shutil.copytree(SKILL, candidate)
            (candidate / "profile.yaml").write_text(
                'mcp_endpoint: "https://openapi-rdc.aliyuncs.com/ai/mcp?toolsets=project-management"\n'
                'organization_id: "org-controlled"\n'
                'default_project_id: "project-controlled"\n'
            )

            errors = validate_skill(candidate)

        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
