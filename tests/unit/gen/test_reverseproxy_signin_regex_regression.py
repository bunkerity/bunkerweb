"""`REVERSE_PROXY_AUTH_REQUEST_SIGNIN_URL` accepts NGINX variables and still refuses anything that could inject a directive.

The regex required a literal ``http(s)://host``, so the documented ``$scheme://$host/start?rd=$request_uri``
form failed validation: the Configurator dropped the key with only a warning and no ``error_page``
redirect was rendered. The scheme may now be ``$variable`` and the host may contain ``$``. The value
lands verbatim inside an ``error_page 401 =302 <url>;`` directive, so a separator, a space or a quote
must stay refused.
"""

from json import loads
from pathlib import Path
from re import search

import pytest

ROOT = Path(__file__).resolve().parents[3]
SETTING = loads((ROOT / "src" / "common" / "core" / "reverseproxy" / "plugin.json").read_text(encoding="utf-8"))["settings"][
    "REVERSE_PROXY_AUTH_REQUEST_SIGNIN_URL"
]


def validates(value):
    # The server validates with re.search (Configurator, Database.is_valid_setting, UI check_variables).
    return bool(search(SETTING["regex"], value))


@pytest.mark.parametrize(
    "value",
    [
        "",
        "https://login.example.com/outpost.goauthentik.io/start?rd=$request_uri",
        "$scheme://$host/outpost.goauthentik.io/start?rd=$scheme://$host$request_uri",
        "$scheme://login.example.com/start",
        "https://$host/start",
    ],
)
def test_a_signin_url_with_nginx_variables_validates(value):
    assert validates(value), value


@pytest.mark.parametrize(
    "value",
    [
        "$scheme://$host/start;include /etc/passwd",
        "https://login.example.com/start\ninclude /etc/passwd",
        "$scheme://$host/start and more",
        'https://login.example.com/"quoted"',
        "https://login.example.com/start{x}",
        "ftp://login.example.com/start",
        "javascript:alert(1)",
    ],
)
def test_a_signin_url_that_could_inject_a_directive_is_refused(value):
    assert not validates(value), value
