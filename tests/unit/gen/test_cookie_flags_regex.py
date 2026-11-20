"""`COOKIE_FLAGS` must refuse what nginx_cookie_flag_module refuses.

The module accepts a cookie name (or `*`) followed by one or more of `HttpOnly`, `Secure` and
`SameSite[=Lax|Strict|None]`. It rejects `Expires=`, `Domain=`, `Path=` and an entry with a name
and no flag, and a rejected directive fails the whole nginx reload: the old configuration stays
live. The setting regex used to accept all of those, so the validation passed and the reload then
failed. The regex is the only gate in front of the module, so it has to match the module.
"""

from json import loads
from pathlib import Path
from re import compile as re_compile

import pytest

ROOT = Path(__file__).resolve().parents[3]
REGEX = re_compile(loads((ROOT / "src" / "common" / "core" / "headers" / "plugin.json").read_text(encoding="utf-8"))["settings"]["COOKIE_FLAGS"]["regex"])


@pytest.mark.parametrize(
    "value",
    [
        "",
        "* HttpOnly SameSite=Lax",
        "* HttpOnly SameSite=None",
        "* SameSite=Strict",
        "session_cookie Secure HttpOnly SameSite=Strict",
        "bw_cookie_1 SameSite=Strict",
        "* httponly samesite=lax secure",
        "* SameSite",
    ],
)
def test_a_value_the_module_accepts_validates(value):
    assert REGEX.match(value), value


@pytest.mark.parametrize(
    "value",
    [
        "* Expires=x",
        "* HttpOnly Expires=Wed",
        "* Domain=example.com",
        "* Path=/",
        "auth_cookie Secure HttpOnly SameSite=Strict Max-Age=3600",
        "session_cookie",
        "*",
        "* HttpOnlySecure",
        "* SameSite=Bogus",
        "bad;name HttpOnly",
        'bad"name HttpOnly',
        "bad{name HttpOnly",
        "* HttpOnly;",
    ],
)
def test_a_value_the_module_rejects_does_not_validate(value):
    assert not REGEX.match(value), value
