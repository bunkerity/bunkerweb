"""Real Configurator + Templator render for the lane-T4 regression tests.

A module of its own rather than ``conftest``: ``from conftest import …`` binds to whichever conftest
module pytest loaded last (see ``_listen_helpers.py``). ``tests/unit/gen`` is on ``sys.path`` through
its conftest, so this name is unambiguous.

Unlike the ``render_tree`` fixture, which keeps ``*.conf`` only, every file the Templator writes is
returned: the ModSecurity rule files (``*.modsec``, ``*.modsec-crs``) are not ``.conf``.
"""

import logging
import tempfile
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CONFS = ROOT / "src" / "common" / "confs"
CORE = ROOT / "src" / "common" / "core"
SETTINGS = ROOT / "src" / "common" / "settings.json"


@contextmanager
def full_renderer():
    """Yield ``render(**variables)`` -> ``{relative path: text}`` of every rendered file, memoised.

    The Jinja bytecode cache is redirected by rebinding ``Templator.sep`` (its only use of
    ``os.path.sep``), the way the ``render_tree`` fixture does it: nothing is written to ``/var/cache``.
    """
    import Templator as T  # type: ignore  (src/common/gen is on the path through the gen conftest)
    from Configurator import Configurator  # type: ignore

    with tempfile.TemporaryDirectory() as root:
        sandbox = Path(root)
        original_sep = T.sep
        T.sep = str(sandbox)
        logger = logging.getLogger("t4-render")
        plugins = sandbox / "plugins"
        plugins.mkdir()
        pro_plugins = sandbox / "pro-plugins"
        pro_plugins.mkdir()
        cache = {}

        def render(**variables):
            key = tuple(sorted(variables.items()))
            if key not in cache:
                config = Configurator(str(SETTINGS), str(CORE), str(plugins), str(pro_plugins), dict(variables), logger).get_config(None)
                output = sandbox / f"out{len(cache)}"
                output.mkdir()
                T.Templator(str(CONFS), str(CORE), str(plugins), str(pro_plugins), str(output), "/etc/nginx", config, config.copy(), config.copy()).render()
                cache[key] = {str(path.relative_to(output)): path.read_text() for path in sorted(output.rglob("*")) if path.is_file()}
            return cache[key]

        try:
            yield render
        finally:
            T.sep = original_sep


def modsec_chains(text):
    """Group the ``SecRule`` lines of a rendered ModSecurity file into chains.

    Returns a list of chains, each a list of ``(variable and operator, action string)`` links. A
    backslash continuation is joined first; a rule whose actions carry ``chain`` pulls the next
    ``SecRule`` into the same chain, as ModSecurity does.
    """
    joined = []
    pending = ""
    for line in text.splitlines():
        stripped = line.strip()
        if pending:
            pending += " " + stripped
        else:
            pending = stripped
        if pending.endswith("\\"):
            pending = pending[:-1].rstrip()
            continue
        if pending:
            joined.append(pending)
        pending = ""

    chains = []
    current = None
    for line in joined:
        if not line.startswith("SecRule "):
            continue
        body = line[len("SecRule ") :].strip()  # noqa: E203
        quoted = []
        index = 0
        while index < len(body):
            if body[index] == '"':
                end = index + 1
                while end < len(body) and body[end] != '"':
                    end += 2 if body[end] == "\\" else 1
                quoted.append(body[index + 1 : end])  # noqa: E203
                index = end + 1
            else:
                index += 1
        target = body.split(" ", 1)[0]
        operator = quoted[0] if quoted else ""
        actions = quoted[1] if len(quoted) > 1 else ""
        link = (f"{target} {operator}".strip(), actions)
        if current is None:
            current = []
            chains.append(current)
        current.append(link)
        if "chain" not in [action.strip() for action in actions.split(",")]:
            current = None
    return chains


def modsec_chain(text, rule_id):
    """The chain (list of links, see ``modsec_chains``) whose head carries ``id:<rule_id>``."""
    for chain in modsec_chains(text):
        head = chain[0][1].replace(" ", "")
        if f"id:{rule_id}," in head + "," or f"id:'{rule_id}'," in head + ",":
            return chain
    raise AssertionError(f"rule {rule_id} not rendered")
