"""Every instance status the model can carry has a `status.<value>` catalog key (smoke Q8 1c: `status.failover` rendered raw)."""

import re
from json import loads
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]


def test_every_instance_status_has_a_catalog_key():
    source = (REPO / "src" / "ui" / "app" / "models" / "instance.py").read_text(encoding="utf-8")
    values = set(re.search(r"status: Literal\[([^\]]+)\]", source).group(1).replace('"', "").replace(" ", "").split(","))
    catalog = loads((REPO / "src" / "ui" / "app" / "static" / "locales" / "en.json").read_text(encoding="utf-8"))["status"]

    assert values >= {"up", "down", "loading", "failover"}
    assert [value for value in sorted(values) if value not in catalog] == []
