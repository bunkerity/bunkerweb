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
    ("src/ui/app/routes/instances.py", "message or f'Instance {instance} {ACTIONS[action]['past']} s"),
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


def _site_key(msgnode):
    return ast.unparse(msgnode)[:SITE_KEY_LENGTH]


def _is_translated_call(node):
    if isinstance(node, ast.Call):
        func = node.func
        name = func.id if isinstance(func, ast.Name) else (func.attr if isinstance(func, ast.Attribute) else None)
        return name == "translated"
    return False


def _already_converted(msgnode):
    if msgnode is None:
        return True
    if _is_translated_call(msgnode):
        return True
    if isinstance(msgnode, ast.BoolOp) and isinstance(msgnode.op, ast.Or):
        return any(_is_translated_call(value) for value in msgnode.values)
    return False


def _is_bare_literal(msgnode):
    return isinstance(msgnode, (ast.Constant, ast.JoinedStr))


def _find_sites(path):
    """Every (msgnode, lineno) reaching the user through flash()/handle_error()/TO_FLASH that is
    not already wrapped in `translated(...)`."""
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    sites = []

    class Visitor(ast.NodeVisitor):
        def visit_Call(self, node):
            msgnode = None
            if isinstance(node.func, ast.Name) and node.func.id == "flash":
                msgnode = node.args[0] if node.args else next((kw.value for kw in node.keywords if kw.arg == "message"), None)
            elif isinstance(node.func, ast.Name) and node.func.id == "handle_error":
                msgnode = node.args[0] if node.args else None
            elif isinstance(node.func, ast.Attribute) and node.func.attr == "append" and isinstance(node.func.value, ast.Subscript):
                sub = node.func.value
                if isinstance(sub.slice, ast.Constant) and sub.slice.value == "TO_FLASH" and node.args and isinstance(node.args[0], ast.Dict):
                    d = node.args[0]
                    for key, value in zip(d.keys, d.values):
                        if isinstance(key, ast.Constant) and key.value == "content":
                            msgnode = value
            if msgnode is not None and not _already_converted(msgnode):
                sites.append(msgnode)
            self.generic_visit(node)

    Visitor().visit(tree)
    return sites


def test_no_bare_english_literal_reaches_flash_handle_error_or_to_flash():
    """A plain string/f-string message is always convertible -- there is no allowlist for this
    one. A hit here means a new `flash("...")`/`handle_error("...")`/`TO_FLASH.append({"content":
    "..."})` call landed without going through `translated()`."""
    offenders = []
    for path in TARGET_FILES:
        for msgnode in _find_sites(path):
            if _is_bare_literal(msgnode):
                offenders.append(f"{path.relative_to(ROOT)}:{msgnode.lineno}")
    assert offenders == []


def test_every_non_literal_site_is_a_reviewed_passthrough():
    """Everything that is not a bare literal (a variable, `str(exc)`, `.message`, a subscript, a
    joined `Markup(...)`, ...) must be a site this lane (or an earlier one) reviewed and recorded
    as relaying an already-translated value or a message from an unowned layer. An unlisted site
    is either a missed conversion or a new one introduced since -- review it, then either fix it
    or add it to `REVIEWED_PASSTHROUGH_SITES` with a one-line reason. A listed site that no longer
    appears (the code moved on) must be removed from the allowlist, so this also asserts equality,
    not just "no new offenders"."""
    found = Counter()
    for path in TARGET_FILES:
        relpath = str(path.relative_to(ROOT))
        for msgnode in _find_sites(path):
            if not _is_bare_literal(msgnode):
                found[(relpath, _site_key(msgnode))] += 1

    reviewed = Counter(REVIEWED_PASSTHROUGH_SITES)
    missing_from_allowlist = found - reviewed
    stale_in_allowlist = reviewed - found

    assert not missing_from_allowlist, f"unreviewed passthrough site(s): {sorted(missing_from_allowlist.elements())}"
    assert not stale_in_allowlist, f"allowlisted site(s) no longer found -- update the table: {sorted(stale_in_allowlist.elements())}"


@pytest.mark.parametrize("path", TARGET_FILES, ids=lambda p: str(p.relative_to(ROOT)))
def test_every_scanned_file_still_parses(path):
    """A syntax error in one of the owned files would silently empty that file's `_find_sites()`
    result and pass the two tests above for the wrong reason."""
    ast.parse(path.read_text(encoding="utf-8"))
