"""``bwcli support`` (dev 4a91e1e13): where it runs, how it reads NGINX configuration, what it does without a database.

The redaction itself is pinned for both producers by ``tests/unit/ui/test_support_redaction_parity.py``.
"""

import ctypes
import os
import platform
import subprocess
import sys
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, Mock
from zipfile import ZipFile

import pytest

ROOT = Path(__file__).resolve().parents[3]
for _p in ("cli", "api", "utils", "db"):
    if str(ROOT / "src" / "common" / _p) not in sys.path:
        sys.path.insert(0, str(ROOT / "src" / "common" / _p))

import CLI as cli_module  # noqa: E402


def _cli(db=None, db_error=None):
    cli = cli_module.CLI.__new__(cli_module.CLI)
    cli._CLI__db, cli._CLI__db_error, cli._CLI__logger, cli._CLI__api_token, cli.apis = db, db_error, Mock(), "global-token", []
    cli._CLI__terminal_width = 80
    return cli


def test_the_subcommand_is_registered():
    paths = os.pathsep.join(str(ROOT / "src" / "common" / name) for name in ("cli", "api", "utils", "db"))
    result = subprocess.run(
        [sys.executable, "src/common/cli/main.py", "support", "-h"],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": paths},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "--no-anonymize" in result.stdout and "--output" in result.stdout


@pytest.mark.parametrize(
    ("text", "secrets", "kept"),
    (
        ("proxy_set_header Authorization 'Bearer abc123SECRET';", ("abc123SECRET",), ("proxy_set_header Authorization",)),
        ("proxy_set_header X-Real-IP $remote_addr;", (), ("X-Real-IP $remote_addr",)),
        ("proxy_set_header Authorization $http_authorization;", (), ("$http_authorization",)),
        ('set $upstream_token "tok-SECRET-9";', ("tok-SECRET-9",), ("set $upstream_token",)),
        ('more_set_headers "X-Api-Key: key-SECRET-7";', ("key-SECRET-7",), ("X-Api-Key:",)),
        ("# proxy_set_header Authorization commentSECRET\nadd_header X-Frame-Options DENY;", (), ("commentSECRET", "X-Frame-Options DENY")),
    ),
)
def test_redact_nginx(text, secrets, kept):
    redacted = cli_module.redact_nginx(text)
    assert all(secret not in redacted for secret in secrets), redacted
    assert all(part in redacted for part in kept), redacted


def _nginx_export(monkeypatch, tmp_path, files):
    """The NGINX part of a real `bwcli support` ZIP generated over `files` ({relative path: content}) as the configuration directory."""
    nginx = tmp_path / "nginx"
    for name, content in files.items():
        (nginx / name).parent.mkdir(parents=True, exist_ok=True)
        (nginx / name).write_text(content)
    (tmp_path / "logs").mkdir(exist_ok=True)
    monkeypatch.setattr(cli_module, "LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setattr(cli_module, "NGINX_PATH", nginx)
    target = tmp_path / "bundle.zip"
    ok, message = _cli(db_error="fixture: no database").support(str(target), True)
    assert ok, message
    with ZipFile(target) as bundle:
        return bundle.read("nginx/etc-nginx-conf.txt").decode()


# A variable that is assigned and then used as the value of a credential header carries the credential, whatever its name and wherever its `set` sits
VARIABLE_HEADER_CASES = (
    pytest.param(
        'set $auth "Basic dXNlcjpwYXNz";\nproxy_set_header Authorization $auth;',
        ("dXNlcjpwYXNz",),
        ("set $auth", "proxy_set_header Authorization $auth;"),
        id="set-before-use",
    ),
    pytest.param(
        'proxy_set_header Authorization $auth;\nset $auth "Basic dXNlcjpwYXNz";',
        ("dXNlcjpwYXNz",),
        ("set $auth", "proxy_set_header Authorization $auth;"),
        id="set-after-use",
    ),
    pytest.param(
        'set $auth "Basic dXNlcjpwYXNz";\nset $trace "trace-id-visible";\nproxy_set_header Authorization $auth;\nproxy_set_header X-Trace $trace;',
        ("dXNlcjpwYXNz",),
        ('set $trace "trace-id-visible";', "proxy_set_header X-Trace $trace;"),
        id="two-variables-only-the-credential-one-is-redacted",
    ),
    pytest.param(
        'set $auth "Basic dXNlcjpwYXNz";\nmore_set_input_headers "Authorization: $auth";',
        ("dXNlcjpwYXNz",),
        ("set $auth",),
        id="more-set-input-headers",
    ),
    pytest.param(
        'set $creds "dXNlcjpwYXNz";\nproxy_set_header Authorization "Basic ${creds}";',
        ("dXNlcjpwYXNz",),
        ("set $creds",),
        id="variable-inside-a-longer-value",
    ),
    pytest.param(
        'set $auth "Basic dXNlcjpwYXNz";\nadd_header Authorization $auth always;',
        ("dXNlcjpwYXNz",),
        ("set $auth",),
        id="add-header",
    ),
    pytest.param(
        'set $label "blue-green";\nproxy_set_header X-Deployment $label;',
        (),
        ('set $label "blue-green";', "proxy_set_header X-Deployment $label;"),
        id="non-secret-header-stays-readable",
    ),
)

# A secret variable carries whatever its value references, so those variables are secret too, to a fixpoint; a `map` block whose output is secret
# redacts every value it maps to
CHAIN_CASES = (
    pytest.param(
        'set $user_part "alice-SECRET1";\nset $creds "$user_part";\nset $auth "Basic $creds";\nproxy_set_header Authorization $auth;',
        ("alice-SECRET1",),
        ("set $user_part", "set $creds", "set $auth", "proxy_set_header Authorization $auth;"),
        id="chain-assigned-before-use",
    ),
    pytest.param(
        'proxy_set_header Authorization $auth;\nset $auth "Basic $creds";\nset $creds "$user_part";\nset $user_part "alice-SECRET1";',
        ("alice-SECRET1",),
        ("set $user_part", "set $creds", "set $auth"),
        id="chain-assigned-after-use",
    ),
    pytest.param(
        'set $a "x-$b";\nset $b "lit-SECRET9 $a";\nproxy_set_header Authorization $a;',
        ("lit-SECRET9",),
        ("set $a", "set $b"),
        id="cycle-terminates",
    ),
    pytest.param(
        'set $label "blue-green";\nset $region "$label";\nset $user_part "alice-SECRET1";\nset $auth "Basic $user_part";\n'
        "proxy_set_header Authorization $auth;\nproxy_set_header X-Region $region;",
        ("alice-SECRET1",),
        ('set $label "blue-green";', 'set $region "$label";', "proxy_set_header X-Region $region;"),
        id="unrelated-chain-stays-readable",
    ),
    pytest.param(
        'set $api_token "$creds";\nset $creds "tok-SECRET2";',
        ("tok-SECRET2",),
        ("set $api_token", "set $creds"),
        id="variable-named-like-a-secret-pulls-in-what-it-references",
    ),
    pytest.param(
        'map $http_x_tenant $tenant_auth {\n    default "def-SECRET7";\n    "acme" "acme-SECRET8";\n    ~^beta "beta-SECRET10";\n}\n'
        "proxy_set_header Authorization $tenant_auth;\nproxy_set_header X-Real-IP $remote_addr;",
        ("def-SECRET7", "acme-SECRET8", "beta-SECRET10"),
        ("map $http_x_tenant $tenant_auth {", "default ", '"acme" ', "~^beta ", "proxy_set_header X-Real-IP $remote_addr;"),
        id="map-output-used-as-a-credential-header",
    ),
    pytest.param(
        'proxy_set_header Authorization $tenant_auth;\nmap $http_x_tenant $tenant_auth {\n    default "def-SECRET7";\n}\n',
        ("def-SECRET7",),
        ("map $http_x_tenant $tenant_auth {", "default "),
        id="map-after-its-use",
    ),
    pytest.param(
        'map $host $api_token {\n    default "tok-SECRET3";\n}\n',
        ("tok-SECRET3",),
        ("map $host $api_token {", "default "),
        id="map-output-named-like-a-secret",
    ),
    pytest.param(
        'map $http_x_tenant $tenant_auth {\n    default $creds;\n}\nset $creds "lit-SECRET4";\nproxy_set_header Authorization $tenant_auth;',
        ("lit-SECRET4",),
        ("default ", "set $creds"),
        id="map-values-reference-further-variables",
    ),
    pytest.param(
        'map $host $backend {\n    default "pool-a";\n    "b.example" "pool-b";\n}\nproxy_set_header X-Backend $backend;',
        (),
        ('default "pool-a";', '"b.example" "pool-b";', "proxy_set_header X-Backend $backend;"),
        id="map-with-a-non-secret-output-stays-readable",
    ),
    pytest.param(
        "map $http_x_tenant $tenant_auth {\n    hostnames;\n    include /etc/nginx/tenants.map;\n    default x-SECRET5;\n}\n"
        "proxy_set_header Authorization $tenant_auth;",
        ("x-SECRET5",),
        ("hostnames;", "include /etc/nginx/tenants.map;"),
        id="map-directives-without-a-value-stay",
    ),
)


@pytest.mark.parametrize(("text", "secrets", "kept"), VARIABLE_HEADER_CASES + CHAIN_CASES)
def test_redact_nginx_variable_used_as_a_credential_header_value(text, secrets, kept):
    redacted = cli_module.redact_nginx(text)
    assert all(secret not in redacted for secret in secrets), redacted
    assert all(part in redacted for part in kept), redacted


@pytest.mark.parametrize(("text", "secrets", "kept"), VARIABLE_HEADER_CASES + CHAIN_CASES)
def test_support_zip_redacts_a_variable_used_as_a_credential_header_value(monkeypatch, tmp_path, text, secrets, kept):
    exported = _nginx_export(monkeypatch, tmp_path, {"server.conf": f"server {{\n{text}\n}}\n"})
    assert all(secret not in exported for secret in secrets), exported
    assert all(part in exported for part in kept), exported


def test_support_zip_redacts_a_set_in_another_file_than_the_header_that_uses_it(monkeypatch, tmp_path):
    files = {"a-vars.conf": 'set $auth "Basic dXNlcjpwYXNz";\nset $label "blue-green";\n', "b-proxy.conf": "proxy_set_header Authorization $auth;\n"}
    exported = _nginx_export(monkeypatch, tmp_path, files)
    assert "dXNlcjpwYXNz" not in exported, exported
    assert 'set $label "blue-green";' in exported and "proxy_set_header Authorization $auth;" in exported, exported
    # and the other way round: the header is read before the file that assigns the variable
    files = {"a-proxy.conf": "proxy_set_header Authorization $auth;\n", "b-vars.conf": 'set $auth "Basic dXNlcjpwYXNz";\n'}
    exported = _nginx_export(monkeypatch, tmp_path / "reverse", files)
    assert "dXNlcjpwYXNz" not in exported, exported


def test_support_zip_follows_a_chain_and_a_map_across_files_in_any_order(monkeypatch, tmp_path):
    files = {
        "a-proxy.conf": "proxy_set_header Authorization $auth;\nproxy_set_header X-Real-IP $remote_addr;\n",
        "b-auth.conf": 'set $auth "Basic $creds";\nset $label "blue-green";\n',
        "c-creds.conf": 'set $creds "$user_part";\nmap $http_x_tenant $user_part {\n    default "alice-SECRET1";\n    "acme" "acme-SECRET6";\n}\n',
    }
    for number, names in enumerate((sorted(files), sorted(files, reverse=True))):
        exported = _nginx_export(monkeypatch, tmp_path / str(number), {name: files[name] for name in names})
        assert "alice-SECRET1" not in exported and "acme-SECRET6" not in exported, exported
        assert 'set $label "blue-green";' in exported and "proxy_set_header X-Real-IP $remote_addr;" in exported, exported
        assert "set $creds" in exported and "map $http_x_tenant $user_part {" in exported, exported


USE_AUTH = "proxy_set_header Authorization $auth;\nproxy_set_header X-Real-IP $remote_addr;\n"


def test_support_zip_redacts_the_entries_of_a_file_included_from_a_secret_map(monkeypatch, tmp_path):
    files = {
        "server.conf": f"map $host $auth {{\n    include auth-values.conf;\n}}\n{USE_AUTH}",
        "auth-values.conf": 'default "cred-SECRET11";\n"acme.example" "acme-SECRET12";\n~^beta "beta-SECRET15";\n',
    }
    exported = _nginx_export(monkeypatch, tmp_path, files)
    assert not any(secret in exported for secret in ("cred-SECRET11", "acme-SECRET12", "beta-SECRET15")), exported
    # keys stay readable, like in an inline map (the domain is pseudonymized by the ZIP's own anonymization, hence the unquoted default and regex keys)
    assert "default " in exported and "~^beta " in exported and "include auth-values.conf;" in exported, exported
    assert "proxy_set_header X-Real-IP $remote_addr;" in exported, exported


def test_support_zip_follows_the_variables_an_included_map_value_references(monkeypatch, tmp_path):
    files = {
        "server.conf": f"map $host $auth {{\n    include auth-values.conf;\n}}\n{USE_AUTH}",
        "auth-values.conf": 'default $token;\n"other-host" "Basic $user_part";\n',
        "vars.conf": 'set $token "tok-SECRET13";\nset $user_part "alice-SECRET16";\nset $label "blue-green";\n',
    }
    exported = _nginx_export(monkeypatch, tmp_path, files)
    assert "tok-SECRET13" not in exported and "alice-SECRET16" not in exported, exported
    assert 'set $label "blue-green";' in exported and "set $token" in exported, exported


def test_support_zip_leaves_a_file_included_from_a_non_secret_map_unchanged(monkeypatch, tmp_path):
    files = {
        "server.conf": "map $host $backend {\n    include backends.conf;\n}\nproxy_set_header X-Backend $backend;\n",
        "backends.conf": 'default "pool-a";\n"b.example" "pool-b";\n',
    }
    exported = _nginx_export(monkeypatch, tmp_path, files)
    assert 'default "pool-a";' in exported, exported


def test_support_zip_redacts_every_file_a_glob_include_could_match_and_nothing_else(monkeypatch, tmp_path):
    files = {
        "server.conf": f"map $host $auth {{\n    include maps/*.conf;\n}}\n{USE_AUTH}",
        "maps/a.conf": 'default "a-SECRET17";\n',
        "maps/deep/b.conf": 'default "b-SECRET18";\n',
        "elsewhere.conf": 'set $label "kept-visible";\n',
    }
    exported = _nginx_export(monkeypatch, tmp_path, files)
    assert "a-SECRET17" not in exported and "b-SECRET18" not in exported, exported
    assert 'set $label "kept-visible";' in exported, exported


def test_support_zip_redacts_an_absolute_include_and_a_nested_include(monkeypatch, tmp_path):
    absolute = tmp_path / "nginx" / "abs" / "values.conf"
    files = {
        "server.conf": f"map $host $auth {{\n    include {absolute.as_posix()};\n}}\n{USE_AUTH}",
        "abs/values.conf": 'default "abs-SECRET19";\ninclude nested/more.conf;\n',
        "nested/more.conf": '"x" "nested-SECRET20";\n',
    }
    exported = _nginx_export(monkeypatch, tmp_path, files)
    assert "abs-SECRET19" not in exported and "nested-SECRET20" not in exported, exported


def test_support_zip_include_that_matches_no_exported_file_changes_nothing(monkeypatch, tmp_path):
    files = {
        "server.conf": f"map $host $auth {{\n    include absent.conf;\n}}\n{USE_AUTH}",
        "other.conf": 'set $label "kept-visible";\nproxy_set_header Authorization "Bearer lit-SECRET21";\n',
    }
    exported = _nginx_export(monkeypatch, tmp_path, files)
    assert 'set $label "kept-visible";' in exported and "include absent.conf;" in exported, exported
    assert "lit-SECRET21" not in exported, exported


def test_support_zip_keeps_redacting_the_directives_of_a_file_a_non_secret_map_include_could_match(monkeypatch, tmp_path):
    files = {
        "server.conf": "map $host $backend {\n    include *.conf;\n}\n",
        "other.conf": 'set $label "blue-green";\nproxy_set_header Authorization "Bearer lit-SECRET22";\n',
    }
    exported = _nginx_export(monkeypatch, tmp_path, files)
    assert "lit-SECRET22" not in exported, exported
    assert 'set $label "blue-green";' in exported and "proxy_set_header Authorization" in exported, exported


class _GlobT(ctypes.Structure):
    """glibc's glob_t, the structure nginx's ngx_open_glob() hands to glob(3)."""

    _fields_ = [("gl_pathc", ctypes.c_size_t), ("gl_pathv", ctypes.c_void_p), ("gl_offs", ctypes.c_size_t), ("gl_flags", ctypes.c_int)] + [
        (f"gl_{name}", ctypes.c_void_p) for name in ("closedir", "readdir", "opendir", "lstat", "stat")
    ]


def _libc_glob(pattern):
    """What the host's glob(3) returns for `pattern`, flags 0 like nginx: the oracle for the include matching."""
    libc = ctypes.CDLL(None)
    found = _GlobT()
    status = libc.glob(pattern.encode(), 0, None, ctypes.byref(found))
    try:
        return {name.decode() for name in (ctypes.c_char_p * found.gl_pathc).from_address(found.gl_pathv)} if status == 0 else set()
    finally:
        libc.globfree(ctypes.byref(found))


GLOB_TREE = ("maps/a.conf", "maps/b1.conf", "maps/x1.conf", "maps/^y.conf", "maps/!z.conf", "maps/[w].conf", "maps/q\\r.conf", "maps/deep/c.conf", "other.conf")
# (pattern, whether glob(3) and the matcher must agree exactly, because the pattern holds nothing the matcher reads differently)
GLOB_PATTERNS = (
    pytest.param("maps/*.conf", True, id="star"),
    pytest.param("maps/?1.conf", True, id="question"),
    pytest.param("maps/[ab]*.conf", True, id="class"),
    # a range follows the locale's collation, so it cannot be translated with certainty: the matcher fails closed (every file under the prefix)
    pytest.param("maps/[a-b]*.conf", False, id="range"),
    # glibc negates on a leading `^` unless POSIXLY_CORRECT is set and FreeBSD reads it as a literal member: the matcher fails closed (every file under the prefix)
    pytest.param("maps/[^x]*.conf", False, id="caret-negation"),
    pytest.param("maps/[^]a]*.conf", False, id="caret-then-bracket"),
    pytest.param("maps/[x^]*.conf", True, id="caret-not-first"),
    pytest.param("maps/[!x]*.conf", True, id="bang-negation"),
    pytest.param("maps/[!a-b]*.conf", False, id="negated-range"),
    pytest.param("maps/[]a]*.conf", True, id="leading-bracket-in-class"),
    pytest.param("maps/[[:alpha:]]*.conf", False, id="posix-class"),
    pytest.param("maps/[[:digit:]a]*.conf", False, id="posix-class-and-member"),
    pytest.param(r"maps/\^y.conf", False, id="escaped-caret"),
    pytest.param(r"maps/q\r.conf", False, id="escaped-letter"),
    pytest.param(r"maps/[\w].conf", False, id="escape-in-class"),
    pytest.param("maps/[w.conf", False, id="unclosed-bracket"),
    pytest.param("maps/[.conf", False, id="unclosed-bracket-alone"),
    pytest.param("maps/[z-a]*.conf", False, id="reversed-range"),
    pytest.param("*/[^x]*.conf", False, id="star-before-class"),
)


@pytest.mark.skipif(platform.libc_ver()[0] != "glibc", reason="the oracle reads glibc's glob_t layout")
@pytest.mark.parametrize("posixly", (pytest.param(False, id="glibc-default"), pytest.param(True, id="posixly-correct")))
@pytest.mark.parametrize(("pattern", "exact"), GLOB_PATTERNS)
def test_include_matches_never_under_match_libc_glob(tmp_path, pattern, exact, posixly):
    for name in GLOB_TREE:
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text("")
    files = [(tmp_path / name).as_posix() for name in GLOB_TREE]
    glob_pattern = f"{tmp_path.as_posix()}/{pattern}"
    expected = {path for path in (_libc_glob_posixly(None, glob_pattern) if posixly else _libc_glob(glob_pattern)) if os.path.isfile(path)}
    matched = set(cli_module.nginx_include_matches(pattern, files, tmp_path.as_posix()))
    assert expected <= matched, (expected - matched, pattern)
    if exact:
        # `*` crosses `/` in the matcher, so it can name deeper files glob(3) does not
        assert {path for path in matched if "/deep/" not in path} == {path for path in expected if "/deep/" not in path}, (matched, expected)


LC_ALL_CATEGORY = 6  # LC_ALL on Linux


def _libc_glob_in(locale, pattern):
    """`_libc_glob()` with the process locale set to `locale` meanwhile, None when the host has no such locale. Names travel as raw bytes."""
    libc = ctypes.CDLL(None)
    libc.setlocale.restype = ctypes.c_char_p
    previous = libc.setlocale(LC_ALL_CATEGORY, None)
    if libc.setlocale(LC_ALL_CATEGORY, locale.encode()) is None:
        return None
    try:
        found = _GlobT()
        status = libc.glob(os.fsencode(pattern), 0, None, ctypes.byref(found))
        try:
            return {os.fsdecode(name) for name in (ctypes.c_char_p * found.gl_pathc).from_address(found.gl_pathv)} if status == 0 else set()
        finally:
            libc.globfree(ctypes.byref(found))
    finally:
        libc.setlocale(LC_ALL_CATEGORY, previous)


# glibc reads POSIXLY_CORRECT once, at the first fnmatch() of the process, and caches it: setting it around a call in this process does nothing once any
# glob(3) ran. The oracle with POSIXLY_CORRECT=1 therefore runs in a fresh interpreter that gets the variable from its environment.
POSIXLY_GLOB_SCRIPT = """
import ctypes, os, sys
class GlobT(ctypes.Structure):
    _fields_ = [("gl_pathc", ctypes.c_size_t), ("gl_pathv", ctypes.c_void_p), ("gl_offs", ctypes.c_size_t), ("gl_flags", ctypes.c_int)] + [
        (f"gl_{name}", ctypes.c_void_p) for name in ("closedir", "readdir", "opendir", "lstat", "stat")
    ]
libc = ctypes.CDLL(None)
libc.setlocale.restype = ctypes.c_char_p
if sys.argv[1] and libc.setlocale(6, sys.argv[1].encode()) is None:
    sys.exit(3)
found = GlobT()
status = libc.glob(os.fsencode(sys.argv[2]), 0, None, ctypes.byref(found))
names = (ctypes.c_char_p * found.gl_pathc).from_address(found.gl_pathv) if status == 0 else ()
sys.stdout.buffer.write(b"\\0".join(names))
"""


def _libc_glob_posixly(locale, pattern):
    """`_libc_glob_in()` with POSIXLY_CORRECT=1 in a fresh process (see above), None when the host has no such locale. `locale` None keeps the default."""
    env = {**os.environ, "POSIXLY_CORRECT": "1"}
    result = subprocess.run([sys.executable, "-I", "-c", POSIXLY_GLOB_SCRIPT, locale or "", pattern], env=env, capture_output=True, check=False)
    if result.returncode == 3:
        return None
    assert result.returncode == 0, result.stderr
    return {os.fsdecode(name) for name in result.stdout.split(b"\0") if name}


# nginx never calls setlocale(), so its glob(3) runs in the C locale: `?` and a class read one byte, `é` is two. A UTF-8 locale reads one character.
GLOB_LOCALES = (pytest.param("C", id="C"), pytest.param("C.utf8", id="utf8"), pytest.param("en_US.utf8", id="en_US-utf8"))
BYTES_TREE = ("maps/a.conf", "maps/ab.conf", "maps/é.conf", "maps/日.conf", "maps/éa.conf", "maps/aé.conf", "maps/\udcff.conf", "maps/\udcffa.conf")
BYTES_PATTERNS = (
    "maps/?.conf",
    "maps/??.conf",
    "maps/???.conf",
    "maps/????.conf",
    "maps/[^x].conf",
    "maps/[x^].conf",
    "maps/[^x][^x].conf",
    "maps/[^x][^x][^x].conf",
    "maps/[!x][!x].conf",
    "maps/[a-z]?.conf",
    "maps/?[^x]*.conf",
    "maps/*?.conf",
    "maps/*[^x].conf",
    "maps/[ab].conf",
    "maps/[ab][ab].conf",
    "maps/é.conf",
    "maps/[é].conf",
    "maps/[é]*.conf",
    "maps/[a-é].conf",
    "maps/[à-ÿ].conf",
    "maps/[a-z].conf",
    "maps/[A-Z].conf",
    "maps/[0-9].conf",
    "maps/[^a-c].conf",
    "maps/[^é].conf",
    "maps/日.conf",
    "maps/?.conf",
)


def _make_tree(root, names):
    for name in names:
        path = os.fsencode(root / name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            os.close(os.open(path, os.O_CREAT | os.O_WRONLY))
        except OSError:
            pytest.skip(f"the filesystem refuses the name {name!r}")


@pytest.mark.skipif(platform.libc_ver()[0] != "glibc", reason="the oracle reads glibc's glob_t layout")
@pytest.mark.parametrize("posixly", (pytest.param(False, id="glibc-default"), pytest.param(True, id="posixly-correct")))
@pytest.mark.parametrize("pattern", dict.fromkeys(BYTES_PATTERNS))
def test_include_matches_cover_glob_in_the_c_locale_and_in_a_utf8_locale(tmp_path, pattern, posixly):
    _make_tree(tmp_path, BYTES_TREE)
    files = [(tmp_path / name).as_posix() for name in BYTES_TREE]
    matched = set(cli_module.nginx_include_matches(pattern, files, tmp_path.as_posix()))
    ran = 0
    for locale in ("C", "C.utf8", "en_US.utf8"):
        glob_pattern = f"{tmp_path.as_posix()}/{pattern}"
        expected = _libc_glob_posixly(locale, glob_pattern) if posixly else _libc_glob_in(locale, glob_pattern)
        if expected is None:
            continue
        ran += 1
        expected = {path for path in expected if os.path.isfile(os.fsencode(path))}
        assert expected <= matched, (locale, expected - matched, pattern)
    assert ran, "no locale could be set"


@pytest.mark.skipif(platform.libc_ver()[0] != "glibc", reason="the oracle reads glibc's glob_t layout")
@pytest.mark.parametrize("locale", GLOB_LOCALES)
def test_the_glob_oracle_runs_in_every_locale_the_host_has(tmp_path, locale):
    _make_tree(tmp_path, ("maps/é.conf",))
    found = _libc_glob_in(locale, f"{tmp_path.as_posix()}/maps/?.conf")
    if found is None:
        pytest.skip(f"locale {locale} is not installed on this host")
    # glob(3) reads `?` per byte in the C locale and per character in a UTF-8 one: the very difference the matcher must cover
    assert bool(found) is locale.endswith("utf8"), (locale, found)


@pytest.mark.skipif(platform.libc_ver()[0] != "glibc", reason="the oracle reads glibc's glob_t layout")
@pytest.mark.parametrize(
    "pattern", ("maps/?.conf", "maps/??.conf", "maps/[!x].conf", "maps/[!x][!x].conf", "maps/[x^].conf", "maps/*?.conf", "maps/[ab]?.conf")
)
def test_include_matches_of_an_ascii_pattern_stay_exact_over_ascii_names(tmp_path, pattern):
    names = ("maps/a.conf", "maps/ab.conf", "maps/abc.conf", "maps/x.conf", "other.conf")
    _make_tree(tmp_path, names)
    files = [(tmp_path / name).as_posix() for name in names]
    expected = {path for path in _libc_glob_in("C", f"{tmp_path.as_posix()}/{pattern}") or () if os.path.isfile(path)}
    assert set(cli_module.nginx_include_matches(pattern, files, tmp_path.as_posix())) == expected


@pytest.mark.parametrize(
    ("pattern", "secret_files", "kept_files"),
    (
        pytest.param("maps/??.conf", ("maps/é.conf",), ("maps/abc.conf",), id="critic-question-marks-over-a-two-byte-character"),
        pytest.param("maps/[!x][!x].conf", ("maps/é.conf", "maps/ab.conf"), ("maps/abc.conf",), id="negated-classes-over-a-two-byte-character"),
        pytest.param("maps/?.conf", ("maps/é.conf", "maps/日.conf", "maps/a.conf"), ("maps/ab.conf", "maps/abc.conf"), id="question-mark-in-a-utf8-locale"),
        pytest.param("maps/???.conf", ("maps/日.conf", "maps/abc.conf"), ("maps/ab.conf",), id="question-marks-over-a-three-byte-character"),
        pytest.param("maps/a?.conf", ("maps/ab.conf", "maps/aé.conf"), ("maps/a.conf",), id="question-mark-after-a-letter"),
        pytest.param("maps/[à-ÿ].conf", ("maps/b.conf", "maps/é.conf"), (), id="critic-non-ascii-range-collates-over-ascii"),
        pytest.param("maps/[a-z].conf", ("maps/b.conf", "maps/é.conf"), (), id="ascii-range"),
        pytest.param("maps/[^a-c].conf", ("maps/b.conf", "maps/x.conf"), (), id="negated-range"),
        pytest.param("maps/[a-é].conf", ("maps/b.conf", "maps/é.conf"), (), id="mixed-range"),
    ),
)
def test_support_zip_redacts_every_file_an_include_could_match_by_byte_or_by_character(monkeypatch, tmp_path, pattern, secret_files, kept_files):
    files = {"server.conf": f"map $host $auth {{\n    include {pattern};\n}}\n{USE_AUTH}"}
    secrets = {}
    for number, name in enumerate(dict.fromkeys(secret_files + kept_files)):
        secrets[name] = f"val-SECRET{number}-{number}"
        files[name] = f'default "{secrets[name]}";\n'
    exported = _nginx_export(monkeypatch, tmp_path, files)
    assert not any(secrets[name] in exported for name in secret_files), exported
    assert all(secrets[name] in exported for name in kept_files), exported


@pytest.mark.parametrize(
    ("pattern", "secret_files", "kept_files"),
    (
        # a leading `^` negates in glibc, not under POSIXLY_CORRECT (the critic's case, x1.conf) and not in FreeBSD: it fails closed, so x1.conf is redacted too
        pytest.param("maps/[^x]*.conf", ("maps/a.conf", "maps/b1.conf", "maps/x1.conf"), (), id="caret-negation"),
        pytest.param("maps/[^]a]*.conf", ("maps/a.conf", "maps/b1.conf", "maps/x1.conf"), (), id="caret-then-bracket"),
        pytest.param("maps/[x^]*.conf", ("maps/x1.conf",), ("maps/a.conf", "maps/b1.conf"), id="caret-not-first-is-a-literal-member"),
        pytest.param("maps/[!x]*.conf", ("maps/a.conf", "maps/b1.conf"), ("maps/x1.conf",), id="bang-negation"),
        pytest.param("maps/[[:alpha:]]*.conf", ("maps/a.conf", "maps/b1.conf", "maps/x1.conf"), (), id="posix-class"),
        pytest.param(r"maps/\a.conf", ("maps/a.conf",), (), id="backslash-escape"),
        pytest.param("maps/[a.conf", ("maps/a.conf",), (), id="unclosed-bracket"),
    ),
)
def test_support_zip_redacts_every_file_a_glob_include_with_a_class_could_match(monkeypatch, tmp_path, pattern, secret_files, kept_files):
    files = {"server.conf": f"map $host $auth {{\n    include {pattern};\n}}\n{USE_AUTH}"}
    secrets = {}
    for number, name in enumerate(dict.fromkeys(secret_files + kept_files + ("maps/a.conf", "maps/b1.conf", "maps/x1.conf"))):
        secrets[name] = f"val-SECRET{number}-{name.rpartition('/')[2].partition('.')[0]}"
        files[name] = f'default "{secrets[name]}";\n'
    exported = _nginx_export(monkeypatch, tmp_path, files)
    assert not any(secrets[name] in exported for name in secret_files), exported
    assert all(secrets[name] in exported for name in kept_files), exported


def test_refused_where_the_scheduler_does_not_run(monkeypatch, tmp_path):
    monkeypatch.setattr(cli_module, "SCHEDULER_PATH", tmp_path / "absent")
    monkeypatch.setattr(cli_module, "get_integration", lambda: "Kubernetes")
    assert "kubectl exec <scheduler pod>" in cli_module.support_refusal()
    monkeypatch.setattr(cli_module, "get_integration", lambda: "Docker")
    assert "docker exec <scheduler container>" in cli_module.support_refusal()


def test_allowed_where_the_scheduler_runs(monkeypatch, tmp_path):
    monkeypatch.setattr(cli_module, "SCHEDULER_PATH", tmp_path)
    monkeypatch.setattr(cli_module, "ALL_IN_ONE_PATH", tmp_path / "absent")
    monkeypatch.setattr(cli_module, "get_integration", lambda: "Docker")
    assert cli_module.support_refusal() is None


def test_all_in_one_without_its_scheduler_is_refused(monkeypatch, tmp_path):
    monkeypatch.setattr(cli_module, "SCHEDULER_PATH", tmp_path)
    monkeypatch.setattr(cli_module, "ALL_IN_ONE_PATH", tmp_path)
    monkeypatch.setattr(cli_module, "get_integration", lambda: "Docker")
    monkeypatch.delenv("SERVICE_SCHEDULER", raising=False)
    assert "SERVICE_SCHEDULER" in cli_module.support_refusal()
    monkeypatch.setenv("SERVICE_SCHEDULER", "yes")
    assert cli_module.support_refusal() is None


@pytest.mark.parametrize(
    ("install_type", "refused"), (("worker", True), ("ui", True), ("api", True), ("full", False), ("manager", False), ("scheduler", False))
)
def test_linux_install_type_decides(monkeypatch, tmp_path, install_type, refused):
    marker = tmp_path / "INSTALL_TYPE"
    marker.write_text(install_type)
    monkeypatch.setattr(cli_module, "SCHEDULER_PATH", tmp_path)
    monkeypatch.setattr(cli_module, "ALL_IN_ONE_PATH", tmp_path / "absent")
    monkeypatch.setattr(cli_module, "INSTALL_TYPE_PATH", marker)
    monkeypatch.setattr(cli_module, "get_integration", lambda: "Linux")
    assert (cli_module.support_refusal() is not None) is refused


def _empty_dirs(monkeypatch, tmp_path):
    (tmp_path / "logs").mkdir()
    monkeypatch.setattr(cli_module, "LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setattr(cli_module, "NGINX_PATH", tmp_path / "absent")


def test_without_a_database_the_bundle_is_still_written_and_says_why(monkeypatch, tmp_path):
    _empty_dirs(monkeypatch, tmp_path)
    target = tmp_path / "bundle.zip"
    ok, message = _cli(db_error="Can't connect to database postgresql://bunkerweb:[REDACTED]@db/bw").support(str(target), True)
    assert ok, message
    with ZipFile(target) as bundle:
        manifest = bundle.read("manifest.json").decode()
        assert "Can't connect to database" in manifest and "environment.json" in bundle.namelist()
        assert "hunter2" not in manifest
        assert "config.json" not in bundle.namelist()


def test_refuses_to_write_a_zip_to_a_terminal(monkeypatch, tmp_path):
    _empty_dirs(monkeypatch, tmp_path)
    monkeypatch.setattr(cli_module, "sys_stdout", Mock(isatty=lambda: True))
    ok, message = _cli().support("-", True)
    assert not ok and "terminal" in message


def test_an_instance_credential_dials_the_instance_and_stays_out_of_the_bundle(monkeypatch, tmp_path):
    _empty_dirs(monkeypatch, tmp_path)
    row = {"hostname": "bunkerweb-1.internal", "name": "bw1", "type": "container", "method": "api", "status": "up", "credential": "instCREDENTIALsecret42"}
    db = MagicMock()
    db.get_instances.return_value = [row]
    db.get_services.return_value = []
    db.get_metadata.return_value = {"version": "1.7.0"}
    db._db_session.side_effect = RuntimeError("fixture")
    api = Mock()
    api.request.return_value = (True, "", 200, {"status": "ok"})
    api_class = Mock()
    api_class.from_instance.return_value = api
    monkeypatch.setattr(cli_module, "API", api_class)
    for name in ("get_plugins", "get_jobs_cache_files", "get_custom_configs"):
        getattr(db, name).return_value = []
    db.get_jobs.return_value = {}

    target = tmp_path / "bundle.zip"
    ok, message = _cli(db=db).support(str(target), True)
    assert ok, message
    assert api_class.from_instance.call_args.args[0]["credential"] == "instCREDENTIALsecret42"
    with ZipFile(BytesIO(target.read_bytes())) as bundle:
        text = "\n".join(bundle.read(name).decode() for name in bundle.namelist())
    assert "instCREDENTIALsecret42" not in text
    assert "bunkerweb-1.internal" not in text, "the hostname is pseudonymized by default"
    assert "reachable" in text
