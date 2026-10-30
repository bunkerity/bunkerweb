"""The stream Lua phases must read the stream shared dict, never the HTTP one.

The ``log``, ``preread`` and ``ssl_certificate`` blocks of a stream service built their ``internalstore`` on
``ngx.shared.internalstore``, the dict of the HTTP subsystem. The stream subsystem has its own ``internalstore_stream``, so the
plugin order and every other internal value the phases read came back empty and the stream security plugins silently stopped
running. This renders the stream service through the real Configurator and Templator and pins the dict each rendered phase
selects. Refs: #3107.
"""

import re

import pytest
from _t4_helpers import full_renderer

STREAM_PHASE_CONFS = ["log-stream-lua.conf", "preread-stream-lua.conf", "ssl-certificate-stream-lua.conf"]
STORE_DICT = re.compile(r"cdatastore:new\(ngx\.shared\.(\w+)\)")


@pytest.fixture(scope="module")
def tree():
    with full_renderer() as render:
        yield render(MULTISITE="no", SERVER_NAME="a.example.com", SERVER_TYPE="stream", LISTEN_STREAM_PORT_SSL="4242")


@pytest.mark.parametrize("name", STREAM_PHASE_CONFS)
def test_a_stream_phase_selects_the_stream_internalstore(tree, name):
    assert name in tree, f"{name} was not rendered for a stream service"
    assert STORE_DICT.findall(tree[name]) == ["internalstore_stream"]


def test_the_http_phases_keep_the_http_internalstore(tree):
    """The same templates for the HTTP subsystem are not touched: only the stream ones moved to the stream dict."""
    http = {name: STORE_DICT.findall(text) for name, text in tree.items() if name.endswith("-lua.conf") and "stream" not in name}
    stream = {name for name, found in http.items() if "internalstore_stream" in found}
    assert not stream, f"HTTP phase configs select the stream dict: {sorted(stream)}"
