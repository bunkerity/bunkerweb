#!/usr/bin/env python3
"""Fail when direct 1.7 Python lines fall below the requested coverage."""

import argparse
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HEADER = re.compile(r"^([0-9a-f]{40}) \d+ (\d+)(?: \d+)?$")
EXCLUDED_PREFIXES = ("src/common/db/alembic/",)


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("coverage_json", type=Path)
    parser.add_argument("--base", default="09951271f6be874eabdad7a8d4129f30c7bf2b10")
    parser.add_argument("--fail-under", type=float, default=80)
    args = parser.parse_args()

    head = git("rev-parse", "HEAD").strip()
    direct_commits = set(git("rev-list", "--first-parent", "--no-merges", f"{args.base}..{head}").splitlines())
    tracked_files = set(git("ls-files").splitlines())
    report = json.loads(args.coverage_json.read_text(encoding="utf-8"))
    covered = total = 0
    missed: dict[str, list[int]] = {}

    for filename, data in report["files"].items():
        path = Path(filename)
        if path.is_absolute():
            try:
                path = path.relative_to(ROOT)
            except ValueError:
                continue
        filename = path.as_posix()
        if not filename.startswith("src/") or filename.startswith(EXCLUDED_PREFIXES) or filename not in tracked_files or not (ROOT / path).is_file():
            continue

        owners = {}
        for line in git("blame", "--line-porcelain", head, "--", path.as_posix()).splitlines():
            match = HEADER.match(line)
            if match:
                owners[int(match.group(2))] = match.group(1)

        hit = set(data.get("executed_lines", ()))
        statements = hit | set(data.get("missing_lines", ()))
        changed = {line for line in statements if owners.get(line) in direct_commits}
        missing = sorted(changed - hit)
        total += len(changed)
        covered += len(changed) - len(missing)
        if missing:
            missed[path.as_posix()] = missing

    percent = covered * 100 / total if total else 100.0
    print(f"Direct 1.7 changed-line coverage: {covered}/{total} ({percent:.1f}%)")
    for filename, lines in sorted(missed.items()):
        print(f"  {filename}: {','.join(map(str, lines))}")
    return int(percent < args.fail_under)


if __name__ == "__main__":
    raise SystemExit(main())
