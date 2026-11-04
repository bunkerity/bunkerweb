"""app/raw_drafts.py: the RAW editor's draft metadata is validated before it can reach the database."""

import json

import pytest

from app.raw_drafts import (
    RAW_DRAFT_SETTINGS,
    RAW_PRESENT_SETTINGS,
    RawDraftSettingsError,
    existing_draft_keys,
    parse_raw_draft_settings,
)

SETTINGS = {
    "USE_X": {"context": "multisite"},
    "LOG_LEVEL": {"context": "global"},
    "REVERSE_PROXY_HOST": {"context": "multisite", "multiple": "reverse-proxy"},
    "PLAIN": {"context": "multisite"},
}


def parse(drafts, present, posted, **kwargs):
    kwargs.setdefault("settings", SETTINGS)
    return parse_raw_draft_settings(json.dumps(drafts), posted_keys=set(posted), present_value=json.dumps(present), **kwargs)


class TestExistingDraftKeys:
    def test_only_mapping_rows_flagged_as_drafts(self):
        config = {"a": {"is_draft": True}, "b": {"is_draft": False}, "c": "x", "d": {"other": 1}}
        assert existing_draft_keys(config) == ("a",)


class TestGlobalForm:
    def test_posted_present_keys_get_an_explicit_boolean(self):
        result = parse(["USE_X"], ["USE_X", "LOG_LEVEL"], ["USE_X", "LOG_LEVEL"])
        assert result == {"USE_X": True, "LOG_LEVEL": False}

    def test_multiple_suffix_is_a_known_setting(self):
        assert parse(["REVERSE_PROXY_HOST_1"], ["REVERSE_PROXY_HOST_1"], ["REVERSE_PROXY_HOST_1"]) == {"REVERSE_PROXY_HOST_1": True}

    def test_posted_but_absent_from_present_is_left_out(self):
        assert parse([], ["USE_X"], ["USE_X", "PLAIN"]) == {"USE_X": False}

    def test_unknown_posted_keys_are_ignored_not_fatal(self):
        assert parse([], ["USE_X"], ["USE_X", "NOT_A_SETTING"]) == {"USE_X": False}

    def test_saved_draft_missing_from_the_editor_is_deleted(self):
        result = parse([], ["USE_X"], ["USE_X"], existing_draft_keys=["LOG_LEVEL", "UNKNOWN_ONE"])
        assert result == {"USE_X": False, "LOG_LEVEL": None}

    def test_existing_drafts_are_untouched_without_the_hint(self):
        assert parse([], ["USE_X"], ["USE_X"]) == {"USE_X": False}


class TestServiceForm:
    def test_bare_editor_names_become_prefixed_keys(self):
        result = parse(["USE_X"], ["USE_X"], ["USE_X"], service="a.com")
        assert result == {"a.com_USE_X": True}

    def test_source_service_prefix_is_recognised_for_clones(self):
        result = parse(["old.com_USE_X"], ["old.com_USE_X"], ["old.com_USE_X"], service="new.com", source_services=["old.com"])
        assert result == {"new.com_USE_X": True}

    def test_global_settings_are_skipped_in_a_service_form(self):
        assert parse([], ["USE_X", "LOG_LEVEL"], ["USE_X", "LOG_LEVEL"], service="a.com") == {"a.com_USE_X": False}

    def test_a_service_cannot_draft_a_global_setting(self):
        with pytest.raises(RawDraftSettingsError, match="Global setting LOG_LEVEL cannot be made a service draft"):
            parse(["LOG_LEVEL"], ["LOG_LEVEL"], ["LOG_LEVEL"], service="a.com")

    def test_deleted_draft_of_a_global_setting_is_not_emitted_for_a_service(self):
        result = parse([], ["USE_X"], ["USE_X"], service="a.com", existing_draft_keys=["a.com_LOG_LEVEL", "a.com_PLAIN"])
        assert result == {"a.com_USE_X": False, "a.com_PLAIN": None}


class TestRejections:
    @pytest.mark.parametrize("raw", [None])
    def test_missing_metadata(self, raw):
        with pytest.raises(RawDraftSettingsError, match=f"Missing {RAW_DRAFT_SETTINGS} metadata"):
            parse_raw_draft_settings(raw, posted_keys=set(), present_value="[]")

    def test_missing_present_metadata(self):
        with pytest.raises(RawDraftSettingsError, match=f"Missing {RAW_PRESENT_SETTINGS} metadata"):
            parse_raw_draft_settings("[]", posted_keys=set(), present_value=None)

    @pytest.mark.parametrize("raw", ["{not json", '{"a": 1}', "[1, 2]", '["a", "a"]'])
    def test_malformed_lists(self, raw):
        with pytest.raises(RawDraftSettingsError, match="must be a JSON list of setting names|duplicate"):
            parse_raw_draft_settings(raw, posted_keys=set(), present_value="[]")

    def test_duplicates_have_their_own_message(self):
        with pytest.raises(RawDraftSettingsError, match=f"{RAW_DRAFT_SETTINGS} contains duplicate setting names"):
            parse_raw_draft_settings('["a", "a"]', posted_keys=set(), present_value="[]")

    def test_non_string_input_is_a_parse_error(self):
        with pytest.raises(RawDraftSettingsError, match="must be a JSON list"):
            parse_raw_draft_settings(123, posted_keys=set(), present_value="[]")

    @pytest.mark.parametrize("name", ["SERVER_NAME", "IS_DRAFT", "USE_TEMPLATE", "MULTISITE", "DATABASE_URI"])
    def test_structural_settings_are_never_drafts(self, name):
        with pytest.raises(RawDraftSettingsError, match=f"Setting {name} cannot be made a draft"):
            parse([name], [name], [name])

    def test_draft_must_have_been_posted(self):
        with pytest.raises(RawDraftSettingsError, match="Draft setting USE_X was not posted"):
            parse(["USE_X"], ["USE_X"], [])

    def test_draft_must_be_a_known_setting(self):
        with pytest.raises(RawDraftSettingsError, match="Setting MADE_UP is not valid"):
            parse(["MADE_UP"], ["MADE_UP"], ["MADE_UP"])

    def test_no_settings_catalog_means_nothing_is_known(self):
        with pytest.raises(RawDraftSettingsError, match="Setting USE_X is not valid"):
            parse(["USE_X"], ["USE_X"], ["USE_X"], settings=None)
        with pytest.raises(RawDraftSettingsError, match="Setting USE_X is not valid"):
            parse(["USE_X"], ["USE_X"], ["USE_X"], settings={})

    def test_draft_must_be_in_the_editor(self):
        with pytest.raises(RawDraftSettingsError, match="Draft setting USE_X is not present in the RAW editor"):
            parse(["USE_X"], [], ["USE_X"])

    def test_present_must_have_been_posted(self):
        with pytest.raises(RawDraftSettingsError, match="Present setting PLAIN was not posted"):
            parse([], ["USE_X", "PLAIN"], ["USE_X"])

    def test_present_must_be_known(self):
        with pytest.raises(RawDraftSettingsError, match="Present setting MADE_UP is not valid"):
            parse([], ["MADE_UP"], ["MADE_UP"])

    def test_structural_controls_in_present_are_ignored(self):
        assert parse([], ["USE_X", "SERVER_NAME"], ["USE_X", "SERVER_NAME"]) == {"USE_X": False}

    def test_multiple_suffix_needs_a_multiple_setting(self):
        with pytest.raises(RawDraftSettingsError, match="Setting USE_X_1 is not valid"):
            parse(["USE_X_1"], ["USE_X_1"], ["USE_X_1"])
