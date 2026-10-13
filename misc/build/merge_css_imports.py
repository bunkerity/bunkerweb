#!/usr/bin/env python3
"""Inline the Web UI overrides.css @import index at build time.

The index holds comments, blank lines, one @charset line before the first import, and
@import url("overrides/<name>.css"); lines. Every part is appended in index order with its
relative url() targets rebased to the index directory, then the overrides/ directory is removed.
"""

from pathlib import Path
from posixpath import join, normpath
from re import DOTALL, compile as re_compile
from shutil import rmtree
from sys import argv, exit as sys_exit, stderr

IMPORT_RE = re_compile(r'@import url\("overrides/([a-z0-9-]+)\.css"\);')
CHARSET = '@charset "UTF-8";'
COMMENT_RE = re_compile(r"(/\*.*?\*/)", DOTALL)
URL_RE = re_compile(r"""url\(\s*(["']?)([^"')\s]+)\1\s*\)""")
ABSOLUTE_RE = re_compile(r"^(data:|#|/|[a-zA-Z][a-zA-Z0-9+.-]*:)")


class MergeError(Exception):
    pass


def read(path: Path) -> str:
    # utf-8-sig drops a BOM, universal newlines turn CRLF into LF
    return path.read_text(encoding="utf-8-sig")


def parse_index(text: str):
    # Blank out comments but keep their newlines so line numbers stay true
    code = COMMENT_RE.sub(lambda m: "\n" * m.group().count("\n"), text)
    names, first_import, charset_seen = [], None, False
    for lineno, line in enumerate(code.split("\n"), 1):
        line = line.strip()
        if not line:
            continue
        match = IMPORT_RE.fullmatch(line)
        if match:
            if match.group(1) in names:
                raise MergeError(f"index line {lineno}: duplicate import of {match.group(1)}.css")
            names.append(match.group(1))
            first_import = first_import or lineno
        elif line == CHARSET and first_import is None and not charset_seen:
            charset_seen = True
        else:
            raise MergeError(f'index line {lineno}: only comments, {CHARSET} before the imports and @import url("overrides/<name>.css"); are allowed')
    if not names:
        raise MergeError("index imports no part")
    header = "".join(text.split("\n")[i] + "\n" for i in range(first_import - 1))
    return header, names


def rebase(part: str, text: str, css_dir: Path) -> str:
    def fix(match):
        quote, url = match.group(1), match.group(2)
        if ABSOLUTE_RE.match(url):
            return match.group(0)
        target = normpath(join("overrides", url))
        if normpath(join("css", target)).startswith(".."):
            raise MergeError(f"{part}.css: url {url} resolves outside static/")
        if not (css_dir / target).is_file():
            raise MergeError(f"{part}.css: url {url} does not exist once merged into css/ (write ../../img/... in parts)")
        return f"url({quote}{target}{quote})"

    # Odd chunks are comments: never rewritten or checked
    chunks = COMMENT_RE.split(text)
    return "".join(chunk if i % 2 else URL_RE.sub(fix, chunk) for i, chunk in enumerate(chunks))


def merge(index: Path) -> None:
    css_dir = index.parent
    parts_dir = css_dir / "overrides"
    header, names = parse_index(read(index))
    present = {p.stem for p in parts_dir.glob("*.css")}
    missing = [n for n in names if n not in present]
    if missing:
        raise MergeError("missing part(s): " + ", ".join(f"{n}.css" for n in missing))
    stray = sorted(present - set(names))
    if stray:
        raise MergeError("part(s) not listed in the index: " + ", ".join(f"{n}.css" for n in stray))
    out = [header.rstrip("\n") + "\n"]
    for name in names:
        text = read(parts_dir / f"{name}.css")
        code = COMMENT_RE.sub("", text)
        if "@import" in code or "@charset" in code:
            raise MergeError(f"{name}.css: parts may not contain @import or @charset")
        out.append(f"\n/* {name}.css */\n" + rebase(name, text, css_dir).rstrip("\n") + "\n")
    tmp = index.with_suffix(".css.tmp")
    tmp.write_text("".join(out), encoding="utf-8")
    tmp.replace(index)
    rmtree(parts_dir)


if __name__ == "__main__":
    if len(argv) != 2:
        print("usage: merge_css_imports.py <path/to/overrides.css>", file=stderr)
        sys_exit(2)
    try:
        merge(Path(argv[1]))
    except (MergeError, OSError, UnicodeDecodeError) as e:
        print(f"merge_css_imports: {e}", file=stderr)
        sys_exit(1)
