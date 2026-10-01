"""Base DatabaseUIUsersMixin.delete_ui_user_session: close one session row (N-M2).

Called through the API at UI logout. It deletes exactly the named row, and only when it belongs
to the named user: a session id alone must not let one account close another's session.
"""

from datetime import datetime, timezone

DT = datetime(2024, 1, 1, tzinfo=timezone.utc)


def test_only_the_named_row_is_deleted(db):
    db.create_ui_user("bob", b"h", [])
    mine = db.mark_ui_user_login("bob", DT, "1.1.1.1", "a")
    other = db.mark_ui_user_login("bob", DT, "2.2.2.2", "b")

    assert db.delete_ui_user_session("bob", mine) == ""

    assert [s["id"] for s in db.get_ui_user_sessions("bob")] == [other]


def test_another_users_row_is_left_alone(db):
    db.create_ui_user("bob", b"h", [])
    db.create_ui_user("eve", b"h", [])
    bobs = db.mark_ui_user_login("bob", DT, "1.1.1.1", "a")

    assert db.delete_ui_user_session("eve", bobs) == ""

    assert [s["id"] for s in db.get_ui_user_sessions("bob")] == [bobs]


def test_an_unknown_row_is_not_an_error(db):
    """Logout may race a wipe or the expiry cleanup; the row being gone already is the goal."""
    db.create_ui_user("bob", b"h", [])

    assert db.delete_ui_user_session("bob", 999) == ""
