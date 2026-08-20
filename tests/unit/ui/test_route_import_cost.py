"""Two boot-time costs the UI pays on every request path but only needs on a few.

Both are the same shape: something expensive placed where it is *always* paid, to serve a case that
is *rarely* reached. Neither is a bug in the sense of a wrong answer, which is why they survive
review — the page is correct, it is only heavier than it has any reason to be.
"""

import ast
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
ROUTES = REPO / "src" / "ui" / "app" / "routes"
TOTP = REPO / "src" / "ui" / "app" / "models" / "totp.py"

# Imports whose cost is out of proportion to how often a route module actually needs them, with the
# measurement that says so. Add to this only with a number, taken in the image, not from intuition —
# and read `-X importtime` correctly: its second column is *cumulative*, so a parent already
# contains its children and summing that column down a 340-module tree inflates the total roughly
# tenfold. Sum the first column (self), or read the cumulative of the top-level row, never both.
EXPENSIVE = {"openpyxl": "311 modules / ~120 ms in the UI image, 2026-08-19 — XLSX export only"}


def _route_modules():
    return sorted(path for path in ROUTES.glob("*.py") if path.name != "__init__.py")


@pytest.mark.parametrize("path", _route_modules(), ids=lambda path: path.name)
def test_no_route_module_pays_an_expensive_import_at_startup(path):
    """`main.py` imports every blueprint at boot, so a module-scope import in any route module is
    paid by every UI worker before it serves its first request.

    `bans.py` and `reports.py` both did this with `openpyxl`, for an XLSX export that most
    deployments never call. Moved into the export functions: same behaviour, and the cost lands on
    whoever actually asked for a spreadsheet.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    offenders = []

    for node in tree.body:  # module scope only — a nested import is exactly the fix
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        else:
            continue
        offenders += [f"{path.name}:{node.lineno} {name} ({EXPENSIVE[root]})" for name in names for root in [name.split(".")[0]] if root in EXPENSIVE]

    assert not offenders, f"move these inside the function that needs them: {offenders}"


def test_the_totp_qr_code_is_a_png():
    """A QR code is flat black-on-white line art: the worst input for a lossy codec, the best for
    PNG's filtering. The same code measured 29,528 bytes as JPEG against 996 as PNG — 39,372 vs
    1,328 base64'd into the data URI the enrolment page carries (UI image, 2026-08-19).

    Size is the visible half; the reason it is not merely cosmetic is that JPEG rings around the
    finder patterns, and this image exists to be read by a machine.

    The format and the MIME type are asserted together because splitting them is the way this
    breaks: a PNG served as `data:image/jpeg` is a broken enrolment page, not a slow one.
    """
    source = TOTP.read_text(encoding="utf-8")

    assert re.search(r'\.save\(virtual_file, format="PNG"\)', source), "the QR is no longer written as PNG"
    assert 'f"data:image/png;base64,{image_as_str}"' in source, "the data URI does not declare the format actually written"
