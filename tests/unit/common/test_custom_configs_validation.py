"""The one validator every custom-config write source now shares.

Before this module existed, six write sources each carried their own copy of the type
set and the name rule -- env accepted any name at all (`.+`), Docker labels silently
dropped the three fleet-global types with no diagnostic, and the two `NAME_RX`/
`CUSTOM_CONF_RX` pairs (API vs UI) had already drifted once (see their own comments in
`src/api/app/schemas.py` and `src/ui/app/routes/utils.py`). These tests pin the
properties `report-CC-2.md`'s divergence table depends on: one canonical type set, one
name rule, one message per verdict, WARN-only on the four autoconf/env sources and
REFUSE on API/UI (design AC 6), and the Docker fleet-global refusal (report-CC-A.md §4.3).
"""

from pathlib import Path

import pytest

from custom_configs_validation import (  # type: ignore  (src/common/utils on sys.path via root conftest)
    CUSTOM_CONFIG_TYPES,
    DOCKER_LABEL_ALLOWED_TYPES,
    DOCKER_LABEL_GLOBAL_TYPES,
    ENFORCED_SOURCES,
    KNOWN_SOURCES,
    MAX_CONFIG_SIZE,
    NAME_RX,
    TYPE_ERROR_MESSAGE,
    WARN_ONLY_SOURCES,
    build_docker_label_key_rx,
    build_env_style_key_rx,
    normalize_type,
    validate,
    validate_name,
)

MODEL_PY = Path(__file__).resolve().parents[3] / "src" / "common" / "db" / "model.py"


def _model_custom_config_types():
    """Read `CUSTOM_CONFIGS_TYPES_ENUM`'s values straight from model.py's source text.

    Not `from model import CUSTOM_CONFIGS_TYPES_ENUM`: that module is a frozen file this
    lane must never edit, but more importantly `sqlalchemy.Enum` objects don't expose
    their member list in a form worth trusting sight-unseen -- reading the literal
    strings out of the source is what actually pins "the model's enum", not an SQLAlchemy
    implementation detail.
    """
    text = MODEL_PY.read_text(encoding="utf-8")
    start = text.index("CUSTOM_CONFIGS_TYPES_ENUM = Enum(")
    end = text.index(")", start)
    block = text[start:end]
    return tuple(line.strip().strip('",') for line in block.splitlines() if line.strip().startswith('"'))


class TestCanonicalTypes:
    def test_matches_the_frozen_db_enum_exactly(self):
        """The one thing that must never drift: model.py is frozen, this module is not."""
        assert CUSTOM_CONFIG_TYPES == _model_custom_config_types()

    def test_has_nine_types(self):
        assert len(CUSTOM_CONFIG_TYPES) == 9

    def test_docker_label_allowed_is_the_six_non_global_types(self):
        assert set(DOCKER_LABEL_ALLOWED_TYPES) == set(CUSTOM_CONFIG_TYPES) - DOCKER_LABEL_GLOBAL_TYPES
        assert len(DOCKER_LABEL_ALLOWED_TYPES) == 6

    def test_global_types_are_exactly_http_stream_default_server_http(self):
        assert DOCKER_LABEL_GLOBAL_TYPES == {"http", "stream", "default_server_http"}


class TestNormalizeType:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("http", "http"),
            ("HTTP", "http"),
            ("server-http", "server_http"),
            ("Server-HTTP", "server_http"),
            ("  modsec_crs  ", "modsec_crs"),
            ("CRS-PLUGINS-BEFORE", "crs_plugins_before"),
        ],
    )
    def test_accepts_any_case_or_separator(self, raw, expected):
        assert normalize_type(raw) == expected

    @pytest.mark.parametrize("raw", ["bogus", "", "ht tp", None, 123])
    def test_rejects_unknown_or_non_string(self, raw):
        assert normalize_type(raw) is None


class TestValidateName:
    @pytest.mark.parametrize("name", ["a_config-1", "A", "a" * 255, "under_score", "with-hyphen"])
    def test_accepts_legal_names(self, name):
        assert validate_name(name) is None

    @pytest.mark.parametrize("name", ["", "bad name!", "a" * 256, "trailing.dot", "a/b"])
    def test_rejects_illegal_names(self, name):
        assert validate_name(name) is not None

    def test_rejects_trailing_newline(self):
        """`\\Z`, not `$`: `$` also matches immediately before a trailing newline."""
        assert not NAME_RX.match("a_config\n")
        assert validate_name("a_config\n") is not None

    def test_message_quotes_the_pattern_it_enforces(self):
        assert NAME_RX.pattern in validate_name("bad name!")


class TestValidateSourceSplit:
    def test_warn_only_and_enforced_partition_known_sources(self):
        assert WARN_ONLY_SOURCES | ENFORCED_SOURCES == KNOWN_SOURCES
        assert WARN_ONLY_SOURCES.isdisjoint(ENFORCED_SOURCES)
        assert WARN_ONLY_SOURCES == {"env", "docker_label", "swarm_config", "configmap"}
        assert ENFORCED_SOURCES == {"api", "ui"}

    @pytest.mark.parametrize("source", sorted(WARN_ONLY_SOURCES))
    def test_bad_name_is_warned_not_refused_on_warn_only_sources(self, source):
        """AC 6: an env-only or autoconf-only install keeps accepting what it accepted before.

        `server_http`, not `http`: `http` is a fleet-global type Docker labels refuse
        outright (a different, type-level refusal covered by TestDockerLabelGlobalTypeRefusal),
        which would otherwise mask the name-level WARN-only behaviour under test here.
        """
        result = validate("server_http", "bad name!", "x", source=source)
        assert result.ok is True
        assert result.error is None
        assert result.warning is not None
        assert "1.8" in result.warning

    @pytest.mark.parametrize("source", sorted(ENFORCED_SOURCES))
    def test_bad_name_is_refused_on_enforced_sources(self, source):
        """API/UI already refuse an invalid name; unification must not loosen that."""
        result = validate("server_http", "bad name!", "x", source=source)
        assert result.ok is False
        assert result.error is not None
        assert result.warning is None

    def test_unknown_source_raises(self):
        with pytest.raises(ValueError):
            validate("http", "x", "y", source="carrier-pigeon")


class TestValidateTypeAlwaysRefuses:
    """Every source already filters its own type set before reaching `validate()` -- a type
    outside the canonical nine reaching here is a caller bug, and every source must refuse
    it identically (design AC 2)."""

    @pytest.mark.parametrize("source", sorted(KNOWN_SOURCES))
    def test_unknown_type_refused_with_the_same_message_shape(self, source):
        result = validate("not-a-real-type", "ok_name", "x", source=source)
        assert result.ok is False
        assert result.normalized_type is None
        assert "Invalid type" in result.error
        assert all(t in result.error for t in CUSTOM_CONFIG_TYPES)


class TestDockerLabelGlobalTypeRefusal:
    """report-CC-A.md §4.3: keep the restriction, but make it an explicit refusal naming
    the alternative instead of the current silent regex non-match."""

    @pytest.mark.parametrize("global_type", sorted(DOCKER_LABEL_GLOBAL_TYPES))
    def test_global_type_refused_only_for_docker_label(self, global_type):
        docker_verdict = validate(global_type, "ok_name", "x", source="docker_label")
        assert docker_verdict.ok is False
        assert "fleet-global" in docker_verdict.error
        assert "docker config create" in docker_verdict.error
        assert "bunkerweb.CONFIG_TYPE" in docker_verdict.error

    @pytest.mark.parametrize("global_type", sorted(DOCKER_LABEL_GLOBAL_TYPES))
    @pytest.mark.parametrize("other_source", ["swarm_config", "configmap", "api", "ui"])
    def test_global_type_allowed_from_every_other_source(self, global_type, other_source):
        """Swarm config objects and K8s ConfigMaps are cluster-scoped, not a container
        label -- only Docker labels lose the fleet-global types."""
        result = validate(global_type, "ok_name", "x", source=other_source)
        assert result.ok is True

    def test_non_global_type_not_refused_for_docker_label(self):
        result = validate("server_http", "ok_name", "x", source="docker_label")
        assert result.ok is True


class TestMessageParityAcrossSources:
    """The literal reading of AC 2: the SAME bad input produces the SAME verdict text
    everywhere the type check applies, and the SAME name-error text everywhere a source
    surfaces it (as an error on api/ui, as a warning fragment on the rest)."""

    def test_same_bad_type_message_everywhere(self):
        messages = {source: validate("nope", "ok_name", "x", source=source).error for source in KNOWN_SOURCES}
        # Anti-vacuity (Criticos round 1): a mutant that always returns `ok=True, error=None`
        # makes every value `None`, `len(set(...)) == 1` still holds, and this test would pass
        # for the wrong reason. Pin the real content, not just its uniformity.
        assert all(message == TYPE_ERROR_MESSAGE for message in messages.values()), messages
        assert len(set(messages.values())) == 1, messages

    def test_same_bad_name_text_embedded_everywhere(self):
        for source in ENFORCED_SOURCES:
            assert NAME_RX.pattern in validate("http", "bad name!", "x", source=source).error
        for source in WARN_ONLY_SOURCES:
            assert NAME_RX.pattern in validate("server_http", "bad name!", "x", source=source).warning


class TestSizeCapIsInformationalOnly:
    """No source enforces a per-config size cap today (report-CC-A.md: 'No size cap exists
    anywhere except the UI's 50 MB request cap'). `validate()` must never refuse on size for
    ANY source -- that would be new behaviour beyond this lane's hygiene-cut scope."""

    @pytest.mark.parametrize("source", sorted(KNOWN_SOURCES))
    def test_oversized_config_still_ok_everywhere(self, source):
        oversized = "x" * (MAX_CONFIG_SIZE + 1)
        # `server_http`, not `http`: `http` is a fleet-global type Docker labels refuse
        # outright, independent of size.
        result = validate("server_http", "ok_name", oversized, source=source)
        assert result.ok is True
        assert result.warning is not None
        assert "byte" in result.warning

    def test_undersized_config_carries_no_size_warning(self):
        assert validate("http", "ok_name", "small", source="api").warning is None


class TestEnvStyleKeyRxBuilder:
    """Shared by the three parsers that hand-rolled this exact pattern: `save_config.py`
    (env), `DockerController.py` (labels) and `ui/app/routes/utils.py` -- the env and UI
    copies "have already drifted once" per their own comments."""

    def test_with_service_prefix_captures_service_type_and_name(self):
        rx = build_env_style_key_rx(with_service_prefix=True)
        m = rx.match("app1.example.com_CUSTOM_CONF_SERVER_HTTP_mysnippet")
        assert m is not None
        assert m.group("service") == "app1.example.com"
        assert m.group("type") == "SERVER_HTTP"
        assert m.group("name") == "mysnippet"

    def test_with_service_prefix_allows_no_service(self):
        rx = build_env_style_key_rx(with_service_prefix=True)
        m = rx.match("CUSTOM_CONF_HTTP_x")
        assert m is not None
        assert m.group("service") == ""
        assert m.group("type") == "HTTP"

    def test_without_service_prefix_has_no_service_group(self):
        rx = build_env_style_key_rx(with_service_prefix=False)
        assert "service" not in rx.groupindex
        m = rx.match("CUSTOM_CONF_MODSEC_foo")
        assert m is not None
        assert m.group("type") == "MODSEC"
        assert m.group("name") == "foo"

    def test_rejects_trailing_newline(self):
        """The exact aliasing bug both twins' comments warn about."""
        rx = build_env_style_key_rx(with_service_prefix=False)
        assert rx.match("CUSTOM_CONF_HTTP_x\n") is None

    def test_modsec_crs_not_misparsed_as_modsec(self):
        """MODSEC is a literal prefix of MODSEC_CRS. If the alternation ever tried the
        shorter alternative first, `CUSTOM_CONF_MODSEC_CRS_foo` would wrongly split into
        type=MODSEC, name=CRS_foo instead of type=MODSEC_CRS, name=foo."""
        rx = build_env_style_key_rx(with_service_prefix=False)
        m = rx.match("CUSTOM_CONF_MODSEC_CRS_foo")
        assert m.group("type") == "MODSEC_CRS"
        assert m.group("name") == "foo"

    def test_crs_plugins_before_not_truncated(self):
        rx = build_env_style_key_rx(with_service_prefix=False)
        m = rx.match("CUSTOM_CONF_CRS_PLUGINS_BEFORE_foo")
        assert m.group("type") == "CRS_PLUGINS_BEFORE"
        assert m.group("name") == "foo"


class TestDockerLabelKeyRxBuilder:
    def test_default_excludes_global_types(self):
        rx = build_docker_label_key_rx()
        assert rx.match("bunkerweb.CUSTOM_CONF_HTTP_x") is None
        assert rx.match("bunkerweb.CUSTOM_CONF_STREAM_x") is None
        assert rx.match("bunkerweb.CUSTOM_CONF_DEFAULT_SERVER_HTTP_x") is None
        m = rx.match("bunkerweb.CUSTOM_CONF_SERVER_HTTP_mysnippet")
        assert m.group("type") == "SERVER_HTTP"
        assert m.group("name") == "mysnippet"

    def test_all_types_variant_matches_global_types(self):
        rx = build_docker_label_key_rx(CUSTOM_CONFIG_TYPES)
        m = rx.match("bunkerweb.CUSTOM_CONF_HTTP_x")
        assert m.group("type") == "HTTP"

    def test_modsec_crs_not_misparsed_as_modsec(self):
        rx = build_docker_label_key_rx()
        m = rx.match("bunkerweb.CUSTOM_CONF_MODSEC_CRS_foo")
        assert m.group("type") == "MODSEC_CRS"
        assert m.group("name") == "foo"
