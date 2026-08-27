from pathlib import Path
import json
import os
import shutil
import subprocess
import tempfile
import unittest

from scripts.install_yunxiao_skill import (
    ALLOWED_TOOLS,
    HOSTED_ENDPOINT,
    InstallationConflict,
    READ_TOOLS,
    install,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE_SKILL = ROOT / ".agents" / "skills" / "yunxiao-project"


def load_server(config_home: Path) -> dict:
    completed = subprocess.run(
        ["codex", "mcp", "get", "yunxiao", "--json"],
        check=True,
        capture_output=True,
        env={**os.environ, "CODEX_HOME": str(config_home)},
        text=True,
    )
    return json.loads(completed.stdout)


class YunxiaoSkillInstallationTests(unittest.TestCase):
    def test_installs_personal_skill_and_restricted_oauth_mcp(self) -> None:
        with tempfile.TemporaryDirectory(prefix="yunxiao-install-") as directory:
            home = Path(directory)
            skill_root = home / ".agents" / "skills"
            config_path = home / ".codex" / "config.toml"

            result = install(SOURCE_SKILL, skill_root, config_path)

            installed = skill_root / "yunxiao-project"
            self.assertEqual(
                (installed / "SKILL.md").read_text(),
                (SOURCE_SKILL / "SKILL.md").read_text(),
            )
            server = load_server(config_path.parent)
            self.assertEqual(server["transport"]["url"], HOSTED_ENDPOINT)
            self.assertEqual(server["enabled_tools"], list(ALLOWED_TOOLS))
            config_text = config_path.read_text()
            self.assertIn('auth = "oauth"', config_text)
            self.assertIn('default_tools_approval_mode = "auto"', config_text)
            self.assertIn('required = true', config_text)
            for write_tool in ("create_work_item_comment", "update_work_item"):
                self.assertIn(
                    f"[mcp_servers.yunxiao.tools.{write_tool}]\n"
                    'approval_mode = "prompt"',
                    config_text,
                )
            for read_tool in READ_TOOLS:
                self.assertIn(
                    f"[mcp_servers.yunxiao.tools.{read_tool}]\n"
                    'approval_mode = "approve"',
                    config_text,
                )
            self.assertEqual(result.skill, "installed")
            self.assertEqual(result.mcp, "configured")

    def test_reinstall_of_identical_skill_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory(prefix="yunxiao-install-") as directory:
            home = Path(directory)
            skill_root = home / ".agents" / "skills"
            config_path = home / ".codex" / "config.toml"
            install(SOURCE_SKILL, skill_root, config_path)

            result = install(SOURCE_SKILL, skill_root, config_path)

            self.assertEqual(result.skill, "unchanged")
            self.assertEqual(result.mcp, "unchanged")

    def test_updates_only_an_unchanged_skill_from_the_same_source(self) -> None:
        with tempfile.TemporaryDirectory(prefix="yunxiao-install-") as directory:
            home = Path(directory)
            source = home / "repo" / ".agents" / "skills" / "yunxiao-project"
            source.parent.mkdir(parents=True)
            shutil.copytree(SOURCE_SKILL, source)
            skill_root = home / ".agents" / "skills"
            config_path = home / ".codex" / "config.toml"
            install(source, skill_root, config_path)
            with (source / "SKILL.md").open("a") as skill:
                skill.write("\n<!-- same-source update -->\n")

            result = install(source, skill_root, config_path)

            self.assertEqual(result.skill, "updated")
            self.assertEqual(
                (skill_root / "yunxiao-project" / "SKILL.md").read_text(),
                (source / "SKILL.md").read_text(),
            )

    def test_different_existing_skill_stops_without_overwrite(self) -> None:
        with tempfile.TemporaryDirectory(prefix="yunxiao-install-") as directory:
            home = Path(directory)
            target = home / ".agents" / "skills" / "yunxiao-project"
            target.mkdir(parents=True)
            foreign_skill = "---\nname: yunxiao-project\n---\nforeign source\n"
            (target / "SKILL.md").write_text(foreign_skill)
            config_path = home / ".codex" / "config.toml"

            with self.assertRaisesRegex(InstallationConflict, "personal skill"):
                install(SOURCE_SKILL, target.parent, config_path)

            self.assertEqual((target / "SKILL.md").read_text(), foreign_skill)
            self.assertFalse(config_path.exists())

    def test_conflicting_mcp_stops_without_changing_config_or_installing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="yunxiao-install-") as directory:
            home = Path(directory)
            skill_root = home / ".agents" / "skills"
            config_path = home / ".codex" / "config.toml"
            config_path.parent.mkdir(parents=True)
            original = (
                '[mcp_servers.yunxiao]\n'
                'url = "https://different.example/mcp"\n'
            )
            config_path.write_text(original)

            with self.assertRaisesRegex(InstallationConflict, "MCP"):
                install(SOURCE_SKILL, skill_root, config_path)

            self.assertEqual(config_path.read_text(), original)
            self.assertFalse((skill_root / "yunxiao-project").exists())

    def test_nested_static_auth_table_stops_without_changes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="yunxiao-install-") as directory:
            home = Path(directory)
            skill_root = home / ".agents" / "skills"
            config_path = home / ".codex" / "config.toml"
            config_path.parent.mkdir(parents=True)
            original = (
                '[mcp_servers.yunxiao]\n'
                f'url = "{HOSTED_ENDPOINT}"\n'
                '[mcp_servers.yunxiao.http_headers]\n'
                'X-Auth = "foreign-value"\n'
            )
            config_path.write_text(original)

            with self.assertRaisesRegex(InstallationConflict, "non-OAuth"):
                install(SOURCE_SKILL, skill_root, config_path)

            self.assertEqual(config_path.read_text(), original)
            self.assertFalse((skill_root / "yunxiao-project").exists())

    def test_equivalent_noncanonical_mcp_tables_stop_without_changes(self) -> None:
        table_headers = (
            "[mcp_servers . yunxiao]",
            '["mcp_servers"."yunxiao"]',
        )
        for table_header in table_headers:
            with self.subTest(table_header=table_header):
                with tempfile.TemporaryDirectory(prefix="yunxiao-install-") as directory:
                    home = Path(directory)
                    skill_root = home / ".agents" / "skills"
                    config_path = home / ".codex" / "config.toml"
                    config_path.parent.mkdir(parents=True)
                    original = (
                        f"{table_header}\n"
                        'url = "https://different.example/mcp"\n'
                    )
                    config_path.write_text(original)

                    with self.assertRaisesRegex(InstallationConflict, "unsupported"):
                        install(SOURCE_SKILL, skill_root, config_path)

                    self.assertEqual(config_path.read_text(), original)
                    self.assertFalse((skill_root / "yunxiao-project").exists())

    def test_inline_mcp_tables_stop_without_changes(self) -> None:
        configs = (
            (
                "[mcp_servers]\n"
                'yunxiao = { url = "https://different.example/mcp" }\n'
            ),
            (
                "mcp_servers = { yunxiao = { "
                'url = "https://different.example/mcp" } }\n'
            ),
        )
        for original in configs:
            with self.subTest(original=original):
                with tempfile.TemporaryDirectory(prefix="yunxiao-install-") as directory:
                    home = Path(directory)
                    skill_root = home / ".agents" / "skills"
                    config_path = home / ".codex" / "config.toml"
                    config_path.parent.mkdir(parents=True)
                    config_path.write_text(original)

                    with self.assertRaisesRegex(InstallationConflict, "unsupported"):
                        install(SOURCE_SKILL, skill_root, config_path)

                    self.assertEqual(config_path.read_text(), original)
                    self.assertFalse((skill_root / "yunxiao-project").exists())

    def test_noncanonical_tool_policy_table_stops_without_changes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="yunxiao-install-") as directory:
            home = Path(directory)
            skill_root = home / ".agents" / "skills"
            config_path = home / ".codex" / "config.toml"
            config_path.parent.mkdir(parents=True)
            original = (
                '[mcp_servers.yunxiao]\n'
                f'url = "{HOSTED_ENDPOINT}"\n'
                '[mcp_servers . yunxiao . tools . update_work_item]\n'
                'approval_mode = "approve"\n'
            )
            config_path.write_text(original)

            with self.assertRaisesRegex(InstallationConflict, "unsupported"):
                install(SOURCE_SKILL, skill_root, config_path)

            self.assertEqual(config_path.read_text(), original)
            self.assertFalse((skill_root / "yunxiao-project").exists())


if __name__ == "__main__":
    unittest.main()
