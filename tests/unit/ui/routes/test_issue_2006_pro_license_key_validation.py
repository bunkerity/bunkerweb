"""Setting the PRO licence key from the UI failed because ``check_variables`` was called without its ``to_check`` argument.

Pins that the route calls the validator with the real signature (variables, config, the key to check) and that the
validated key is then persisted. Ref: #2006.
"""

import pytest


@pytest.fixture
def pro(h):
    h.db.readonly = False
    h.db.get_config.return_value = {"PRO_LICENSE_KEY": "old"}
    h.config.edit_global_conf.return_value = ("", "")
    return h.routes.pro


def test_the_validator_gets_all_its_arguments_and_the_new_key_is_saved(h, pro):
    calls = []

    def check_variables(variables, config, to_check, *, global_config=False, new=False, threaded=False):
        # same positional parameters as app.models.config.Config.check_variables: a missing to_check is a TypeError
        calls.append((variables, config, to_check, global_config))
        return {"PRO_LICENSE_KEY": to_check["PRO_LICENSE_KEY"]}

    h.config.check_variables.side_effect = check_variables

    response = h.client().post("/pro/key", data={"PRO_LICENSE_KEY": "new"})

    assert response.status_code == 302
    variables, _config, to_check, global_config = calls[0]
    assert to_check == {"PRO_LICENSE_KEY": "new"} and variables["PRO_LICENSE_KEY"] == "new" and global_config is True
    h.config.edit_global_conf.assert_called_once_with({"PRO_LICENSE_KEY": "new"}, check_changes=True)
