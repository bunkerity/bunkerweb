"""An explicit ``*.example.com`` in ``SERVER_NAME`` is a scope the operator chose: grouping keeps it (dev 792031c99, #3326).

``certbot-new.py`` strips the ``*.`` of every name before grouping, so ``*.a.example.com`` +
``b.example.com`` collapsed into one ``example.com`` lineage and the ``a.example.com`` scope the
operator asked for was never issued; ``*.example.com`` + ``a.b.example.com`` was refused as a whole
group (a wildcard covers one label) although the explicit scope plainly asks for ``example.com``.
Now every explicit scope is its own group and the names it already covers are not grouped again.

``letsencrypt.lua`` mirrors the grouping to publish the certificate identifiers ("Mirror certbot-new
wildcard grouping so certificate identifiers stay in sync"). A mirror that drifts serves the wrong
lineage, so the Lua side is run on the same inputs and must produce the same groups as the job.
The Lua mirror also lacked the refusal of a group a wildcard cannot cover (``a.b.example.com`` next
to ``example.com``), which the job already applies: the parity cases include it.
"""

from collections import defaultdict
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Set, Tuple  # noqa: F401  (the extracted signatures annotate with these)

import pytest

ROOT = Path(__file__).resolve().parents[3]
JOB = ROOT / "src" / "common" / "core" / "letsencrypt" / "jobs" / "certbot-new.py"
LE_LUA = ROOT / "src" / "common" / "core" / "letsencrypt" / "letsencrypt.lua"

LUA = shutil.which("lua") or shutil.which("lua5.4") or shutil.which("luajit")


class _Logger:
    def __init__(self):
        self.errors: List[str] = []

    def error(self, message):
        self.errors.append(str(message))

    def warning(self, _message):
        pass


def _job_grouping():
    """exec just the grouping functions of the job (it is a script: importing it would run it)."""
    source = JOB.read_text(encoding="utf-8")
    chunks = []
    for pattern, what in (
        (r"^def extract_wildcard_groups\(.*?\n(?=\n\ndef |\n\n[A-Za-z_])", "extract_wildcard_groups"),
        (r"^def _determine_wildcard_bases\(.*?\n(?=\n\ndef |\n\n[A-Za-z_])", "_determine_wildcard_bases"),
    ):
        found = re.search(pattern, source, re.S | re.M)
        assert found, f"{what} not found in certbot-new.py -- renamed or restructured?"
        chunks.append(found.group(0))
    logger = _Logger()
    namespace = {"defaultdict": defaultdict, "LOGGER": logger, "Dict": Dict, "List": List, "Set": Set, "Tuple": Tuple}
    exec("\n".join(chunks), namespace)  # noqa: S102  -- the code under test, read from the repo
    return namespace["extract_wildcard_groups"], logger


def _lua_grouping(domains: List[str]) -> Dict[str, List[str]]:
    """Run the Lua mirror (`build_wildcard_groups` and its two helpers, lifted verbatim)."""
    source = LE_LUA.read_text(encoding="utf-8")
    functions = []
    for name in ("sanitize_domain_labels", "determine_wildcard_bases", "build_wildcard_groups"):
        found = re.search(rf"^local function {name}\(.*?^end$", source, re.S | re.M)
        assert found, f"{name} not found in letsencrypt.lua -- renamed or removed?"
        functions.append(found.group(0))
    script = (
        "local insert, sort, lower, gsub, sub = table.insert, table.sort, string.lower, string.gsub, string.sub\n"
        "local ipairs, pairs = ipairs, pairs\n" + "\n".join(functions) + """
local domains = {}
for domain in arg[1]:gmatch("[^,]+") do domains[#domains + 1] = domain end
local groups = build_wildcard_groups(domains)
local bases = {}
for base in pairs(groups) do bases[#bases + 1] = base end
sort(bases)
local out = {}
for _, base in ipairs(bases) do
    local names = {}
    for _, name in ipairs(groups[base]) do names[#names + 1] = '"' .. name .. '"' end
    out[#out + 1] = '"' .. base .. '":[' .. table.concat(names, ",") .. "]"
end
print("{" .. table.concat(out, ",") .. "}")
"""
    )
    assert LUA is not None
    result = subprocess.run([LUA, "-", ",".join(domains)], input=script, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


@pytest.fixture
def grouping():
    return _job_grouping()


EXPLICIT_SCOPE_CASES = [
    # An explicit scope is its own group, whatever else is listed next to it.
    (["*.a.example.com", "b.example.com"], {"a.example.com": ["*.a.example.com", "a.example.com"], "example.com": ["*.example.com", "example.com"]}),
    (
        ["*.b.example.com", "example.com", "a.example.com"],
        {"b.example.com": ["*.b.example.com", "b.example.com"], "example.com": ["*.example.com", "example.com"]},
    ),
    # The explicit scope covers a name one label deeper only through its own group: the other names
    # are no longer refused as a whole.
    (
        ["*.example.com", "a.b.example.com"],
        {"example.com": ["*.example.com", "example.com"], "b.example.com": ["*.b.example.com", "b.example.com"]},
    ),
    # Names an explicit scope already covers are not grouped again.
    (["*.example.com", "example.com", "a.example.com"], {"example.com": ["*.example.com", "example.com"]}),
    (["*.example.com", "www.example.com", "api.example.com"], {"example.com": ["*.example.com", "example.com"]}),
    (["*.example.com"], {"example.com": ["*.example.com", "example.com"]}),
    # Explicit scopes of two domains do not touch each other.
    (
        ["*.example.com", "*.example.org", "x.example.org"],
        {"example.com": ["*.example.com", "example.com"], "example.org": ["*.example.org", "example.org"]},
    ),
]

# No explicit scope: the grouping is unchanged, including the refusal of an uncoverable group.
UNCHANGED_CASES = [
    (["a.example.com", "b.example.com"], {"example.com": ["*.example.com", "example.com"]}),
    (["example.com", "a.example.com"], {"example.com": ["*.example.com", "example.com"]}),
    (["example.com", "a.b.example.com"], {}),
    (["example.com", "a.b.example.com", "x.example.org"], {"example.org": ["*.example.org", "example.org"]}),
    (["a.example.com", "a.example.org"], {"example.com": ["*.example.com", "example.com"], "example.org": ["*.example.org", "example.org"]}),
]


@pytest.mark.parametrize("domains, expected", EXPLICIT_SCOPE_CASES)
def test_the_job_keeps_every_explicit_scope(grouping, domains, expected):
    extract, logger = grouping
    assert extract(domains, "svc") == expected
    assert logger.errors == [], "an explicit scope must not be refused as an uncoverable group"


@pytest.mark.parametrize("domains, expected", UNCHANGED_CASES)
def test_the_job_grouping_is_unchanged_without_an_explicit_scope(grouping, domains, expected):
    extract, _ = grouping
    assert extract(domains, "svc") == expected


@pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")
@pytest.mark.parametrize("domains, expected", EXPLICIT_SCOPE_CASES + UNCHANGED_CASES)
def test_the_lua_mirror_publishes_the_same_groups_as_the_job(grouping, domains, expected):
    """The identifiers the Lua side publishes are the lineage names the job issued."""
    extract, _ = grouping
    assert _lua_grouping(domains) == extract(domains, "svc") == expected
