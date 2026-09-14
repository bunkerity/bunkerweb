"""`schemas.py` must consume the shared validator, not a private copy of it.

Before this lane, `NAME_RX` / `validate_config_name` / the type set were defined locally in
`schemas.py`, duplicating `src/ui/app/routes/configs.py`'s `CONFIG_NAME_RX`. This asserts
identity (the same object, not merely an equal-looking one), so a future revert to a local
copy fails loudly here instead of silently re-opening the drift `report-CC-A.md` found.
"""

import schemas  # type: ignore  (src/api/app on sys.path via conftest)

import custom_configs_validation as shared  # type: ignore  (src/common/utils on sys.path via root conftest)


def test_name_rx_is_the_shared_object():
    """Not just an `is` check: CPython's `re` module caches compiled patterns by (pattern,
    flags), so two independently-written `re.compile(same_string)` calls can accidentally
    return the identical cached object even with no sharing at all -- that made this
    assertion pass against the pre-unification duplicate too. `NAME_RX` re-exported by
    reference (`from custom_configs_validation import NAME_RX`) is still checked with `is`,
    but the pattern-text check alongside it is what actually falls back to catching a
    divergence if the cache detail ever changes."""
    assert schemas.NAME_RX is shared.NAME_RX
    assert schemas.NAME_RX.pattern == shared.NAME_RX.pattern


def test_validate_config_name_is_the_shared_function():
    assert schemas.validate_config_name is shared.validate_name


def test_normalize_config_type_is_the_shared_function():
    assert schemas.normalize_config_type is shared.normalize_type


def test_config_types_matches_the_shared_canonical_set():
    assert schemas.CONFIG_TYPES == set(shared.CUSTOM_CONFIG_TYPES)


def test_config_type_annotation_rejects_what_the_shared_module_rejects():
    """`_normalize_and_validate_config_type` must reject exactly what `normalize_type()`
    rejects -- the ACCEPT/REJECT boundary AC 2 pins -- AND raise `shared.TYPE_ERROR_MESSAGE`
    verbatim, not a local re-derivation of it (Criticos round 1, R1: `schemas.py` used to sort
    `CONFIG_TYPES` itself, which drifted from `TYPE_ERROR_MESSAGE`'s declaration order the
    moment `src/common/cli/CLI.py` started importing that exact constant -- two spellings of
    the identical verdict). The message assertion is the regression test for that fix; the
    boundary assertions alone would stay green even if the sorted re-derivation came back."""
    from pydantic import TypeAdapter

    adapter = TypeAdapter(schemas.ConfigType)
    assert adapter.validate_python("Server-HTTP") == "server_http" == shared.normalize_type("Server-HTTP")
    for good in shared.CUSTOM_CONFIG_TYPES:
        assert adapter.validate_python(good) == good
    try:
        adapter.validate_python("not-a-real-type")
        assert False, "expected a validation error"
    except Exception as exc:
        assert shared.normalize_type("not-a-real-type") is None
        assert shared.TYPE_ERROR_MESSAGE in str(exc), f"schemas.py re-derived its own type-error text instead of reusing TYPE_ERROR_MESSAGE verbatim: {exc}"
