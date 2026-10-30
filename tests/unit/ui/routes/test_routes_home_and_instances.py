"""The home dashboard feed and the /instances blueprint."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


def _flashed(h, client):
    return [message for message, _category in h.flashes(client)]


# --------------------------------------------------------------------------------------
# home
# --------------------------------------------------------------------------------------
@pytest.fixture
def home(h):
    h.routes.home.get_redis_client = lambda: "redis"
    h.instances.get_home_aggregates.return_value = {
        "request_countries": {"FR": {"blocked": 1}, "US": {"blocked": 5}, "DE": {"blocked": 5}},
        "top_blocked_ips": {"1.1.1.1": 3},
        "blocked_unique_ips": 9,
        "time_buckets": {"t": 1},
        "request_statuses": {200: 7, 404: 1},
    }
    h.instances.get_metrics.return_value = {}
    h.instances.get_instances.return_value = ["instance"]
    h.db.get_services.return_value = ["service"]
    return h.routes.home


def _context(h):
    template, context = h.renders[-1]
    assert template == "home.html"
    return context


def test_home_orders_countries_by_blocked_count_then_code(h, home):
    h.client().get("/home")

    assert list(_context(h)["request_countries"]) == ["DE", "US", "FR"]
    h.instances.get_home_aggregates.assert_called_once_with(hours=24 * 7, redis_client="redis")


def test_home_prefers_the_cumulative_error_counters_for_statuses(h, home):
    h.instances.get_metrics.return_value = {"counter_404": {"value": "3"}, "502": 2, "counter_404 ": 1, "not-a-status": 5, "500": 0, "200": "x"}

    h.client().get("/home")

    context = _context(h)
    assert context["request_errors"] == {404: 4, 502: 2}
    assert context["statuses_all_time"] is True


def test_home_falls_back_to_windowed_statuses_without_error_counters(h, home):
    h.client().get("/home")

    context = _context(h)
    assert context["request_errors"] == {200: 7, 404: 1}
    assert context["statuses_all_time"] is False
    assert context["blocked_unique_ips"] == 9
    assert context["instances"] == ["instance"] and context["services"] == ["service"]


@pytest.mark.parametrize(
    "total_gb, used_gb, state",
    [(4, 1, "low"), (8, 1, "medium"), (32, 1, "high"), (32, 30, "danger"), (4, 3.8, "danger")],
)
def test_home_memory_state(h, home, monkeypatch, total_gb, used_gb, state):
    gib = 1024**3
    monkeypatch.setattr(home, "virtual_memory", lambda: SimpleNamespace(total=total_gb * gib, used=used_gb * gib, available=(total_gb - used_gb) * gib))

    h.client().get("/home")

    info = _context(h)["memory_info"]
    assert info["memory_state"] == state
    assert info["total_gb"] == round(total_gb, 1)
    assert info["used_percent"] == round(used_gb / total_gb * 100, 1)


# --------------------------------------------------------------------------------------
# instances
# --------------------------------------------------------------------------------------
@pytest.fixture
def instances(h):
    h.config.get_config.return_value = {}
    h.instances.get_instances.return_value = []
    h.db.add_instance.return_value = ""
    return h.routes.instances


def test_instances_page_lists_the_instances(h, instances):
    h.instances.get_instances.return_value = ["a"]

    assert h.client().get("/instances").status_code == 200
    assert h.renders[-1] == ("instances.html", {"instances": ["a"]})


@pytest.mark.parametrize(
    "hostname, expected",
    [
        ("bw-1", {"hostname": "bw-1", "port": "5000", "listen_https": False, "https_port": "5443"}),
        ("bw-1:8080", {"hostname": "bw-1", "port": "8080", "listen_https": False, "https_port": "5443"}),
        ("https://bw-1", {"hostname": "bw-1", "port": "5000", "listen_https": True, "https_port": "5443"}),
        ("https://bw-1:9443", {"hostname": "bw-1", "port": "5000", "listen_https": True, "https_port": "9443"}),
        ("http://bw-1:81", {"hostname": "bw-1", "port": "81", "listen_https": False, "https_port": "5443"}),
    ],
)
def test_new_instance_derives_ports_and_scheme_from_the_hostname(h, instances, hostname, expected):
    h.client().post("/instances/new", data={"hostname": hostname, "name": "edge"})

    kwargs = h.db.add_instance.call_args.kwargs
    assert {key: kwargs[key] for key in expected} == expected
    assert kwargs["name"] == "edge" and kwargs["method"] == "ui" and kwargs["server_name"] == "bwapi"


def test_new_instance_uses_the_configured_api_defaults(h, instances):
    h.config.get_config.return_value = {"API_HTTP_PORT": "6000", "API_SERVER_NAME": "api.local", "API_LISTEN_HTTPS": "yes", "API_HTTPS_PORT": "6443"}

    h.client().post("/instances/new", data={"hostname": "bw-2", "name": "x"})

    kwargs = h.db.add_instance.call_args.kwargs
    assert (kwargs["port"], kwargs["server_name"], kwargs["listen_https"], kwargs["https_port"]) == ("6000", "api.local", True, "6443")


def test_new_instance_rejects_a_hostname_already_in_use(h, instances):
    h.instances.get_instances.return_value = [SimpleNamespace(hostname="bw-1")]
    client = h.client()

    client.post("/instances/new", data={"hostname": "bw-1", "name": "dup"})

    h.db.add_instance.assert_not_called()
    assert "The hostname bw-1 is already in use." in _flashed(h, client)


def test_new_instance_reports_a_database_error(h, instances):
    h.db.add_instance.return_value = "constraint failed"
    client = h.client()

    client.post("/instances/new", data={"hostname": "bw-9", "name": "x"})

    assert "Couldn't create the instance in the database: constraint failed" in _flashed(h, client)


def test_new_instance_rejects_an_invalid_hostname(h, instances):
    client = h.client()

    client.post("/instances/new", data={"hostname": "http://", "name": "x"})

    h.db.add_instance.assert_not_called()


@pytest.mark.parametrize("form", [{"name": "x"}, {"hostname": "bw"}, {}])
def test_new_instance_needs_hostname_and_name_with_a_redirect(h, instances, form):
    response = h.client().post("/instances/new", data=form)

    assert response.status_code == 302


@pytest.mark.parametrize("form", [{"name": "x"}, {"hostname": "bw"}, {}])
def test_new_instance_without_hostname_or_name_creates_nothing(h, instances, form):
    h.client().post("/instances/new", data=form)

    h.db.add_instance.assert_not_called()


def test_new_instance_in_read_only_mode(h, instances):
    h.db.readonly = True

    h.client().post("/instances/new", data={"hostname": "bw", "name": "x"})

    h.db.add_instance.assert_not_called()


def test_instance_ping_reports_who_answered(h, instances):
    good, bad = MagicMock(), MagicMock()
    good.ping.return_value = ("ok", 200)
    bad.ping.return_value = "Can't reach the instance"
    instances.Instance = MagicMock()
    instances.Instance.from_hostname.side_effect = lambda hostname, db: {"up": good, "down": bad}.get(hostname)

    body = h.client().post("/instances/ping", data={"instances": "up,down,ghost"}).get_json()

    assert body["succeed"] == ["up"]
    assert {failure["hostname"]: failure["message"] for failure in body["failed"]} == {
        "down": "Can't reach the instance",
        "ghost": "The instance ghost does not exist.",
    }


def test_instance_delete_only_removes_ui_and_api_instances(h, instances):
    h.db.get_instances.return_value = [{"hostname": "ui-one", "method": "ui"}, {"hostname": "auto", "method": "autoconf"}]
    h.db.delete_instances.return_value = ""
    client = h.client()

    client.post("/instances/delete", data={"instances": "ui-one,auto,ghost"})

    h.db.delete_instances.assert_called_once_with({"ui-one"})
    flashed = _flashed(h, client)
    assert "Instance auto is not a UI/API instance and will not be deleted." in flashed
    assert any("ui-one Deleted successfully" in message for message in flashed)


def test_instance_delete_with_nothing_deletable(h, instances):
    h.db.get_instances.return_value = [{"hostname": "auto", "method": "autoconf"}]
    client = h.client()

    client.post("/instances/delete", data={"instances": "auto"})

    h.db.delete_instances.assert_not_called()
    assert "Selected instance could not be found or is not a UI/API instance." in _flashed(h, client)


def test_instance_delete_database_error(h, instances):
    h.db.get_instances.return_value = [{"hostname": "a", "method": "ui"}]
    h.db.delete_instances.return_value = "locked"
    client = h.client()

    client.post("/instances/delete", data={"instances": "a"})

    assert "Couldn't delete the instance in the database: locked" in _flashed(h, client)


def test_instance_reload_runs_the_action_and_queues_the_result_message(h, instances):
    live = MagicMock()
    live.reload.return_value = "ok"
    broken = MagicMock()
    broken.reload.return_value = "Can't reload: refused"
    instances.Instance = MagicMock()
    instances.Instance.from_hostname.side_effect = lambda hostname, db: {"live": live, "broken": broken}.get(hostname)

    response = h.client().post("/instances/reload", data={"instances": "live,broken,ghost"})

    assert "message=Reloading+instances+live,+broken,+ghost" in response.headers["Location"]
    queued = {(item["content"], item["type"]) for item in h.data["TO_FLASH"]}
    assert ("Instance live Reloaded successfully.", "success") in queued
    assert ("Can't reload: refused", "error") in queued
    assert ("The instance ghost does not exist.", "error") in queued
    assert h.data["RELOADING"] is False


@pytest.mark.parametrize("action", ["reload", "stop", "delete", "ping"])
def test_instance_actions_in_read_only_mode(h, instances, action):
    h.db.readonly = True

    h.client().post(f"/instances/{action}", data={"instances": "a"})

    h.db.delete_instances.assert_not_called()
    h.instances.ban.assert_not_called()
    assert h.data["TO_FLASH"] == []
