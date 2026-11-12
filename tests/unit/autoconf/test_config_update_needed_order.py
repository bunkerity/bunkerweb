"""`update_needed` must agree with `apply()` about what "changed" means.

Both look at the same three values -- instances, services, custom configs -- a few lines apart.
`apply()` compares each with `!=`; `update_needed` compared them with `set(map(str, …))`, and
`str()` of a dict follows its INSERTION order. The same services or the same custom configs,
rebuilt from a labels dict the daemon serialised in another order, therefore read as a change.

That difference never converges, which is what makes it a loop rather than a hiccup: `apply()` is
what stores the new value, so when it compares by value, finds no change and declines to store,
`self.__instances` / `__services` / `__configs` keep the OLD content and the next poll reports the
identical difference again. On the Autoconf arm of run 32508782608 the controller re-applied every
~20 s for the whole 400 s the harness waited for the stack to go quiet -- 590 job completions, 36
of them push-configs -- and `wait_config` timed out because it never saw 5 consecutive quiet
seconds.

The second half of the chain -- an empty `changes` list being read as "everything changed" -- is
covered in test_config.py, next to the apply() fixture that already produces it.
"""

import pytest

from Config import Config

# What the autoconf-configs example produces: one server-http config per service.
STORED = {
    "http": {},
    "server-http": {
        "app1.example.com/example.conf": b"location /hello { return 200 'app1'; }",
        "app2.example.com/example.conf": b"location /hello { return 200 'app2'; }",
        "app3.example.com/example.conf": b"location /hello { return 200 'app3'; }",
    },
}
REORDERED = {
    "http": {},
    "server-http": {
        "app3.example.com/example.conf": STORED["server-http"]["app3.example.com/example.conf"],
        "app1.example.com/example.conf": STORED["server-http"]["app1.example.com/example.conf"],
        "app2.example.com/example.conf": STORED["server-http"]["app2.example.com/example.conf"],
    },
}

# What DockerController._to_services builds: one dict per service, keys in whatever order the
# daemon serialised the container's labels.
SERVICES = [{"SERVER_NAME": "app1.example.com", "USE_ANTIBOT": "no", "REVERSE_PROXY_HOST": "http://app1:8080"}]
SERVICES_REORDERED = [{"REVERSE_PROXY_HOST": "http://app1:8080", "SERVER_NAME": "app1.example.com", "USE_ANTIBOT": "no"}]
INSTANCES = [{"hostname": "bw-1", "name": "bw-1", "env": {"API_HTTP_PORT": "5000", "API_SERVER_NAME": "bwapi"}}]
INSTANCES_REORDERED = [{"env": {"API_SERVER_NAME": "bwapi", "API_HTTP_PORT": "5000"}, "hostname": "bw-1", "name": "bw-1"}]


@pytest.fixture
def config(fake_db):
    cfg = Config("docker")
    assert cfg.apply(INSTANCES, SERVICES, configs=STORED, first=True)
    fake_db.checked.clear()
    fake_db.saved_instances.clear()
    fake_db.saved_configs.clear()
    fake_db.saved_custom_configs.clear()
    return cfg


def test_the_premise_holds():
    """If these ever stop being equal the tests below prove nothing."""
    for stored, reordered in ((STORED, REORDERED), (SERVICES[0], SERVICES_REORDERED[0]), (INSTANCES[0], INSTANCES_REORDERED[0])):
        assert stored == reordered
    assert list(STORED["server-http"]) != list(REORDERED["server-http"])
    assert list(SERVICES[0]) != list(SERVICES_REORDERED[0])
    assert list(INSTANCES[0]) != list(INSTANCES_REORDERED[0])
    # …and that the string form, which is what the old code compared, really does differ.
    assert str(SERVICES[0]) != str(SERVICES_REORDERED[0])


def test_the_same_configs_in_another_order_are_not_a_change(config):
    assert config.update_needed(INSTANCES, SERVICES, REORDERED) is False


def test_the_same_services_in_another_order_are_not_a_change(config):
    assert config.update_needed(INSTANCES, SERVICES_REORDERED, STORED) is False


def test_the_same_instances_in_another_order_are_not_a_change(config):
    assert config.update_needed(INSTANCES_REORDERED, SERVICES, STORED) is False


def test_a_real_change_is_still_a_change(config):
    changed = {"http": {}, "server-http": dict(STORED["server-http"], **{"app2.example.com/example.conf": b"different"})}
    assert config.update_needed(INSTANCES, SERVICES, changed) is True


def test_a_removed_config_is_still_a_change(config):
    fewer = {"http": {}, "server-http": {k: v for k, v in STORED["server-http"].items() if not k.startswith("app3")}}
    assert config.update_needed(INSTANCES, SERVICES, fewer) is True


def test_a_real_service_change_is_still_a_change(config):
    assert config.update_needed(INSTANCES, [dict(SERVICES[0], USE_ANTIBOT="captcha")], STORED) is True


def test_a_real_instance_change_is_still_a_change(config):
    changed = [dict(INSTANCES[0], env={"API_HTTP_PORT": "5001", "API_SERVER_NAME": "bwapi"})]
    assert config.update_needed(changed, SERVICES, STORED) is True


def test_update_needed_and_apply_compare_the_same_way(config, fake_db):
    """The defect was the two disagreeing, not either one on its own."""
    for instances, services, configs in ((INSTANCES_REORDERED, SERVICES, STORED), (INSTANCES, SERVICES_REORDERED, STORED), (INSTANCES, SERVICES, REORDERED)):
        assert config.update_needed(instances, services, configs) is False
        assert config.apply(instances, services, configs=configs)
    assert fake_db.checked == []
    assert fake_db.saved_instances == []
    assert fake_db.saved_configs == []
    assert fake_db.saved_custom_configs == []


def test_extra_config_in_another_order_is_not_published(config, fake_db):
    assert config.apply(INSTANCES, SERVICES, configs=STORED, extra_config={"SECURITY_MODE": "block", "USE_ANTIBOT": "captcha"})
    assert fake_db.checked == [["extra_config", "config"]]
    fake_db.checked.clear()
    fake_db.saved_configs.clear()
    reordered = {"USE_ANTIBOT": "captcha", "SECURITY_MODE": "block"}

    assert config.update_needed(INSTANCES, SERVICES, STORED, reordered) is False
    assert config.apply(INSTANCES, SERVICES, configs=STORED, extra_config=reordered)
    assert fake_db.checked == []
    assert fake_db.saved_configs == []
