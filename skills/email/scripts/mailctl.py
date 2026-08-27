#!/usr/bin/env python3
"""Project-scoped Alibaba Mail CLI used by the email skill."""

from __future__ import annotations

import argparse
import base64
from datetime import datetime, timedelta, timezone
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.headerregistry import Address
from email.utils import format_datetime, formataddr, getaddresses, make_msgid, parsedate_to_datetime
import hashlib
from html import escape
from html.parser import HTMLParser
import imaplib
import json
import os
from pathlib import Path
import re
import shutil
import smtplib
import ssl
import subprocess
import sys
import tomllib
from typing import Any


STATE_DIR_NAME = ".mailctl"
MAX_BODY_BYTES = 5 * 1024 * 1024
MAX_ATTACHMENT_BYTES = 20 * 1024 * 1024


class MailctlError(Exception):
    def __init__(self, category: str, message: str) -> None:
        super().__init__(message)
        self.category = category


def emit(payload: dict[str, object]) -> None:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def validate_email(value: str) -> str:
    try:
        parsed = Address(addr_spec=value)
    except (TypeError, ValueError) as error:
        raise MailctlError("invalid-input", f"invalid email address: {value}") from error
    if not parsed.domain or not parsed.username:
        raise MailctlError("invalid-input", f"invalid email address: {value}")
    return parsed.addr_spec


def toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def ensure_state_is_untracked(project: Path) -> None:
    state = project / STATE_DIR_NAME
    if state.is_symlink() or (state.exists() and not state.is_dir()):
        raise MailctlError(
            "unsafe-project-state",
            ".mailctl must be a real directory inside the Calling Project",
        )
    for name in ("config.toml", ".gitignore", "drafts", "attachments", "tmp"):
        if (state / name).is_symlink():
            raise MailctlError(
                "unsafe-project-state",
                f".mailctl/{name} must not be a symbolic link",
            )
    inside = subprocess.run(
        ["git", "-C", str(project), "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        text=True,
    )
    if inside.returncode != 0:
        return
    tracked = subprocess.run(
        ["git", "-C", str(project), "ls-files", "--", STATE_DIR_NAME],
        check=True,
        capture_output=True,
        text=True,
    )
    if tracked.stdout.strip():
        raise MailctlError(
            "unsafe-project-state",
            ".mailctl contains Git-tracked files; remove them from the index before using mailctl",
        )


def command_init(args: argparse.Namespace) -> dict[str, object]:
    address = validate_email(args.email)
    project = Path.cwd()
    ensure_state_is_untracked(project)
    state = project / STATE_DIR_NAME
    state.mkdir(mode=0o700, exist_ok=True)
    os.chmod(state, 0o700)
    for name in ("drafts", "attachments", "tmp"):
        child = state / name
        child.mkdir(mode=0o700, exist_ok=True)
        os.chmod(child, 0o700)
    (state / ".gitignore").write_text("*\n")
    config = "\n".join(
        (
            "[account.default]",
            f"address = {toml_string(address)}",
            f"display_name = {toml_string(args.display_name or '')}",
            'imap_host = "imap.qiye.aliyun.com"',
            "imap_port = 993",
            'smtp_host = "smtp.qiye.aliyun.com"',
            "smtp_port = 465",
            "",
        )
    )
    config_path = state / "config.toml"
    config_path.write_text(config)
    os.chmod(state / ".gitignore", 0o600)
    os.chmod(config_path, 0o600)
    return {"status": "initialized", "project": str(project), "state_dir": str(state)}


def load_default_account(project: Path) -> dict[str, object]:
    config_path = project / STATE_DIR_NAME / "config.toml"
    try:
        config = tomllib.loads(config_path.read_text())
        account = config["account"]["default"]
    except (OSError, KeyError, TypeError, tomllib.TOMLDecodeError) as error:
        raise MailctlError(
            "configuration",
            "missing or invalid .mailctl/config.toml; run mailctl init in this directory",
        ) from error
    if not isinstance(account, dict):
        raise MailctlError("configuration", "account.default must be a table")
    return account


def command_auth_setup(args: argparse.Namespace) -> dict[str, object]:
    project = Path.cwd()
    ensure_state_is_untracked(project)
    account = load_default_account(project)
    address = str(account.get("address", ""))
    validate_email(address)
    command = [
        "/usr/bin/security",
        "add-generic-password",
        "-a",
        address,
        "-s",
        "mailctl:default",
        "-U",
        "-w",
    ]
    completed = subprocess.run(command)
    if completed.returncode != 0:
        raise MailctlError("authentication", "Keychain did not store the mail credential")
    return {"status": "credential-stored", "account": "default", "address": address}


def read_keychain_password(address: str) -> str:
    command = [
        "/usr/bin/security",
        "find-generic-password",
        "-a",
        address,
        "-s",
        "mailctl:default",
        "-w",
    ]
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode != 0 or not completed.stdout.rstrip("\n"):
        raise MailctlError(
            "authentication",
            "mail credential is unavailable; unlock Keychain or run mailctl auth setup",
        )
    return completed.stdout.rstrip("\n")


def command_doctor(args: argparse.Namespace) -> dict[str, object]:
    project = Path.cwd()
    ensure_state_is_untracked(project)
    account = load_default_account(project)
    address = validate_email(str(account.get("address", "")))
    password = read_keychain_password(address)
    context = ssl.create_default_context()
    try:
        imap = imaplib.IMAP4_SSL(
            str(account["imap_host"]),
            int(account["imap_port"]),
            ssl_context=context,
            timeout=30,
        )
        try:
            imap.login(address, password)
        except imaplib.IMAP4.error as error:
            raise MailctlError("authentication", "IMAP authentication failed") from error
        _, capabilities = imap.capability()
        imap.logout()
        with smtplib.SMTP_SSL(
            str(account["smtp_host"]),
            int(account["smtp_port"]),
            context=context,
            timeout=30,
        ) as smtp:
            try:
                smtp.login(address, password)
            except smtplib.SMTPAuthenticationError as error:
                raise MailctlError("authentication", "SMTP authentication failed") from error
            code, _ = smtp.noop()
            if code != 250:
                raise MailctlError("capability", f"SMTP NOOP returned {code}")
    except MailctlError:
        raise
    except (KeyError, OSError, imaplib.IMAP4.error, smtplib.SMTPException) as error:
        raise MailctlError("connection", f"mail connectivity check failed: {error}") from error
    return {
        "status": "healthy",
        "account": "default",
        "address": address,
        "imap_capabilities": [
            item.decode("ascii", "replace") if isinstance(item, bytes) else str(item)
            for item in capabilities
        ],
        "smtp": "available",
    }


def encode_token(payload: dict[str, object]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def decode_token(value: str, category: str) -> dict[str, Any]:
    try:
        padded = value + "=" * (-len(value) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode())
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise MailctlError("invalid-input", f"invalid {category}") from error
    if not isinstance(payload, dict):
        raise MailctlError("invalid-input", f"invalid {category}")
    return payload


def parse_timestamp(value: str, label: str) -> datetime:
    try:
        timestamp = datetime.fromisoformat(value)
    except ValueError as error:
        raise MailctlError("invalid-input", f"{label} must be an ISO 8601 timestamp") from error
    if timestamp.tzinfo is None:
        raise MailctlError("invalid-input", f"{label} must include a timezone")
    return timestamp


class ImapMailbox:
    def __init__(self, project: Path, folder: str) -> None:
        account = load_default_account(project)
        self.address = validate_email(str(account.get("address", "")))
        password = read_keychain_password(self.address)
        context = ssl.create_default_context()
        try:
            self.client = imaplib.IMAP4_SSL(
                str(account["imap_host"]),
                int(account["imap_port"]),
                ssl_context=context,
                timeout=30,
            )
            try:
                self.client.login(self.address, password)
            except imaplib.IMAP4.error as error:
                raise MailctlError("authentication", "IMAP authentication failed") from error
            status, _ = self.client.select(folder, readonly=True)
            if status != "OK":
                raise MailctlError("permission", f"cannot read mailbox folder {folder}")
            _, validity = self.client.response("UIDVALIDITY")
            self.uidvalidity = int(validity[0]) if validity else 0
        except MailctlError:
            raise
        except (KeyError, OSError, ValueError, imaplib.IMAP4.error) as error:
            raise MailctlError("connection", f"IMAP connection failed: {error}") from error
        self.folder = folder

    def __enter__(self) -> "ImapMailbox":
        return self

    def __exit__(self, *args: object) -> None:
        try:
            self.client.logout()
        except (OSError, imaplib.IMAP4.error):
            pass

    def search(self, criteria: list[tuple[str, object]]) -> list[int]:
        tokens: list[str] = []
        for key, value in criteria:
            if key in {"FROM", "TO", "SUBJECT"}:
                tokens.extend((key, f'"{value}"'))
            elif key == "MESSAGE_ID":
                tokens.extend(("HEADER", "Message-ID", f'"{value}"'))
            elif key in {"SINCE", "BEFORE"}:
                timestamp = parse_timestamp(str(value), key.lower())
                tokens.extend((key, timestamp.strftime("%d-%b-%Y")))
        if not tokens:
            tokens.append("ALL")
        status, data = self.client.uid("SEARCH", None, *tokens)
        if status != "OK":
            raise MailctlError("connection", "IMAP search failed")
        return [int(value) for value in (data[0] or b"").split()]

    def summary(self, uid: int) -> dict[str, object]:
        status, data = self.client.uid(
            "FETCH",
            str(uid),
            "(INTERNALDATE BODYSTRUCTURE BODY.PEEK[HEADER] BODY.PEEK[TEXT]<0.1024>)",
        )
        if status != "OK":
            raise MailctlError("connection", f"IMAP fetch failed for UID {uid}")
        chunks = [item[1] for item in data if isinstance(item, tuple) and len(item) == 2]
        if not chunks:
            raise MailctlError("connection", f"IMAP returned no message for UID {uid}")
        header_bytes = chunks[0]
        text_bytes = chunks[1] if len(chunks) > 1 else b""
        message = BytesParser(policy=policy.default).parsebytes(header_bytes)
        metadata = b" ".join(
            item[0] for item in data if isinstance(item, tuple) and len(item) == 2
        ).decode("ascii", "replace")
        internal_date = re.search(r'INTERNALDATE "([^"]+)"', metadata)
        try:
            received = (
                datetime.strptime(internal_date.group(1), "%d-%b-%Y %H:%M:%S %z").isoformat()
                if internal_date
                else parsedate_to_datetime(str(message.get("Date", ""))).isoformat()
            )
        except (TypeError, ValueError):
            received = ""
        addresses = lambda name: [addr for _, addr in getaddresses(message.get_all(name, [])) if addr]
        bodystructure_has_attachment = bool(
            re.search(
                r'(?i)"ATTACHMENT"\s+(?:\(|NIL)|"FILENAME"\s',
                metadata,
            )
        )
        return {
            "uid": uid,
            "message_id": str(message.get("Message-ID", "")),
            "received_at": received,
            "from": addresses("From"),
            "to": addresses("To"),
            "cc": addresses("Cc"),
            "subject": str(message.get("Subject", "")),
            "snippet": text_bytes.decode("utf-8", "replace").strip()[:1024],
            "has_attachments": bodystructure_has_attachment,
        }

    def fetch(self, uid: int) -> bytes:
        status, data = self.client.uid("FETCH", str(uid), "(BODY.PEEK[])")
        if status != "OK":
            raise MailctlError("connection", f"IMAP fetch failed for UID {uid}")
        chunks = [item[1] for item in data if isinstance(item, tuple) and len(item) == 2]
        if not chunks:
            raise MailctlError("connection", f"IMAP returned no message for UID {uid}")
        return b"".join(chunks)


def open_mailbox(project: Path, folder: str) -> ImapMailbox:
    return ImapMailbox(project, folder)


def retry_read(operation):
    for attempt in range(3):
        try:
            return operation()
        except MailctlError as error:
            if error.category != "connection" or attempt == 2:
                raise
    raise AssertionError("unreachable")


def command_search(args: argparse.Namespace) -> dict[str, object]:
    project = Path.cwd()
    ensure_state_is_untracked(project)
    if not 1 <= args.limit <= 200:
        raise MailctlError("invalid-input", "limit must be between 1 and 200")
    criteria: list[tuple[str, object]] = []
    from_address = validate_email(args.from_address) if args.from_address else None
    to_address = validate_email(args.to_address) if args.to_address else None
    if from_address:
        criteria.append(("FROM", from_address))
    if to_address:
        criteria.append(("TO", to_address))
    since_time = parse_timestamp(args.since, "since") if args.since else None
    before_time = parse_timestamp(args.before, "before") if args.before else None
    if since_time:
        criteria.append(("SINCE", args.since))
    if before_time:
        criteria.append(("BEFORE", args.before))
    if args.subject:
        criteria.append(("SUBJECT", args.subject))
    if args.message_id:
        criteria.append(("MESSAGE_ID", args.message_id))

    before_uid: int | None = None
    if args.cursor:
        cursor = decode_token(args.cursor, "cursor")
        try:
            before_uid = int(cursor["before_uid"])
        except (KeyError, TypeError, ValueError) as error:
            raise MailctlError("invalid-input", "invalid cursor") from error

    def perform() -> dict[str, object]:
        with open_mailbox(project, args.folder) as mailbox:
            uids = sorted(mailbox.search(criteria), reverse=True)
            if before_uid is not None:
                uids = [uid for uid in uids if uid < before_uid]
            candidates = uids[: args.limit + 1]
            page_uids = candidates[: args.limit]
            items: list[dict[str, object]] = []
            for uid in page_uids:
                item = mailbox.summary(uid)
                if from_address and from_address.lower() not in {
                    str(value).lower() for value in item.get("from", [])
                }:
                    continue
                if to_address and to_address.lower() not in {
                    str(value).lower() for value in item.get("to", [])
                }:
                    continue
                if args.message_id and item.get("message_id") != args.message_id:
                    continue
                if since_time or before_time:
                    try:
                        received = datetime.fromisoformat(str(item.get("received_at", "")))
                    except ValueError:
                        continue
                    if since_time and received < since_time:
                        continue
                    if before_time and received >= before_time:
                        continue
                if args.has_attachment and not item.get("has_attachments"):
                    continue
                item["folder"] = mailbox.folder
                item["uidvalidity"] = mailbox.uidvalidity
                item["message_ref"] = encode_token(
                    {
                        "folder": mailbox.folder,
                        "uidvalidity": mailbox.uidvalidity,
                        "uid": uid,
                        "message_id": item.get("message_id", ""),
                    }
                )
                items.append(item)
            next_cursor = (
                encode_token({"before_uid": page_uids[-1]})
                if len(candidates) > args.limit and page_uids
                else None
            )
        return {"status": "ok", "items": items, "next_cursor": next_cursor}

    return retry_read(perform)


class SafeHtmlParser(HTMLParser):
    allowed_tags = {
        "p",
        "br",
        "strong",
        "b",
        "em",
        "i",
        "ul",
        "ol",
        "li",
        "blockquote",
        "pre",
        "code",
        "table",
        "thead",
        "tbody",
        "tr",
        "th",
        "td",
        "a",
        "h1",
        "h2",
        "h3",
        "h4",
    }
    blocked_content_tags = {"script", "style", "form", "object", "iframe", "svg"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.blocked_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in self.blocked_content_tags:
            self.blocked_depth += 1
            return
        if self.blocked_depth or tag == "img" or tag not in self.allowed_tags:
            return
        safe_attrs: list[str] = []
        if tag == "a":
            for key, value in attrs:
                if key.lower() == "href" and value and value.startswith(("https://", "http://", "mailto:")):
                    safe_attrs.append(f'href="{escape(value, quote=True)}"')
        suffix = f" {' '.join(safe_attrs)}" if safe_attrs else ""
        self.parts.append(f"<{tag}{suffix}>")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in self.blocked_content_tags and self.blocked_depth:
            self.blocked_depth -= 1
            return
        if not self.blocked_depth and tag in self.allowed_tags and tag != "br":
            self.parts.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        if not self.blocked_depth:
            self.parts.append(escape(data))

    def html(self) -> str:
        return "".join(self.parts)


def sanitize_html(value: str) -> str:
    parser = SafeHtmlParser()
    parser.feed(value)
    parser.close()
    return parser.html()


def normalized_text(value: str) -> tuple[str, bool, bool]:
    kept: list[str] = []
    quoted = False
    signature = False
    for line in value.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if line.strip() == "--":
            signature = True
            break
        if line.lstrip().startswith(">"):
            quoted = True
            continue
        if line.lower().startswith("on ") and line.rstrip().endswith("wrote:"):
            quoted = True
            break
        kept.append(line.rstrip())
    while kept and not kept[-1]:
        kept.pop()
    return "\n".join(kept).strip(), quoted, signature


def message_content(raw: bytes, include_html: bool) -> dict[str, object]:
    if len(raw) > MAX_BODY_BYTES:
        raise MailctlError("size-limit", "message exceeds the 5 MB decoded-content limit")
    message = BytesParser(policy=policy.default).parsebytes(raw)
    plain = ""
    html = ""
    attachments: list[dict[str, object]] = []
    for index, part in enumerate(message.walk()):
        if part.is_multipart():
            continue
        payload = part.get_payload(decode=True) or b""
        disposition = part.get_content_disposition()
        filename = part.get_filename()
        if disposition == "attachment" or filename:
            attachments.append(
                {
                    "part_id": str(index),
                    "filename": filename or f"attachment-{index}",
                    "content_type": part.get_content_type(),
                    "size": len(payload),
                }
            )
            continue
        charset = part.get_content_charset() or "utf-8"
        decoded = payload.decode(charset, "replace")
        if part.get_content_type() == "text/plain" and not plain:
            plain = decoded
        elif part.get_content_type() == "text/html" and not html:
            html = decoded
    text, quoted, signature = normalized_text(plain)
    result: dict[str, object] = {
        "message_id": str(message.get("Message-ID", "")),
        "subject": str(message.get("Subject", "")),
        "from": [addr for _, addr in getaddresses(message.get_all("From", [])) if addr],
        "to": [addr for _, addr in getaddresses(message.get_all("To", [])) if addr],
        "cc": [addr for _, addr in getaddresses(message.get_all("Cc", [])) if addr],
        "text": text,
        "quoted_history_collapsed": quoted,
        "signature_collapsed": signature,
        "attachments": attachments,
    }
    if include_html:
        result["html"] = sanitize_html(html)
    return result


def fetch_referenced_message(
    project: Path,
    message_ref: str,
) -> tuple[dict[str, Any], bytes, EmailMessage]:
    reference = decode_token(message_ref, "message reference")
    try:
        folder = str(reference["folder"])
        expected_validity = int(reference["uidvalidity"])
        uid = int(reference["uid"])
    except (KeyError, TypeError, ValueError) as error:
        raise MailctlError("invalid-input", "invalid message reference") from error

    def perform() -> bytes:
        with open_mailbox(project, folder) as mailbox:
            if mailbox.uidvalidity != expected_validity:
                raise MailctlError("stale-reference", "mailbox UIDVALIDITY changed; search again")
            return mailbox.fetch(uid)

    raw = retry_read(perform)
    message = BytesParser(policy=policy.default).parsebytes(raw)
    expected_message_id = str(reference.get("message_id", ""))
    if expected_message_id and str(message.get("Message-ID", "")) != expected_message_id:
        raise MailctlError("stale-reference", "message identity no longer matches; search again")
    return reference, raw, message


def command_get(args: argparse.Namespace) -> dict[str, object]:
    project = Path.cwd()
    ensure_state_is_untracked(project)
    reference, raw, _ = fetch_referenced_message(project, args.message_ref)
    result = message_content(raw, args.include_html)
    result.update(
        {
            "status": "ok",
            "folder": reference["folder"],
            "uidvalidity": reference["uidvalidity"],
            "uid": reference["uid"],
            "message_ref": args.message_ref,
        }
    )
    return result


def allowed_attachment_type(content_type: str) -> bool:
    return (
        content_type.startswith(("text/", "image/"))
        or content_type
        in {
            "application/pdf",
            "application/msword",
            "application/vnd.ms-excel",
            "application/vnd.ms-powerpoint",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        }
    )


def safe_filename(value: str) -> str:
    name = Path(value.replace("\\", "/")).name
    name = re.sub(r"[^A-Za-z0-9._() -]+", "_", name).strip(". ")
    return name or "attachment"


def unique_output_path(directory: Path, filename: str) -> Path:
    candidate = directory / filename
    counter = 1
    while candidate.exists() or candidate.is_symlink():
        candidate = directory / f"{Path(filename).stem}-{counter}{Path(filename).suffix}"
        counter += 1
    return candidate


def command_attachment_get(args: argparse.Namespace) -> dict[str, object]:
    project = Path.cwd()
    ensure_state_is_untracked(project)
    try:
        part_id = int(args.part_id)
    except ValueError as error:
        raise MailctlError("invalid-input", "invalid attachment part ID") from error
    _, _, message = fetch_referenced_message(project, args.message_ref)
    parts = list(message.walk())
    if part_id < 0 or part_id >= len(parts):
        raise MailctlError("invalid-input", "attachment part does not exist")
    part = parts[part_id]
    filename = part.get_filename()
    if not filename and part.get_content_disposition() != "attachment":
        raise MailctlError("invalid-input", "selected MIME part is not an attachment")
    content_type = part.get_content_type()
    if not allowed_attachment_type(content_type):
        raise MailctlError("unsafe-attachment", f"attachment type is not allowed: {content_type}")
    payload = part.get_payload(decode=True) or b""
    if len(payload) > MAX_ATTACHMENT_BYTES:
        raise MailctlError("size-limit", "attachment exceeds the 20 MB limit")
    output_dir = project / STATE_DIR_NAME / "attachments"
    output_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    output = unique_output_path(output_dir, safe_filename(filename or f"attachment-{part_id}"))
    output.write_bytes(payload)
    os.chmod(output, 0o600)
    return {
        "status": "saved",
        "path": str(output),
        "filename": output.name,
        "content_type": content_type,
        "size": len(payload),
    }


def manifest_scalar(value: str) -> str | None:
    value = value.strip()
    if value in {"null", "~"}:
        return None
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def parse_manifest(text: str) -> tuple[dict[str, object], str]:
    lines = text.replace("\r\n", "\n").split("\n")
    if not lines or lines[0] != "---":
        raise MailctlError("invalid-input", "Draft Manifest must start with YAML frontmatter")
    try:
        end = lines.index("---", 1)
    except ValueError as error:
        raise MailctlError("invalid-input", "Draft Manifest frontmatter is not closed") from error
    header_lines = lines[1:end]
    body = "\n".join(lines[end + 1 :]).strip()
    manifest: dict[str, object] = {}
    active_list: str | None = None
    for line in header_lines:
        if not line.strip():
            continue
        if line.startswith("  - ") and active_list:
            value = manifest_scalar(line[4:])
            if not value:
                raise MailctlError("invalid-input", f"{active_list} contains an empty address")
            values = manifest.setdefault(active_list, [])
            assert isinstance(values, list)
            values.append(value)
            continue
        if ":" not in line or line.startswith((" ", "\t")):
            raise MailctlError("invalid-input", f"unsupported Draft Manifest line: {line}")
        key, raw_value = line.split(":", 1)
        key = key.strip()
        if key not in {"account", "to", "cc", "subject", "reply_to", "reply_mode"}:
            raise MailctlError("invalid-input", f"unsupported Draft Manifest field: {key}")
        active_list = None
        if key in {"to", "cc"}:
            value = raw_value.strip()
            if value == "[]":
                manifest[key] = []
            elif value:
                raise MailctlError("invalid-input", f"{key} must be a YAML list")
            else:
                manifest[key] = []
                active_list = key
        else:
            manifest[key] = manifest_scalar(raw_value)
    if not body:
        raise MailctlError("invalid-input", "Draft Manifest body is empty")
    return manifest, body


def render_inline(value: str) -> str:
    rendered = escape(value)
    rendered = re.sub(
        r"\[([^\]]+)\]\(((?:https?://|mailto:)[^)]+)\)",
        lambda match: (
            f'<a href="{escape(match.group(2), quote=True)}" '
            'style="color:#2563eb;text-decoration:underline">{}</a>'.format(
                match.group(1)
            )
        ),
        rendered,
    )
    rendered = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", rendered)
    rendered = re.sub(r"(?<!\*)\*([^*]+)\*", r"<em>\1</em>", rendered)
    rendered = re.sub(r"`([^`]+)`", r"<code>\1</code>", rendered)
    return rendered


def table_cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def is_table_separator(line: str) -> bool:
    cells = table_cells(line)
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)


def markdown_to_html(markdown: str) -> str:
    lines = markdown.replace("\r\n", "\n").split("\n")
    output: list[str] = [
        '<div style="font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;'
        'font-size:15px;line-height:1.65;color:#1f2937;max-width:760px">'
    ]
    index = 0
    list_tag: str | None = None
    in_code = False
    code_lines: list[str] = []

    def close_list() -> None:
        nonlocal list_tag
        if list_tag:
            output.append(f"</{list_tag}>")
            list_tag = None

    while index < len(lines):
        line = lines[index]
        if line.startswith("```"):
            close_list()
            if in_code:
                output.append(
                    '<pre style="background:#f3f4f6;padding:12px;border-radius:6px;overflow:auto"><code>'
                    + escape("\n".join(code_lines))
                    + "</code></pre>"
                )
                code_lines = []
                in_code = False
            else:
                in_code = True
            index += 1
            continue
        if in_code:
            code_lines.append(line)
            index += 1
            continue
        if not line.strip():
            close_list()
            index += 1
            continue
        if index + 1 < len(lines) and "|" in line and is_table_separator(lines[index + 1]):
            close_list()
            headers = table_cells(line)
            rows: list[list[str]] = []
            index += 2
            while index < len(lines) and "|" in lines[index] and lines[index].strip():
                rows.append(table_cells(lines[index]))
                index += 1
            output.append('<table style="border-collapse:collapse;width:100%;margin:12px 0">')
            output.append("<thead><tr>")
            for header in headers:
                output.append(
                    '<th style="border:1px solid #d1d5db;background:#f9fafb;padding:8px;text-align:left">'
                    + render_inline(header)
                    + "</th>"
                )
            output.append("</tr></thead><tbody>")
            for row in rows:
                output.append("<tr>")
                for cell in row:
                    output.append(
                        '<td style="border:1px solid #d1d5db;padding:8px">'
                        + render_inline(cell)
                        + "</td>"
                    )
                output.append("</tr>")
            output.append("</tbody></table>")
            continue
        heading = re.match(r"^(#{1,4})\s+(.+)$", line)
        if heading:
            close_list()
            level = len(heading.group(1))
            sizes = {1: "24px", 2: "20px", 3: "17px", 4: "15px"}
            output.append(
                f'<h{level} style="font-size:{sizes[level]};margin:18px 0 8px;color:#111827">'
                + render_inline(heading.group(2))
                + f"</h{level}>"
            )
            index += 1
            continue
        unordered = re.match(r"^[-*]\s+(.+)$", line)
        ordered = re.match(r"^\d+\.\s+(.+)$", line)
        if unordered or ordered:
            target = "ul" if unordered else "ol"
            if list_tag != target:
                close_list()
                list_tag = target
                output.append(f'<{target} style="padding-left:24px;margin:8px 0">')
            output.append(f"<li>{render_inline((unordered or ordered).group(1))}</li>")
            index += 1
            continue
        if line.startswith("> "):
            close_list()
            output.append(
                '<blockquote style="border-left:4px solid #d1d5db;margin:12px 0;padding:4px 12px;color:#4b5563">'
                + render_inline(line[2:])
                + "</blockquote>"
            )
            index += 1
            continue
        close_list()
        output.append(f'<p style="margin:8px 0">{render_inline(line)}</p>')
        index += 1
    if in_code:
        output.append(
            '<pre style="background:#f3f4f6;padding:12px;border-radius:6px"><code>'
            + escape("\n".join(code_lines))
            + "</code></pre>"
        )
    close_list()
    output.append("</div>")
    return "".join(output)


def markdown_to_plain(markdown: str) -> str:
    text = re.sub(r"<[^>]*>", lambda match: match.group(0), markdown)
    text = re.sub(r"^#{1,4}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    return text.strip()


def manifest_path(project: Path, value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = project / path
    resolved = path.resolve()
    try:
        resolved.relative_to(project.resolve())
    except ValueError as error:
        raise MailctlError("permission", "Draft Manifest must be inside the Calling Project") from error
    return resolved


def prune_old_drafts(project: Path, now: datetime) -> None:
    drafts = project / STATE_DIR_NAME / "drafts"
    if not drafts.is_dir():
        return
    cutoff = now - timedelta(days=30)
    for candidate in drafts.iterdir():
        if candidate.is_symlink() or not candidate.is_dir() or not re.fullmatch(r"[0-9a-f]{20}", candidate.name):
            continue
        try:
            state = json.loads((candidate / "state.json").read_text())
            created_at = datetime.fromisoformat(str(state["created_at"]))
        except (OSError, KeyError, ValueError, TypeError, json.JSONDecodeError):
            continue
        if created_at < cutoff:
            shutil.rmtree(candidate)


def unique_addresses(values: list[str], excluded: set[str]) -> list[str]:
    result: list[str] = []
    seen = {value.lower() for value in excluded}
    for value in values:
        address = validate_email(value)
        key = address.lower()
        if key not in seen:
            result.append(address)
            seen.add(key)
    return result


def resolve_reply(
    project: Path,
    message_ref: str,
    mode: str,
    own_address: str,
) -> tuple[list[str], list[str], str, str]:
    if mode not in {"reply", "reply-all"}:
        raise MailctlError("invalid-input", "reply_mode must be reply or reply-all")
    _, _, original = fetch_referenced_message(project, message_ref)
    message_id = str(original.get("Message-ID", ""))
    if not message_id:
        raise MailctlError("stale-reference", "reply message has no Message-ID")
    senders = [addr for _, addr in getaddresses(original.get_all("From", [])) if addr]
    if not senders:
        raise MailctlError("invalid-input", "reply message has no sender")
    to = unique_addresses(senders, {own_address})
    cc: list[str] = []
    if mode == "reply-all":
        original_to = [addr for _, addr in getaddresses(original.get_all("To", [])) if addr]
        original_cc = [addr for _, addr in getaddresses(original.get_all("Cc", [])) if addr]
        to.extend(unique_addresses(original_to, {own_address, *to}))
        cc = unique_addresses(original_cc, {own_address, *to})
    references = str(original.get("References", "")).strip()
    thread_references = f"{references} {message_id}".strip()
    return to, cc, message_id, thread_references


def command_prepare(args: argparse.Namespace) -> dict[str, object]:
    project = Path.cwd()
    ensure_state_is_untracked(project)
    now = datetime.now(timezone.utc)
    prune_old_drafts(project, now)
    account = load_default_account(project)
    path = manifest_path(project, args.file)
    try:
        manifest, body = parse_manifest(path.read_text())
    except OSError as error:
        raise MailctlError("invalid-input", f"cannot read Draft Manifest: {error}") from error
    if manifest.get("account", "default") != "default":
        raise MailctlError("invalid-input", "only the default Mailbox Account is supported")
    address = validate_email(str(account.get("address", "")))
    manifest_to = [validate_email(str(value)) for value in manifest.get("to", [])]
    manifest_cc = [validate_email(str(value)) for value in manifest.get("cc", [])]
    reply_to = manifest.get("reply_to")
    in_reply_to = ""
    references = ""
    if reply_to:
        if manifest_to or manifest_cc:
            raise MailctlError(
                "invalid-input",
                "reply Draft Manifest recipients are derived from the referenced message",
            )
        to, cc, in_reply_to, references = resolve_reply(
            project,
            str(reply_to),
            str(manifest.get("reply_mode") or "reply"),
            address,
        )
    else:
        if manifest.get("reply_mode"):
            raise MailctlError("invalid-input", "reply_mode requires reply_to")
        to, cc = manifest_to, manifest_cc
    if not to:
        raise MailctlError("invalid-input", "Draft Manifest resolves to no To recipient")
    subject = str(manifest.get("subject") or "").strip()
    if not subject or "\n" in subject or "\r" in subject:
        raise MailctlError("invalid-input", "Draft Manifest requires a one-line subject")
    display_name = str(account.get("display_name", ""))
    html_body = markdown_to_html(body)
    plain_body = markdown_to_plain(body)
    message = EmailMessage(policy=policy.SMTP)
    message["From"] = formataddr((display_name, address)) if display_name else address
    message["To"] = ", ".join(to)
    if cc:
        message["Cc"] = ", ".join(cc)
    message["Subject"] = subject
    message["Date"] = format_datetime(now)
    message["Message-ID"] = make_msgid(domain=address.split("@", 1)[1])
    if in_reply_to:
        message["In-Reply-To"] = in_reply_to
        message["References"] = references
    message.set_content(plain_body)
    message.add_alternative(html_body, subtype="html")
    raw = message.as_bytes(policy=policy.SMTP)
    digest = hashlib.sha256(raw).hexdigest()
    draft_id = digest[:20]
    draft_dir = project / STATE_DIR_NAME / "drafts" / draft_id
    draft_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
    os.chmod(draft_dir, 0o700)
    eml_path = draft_dir / "message.eml"
    preview_path = draft_dir / "preview.html"
    state_path = draft_dir / "state.json"
    eml_path.write_bytes(raw)
    preview_path.write_text(html_body)
    state = {
        "draft_id": draft_id,
        "content_sha256": digest,
        "status": "pending",
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(hours=72)).isoformat(),
        "account": "default",
        "from": address,
        "to": to,
        "cc": cc,
        "subject": subject,
        "message_id": str(message["Message-ID"]),
    }
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    for output in (eml_path, preview_path, state_path):
        os.chmod(output, 0o600)
    return {
        "status": "prepared",
        "draft_id": draft_id,
        "from": address,
        "to": to,
        "cc": cc,
        "subject": subject,
        "expires_at": state["expires_at"],
        "preview_path": str(preview_path),
    }


def load_draft(project: Path, draft_id: str) -> tuple[dict[str, Any], bytes, Path]:
    if not re.fullmatch(r"[0-9a-f]{20}", draft_id):
        raise MailctlError("invalid-input", "invalid Prepared Draft ID")
    draft_dir = project / STATE_DIR_NAME / "drafts" / draft_id
    state_path = draft_dir / "state.json"
    eml_path = draft_dir / "message.eml"
    if draft_dir.is_symlink() or state_path.is_symlink() or eml_path.is_symlink():
        raise MailctlError("draft-integrity", "Prepared Draft contains a symbolic link")
    try:
        state = json.loads(state_path.read_text())
        raw = eml_path.read_bytes()
    except (OSError, json.JSONDecodeError) as error:
        raise MailctlError("draft-not-found", "Prepared Draft does not exist") from error
    if not isinstance(state, dict) or state.get("draft_id") != draft_id:
        raise MailctlError("draft-integrity", "Prepared Draft state is invalid")
    content_digest = hashlib.sha256(raw).hexdigest()
    if (
        content_digest != state.get("content_sha256")
        or not content_digest.startswith(draft_id)
    ):
        raise MailctlError("draft-integrity", "Prepared Draft MIME content has changed")
    return state, raw, draft_dir


def command_draft_show(args: argparse.Namespace) -> dict[str, object]:
    project = Path.cwd()
    ensure_state_is_untracked(project)
    state, raw, draft_dir = load_draft(project, args.draft_id)
    message = BytesParser(policy=policy.default).parsebytes(raw)
    plain_part = message.get_body(preferencelist=("plain",))
    html_part = message.get_body(preferencelist=("html",))
    return {
        "status": state.get("status"),
        "draft_id": args.draft_id,
        "from": state.get("from"),
        "to": state.get("to", []),
        "cc": state.get("cc", []),
        "subject": state.get("subject"),
        "message_id": state.get("message_id"),
        "created_at": state.get("created_at"),
        "expires_at": state.get("expires_at"),
        "text": plain_part.get_content().rstrip("\n") if plain_part else "",
        "html": html_part.get_content().rstrip("\n") if html_part else "",
        "preview_path": str(draft_dir / "preview.html"),
    }


def save_draft_state(draft_dir: Path, state: dict[str, Any]) -> None:
    destination = draft_dir / "state.json"
    temporary = draft_dir / ".state.json.tmp"
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    os.chmod(temporary, 0o600)
    temporary.replace(destination)


def lock_uncertain_send(
    draft_dir: Path,
    state: dict[str, Any],
    message: str,
) -> None:
    state["status"] = "uncertain"
    state["uncertain_at"] = datetime.now(timezone.utc).isoformat()
    save_draft_state(draft_dir, state)
    raise MailctlError("uncertain-send", message)


def command_send(args: argparse.Namespace) -> dict[str, object]:
    project = Path.cwd()
    ensure_state_is_untracked(project)
    state, raw, draft_dir = load_draft(project, args.draft_id)
    if state.get("status") != "pending":
        raise MailctlError(
            "draft-locked",
            f"Prepared Draft is {state.get('status')}; create and preview a new Prepared Draft",
        )
    try:
        expires_at = datetime.fromisoformat(str(state["expires_at"]))
    except (KeyError, ValueError) as error:
        raise MailctlError("draft-integrity", "Prepared Draft expiry is invalid") from error
    if datetime.now(timezone.utc) > expires_at:
        state["status"] = "expired"
        save_draft_state(draft_dir, state)
        raise MailctlError("draft-expired", "Prepared Draft is older than 72 hours")
    account = load_default_account(project)
    address = validate_email(str(account.get("address", "")))
    if state.get("from") != address:
        raise MailctlError("draft-integrity", "Prepared Draft sender does not match the account")
    password = read_keychain_password(address)
    message = BytesParser(policy=policy.default).parsebytes(raw)
    context = ssl.create_default_context()
    smtp: smtplib.SMTP_SSL | None = None
    try:
        smtp = smtplib.SMTP_SSL(
            str(account["smtp_host"]),
            int(account["smtp_port"]),
            context=context,
            timeout=30,
        )
        smtp.login(address, password)
        try:
            refused = smtp.send_message(message)
        except smtplib.SMTPRecipientsRefused as error:
            raise MailctlError("send-failed", "SMTP rejected every recipient") from error
        except smtplib.SMTPResponseException as error:
            raise MailctlError(
                "send-failed",
                f"SMTP rejected the message with code {error.smtp_code}",
            ) from error
        except (TimeoutError, OSError, smtplib.SMTPServerDisconnected) as error:
            lock_uncertain_send(
                draft_dir,
                state,
                f"SMTP transport failed after sending began; this is an Uncertain Send: {error}",
            )
        if refused:
            lock_uncertain_send(
                draft_dir,
                state,
                "SMTP may have accepted only some recipients; the Prepared Draft is locked",
            )
    except MailctlError:
        raise
    except smtplib.SMTPAuthenticationError as error:
        raise MailctlError("authentication", "SMTP authentication failed") from error
    except (KeyError, OSError, smtplib.SMTPException) as error:
        raise MailctlError("connection", f"SMTP connection failed before sending: {error}") from error
    finally:
        if smtp is not None:
            try:
                smtp.quit()
            except (AttributeError, OSError, smtplib.SMTPException):
                try:
                    smtp.close()
                except (AttributeError, OSError, smtplib.SMTPException):
                    pass
    state["status"] = "consumed"
    state["sent_at"] = datetime.now(timezone.utc).isoformat()
    save_draft_state(draft_dir, state)
    return {
        "status": "consumed",
        "draft_id": args.draft_id,
        "message_id": state.get("message_id"),
        "sent_at": state["sent_at"],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mailctl")
    subparsers = parser.add_subparsers(dest="command", required=True)
    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("--email", required=True)
    init_parser.add_argument("--display-name")
    init_parser.set_defaults(handler=command_init)
    auth_parser = subparsers.add_parser("auth")
    auth_subparsers = auth_parser.add_subparsers(dest="auth_command", required=True)
    setup_parser = auth_subparsers.add_parser("setup")
    setup_parser.set_defaults(handler=command_auth_setup)
    doctor_parser = subparsers.add_parser("doctor")
    doctor_parser.set_defaults(handler=command_doctor)
    search_parser = subparsers.add_parser("search")
    search_parser.add_argument("--folder", default="INBOX")
    search_parser.add_argument("--from", dest="from_address")
    search_parser.add_argument("--to", dest="to_address")
    search_parser.add_argument("--since")
    search_parser.add_argument("--before")
    search_parser.add_argument("--subject")
    search_parser.add_argument("--message-id")
    search_parser.add_argument("--has-attachment", action="store_true")
    search_parser.add_argument("--limit", type=int, default=50)
    search_parser.add_argument("--cursor")
    search_parser.set_defaults(handler=command_search)
    get_parser = subparsers.add_parser("get")
    get_parser.add_argument("--message-ref", required=True)
    get_parser.add_argument("--include-html", action="store_true")
    get_parser.set_defaults(handler=command_get)
    attachment_parser = subparsers.add_parser("attachment")
    attachment_subparsers = attachment_parser.add_subparsers(
        dest="attachment_command", required=True
    )
    attachment_get_parser = attachment_subparsers.add_parser("get")
    attachment_get_parser.add_argument("--message-ref", required=True)
    attachment_get_parser.add_argument("--part-id", required=True)
    attachment_get_parser.set_defaults(handler=command_attachment_get)
    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--file", required=True)
    prepare_parser.set_defaults(handler=command_prepare)
    draft_parser = subparsers.add_parser("draft")
    draft_subparsers = draft_parser.add_subparsers(dest="draft_command", required=True)
    draft_show_parser = draft_subparsers.add_parser("show")
    draft_show_parser.add_argument("--draft-id", required=True)
    draft_show_parser.set_defaults(handler=command_draft_show)
    send_parser = subparsers.add_parser("send")
    send_parser.add_argument("--draft-id", required=True)
    send_parser.set_defaults(handler=command_send)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        emit(args.handler(args))
        return 0
    except MailctlError as error:
        emit({"status": "error", "category": error.category, "message": str(error)})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
