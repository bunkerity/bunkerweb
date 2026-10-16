"""`overrides.css` is an `@import` index over `css/overrides/*.css`, inlined again at image build.

Three things can go wrong silently and are pinned here: the cut losing or reordering a rule (the
cascade is the file order), the merge script accepting a broken tree, and a Dockerfile shipping the
index un-merged (cssnano does not inline `@import`, so the sheet would 404 its parts).
"""

import hashlib
import re
import subprocess
import sys

import pytest
from _css import OVERRIDES_INDEX, REPO, STATIC

sys.path.insert(0, str(REPO / "misc" / "build"))

from merge_css_imports import MergeError, merge, merged_text  # noqa: E402

SCRIPT = REPO / "misc" / "build" / "merge_css_imports.py"
MARKER_RE = re.compile(r"/\* [a-z0-9-]+\.css \*/")

# The 1.7 overrides.css as it was before the split (HEAD b1b3cc27e): its non-blank lines, after the
# leading banner comment (the index rewrites it), hashed in file order. A part cut that drops, duplicates
# or reorders a line changes this; blank lines and the per-part `/* name.css */` markers do not.
# Re-pinned for the four tooltip lines of dev 890d8777c (`--bs-tooltip-max-width`, `.tooltip-inner { overflow-wrap }`)
# and for the 44 lines of dev 83462ec57 (DataTables toolbar wrap) and 04330f635 (`.btn-outline-crowdsec`) in main.css;
# the next edit to any part re-pins it the same way.
PRE_SPLIT_LINES = 4477
PRE_SPLIT_SHA256 = "27400c7c47ea89f6357f2d2d7f53e4669ef1dbb7e6126865544541e0aec34dcf"
# The one line the split rewrote on purpose: a comment citing `overrides.css:4390-4398`, a line range that no longer exists.
REFRESHED_COMMENT = ("but kit-fidelity.css's", "but overrides.css:4390-4398's")


def significant_lines(text):
    text = re.sub(r"\A\s*/\*.*?\*/", "", text, count=1, flags=re.DOTALL)
    return [line for line in MARKER_RE.sub("", text).splitlines() if line.strip()]


def test_the_split_loses_and_reorders_nothing():
    merged = merged_text(OVERRIDES_INDEX)
    assert merged.count(REFRESHED_COMMENT[0]) == 1
    lines = significant_lines(merged.replace(*REFRESHED_COMMENT))
    assert len(lines) == PRE_SPLIT_LINES
    assert hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest() == PRE_SPLIT_SHA256


def test_the_sheet_in_the_tree_is_only_an_index():
    index = OVERRIDES_INDEX.read_text(encoding="utf-8")
    assert re.search(r'^@import url\("overrides/[a-z0-9-]+\.css"\);$', index, re.MULTILINE)
    assert len(index.splitlines()) < 60
    assert sorted(p.stem for p in (STATIC / "css" / "overrides").glob("*.css")) == sorted(
        re.findall(r'^@import url\("overrides/([a-z0-9-]+)\.css"\);$', index, re.MULTILINE)
    )


def test_the_merged_sheet_has_no_import_and_one_charset():
    merged = merged_text(OVERRIDES_INDEX)
    code = re.sub(r"/\*.*?\*/", "", merged, flags=re.DOTALL)
    assert "@import" not in code
    assert code.count("@charset") == 1
    assert merged.index("@charset") < merged.index(":root")


def test_merging_in_memory_leaves_the_tree_alone():
    before = sorted(p.name for p in (STATIC / "css" / "overrides").glob("*.css"))
    merged_text(OVERRIDES_INDEX)
    assert sorted(p.name for p in (STATIC / "css" / "overrides").glob("*.css")) == before


# --------------------------------------------------------------------------------------
# The merge script, on a throwaway tree
# --------------------------------------------------------------------------------------
INDEX = '/*\n* index\n*/\n\n@charset "UTF-8";\n@import url("overrides/a.css");\n@import url("overrides/b.css");\n'


@pytest.fixture
def tree(tmp_path):
    css = tmp_path / "static" / "css"
    (css / "overrides").mkdir(parents=True)
    (tmp_path / "static" / "img").mkdir()
    (tmp_path / "static" / "img" / "x.svg").write_text("<svg/>")
    (css / "overrides.css").write_text(INDEX)
    (css / "overrides" / "a.css").write_text(".a {\n  color: red;\n}\n\n")
    (css / "overrides" / "b.css").write_text('.b {\n  background: url("../../img/x.svg");\n}\n')
    return css


def test_parts_are_inlined_in_index_order_with_urls_rebased(tree):
    assert merged_text(tree / "overrides.css") == (
        '/*\n* index\n*/\n\n@charset "UTF-8";\n\n/* a.css */\n.a {\n  color: red;\n}\n\n/* b.css */\n.b {\n  background: url("../img/x.svg");\n}\n'
    )


def test_url_forms_that_must_not_move_and_ones_that_must(tree):
    (tree / "overrides" / "a.css").write_text(
        "/* url(../../img/not-checked.svg) in a comment */\n"
        '.a { background: url("data:image/svg+xml,%3Csvg/%3E"); }\n'
        ".b { background: url(#frag); }\n"
        ".c { background: url('https://example.test/x.png'); }\n"
        ".d { background: url(/abs/x.png); }\n"
        ".e { background: url(../../img/x.svg); }\n"
        ".f { background: url( '../../img/x.svg' ); }\n"
    )
    merged = merged_text(tree / "overrides.css")
    assert "url(../../img/not-checked.svg) in a comment" in merged
    assert 'url("data:image/svg+xml,%3Csvg/%3E")' in merged
    assert "url(#frag)" in merged and "url('https://example.test/x.png')" in merged and "url(/abs/x.png)" in merged
    assert ".e { background: url(../img/x.svg); }" in merged
    assert ".f { background: url('../img/x.svg'); }" in merged


def test_merge_writes_the_index_and_removes_the_parts(tree):
    expected = merged_text(tree / "overrides.css")
    merge(tree / "overrides.css")
    assert (tree / "overrides.css").read_text() == expected
    assert not (tree / "overrides").exists()
    assert not list(tree.glob("*.tmp"))


@pytest.mark.parametrize(
    ("break_it", "message"),
    [
        (lambda t: (t / "overrides" / "b.css").unlink(), "missing part"),
        (lambda t: (t / "overrides" / "c.css").write_text(".c {}"), "not listed in the index"),
        (lambda t: (t / "overrides.css").write_text(INDEX + '@import url("overrides/a.css");\n'), "duplicate import"),
        (lambda t: (t / "overrides" / "a.css").write_text('@import url("x.css");\n.a {}'), "may not contain @import"),
        (lambda t: (t / "overrides" / "a.css").write_text('@charset "UTF-8";\n.a {}'), "may not contain @import or @charset"),
        (lambda t: (t / "overrides" / "a.css").write_text('.a { background: url("../../img/missing.svg"); }'), "does not exist once merged"),
        (lambda t: (t / "overrides" / "a.css").write_text('.a { background: url("../../../../etc/passwd"); }'), "outside static/"),
        (lambda t: (t / "overrides.css").write_text(INDEX + ".stray { color: red; }\n"), "only comments"),
        (lambda t: (t / "overrides.css").write_text(INDEX.replace("@charset", ".x {}\n@charset")), "only comments"),
        (lambda t: (t / "overrides.css").write_text('@import url("overrides/a.css");\n@charset "UTF-8";\n'), "only comments"),
        (lambda t: (t / "overrides.css").write_text('/* nothing */\n@charset "UTF-8";\n'), "imports no part"),
    ],
)
def test_a_broken_tree_is_refused_and_left_untouched(tree, break_it, message):
    break_it(tree)
    index_before = (tree / "overrides.css").read_text()
    parts_before = sorted(p.name for p in (tree / "overrides").glob("*.css"))
    with pytest.raises(MergeError, match=message):
        merge(tree / "overrides.css")
    assert (tree / "overrides.css").read_text() == index_before
    assert sorted(p.name for p in (tree / "overrides").glob("*.css")) == parts_before


def test_a_commented_out_import_in_a_part_is_fine(tree):
    (tree / "overrides" / "a.css").write_text('/* was: @import url("x.css"); */\n.a {}\n')
    assert ".a {}" in merged_text(tree / "overrides.css")


def run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True)


def test_cli_merges_in_place(tree):
    expected = merged_text(tree / "overrides.css")
    result = run(tree / "overrides.css")
    assert result.returncode == 0, result.stderr
    assert (tree / "overrides.css").read_text() == expected
    assert not (tree / "overrides").exists()


def test_cli_print_mode_writes_the_merged_text_and_touches_nothing(tree):
    result = run("--print", tree / "overrides.css")
    assert result.returncode == 0, result.stderr
    assert result.stdout == merged_text(tree / "overrides.css")
    assert (tree / "overrides.css").read_text() == INDEX
    assert (tree / "overrides").is_dir()


def test_cli_reports_a_broken_tree_and_a_bad_call(tree):
    (tree / "overrides" / "b.css").unlink()
    broken = run(tree / "overrides.css")
    assert broken.returncode == 1 and "missing part(s): b.css" in broken.stderr
    assert run().returncode == 2


# --------------------------------------------------------------------------------------
# Every image that ships the UI merges before cssnano runs
# --------------------------------------------------------------------------------------
DOCKERFILES = sorted([REPO / "src" / "ui" / "Dockerfile", REPO / "src" / "all-in-one" / "Dockerfile", *(REPO / "src" / "linux").glob("Dockerfile-*")])
MERGE_RUN = re.compile(
    r"^RUN (python3(?:\.\d+)?) /tmp/merge_css_imports\.py /usr/share/bunkerweb/ui/app/static/css/overrides\.css && \\\n\s+rm -f /tmp/merge_css_imports\.py$",
    re.MULTILINE,
)


def test_the_twelve_ui_dockerfiles_are_all_covered():
    assert len(DOCKERFILES) == 12


@pytest.mark.parametrize("dockerfile", DOCKERFILES, ids=lambda p: str(p.relative_to(REPO)))
def test_the_dockerfile_merges_the_overrides_before_minifying(dockerfile):
    text = dockerfile.read_text(encoding="utf-8")
    copy_ui = text.index("\nCOPY src/ui ui\n")
    copy_script = text.index("\nCOPY misc/build/merge_css_imports.py /tmp/merge_css_imports.py\n")
    run_match = MERGE_RUN.search(text)
    assert run_match, f"{dockerfile.name}: no merge RUN"
    assert copy_ui < copy_script < run_match.start() < text.index("npx postcss")
    # the interpreter must be one this builder stage actually installs
    builder = text.split("\nFROM ")[0]
    interpreter = run_match.group(1)
    assert interpreter == "python3" or f"{interpreter} -m pip" in builder
