"""Compile shipped libinjection and check detection at its public C API."""

import ctypes
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "src/deps/src/libinjection/src"
pytestmark = pytest.mark.skipif(not shutil.which("cc"), reason="C compiler required")


@pytest.fixture(scope="module")
def libinjection(tmp_path_factory):
    library = tmp_path_factory.mktemp("libinjection") / "libinjection.so"
    result = subprocess.run(
        [
            "cc",
            "-shared",
            "-fPIC",
            "-fsigned-char",
            "-o",
            str(library),
            *[str(SOURCE / name) for name in ["libinjection_sqli.c", "libinjection_xss.c", "libinjection_html5.c"]],
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    lib = ctypes.CDLL(str(library))
    lib.libinjection_sqli.argtypes = [ctypes.c_char_p, ctypes.c_size_t, ctypes.c_char_p]
    lib.libinjection_sqli.restype = ctypes.c_int
    lib.libinjection_xss.argtypes = [ctypes.c_char_p, ctypes.c_size_t]
    lib.libinjection_xss.restype = ctypes.c_int
    return lib


@pytest.mark.parametrize(
    "payload", [b"<input \xff onfocus=alert(1) autofocus>", b"<input x \xff onfocus=alert(1) autofocus>", b"<a href= \xff onfocus=alert(1)>"]
)
def test_ff_byte_does_not_end_xss_scan(libinjection, payload):
    assert libinjection.libinjection_xss(payload, len(payload)) == 1


def test_like_expression_is_detected_as_sqli(libinjection):
    payload = b"1 OR 1 LIKE (1)"
    fingerprint = ctypes.create_string_buffer(8)
    assert libinjection.libinjection_sqli(payload, len(payload), fingerprint) == 1
    assert fingerprint.value == b"1&1o(", "LIKE after operand must remain an operator"


def test_benign_input_stays_benign(libinjection):
    payload = b"ordinary search term"
    fingerprint = ctypes.create_string_buffer(8)
    assert libinjection.libinjection_sqli(payload, len(payload), fingerprint) == 0
    assert libinjection.libinjection_xss(payload, len(payload)) == 0
