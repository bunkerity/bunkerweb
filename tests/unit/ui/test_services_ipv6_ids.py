"""A service named by an IPv6 address keeps working on the services page.

The page uses the service name as an element id (``#type-<name>``, ``#method-<name>``) and reads it back with a
jQuery ``#id`` selector. A colon is selector syntax, so ``2001:db8::1`` must be turned into a plain id, like the dots
of a hostname. ``idFor`` is a closure of the page script, so its shipped line is sliced out and run in Node.
"""

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(os.environ.get("BW_TEST_SERVICES_JS") or Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "static" / "js" / "pages" / "services.js")
SOURCE = SCRIPT.read_text(encoding="utf-8")
NAMES = ["www.example.com", "192.0.2.10", "2001:db8::1", "::1", "fe80::", "2001:db8:0:0:0:0:0:1"]

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def _ids():
    line = re.search(r"^  const idFor = .*;$", SOURCE, re.M)
    assert line, "idFor is gone from services.js"
    result = subprocess.run(
        ["node", "-e", f"{line.group(0)}\nconsole.log(JSON.stringify({json.dumps(NAMES)}.map(idFor)))"],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    return json.loads(result.stdout)


def test_every_service_name_becomes_a_plain_element_id():
    for name, element_id in zip(NAMES, _ids()):
        assert re.fullmatch(r"[A-Za-z0-9_-]+", element_id), (name, element_id)


def test_a_hostname_keeps_the_id_the_page_always_used():
    assert _ids()[0] == "www-example-com"


def test_two_ipv6_names_do_not_share_an_id():
    ids = _ids()
    assert len({ids[2], ids[3], ids[4]}) == 3
