"""Drive real scheduler publication and health confirmation with fake instance APIs."""

from types import SimpleNamespace

import pytest

from ApiCaller import ApiCaller
import ApiCaller as api_caller_module
import reload_utils
from scheduler_fakes import instance
import test_main_loop as loop

# Reuse the existing end-to-end main-loop harness; replace only its transport stubs below.
drive = loop.drive


@pytest.fixture
def publication(sched_main, monkeypatch, request):
    sender = sched_main.send_file_to_bunkerweb
    h = request.getfixturevalue("drive")
    custom_generator = sched_main.generate_custom_configs
    plugins_generator = sched_main.generate_external_plugins
    monkeypatch.setattr(
        sched_main,
        "generate_custom_configs",
        lambda configs=None, **kwargs: custom_generator(configs, original_path=kwargs.pop("original_path", h.sandbox.CUSTOM_CONFIGS_PATH), **kwargs),
    )
    monkeypatch.setattr(
        sched_main,
        "generate_external_plugins",
        lambda original_path=None, **kwargs: plugins_generator(original_path or h.sandbox.EXTERNAL_PLUGINS_PATH, **kwargs),
    )
    now = [0.0]
    h.phase = 0
    h.requests = []
    h.nodes = {}

    class Node:
        def __init__(self, hostname):
            self.hostname = hostname
            self.endpoint = sched_main.API.build_endpoint(hostname, port=5000) + "/"
            self.online = True
            self.busy = set()
            self.answers = {}  # endpoint -> (sent, http status, body) the instance gives instead of success
            self.reload_delay = 0
            self.ready_at = 0

        def request(self, method, url, **kwargs):
            endpoint = "/" + url.lstrip("/").split("?", 1)[0]
            h.requests.append((h.phase, self.hostname, method, endpoint))
            if not self.online:
                return False, "connection refused", 0, {}
            if endpoint in self.busy:
                return True, "", 503, {"status": "error", "msg": "a push swap is in progress"}
            if endpoint in self.answers:
                sent, status, body = self.answers[endpoint]
                return sent, "" if sent else "Request failed: no JSON", status, body
            if method == "GET":
                state = "ok" if now[0] >= self.ready_at else "reloading"
                return True, "", 200, {"status": "success", "msg": state}
            if endpoint == "/reload":
                self.ready_at = now[0] + self.reload_delay
                return True, "", 200, {"status": "success", "confirmed": not self.reload_delay, "msg": "reload signalled"}
            return True, "", 200, {"status": "success", "msg": "uploaded"}

    def node(hostname):
        return h.nodes.setdefault(hostname, Node(hostname))

    def advance(delay):
        now[0] += delay

    def change_phase(phase, *, change=None, delay=1000):
        h.phase = phase
        now[0] += delay
        if change:
            h.db.metadata[change] = ["antibot"] if change == "plugins_config_changed" else True

    old_checked = h.db.checked_changes

    def checked(changes=None, plugins_changes=None):
        result = old_checked(changes, plugins_changes)
        for key in changes or ("pro_plugins", "external_plugins", "custom_configs", "config", "instances"):
            flag = "plugins_config_changed" if key == "config" else key + "_changed"
            h.db.metadata[flag] = [] if flag == "plugins_config_changed" else False
        return result

    old_update = h.db.update_instance

    def update(hostname, status):
        result = old_update(hostname, status)
        for record in h.db.instances:
            if record["hostname"] == hostname:
                record["status"] = status
        return result

    monkeypatch.setattr(sched_main, "API", SimpleNamespace(from_instance=lambda record: node(record["hostname"]), build_endpoint=sched_main.API.build_endpoint))
    monkeypatch.setattr(sched_main, "ApiCaller", ApiCaller)
    monkeypatch.setattr(sched_main, "send_file_to_bunkerweb", sender)
    monkeypatch.setattr(h.sched, "send_files", lambda *args, **kwargs: ApiCaller(list(h.sched.apis)).send_files(*args, **kwargs))
    monkeypatch.setattr(h.sched, "send_to_apis", lambda *args, **kwargs: ApiCaller(list(h.sched.apis)).send_to_apis(*args, **kwargs))
    monkeypatch.setattr(h.db, "checked_changes", checked)
    monkeypatch.setattr(h.db, "update_instance", update)
    monkeypatch.setattr(sched_main, "monotonic", lambda: now[0])
    monkeypatch.setattr(sched_main, "sleep", advance)
    monkeypatch.setattr(reload_utils, "monotonic", lambda: now[0])
    monkeypatch.setattr(reload_utils, "sleep", advance)
    monkeypatch.setattr(api_caller_module, "sleep", advance)
    sched_main.PUSH_BUSY.clear()
    sched_main.HEALTHCHECK_RELOADS.clear()
    sched_main.NEEDS_CONFIG_PENDING.clear()
    h.node = node
    h.change_phase = change_phase
    h.now = now
    yield h
    sched_main.PUSH_BUSY.clear()
    sched_main.HEALTHCHECK_RELOADS.clear()
    sched_main.NEEDS_CONFIG_PENDING.clear()


def posted(h, phase, host="bw1"):
    return [endpoint for current, hostname, method, endpoint in h.requests if current == phase and hostname == host and method == "POST"]


def test_down_registered_instance_is_not_a_publication_recipient(publication):
    h = publication
    h.db.instances.append(instance("bw2", status="down"))
    h.node("bw2").online = False
    h.run()
    assert loop.set_metadata_calls(h)[0] == {"failover": False, "failover_message": ""}
    assert "bw2" in h.main.NEEDS_CONFIG_PENDING
    assert posted(h, 0).count("/reload") == 2  # startup pre-job and post-job generations


def test_returning_instance_receives_every_current_folder_before_reload(publication):
    h = publication
    h.db.instances.append(instance("bw2", status="down"))
    h.node("bw2").online = False
    h.run()
    h.change_phase(1)
    h.main.APPLYING_CHANGES.clear()
    h.node("bw2").online = True
    h.main.healthcheck_job()
    assert sorted(posted(h, 1, "bw2")) == ["/cache", "/confs", "/custom_configs", "/plugins", "/pro_plugins", "/reload"]
    assert posted(h, 1) == []
    assert "bw2" not in h.main.NEEDS_CONFIG_PENDING
    assert h.db.instances[1]["status"] == "up"


@pytest.mark.parametrize(
    "endpoint,flag", [("/custom_configs", "custom_configs_changed"), ("/plugins", "external_plugins_changed"), ("/pro_plugins", "pro_plugins_changed")]
)
def test_busy_folder_is_sent_again_before_generation_is_acknowledged(publication, endpoint, flag):
    h = publication
    h.iterations = 3

    def change():
        h.change_phase(1, change=flag)
        h.node("bw1").busy.add(endpoint)

    def recover():
        h.node("bw1").busy.clear()
        h.change_phase(2)

    h.on_iteration.update({1: change, 2: recover})
    h.run()
    assert loop.set_metadata_calls(h)[1]["failover"] is True
    assert endpoint in posted(h, 2)
    assert posted(h, 2).index(endpoint) < posted(h, 2).index("/reload")
    assert loop.set_metadata_calls(h)[2] == {"failover": False, "failover_message": ""}


@pytest.mark.parametrize("change", ["custom_configs_changed", "plugins_config_changed"])
def test_slow_accepted_reload_is_confirmed_on_retry_before_render_or_repost(publication, change):
    h = publication
    h.iterations = 4
    renders = []

    def slow_change():
        h.change_phase(1, change=change)
        h.node("bw1").reload_delay = 180

    def ready():
        renders.append(h.renders)
        h.change_phase(2)

    def new_change():
        renders.append(h.renders)
        h.change_phase(3, change="custom_configs_changed")
        h.node("bw1").reload_delay = 0

    h.on_iteration.update({1: slow_change, 2: ready, 3: new_change})
    h.run()
    assert posted(h, 1).count("/reload") == 1
    assert posted(h, 2) == []
    assert renders[0] == renders[1]
    assert loop.set_metadata_calls(h)[2] == {"failover": False, "failover_message": ""}
    assert posted(h, 3).count("/reload") == 1


def test_retry_reloads_only_recipient_that_has_not_confirmed(publication):
    h = publication
    h.db.instances.append(instance("bw2"))
    h.iterations = 3

    def change():
        h.change_phase(1, change="custom_configs_changed")
        h.node("bw2").busy.add("/reload")

    def recover():
        h.node("bw2").busy.clear()
        h.change_phase(2)

    h.on_iteration.update({1: change, 2: recover})
    h.run()
    assert posted(h, 2) == []
    assert posted(h, 2, "bw2").count("/reload") == 1
    assert loop.set_metadata_calls(h)[2] == {"failover": False, "failover_message": ""}


def test_returning_instance_catchup_waits_for_confirmation_without_second_push(publication):
    h = publication
    h.db.instances.append(instance("bw2", status="down"))
    h.node("bw2").online = False
    h.run()
    h.change_phase(1)
    h.main.APPLYING_CHANGES.clear()
    h.node("bw2").online = True
    h.node("bw2").reload_delay = 180
    h.main.healthcheck_job()
    assert "bw2" in h.main.NEEDS_CONFIG_PENDING
    assert "bw2" in h.main.HEALTHCHECK_RELOADS
    assert h.db.instances[1]["status"] == "loading"
    h.change_phase(2)
    h.main.healthcheck_job()
    assert posted(h, 2, "bw2") == []
    assert "bw2" not in h.main.NEEDS_CONFIG_PENDING
    assert "bw2" not in h.main.HEALTHCHECK_RELOADS
    assert h.db.instances[1]["status"] == "up"


def test_busy_folder_retry_leaves_confirmed_sibling_untouched(publication):
    h = publication
    h.db.instances.append(instance("bw2"))
    h.iterations = 3

    def change():
        h.change_phase(1, change="custom_configs_changed")
        h.node("bw2").busy.add("/custom_configs")

    def recover():
        h.node("bw2").busy.clear()
        h.change_phase(2)

    h.on_iteration.update({1: change, 2: recover})
    h.run()
    assert posted(h, 2) == []
    assert sorted(posted(h, 2, "bw2")) == ["/custom_configs", "/reload"]
    assert loop.set_metadata_calls(h)[2]["failover"] is False


def test_new_change_waits_for_old_reload_then_publishes_once(publication):
    h = publication
    h.iterations = 4
    renders = []

    def slow_change():
        h.change_phase(1, change="custom_configs_changed")
        h.node("bw1").reload_delay = 1000

    def overlapping_change():
        renders.append(h.renders)
        h.change_phase(2, change="custom_configs_changed", delay=1)

    def ready():
        renders.append(h.renders)
        h.change_phase(3)
        h.node("bw1").reload_delay = 0

    h.on_iteration.update({1: slow_change, 2: overlapping_change, 3: ready})
    h.run()
    assert posted(h, 1).count("/reload") == 1
    assert posted(h, 2) == []
    assert renders[0] == renders[1]
    assert posted(h, 3).count("/reload") == 1
    assert "/custom_configs" in posted(h, 3)
    assert loop.set_metadata_calls(h)[3]["failover"] is False


def test_failed_folder_is_kept_until_evicted_recipient_returns(publication, monkeypatch):
    h = publication
    h.db.instances.append(instance("bw2"))
    h.iterations = 4
    old_request = h.node("bw2").request

    def fail_folder(method, url, **kwargs):
        if h.phase == 1 and url.lstrip("/") == "custom_configs":
            h.node("bw2").online = False
        return old_request(method, url, **kwargs)

    monkeypatch.setattr(h.node("bw2"), "request", fail_folder)

    def change():
        h.change_phase(1, change="custom_configs_changed")

    def still_down():
        h.change_phase(2)

    def recover():
        h.change_phase(3)
        h.node("bw2").online = True
        h.main.APPLYING_CHANGES.clear()
        h.main.healthcheck_job()

    h.on_iteration.update({1: change, 2: still_down, 3: recover})
    h.run()
    assert loop.set_metadata_calls(h)[1]["failover"] is True
    assert loop.set_metadata_calls(h)[2]["failover"] is True
    assert posted(h, 2) == []
    assert posted(h, 2, "bw2") == []
    assert "/custom_configs" in posted(h, 3, "bw2")
    assert posted(h, 3, "bw2").count("/reload") == 1
    assert posted(h, 3) == []
    assert loop.set_metadata_calls(h)[3]["failover"] is False


def test_new_generation_waits_for_returning_nodes_accepted_catchup(publication):
    h = publication
    h.db.instances.append(instance("bw2", status="down"))
    h.node("bw2").online = False
    h.iterations = 3
    pending = []

    def returning():
        h.change_phase(1, change="custom_configs_changed", delay=1)
        h.node("bw2").online = True
        h.node("bw2").reload_delay = 1000
        h.main.APPLYING_CHANGES.clear()
        h.main.healthcheck_job()

    def ready():
        pending.append("bw2" in h.main.NEEDS_CONFIG_PENDING)
        h.change_phase(2)
        h.node("bw2").reload_delay = 0

    h.on_iteration.update({1: returning, 2: ready})
    h.run()
    assert posted(h, 1, "bw2").count("/reload") == 1
    assert posted(h, 1) == []
    assert pending == [True]
    assert sorted(posted(h, 2, "bw2")) == ["/cache", "/confs", "/custom_configs", "/plugins", "/pro_plugins", "/reload"]
    assert posted(h, 2).count("/reload") == 1
    assert "bw2" not in h.main.HEALTHCHECK_RELOADS
    assert "bw2" not in h.main.NEEDS_CONFIG_PENDING


def test_catchup_does_not_push_or_reload_after_render_failure(publication):
    h = publication
    h.db.instances.append(instance("bw2", status="down"))
    h.node("bw2").online = False
    h.run()
    h.change_phase(1)
    h.node("bw2").online = True
    h.render_ok = False
    h.main.APPLYING_CHANGES.clear()
    h.main.healthcheck_job()
    assert posted(h, 1, "bw2") == []
    assert "bw2" in h.main.NEEDS_CONFIG_PENDING
    assert h.db.instances[1]["status"] != "up"


@pytest.mark.parametrize("hostname", ["bw1", "BW1"])
def test_explicit_confirmation_failure_is_retained_for_retry(publication, monkeypatch, hostname):
    h = publication
    h.db.instances = [instance(hostname)]
    api = h.node(hostname)
    monkeypatch.setattr(api, "request", lambda *args, **kwargs: (True, "", 500, {"status": "error", "msg": "initialization failed"}))
    responses = {hostname: {"status": "success", "confirmed": False}}
    assert h.main.confirm_unconfirmed_reloads(responses, 15) == {hostname: "initialization failed"}
    assert responses[hostname]["status"] == "error"
    assert responses[hostname]["msg"] == "reload failed: initialization failed"


REFUSED = (True, 500, {"status": "error", "msg": "cannot extract archive"})


def answers_again(h):
    """The loop harness stubs wait_for_reachable_instance without its job: put the instances that answer back in apis."""

    def wait(timeout=60):
        for record in h.db.get_instances():
            api = h.main.API.from_instance(record)
            if api.request("GET", "health")[0] and all(known.endpoint != api.endpoint for known in h.main.SCHEDULER.apis):
                h.main.SCHEDULER.apis.append(api)
        return bool(h.main.SCHEDULER.apis)

    h.main.wait_for_reachable_instance = wait


def reloads(h, host="bw1"):
    return posted(h, 0, host).count("/reload")


@pytest.mark.parametrize("endpoint", ["/custom_configs", "/plugins", "/pro_plugins"])
def test_ignore_fail_sending_config_does_not_block_reload_on_a_failed_folder(publication, monkeypatch, caplog, endpoint):
    h = publication
    monkeypatch.setattr(h.main, "IGNORE_FAIL_SENDING_CONFIG", True)
    h.node("bw1").answers[endpoint] = REFUSED
    with caplog.at_level("WARNING"):
        h.run()
    assert reloads(h) == 2
    assert f"{endpoint} was not applied on bw1, reloading without it (IGNORE_FAIL_SENDING_CONFIG is set)" in caplog.text
    assert loop.set_metadata_calls(h)[0] == {"failover": False, "failover_message": ""}


@pytest.mark.parametrize("ignore_failure", [False, True], ids=["flag-off", "flag-on"])
def test_partial_folder_failure_names_only_failed_host(publication, monkeypatch, caplog, ignore_failure):
    h = publication
    h.db.instances.append(instance("bw2"))
    h.run()
    h.change_phase(1)
    monkeypatch.setattr(h.main, "IGNORE_FAIL_SENDING_CONFIG", ignore_failure)
    endpoint = "/plugins"
    h.node("bw2").answers[endpoint] = REFUSED
    recipients = {hostname: h.node(hostname) for hostname in ("bw1", "bw2")}
    outcome = {"rendered": True, "recipients": recipients, "folders": {endpoint: set(recipients)}}
    call_count = len(h.db.calls)
    with caplog.at_level("WARNING"):
        h.main.publish_configuration({}, outcome)

    assert posted(h, 1, "bw1") == [endpoint, "/reload"]
    assert outcome["success"] is ignore_failure
    reachable = {api.endpoint for api in h.sched.apis}
    down = [(hostname, status) for method, hostname, status in h.db.calls[call_count:] if method == "update_instance" and status == "down"]
    warnings = [record.message for record in caplog.records if "reloading without it" in record.message]
    if ignore_failure:
        assert posted(h, 1, "bw2") == [endpoint, "/reload"]
        assert outcome["folders"][endpoint] == set()
        assert reachable == {node.endpoint for node in recipients.values()}
        assert down == []
        assert warnings == [f"{endpoint} was not applied on bw2, reloading without it (IGNORE_FAIL_SENDING_CONFIG is set)"]
    else:
        assert posted(h, 1, "bw2") == [endpoint]
        assert outcome["folders"][endpoint] == {"bw2"}
        assert reachable == {h.node("bw1").endpoint}
        assert down == [("bw2", "down")]
        assert warnings == []


@pytest.mark.parametrize("endpoint", ["/custom_configs", "/plugins", "/pro_plugins"])
def test_refused_folder_keeps_publication_pending_without_the_flag(publication, caplog, endpoint):
    h = publication
    h.run()
    h.change_phase(1)
    h.node("bw1").answers[endpoint] = REFUSED
    outcome = {"new_folders": {endpoint}}
    with caplog.at_level("WARNING"):
        h.main.publish_configuration({}, outcome)
    assert endpoint in posted(h, 1)
    assert "/reload" not in posted(h, 1)
    assert outcome["folders"][endpoint] == {"bw1"}
    assert "reloading without it" not in caplog.text

    h.change_phase(2)
    h.node("bw1").answers.clear()
    answers_again(h)
    assert h.main.wait_for_reachable_instance()
    h.main.publish_configuration({}, outcome)
    assert posted(h, 2) == [endpoint, "/reload"]
    assert outcome["success"]


@pytest.mark.parametrize("endpoint", ["/custom_configs", "/plugins", "/pro_plugins", "/confs", "/cache"])
def test_refused_folder_blocks_startup_reload_without_the_flag(publication, endpoint):
    h = publication
    answers_again(h)
    h.node("bw1").answers[endpoint] = REFUSED
    h.run()
    assert reloads(h) == 0
    assert endpoint in posted(h, 0)


@pytest.mark.parametrize(
    "answer",
    [
        (False, 0, {}),  # connection refused or timeout
        (False, None, None),  # API.request could not decode the answer: same four-tuple as a transport error
    ],
)
@pytest.mark.parametrize("endpoint,flag", [("/plugins", "external_plugins_changed"), ("/pro_plugins", "pro_plugins_changed")])
def test_silent_instance_keeps_the_plugin_folder_pending(publication, caplog, endpoint, flag, answer):
    h = publication
    h.db.instances.append(instance("bw2"))
    h.iterations = 3

    def change():
        h.change_phase(1, change=flag)
        h.node("bw2").answers[endpoint] = answer

    def recover():
        h.node("bw2").answers.clear()
        h.change_phase(2)

    h.on_iteration.update({1: change, 2: recover})
    with caplog.at_level("WARNING"):
        h.run()
    assert endpoint in posted(h, 1, "bw2")
    assert "/reload" not in posted(h, 1, "bw2")
    assert "reloading without it" not in caplog.text
    assert loop.set_metadata_calls(h)[1]["failover"] is True


@pytest.mark.parametrize("endpoint", ["/plugins", "/pro_plugins"])
def test_busy_plugin_folder_is_not_treated_as_a_refusal(publication, caplog, endpoint):
    h = publication
    h.node("bw1").busy.add(endpoint)
    with caplog.at_level("WARNING"):
        h.run()
    assert reloads(h) == 0
    assert "reloading without it" not in caplog.text
    assert loop.set_metadata_calls(h)[0]["failover"] is True


def test_all_folders_accepted_logs_no_refusal(publication, caplog):
    h = publication
    with caplog.at_level("WARNING"):
        h.run()
    assert reloads(h) == 2
    assert "reloading without it" not in caplog.text


PENDING_ERRORS = [
    "swap failed: attempt to index a nil value",  # Lua error inside pushswap.swap: state unknown
    "cannot park saml: Permission denied",  # swap aborted, rolled back in full
    "cannot place saml: Permission denied",
    "cannot sweep old: Permission denied",
    "cannot park saml: Permission denied (rollback incomplete, left in place: /d/saml (copy kept at /d/.bw-rescue.1/saml))",  # mixed tree
    "cannot open /tmp/upload",  # body handling
]


@pytest.mark.parametrize("message", PENDING_ERRORS)
@pytest.mark.parametrize("endpoint,flag", [("/plugins", "external_plugins_changed"), ("/pro_plugins", "pro_plugins_changed")])
def test_plugin_push_error_that_may_leave_a_mixed_tree_keeps_the_reload_blocked(publication, caplog, endpoint, flag, message):
    h = publication
    h.iterations = 2

    def change():
        h.change_phase(1, change=flag)
        h.node("bw1").answers[endpoint] = (True, 500, {"status": "error", "msg": message})

    h.on_iteration.update({1: change})
    with caplog.at_level("WARNING"):
        h.run()
    assert endpoint in posted(h, 1)
    assert "/reload" not in posted(h, 1)
    assert "reloading without it" not in caplog.text


def prepare_returning_instance(h):
    h.db.instances.append(instance("bw2", status="down"))
    h.node("bw2").online = False
    h.run()
    h.change_phase(1)
    h.main.APPLYING_CHANGES.clear()
    h.node("bw2").online = True


@pytest.mark.parametrize("endpoint", ["/custom_configs", "/plugins", "/pro_plugins"])
def test_catchup_with_ignore_fail_sending_config_reloads_after_any_failed_folder(publication, monkeypatch, caplog, endpoint):
    h = publication
    prepare_returning_instance(h)
    monkeypatch.setattr(h.main, "IGNORE_FAIL_SENDING_CONFIG", True)
    h.node("bw2").answers[endpoint] = REFUSED
    with caplog.at_level("WARNING"):
        h.main.healthcheck_job()
    assert posted(h, 1, "bw2")[-1] == "/reload"
    assert f"{endpoint} was not applied on bw2, reloading without it (IGNORE_FAIL_SENDING_CONFIG is set)" in caplog.text


@pytest.mark.parametrize(
    "endpoint,answer",
    [
        ("/custom_configs", REFUSED),
        ("/plugins", REFUSED),
        ("/pro_plugins", REFUSED),
        ("/plugins", (True, 503, {"status": "error", "msg": "a push swap is in progress"})),
        ("/plugins", (True, 500, {"status": "error", "msg": "cannot park saml: Permission denied"})),
        ("/pro_plugins", (False, 0, {})),  # silent instance
    ],
)
def test_catchup_keeps_failed_folders_pending_without_the_flag(publication, endpoint, answer):
    h = publication
    prepare_returning_instance(h)
    h.node("bw2").answers[endpoint] = answer
    h.main.healthcheck_job()
    assert endpoint in posted(h, 1, "bw2")
    assert "/reload" not in posted(h, 1, "bw2")
    assert "bw2" in h.main.NEEDS_CONFIG_PENDING

    h.change_phase(2)
    h.node("bw2").answers.clear()
    h.main.healthcheck_job()
    assert endpoint in posted(h, 2, "bw2")
    assert posted(h, 2, "bw2")[-1] == "/reload"
    assert "bw2" not in h.main.NEEDS_CONFIG_PENDING


@pytest.mark.parametrize("catchup", [False, True], ids=["publication", "catchup"])
@pytest.mark.parametrize("ignore_failure", [False, True], ids=["flag-off", "flag-on"])
def test_folder_archive_error_obeys_ignore_fail_sending_config(publication, monkeypatch, caplog, catchup, ignore_failure):
    h = publication
    if catchup:
        prepare_returning_instance(h)
    else:
        h.run()
        h.change_phase(1)
    hostname = "bw2" if catchup else "bw1"
    monkeypatch.setattr(h.main, "IGNORE_FAIL_SENDING_CONFIG", ignore_failure)
    build_archive = ApiCaller._build_archive
    failed_folders = {str(h.main.CUSTOM_CONFIGS_PATH), str(h.main.CACHE_PATH)}

    def build(path):
        if path in failed_folders:
            raise OSError("archive file disappeared")
        return build_archive(path)

    monkeypatch.setattr(ApiCaller, "_build_archive", staticmethod(build))
    outcome = {"new_folders": {"/custom_configs", "/plugins", "/pro_plugins"}}
    with caplog.at_level("WARNING"):
        if catchup:
            h.main.healthcheck_job()
        else:
            h.main.publish_configuration({}, outcome)

    posts = posted(h, 1, hostname)
    assert ("/reload" in posts) is ignore_failure
    assert sorted(endpoint for endpoint in posts if endpoint != "/reload") == ["/confs", "/plugins", "/pro_plugins"]
    if ignore_failure:
        assert posts[-1] == "/reload"
    if catchup:
        assert (hostname in h.main.NEEDS_CONFIG_PENDING) is not ignore_failure
    for endpoint in ("/custom_configs", "/cache"):
        assert f"Exception while sending {endpoint}: archive file disappeared" in caplog.text
        if ignore_failure:
            assert f"{endpoint} was not applied on {hostname}, reloading without it (IGNORE_FAIL_SENDING_CONFIG is set)" in caplog.text
        if not catchup:
            assert outcome["folders"][endpoint] == (set() if ignore_failure else {hostname})
