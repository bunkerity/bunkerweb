"""``cache_partition.lua`` runs, instead of being stubbed away everywhere.

It is the module the port of dev ``c54c49e7e`` rewrote, and until now nothing loaded it: both Lua
harnesses that reach it (``test_crowdsec_defer_lua``, ``test_crowdsec_init_health_lua``) replace it
through ``package.loaded``, because it requires ``resty.sha256`` and ``resty.string``, which the
plain ``lua`` binary has not got. Two ``package.preload`` shims are enough to load the shipped file
unchanged, and they buy two things a real digest could not:

* the hash is the **identity**, so a prefix reads as the string that was hashed and a test can say
  *which* inputs were framed into it rather than comparing two opaque hex blobs;
* the hash can be made **constant**, which is the only way to reach the collision arm of
  ``prefixes()`` at all -- with a real SHA-256 it is dead code under test.

What is deliberately NOT asserted here: that SHA-256 is the digest. That is a one-line `require`
and a review question, not something a shim can honestly check.
"""

import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

ROOT = Path(__file__).resolve().parents[3]
CACHE_PARTITION_LUA = ROOT / "src" / "common" / "core" / "crowdsec" / "cache_partition.lua"

pytestmark = pytest.mark.skipif(shutil.which("lua") is None, reason="the lua interpreter is not installed")

SOURCE = CACHE_PARTITION_LUA.read_text(encoding="utf-8")

HARNESS = """
-- The digest is the fixture, not the subject. HASH = identity makes a prefix legible; HASH =
-- constant is what makes two distinct Local APIs land in one namespace, which is the only way to
-- reach the collision arm.
package.preload["resty.sha256"] = function()
  local sha = {}
  sha.__index = sha
  function sha.new() return setmetatable({ buf = "" }, sha) end
  function sha:update(chunk) self.buf = self.buf .. chunk return true end
  function sha:final() return HASH(self.buf) end
  return sha
end
package.preload["resty.string"] = function()
  return { to_hex = function(raw) return raw end }
end

local cache_partition = dofile([==[%(lua)s]==])

%(body)s
"""

IDENTITY = "function(raw) return raw end"
CONSTANT = 'function() return "same" end'


def run(body: str, *, hash_fn: str = IDENTITY, source: str | None = None) -> subprocess.CompletedProcess:
    lua_path = CACHE_PARTITION_LUA
    with TemporaryDirectory() as tmp:
        if source is not None:
            lua_path = Path(tmp) / "cache_partition.lua"
            lua_path.write_text(source, encoding="utf-8")
        script = f"HASH = {hash_fn}\n" + HARNESS % {"lua": str(lua_path), "body": body}
        return subprocess.run(["lua", "-e", script], capture_output=True, text=True)


def field(out: str, key: str) -> str:
    for line in out.splitlines():
        if line.startswith(key + "="):
            return line.split("=", 1)[1]
    raise AssertionError(f"{key} missing from:\n{out}")


class TestTheLocalApiPrefix:
    def test_two_local_apis_never_share_a_namespace(self):
        res = run("""
print("A=" .. cache_partition.prefix_for("http://a:8080"))
print("B=" .. cache_partition.prefix_for("http://b:8080"))
""")
        assert res.returncode == 0, res.stderr
        assert field(res.stdout, "A") != field(res.stdout, "B")

    def test_the_prefix_depends_on_that_api_alone(self):
        """The whole point of the hash, and it has to be asserted by **varying the siblings**: a
        positional prefix shifted for every untouched service the moment another service's Local API
        was added, removed or replaced, so a reload silently pointed an untouched service at another
        service's cached decisions.

        Comparing two identical calls would prove nothing -- any pure function of one argument passes
        that, a constant included (found by Criticos round 2)."""
        res = run("""
local alone = cache_partition.prefixes({ "http://a:8080" })
local crowded = cache_partition.prefixes({ "http://a:8080", "http://b:8080", "http://c:8080" })
-- a is no longer first, and its siblings are different ones: a positional scheme moves it here.
local reordered = cache_partition.prefixes({ "http://z:8080", "http://a:8080" })
print("ALONE=" .. alone["http://a:8080"])
print("CROWDED=" .. crowded["http://a:8080"])
print("REORDERED=" .. reordered["http://a:8080"])
print("SIBLING=" .. crowded["http://b:8080"])
""")
        assert res.returncode == 0, res.stderr
        a = field(res.stdout, "ALONE")
        assert field(res.stdout, "CROWDED") == a
        assert field(res.stdout, "REORDERED") == a
        # ... and it is a real namespace, not one constant shared by the whole fleet: without this
        # the assertions above hold for `prefix_for = function() return "v2|c|" end`.
        assert field(res.stdout, "SIBLING") != a

    def test_trailing_slashes_are_normalized_away(self):
        """The only variance seen between an env value and a rendered default."""
        res = run("""
print("BARE=" .. cache_partition.normalize("http://a:8080"))
print("SLASHED=" .. cache_partition.normalize("http://a:8080///"))
""")
        assert field(res.stdout, "BARE") == field(res.stdout, "SLASHED") == "http://a:8080"

    def test_the_namespace_is_versioned(self):
        """`v2|` is what stops a legacy 32-bit namespace being trusted after an upgrade; the dict is
        never flushed, the old decisions just expire."""
        res = run('print("P=" .. cache_partition.prefix_for("http://a:8080"))')
        assert field(res.stdout, "P").startswith("v2|")
        assert field(res.stdout, "P").endswith("|")


class TestTheChallengePrefixIsLengthFramed:
    """`#scope .. ":" .. scope .. #content .. ":" .. content` -- the framing exists so that two
    different (scope, content) pairs cannot concatenate into the same string."""

    AMBIGUOUS = """
print("AB_C=" .. cache_partition.challenge_prefix("ab", "c", ""))
print("A_BC=" .. cache_partition.challenge_prefix("a", "bc", ""))
"""

    def test_an_ambiguous_split_still_gives_two_namespaces(self):
        res = run(self.AMBIGUOUS)
        assert res.returncode == 0, res.stderr
        assert field(res.stdout, "AB_C") != field(res.stdout, "A_BC")

    def test_dropping_the_framing_collides_them(self):
        """Mutation: concatenate without the lengths and `("ab", "c")` becomes `("a", "bc")` -- one
        challenge namespace for two services."""
        mutated = SOURCE.replace(
            '.. cache_partition.hash(#scope .. ":" .. scope .. #content .. ":" .. content .. (captcha_template or ""))',
            '.. cache_partition.hash(scope .. content .. (captcha_template or ""))',
        )
        assert mutated != SOURCE, "the length framing no longer reads as expected -- update this mutation"
        res = run(self.AMBIGUOUS, source=mutated)
        assert field(res.stdout, "AB_C") == field(res.stdout, "A_BC")

    def test_the_captcha_template_is_part_of_it(self):
        """A provider, key or policy change has to invalidate the challenges issued under the old
        one, or a captcha solved against the previous configuration keeps working."""
        res = run("""
print("T1=" .. cache_partition.challenge_prefix("a", "conf", "tpl-1"))
print("T2=" .. cache_partition.challenge_prefix("a", "conf", "tpl-2"))
print("NONE=" .. cache_partition.challenge_prefix("a", "conf", nil))
""")
        assert field(res.stdout, "T1") != field(res.stdout, "T2")
        assert field(res.stdout, "NONE") not in (field(res.stdout, "T1"), field(res.stdout, "T2"))


class TestThePrefixMap:
    FLEET = """
local prefixes, count = cache_partition.prefixes(URLS)
if not prefixes then
  print("REFUSED=" .. tostring(count))
else
  print("COUNT=" .. tostring(count))
  local keys = {}
  for url in pairs(prefixes) do keys[#keys + 1] = url end
  table.sort(keys)
  for _, url in ipairs(keys) do print("MAP=" .. url .. " -> " .. prefixes[url]) end
end
"""

    @staticmethod
    def _fleet(urls: list[str]) -> str:
        return "URLS = { " + ", ".join(f"[==[{u}]==]" for u in urls) + " }\n" + TestThePrefixMap.FLEET

    def test_two_local_apis_are_counted_and_mapped(self):
        res = run(self._fleet(["http://a:8080", "http://b:8080"]))
        assert res.returncode == 0, res.stderr
        assert field(res.stdout, "COUNT") == "2"

    def test_a_configuration_without_a_local_api_is_neither_counted_nor_mapped(self):
        """It does no decision lookup at all, so it cannot bleed into anything -- and counting it
        would partition the common `AppSec everywhere, Local API on a subset` fleet for nothing."""
        out = run(self._fleet(["http://a:8080", "", ""])).stdout
        assert field(out, "COUNT") == "1"
        assert [line for line in out.splitlines() if line.startswith("MAP=")] == ["MAP=http://a:8080 -> v2|http://a:8080|"]

    def test_the_only_local_api_in_a_fleet_still_gets_a_prefix(self):
        """So that adding a second one later never changes the key space of the first."""
        assert field(run(self._fleet(["http://a:8080"])).stdout, "COUNT") == "1"

    def test_the_same_api_written_twice_is_one_namespace(self):
        out = run(self._fleet(["http://a:8080", "http://a:8080/"])).stdout
        assert field(out, "COUNT") == "1"
        maps = [line.split(" -> ")[1] for line in out.splitlines() if line.startswith("MAP=")]
        assert len(set(maps)) == 1, maps


class TestACollisionIsRefused:
    """Unreachable with a real digest, which is exactly why it needs a constant one to be tested at
    all: silently mapping two Local APIs onto one namespace is the failure this arm exists to stop,
    and `crowdsec:init()` turns the refusal into a fleet-wide `no bouncer loaded`."""

    FLEET = "URLS = { [==[http://a:8080]==], [==[http://b:8080]==] }\n" + TestThePrefixMap.FLEET

    def test_two_apis_hashing_alike_are_refused(self):
        res = run(self.FLEET, hash_fn=CONSTANT)
        assert res.returncode == 0, res.stderr
        assert field(res.stdout, "REFUSED") == "CrowdSec cache namespace collision"

    def test_without_the_refusal_they_silently_share_one_namespace(self):
        """Mutation: return the map anyway. Two services then read each other's decisions -- an
        allow cached for one Local API answers a request checked against the other."""
        mutated = SOURCE.replace(
            '\t\t\t\treturn nil, "CrowdSec cache namespace collision"\n',
            "",
        )
        assert mutated != SOURCE, "the collision refusal no longer reads as expected -- update this mutation"
        res = run(self.FLEET, hash_fn=CONSTANT, source=mutated)
        assert field(res.stdout, "COUNT") == "2"
        maps = [line.split(" -> ")[1] for line in res.stdout.splitlines() if line.startswith("MAP=")]
        assert len(set(maps)) == 1, "both Local APIs landed in the one namespace"

    def test_the_same_api_repeated_is_not_a_collision(self):
        """The arm compares the *normalized* owner, so one API written two ways must not trip it."""
        res = run("URLS = { [==[http://a:8080]==], [==[http://a:8080//]==] }\n" + TestThePrefixMap.FLEET, hash_fn=CONSTANT)
        assert field(res.stdout, "COUNT") == "1"


class TestTheApiUrlIsReadOffTheRenderedConfiguration:
    @staticmethod
    def _read(content: str) -> str:
        return field(run(f'print("URL=" .. cache_partition.api_url([==[{content}]==]))').stdout, "URL")

    def test_a_commented_out_local_api_is_not_the_local_api(self):
        """The anchor is what makes it line-*start* matching. Without it the first line containing
        the key anywhere wins, and a commented-out or prefixed key silently decides the cache
        namespace -- pointing the service at a partition nothing else uses.

        The previous fixture here paired `APPSEC_URL` with `API_URL` and asserted the right answer;
        it could not fail, because `APPSEC_URL` does not contain `API_URL` as a substring, so
        anchored and unanchored agree on it (found by Criticos round 2)."""
        assert self._read("# API_URL=http://stale:8080\nAPI_URL=http://lapi:8080\n") == "http://lapi:8080"

    def test_a_different_setting_ending_in_the_same_key_is_not_it(self):
        assert self._read("CROWDSEC_API_URL=http://wrong:8080\nAPI_URL=http://lapi:8080\n") == "http://lapi:8080"

    def test_appsec_url_is_never_mistaken_for_it(self):
        """Different endpoints, and only one of them partitions the decision cache."""
        assert self._read("APPSEC_URL=http://appsec:7422\nAPI_URL=http://lapi:8080\n") == "http://lapi:8080"

    def test_appsec_only_configurations_report_no_local_api(self):
        assert self._read("APPSEC_URL=http://appsec:7422\n") == ""

    def test_surrounding_whitespace_is_stripped(self):
        assert self._read("  API_URL = http://lapi:8080  \n") == "http://lapi:8080"

    def test_the_first_local_api_line_wins(self):
        assert self._read("API_URL=http://one:8080\nAPI_URL=http://two:8080\n") == "http://one:8080"
