"""`DELETE /users/{username}/sessions/{session_id}`: close one session row (N-M2).

The UI calls it at logout; before, only "wipe other sessions" and a password change deleted rows,
so every logged-out session stayed in `GET /users/{username}/sessions`. Same loader as
`test_users_totp_endpoint.py`: the router's handlers called directly against a Mock db.
"""

import pytest

from test_users_totp_endpoint import _DB, ROUTER


@pytest.fixture(autouse=True)
def db():
    _DB.reset_mock(return_value=True, side_effect=True)
    return _DB


def test_one_row_is_deleted(db):
    db.delete_ui_user_session.return_value = ""

    response = ROUTER.delete_user_session("alice", 7)

    assert response.status_code == 200
    db.delete_ui_user_session.assert_called_once_with("alice", 7)


def test_a_read_only_database_is_a_client_error(db):
    db.delete_ui_user_session.return_value = "The database is read-only, the changes will not be saved"

    assert ROUTER.delete_user_session("alice", 7).status_code == 400


def test_a_database_failure_is_a_server_error(db):
    db.delete_ui_user_session.return_value = "connection lost"

    assert ROUTER.delete_user_session("alice", 7).status_code == 500
