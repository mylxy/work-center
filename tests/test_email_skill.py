from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tests.validate_email_skill import validate_skill


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".agents" / "skills" / "email"
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
