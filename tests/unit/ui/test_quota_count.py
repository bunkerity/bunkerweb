"""The UI must show the same billable number the license path sends.

Two places recounted services their own way: the every-request overlap check in
``main.py`` (``len(BW_CONFIG.get_services())``) and the ``/pro`` page
(``online_services``). Both now call ``billable_service_count()``, which is the
shared classifier — otherwise a valid redirect-only service is free on the
license side and still shown as consuming a slot.
"""

import json
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import service_classification  # type: ignore
from app.utils import billable_service_count  # type: ignore

_ROOT = Path(__file__).resolve().parents[3]

SNAPSHOT = {
    "SERVER_NAME": "app.example.com old.example.com draft.example.com",
    "app.example.com_USE_REVERSE_PROXY": "yes",
    "old.example.com_SERVICE_MODE": "redirect_only",
    "old.example.com_REDIRECT_TO": "https://app.example.com",
    # SERVE_FILES defaults to yes, so a redirect service that never sets it still
    # serves the document root -- see CAPABILITY_DEFAULTS in the classifier.
    "old.example.com_SERVE_FILES": "no",
    "draft.example.com_IS_DRAFT": "yes",
}


def _patched_dependencies(snapshot):
    dependencies = ModuleType("app.dependencies")
    dependencies.BW_CONFIG = Mock()
    dependencies.BW_CONFIG.get_config.return_value = snapshot
    return dependencies


def test_billable_count_reads_the_non_default_persisted_config():
    dependencies = _patched_dependencies(SNAPSHOT)
    with patch.dict(sys.modules, {"app.dependencies": dependencies}):
        # The gate is shut (see service_classification.EXEMPTION_ENABLED), so both
        # non-draft services are billed and the draft is not: the same number the
        # UI showed before any of this was wired.
        assert billable_service_count() == 2
    # The classifier's input contract: the NON-default persisted config (full=False),
    # every service (global_only=False), drafts excluded at the source.
    assert dependencies.BW_CONFIG.get_config.call_args.kwargs == {"global_only": False, "methods": False, "with_drafts": False}


def test_billable_count_drops_a_valid_redirect_service_once_lot_c_opens_the_gate():
    dependencies = _patched_dependencies(SNAPSHOT)
    with patch.dict(sys.modules, {"app.dependencies": dependencies}):
        original = service_classification.EXEMPTION_ENABLED
        service_classification.EXEMPTION_ENABLED = True
        try:
            assert billable_service_count() == 1
        finally:
            service_classification.EXEMPTION_ENABLED = original


def test_billable_count_bills_a_redirect_declaration_that_does_not_hold_up():
    snapshot = dict(SNAPSHOT, **{"old.example.com_USE_REVERSE_PROXY": "yes"})
    with patch.dict(sys.modules, {"app.dependencies": _patched_dependencies(snapshot)}):
        assert billable_service_count() == 2


def test_the_live_overlap_check_uses_the_shared_count():
    """Pins the call site: a len() recount here diverges from the license path."""
    source = (_ROOT / "src" / "ui" / "main.py").read_text(encoding="utf-8")
    assert 'pro_overlapped = billable_service_count() > metadata["pro_services"]' in source
    assert "len(BW_CONFIG.get_services())" not in source


def test_the_pro_page_shows_both_numbers():
    """`online_services` must stay the row count: pro.html labels it "Online services".

    The billable figure is what the license is charged for, and it gets its own
    line — conflating the two under the "Online" label would be a lie the moment a
    redirect-only service stops being billed.
    """
    source = (_ROOT / "src" / "ui" / "app" / "routes" / "pro.py").read_text(encoding="utf-8")
    assert "billable_services = billable_service_count()" in source
    assert "online_services = billable_service_count()" not in source
    # The online/draft tiles still count rows — a service-table fact, not a quota one.
    assert 'if service["is_draft"]' in source
    assert "billable_services=billable_services," in source

    template = (_ROOT / "src" / "ui" / "app" / "templates" / "pro.html").read_text(encoding="utf-8")
    assert 'pro.status.services_count", online_services=online_services' in template
    assert 'pro.status.billable_services_count", billable_services=billable_services' in template


def test_the_billable_label_exists_in_every_locale():
    """A key missing from one of the 18 catalogs renders as its own id on that page."""
    locales = sorted((_ROOT / "src" / "ui" / "app" / "static" / "locales").glob("*.json"))
    assert len(locales) == 18
    for path in locales:
        catalog = json.loads(path.read_text(encoding="utf-8"))
        text = catalog["pro"]["status"]["billable_services_count"]
        assert "{{billable_services}}" in text, f"{path.name} lost the interpolation slot"


def test_service_mode_is_not_editable_from_the_generic_form():
    """SERVICE_MODE decides whether a service is free: not a knob on a plugin page.

    Blacklisting closes the UI's generic form only — env and the API still reach
    the setting, which is why the exemption itself is gated off in the classifier.
    """
    from app.utils import get_blacklisted_settings  # type: ignore

    assert "SERVICE_MODE" in get_blacklisted_settings()
    assert "SERVICE_MODE" in get_blacklisted_settings(True)


def test_an_ordinary_service_save_drops_an_env_set_service_mode():
    """KNOWN HAZARD, pinned so Lot C flips a red test instead of finding it live.

    Blacklisting SERVICE_MODE closes the generic per-plugin form (check_variables
    drops it), but the same set is the service page's `restore_skip`, and a stored
    setting that is neither posted nor restored has its row DELETED
    (db_methods/config_save.py). So a SERVICE_MODE that env or the API set is lost
    on the next ordinary save from the UI.

    Accepted for now because it is money-inert: the exemption is gated off, so a
    dropped row reverts the service to `standard` -- billable, fail closed.

    **Lot C must add SERVICE_MODE to `_SERVICE_CONTROL_KEYS` in
    src/ui/app/models/save_scope.py and render its hidden input, in the same change
    that opens the gate.** When it does, this test goes red and should be inverted.
    """
    from app.models.save_scope import control_keys, restore_unowned_settings  # type: ignore
    from app.utils import get_blacklisted_settings  # type: ignore

    stored = {
        "SERVICE_MODE": {"value": "redirect_only", "method": "manual", "template": None},
        "REDIRECT_TO": {"value": "https://app.example.com", "method": "manual", "template": None},
    }
    posted = {"SERVER_NAME": "old.example.com", "OLD_SERVER_NAME": "old.example.com"}

    restored = restore_unowned_settings(posted, stored, restore_skip=get_blacklisted_settings() | set(control_keys()))

    assert "REDIRECT_TO" in restored, "an ordinary setting must survive a save that did not post it"
    assert "SERVICE_MODE" not in restored, "the hazard changed shape -- re-read this docstring"
    assert "SERVICE_MODE" not in control_keys(), "Lot C landed: invert this test and delete the hazard note"
