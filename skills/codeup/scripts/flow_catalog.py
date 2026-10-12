#!/usr/bin/env python3
"""Discover Flow commands from installed CLI help; never call a cloud API."""

import argparse
from pathlib import Path
import re
import subprocess
import sys


def discover(help_text):
    commands = sorted(set(re.findall(r"^  (flow-[a-z0-9-]+)\s", help_text, re.M)))
    if not commands:
        raise ValueError("No Flow commands found; check plugin installation/help format")
    return commands


def command_row(command, help_text):
    description = re.search(r"^(?:描述|Description):\s*(.+)$", help_text, re.M)
    if not description:
        raise ValueError(f"Cannot parse help for {command}")
    local = re.search(
        r"^(?:参数|Parameters):\n(.*?)(?=^(?:全局参数|Global Flags|Global Parameters):|\Z)",
        help_text, re.M | re.S,
    )
    flags = []
    if local:
        for flag, spec in re.findall(r"^\s+(--[a-z0-9-]+)\s+([^\n]+)", local[1], re.M):
            flags.append(f"`{flag}`" + ("*" if "(required)" in spec else ""))
    return f"| `{command}` | {description[1].replace('|', '/')} | {', '.join(flags) or '—'} |"


def cli(*args):
    result = subprocess.run(
        ["aliyun", "devops", *args], capture_output=True, text=True, timeout=30,
    )
    if result.returncode:
        raise ValueError(f"CLI help/version failed ({result.returncode}); check aliyun devops --help")
    return result.stdout


def catalog():
    version = cli("version").strip()
    commands = discover(cli("--help"))
    rows = [command_row(command, cli(command, "--help")) for command in commands]
    return "\n".join([
        "# Flow CLI 命令索引（自动生成）", "",
        f"来源：`{version}` 的 `--help`；共 {len(commands)} 个 Flow 命令。", "",
        "每条命令前加 `aliyun devops`。星号标记必填业务参数；类型、枚举、JSON 结构及全局参数以该命令当前 `--help` 和官方 OpenAPI 文档为准。",
        "此表用于完整能力发现，不是静态 allowlist；插件新增命令后可直接按实际帮助使用。", "",
        "更新：`python3 skills/codeup/scripts/flow_catalog.py --output skills/codeup/references/flow-commands.md`。",
        "检查漂移：`python3 skills/codeup/scripts/flow_catalog.py --check skills/codeup/references/flow-commands.md`。", "",
        "| 命令 | 能力与适用版本 | 业务参数（* 必填） |",
        "| --- | --- | --- |", *rows, "",
    ])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--output", type=Path)
    group.add_argument("--check", type=Path)
    args = parser.parse_args()
    try:
        content = catalog()
        if args.check:
            if args.check.read_text() != content:
                raise ValueError("Flow catalog differs from installed plugin; regenerate and review")
            print("Flow catalog matches installed plugin")
        elif args.output:
            args.output.write_text(content)
        else:
            print(content, end="")
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
