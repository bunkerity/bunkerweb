"""Pure-logic helpers on the ``Database`` class — no DB connection required.

These exercise the small, high-traffic helpers that decide setting-key suffixes,
template-config normalization, method compatibility and None-emptying. We build a bare
instance with ``Database.__new__`` (bypassing ``__init__``/engine/connection) since the
helpers only read class attributes and recurse on ``self``.
"""

import pytest

from Database import Database
from model import Resources


@pytest.fixture(scope="module")
def helpers():
    # No __init__: no engine, no env, no connection. Helpers use class attrs only.
    return Database.__new__(Database)


class TestMethodsAreCompatible:
    @pytest.mark.parametrize(
        "new,current,expected",
        [
            (None, "ui", True),  # new None -> always allowed
            ("ui", None, True),  # current None -> always allowed
            ("autoconf", "ui", True),  # autoconf wins over everything
            ("autoconf", "autoconf", True),
            ("ui", "autoconf", False),  # only autoconf overwrites autoconf
            ("api", "autoconf", False),
            ("ui", "api", True),  # ui/api interchangeable
            ("api", "ui", True),
            # `wizard` joined them in dev 33f42592d (#3751). The setup wizard creates its service
            # with method "wizard" and then writes that service's settings as "ui"; while the two
            # were incompatible, every later edit of a wizard-created service was DISCARDED --
            # no error, and the old value redrawn, which reads as the save not having been clicked.
            ("ui", "wizard", True),
            ("wizard", "ui", True),
            ("api", "wizard", True),
            ("wizard", "api", True),
            ("wizard", "wizard", True),
            # ...and the widening stops there. `wizard` is editable, not privileged.
            ("wizard", "autoconf", False),
            ("wizard", "scheduler", False),
            ("manual", "wizard", False),
            # scheduler (env-var origin) no longer unconditionally overwrites ui/api: a
            # default-filled scheduler pass must NOT clobber in-session UI/API edits. The
            # override is gated behind allow_scheduler_override (see test_scheduler_override).
            ("scheduler", "ui", False),
            ("scheduler", "api", False),
            ("ui", "scheduler", False),  # ...and the reverse stays blocked
            ("api", "scheduler", False),
            ("scheduler", "scheduler", True),  # equality fallback
            ("manual", "ui", False),
            ("api", "api", True),
        ],
    )
    def test_matrix(self, new, current, expected):
        assert Database._methods_are_compatible(new, current) is expected

    @pytest.mark.parametrize(
        "new,current,allow,expected",
        [
            # allow_scheduler_override only unlocks the scheduler->ui/api transition; it is
            # consulted exclusively for that case (config-as-code reasserting an explicitly
            # declared env key over an in-session UI/API edit).
            ("scheduler", "ui", True, True),
            ("scheduler", "api", True, True),
            ("scheduler", "wizard", True, True),
            ("scheduler", "ui", False, False),
            ("scheduler", "api", False, False),
            # The gate covers the wizard too: an env-var pass must not clobber a wizard-created
            # service's settings any more than it may clobber a UI edit.
            ("scheduler", "wizard", False, False),
            # It must not loosen any other rule.
            ("ui", "scheduler", True, False),
            ("ui", "api", True, True),
            ("scheduler", "scheduler", False, True),
        ],
    )
    def test_scheduler_override(self, new, current, allow, expected):
        assert Database._methods_are_compatible(new, current, allow_scheduler_override=allow) is expected


def test_resource_type_is_validated_on_orm_write():
    with pytest.raises(ValueError, match="Unsupported resource type"):
        Resources(type="plugin-defined")


class TestSplitSettingKey:
    @pytest.mark.parametrize(
        "key,expected",
        [
            ("USE_ANTIBOT", ("USE_ANTIBOT", None)),
            ("REVERSE_PROXY_URL_1", ("REVERSE_PROXY_URL", 1)),
            ("REVERSE_PROXY_URL_42", ("REVERSE_PROXY_URL", 42)),
            ("X_0", ("X", 0)),
            ("NO_SUFFIX_HERE", ("NO_SUFFIX_HERE", None)),
        ],
    )
    def test_split(self, helpers, key, expected):
        assert helpers._split_setting_key(key) == expected


class TestNormalizeTemplateConfigReference:
    @pytest.mark.parametrize(
        "ref,expected",
        [
            ("server-http/foo", "server_http/foo.conf"),  # hyphen->underscore, .conf added
            ("server_http/foo.conf", "server_http/foo.conf"),  # idempotent
            ("modsec-crs/bar.conf", "modsec_crs/bar.conf"),
            ("server-http/My-File", "server_http/My-File.conf"),  # name keeps case/hyphens
        ],
    )
    def test_valid(self, helpers, ref, expected):
        assert helpers._normalize_template_config_reference(ref) == expected

    @pytest.mark.parametrize(
        "ref",
        [
            "",
            "   ",
            "noslash",
            "http/foo",  # 'http' not in the server-scoped multisite types
            "unknown/foo",
            "server-http/",  # empty name
            "/onlyslash",  # empty type
        ],
    )
    def test_invalid_returns_none(self, helpers, ref):
        assert helpers._normalize_template_config_reference(ref) is None


class TestEmptyIfNone:
    def test_none_becomes_empty_string(self, helpers):
        assert helpers._empty_if_none(None) == ""

    def test_passthrough(self, helpers):
        assert helpers._empty_if_none("x") == "x"
        assert helpers._empty_if_none(5) == 5
        assert helpers._empty_if_none(False) is False

    def test_nested_collections(self, helpers):
        assert helpers._empty_if_none({"a": None, "b": 1}) == {"a": "", "b": 1}
        assert helpers._empty_if_none([None, "y"]) == ["", "y"]
        assert helpers._empty_if_none((None, 2)) == ("", 2)
