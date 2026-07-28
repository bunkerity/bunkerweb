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
        ("no", "yes", True),  # workflow-only challenge — the case this exists for
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


def test_the_http_level_exclusion_covers_workflow_only_services():
    """The http-context rule is built per server from ``all``, so both sources matter."""
    rendered = _render(
        CONFS / "http" / "antibot.modsec-crs",
        SERVER_NAME="a.example.com b.example.com c.example.com",
        MULTISITE="yes",
        all={
            "a.example.com_USE_ANTIBOT": "captcha",
            "a.example.com_WORKFLOWS_HAS_CHALLENGE": "no",
            "a.example.com_SERVER_NAME": "a.example.com",
            "b.example.com_USE_ANTIBOT": "no",
            "b.example.com_WORKFLOWS_HAS_CHALLENGE": "yes",
            "b.example.com_SERVER_NAME": "b.example.com",
            "c.example.com_USE_ANTIBOT": "no",
            "c.example.com_WORKFLOWS_HAS_CHALLENGE": "no",
            "c.example.com_SERVER_NAME": "c.example.com",
        },
    )

    assert "a\\.example\\.com" in rendered
    assert "b\\.example\\.com" in rendered  # workflow-only service must be covered
    assert "c\\.example\\.com" not in rendered


def test_a_service_without_the_flag_at_all_is_treated_as_absent():
    """The compiler emits the flag for every server, but a stale config may not have it."""
    rendered = _render(CONFS / "server-http" / "antibot.conf", USE_ANTIBOT="no")
    assert "location /challenge" not in rendered
