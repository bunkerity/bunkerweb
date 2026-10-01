"""`POST /users` without a role creates a `reader`, never an `admin` (PO 2026-09-30).

Same loader and Mock db as `test_api_users_password.py`.
"""

import pytest
from test_api_users_password import PLAIN, ROUTER, _DB


@pytest.fixture(autouse=True)
def db():
    _DB.reset_mock(return_value=True, side_effect=True)
    _DB.create_ui_user.return_value = ""
    return _DB


def _roles(db):
    return db.create_ui_user.call_args.kwargs["roles"]


def test_omitted_role_is_reader(db):
    response = ROUTER.create_user(ROUTER.CreateUserRequest.model_validate({"username": "bob", "password": PLAIN}))

    assert response.status_code == 201
    assert _roles(db) == ["reader"]


def test_explicit_admin_role_is_kept(db):
    ROUTER.create_user(ROUTER.CreateUserRequest.model_validate({"username": "bob", "password": PLAIN, "roles": ["admin"]}))

    assert _roles(db) == ["admin"]
