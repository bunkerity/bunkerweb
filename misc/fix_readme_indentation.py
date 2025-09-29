#!/usr/bin/env python3
"""Normalize indentation in README translation files.

Rules applied (mirroring English base README.md patterns):
1. Admonition blocks starting with "!!! " must have their content indented by 4 spaces
   until a blank line or a new block/heading/tab header begins.
2. Tabbed content sections (lines starting with '=== "') must have all following
   non-empty lines indented by 4 spaces until the next tab header (=== "...),
   or a markdown heading starting with '##' / '###'.

The script is idempotent: running it multiple times won't change already-correct files.

Only README files under src/common/core/*/ matching README*.md are processed.
"""

from __future__ import annotations

import difflib
from pathlib import Path

CORE_DIR = Path(__file__).resolve().parent.parent / "src" / "common" / "core"


def needs_processing(path: Path) -> bool:
    # Process all README*.md (including English) for consistency, it's harmless.
    return path.name.startswith("README") and path.suffix == ".md"


def normalize_indentation(lines: list[str]) -> list[str]:
    new: list[str] = []
    i = 0
    length = len(lines)

    def is_section_terminator(crline: str) -> bool:
        return crline.lstrip().startswith(("=== ", "## ", "### ", "!!! "))

    while i < length:
        line = lines[i]

        # Admonition block
        if line.lstrip().startswith("!!! "):
            new.append(line)
            i += 1
            # Indent following lines until blank line or terminator
            while i < length:
                crline = lines[i]
                if crline.strip() == "":
                    new.append(crline)
                    i += 1
                    break  # blank line ends admonition block
                if is_section_terminator(crline):
                    break
                if not crline.startswith("    "):
                    # Avoid adding indentation to fenced code delimiters already indented
                    crline = "    " + crline.lstrip()
                new.append(crline)
                i += 1
            continue

        # Tab header
        if line.lstrip().startswith("=== "):
            new.append(line)
            i += 1
            # Process content until next tab header / heading
            while i < length:
                crline = lines[i]
                if is_section_terminator(crline):
                    break
                if crline.strip() == "":
                    new.append(crline)
                    i += 1
                    continue
                if not crline.startswith("    "):
                    crline = "    " + crline.lstrip()
                new.append(crline)
                i += 1
            continue

        new.append(line)
        i += 1

    return new


def process_file(path: Path) -> bool:
    original = path.read_text(encoding="utf-8").splitlines(keepends=True)
    updated = normalize_indentation(original)
    if original != updated:
        path.write_text("".join(updated), encoding="utf-8")
        diff = difflib.unified_diff(original, updated, fromfile=str(path), tofile=str(path), lineterm="")
        print(f"Fixed indentation: {path}")
        # Print a short diff preview (first 40 changed lines)
        changes = [d for d in diff]
        shown = 0
        for line in changes:
            if line.startswith(("+", "-")) and not line.startswith(("+++", "---")):
                shown += 1
            if shown > 80:
                print("... (diff truncated) ...")
                break
            print(line)
        return True
    return False


def main() -> None:
    if not CORE_DIR.exists():
        raise SystemExit(f"Core directory not found: {CORE_DIR}")
    readmes = sorted(CORE_DIR.glob("*/README*.md"))
    changed = 0
    for readme in readmes:
        if not needs_processing(readme):
            continue
        if process_file(readme):
            changed += 1
    print(f"Processed {len(readmes)} README files. Updated: {changed}")


if __name__ == "__main__":
    main()
