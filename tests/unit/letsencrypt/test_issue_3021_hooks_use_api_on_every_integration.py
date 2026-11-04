"""The ACME challenge hooks reach instances through their API whatever the integration is.

On a Linux install the hooks used to write the challenge token into a local directory, which the
instance serving the domain never read when the scheduler and the instance ran apart: the challenge
was answered by the wrong host. Both hooks now send the token to every instance over the API on
every integration and touch no local challenge file. Refs #3021.
"""

from pathlib import Path
from runpy import run_path
from sys import modules
from types import ModuleType
from unittest.mock import MagicMock

import pytest

import common_utils

_JOBS = Path(__file__).resolve().parents[3] / "src" / "common" / "core" / "letsencrypt" / "jobs"
INSTANCES = [{"hostname": "bw-1"}, {"hostname": "bw-2"}]


def _run_hook(name, monkeypatch, integration):
    apis = []

    def from_instance(instance):
        api = MagicMock()
        api.endpoint = f"http://{instance['hostname']}:5000"
        api.request.return_value = (True, None, 200, {"status": "success"})
        apis.append(api)
        return api

    for mod_name, attr, value in (
        ("Database", "Database", MagicMock(return_value=MagicMock(get_instances=MagicMock(return_value=INSTANCES)))),
        ("logger", "getLogger", MagicMock(return_value=MagicMock())),
        ("API", "API", MagicMock(from_instance=from_instance)),
    ):
        stub = ModuleType(mod_name)
        setattr(stub, attr, value)
        monkeypatch.setitem(modules, mod_name, stub)

    # A hook that still branches on the integration must see the one under test.
    monkeypatch.setattr(common_utils, "get_integration", lambda: integration)
    monkeypatch.setenv("CERTBOT_TOKEN", "tok123")
    monkeypatch.setenv("CERTBOT_VALIDATION", "val456")

    # Any local challenge file operation is recorded instead of touching the real filesystem.
    touched = []
    monkeypatch.setattr(Path, "mkdir", lambda self, *a, **k: touched.append(("mkdir", str(self))))
    monkeypatch.setattr(Path, "write_text", lambda self, *a, **k: touched.append(("write_text", str(self))))
    monkeypatch.setattr(Path, "unlink", lambda self, *a, **k: touched.append(("unlink", str(self))))

    with pytest.raises(SystemExit) as exit_info:
        run_path(str(_JOBS / name), run_name="__main__")
    return exit_info.value.code, apis, touched


@pytest.mark.parametrize("integration", ["Linux", "Docker", "Kubernetes"])
def test_auth_hook_posts_the_challenge_to_every_instance_and_writes_no_local_file(monkeypatch, integration):
    code, apis, touched = _run_hook("certbot-auth.py", monkeypatch, integration)

    assert code == 0
    assert [api.endpoint for api in apis] == ["http://bw-1:5000", "http://bw-2:5000"]
    for api in apis:
        api.request.assert_called_once_with("POST", "/lets-encrypt/challenge", data={"token": "tok123", "validation": "val456"})
    assert touched == []


@pytest.mark.parametrize("integration", ["Linux", "Docker", "Kubernetes"])
def test_cleanup_hook_deletes_the_challenge_on_every_instance_and_touches_no_local_file(monkeypatch, integration):
    code, apis, touched = _run_hook("certbot-cleanup.py", monkeypatch, integration)

    assert code == 0
    assert [api.endpoint for api in apis] == ["http://bw-1:5000", "http://bw-2:5000"]
    for api in apis:
        api.request.assert_called_once_with("DELETE", "/lets-encrypt/challenge", data={"token": "tok123"})
    assert touched == []
