"""Startup discovery must deliver template exclusions before the first reload."""

from pathlib import Path
from tarfile import open as tar_open
from types import SimpleNamespace

import pytest

from scheduler_fakes import instance

REPO = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize("startup_instance", ["undiscovered", "unreachable"])
def test_first_reload_receives_template_custom_configs(sched_main, sandbox, fake_sched, monkeypatch, startup_instance):
    from ApiCaller import ApiCaller

    expected = {}
    for config_type in ("modsec", "modsec-crs"):
        data = (REPO / "src/common/core/templates/templates/api/configs" / config_type / "api.conf").read_bytes()
        expected[f"{config_type}/www.example.com/api.conf"] = data
        fake_sched.db.configs.append(
            {"type": config_type, "service_id": "www.example.com", "name": "api", "data": data, "method": "default", "template": "api"}
        )

    received = {}
    reload_snapshots = []
    requests = []
    fail_upload = startup_instance == "unreachable"

    def request(method, url, files=None, **kwargs):
        requests.append(url)
        if files is not None:
            if fail_upload:
                return False, "connection refused", None, {"status": "error"}
            if url == "custom_configs":
                with tar_open(fileobj=files["archive.tar.gz"], mode="r:gz") as archive:
                    received.clear()
                    for member in archive:
                        if member.isfile():
                            content = archive.extractfile(member)
                            assert content is not None
                            received[member.name.removeprefix("./")] = content.read()
        elif url.startswith("reload"):
            reload_snapshots.append(dict(received))
        return True, "", 200, {"status": "success", "msg": "ok"}

    api = SimpleNamespace(endpoint="http://bw1:5000/", request=request)
    real_api = sched_main.API
    monkeypatch.setattr(sched_main, "API", SimpleNamespace(from_instance=lambda row: api, build_endpoint=real_api.build_endpoint))
    monkeypatch.setattr(fake_sched, "send_files", lambda *args, **kwargs: ApiCaller(fake_sched.apis).send_files(*args, **kwargs))
    monkeypatch.setattr(fake_sched, "send_to_apis", lambda *args, **kwargs: ApiCaller(fake_sched.apis).send_to_apis(*args, **kwargs))
    monkeypatch.setattr(sched_main, "generate_configs", lambda: True)
    monkeypatch.setattr(sched_main, "IGNORE_FAIL_SENDING_CONFIG", False)

    if startup_instance == "unreachable":
        fake_sched.db.instances = [instance()]
        fake_sched.apis = [api]
    sched_main.generate_custom_configs(original_path=sandbox.CUSTOM_CONFIGS_PATH)
    assert not fake_sched.apis
    assert not received
    for path, data in expected.items():
        assert (sandbox.CUSTOM_CONFIGS_PATH / path).read_bytes() == data

    fail_upload = False
    fake_sched.db.instances = [instance()]
    requests.clear()
    assert sched_main.pre_push_configuration({"SERVER_NAME": "www.example.com"}, first_start=True) == (True, True, False)
    assert reload_snapshots == [expected]
    assert requests.index("custom_configs") < requests.index("confs") < requests.index("reload?test=yes")
