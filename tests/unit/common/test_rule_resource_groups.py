"""Resource-group ``@name`` references inside a composite (AND) rule.

Everywhere else a group token is a bare, space-separated word in a flat list. Inside a rule it
is a *term value* (``ip:@office``), which is why three separate places had to learn about it:
validation (which kind does this token have to satisfy?), expansion (what does it become?) and
the reference scanner that decides whether a group is still in use before it can be deleted.

The expansion rule that matters most is the fail-closed one: an unresolvable reference kills
the whole rule, never just its term. Dropping a term from a conjunction *widens* it, so
``ip:@office AND ua:^Bot`` losing its first term would whitelist every client running that
agent.
"""

import json
from pathlib import Path

import pytest

from resource_group_resolver import (  # on sys.path via tests/unit/conftest.py
    RULE_SETTINGS,
    expand_resource_group_refs,
    group_tokens,
    is_rule_key,
    kind_for_key,
    validate_resource_group_refs,
)

GROUPS = {
    "office": {"ip": ["10.0.0.0/8", "192.168.1.0/24"], "rdns": [".office.example"]},
    "badbots": {"user_agent": ["^curl", "^wget"]},
    "eu": {"country": ["FR", "DE"]},
    "empty": {"ip": []},
}


@pytest.mark.parametrize(
    "key, expected",
    [
        ("GREYLIST_RULE", True),
        ("GREYLIST_RULE_1", True),
        ("WHITELIST_RULE_12", True),
        ("BLACKLIST_RULE", True),
        ("app.example.com_GREYLIST_RULE_2", True),
        ("GREYLIST_IP", False),
        ("GREYLIST_RULES", False),
        ("GREYLIST_RULE_X", False),
        ("MY_GREYLIST_RULE_OTHER", False),
    ],
)
def test_is_rule_key(key, expected):
    assert is_rule_key(key) is expected


def test_kind_for_key_still_says_nothing_about_a_rule():
    """A rule has no single kind -- that is the whole reason the term branch exists.

    The UI renders a group picker off kind_for_key, and config_save gates its @group check on
    it; a rule answering "ip" here would put an IP picker on a setting whose first term may be
    a uri.
    """
    for base in RULE_SETTINGS:
        assert kind_for_key(base) is None
        assert kind_for_key(f"{base}_1") is None
    assert kind_for_key("GREYLIST_IP") == "ip"


@pytest.mark.parametrize(
    "value, error_fragment",
    [
        ("ip:@office AND ua:@badbots", None),
        ("country:@eu", None),
        ("NOT rdns:@office AND ip:1.2.3.4", None),
        ("ip:@nope", "Unknown resource group @nope"),
        # @badbots only holds user_agent entries, so it cannot satisfy an ip: term.
        ("ip:@badbots", "has no ip entries"),
        ("ip:@empty", "has no ip entries"),
        # A malformed rule is the setting regex's business, not this check's.
        ("garbage @office", None),
    ],
)
def test_validate_per_term_kind(value, error_fragment):
    error = validate_resource_group_refs({"GREYLIST_RULE_1": value}, GROUPS)
    if error_fragment is None:
        assert error is None
    else:
        assert error is not None and error_fragment in error


def test_expand_joins_by_kind():
    out = expand_resource_group_refs(
        {
            "GREYLIST_RULE_1": "ip:@office AND NOT ua:@badbots",
            "GREYLIST_RULE_2": "country:@eu",
            "GREYLIST_RULE_3": "ip:10.0.0.1 AND ua:^Bot",
        },
        GROUPS,
    )
    # Non-regex kinds become a comma list; the regex kinds become an alternation, because a
    # comma is legal inside a PCRE quantifier and splitting on it would corrupt the pattern.
    assert out["GREYLIST_RULE_1"] == "ip:10.0.0.0/8,192.168.1.0/24 AND NOT ua:(?:^curl|^wget)"
    assert out["GREYLIST_RULE_2"] == "country:FR,DE"
    # No token, no rewrite.
    assert out["GREYLIST_RULE_3"] == "ip:10.0.0.1 AND ua:^Bot"


def test_expand_kills_the_whole_rule_on_an_unresolvable_reference():
    out = expand_resource_group_refs(
        {
            "WHITELIST_RULE_1": "ip:@nope AND ua:^Bot",
            "WHITELIST_RULE_2": "ip:@empty AND ua:^Bot",
            "WHITELIST_RULE_3": "ip:@office AND ua:^Bot",
        },
        GROUPS,
    )
    assert out["WHITELIST_RULE_1"] == ""
    assert out["WHITELIST_RULE_2"] == ""
    assert out["WHITELIST_RULE_3"] != ""


def test_expand_keeps_a_builtin_country_alias():
    """A built-in country alias with no seeded group is preserved verbatim, not dropped.

    It is preserved rather than resolved: nothing downstream expands ``@EU`` any more.
    ``country.lua``'s ``string_to_set`` **skips** an ``@`` token and logs a WARN
    (``unexpanded group token @EU in country setting``), and ``rules.warnings`` flags the same
    shape for a rule term, so such a term can never match. Preserving it keeps the operator's
    text intact for the UI and puts the failure in the log; rewriting or silently deleting it
    would either widen the rule or hide the misconfiguration.
    """
    out = expand_resource_group_refs({"BLACKLIST_RULE_1": "country:@EU AND ip:1.2.3.4"}, {})
    assert out["BLACKLIST_RULE_1"] == "country:@EU AND ip:1.2.3.4"


@pytest.mark.parametrize(
    "entries, kind, expanded",
    [
        # A group entry holding the separator in any casing would make the stored rule
        # unparseable -- rules.parse refuses " and " inside a term value, and expansion is a
        # third transform neither the setting regex nor the entry's own kind regex validates.
        (["^curl and friends"], "ua", False),
        (["^curl AND wget"], "ua", False),
        (["^curl And wget"], "ua", False),
        # Only the separator spelling is refused: a value merely starting or ending with the
        # word is fine, exactly where rules.parse draws the line.
        (["^and-then"], "ua", True),
        (["^android"], "ua", True),
        # A regex entry ENDING in " and" survives, because the alternation wrap puts a ")"
        # behind it -- `(?:^curl and)` is a value rules.parse accepts. The two gates agree
        # because this check is the parser's, character for character.
        (["^curl and"], "ua", True),
        # The comma-joined kinds have no such wrapper, so a trailing " and" is fatal there.
        (["1.2.3.4 and"], "ip", False),
        # The comma-joined kinds go through the same check.
        (["1.2.3.4 and 5.6.7.8"], "ip", False),
        (["1.2.3.4"], "ip", True),
    ],
)
def test_expand_kills_a_rule_whose_group_entry_holds_the_separator(entries, kind, expanded):
    groups = {"grp": {"user_agent" if kind == "ua" else kind: entries}}
    out = expand_resource_group_refs({"GREYLIST_RULE_1": f"{kind}:@grp AND country:FR"}, groups)
    assert (out["GREYLIST_RULE_1"] != "") is expanded


def test_the_dropped_rule_is_logged():
    """A rule that disappears at generation time must say so; the request path cannot."""
    messages = []
    logger = type("L", (), {"warning": lambda _self, msg: messages.append(msg)})()
    expand_resource_group_refs({"GREYLIST_RULE_1": "ua:@grp"}, {"grp": {"user_agent": ["^a and b"]}}, logger)
    assert len(messages) == 1 and "GREYLIST_RULE_1" in messages[0] and "rule dropped" in messages[0]


def test_expand_leaves_a_malformed_rule_alone():
    out = expand_resource_group_refs({"GREYLIST_RULE_1": "not a rule @office"}, GROUPS)
    assert out["GREYLIST_RULE_1"] == "not a rule @office"


def test_group_tokens_finds_a_token_buried_in_a_term():
    """The reference scanner used to split on whitespace, which finds nothing in ``ip:@office``
    -- so a group referenced only by a rule looked unreferenced and was deletable."""
    assert group_tokens("GREYLIST_RULE", "ip:@office AND ua:@badbots") == {"@office", "@badbots"}
    assert group_tokens("GREYLIST_IP", "@office 1.2.3.4") == {"@office"}
    assert group_tokens("GREYLIST_RULE", "ip:1.2.3.4") == set()
    assert group_tokens("GREYLIST_IP", "1.2.3.4") == set()
    assert group_tokens("GREYLIST_RULE", None) == set()


@pytest.mark.parametrize("plugin, setting", [("greylist", "GREYLIST_RULE"), ("whitelist", "WHITELIST_RULE"), ("blacklist", "BLACKLIST_RULE")])
def test_each_rule_setting_is_declared_multiple(plugin, setting):
    """Without ``multiple``, ``Configurator.__find_var`` does not recognise ``<LIST>_RULE_1``.

    The failure is silent in the worst way: the numeric-suffix variable is treated as an
    unknown name and dropped from the generated config, so every rule past the bare base
    disappears with nothing in the request path to notice. The declaration is one JSON key,
    and this is the assertion that keeps it there.
    """
    root = Path(__file__).resolve().parents[3]
    schema = json.loads((root / "src" / "common" / "core" / plugin / "plugin.json").read_text())["settings"][setting]
    assert schema["multiple"] == f"{plugin}-rules"
    assert schema["context"] == "multisite"
    assert schema["default"] == ""
    assert schema["type"] == "text"
