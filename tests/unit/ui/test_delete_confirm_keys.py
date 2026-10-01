"""M25: bulk-delete confirmation modals must not say "instance" for a template, config or plugin.

`modal.body.delete_confirmation_alert(_plural)` is hard-coded to "Are you sure you want to delete
the selected instance(s)?" -- correct on `/instances`, wrong everywhere else it got reused.
`templates.js`, `configs.js` and `plugins.js` each already build the *correct* English sentence as
a JS-literal fallback for `t()`, but the shared key's catalog hit shadows it (the catalog is
checked before the fallback, and the key exists -- just says the wrong noun). `configs.js` and
`plugins.js` had a same-shaped, correctly-worded key sitting unused
(`confirm_configs_deletion_alert(_plural)`, `confirm_plugin_deletion(_plural)`); `templates.js`
needed one added (`confirm_templates_deletion_alert(_plural)`, `en.json`).

Source-text assertions: no JS runtime in this suite, and the defect and the fix are both which
catalog key string appears in the delete-modal builder -- exactly what a source read settles.
"""

from pathlib import Path

import pytest

JS = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "static" / "js" / "pages"

CASES = [
    ("templates.js", "modal.body.confirm_templates_deletion_alert", "modal.body.confirm_templates_deletion_alert_plural"),
    ("configs.js", "modal.body.confirm_configs_deletion_alert", "modal.body.confirm_configs_deletion_alert_plural"),
    # plugins.js was the retired DataTable page (deleted in Q8); the live grid deletes through the shared modal in plugins.html.
]


@pytest.mark.parametrize("filename,singular_key,plural_key", CASES)
def test_the_bulk_delete_modal_asks_for_its_own_resource_key(filename, singular_key, plural_key):
    source = (JS / filename).read_text(encoding="utf-8")

    assert singular_key in source, f"{filename}: expected {singular_key!r} in the delete-modal builder"
    assert plural_key in source, f"{filename}: expected {plural_key!r} in the delete-modal builder"


@pytest.mark.parametrize("filename,singular_key,plural_key", CASES)
def test_the_bulk_delete_modal_no_longer_asks_the_instance_key(filename, singular_key, plural_key):
    """The old, wrong key, as an exact quoted string literal -- not a ban on the substring, which
    is also a prefix of the (fine, still used elsewhere) `..._plural` and `confirmation_instance_
    deletion` keys."""
    source = (JS / filename).read_text(encoding="utf-8")

    assert '"modal.body.delete_confirmation_alert"' not in source, filename
    assert '"modal.body.delete_confirmation_alert_plural"' not in source, filename
