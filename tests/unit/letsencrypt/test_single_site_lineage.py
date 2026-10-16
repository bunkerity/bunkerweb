"""Single-site mode: one certificate lineage per site, named after the first ``SERVER_NAME`` entry (dev 513ac59fe).

With ``MULTISITE=no`` the other ``SERVER_NAME`` entries are aliases of the one service. Once the
configuration reader keeps every entry (``db_methods/config_read.py``), the job used to treat each alias
as a service of its own and issued one lineage per entry, every one of them for ALL the names. Now the
first entry names the single lineage that covers them all, and multisite is unchanged.

Adding names to an existing certificate expands it in place instead of deleting it first, so a new name
that fails to validate keeps the certificate that is serving traffic. Removing or swapping a name still
reissues from scratch.
"""

import pytest
from test_certbot_new_readiness_gate import _load_definitions


@pytest.fixture
def module():
    return _load_definitions()


def acme_env(monkeypatch, **settings):
    for key, value in {"AUTO_LETS_ENCRYPT": "yes", "LETS_ENCRYPT_CHALLENGE": "http", "EMAIL_LETS_ENCRYPT": "admin@example.com", **settings}.items():
        monkeypatch.setenv(key, value)


def test_single_site_names_one_lineage_after_the_first_entry(module, monkeypatch):
    module.IS_MULTISITE = False
    acme_env(monkeypatch, SERVER_NAME="a.example b.example c.example")
    services = module.load_services("a.example b.example c.example")
    assert list(services) == ["a.example"]
    assert module.normalize_server_names(services["a.example"]["server_names"]) == {"a.example", "b.example", "c.example"}
    assert services["a.example"]["activated"] is True


def test_single_site_with_one_entry_is_unchanged(module, monkeypatch):
    module.IS_MULTISITE = False
    acme_env(monkeypatch, SERVER_NAME="a.example")
    assert list(module.load_services("a.example")) == ["a.example"]


def test_multisite_keeps_one_lineage_per_service(module, monkeypatch):
    """Guard: the first-entry rule is single-site only."""
    module.IS_MULTISITE = True
    acme_env(monkeypatch, MULTISITE="yes", SERVER_NAME="a.example b.example")
    monkeypatch.setenv("a.example_SERVER_NAME", "a.example www.a.example")
    monkeypatch.setenv("b.example_SERVER_NAME", "b.example")
    services = module.load_services("a.example b.example")
    assert list(services) == ["a.example", "b.example"]
    assert module.normalize_server_names(services["a.example"]["server_names"]) == {"a.example", "www.a.example"}
    assert module.normalize_server_names(services["b.example"]["server_names"]) == {"b.example"}


@pytest.mark.parametrize(
    "configured, existing, expected",
    [
        ({"example.com", "8.8.8.8"}, {"example.com"}, True),
        ({"example.com", "other.example"}, {"example.com"}, True),
        ({"a.example", "b.example", "c.example"}, {"a.example"}, True),
        ({"example.com"}, {"example.com", "other.example"}, False),
        ({"example.com", "new.example"}, {"example.com", "old.example"}, False),
        ({"example.com"}, {"example.com"}, False),
        ({"8.8.8.8"}, set(), False),
    ],
)
def test_names_added_expand_in_place_removed_or_swapped_names_reissue(module, configured, existing, expected):
    assert module.names_only_added(configured, existing) is expected
