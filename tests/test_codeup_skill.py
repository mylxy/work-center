from pathlib import Path
import tempfile
import unittest

from scripts.install_codeup_skill import install
from skills.codeup.scripts.flow_catalog import discover, command_row


class CodeupSkillTests(unittest.TestCase):
    def test_discovery_uses_only_real_flow_commands(self):
        help_text = "  flow-get-pipeline  获取流水线\n  app-stack-flow-other  其他\n"
        self.assertEqual(discover(help_text), ["flow-get-pipeline"])
        with self.assertRaises(ValueError):
            discover("plugin is missing")

    def test_catalog_keeps_optional_flags_and_excludes_global_credentials(self):
        help_text = """描述: 获取流水线（可用版本：中心版）
API 版本: 2026-05-25
参数:
  --group-id int (required), 分组
  --page int, 当前页
全局参数:
  --yunxiao-access-token string, token
"""
        row = command_row("flow-get-pipeline", help_text)
        self.assertIn("`--group-id`*", row)
        self.assertIn("`--page`", row)
        self.assertNotIn("--yunxiao-access-token", row)
        self.assertIn("中心版", row)
        self.assertNotIn("--", command_row("flow-list-tags", "描述: 标签\n全局参数:\n  --help bool"))

    def test_install_is_idempotent_and_preserves_conflicting_skill(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, target = Path(tmp) / "source", Path(tmp) / "target"
            source.mkdir()
            (source / "SKILL.md").write_text("codeup skill")
            self.assertEqual(install(source, target), "installed")
            self.assertEqual(install(source, target), "unchanged")
            (target / "SKILL.md").write_text("user content")
            with self.assertRaises(ValueError):
                install(source, target)
            self.assertEqual((target / "SKILL.md").read_text(), "user content")


if __name__ == "__main__":
    unittest.main()
