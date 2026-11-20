"""Service mutation regressions shared with dev."""

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


def test_rename_only_removes_keys_at_underscore_boundary():
    cfg = model([{"SERVER_NAME": "a.example"}])
    cfg.get_config = Mock(return_value={"SERVER_NAME": "a.example", "a.example_VALUE": "old", "a.example.org_VALUE": "sibling"})
    cfg.gen_conf = Mock(return_value=set())
    assert cfg.edit_service("a.example", {"SERVER_NAME": "renamed.example"})[1] == 0
    seed = cfg.gen_conf.call_args.args[0]
    assert "a.example_VALUE" not in seed
    assert seed["a.example.org_VALUE"] == "sibling"
