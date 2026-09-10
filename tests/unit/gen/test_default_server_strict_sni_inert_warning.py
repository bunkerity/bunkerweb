"""``DISABLE_DEFAULT_SERVER_STRICT_SNI`` only has a default server to enforce it on -- SNI is
negotiated before NGINX picks a ``server{}`` block, so the setting only acts when one exists
(``MULTISITE=yes``, or ``DISABLE_DEFAULT_SERVER=yes`` in single-site). In plain single-site it is
silently inert: ``core/misc/README.md`` documents exactly this condition, but nothing told the
operator at generation time that their `yes` does nothing (wave 19, lane N18, note #12).

``Templator.__init__`` now warns once, unconditionally of which branch the render takes, in the
inert case only.
"""

SETTING = "DISABLE_DEFAULT_SERVER_STRICT_SNI"


def warned(render_tree, monkeypatch, **variables):
    """``render_tree(**variables)`` with the Templator logger captured; returns every message said."""
    import Templator as T  # type: ignore
    from types import SimpleNamespace

    said = []
    monkeypatch.setattr(T, "logger", SimpleNamespace(warning=said.append, error=said.append, info=lambda *a: None, debug=lambda *a: None))
    render_tree(**variables)
    return said


class TestTheInertCaseWarns:
    def test_plain_single_site_warns(self, render_tree, monkeypatch):
        said = warned(render_tree, monkeypatch, **{SETTING: "yes", "MULTISITE": "no", "SERVER_NAME": "app.example.com"})
        assert [message for message in said if SETTING in message and "no effect" in message], said

    def test_off_never_warns(self, render_tree, monkeypatch):
        said = warned(render_tree, monkeypatch, **{SETTING: "no", "MULTISITE": "no", "SERVER_NAME": "app.example.com"})
        assert not [message for message in said if SETTING in message], said


class TestTheActiveCasesDoNotWarn:
    def test_multisite_does_not_warn(self, render_tree, monkeypatch):
        said = warned(render_tree, monkeypatch, **{SETTING: "yes", "MULTISITE": "yes"})
        assert not [message for message in said if SETTING in message], said

    def test_single_site_with_disable_default_server_does_not_warn(self, render_tree, monkeypatch):
        said = warned(
            render_tree,
            monkeypatch,
            **{SETTING: "yes", "MULTISITE": "no", "DISABLE_DEFAULT_SERVER": "yes", "SERVER_NAME": "app.example.com"},
        )
        assert not [message for message in said if SETTING in message], said
