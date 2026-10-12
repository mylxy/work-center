#!/usr/bin/env python3
"""Copy the codeup skill to the personal Codex skill directory without overwriting."""

import argparse
from pathlib import Path
import shutil
import sys


SOURCE = Path(__file__).resolve().parents[1] / "skills" / "codeup"
TARGET = Path.home() / ".agents" / "skills" / "codeup"


def contents(root):
    return {p.relative_to(root): p.read_bytes() for p in root.rglob("*")
            if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"}


def install(source, target):
    if not (source / "SKILL.md").is_file():
        raise ValueError("Source skill is missing SKILL.md")
    if target.is_symlink():
        raise ValueError(f"Refusing to replace symbolic link: {target}")
    if target.exists():
        if target.is_dir() and contents(source) == contents(target):
            return "unchanged"
        raise ValueError(f"Existing skill differs; review before replacing: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    return "installed"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, default=TARGET)
    args = parser.parse_args()
    try:
        print(f"{install(SOURCE, args.target.expanduser())}: {args.target.expanduser()}")
    except (OSError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
