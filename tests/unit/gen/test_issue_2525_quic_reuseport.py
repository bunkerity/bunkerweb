"""HTTP/3 only works when the QUIC socket is opened with ``reuseport``.

QUIC multiplexes connections on one UDP socket and NGINX needs ``reuseport`` on the ``listen ... quic``
to steer packets to the right worker; without it HTTP/3 handshakes stall. The default server's QUIC
listeners lacked it (#2525), and so did the service's own ones in ``ssl-certificate-lua.conf`` (#2869).
``reuseport`` may be given once per socket, so the service block only carries it when no default server
is loaded in front of it (single-site with the default server left enabled).

Refs: #2525, #2869.
"""

import os.path

import pytest

from _listen_helpers import included_blocks, listen_lines
from _t4_helpers import full_renderer


@pytest.fixture(scope="module", autouse=True)
def default_server_certificate():
    """Exercise HTTPS listeners without requiring a root-owned certificate cache."""
    isfile = os.path.isfile
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(os.path, "isfile", lambda path: path == "/var/cache/bunkerweb/misc/default-server-cert.pem" or isfile(path))
        yield


@pytest.fixture(scope="module")
def render():
    with full_renderer() as render:
        yield render


def quic_listens(tree, name):
    return [line for _, line in listen_lines(tree, name) if " quic" in line]


HTTP3 = {"HTTP3": "yes", "USE_IPV6": "yes", "AUTO_LETS_ENCRYPT": "no"}


def test_default_server_quic_listeners_carry_reuseport(render):
    """#2525: both address families of the default server's QUIC socket."""
    tree = render(MULTISITE="yes", SERVER_NAME="a.example.com", **HTTP3)
    listens = quic_listens(tree, "default-server-http.conf")
    assert len(listens) == 2, listens
    assert all("reuseport" in line and "default_server" in line for line in listens), listens


def test_single_site_service_quic_listeners_carry_reuseport(render):
    """#2869: single-site with the default server enabled, the service block is the only QUIC owner."""
    tree = render(MULTISITE="no", SERVER_NAME="a.example.com", **HTTP3)
    assert "default-server-http.conf" not in included_blocks(tree)
    listens = quic_listens(tree, "ssl-certificate-lua.conf")
    assert len(listens) == 2, listens
    assert all(line.endswith("quic reuseport;") for line in listens), listens


@pytest.mark.parametrize(
    "variables",
    [
        {"MULTISITE": "no", "SERVER_NAME": "a.example.com", "DISABLE_DEFAULT_SERVER": "yes"},
        {"MULTISITE": "yes", "SERVER_NAME": "a.example.com"},
    ],
    ids=["single-site-default-server-loaded", "multisite"],
)
def test_service_does_not_repeat_reuseport_the_default_server_already_owns(render, variables):
    """A second ``reuseport`` on the same socket would make NGINX refuse the configuration."""
    tree = render(**variables, **HTTP3)
    service_blocks = [name for name in tree if name.endswith("ssl-certificate-lua.conf")]
    assert service_blocks
    for block in service_blocks:
        assert all("reuseport" not in line for line in quic_listens(tree, block)), block
    assert all("reuseport" in line for line in quic_listens(tree, "default-server-http.conf"))
