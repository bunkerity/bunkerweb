"""IGNORE_URI matches the normalized path only, and rDNS is skipped when no rDNS entry is configured.

Port of dev 1.6.18~rc1/rc2 (``d292954f9``, ``05fec4057``, ``c4a055f1e``, ``7ec69e89f``).

* ``ANTIBOT_IGNORE_URI`` / ``COUNTRY_IGNORE_URI`` were also matched against the raw ``request_uri``. NGINX
  routes ``//x``, ``/%78`` and ``/./x`` to the same location as ``/x`` while the raw string differs, so a
  negative-lookahead pattern such as ``^/(?!search)`` matched the raw variant of a protected path and the
  challenge / country block was skipped. Only the normalized path (alone, or joined with the query string)
  may match.
* ``is_*_ip`` of the list plugins and antibot ran a reverse DNS lookup per request even with no rDNS entry.
* ``is_safe_relative_path`` accepted aliases of the challenge URI (``/challenge/``, ``/./challenge``,
  ``/%63hallenge``), which loops the post-solve redirect back to the challenge.
* A failed first solve lost the ``next`` target (the form POSTs without ``?next=``).

The methods are spliced out of the shipped sources and run through the stand-alone ``lua`` binary.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
CORE = ROOT / "src" / "common" / "core"
LUA = shutil.which("lua") or shutil.which("luajit")
pytestmark = pytest.mark.skipif(LUA is None, reason="no stand-alone lua/luajit on PATH")


def _src(plugin):
    return (CORE / plugin / f"{plugin}.lua").read_text(encoding="utf-8")


def _method(plugin, name):
    match = re.search(rf"^function {plugin}:{name}\(.*?^end$", _src(plugin), re.S | re.M)
    assert match, f"{plugin}:{name}() not found"
    return match.group(0)


def _local_function(plugin, name):
    match = re.search(rf"^local function {name}\(.*?^end$", _src(plugin), re.S | re.M)
    assert match, f"local function {name}() not found in {plugin}"
    return match.group(0)


def _lua(script):
    assert LUA is not None
    result = subprocess.run([LUA, "-"], input=script, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, f"lua failed:\n{result.stdout}\n{result.stderr}"
    return result.stdout.strip()


# regex_match stub: a Lua pattern is not PCRE, so the patterns below are written as plain Lua patterns whose
# meaning is the same as the PCRE one named in each test.
REGEX_STUB = "local function regex_match(subject, pattern) return subject ~= nil and subject:find(pattern) ~= nil end"


def _ignored_uri(plugin, uri, request_uri, patterns):
    field = "lists" if plugin == "antibot" else "ignore_uri"
    holder = '{ ["IGNORE_URI"] = PATTERNS }' if plugin == "antibot" else "PATTERNS"
    literals = ", ".join(f"[==[{p}]==]" for p in patterns)
    return _lua(
        "\n".join(
            [
                REGEX_STUB,
                f"local {plugin} = {{}}",
                _method(plugin, "is_ignored_uri"),
                f"local PATTERNS = {{ {literals} }}",
                f"local self = {{ ctx = {{ bw = {{ uri = [==[{uri}]==], request_uri = [==[{request_uri}]==] }} }}, {field} = {holder} }}",
                f"print(tostring((({plugin}.is_ignored_uri(self)))))",
            ]
        )
    )


# Pattern meaning "everything but /search" (the PCRE ``^/(?!search)`` of the dev regression): a Lua pattern has
# no lookahead, so model it as "starts with / and the next char is not 's'".
NEG = "^/[^s]"


@pytest.mark.parametrize("plugin", ["antibot", "country"])
class TestIgnoreUriNormalizedOnly:
    def test_raw_variant_of_protected_path_is_not_ignored(self, plugin):
        """/search is the only path the negative pattern spares; the raw ``//search`` form routes to /search
        (uri normalized) and must not match through the raw string."""
        # normalized /search: pattern does not match; raw //search matches ^/[^s] ('/' is not 's').
        assert _ignored_uri(plugin, "/search", "//search", [NEG]) == "false"

    def test_percent_encoded_variant_is_not_ignored(self, plugin):
        assert _ignored_uri(plugin, "/search", "/%73earch", [NEG]) == "false"

    def test_dot_segment_variant_is_not_ignored(self, plugin):
        assert _ignored_uri(plugin, "/search", "/./search", [NEG]) == "false"

    def test_normalized_path_still_matches(self, plugin):
        assert _ignored_uri(plugin, "/health", "/health", ["^/health"]) == "true"

    def test_normalized_path_joined_with_query_still_matches(self, plugin):
        """A pattern written against ``/path?query`` keeps working: the normalized path is joined with the
        query string of the request."""
        assert _ignored_uri(plugin, "/x", "//x?token=abc", ["^/x%?token=abc$"]) == "true"

    def test_raw_path_does_not_match_even_with_query(self, plugin):
        assert _ignored_uri(plugin, "/search", "//search?a=1", ["^//search"]) == "false"


def _rdns_calls(plugin, method, lists, rdns_global="no"):
    var = {"antibot": "ANTIBOT_RDNS_GLOBAL", "blacklist": "BLACKLIST_RDNS_GLOBAL", "greylist": "GREYLIST_RDNS_GLOBAL", "whitelist": "WHITELIST_RDNS_GLOBAL"}[
        plugin
    ]
    list_lits = ", ".join(f'["{k}"] = {{ {", ".join(repr(v) for v in vals)} }}' for k, vals in lists.items())
    return _lua(
        "\n".join(
            [
                "local ERR = 3",
                "ngx = { ERR = 3 }",
                "local calls = 0",
                "local function get_rdns() calls = calls + 1; return { 'host.example.net' } end",
                "local function rdns_forward_confirmed() return nil end",
                "local ipm = { match = function() return false end }",
                "local function ipmatcher_new() return ipm end",
                "local ipmatcher = { new = ipmatcher_new }",
                f"local {plugin} = {{}}",
                _method(plugin, method),
                f"local self = {{ lists = {{ IP = {{}}, ASN = {{}}, IGNORE_IP = {{}}, IGNORE_ASN = {{}}, IGNORE_RDNS = {{}}, RDNS = {{}}, {list_lits} }},",
                f"  variables = {{ {var} = '{rdns_global}' }}, ip_matcher = ipm,",
                "  logger = { log = function() end },",
                "  ctx = { bw = { remote_addr = '1.2.3.4', ip_is_global = true, asn_number = nil } } }",
                f"{plugin}.{method}(self)",
                "print(calls)",
            ]
        )
    )


RDNS_CASES = [
    ("antibot", "is_ignored_ip", "IGNORE_RDNS"),
    ("blacklist", "is_blacklisted_ip", "RDNS"),
    ("greylist", "is_greylisted_ip", "RDNS"),
    ("whitelist", "is_whitelisted_ip", "RDNS"),
]


@pytest.mark.parametrize("plugin,method,key", RDNS_CASES)
class TestRdnsSkippedWithoutEntries:
    def test_no_lookup_without_rdns_entry(self, plugin, method, key):
        assert _rdns_calls(plugin, method, {}) == "0"

    def test_lookup_with_rdns_entry(self, plugin, method, key):
        assert _rdns_calls(plugin, method, {key: [".example.net"]}) == "1"


def _safe_path(p, antibot_uri="/challenge"):
    return _lua(
        "\n".join(
            [
                _local_function("antibot", "is_safe_relative_path"),
                f"local r = is_safe_relative_path([==[{p}]==], [==[{antibot_uri}]==])",
                "print(tostring(r))",
            ]
        )
    )


class TestChallengeAliasLoop:
    @pytest.mark.parametrize("alias", ["/./challenge", "/%63hallenge", "/a/../challenge", "/%2e/challenge", "/a/%2e%2e/challenge", "/a\\..\\challenge"])
    def test_alias_of_the_challenge_is_refused(self, alias):
        assert _safe_path(alias) == "nil"

    @pytest.mark.parametrize("alias", ["/ch/", "/./ch/", "/%63h/", "/x/../ch/", "/ch/."])
    def test_alias_of_a_trailing_slash_challenge_is_refused(self, alias):
        assert _safe_path(alias, "/ch/") == "nil"

    def test_ordinary_path_is_kept(self):
        assert _safe_path("/page?x=1") == "/page?x=1"

    def test_similar_prefix_is_kept(self):
        assert _safe_path("/challenge2") == "/challenge2"

    def test_parent_of_the_challenge_is_kept(self):
        assert _safe_path("/challenge/..") == "/challenge/.."


class TestFailedSolveKeepsNext:
    def test_get_original_uri_reads_post_next_and_restores_session_query(self):
        src = _method("antibot", "get_original_uri")
        assert "get_post_args" in src, "a failed solve (POST without ?next=) must recover next from the form"
        assert "session_data.original_uri" in src, "the session query must be restored after a failed solve"
