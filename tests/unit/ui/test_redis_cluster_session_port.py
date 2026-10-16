"""Exercise the actual UI session initialization statements."""

import ast
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]


def test_ui_keeps_selected_cluster_client_after_session_initialization(monkeypatch):
    source = (ROOT / "src/ui/main.py").read_text()
    tree = ast.parse(source)
    nodes = next(
        n.body
        for n in ast.walk(tree)
        if hasattr(n, "body") and any(isinstance(x, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "sess" for t in x.targets) for x in n.body)
    )
    start = next(i for i, n in enumerate(nodes) if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "sess" for t in n.targets))
    end = next(
        i
        for i in range(start, len(nodes))
        if isinstance(nodes[i], ast.Expr)
        and isinstance(nodes[i].value, ast.Call)
        and isinstance(nodes[i].value.func, ast.Name)
        and nodes[i].value.func.id == "bind_session_cookie_per_request"
    )
    cluster = object()
    app = SimpleNamespace(config={"SESSION_CACHELIB": object(), "SESSION_KEY_PREFIX": "p:", "SESSION_ID_LENGTH": 64})

    class Resilient:
        """Stands in for the real interface, which needs flask-session and cachelib."""

        def __init__(self, app, *, client, **kwargs):
            # flask-session's Redis type check substitutes localhost for RedisCluster.
            self.client = object()

    monkeypatch.setitem(sys.modules, "app.models.resilient_session", SimpleNamespace(ResilientRedisSessionInterface=Resilient))

    class Session:
        def init_app(self, app):
            # flask-session replaces RedisCluster because it is not redis.Redis.
            app.session_interface = SimpleNamespace(client=object())

    ns = dict(
        app=app,
        redis_client=cluster,
        Session=Session,
        is_cluster=lambda c: c is cluster,
        LOGGER=object(),
        CacheLibSessionInterface=lambda **kw: object(),
        chain_session_fallback=lambda *a: None,
    )
    exec(compile(ast.Module(body=nodes[start:end], type_ignores=[]), str(ROOT / "src/ui/main.py"), "exec"), ns)
    assert app.session_interface.client is cluster
