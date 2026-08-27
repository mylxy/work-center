from __future__ import annotations

from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest

from scripts.validate_yunxiao_install import (
    ValidationFailure,
    run_live_validation,
    scan_credential_files,
)


def fake_codex(directory: Path, final: dict | None, event_tools=(), error="") -> Path:
    executable = directory / "codex"
    payload = json.dumps(final, ensure_ascii=False) if final is not None else ""
    events = "\n".join(
        json.dumps({"type": "mcp_tool_call", "tool": tool})
        for tool in event_tools
    )
    source = f'''#!/usr/bin/env python3
import pathlib
import sys

args = sys.argv[1:]
if {bool(final)!r}:
    output = pathlib.Path(args[args.index("--output-last-message") + 1])
    output.write_text({payload!r})
if {events!r}:
    print({events!r})
if {error!r}:
    print({error!r}, file=sys.stderr)
    raise SystemExit(1)
'''
    executable.write_text(source)
    executable.chmod(0o755)
    return executable


class YunxiaoLiveValidationTests(unittest.TestCase):
    def test_validation_script_can_run_as_a_file(self) -> None:
        completed = subprocess.run(
            [sys.executable, "scripts/validate_yunxiao_install.py", "--help"],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("read-only live MCP calls", completed.stdout)

    def test_credential_scan_reports_only_file_paths(self) -> None:
        with tempfile.TemporaryDirectory(prefix="yunxiao-scan-") as directory:
            workspace = Path(directory)
            credential_file = workspace / "unsafe.log"
            credential_file.write_text(
                "oauth_" + "token: " + "not-a-real-secret-value\n"
            )

            matches = scan_credential_files(workspace)

            self.assertEqual(matches, (Path("unsafe.log"),))

    def test_read_only_validation_reports_identity_organization_and_project(self) -> None:
        with tempfile.TemporaryDirectory(prefix="yunxiao-live-") as directory:
            workspace = Path(directory)
            final = {
                "identity": "受控用户",
                "organization": "受控组织",
                "resource_kind": "project",
                "resource": "受控项目",
                "tools_used": [
                    "get_current_user",
                    "get_current_organization_info",
                    "search_projects",
                ],
                "diagnostic": None,
            }
            binary = fake_codex(
                workspace,
                final,
                event_tools=(
                    "get_current_user",
                    "get_current_organization_info",
                    "search_projects",
                ),
            )

            result = run_live_validation(binary, workspace)

            self.assertEqual(result.identity, "受控用户")
            self.assertEqual(result.organization, "受控组织")
            self.assertEqual(result.resource_kind, "project")
            self.assertEqual(result.resource, "受控项目")

    def test_oauth_failure_has_actionable_login_guidance(self) -> None:
        with tempfile.TemporaryDirectory(prefix="yunxiao-live-") as directory:
            workspace = Path(directory)
            binary = fake_codex(
                workspace,
                None,
                error="UNAUTHENTICATED: OAuth session missing",
            )

            with self.assertRaisesRegex(
                ValidationFailure,
                "codex mcp login yunxiao",
            ):
                run_live_validation(binary, workspace)

    def test_read_only_validation_rejects_any_write_tool_attempt(self) -> None:
        with tempfile.TemporaryDirectory(prefix="yunxiao-live-") as directory:
            workspace = Path(directory)
            final = {
                "identity": "受控用户",
                "organization": "受控组织",
                "resource_kind": "project",
                "resource": "受控项目",
                "tools_used": ["create_work_item_comment"],
                "diagnostic": None,
            }
            binary = fake_codex(
                workspace,
                final,
                event_tools=("create_work_item_comment",),
            )

            with self.assertRaisesRegex(ValidationFailure, "写工具"):
                run_live_validation(binary, workspace)


if __name__ == "__main__":
    unittest.main()
