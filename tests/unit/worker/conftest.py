"""Filesystem setup omitted by the lightweight worker loader."""

import pytest


@pytest.fixture(autouse=True)
def cache_publication_root(tmp_path, monkeypatch):
    from test_delivery_guarantees import TASKS
    from test_execute_job_deferral_reason import TASKS as deferral_tasks

    # Each lightweight loader can retain its own jobs namespace after restoring
    # sys.modules. Supply every loader used by the worker tests a real root.
    for tasks in (TASKS, deferral_tasks):
        monkeypatch.setitem(tasks.cache_publication_lock.__wrapped__.__globals__, "CACHE_PATH", tmp_path)
