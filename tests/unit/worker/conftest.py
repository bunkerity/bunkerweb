"""Filesystem setup omitted by the lightweight worker loader."""

import pytest


@pytest.fixture(autouse=True)
def cache_publication_root(tmp_path, monkeypatch):
    from test_delivery_guarantees import TASKS

    # The loader retains this jobs namespace after restoring sys.modules.
    # Supply a real root and keep the production lock, writes and failure paths.
    monkeypatch.setitem(TASKS.cache_publication_lock.__wrapped__.__globals__, "CACHE_PATH", tmp_path)
