"""Behaviour of ``src/common/core/crowdsec/cache_partition.lua``, the real file run under plain Lua.

The module derives the key space each Local API gets in the shared CrowdSec decision cache. What an
operator relies on is that a prefix depends on its own Local API alone, that equivalent spellings of
the URL share one prefix, that a changed policy changes the fingerprint, and that two distinct APIs
can never silently share a prefix. ``resty.sha256`` is a pure-Lua SHA-256 (compared with ``hashlib``
below), ``resty.string`` and ``cjson`` are minimal stand-ins from ``_lua_state_helpers.py``.
"""

import hashlib

import pytest
from _lua_state_helpers import BASE_LUA, CORE, LUA, last_json, module_path, run_lua, to_lua  # type: ignore

pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")

MODULE = module_path("CROWDSEC_CACHE_PARTITION", CORE / "crowdsec" / "cache_partition.lua")

STUBS = r"""
package.loaded["resty.sha256"] = {
    new = function()
        local parts = {}
        return {
            update = function(_, chunk) parts[#parts + 1] = chunk return true end,
            final = function()
                if CONSTANT_DIGEST then return string.rep("\1", 32) end
                return SHA256(table.concat(parts))
            end,
        }
    end,
}
package.loaded["resty.string"] = {
    to_hex = function(raw) return (raw:gsub(".", function(c) return string.format("%02x", c:byte()) end)) end,
}
package.loaded["cjson"] = json
"""


def run(body: str, *, constant_digest: bool = False):
    prefix = f"CONSTANT_DIGEST = {'true' if constant_digest else 'false'}\n"
    script = BASE_LUA + STUBS + prefix + f'\nlocal cp = dofile("{MODULE}")\n' + body
    return last_json(run_lua(script))


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


class TestHash:
    @pytest.mark.parametrize("text", ["", "abc", "http://lapi:8080", "x" * 200])
    def test_hash_is_the_hex_sha256_of_its_input(self, text):
        assert run(f"emit(cp.hash({to_lua(text)}))") == sha(text)


class TestApiUrl:
    def test_the_local_api_line_is_found_and_trimmed(self):
        content = "MODE=live\n  API_URL =  http://lapi:8080/  \nAPI_KEY=k\n"
        assert run(f"emit(cp.api_url({to_lua(content)}))") == "http://lapi:8080/"

    def test_appsec_url_is_never_mistaken_for_the_local_api(self):
        content = "APPSEC_URL=http://appsec:7422\nMODE=live\n"
        assert run(f"emit(cp.api_url({to_lua(content)}))") == ""

    def test_the_first_local_api_line_wins(self):
        content = "API_URL=http://one\nAPI_URL=http://two\n"
        assert run(f"emit(cp.api_url({to_lua(content)}))") == "http://one"

    def test_a_configuration_without_a_local_api_yields_an_empty_string(self):
        assert run('emit(cp.api_url(""))') == ""


class TestNormalize:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("http://lapi:8080", "http://lapi:8080"),
            ("http://lapi:8080/", "http://lapi:8080"),
            ("http://lapi:8080///", "http://lapi:8080"),
            ("http://lapi:8080/v1/", "http://lapi:8080/v1"),
            ("", ""),
        ],
    )
    def test_only_trailing_slashes_are_removed(self, raw, expected):
        assert run(f"emit(cp.normalize({to_lua(raw)}))") == expected


class TestPrefixFor:
    def test_the_prefix_is_versioned_and_derived_from_the_normalized_url(self):
        assert run('emit(cp.prefix_for("http://lapi:8080"))') == f"v2|{sha('http://lapi:8080')}|"

    def test_equivalent_spellings_share_one_prefix(self):
        out = run('emit({ cp.prefix_for("http://lapi:8080"), cp.prefix_for("http://lapi:8080/") })')
        assert out[0] == out[1]

    def test_a_prefix_does_not_depend_on_any_other_api(self):
        # positional prefixes would shift when a sibling is added; a hash of the API alone cannot
        alone = run('emit(cp.prefixes({ "http://a:8080" }))')
        with_sibling = run('emit(cp.prefixes({ "http://b:8080", "http://a:8080", "http://c:8080" }))')
        assert alone["http://a:8080"] == with_sibling["http://a:8080"]

    def test_two_apis_never_share_a_prefix(self):
        out = run('emit({ cp.prefix_for("http://a:8080"), cp.prefix_for("http://b:8080") })')
        assert out[0] != out[1]


class TestPrefixes:
    def test_every_api_gets_a_prefix_and_the_distinct_count_is_returned(self):
        out = run('local p, n = cp.prefixes({ "http://a:8080", "http://b:8080" }); emit({ p = p, n = n })')
        assert out["n"] == 2
        assert out["p"] == {
            "http://a:8080": f"v2|{sha('http://a:8080')}|",
            "http://b:8080": f"v2|{sha('http://b:8080')}|",
        }

    def test_a_single_api_still_gets_a_prefix(self):
        # otherwise adding a second Local API later would change the first one's key space
        out = run('local p, n = cp.prefixes({ "http://a:8080" }); emit({ p = p, n = n })')
        assert out["n"] == 1
        assert out["p"] == {"http://a:8080": f"v2|{sha('http://a:8080')}|"}

    def test_configurations_without_a_local_api_get_no_prefix_and_are_not_counted(self):
        out = run('local p, n = cp.prefixes({ "", "http://a:8080", "" }); emit({ p = p, n = n })')
        assert out["n"] == 1
        assert list(out["p"]) == ["http://a:8080"]

    def test_spellings_of_one_api_share_a_prefix_and_count_once(self):
        out = run('local p, n = cp.prefixes({ "http://a:8080", "http://a:8080/" }); emit({ p = p, n = n })')
        assert out["n"] == 1
        assert out["p"]["http://a:8080"] == out["p"]["http://a:8080/"]

    def test_a_repeated_url_is_counted_once(self):
        out = run('local p, n = cp.prefixes({ "http://a:8080", "http://a:8080" }); emit({ p = p, n = n })')
        assert out["n"] == 1

    def test_a_namespace_collision_between_distinct_apis_is_refused(self):
        out = run(
            'local p, err = cp.prefixes({ "http://a:8080", "http://b:8080" }); emit({ p = p == nil, err = err })',
            constant_digest=True,
        )
        assert out == {"p": True, "err": "CrowdSec cache namespace collision"}

    def test_no_apis_at_all_gives_an_empty_map(self):
        out = run("local p, n = cp.prefixes({}); emit({ n = n, empty = next(p) == nil })")
        assert out == {"n": 0, "empty": True}


class TestFingerprint:
    BASE = '{ API_URL = "http://a:8080", API_KEY = "k", BOUNCING_ON_TYPE = "all", FALLBACK_REMEDIATION = "ban", MODE = "live", CACHE_EXPIRATION = "1" }'

    def fingerprint(self, **changes):
        overrides = "".join(f"conf.{key} = {to_lua(value)}\n" for key, value in changes.items())
        return run(f"local conf = {self.BASE}\n{overrides}emit(cp.fingerprint(conf))")

    def test_the_fingerprint_is_stable(self):
        assert self.fingerprint() == self.fingerprint()

    def test_a_trailing_slash_on_the_api_does_not_change_it(self):
        assert self.fingerprint(API_URL="http://a:8080/") == self.fingerprint()

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("API_URL", "http://b:8080"),
            ("API_KEY", "other"),
            ("BOUNCING_ON_TYPE", "ban"),
            ("FALLBACK_REMEDIATION", "captcha"),
            ("MODE", "stream"),
            ("CACHE_EXPIRATION", "60"),
        ],
    )
    def test_every_policy_field_changes_it(self, field, value):
        assert self.fingerprint(**{field: value}) != self.fingerprint()


class TestFingerprints:
    CONF = '{ API_URL = "%s", API_KEY = "%s", MODE = "%s" }'

    def run(self, *confs):
        listing = ", ".join(self.CONF % conf for conf in confs)
        return run(f"emit(cp.fingerprints({{ {listing} }}))")

    def test_one_fingerprint_is_published_per_api(self):
        out = self.run(("http://a:8080", "k1", "live"), ("http://b:8080", "k2", "live"))
        assert sorted(out) == ["http://a:8080", "http://b:8080"]
        assert out["http://a:8080"] != out["http://b:8080"]

    def test_several_bouncers_with_one_policy_share_the_api_fingerprint(self):
        single = self.run(("http://a:8080", "k1", "live"))
        doubled = self.run(("http://a:8080", "k1", "live"), ("http://a:8080/", "k1", "live"))
        assert doubled == single

    def test_the_order_of_the_configurations_does_not_matter(self):
        one = self.run(("http://a:8080", "k1", "live"), ("http://a:8080", "k2", "stream"))
        two = self.run(("http://a:8080", "k2", "stream"), ("http://a:8080", "k1", "live"))
        assert one == two

    def test_a_second_policy_on_the_same_api_changes_the_fingerprint(self):
        single = self.run(("http://a:8080", "k1", "live"))
        mixed = self.run(("http://a:8080", "k1", "live"), ("http://a:8080", "k1", "stream"))
        assert mixed["http://a:8080"] != single["http://a:8080"]


class TestChallengePrefix:
    @pytest.mark.parametrize(
        ("scope", "content", "template"),
        [("svc", "conf", "tpl"), ("svc", "conf", None), ("a:b", "1:c", "")],
    )
    def test_the_prefix_hashes_the_length_framed_scope_content_and_template(self, scope, content, template):
        framed = str(len(scope)) + ":" + scope + str(len(content)) + ":" + content + (template or "")
        expected = "captcha-v2|" + sha(framed) + "|"
        out = run(f"emit(cp.challenge_prefix({to_lua(scope)}, {to_lua(content)}, {to_lua(template)}))")
        assert out == expected

    def test_length_framing_keeps_shifted_boundaries_apart(self):
        out = run('emit({ cp.challenge_prefix("ab", "c"), cp.challenge_prefix("a", "bc") })')
        assert out[0] != out[1]

    def test_a_changed_configuration_changes_the_prefix(self):
        out = run('emit({ cp.challenge_prefix("svc", "key=1"), cp.challenge_prefix("svc", "key=2") })')
        assert out[0] != out[1]
