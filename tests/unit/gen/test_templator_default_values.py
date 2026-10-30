"""Jinja templates can read default settings omitted from the non-default config."""

from types import SimpleNamespace

from jinja2 import Environment, UndefinedError
import pytest

import Templator


@pytest.fixture
def environment(monkeypatch):
    monkeypatch.setattr(Templator.ConfigurableCustomUndefined, "_config_dict", {})

    def build(defaults):
        return Environment(undefined=Templator.create_custom_undefined_class(defaults))

    return build


def test_defaults_render_nested_attributes_and_mapping_items(environment):
    env = environment({"ORIGIN": SimpleNamespace(host="backend", ports=[8080]), "HEADERS": {"name": "X-Safe"}})
    assert env.from_string("proxy_pass http://{{ ORIGIN.host }}:{{ ORIGIN.ports[0] }};\nadd_header {{ HEADERS['name'] }} yes;").render() == (
        "proxy_pass http://backend:8080;\nadd_header X-Safe yes;"
    )


def test_flattened_defaults_resolve_missing_attribute_and_item_paths(environment):
    env = environment({"ORIGIN.host": "flat-backend", "PORTS[0]": "8080", "[name]": "root-item", "host": "root-attribute"})
    assert env.from_string("{{ ORIGIN.host }}:{{ PORTS[0] }}").render() == "flat-backend:8080"
    undefined = env.undefined()
    assert undefined["name"] == "root-item"
    assert undefined.host == "root-attribute"


def test_out_of_range_or_missing_item_remains_empty(environment):
    env = environment({"PORTS": [8080], "HEADERS": {"name": "X-Safe"}, "NUMBER": 3})
    assert env.from_string("{{ PORTS[5] }}|{{ HEADERS['missing'] }}|{{ NUMBER['missing'] }}|{{ MISSING.child['key'] }}").render() == "|||"


@pytest.mark.parametrize(
    "value,expected", [("yes", "enabled"), ("   ", "disabled"), ("", "disabled"), (0, "disabled"), (False, "disabled"), (None, "disabled")]
)
def test_default_truthiness_controls_directive_emission(environment, value, expected):
    env = environment({"FLAG": value})
    assert env.from_string("{% if FLAG %}enabled{% else %}disabled{% endif %}").render() == expected


def test_numeric_defaults_support_all_ordered_comparisons(environment):
    env = environment({"TIMEOUT": 6})
    assert (
        env.from_string("{% if TIMEOUT > 5 and TIMEOUT >= 6 and TIMEOUT < 7 and TIMEOUT <= 6 %}proxy_read_timeout {{ TIMEOUT }};{% endif %}").render()
        == "proxy_read_timeout 6;"
    )


@pytest.mark.parametrize("operator", ["<", "<=", ">", ">="])
@pytest.mark.parametrize("defaults", [{}, {"TIMEOUT": "six"}])
def test_missing_or_incompatible_ordering_fails_instead_of_emitting_directive(environment, operator, defaults):
    env = environment(defaults)
    with pytest.raises(UndefinedError):
        env.from_string("{% if TIMEOUT " + operator + " 5 %}proxy_read_timeout 5;{% endif %}").render()


def test_blank_default_compares_as_empty_and_missing_values_keep_jinja_semantics(environment):
    env = environment({"BLANK": "  ", "VALUE": "ready"})
    assert env.from_string("{% if BLANK == '' and not BLANK != '' and VALUE != '' and VALUE == 'ready' %}ok{% endif %}").render() == "ok"
    assert env.from_string("{{ MISSING }}|{{ MISSING|length }}|{% for item in MISSING %}bad{% endfor %}").render() == "|0|"
    undefined = env.undefined(name="MISSING")
    assert undefined == env.undefined(name="OTHER")
    assert (undefined != env.undefined(name="OTHER")) is False
    assert repr(undefined) == "Undefined"


def test_default_sequence_iteration_length_membership_and_repr(environment):
    env = environment({"PORTS": [80, 443], "NO_LENGTH": 2})
    assert (
        env.from_string("{% for port in PORTS %}listen {{ port }};{% endfor %}count={{ PORTS|length }};{% if 443 in PORTS %}tls{% endif %}").render()
        == "listen 80;listen 443;count=2;tls"
    )
    assert repr(env.undefined(name="PORTS")) == "[80, 443]"
    assert len(env.undefined(name="NO_LENGTH")) == 0
    assert ("item" in env.undefined(name="NO_LENGTH")) is False
    assert list(env.undefined(name="NO_LENGTH")) == []


@pytest.mark.parametrize("argument", ["templates", "core", "plugins", "pro_plugins", "output", "target", "config"])
def test_invalid_constructor_arguments_are_rejected_before_filesystem_access(argument):
    args = dict(
        templates="unused",
        core="unused",
        plugins="unused",
        pro_plugins="unused",
        output="unused",
        target="unused",
        config={},
        default_config={},
        full_config={},
    )
    args[argument] = None
    with pytest.raises(TypeError, match=argument):
        Templator.Templator(**args)
