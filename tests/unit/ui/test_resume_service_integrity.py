"""Service mutation regressions using the real UI model and captured API payloads."""

from unittest.mock import Mock

import pytest

from app.models.config import Config


def model(services):
    cfg = Config.__new__(Config)
    cfg._Config__api_client = Mock()
    cfg._Config__api_client.save_config.return_value = {}
    cfg.get_services = Mock(side_effect=lambda **kwargs: [dict(service) for service in services])
    cfg.get_plugins_settings = Mock(return_value={key: {"context": "multisite"} for key in ("SERVER_NAME", "IS_DRAFT", "USE_TEMPLATE", "VALUE")})
    global_config = {"SERVER_NAME": " ".join(service["SERVER_NAME"].split()[0] for service in services), "VALUE": "global"}
    full_config = global_config | {f"{service['SERVER_NAME'].split()[0]}_VALUE": "fallback" for service in services}
    cfg.get_config = Mock(side_effect=lambda global_only=False, **kwargs: dict(global_config if global_only else full_config))
    return cfg


@pytest.mark.parametrize("operation", ["new", "edit"])
def test_alias_collision_is_rejected_without_saving(operation):
    cfg = model([{"SERVER_NAME": "a.example shared.example"}, {"SERVER_NAME": "b.example"}])
    variables = {"SERVER_NAME": ("c.example" if operation == "new" else "b.example") + " shared.example"}
    result = cfg.new_service(variables) if operation == "new" else cfg.edit_service("b.example", variables)
    assert result[1] == 1
    cfg._Config__api_client.save_config.assert_not_called()


def test_edit_selects_only_the_primary_service_name():
    cfg = model([{"SERVER_NAME": "a.example b.example"}, {"SERVER_NAME": "b.example"}])
    assert cfg.edit_service("a.example b.example", {"SERVER_NAME": "a.example c.example"})[1] == 0
    payload = cfg._Config__api_client.save_config.call_args.args[0]
    assert payload["SERVER_NAME"] == "b.example a.example"


@pytest.mark.parametrize("operation", ["new", "delete"])
def test_create_delete_seed_global_values_instead_of_stale_service_fallback(operation):
    cfg = model([{"SERVER_NAME": "a.example", "VALUE": "template"}, {"SERVER_NAME": "b.example"}])
    result = cfg.new_service({"SERVER_NAME": "c.example"}) if operation == "new" else cfg.delete_service("b.example")
    assert result[1] == 0
    payload = cfg._Config__api_client.save_config.call_args.args[0]
    assert payload["a.example_VALUE"] == "template"


def test_delete_preserves_prefix_sibling():
    cfg = model([{"SERVER_NAME": "a.example"}, {"SERVER_NAME": "a.example.org", "VALUE": "sibling"}])
    assert cfg.delete_service("a.example")[1] == 0
    payload = cfg._Config__api_client.save_config.call_args.args[0]
    assert payload["a.example.org_VALUE"] == "sibling"


def test_rename_only_removes_keys_at_underscore_boundary():
    cfg = model([{"SERVER_NAME": "a.example"}])
    cfg.get_config = Mock(return_value={"SERVER_NAME": "a.example", "a.example_VALUE": "old", "a.example.org_VALUE": "sibling"})
    cfg.gen_conf = Mock(return_value=set())
    assert cfg.edit_service("a.example", {"SERVER_NAME": "renamed.example"})[1] == 0
    seed = cfg.gen_conf.call_args.args[0]
    assert "a.example_VALUE" not in seed
    assert seed["a.example.org_VALUE"] == "sibling"


def test_service_read_preserves_api_template_values():
    cfg = model([])
    del cfg.get_services
    # /global_settings already reports template values through reportable_config;
    # full=True would additionally materialize inherited port-list copies.
    cfg._Config__api_client.get_global_settings.return_value = {
        "SERVER_NAME": "a.example",
        "VALUE": "global",
        "a.example_SERVER_NAME": "a.example",
        "a.example_USE_TEMPLATE": "tpl",
        "a.example_VALUE": "template",
    }
    assert cfg.get_services(methods=False, with_drafts=True)[0]["VALUE"] == "template"
    assert not cfg._Config__api_client.get_global_settings.call_args.kwargs.get("full", False)
