"""What survives a save that only owns part of a service's configuration.

`Database.save_config` deletes the row for any key the payload omits
(`db_methods/config_save.py:592`). These tests pin down which keys
`restore_unowned_settings` puts back, and — just as importantly — which it
deliberately does not, because a key it wrongly restores is a user's clear that
silently did not happen.
"""

import pytest

from app.models.save_scope import restore_unowned_settings

RESTORE_SKIP = {"SERVER_NAME", "OLD_SERVER_NAME", "USE_TEMPLATE", "USE_UI", "IS_DRAFT"}


def _entry(value, method="ui", template=""):
    return {"value": value, "method": method, "template": template}


def _db(**pairs):
    """db_config shorthand: KEY=(value, method) or KEY=(value, method, template)."""
    return {key: _entry(*args) for key, args in pairs.items()}


# ---------------------------------------------------------------- scope=None
# With no scope declared the function must behave exactly as the loop it
# replaces, or this slice is not invisible.


def test_scope_none_restores_non_editable_methods():
    db_config = _db(X_FRAME_OPTIONS=("SAMEORIGIN", "scheduler"))
    result = restore_unowned_settings({}, db_config, restore_skip=RESTORE_SKIP)
    assert result == {"X_FRAME_OPTIONS": "SAMEORIGIN"}


def test_scope_none_does_not_restore_ui_owned_keys():
    """A ui-method key absent from the payload is a real clear and must delete."""
    db_config = _db(USE_ANTIBOT=("captcha", "ui"))
    result = restore_unowned_settings({}, db_config, restore_skip=RESTORE_SKIP)
    assert result == {}


def test_scope_none_restores_template_defaults_when_template_unchanged():
    db_config = _db(SSL_PROTOCOLS=("TLSv1.2 TLSv1.3", "default", "low"))
    result = restore_unowned_settings({}, db_config, restore_skip=RESTORE_SKIP, template_unchanged=True)
    assert result == {"SSL_PROTOCOLS": "TLSv1.2 TLSv1.3"}


def test_template_unchanged_defaults_to_true():
    """`template_unchanged` defaults to True: a 3-arg call is the documented "adopt this
    before you can compute a scope" path, and it must mean "template did not change"."""
    db_config = _db(SSL_PROTOCOLS=("TLSv1.2 TLSv1.3", "default", "low"))
    result = restore_unowned_settings({}, db_config, restore_skip=RESTORE_SKIP)
    assert result == {"SSL_PROTOCOLS": "TLSv1.2 TLSv1.3"}


def test_scope_none_drops_outgoing_template_defaults_when_template_changed():
    """Switching template must not freeze the old template's values into the service."""
    db_config = _db(SSL_PROTOCOLS=("TLSv1.2 TLSv1.3", "default", "low"))
    result = restore_unowned_settings({}, db_config, restore_skip=RESTORE_SKIP, template_unchanged=False)
    assert result == {}


def test_bare_default_is_restored_even_when_template_changed():
    """The template guard only skips defaults that came FROM a template.

    A bare default (no template attached) must still be restored during a
    template switch -- ``entry.get("template")`` is the conjunct that scopes
    the guard to outgoing-template values, not to every "default" method.
    """
    db_config = _db(X_FRAME_OPTIONS=("SAMEORIGIN", "default"))
    result = restore_unowned_settings({}, db_config, restore_skip=RESTORE_SKIP, template_unchanged=False)
    assert result == {"X_FRAME_OPTIONS": "SAMEORIGIN"}


def test_non_default_method_with_template_is_restored_on_template_switch():
    """The template guard also requires ``setting_method == "default"``, not just a
    template value being present.

    Not reachable from today's producers -- every site in db_methods/config_read.py that
    sets a template also hardcodes method "default" -- so this pins a defensive contract
    rather than a live bug: a scheduler-owned row that merely records a template must
    still be restored, never skipped as if it were an outgoing template default.
    """
    db_config = _db(X=("1", "scheduler", "low"))
    result = restore_unowned_settings({}, db_config, restore_skip=RESTORE_SKIP, template_unchanged=False)
    assert result == {"X": "1"}


def test_restore_skip_defaults_to_empty_set():
    """``restore_skip`` defaults to None in the signature; omitting it must still work via
    the `or set()` normalisation rather than raising on `setting in None`."""
    result = restore_unowned_settings({}, _db(X=("1", "scheduler")))
    assert result == {"X": "1"}


def test_restore_skip_keys_are_never_restored():
    db_config = _db(USE_TEMPLATE=("low", "scheduler"), SERVER_NAME=("app.example.com", "scheduler"))
    result = restore_unowned_settings({}, db_config, restore_skip=RESTORE_SKIP)
    assert result == {}


def test_posted_keys_are_never_overwritten():
    db_config = _db(USE_ANTIBOT=("captcha", "scheduler"))
    result = restore_unowned_settings({"USE_ANTIBOT": "no"}, db_config, restore_skip=RESTORE_SKIP)
    assert result == {"USE_ANTIBOT": "no"}


def test_payload_is_not_mutated():
    payload = {"USE_ANTIBOT": "no"}
    db_config = _db(X_FRAME_OPTIONS=("SAMEORIGIN", "scheduler"))
    restore_unowned_settings(payload, db_config, restore_skip=RESTORE_SKIP)
    assert payload == {"USE_ANTIBOT": "no"}


# --------------------------------------------------------------- scope given
# The new behaviour: a form owning part of the config cannot delete the rest.


def test_out_of_scope_ui_owned_key_is_preserved():
    """The whole point: an antibot page must not delete limit's ui-owned rows."""
    db_config = _db(USE_ANTIBOT=("captcha", "ui"), LIMIT_REQ_RATE=("10r/s", "ui"))
    result = restore_unowned_settings({"USE_ANTIBOT": "no"}, db_config, scope={"USE_ANTIBOT", "ANTIBOT_URI"}, restore_skip=RESTORE_SKIP)
    assert result == {"USE_ANTIBOT": "no", "LIMIT_REQ_RATE": "10r/s"}


def test_in_scope_key_omitted_from_payload_still_clears():
    """Clearing a ui-owned setting from its own page must still go through."""
    db_config = _db(ANTIBOT_URI=("/challenge", "ui"))
    result = restore_unowned_settings({}, db_config, scope={"USE_ANTIBOT", "ANTIBOT_URI"}, restore_skip=RESTORE_SKIP)
    assert result == {}


def test_in_scope_non_editable_key_is_restored():
    """Inside the declared scope, the method-based protection still applies."""
    db_config = _db(X_FRAME_OPTIONS=("SAMEORIGIN", "scheduler"))
    result = restore_unowned_settings({}, db_config, scope={"X_FRAME_OPTIONS"}, restore_skip=RESTORE_SKIP)
    assert result == {"X_FRAME_OPTIONS": "SAMEORIGIN"}


def test_out_of_scope_key_is_preserved_regardless_of_method():
    db_config = _db(A=("1", "ui"), B=("2", "api"), C=("3", "scheduler"), D=("4", "default"))
    result = restore_unowned_settings({}, db_config, scope=set(), restore_skip=RESTORE_SKIP)
    assert result == {"A": "1", "B": "2", "C": "3", "D": "4"}


def test_restore_skip_wins_over_scope_preservation():
    """restore_skip must win even for an out-of-scope, non-editable-method key."""
    db_config = _db(SERVER_NAME=("app.example.com", "scheduler"))
    result = restore_unowned_settings({}, db_config, scope=set(), restore_skip=RESTORE_SKIP)
    assert result == {}


def test_outgoing_template_default_not_carried_forward_even_when_out_of_scope():
    """The template guard is hoisted above the scope branch on purpose.

    Changing USE_TEMPLATE happens on the service page, whose scope excludes every
    plugin setting -- so without the hoist the preserve branch would materialise
    the outgoing template's values as real service rows.
    """
    db_config = _db(SSL_PROTOCOLS=("TLSv1.2 TLSv1.3", "default", "low"))
    result = restore_unowned_settings({}, db_config, scope=set(), restore_skip=RESTORE_SKIP, template_unchanged=False)
    assert result == {}


def test_empty_scope_and_empty_db_config_is_a_no_op():
    assert restore_unowned_settings({}, {}, scope=set(), restore_skip=RESTORE_SKIP) == {}


def test_suffixed_multiple_key_matches_a_base_name_scope():
    """A scope derived from plugin.json carries base names; suffixed `multiple`
    settings must still be recognised as in-scope so a real clear goes through."""
    db_config = _db(REVERSE_PROXY_URL_2=("/app", "ui"))
    result = restore_unowned_settings({}, db_config, scope={"REVERSE_PROXY_URL"}, restore_skip=RESTORE_SKIP)
    assert result == {}


def test_similar_key_is_not_swallowed_by_base_matching():
    """Base-matching must strip a genuine `_<digits>` suffix only, not match by prefix."""
    db_config = _db(LIMIT_REQ_RATE=("10r/s", "ui"))
    result = restore_unowned_settings({}, db_config, scope={"LIMIT_REQ"}, restore_skip=RESTORE_SKIP)
    assert result == {"LIMIT_REQ_RATE": "10r/s"}


def test_suffixed_scope_key_matches_the_stored_suffixed_key():
    """`_in_scope`'s exact-match branch: a scope built from posted field names carries the
    suffixed key itself, not its base -- that's how a multi-value page posts its own fields."""
    db_config = _db(REVERSE_PROXY_URL_2=("/app", "ui"))
    result = restore_unowned_settings({}, db_config, scope={"REVERSE_PROXY_URL_2"}, restore_skip=RESTORE_SKIP)
    assert result == {}


def test_base_matching_requires_a_terminal_numeric_suffix():
    """The `$` anchor in the suffix regex: without it, a mid-string `_<digits>` segment
    would rsplit into a false base match instead of correctly leaving the key out of scope."""
    db_config = _db(FOO_2_BAR=("1", "ui"))
    result = restore_unowned_settings({}, db_config, scope={"FOO_2"}, restore_skip=RESTORE_SKIP)
    assert result == {"FOO_2_BAR": "1"}


def test_multi_digit_suffix_matches_a_base_name_scope():
    """The `+` in `_\\d+$`: multi-value suffixes routinely pass 9 -- `reverseproxy` alone
    declares 19 `multiple` settings -- so a single-digit pattern would leave every entry
    from _10 upwards permanently unclearable."""
    db_config = _db(REVERSE_PROXY_URL_10=("/app", "ui"))
    result = restore_unowned_settings({}, db_config, scope={"REVERSE_PROXY_URL"}, restore_skip=RESTORE_SKIP)
    assert result == {}


def test_trailing_digit_without_a_separator_is_not_a_suffix():
    """The leading `_` in `_\\d+$`: real setting ids end in a bare digit (LIMIT_CONN_MAX_HTTP2,
    ANTIBOT_RECAPTCHA_JA3, USE_IPV6). Those are whole names, not indexed entries, and must not
    be stripped down to a base that happens to be in scope."""
    db_config = _db(LIMIT_CONN_MAX_HTTP2=("100", "ui"))
    result = restore_unowned_settings({}, db_config, scope={"LIMIT_CONN_MAX"}, restore_skip=RESTORE_SKIP)
    assert result == {"LIMIT_CONN_MAX_HTTP2": "100"}


# ------------------------------------------------------------- parity oracle
# A verbatim copy of the loop this function replaces (services.py:447-455 as of
# f903102b2). Same pattern as test_plugin_activation.py's LEGACY_SPECIFICS: the
# old implementation is kept as the thing the new one must agree with.


def _legacy_restore(payload, db_config, restore_skip, template_unchanged):
    from app.utils import is_editable_method

    variables = dict(payload)
    for setting, value in db_config.items():
        if setting in variables or setting in restore_skip:
            continue
        setting_method = value.get("method")
        if not is_editable_method(setting_method, allow_default=False):
            if setting_method == "default" and value.get("template") and not template_unchanged:
                continue
            variables[setting] = value["value"]
    return variables


PARITY_CASES = [
    pytest.param({}, _db(A=("1", "ui")), True, id="ui-method-cleared"),
    pytest.param({}, _db(A=("1", "api")), True, id="api-method-cleared"),
    pytest.param({}, _db(A=("1", "scheduler")), True, id="scheduler-method-restored"),
    pytest.param({}, _db(A=("1", "default")), True, id="bare-default-restored"),
    pytest.param({}, _db(A=("1", "default", "low")), True, id="template-default-kept"),
    pytest.param({}, _db(A=("1", "default", "low")), False, id="template-default-dropped"),
    pytest.param({"A": "2"}, _db(A=("1", "api")), True, id="posted-wins"),
    pytest.param({}, _db(USE_TEMPLATE=("low", "api")), True, id="restore-skip-honoured"),
    pytest.param({}, _db(A=("1", "ui"), B=("2", "api"), C=("3", "default", "high")), False, id="mixed"),
]


@pytest.mark.parametrize("payload, db_config, template_unchanged", PARITY_CASES)
def test_scope_none_matches_the_loop_it_replaces(payload, db_config, template_unchanged):
    assert restore_unowned_settings(payload, db_config, scope=None, restore_skip=RESTORE_SKIP, template_unchanged=template_unchanged) == _legacy_restore(
        payload, db_config, RESTORE_SKIP, template_unchanged
    )


def test_draft_and_identity_keys_are_never_restored():
    """restore_skip keys are the caller's responsibility, whatever the scope.

    IS_DRAFT is the sharp edge: `services.py` does `variables.pop("IS_DRAFT", "no")`, so a
    surface that omits it publishes a draft service. This test pins that the restore loop
    will NOT quietly cover for that -- the page must post these keys itself.
    """
    db_config = _db(IS_DRAFT=("yes", "ui"), SERVER_NAME=("app.example.com", "ui"), USE_TEMPLATE=("low", "ui"))
    result = restore_unowned_settings({}, db_config, scope=set(), restore_skip=RESTORE_SKIP)
    assert result == {}
