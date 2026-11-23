"""BW-2450: a refused folder push leaves the instance's own message in the scheduler log, whichever caller sent it."""

import logging

from scheduler_fakes import FakeApi, instance

PARK_ERROR = "cannot park modsec-crs: /etc/bunkerweb/configs/modsec-crs: Permission denied"
REFUSAL = (True, "", 500, {"status": "error", "msg": PARK_ERROR})


def test_folder_push_refusal_message_reaches_the_log(sched_main, fake_sched, fake_api, tmp_path, caplog):
    (tmp_path / "http").mkdir()
    fake_sched.db.instances = [instance("bw1")]
    target = FakeApi("http://bw1:5000/", answer=REFUSAL)
    fake_sched.apis = [target]
    failed = {}
    with caplog.at_level(logging.ERROR):
        sched_main.send_file_to_bunkerweb(tmp_path, "/custom_configs", api_caller=sched_main.ApiCaller([target]), failed=failed)
    assert failed["bw1"]["msg"] == PARK_ERROR
    errors = [record.getMessage() for record in caplog.records if record.levelno >= logging.ERROR]
    assert any(PARK_ERROR in line and "/custom_configs" in line for line in errors), errors


def test_scheduler_wide_push_refusal_message_reaches_the_log(sched_main, fake_sched, fake_api, tmp_path, caplog):
    (tmp_path / "http").mkdir()
    fake_sched.db.instances = [instance("bw1")]
    target = FakeApi("http://bw1:5000/", answer=REFUSAL)
    fake_sched.apis = [target]
    caller = sched_main.ApiCaller([target])
    fake_sched.send_files = lambda *args, **kwargs: caller.send_files(*args, **kwargs)
    with caplog.at_level(logging.ERROR):
        assert sched_main.send_file_to_bunkerweb(tmp_path, "/custom_configs") is False
    errors = [record.getMessage() for record in caplog.records if record.levelno >= logging.ERROR]
    assert any(PARK_ERROR in line for line in errors), errors
