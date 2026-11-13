"""The challenge location must render for a workflow challenge, not only for USE_ANTIBOT.

A workflow rule can request a challenge on a service whose ``USE_ANTIBOT`` is ``no``. The
Lua honours that, but without the ``location`` block the redirect lands on a 404 and
``resty.template`` never gets its root — so these three templates are load-bearing, and the
ModSecurity allow rule has to follow or CRS blocks the challenge POST.
"""

from importlib import import_module
from pathlib import Path

import pytest

jinja2 = pytest.importorskip("jinja2")

ROOT = Path(__file__).resolve().parents[3]
CONFS = ROOT / "src" / "common" / "core" / "antibot" / "confs"


def _render(path: Path, **variables) -> str:
    environment = jinja2.Environment(undefined=jinja2.ChainableUndefined, keep_trailing_newline=True)
    # Templator exposes `import` to templates; the modsec-crs one uses it to escape hosts.
    environment.globals["import"] = import_module
    return environment.from_string(path.read_text(encoding="utf-8")).render(ANTIBOT_URI="/challenge", **variables)


@pytest.mark.parametrize(
    ("use_antibot", "has_challenge", "expected"),
    [
        ("captcha", "no", True),  # global antibot, unchanged behaviour
        ("captcha", "yes", True),
        ("no", "no", False),  # neither: nothing must be emitted
    ],
)
def test_the_challenge_location_and_its_modsec_exclusion_follow_either_source(use_antibot, has_challenge, expected):
    location = _render(CONFS / "server-http" / "antibot.conf", USE_ANTIBOT=use_antibot, WORKFLOWS_HAS_CHALLENGE=has_challenge)
    modsec = _render(CONFS / "modsec-crs" / "antibot.conf", USE_ANTIBOT=use_antibot, WORKFLOWS_HAS_CHALLENGE=has_challenge)

    assert ("location /challenge" in location) is expected
    # Without the allow rule, CRS inspects the challenge POST and can block the answer.
    assert ("id:1010" in modsec) is expected


def test_a_service_without_the_flag_at_all_is_treated_as_absent():
    """The compiler emits the flag for every server, but a stale config may not have it."""
    rendered = _render(CONFS / "server-http" / "antibot.conf", USE_ANTIBOT="no")
    assert "location /challenge" not in rendered


@pytest.mark.parametrize(
    ("inject_head", "inject_body"),
    [
        ("<style>head</style>", ""),
        ("", "<script>body</script>"),
        ("<style>head</style>", "<script>body</script>"),
    ],
)
def test_the_challenge_page_is_not_rewritten_by_html_injection(inject_head, inject_body):
    """INJECT_HEAD/INJECT_BODY are server-level sub_filter rules that every location inherits (#3234).

    The challenge page sends a nonce-based CSP that blocks whatever they inject, so the location
    defines its own no-op rule: NGINX only inherits sub_filter rules into a location that has none.
    """
    rendered = _render(CONFS / "server-http" / "antibot.conf", USE_ANTIBOT="captcha", INJECT_HEAD=inject_head, INJECT_BODY=inject_body)
    location = rendered.split("location /challenge", 1)[1]

    assert "sub_filter '</head>' '</head>';" in location
    # The override must not carry the injected markup itself.
    assert "head</style>" not in location and "body</script>" not in location


def test_no_sub_filter_is_added_when_html_injection_is_unset():
    rendered = _render(CONFS / "server-http" / "antibot.conf", USE_ANTIBOT="captcha", INJECT_HEAD="", INJECT_BODY="")
    assert "location /challenge" in rendered
    assert "sub_filter" not in rendered
