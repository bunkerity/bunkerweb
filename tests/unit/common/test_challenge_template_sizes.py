"""Static byte ceilings: rc4 template sizes plus five percent, not rendered wire sizes."""

import os
from pathlib import Path

import pytest

ROOT = Path(os.environ.get("BW_GUARD_SOURCE_ROOT", Path(__file__).resolve().parents[3]))
CEILINGS = {
    "errors/files/error.html": 69447,
    "antibot/files/capjs.html": 33016,
    "antibot/files/capjs_frame.html": 2142,
    "antibot/files/captcha.html": 24371,
    "antibot/files/hcaptcha.html": 31922,
    "antibot/files/javascript.html": 39271,
    "antibot/files/mcaptcha.html": 31453,
    "antibot/files/recaptcha.html": 37845,
    "antibot/files/turnstile.html": 31874,
}


@pytest.mark.parametrize("path,ceiling", CEILINGS.items())
def test_template_byte_ceiling(path, ceiling):
    size = (ROOT / "src/common/core" / path).stat().st_size
    assert size <= ceiling, f"{path}: {size} bytes exceeds {ceiling}"
