"""FIX-QA5-I18N item 1: every `flash(...)`, `handle_error(...)` and `DATA["TO_FLASH"].append(...)`
call site in the owned globs must route its message through `app.i18n.translated`, not a bare
English literal. This is the AST scanner the lane used to convert ~500 call sites, kept on as a
regression test so a new literal introduced later fails the suite instead of shipping untranslated.

Two separate guarantees:

* No site may pass a plain string/f-string literal directly (``sites_with_bare_literal`` must be
  empty, always -- there is no allowlist for this, a literal is always convertible).
* A site that passes something else (a bare variable, `str(exc)`, `.message`, a subscript, ...) is
  legitimate only when the value was already resolved through `translated()` upstream -- e.g. at
  the `raise ValueError(translated(...) or "...")` site, or because it genuinely relays a message
  from a layer this brief does not own (an API error body, a stdlib exception). Each such site is
  reviewed once and named in ``REVIEWED_PASSTHROUGH_SITES`` (the report's pass-through table); an
  unlisted one fails the test, forcing a conscious decision -- fix it, or review and allowlist it.
"""

import ast
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]

TARGET_FILES = sorted((ROOT / "src/ui/app/routes").glob("*.py")) + [ROOT / "src/ui/main.py"] + sorted((ROOT / "src/common/core").glob("*/ui/*.py"))

# (file relative to ROOT, the message argument's source as `ast.unparse` prints it, cut at
# `SITE_KEY_LENGTH` chars) -- reviewed in report-FIX-QA5-I18N.md's pass-through tables. Keyed on
# the expression, not the line number, so reformatting or an edit above a site does not stale the
# table; a repeated expression in one file is listed once per occurrence (compared as a multiset).
REVIEWED_PASSTHROUGH_SITES = [
    # certificates.py: `_refuse`'s own relay + the `str(exc)` from an already-translated raise.
    ("src/ui/app/routes/certificates.py", "message"),
    ("src/ui/app/routes/certificates.py", "str(exc)"),
    # global_settings.py: `operation`/`content` already resolved before being appended.
    ("src/ui/app/routes/global_settings.py", "content"),
    ("src/ui/app/routes/global_settings.py", "operation"),
    # instances.py: `common_utils.parse_host` (ValueError, not owned) and an `Instance` model
    # method's return value (app/models/, not routes/*.py).
    ("src/ui/app/routes/instances.py", "message"),
    ("src/ui/app/routes/instances.py", "ret"),
    # reload/stop message is resolved by translated() before its explicit English fallback.
    ("src/ui/app/routes/instances.py", "message or f\"Instance {instance} {ACTIONS[action]['past']} s"),
    # jobs.py: `e.message` from ApiClientError/ApiUnavailableError -- the API's own error body.
    ("src/ui/app/routes/jobs.py", "e.message"),
    # login.py: already-translated message re-raised as `str(exc)`.
    ("src/ui/app/routes/login.py", 'Markup(\'{} <a href="#" class="alert-link" data-dismiss-notic'),
    # plugins.py: `message` (translated at both branches above), `str(e)` from TarError/OSError/
    # Exception (library relay), `done` (translated at both call sites), `str(e)` from `_Refusal`
    # (translated at every raise site).
    ("src/ui/app/routes/plugins.py", "message"),
    # delete_plugin translates both caught API error messages before appending this value.
    ("src/ui/app/routes/plugins.py", "message"),
    ("src/ui/app/routes/plugins.py", "str(e)"),
    ("src/ui/app/routes/plugins.py", "str(e)"),
    ("src/ui/app/routes/plugins.py", "done"),
    ("src/ui/app/routes/plugins.py", "str(e)"),
    ("src/ui/app/routes/plugins.py", "str(e)"),
    # pro.py: `operation` (translated at its two assignment sites) + `e.message` (API relay) x3.
    ("src/ui/app/routes/pro.py", "operation"),
    ("src/ui/app/routes/pro.py", "operation"),
    ("src/ui/app/routes/pro.py", "operation"),
    ("src/ui/app/routes/pro.py", "e.message"),
    ("src/ui/app/routes/pro.py", "e.message"),
    ("src/ui/app/routes/pro.py", "e.message"),
    # redirects.py / resource_groups.py / upstreams.py / workflows.py: `str(exc)` from a
    # `ValueError` already translated at its raise site (`_rule`/`_services`/`_attachments`/
    # `_pool`/`_alias`/`_entries`/`_identity`, and the routes' own inline raises).
    ("src/ui/app/routes/redirects.py", "str(exc)"),
    ("src/ui/app/routes/redirects.py", "str(exc)"),
    ("src/ui/app/routes/redirects.py", "str(exc)"),
    ("src/ui/app/routes/resource_groups.py", "str(exc)"),
    ("src/ui/app/routes/resource_groups.py", "str(exc)"),
    ("src/ui/app/routes/upstreams.py", "str(exc)"),
    ("src/ui/app/routes/upstreams.py", "str(exc)"),
    ("src/ui/app/routes/upstreams.py", "str(exc)"),
    ("src/ui/app/routes/workflows.py", "str(exc)"),
    ("src/ui/app/routes/workflows.py", "str(exc)"),
    ("src/ui/app/routes/workflows.py", "str(exc)"),
    # services.py: `operation`/`ret`/`refusal`/`getattr(e, "message", ...)` -- Configurator,
    # default_server.py and ApiClientError bodies, none of which routes/*.py owns (see report).
    ("src/ui/app/routes/services.py", "str(e)"),
    ("src/ui/app/routes/services.py", "getattr(e, 'message', None) or str(e)"),
    ("src/ui/app/routes/services.py", "ret"),
    ("src/ui/app/routes/services.py", "message"),
    ("src/ui/app/routes/services.py", "operation"),
    ("src/ui/app/routes/services.py", "operation"),
    ("src/ui/app/routes/services.py", "operation"),
    ("src/ui/app/routes/services.py", "refusal"),
    # RAW setting drafts (app/raw_drafts.py): `draft_edits_discarded()`, `metadata_raw_only()` and the
    # `RawDraftSettingsError`/`locked_draft_change` messages are built by `raw_drafts._msg`, which is
    # `translated("raw_drafts.<key>") or <English>`; the service "not edited" flash appends that notice.
    ("src/ui/app/routes/global_settings.py", "draft_edits_discarded()"),
    ("src/ui/app/routes/global_settings.py", "error"),
    ("src/ui/app/routes/global_settings.py", "metadata_raw_only()"),
    ("src/ui/app/routes/global_settings.py", "str(error)"),
    ("src/ui/app/routes/services.py", "(translated('services.flash.service_not_edited_because_no_va"),
    ("src/ui/app/routes/services.py", "draft_edits_discarded()"),
    ("src/ui/app/routes/services.py", "error"),
    ("src/ui/app/routes/services.py", "metadata_raw_only()"),
    ("src/ui/app/routes/services.py", "str(error)"),
    # templates.py: `permission["message"]` (translated in `_check_permissions`) and the joined
    # `errors` list (each entry translated at its own `.append(...)` site).
    ("src/ui/app/routes/templates.py", "permission['message']"),
    ("src/ui/app/routes/templates.py", "' '.join(errors)"),
    # submit_config_task resolves the error in the request locale before the callback.
    ("src/ui/app/routes/utils.py", "error_message"),
    # utils.py: `verify_data_in_form`/`handle_error`'s own internal calls -- the shared helpers
    # forward whatever their caller already resolved (every caller's own literal is converted at
    # its call site, not here).
    ("src/ui/app/routes/utils.py", "err_message"),
    ("src/ui/app/routes/utils.py", "err_message"),
    # main.py: `Markup(...).format(...)` built from already-translated pieces (the MFA reminder,
    # the push-configs banners, the failover messages), and the `TO_FLASH` flush loop (`content`
    # was resolved by whichever route queued it).
    ("src/ui/main.py", 'Markup(\'{}\\n<div class="mt-2 pt-2 border-top border-white">\\'),
    ("src/ui/main.py", "Markup(\"{} <a class='alert-link' href='{}'>{}</a>\").format(m"),
    ("src/ui/main.py", "Markup(\"{} <a class='alert-link' href='{}'>{}</a>\").format(m"),
    ("src/ui/main.py", "Markup(\"<p class='p-0 m-0 fst-italic'>{}</p>\").format(transl"),
    ("src/ui/main.py", "Markup(\"<div class='d-flex flex-column'>\\n                  "),
    ("src/ui/main.py", "content"),
    # letsencrypt/ui/hooks.py: `Markup(text)` where `text` was resolved through `translated()`
    # two lines above.
    ("src/common/core/letsencrypt/ui/hooks.py", "Markup(text)"),
]


SITE_KEY_LENGTH = 60


def _key_of(source):
    # Quote style is not stable across CPython releases (3.12.x changed how `ast.unparse` quotes
    # nested f-strings), so keys compare with every `"` read as `'`.
    return source[:SITE_KEY_LENGTH].replace('"', "'")


def _reviewed_counter():
    return Counter((path, _key_of(key)) for path, key in REVIEWED_PASSTHROUGH_SITES)


@pytest.mark.parametrize("path", TARGET_FILES, ids=lambda p: str(p.relative_to(ROOT)))
def test_every_scanned_file_still_parses(path):
    """A syntax error in one of the owned files would silently empty that file's `_find_sites()`
    result and pass the two tests above for the wrong reason."""
    ast.parse(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "unparsed",
    [
        "message or f'Instance {instance} {ACTIONS[action]['past']} successfully.'",
        "message or f\"Instance {instance} {ACTIONS[action]['past']} successfully.\"",
    ],
    ids=["single-quoted", "double-quoted"],
)
def test_the_instances_key_matches_whichever_quotes_unparse_prints(unparsed):
    """`ast.unparse` quoted nested f-strings differently between 3.12.x releases; the allowlist must
    not depend on which one the interpreter running the suite prints."""
    assert ("src/ui/app/routes/instances.py", _key_of(unparsed)) in _reviewed_counter()
