from pathlib import Path
from contextlib import redirect_stdout
from email import policy
from email.parser import BytesParser
import importlib.util
import io
import json
import os
import subprocess
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
MAILCTL = ROOT / ".agents" / "skills" / "email" / "scripts" / "mailctl"
MAILCTL_MODULE_PATH = MAILCTL.with_suffix(".py")


def run_mailctl(project: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(MAILCTL), *args],
        cwd=project,
        capture_output=True,
        text=True,
    )


def load_mailctl_module():
    spec = importlib.util.spec_from_file_location("mailctl_under_test", MAILCTL_MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MailctlCliTests(unittest.TestCase):
    def test_init_creates_project_local_state_and_config(self) -> None:
        with tempfile.TemporaryDirectory(prefix="mailctl-project-") as directory:
            project = Path(directory)

            result = run_mailctl(
                project,
                "init",
                "--email",
                "owner@example.com",
                "--display-name",
                "Owner",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["status"], "initialized")
            state = project / ".mailctl"
            self.assertTrue((state / "config.toml").is_file())
            self.assertTrue((state / "drafts").is_dir())
            self.assertTrue((state / "attachments").is_dir())
            self.assertTrue((state / "tmp").is_dir())
            config = (state / "config.toml").read_text()
            self.assertIn('address = "owner@example.com"', config)
            self.assertIn('imap_host = "imap.qiye.aliyun.com"', config)
            self.assertIn('smtp_host = "smtp.qiye.aliyun.com"', config)
            self.assertEqual(state.stat().st_mode & 0o777, 0o700)

    def test_init_refuses_tracked_mail_state(self) -> None:
        with tempfile.TemporaryDirectory(prefix="mailctl-project-") as directory:
            project = Path(directory)
            subprocess.run(["git", "init", "-q"], cwd=project, check=True)
            state = project / ".mailctl"
            state.mkdir()
            (state / "config.toml").write_text("tracked = true\n")
            subprocess.run(
                ["git", "add", "-f", ".mailctl/config.toml"],
                cwd=project,
                check=True,
            )

            result = run_mailctl(project, "init", "--email", "owner@example.com")

            self.assertEqual(result.returncode, 2)
            self.assertEqual(json.loads(result.stdout)["category"], "unsafe-project-state")
            self.assertEqual((state / "config.toml").read_text(), "tracked = true\n")

    def test_init_refuses_mail_state_symlink_outside_project(self) -> None:
        with (
            tempfile.TemporaryDirectory(prefix="mailctl-project-") as project_directory,
            tempfile.TemporaryDirectory(prefix="mailctl-outside-") as outside_directory,
        ):
            project = Path(project_directory)
            outside = Path(outside_directory)
            (project / ".mailctl").symlink_to(outside, target_is_directory=True)

            result = run_mailctl(project, "init", "--email", "owner@example.com")

            self.assertEqual(result.returncode, 2)
            self.assertEqual(
                json.loads(result.stdout)["category"], "unsafe-project-state"
            )
            self.assertEqual(list(outside.iterdir()), [])

    def test_auth_setup_uses_interactive_keychain_prompt(self) -> None:
        with tempfile.TemporaryDirectory(prefix="mailctl-project-") as directory:
            project = Path(directory)
            initialized = run_mailctl(project, "init", "--email", "owner@example.com")
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            module = load_mailctl_module()
            calls: list[list[str]] = []

            def fake_run(command, **kwargs):
                calls.append(command)
                if command[0] == "git":
                    return subprocess.CompletedProcess(command, 1, "", "")
                return subprocess.CompletedProcess(command, 0, "", "")

            previous = Path.cwd()
            output = io.StringIO()
            try:
                os.chdir(project)
                with mock.patch.object(module.subprocess, "run", side_effect=fake_run):
                    with redirect_stdout(output):
                        exit_code = module.main(["auth", "setup"])
            finally:
                os.chdir(previous)

            self.assertEqual(exit_code, 0, output.getvalue())
            security_call = next(call for call in calls if call[0] == "/usr/bin/security")
            self.assertEqual(
                security_call,
                [
                    "/usr/bin/security",
                    "add-generic-password",
                    "-a",
                    "owner@example.com",
                    "-s",
                    "mailctl:default",
                    "-U",
                    "-w",
                ],
            )

    def test_doctor_checks_imap_and_smtp_without_sending(self) -> None:
        with tempfile.TemporaryDirectory(prefix="mailctl-project-") as directory:
            project = Path(directory)
            initialized = run_mailctl(project, "init", "--email", "owner@example.com")
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            module = load_mailctl_module()
            events: list[tuple] = []

            class FakeImap:
                def __init__(self, host, port, **kwargs):
                    events.append(("imap-connect", host, port))

                def login(self, address, password):
                    events.append(("imap-login", address, password))
                    return "OK", []

                def capability(self):
                    return "OK", [b"IMAP4rev1 UIDPLUS"]

                def logout(self):
                    events.append(("imap-logout",))

            class FakeSmtp:
                def __init__(self, host, port, **kwargs):
                    events.append(("smtp-connect", host, port))

                def __enter__(self):
                    return self

                def __exit__(self, *args):
                    events.append(("smtp-close",))

                def login(self, address, password):
                    events.append(("smtp-login", address, password))

                def noop(self):
                    events.append(("smtp-noop",))
                    return 250, b"OK"

            def fake_run(command, **kwargs):
                if command[0] == "git":
                    return subprocess.CompletedProcess(command, 1, "", "")
                self.assertEqual(command[1], "find-generic-password")
                return subprocess.CompletedProcess(command, 0, "client-password\n", "")

            previous = Path.cwd()
            output = io.StringIO()
            try:
                os.chdir(project)
                with (
                    mock.patch.object(module.subprocess, "run", side_effect=fake_run),
                    mock.patch.object(module.imaplib, "IMAP4_SSL", FakeImap),
                    mock.patch.object(module.smtplib, "SMTP_SSL", FakeSmtp),
                    redirect_stdout(output),
                ):
                    exit_code = module.main(["doctor"])
            finally:
                os.chdir(previous)

            result = json.loads(output.getvalue())
            self.assertEqual(exit_code, 0, result)
            self.assertEqual(result["status"], "healthy")
            self.assertNotIn("client-password", output.getvalue())
            self.assertIn(("smtp-noop",), events)
            self.assertFalse(any(event[0] == "smtp-send" for event in events))

    def test_search_returns_stable_references_without_mutating_mailbox(self) -> None:
        with tempfile.TemporaryDirectory(prefix="mailctl-project-") as directory:
            project = Path(directory)
            initialized = run_mailctl(project, "init", "--email", "owner@example.com")
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            module = load_mailctl_module()
            observed: dict[str, object] = {}

            class FakeMailbox:
                folder = "INBOX"
                uidvalidity = 90210

                def __enter__(self):
                    return self

                def __exit__(self, *args):
                    return None

                def search(self, criteria):
                    observed["criteria"] = criteria
                    return [41]

                def summary(self, uid):
                    self.assert_uid = uid
                    return {
                        "uid": uid,
                        "message_id": "<weekly-41@example.com>",
                        "received_at": "2026-08-27T09:00:00+08:00",
                        "from": ["alice@example.com"],
                        "to": ["owner@example.com"],
                        "cc": [],
                        "subject": "Weekly update",
                        "snippet": "Status changed to ready.",
                        "has_attachments": False,
                    }

            previous = Path.cwd()
            output = io.StringIO()
            try:
                os.chdir(project)
                with (
                    mock.patch.object(module, "open_mailbox", return_value=FakeMailbox()),
                    redirect_stdout(output),
                ):
                    exit_code = module.main(
                        [
                            "search",
                            "--from",
                            "alice@example.com",
                            "--since",
                            "2026-08-26T00:00:00+08:00",
                        ]
                    )
            finally:
                os.chdir(previous)

            result = json.loads(output.getvalue())
            self.assertEqual(exit_code, 0, result)
            self.assertEqual(result["items"][0]["message_id"], "<weekly-41@example.com>")
            self.assertEqual(result["items"][0]["uid"], 41)
            self.assertTrue(result["items"][0]["message_ref"])
            self.assertEqual(result["next_cursor"], None)
            self.assertIn(("FROM", "alice@example.com"), observed["criteria"])
            self.assertIn(("SINCE", "2026-08-26T00:00:00+08:00"), observed["criteria"])

    def test_search_retries_connection_failure_twice(self) -> None:
        with tempfile.TemporaryDirectory(prefix="mailctl-project-") as directory:
            project = Path(directory)
            self.assertEqual(
                run_mailctl(project, "init", "--email", "owner@example.com").returncode,
                0,
            )
            module = load_mailctl_module()
            attempts = 0

            class EmptyMailbox:
                folder = "INBOX"
                uidvalidity = 1

                def __enter__(self):
                    return self

                def __exit__(self, *args):
                    return None

                def search(self, criteria):
                    return []

            def flaky_open(project, folder):
                nonlocal attempts
                attempts += 1
                if attempts < 3:
                    raise module.MailctlError("connection", "temporary failure")
                return EmptyMailbox()

            previous = Path.cwd()
            output = io.StringIO()
            try:
                os.chdir(project)
                with mock.patch.object(module, "open_mailbox", side_effect=flaky_open), redirect_stdout(output):
                    exit_code = module.main(["search"])
            finally:
                os.chdir(previous)

            self.assertEqual(exit_code, 0, output.getvalue())
            self.assertEqual(attempts, 3)

    def test_search_applies_exact_time_window_after_imap_date_search(self) -> None:
        with tempfile.TemporaryDirectory(prefix="mailctl-project-") as directory:
            project = Path(directory)
            self.assertEqual(
                run_mailctl(project, "init", "--email", "owner@example.com").returncode,
                0,
            )
            module = load_mailctl_module()

            class FakeMailbox:
                folder = "INBOX"
                uidvalidity = 1

                def __enter__(self):
                    return self

                def __exit__(self, *args):
                    return None

                def search(self, criteria):
                    return [1]

                def summary(self, uid):
                    return {
                        "uid": uid,
                        "message_id": "<old@example.com>",
                        "received_at": "2026-08-26T23:59:59+08:00",
                        "from": ["alice@example.com"],
                        "to": ["owner@example.com"],
                        "cc": [],
                        "subject": "Old",
                        "snippet": "Old",
                        "has_attachments": False,
                    }

            previous = Path.cwd()
            output = io.StringIO()
            try:
                os.chdir(project)
                with mock.patch.object(module, "open_mailbox", return_value=FakeMailbox()), redirect_stdout(output):
                    exit_code = module.main(
                        ["search", "--since", "2026-08-27T00:00:00+08:00"]
                    )
            finally:
                os.chdir(previous)

            result = json.loads(output.getvalue())
            self.assertEqual(exit_code, 0, result)
            self.assertEqual(result["items"], [])

    def test_search_post_filters_imap_address_matches_to_exact_address(self) -> None:
        with tempfile.TemporaryDirectory(prefix="mailctl-project-") as directory:
            project = Path(directory)
            self.assertEqual(
                run_mailctl(project, "init", "--email", "owner@example.com").returncode,
                0,
            )
            module = load_mailctl_module()

            class FakeMailbox:
                folder = "INBOX"
                uidvalidity = 1

                def __enter__(self):
                    return self

                def __exit__(self, *args):
                    return None

                def search(self, criteria):
                    return [2, 1]

                def summary(self, uid):
                    return {
                        "uid": uid,
                        "message_id": f"<{uid}@example.com>",
                        "received_at": "2026-08-27T09:00:00+08:00",
                        "from": [
                            "alice@example.com"
                            if uid == 1
                            else "not-alice@example.com"
                        ],
                        "to": ["owner@example.com"],
                        "cc": [],
                        "subject": "Update",
                        "snippet": "Status",
                        "has_attachments": False,
                    }

            previous = Path.cwd()
            output = io.StringIO()
            try:
                os.chdir(project)
                with (
                    mock.patch.object(module, "open_mailbox", return_value=FakeMailbox()),
                    redirect_stdout(output),
                ):
                    exit_code = module.main(
                        ["search", "--from", "alice@example.com"]
                    )
            finally:
                os.chdir(previous)

            result = json.loads(output.getvalue())
            self.assertEqual(exit_code, 0, result)
            self.assertEqual([item["uid"] for item in result["items"]], [1])

    def test_get_normalizes_body_and_lists_attachments_without_remote_loading(self) -> None:
        with tempfile.TemporaryDirectory(prefix="mailctl-project-") as directory:
            project = Path(directory)
            initialized = run_mailctl(project, "init", "--email", "owner@example.com")
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            module = load_mailctl_module()
            reference = module.encode_token(
                {
                    "folder": "INBOX",
                    "uidvalidity": 77,
                    "uid": 9,
                    "message_id": "<message-9@example.com>",
                }
            )
            raw_message = (
                b"From: Alice <alice@example.com>\r\n"
                b"To: owner@example.com\r\n"
                b"Subject: Update\r\n"
                b"Message-ID: <message-9@example.com>\r\n"
                b"MIME-Version: 1.0\r\n"
                b"Content-Type: multipart/mixed; boundary=outer\r\n\r\n"
                b"--outer\r\nContent-Type: multipart/alternative; boundary=inner\r\n\r\n"
                b"--inner\r\nContent-Type: text/plain; charset=utf-8\r\n\r\n"
                b"Current status is ready.\r\n> old quoted text\r\n"
                b"--inner\r\nContent-Type: text/html; charset=utf-8\r\n\r\n"
                b"<p>Current status is <strong>ready</strong>.</p>"
                b"<img src=\"https://tracker.example/pixel\">\r\n"
                b"--inner--\r\n"
                b"--outer\r\nContent-Type: application/pdf\r\n"
                b"Content-Disposition: attachment; filename=report.pdf\r\n\r\n"
                b"PDFDATA\r\n--outer--\r\n"
            )

            class FakeMailbox:
                folder = "INBOX"
                uidvalidity = 77

                def __enter__(self):
                    return self

                def __exit__(self, *args):
                    return None

                def fetch(self, uid):
                    self.requested_uid = uid
                    return raw_message

            previous = Path.cwd()
            output = io.StringIO()
            try:
                os.chdir(project)
                with (
                    mock.patch.object(module, "open_mailbox", return_value=FakeMailbox()),
                    redirect_stdout(output),
                ):
                    exit_code = module.main(
                        ["get", "--message-ref", reference, "--include-html"]
                    )
            finally:
                os.chdir(previous)

            result = json.loads(output.getvalue())
            self.assertEqual(exit_code, 0, result)
            self.assertEqual(result["message_id"], "<message-9@example.com>")
            self.assertEqual(result["text"], "Current status is ready.")
            self.assertTrue(result["quoted_history_collapsed"])
            self.assertNotIn("tracker.example", result["html"])
            self.assertEqual(result["attachments"][0]["filename"], "report.pdf")
            self.assertEqual(result["attachments"][0]["content_type"], "application/pdf")

    def test_attachment_get_saves_allowed_file_inside_project(self) -> None:
        with tempfile.TemporaryDirectory(prefix="mailctl-project-") as directory:
            project = Path(directory)
            initialized = run_mailctl(project, "init", "--email", "owner@example.com")
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            module = load_mailctl_module()
            reference = module.encode_token(
                {
                    "folder": "INBOX",
                    "uidvalidity": 77,
                    "uid": 9,
                    "message_id": "<message-9@example.com>",
                }
            )
            raw_message = (
                b"Message-ID: <message-9@example.com>\r\n"
                b"MIME-Version: 1.0\r\n"
                b"Content-Type: multipart/mixed; boundary=outer\r\n\r\n"
                b"--outer\r\nContent-Type: text/plain\r\n\r\nBody\r\n"
                b"--outer\r\nContent-Type: application/pdf\r\n"
                b'Content-Disposition: attachment; filename="../../report.pdf"\r\n\r\n'
                b"PDFDATA\r\n--outer--\r\n"
            )

            class FakeMailbox:
                uidvalidity = 77

                def __enter__(self):
                    return self

                def __exit__(self, *args):
                    return None

                def fetch(self, uid):
                    return raw_message

            previous = Path.cwd()
            output = io.StringIO()
            try:
                os.chdir(project)
                with (
                    mock.patch.object(module, "open_mailbox", return_value=FakeMailbox()),
                    redirect_stdout(output),
                ):
                    exit_code = module.main(
                        [
                            "attachment",
                            "get",
                            "--message-ref",
                            reference,
                            "--part-id",
                            "2",
                        ]
                    )
            finally:
                os.chdir(previous)

            result = json.loads(output.getvalue())
            self.assertEqual(exit_code, 0, result)
            saved = Path(result["path"])
            self.assertEqual(saved.parent.resolve(), (project / ".mailctl" / "attachments").resolve())
            self.assertEqual(saved.name, "report.pdf")
            self.assertEqual(saved.read_bytes(), b"PDFDATA")

    def test_prepare_creates_immutable_html_and_plain_text_draft(self) -> None:
        with tempfile.TemporaryDirectory(prefix="mailctl-project-") as directory:
            project = Path(directory)
            initialized = run_mailctl(
                project,
                "init",
                "--email",
                "owner@example.com",
                "--display-name",
                "Owner",
            )
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            manifest = project / "weekly.md"
            manifest.write_text(
                "---\n"
                "account: default\n"
                "to:\n"
                "  - alice@example.com\n"
                "cc:\n"
                "  - boss@example.com\n"
                "subject: Weekly report\n"
                "reply_to: null\n"
                "---\n\n"
                "# Weekly Report\n\n"
                "**Status:** Ready\n\n"
                "| Item | State |\n"
                "| --- | --- |\n"
                "| Mail skill | Ready |\n\n"
                "<script>alert('unsafe')</script>\n"
            )

            result = run_mailctl(project, "prepare", "--file", str(manifest))

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "prepared")
            draft_dir = project / ".mailctl" / "drafts" / payload["draft_id"]
            eml = draft_dir / "message.eml"
            preview = draft_dir / "preview.html"
            state = json.loads((draft_dir / "state.json").read_text())
            self.assertTrue(eml.is_file())
            self.assertTrue(preview.is_file())
            self.assertEqual(state["status"], "pending")
            message = BytesParser(policy=policy.default).parsebytes(eml.read_bytes())
            self.assertEqual(message["From"].addresses[0].addr_spec, "owner@example.com")
            self.assertEqual(message["To"].addresses[0].addr_spec, "alice@example.com")
            self.assertEqual(message["Cc"].addresses[0].addr_spec, "boss@example.com")
            plain = message.get_body(preferencelist=("plain",)).get_content()
            html = message.get_body(preferencelist=("html",)).get_content()
            self.assertIn("Weekly Report", plain)
            self.assertIn("<h1", html)
            self.assertIn("<table", html)
            self.assertNotIn("<script", html)
            self.assertIn("&lt;script&gt;", html)

            shown = run_mailctl(project, "draft", "show", "--draft-id", payload["draft_id"])
            self.assertEqual(shown.returncode, 0, shown.stderr)
            shown_payload = json.loads(shown.stdout)
            self.assertEqual(shown_payload["status"], "pending")
            self.assertEqual(shown_payload["subject"], "Weekly report")
            self.assertIn("<table", shown_payload["html"])

            eml.write_bytes(eml.read_bytes() + b"tampered")
            rejected = run_mailctl(project, "draft", "show", "--draft-id", payload["draft_id"])
            self.assertEqual(rejected.returncode, 2)
            self.assertEqual(json.loads(rejected.stdout)["category"], "draft-integrity")

    def test_prepare_refuses_manifest_outside_calling_project(self) -> None:
        with (
            tempfile.TemporaryDirectory(prefix="mailctl-project-") as project_directory,
            tempfile.TemporaryDirectory(prefix="mailctl-outside-") as outside_directory,
        ):
            project = Path(project_directory)
            self.assertEqual(
                run_mailctl(project, "init", "--email", "owner@example.com").returncode,
                0,
            )
            manifest = Path(outside_directory) / "message.md"
            manifest.write_text(
                "---\naccount: default\nto:\n  - alice@example.com\ncc: []\n"
                "subject: Outside\nreply_to: null\n---\n\nNo.\n"
            )

            result = run_mailctl(project, "prepare", "--file", str(manifest))

            self.assertEqual(result.returncode, 2)
            self.assertEqual(json.loads(result.stdout)["category"], "permission")
            self.assertEqual(list((project / ".mailctl" / "drafts").iterdir()), [])

    def test_send_consumes_prepared_draft_once(self) -> None:
        with tempfile.TemporaryDirectory(prefix="mailctl-project-") as directory:
            project = Path(directory)
            self.assertEqual(
                run_mailctl(project, "init", "--email", "owner@example.com").returncode,
                0,
            )
            manifest = project / "message.md"
            manifest.write_text(
                "---\naccount: default\nto:\n  - alice@example.com\ncc: []\n"
                "subject: Status update\nreply_to: null\n---\n\nReady.\n"
            )
            prepared = json.loads(run_mailctl(project, "prepare", "--file", str(manifest)).stdout)
            module = load_mailctl_module()
            events: list[tuple] = []

            class FakeSmtp:
                def __init__(self, host, port, **kwargs):
                    events.append(("connect", host, port))

                def __enter__(self):
                    return self

                def __exit__(self, *args):
                    return None

                def login(self, address, password):
                    events.append(("login", address, password))

                def send_message(self, message):
                    events.append(("send", str(message["Message-ID"])))
                    return {}

            def fake_run(command, **kwargs):
                if command[0] == "git":
                    return subprocess.CompletedProcess(command, 1, "", "")
                return subprocess.CompletedProcess(command, 0, "client-password\n", "")

            previous = Path.cwd()
            first_output = io.StringIO()
            second_output = io.StringIO()
            try:
                os.chdir(project)
                with (
                    mock.patch.object(module.subprocess, "run", side_effect=fake_run),
                    mock.patch.object(module.smtplib, "SMTP_SSL", FakeSmtp),
                    redirect_stdout(first_output),
                ):
                    first_exit = module.main(["send", "--draft-id", prepared["draft_id"]])
                with (
                    mock.patch.object(module.subprocess, "run", side_effect=fake_run),
                    mock.patch.object(module.smtplib, "SMTP_SSL", FakeSmtp),
                    redirect_stdout(second_output),
                ):
                    second_exit = module.main(["send", "--draft-id", prepared["draft_id"]])
            finally:
                os.chdir(previous)

            self.assertEqual(first_exit, 0, first_output.getvalue())
            self.assertEqual(json.loads(first_output.getvalue())["status"], "consumed")
            self.assertEqual(second_exit, 2)
            self.assertEqual(json.loads(second_output.getvalue())["category"], "draft-locked")
            self.assertEqual(sum(event[0] == "send" for event in events), 1)

    def test_send_timeout_locks_draft_as_uncertain_without_retry(self) -> None:
        with tempfile.TemporaryDirectory(prefix="mailctl-project-") as directory:
            project = Path(directory)
            self.assertEqual(
                run_mailctl(project, "init", "--email", "owner@example.com").returncode,
                0,
            )
            manifest = project / "message.md"
            manifest.write_text(
                "---\naccount: default\nto:\n  - alice@example.com\ncc: []\n"
                "subject: Status update\nreply_to: null\n---\n\nReady.\n"
            )
            prepared = json.loads(run_mailctl(project, "prepare", "--file", str(manifest)).stdout)
            module = load_mailctl_module()
            attempts = 0

            class TimeoutSmtp:
                def __init__(self, host, port, **kwargs):
                    pass

                def __enter__(self):
                    return self

                def __exit__(self, *args):
                    return None

                def login(self, address, password):
                    pass

                def send_message(self, message):
                    nonlocal attempts
                    attempts += 1
                    raise TimeoutError("response lost")

            def fake_run(command, **kwargs):
                if command[0] == "git":
                    return subprocess.CompletedProcess(command, 1, "", "")
                return subprocess.CompletedProcess(command, 0, "client-password\n", "")

            previous = Path.cwd()
            output = io.StringIO()
            try:
                os.chdir(project)
                with (
                    mock.patch.object(module.subprocess, "run", side_effect=fake_run),
                    mock.patch.object(module.smtplib, "SMTP_SSL", TimeoutSmtp),
                    redirect_stdout(output),
                ):
                    exit_code = module.main(["send", "--draft-id", prepared["draft_id"]])
            finally:
                os.chdir(previous)

            self.assertEqual(exit_code, 2)
            self.assertEqual(json.loads(output.getvalue())["category"], "uncertain-send")
            state_path = project / ".mailctl" / "drafts" / prepared["draft_id"] / "state.json"
            self.assertEqual(json.loads(state_path.read_text())["status"], "uncertain")
            self.assertEqual(attempts, 1)

    def test_prepare_reply_all_preserves_thread_and_excludes_own_address(self) -> None:
        with tempfile.TemporaryDirectory(prefix="mailctl-project-") as directory:
            project = Path(directory)
            self.assertEqual(
                run_mailctl(project, "init", "--email", "owner@example.com").returncode,
                0,
            )
            module = load_mailctl_module()
            reference = module.encode_token(
                {
                    "folder": "INBOX",
                    "uidvalidity": 88,
                    "uid": 12,
                    "message_id": "<original@example.com>",
                }
            )
            manifest = project / "reply.md"
            manifest.write_text(
                "---\naccount: default\nto: []\ncc: []\nsubject: Re: Update\n"
                f"reply_to: {reference}\nreply_mode: reply-all\n---\n\nThanks.\n"
            )
            original = (
                b"From: Alice <alice@example.com>\r\n"
                b"To: owner@example.com, bob@example.com\r\n"
                b"Cc: carol@example.com\r\n"
                b"Subject: Update\r\n"
                b"Message-ID: <original@example.com>\r\n"
                b"References: <older@example.com>\r\n\r\nBody\r\n"
            )

            class FakeMailbox:
                uidvalidity = 88

                def __enter__(self):
                    return self

                def __exit__(self, *args):
                    return None

                def fetch(self, uid):
                    return original

            previous = Path.cwd()
            output = io.StringIO()
            try:
                os.chdir(project)
                with (
                    mock.patch.object(module, "open_mailbox", return_value=FakeMailbox()),
                    redirect_stdout(output),
                ):
                    exit_code = module.main(["prepare", "--file", str(manifest)])
            finally:
                os.chdir(previous)

            payload = json.loads(output.getvalue())
            self.assertEqual(exit_code, 0, payload)
            raw = (
                project
                / ".mailctl"
                / "drafts"
                / payload["draft_id"]
                / "message.eml"
            ).read_bytes()
            message = BytesParser(policy=policy.default).parsebytes(raw)
            self.assertEqual(
                [address.addr_spec for address in message["To"].addresses],
                ["alice@example.com", "bob@example.com"],
            )
            self.assertEqual(
                [address.addr_spec for address in message["Cc"].addresses],
                ["carol@example.com"],
            )
            self.assertEqual(str(message["In-Reply-To"]), "<original@example.com>")
            self.assertEqual(
                str(message["References"]),
                "<older@example.com> <original@example.com>",
            )

    def test_prepare_prunes_drafts_older_than_thirty_days(self) -> None:
        with tempfile.TemporaryDirectory(prefix="mailctl-project-") as directory:
            project = Path(directory)
            self.assertEqual(
                run_mailctl(project, "init", "--email", "owner@example.com").returncode,
                0,
            )
            manifest = project / "message.md"
            manifest.write_text(
                "---\naccount: default\nto:\n  - alice@example.com\ncc: []\n"
                "subject: First\nreply_to: null\n---\n\nReady.\n"
            )
            first = json.loads(run_mailctl(project, "prepare", "--file", str(manifest)).stdout)
            old_dir = project / ".mailctl" / "drafts" / first["draft_id"]
            state_path = old_dir / "state.json"
            state = json.loads(state_path.read_text())
            state["created_at"] = "2026-01-01T00:00:00+00:00"
            state_path.write_text(json.dumps(state))
            manifest.write_text(manifest.read_text().replace("subject: First", "subject: Second"))

            second = run_mailctl(project, "prepare", "--file", str(manifest))

            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertFalse(old_dir.exists())


if __name__ == "__main__":
    unittest.main()
