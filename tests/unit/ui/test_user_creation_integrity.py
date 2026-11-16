"""Role validation must finish before pending FK children can autoflush."""

import pytest
from sqlalchemy import select

from fixtures.seed import FIXED_DT, session
from app.models.models import UiUsers
from model import Roles, RolesUsers, UserPreferences, UserRecoveryCodes


@pytest.fixture
def roles(ui_db):
    with session(ui_db) as s:
        s.add_all([Roles(name="one", description="First", update_datetime=FIXED_DT), Roles(name="two", description="Second", update_datetime=FIXED_DT)])
    return ui_db


def test_two_roles_are_created_after_user(roles):
    assert roles.create_ui_user("bob", b"opaque-hash", ["one", "two"], totp_recovery_codes=["recover"]) == ""
    user = roles.get_ui_user(username="bob", as_dict=True)
    assert set(user["roles"]) == {"one", "two"}
    assert len(user["recovery_codes"]) == 1


def test_unknown_second_role_leaves_no_partial_user(roles):
    assert roles.create_ui_user("bob", b"opaque-hash", ["one", "missing"]) == "Role missing doesn't exist"
    with session(roles) as s:
        assert s.get(UiUsers, "bob") is None
        for model in (RolesUsers, UserPreferences, UserRecoveryCodes):
            assert s.scalars(select(model).filter_by(user_name="bob")).first() is None
    assert roles.create_ui_user("bob", b"opaque-hash", ["one", "two"]) == ""
