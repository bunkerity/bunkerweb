"""Behaviour of ``src/bw/lua/bunkerweb/acme.lua``, the real file run under plain Lua.

``is_challenge_uri`` is the cheap prefix gate both access hooks run on every request; ``is_http_challenge``
decides whether a request is an HTTP-01 challenge BunkerWeb itself must answer: right token shape, the
Let's Encrypt settings that make BunkerWeb the responder, and a non-empty token file in the jobs' challenge
directory. ``bunkerweb.utils.get_variable`` is a stand-in driven by ``VARS``; the challenge directory is
redirected into ``tmp_path`` so the file checks (missing, empty, directory) are real filesystem answers.
"""

import pytest
from _lua_core_helpers import BW_MODULES, LUA, module_path, run_core  # type: ignore

pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")

MODULE = module_path("ACME", BW_MODULES / "acme.lua")

PREFIX = "/.well-known/acme-challenge/"
GOOD_VARS = {"AUTO_LETS_ENCRYPT": "yes", "LETS_ENCRYPT_CHALLENGE": "http", "LETS_ENCRYPT_PASSTHROUGH": "no"}

STUBS = """
VAR_CALLS = {}
local real_open = io.open
local CHALLENGE_DIR = "/var/tmp/bunkerweb/lets-encrypt/"
io.open = function(path, mode)
    OPENED = path
    if path:sub(1, #CHALLENGE_DIR) == CHALLENGE_DIR then path = FS_ROOT .. "/" .. path:sub(#CHALLENGE_DIR + 1) end
    return real_open(path, mode)
end
package.loaded["bunkerweb.utils"] = {
    get_variable = function(name, site_search, ctx)
        VAR_CALLS[#VAR_CALLS + 1] = { name, site_search, ctx }
        local value = VARS[name]
        if value == nil then return nil, "not found" end
        return value, "success"
    end,
}
local acme = dofile(MODULE)
"""


@pytest.fixture
def challenge_dir(tmp_path):
    path = tmp_path / ".well-known" / "acme-challenge"
    path.mkdir(parents=True)
    return path


def run(body, tmp_path, **vars_):
    values = {**GOOD_VARS, **vars_}
    return run_core(MODULE, STUBS + body, FS_ROOT=str(tmp_path), VARS={k: v for k, v in values.items() if v is not None})


def http(tmp_path, uri, **vars_):
    return run(f"emit(acme.is_http_challenge({{ bw = {{ uri = {uri!r} }} }}))".replace("'", '"'), tmp_path, **vars_)


class TestIsChallengeUri:
    @pytest.mark.parametrize(
        ("uri", "expected"),
        [
            (PREFIX + "token", True),
            (PREFIX, True),
            (PREFIX + "a/b", True),
            ("/.well-known/acme-challenge", False),
            ("/.well-known/acme-challenge-x/token", False),
            ("/.Well-Known/acme-challenge/token", False),
            ("/other/.well-known/acme-challenge/token", False),
            ("/", False),
            ("", False),
        ],
    )
    def test_only_the_challenge_prefix_matches(self, tmp_path, uri, expected):
        assert run(f"emit(acme.is_challenge_uri({{ bw = {{ uri = {uri!r} }} }}))".replace("'", '"'), tmp_path) is expected

    @pytest.mark.parametrize("ctx", ["nil", "{}", "{ bw = {} }", "{ bw = { uri = 42 } }", "{ bw = { uri = false } }"])
    def test_a_context_without_a_string_uri_is_not_a_challenge(self, tmp_path, ctx):
        assert run(f"emit(acme.is_challenge_uri({ctx}))", tmp_path) is False

    def test_no_setting_is_read_for_the_prefix_check(self, tmp_path):
        out = run(f'acme.is_challenge_uri({{ bw = {{ uri = "{PREFIX}tok" }} }}) emit(#VAR_CALLS)', tmp_path)
        assert out == 0


class TestIsHttpChallenge:
    def test_a_token_with_a_non_empty_file_is_a_challenge(self, tmp_path, challenge_dir):
        (challenge_dir / "tok-en_1").write_text("tok-en_1.thumbprint")
        assert http(tmp_path, PREFIX + "tok-en_1") is True

    @pytest.mark.parametrize("uri", ["/", "/index.html", "/.well-known/other/token", PREFIX[:-1]])
    def test_a_request_outside_the_challenge_path_is_never_one(self, tmp_path, challenge_dir, uri):
        (challenge_dir / "token").write_text("x")
        assert http(tmp_path, uri) is False

    def test_a_request_outside_the_challenge_path_reads_no_setting_and_opens_no_file(self, tmp_path):
        out = run('emit({ is = acme.is_http_challenge({ bw = { uri = "/x" } }), vars = #VAR_CALLS, opened = OPENED })', tmp_path)
        assert out == {"is": False, "vars": 0}

    @pytest.mark.parametrize(
        "token",
        ["", "../etc/passwd", "a/b", "tok.en", "tok en", "tok%2e", "tok\\n", "a..", "..", "tok\\0x"],
    )
    def test_a_token_outside_the_allowed_alphabet_is_refused_without_touching_the_disk(self, tmp_path, token):
        out = run(f'emit({{ is = acme.is_http_challenge({{ bw = {{ uri = "{PREFIX}{token}" }} }}), opened = OPENED }})', tmp_path)
        assert out == {"is": False}

    @pytest.mark.parametrize(
        "override",
        [
            {"AUTO_LETS_ENCRYPT": "no"},
            {"AUTO_LETS_ENCRYPT": None},
            {"LETS_ENCRYPT_CHALLENGE": "dns"},
            {"LETS_ENCRYPT_CHALLENGE": None},
            {"LETS_ENCRYPT_PASSTHROUGH": "yes"},
            {"LETS_ENCRYPT_PASSTHROUGH": None},
        ],
    )
    def test_every_letsencrypt_switch_must_make_bunkerweb_the_responder(self, tmp_path, challenge_dir, override):
        (challenge_dir / "token").write_text("x")
        assert http(tmp_path, PREFIX + "token", **override) is False

    def test_the_switches_are_read_for_the_current_service(self, tmp_path, challenge_dir):
        (challenge_dir / "token").write_text("x")
        out = run(
            f"""
local ctx = {{ bw = {{ uri = "{PREFIX}token" }} }}
acme.is_http_challenge(ctx)
local out = {{}}
for _, call in ipairs(VAR_CALLS) do out[#out + 1] = {{ call[1], call[2], call[3] == ctx }} end
emit(out)
""",
            tmp_path,
        )
        assert out == [[name, True, True] for name in ("AUTO_LETS_ENCRYPT", "LETS_ENCRYPT_CHALLENGE", "LETS_ENCRYPT_PASSTHROUGH")]

    @pytest.mark.usefixtures("challenge_dir")
    def test_a_missing_token_file_is_not_a_challenge(self, tmp_path):
        assert http(tmp_path, PREFIX + "absent") is False

    def test_an_empty_token_file_is_not_a_challenge(self, tmp_path, challenge_dir):
        (challenge_dir / "stale").write_text("")
        assert http(tmp_path, PREFIX + "stale") is False

    def test_a_directory_named_like_a_token_is_not_a_challenge(self, tmp_path, challenge_dir):
        (challenge_dir / "folder").mkdir()
        assert http(tmp_path, PREFIX + "folder") is False

    @pytest.mark.usefixtures("challenge_dir")
    def test_the_token_file_is_opened_in_the_jobs_challenge_directory(self, tmp_path):
        out = run(f'acme.is_http_challenge({{ bw = {{ uri = "{PREFIX}abc" }} }}) emit(OPENED)', tmp_path)
        assert out == "/var/tmp/bunkerweb/lets-encrypt/.well-known/acme-challenge/abc"

    def test_a_one_byte_token_file_is_enough(self, tmp_path, challenge_dir):
        (challenge_dir / "one").write_bytes(b"x")
        assert http(tmp_path, PREFIX + "one") is True
