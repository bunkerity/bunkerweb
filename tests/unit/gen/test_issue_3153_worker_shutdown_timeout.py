"""Old NGINX workers must be force-closed after a reload, or they linger and leak memory.

A reload starts new workers and lets the old ones finish their connections; with long-lived
connections (WebSocket, streams, keep-alive) an old worker never exits and the memory of every
generation piles up. ``nginx.conf`` now renders ``worker_shutdown_timeout`` in the main context from
the global ``WORKER_SHUTDOWN_TIMEOUT`` setting.

Refs: #3153.
"""

import re

import pytest

from _t4_helpers import full_renderer


@pytest.fixture(scope="module")
def render():
    with full_renderer() as render:
        yield render


def main_context_directives(nginx_conf):
    """The directives written before the first block, i.e. in NGINX's main context."""
    return [line.strip() for line in nginx_conf.split("events {", 1)[0].splitlines() if line.strip() and not line.strip().startswith("#")]


def test_default_bounds_the_graceful_shutdown_of_old_workers(render):
    nginx_conf = render(MULTISITE="no", SERVER_NAME="app.example.com")["nginx.conf"]
    assert "worker_shutdown_timeout 30s;" in main_context_directives(nginx_conf)


@pytest.mark.parametrize("value", ["5s", "90s", "10m", "500ms"])
def test_the_setting_is_rendered_verbatim(render, value):
    nginx_conf = render(MULTISITE="no", SERVER_NAME="app.example.com", WORKER_SHUTDOWN_TIMEOUT=value)["nginx.conf"]
    assert [line for line in main_context_directives(nginx_conf) if line.startswith("worker_shutdown_timeout")] == [f"worker_shutdown_timeout {value};"]


def test_the_directive_is_rendered_exactly_once(render):
    nginx_conf = render(MULTISITE="no", SERVER_NAME="app.example.com")["nginx.conf"]
    assert len(re.findall(r"^\s*worker_shutdown_timeout\b", nginx_conf, re.M)) == 1
