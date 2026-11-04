"""The anonymous report counts services rather than single-site aliases."""

from pathlib import Path
import runpy
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

JOB_PATH = Path(__file__).resolve().parents[3] / "src/common/core/misc/jobs/anonymous-report.py"


@pytest.mark.parametrize("multisite,expected", [("no", "1"), ("yes", "3")])
def test_report_service_count(monkeypatch, multisite, expected):
    db = Mock(database_uri="sqlite:///test.db")
    db.get_metadata.return_value = {"version": "1.7", "integration": "Docker", "database_version": "3.0", "is_pro": False}
    db.get_non_default_settings.return_value = {
        "SERVER_NAME": {"value": "a.example b.example c.example"},
        "MULTISITE": {"value": multisite},
    }
    db.get_config.return_value = {}
    db.get_plugins.return_value = []
    db.get_instances.return_value = []
    db.get_custom_configs.return_value = {}
    db.get_ui_users.return_value = []
    job = Mock(db=db)
    job.is_cached_file.return_value = False
    job.cache_file.return_value = (True, "")
    post = Mock(return_value=Mock(status_code=200))
    monkeypatch.setattr(sys, "path", sys.path.copy())
    monkeypatch.setenv("SEND_ANONYMOUS_REPORT", "yes")
    monkeypatch.setitem(sys.modules, "jobs", SimpleNamespace(Job=lambda *_: job))
    monkeypatch.setitem(sys.modules, "logger", SimpleNamespace(getLogger=lambda *_: Mock()))
    monkeypatch.setitem(sys.modules, "common_utils", SimpleNamespace(get_os_info=lambda: "test", split_templates=lambda value: (value or "").split()))
    monkeypatch.setitem(sys.modules, "requests", SimpleNamespace(post=post))
    with pytest.raises(SystemExit) as result:
        runpy.run_path(str(JOB_PATH))
    assert result.value.code == 0
    assert post.call_args.kwargs["json"]["service_number"] == expected
