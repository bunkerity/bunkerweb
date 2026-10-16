"""The Web UI's global-CRS exclusions must cover every host name of every UI service.

``ui.modsec-crs`` renders in the ``http`` context and scopes each exclusion to the UI's own
``Host`` header. It used to loop over ``SERVER_NAME`` -- the list of service *ids* -- so a UI
service with ``<id>_SERVER_NAME=ui.example.com ui2.example.com`` was matched on its id alone and
the exclusions never applied to the names a browser actually sends. The reserved default-server id
is not a host name and must stay out.
"""

from importlib import import_module
from pathlib import Path

import pytest

jinja2 = pytest.importorskip("jinja2")

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = ROOT / "src" / "common" / "core" / "ui" / "confs" / "http" / "ui.modsec-crs"
HOST_RULE = "SecRule REQUEST_HEADERS:Host"


def render(**variables) -> str:
    """Render with the Templator's whitespace flags and its real ``has_variable`` / ``import`` globals."""
    from Templator import Templator

    environment = jinja2.Environment(undefined=jinja2.ChainableUndefined, lstrip_blocks=True, trim_blocks=True, keep_trailing_newline=True)
    environment.globals["import"] = import_module
    environment.globals["has_variable"] = Templator.has_variable
    return environment.from_string(TEMPLATE.read_text(encoding="utf-8")).render(variables)


def host_patterns(rendered: str) -> set:
    return {line.split('"@rx ^(?:')[1].split(")(?::")[0] for line in rendered.splitlines() if line.startswith(HOST_RULE)}


def ctx(services: dict, **extra) -> dict:
    """``services`` maps a service id to its settings (without the id prefix)."""
    all_vars = {"MULTISITE": "yes", "SERVER_NAME": " ".join(services), **extra}
    for service_id, settings in services.items():
        all_vars.update({f"{service_id}_{key}": value for key, value in settings.items()})
    return {"all": all_vars, **all_vars}


def test_every_server_name_of_a_ui_service_is_covered():
    rendered = render(**ctx({"ui": {"USE_UI": "yes", "SERVER_NAME": "ui.example.com Ui2.example.com"}}))
    assert host_patterns(rendered) == {r"ui\.example\.com|ui2\.example\.com"}


def test_two_ui_services_are_both_covered():
    rendered = render(
        **ctx(
            {
                "ui-a": {"USE_UI": "yes", "SERVER_NAME": "a.example.com a2.example.com"},
                "ui-b": {"USE_UI": "yes", "SERVER_NAME": "b.example.com"},
                "app": {"USE_UI": "no", "SERVER_NAME": "app.example.com"},
            }
        )
    )
    assert host_patterns(rendered) == {r"a\.example\.com|a2\.example\.com|b\.example\.com"}
    assert "app" not in "".join(host_patterns(rendered))


def test_ip_server_names_go_to_the_ip_rule_only():
    rendered = render(**ctx({"ui": {"USE_UI": "yes", "SERVER_NAME": "ui.example.com 10.0.0.5"}}))
    assert host_patterns(rendered) == {r"ui\.example\.com", r"10\.0\.0\.5"}
    assert "id:1007781" in rendered


def test_a_service_without_server_name_falls_back_to_its_id():
    rendered = render(**ctx({"ui.example.com": {"USE_UI": "yes"}}))
    assert host_patterns(rendered) == {r"ui\.example\.com"}


def test_the_default_server_id_stays_excluded():
    from default_server import DEFAULT_SERVER_ID

    rendered = render(
        **ctx({DEFAULT_SERVER_ID: {"USE_UI": "yes", "SERVER_NAME": "ghost.example.com"}, "ui": {"USE_UI": "yes", "SERVER_NAME": "ui.example.com"}})
    )
    assert host_patterns(rendered) == {r"ui\.example\.com"}
    assert "ghost" not in rendered
