"""Login cleared the session and then asked the session store to rotate the id, but the store only rotates a non-empty session.

Pins that the id is rotated after the authenticated state is seeded, and that nothing planted before login survives.
"""

import pytest

from _ui_routes_helpers import FakeUser


@pytest.fixture
def login(h, tmp_path, monkeypatch):
    monkeypatch.setattr(h.routes.login, "BISCUIT_PRIVATE_KEY_FILE", tmp_path / "missing.key")
    user = FakeUser("alice", language="en")
    h.db.get_ui_user.side_effect = lambda username=None: user if username in (None, "alice") else None
    h.db.mark_ui_user_login.return_value = 41
    h.db.update_ui_user.return_value = ""
    h.users["alice"] = user


def test_the_session_id_is_rotated_while_the_session_is_not_empty(h, login, monkeypatch):
    rotated = []

    def regenerate(session):
        # flask-session only rotates a truthy session; an empty one keeps the attacker-known id
        rotated.append(dict(session))

    monkeypatch.setattr(h.app.session_interface, "regenerate", regenerate)
    client = h.client(None)
    with client.session_transaction() as sess:
        sess["planted"] = "attacker-controlled"

    response = client.post("/login", data={"username": "alice", "password": "Correct-Horse1!"})

    assert response.status_code == 302
    assert len(rotated) == 1
    assert rotated[0], "regenerate() ran on an empty session, so the session id is not rotated"
    assert "creation_date" in rotated[0] and "planted" not in rotated[0]
    with client.session_transaction() as sess:
        assert "planted" not in sess and sess["_user_id"] == "alice"
