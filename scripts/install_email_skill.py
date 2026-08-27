#!/usr/bin/env python3
"""Install the repository-owned email skill with a symbolic link."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE = REPOSITORY_ROOT / ".agents" / "skills" / "email"
DEFAULT_TARGET = Path.home() / ".codex" / "skills" / "email"


def install(target: Path) -> None:
    source = SOURCE.resolve(strict=True)
    target = target.expanduser()
    if target.is_symlink():
        try:
            installed_source = target.resolve(strict=True)
        except FileNotFoundError as error:
            raise ValueError(f"refusing to replace broken symbolic link: {target}") from error
        if installed_source == source:
            return
        raise ValueError(f"refusing to replace symbolic link to another source: {target}")
    if target.exists():
        raise ValueError(f"refusing to replace existing path: {target}")
    target.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    target.symlink_to(source, target_is_directory=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Install the repository-owned email skill as a symbolic link."
    )
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    args = parser.parse_args(argv)
    try:
        install(args.target)
    except (OSError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    print(f"Installed email skill: {args.target.expanduser()} -> {SOURCE.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
