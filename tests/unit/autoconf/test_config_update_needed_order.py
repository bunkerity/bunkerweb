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

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[3]
AUTOCONF = ROOT / "src" / "autoconf"


def _load_config():
    """Same loader as test_config.py, for the same reason.

    `Config.py` does a flat `from api_client import ApiUnavailableError`, and
    `src/scheduler/api_client.py` answers to that same bare name. Putting `src/autoconf` on
    `sys.path` to satisfy it leaks: whichever module pytest collects next and does a flat
    `from api_client import …` gets the autoconf file, which is an ImportError at *collection*
    and takes the whole `pytest tests/unit` run down with it. Stubbing the one name inside
    `patch.dict` needs no path at all, so there is nothing left to restore. (The rest of
    Config.py's flat imports -- common_utils, unit_parser, logger -- are already resolvable:
    tests/unit/conftest.py puts src/common/utils and src/common/api on sys.path for every run.)
    """
    api_client = ModuleType("api_client")
    api_client.ApiUnavailableError = RuntimeError
    with patch.dict(sys.modules, {"api_client": api_client}):
        spec = importlib.util.spec_from_file_location("bw_autoconf_config_order", AUTOCONF / "Config.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.Config


Config = _load_config()

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
INSTANCES = [{"hostname": "bw-1", "name": "bw-1", "port": 5000, "server_name": "bwapi"}]
INSTANCES_REORDERED = [{"server_name": "bwapi", "port": 5000, "hostname": "bw-1", "name": "bw-1"}]


@pytest.fixture
def config():
    cfg = Config("docker", api_client=object())
    cfg._Config__configs = STORED
    cfg._Config__services = SERVICES
    cfg._Config__instances = INSTANCES
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
    assert config.update_needed([dict(INSTANCES[0], port=5001)], SERVICES, STORED) is True


def test_update_needed_and_apply_compare_the_same_way():
    """The defect was the two disagreeing, not either one on its own."""
    source = (AUTOCONF / "Config.py").read_text(encoding="utf-8")
    for predicate in ("if self.__instances != instances:", "if self.__services != services:", "if self.__configs != configs:"):
        assert predicate in source
    for stored in ("if instances != self.__instances or first:", "if services != self.__services or first:", "if configs != self.__configs or first:"):
        assert stored in source
    # extra_config is a flat Dict[str, str]: set(map(str, items())) is genuinely equivalent to
    # `!=` there, and it is the one line of the four that keeps the idiom. Count CODE lines only --
    # the comment above the block names the idiom too, and counting raw occurrences would pass or
    # fail on how the comment is worded.
    idiom = [line.strip() for line in source.splitlines() if "set(map(str, " in line and not line.lstrip().startswith("#")]
    assert idiom == ["if set(map(str, self.__extra_config.items())) != set(map(str, extra_config.items())):"]
