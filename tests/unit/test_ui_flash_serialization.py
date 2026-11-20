"""Flash messages must survive the Redis session serializer and stay escaped.

The Redis session backend (Flask-Session) encodes the session with msgspec, which only
accepts plain types. `flash()` escapes user data into a Markup object; storing that object
in `_flashes` made every login on a Redis-backed UI answer 500. The escaped text is stored
as str and rendered with |safe, so escaping must still hold end to end.
"""

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
for path in (REPO / "src" / "ui", REPO / "src" / "common" / "utils", REPO / "src" / "common" / "db"):
    sys.path.insert(0, str(path))

from flask import Flask, render_template_string, session  # noqa: E402
from flask_session.base import MsgSpecSerializer  # noqa: E402
from markupsafe import Markup  # noqa: E402

from app.utils import flash  # noqa: E402

TEMPLATE = (REPO / "src" / "ui" / "app" / "templates" / "flash.html").read_text()
HISTORY_TEMPLATE = (REPO / "src" / "ui" / "app" / "templates" / "sidebar-notifications.html").read_text()


def make_app() -> Flask:
    app = Flask("flash-test", template_folder=str(REPO / "src" / "ui" / "app" / "templates"))
    app.secret_key = "test"
    # flash.html links to the profile page; the endpoint only has to resolve.
    app.add_url_rule("/profile", "profile", lambda: "")
    return app


class FlashSerializationTest(unittest.TestCase):
    def test_flashes_encode_with_the_redis_serializer(self):
        app = make_app()
        serializer = MsgSpecSerializer(app, "msgpack")
        with app.test_request_context("/"):
            session["flash_messages"] = []
            flash("Service <b>evil</b> saved")
            flash("Couldn't connect to redis", "error")
            flash("Saved", "success", i18n_key="flash.saved")
            flash(Markup('Enable 2FA <a href="/profile">here</a>'), "warning")
            encoded = serializer.encode(dict(session))
        decoded = serializer.decode(encoded)
        self.assertEqual(len(decoded["_flashes"]), 4)
        self.assertEqual(len(decoded["flash_messages"]), 4)
        for entry in decoded["_flashes"]:
            self.assertIsInstance(entry[1], str)

    def test_user_data_is_escaped_and_markup_is_kept(self):
        app = make_app()
        with app.test_request_context("/"):
            session["flash_messages"] = []
            flash('<script>alert("x")</script> service')
            flash(Markup('Enable 2FA <a href="/profile">here</a>'), "warning")
            flash("Saved", "success", i18n_key="flash.saved")
            rendered = render_template_string(TEMPLATE, theme="light", user_readonly=False, current_endpoint="home", pro_diamond_url="")
            history = render_template_string(HISTORY_TEMPLATE, flash_messages=session["flash_messages"])
        for html in (rendered, history):
            self.assertNotIn("<script>", html)
            self.assertIn("&lt;script&gt;", html)
            self.assertIn('<a href="/profile">here</a>', html)
            self.assertIn('<span data-i18n="flash.saved">Saved</span>', html)
            # The body is escaped exactly once (the data-flash-html attribute is entity-encoded
            # again by autoescape, which is what the toast JS expects).
            self.assertIn(">&lt;script&gt;alert(&#34;x&#34;)&lt;/script&gt; service</div>", html)


if __name__ == "__main__":
    unittest.main()
