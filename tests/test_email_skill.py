from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from tests.validate_email_skill import AUTH_TERMINAL_INSTRUCTIONS, validate_skill


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "email"
INSTALLER = ROOT / "scripts" / "install_email_skill.py"


class EmailSkillPackageTests(unittest.TestCase):
    def test_explicit_email_skill_bundles_mailctl(self) -> None:
        self.assertTrue((SKILL / "SKILL.md").is_file())
        self.assertTrue((SKILL / "agents" / "openai.yaml").is_file())
        launcher = SKILL / "scripts" / "mailctl"
        self.assertTrue(launcher.is_file())
        self.assertTrue(launcher.stat().st_mode & 0o111)

    def test_package_passes_executable_validator(self) -> None:
        self.assertEqual(validate_skill(SKILL), [])
        result = subprocess.run(
            [sys.executable, str(ROOT / "tests" / "validate_email_skill.py"), str(SKILL)],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_auth_setup_requires_a_verified_visible_terminal_handoff(self) -> None:
        for instruction in AUTH_TERMINAL_INSTRUCTIONS:
            with self.subTest(instruction=instruction):
                with tempfile.TemporaryDirectory(
                    prefix="email-skill-auth-terminal-"
                ) as directory:
                    skill = Path(directory) / "email"
                    shutil.copytree(SKILL, skill)
                    skill_file = skill / "SKILL.md"
                    skill_file.write_text(
                        skill_file.read_text().replace(instruction, "<REMOVED>")
                    )

                    errors = validate_skill(skill)

                self.assertIn(
                    "SKILL.md is missing authentication terminal instruction: "
                    f"{instruction}",
                    errors,
                )

    def test_auth_setup_requires_terminal_handoff_workflow_order(self) -> None:
        with tempfile.TemporaryDirectory(prefix="email-skill-auth-order-") as directory:
            skill = Path(directory) / "email"
            shutil.copytree(SKILL, skill)
            skill_file = skill / "SKILL.md"
            skill_text = skill_file.read_text()
            skill_file.write_text(
                skill_text.replace("`open_in_codex`", "<SWAP>")
                .replace("`read_thread_terminal`", "`open_in_codex`")
                .replace("<SWAP>", "`read_thread_terminal`")
            )

            errors = validate_skill(skill)

        self.assertIn(
            "SKILL.md authentication terminal instructions must appear in workflow order",
            errors,
        )

    def test_installer_creates_idempotent_authoritative_symlink(self) -> None:
        with tempfile.TemporaryDirectory(prefix="email-skill-install-") as directory:
            target = Path(directory) / "email"

            first = subprocess.run(
                [sys.executable, str(INSTALLER), "--target", str(target)],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            second = subprocess.run(
                [sys.executable, str(INSTALLER), "--target", str(target)],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )

            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertTrue(target.is_symlink())
            self.assertEqual(target.resolve(), SKILL.resolve())

    def test_installer_refuses_to_replace_an_existing_target(self) -> None:
        with tempfile.TemporaryDirectory(prefix="email-skill-install-") as directory:
            target = Path(directory) / "email"
            target.mkdir()
            marker = target / "keep.txt"
            marker.write_text("keep\n")

            result = subprocess.run(
                [sys.executable, str(INSTALLER), "--target", str(target)],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 2)
            self.assertTrue(marker.is_file())


if __name__ == "__main__":
    unittest.main()
