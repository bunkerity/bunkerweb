"""Q8 F-3: the bulk-delete flash has a singular and a plural key, not an English `s` suffix.

The route passed `value="s"` into `"Service{{value}} supprimé : ..."`, which read "Services
supprimé" in French and "Diensts gelöscht" in German. Every language needs its own plural.
"""

from json import loads
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
ROUTE = (REPO / "src" / "ui" / "app" / "routes" / "services.py").read_text(encoding="utf-8")
EN = loads((REPO / "src" / "ui" / "app" / "static" / "locales" / "en.json").read_text(encoding="utf-8"))["services"]["flash"]


def test_the_route_no_longer_builds_a_plural_from_an_english_suffix():
    assert 'translated("services.flash.deleted_service"' not in ROUTE
    assert 'value="s" if len(services_to_delete) > 1' not in ROUTE


def test_singular_and_plural_keys_are_distinct_and_used():
    assert 'translated("services.flash.services_deleted", services=' in ROUTE
    assert 'translated("services.flash.service_deleted", services=' in ROUTE
    assert "{{services}}" in EN["service_deleted"] and "{{services}}" in EN["services_deleted"]
    assert EN["service_deleted"] != EN["services_deleted"]
    assert "{{value}}" not in EN["service_deleted"] + EN["services_deleted"]
