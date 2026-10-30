"""Read helpers for the rendered ``listen`` directives.

A module of its own rather than ``conftest``: ``from conftest import …`` binds to whichever
conftest package got imported first when several test directories run together, so it silently
resolves to another directory's conftest and fails collection. ``tests/unit/gen`` is put on
``sys.path`` by its conftest, so this name is unambiguous.
"""


def listen_lines(tree, name=None):
    """Every rendered ``listen`` directive, as ``(file, stripped directive)``."""
    return [
        (path, line.strip())
        for path, text in tree.items()
        if name is None or path.endswith(name)
        for line in text.splitlines()
        if line.strip().startswith("listen ")
    ]


def listen_addresses(tree, name):
    """The ``addr:port`` of every ``listen`` in ``name``, in rendered order."""
    return [line.split()[1].rstrip(";") for _, line in listen_lines(tree, name)]


def socket_of(directive):
    """``(addr, transport)`` of a rendered ``listen``. ``quic`` is UDP, so it never collides with
    the TCP listener on the same number -- NGINX keys its listening list on (port, type, family)."""
    return directive.split()[1].rstrip(";"), "udp" if " quic" in directive else "tcp"


def included_blocks(tree):
    """The files ``http.conf`` actually includes, as keys of ``tree``.

    Templator renders every template; ``http.conf`` decides which ones NGINX loads
    (``:91-93`` for the default server, ``:105-127`` for the services). Only the included ones can
    collide, so only they are worth asserting on.
    """
    prefix = "include /etc/nginx/"
    names = []
    for line in tree["http.conf"].splitlines():
        line = line.strip()
        if line.startswith(prefix) and line.endswith(".conf;"):
            name = line[len(prefix) : -1]  # noqa: E203
            if name in tree:
                names.append(name)
    return names
