"""``Templator.has_service_with`` — conditions that must hold on ONE service, not across the fleet.

Port of dev ``0af49ac8b``. ``has_variable`` answers each setting independently over the whole
fleet, so ANDing several of its calls is satisfied by two *different* services each meeting one
condition. The fleet-wide ACME challenge location is exactly that shape: it must render only when
some single service really is `AUTO_LETS_ENCRYPT=yes` **and** `LETS_ENCRYPT_CHALLENGE=http` **and**
`LETS_ENCRYPT_PASSTHROUGH=no` together (`core/letsencrypt/confs/default-server-http/lets-encrypt.conf`).

Get this wrong in the permissive direction and the challenge location renders for a fleet that
never uses http-01; get it wrong in the strict direction and HTTP-01 issuance stops working with
no error anywhere, which is why the mixed-service case below is the one that matters.
"""

import pytest
from Templator import Templator  # type: ignore  # tests/unit/gen/conftest.py puts src/common/gen on sys.path

# The real conditions the ACME template passes, so a change to their shape breaks this test too.
ACME = {"AUTO_LETS_ENCRYPT": "yes", "LETS_ENCRYPT_CHALLENGE": "http", "LETS_ENCRYPT_PASSTHROUGH": "no"}


def test_single_site_reads_the_global_values():
    assert Templator.has_service_with({"MULTISITE": "no", **ACME}, ACME) is True


def test_single_site_one_condition_off_is_a_non_match():
    config = {"MULTISITE": "no", **ACME, "LETS_ENCRYPT_CHALLENGE": "dns"}

    assert Templator.has_service_with(config, ACME) is False


def test_a_service_that_meets_every_condition_matches():
    config = {
        "MULTISITE": "yes",
        "SERVER_NAME": "a.example.com",
        "a.example.com_AUTO_LETS_ENCRYPT": "yes",
        "a.example.com_LETS_ENCRYPT_CHALLENGE": "http",
        "a.example.com_LETS_ENCRYPT_PASSTHROUGH": "no",
    }

    assert Templator.has_service_with(config, ACME) is True


def test_conditions_spread_over_two_services_are_not_a_match():
    """The whole reason the helper exists: this is what ANDing `has_variable` calls gets wrong.

    ``a`` wants Let's Encrypt but over DNS; ``b`` is on the http challenge but has Let's Encrypt
    off. Neither will ever answer an http-01 challenge, yet ``has_variable("AUTO_LETS_ENCRYPT",
    "yes") and has_variable("LETS_ENCRYPT_CHALLENGE", "http")`` is true, because each call finds
    its own service.
    """
    config = {
        "MULTISITE": "yes",
        "SERVER_NAME": "a.example.com b.example.com",
        "a.example.com_AUTO_LETS_ENCRYPT": "yes",
        "a.example.com_LETS_ENCRYPT_CHALLENGE": "dns",
        "a.example.com_LETS_ENCRYPT_PASSTHROUGH": "no",
        "b.example.com_AUTO_LETS_ENCRYPT": "no",
        "b.example.com_LETS_ENCRYPT_CHALLENGE": "http",
        "b.example.com_LETS_ENCRYPT_PASSTHROUGH": "no",
    }

    assert Templator.has_service_with(config, ACME) is False
    # Anti-vacuity: the old fleet-wide spelling DOES pass on this very config.
    assert all(Templator.has_variable(config, setting, value) for setting, value in ACME.items()) is True


def test_a_service_inherits_the_global_value_for_a_setting_it_does_not_override():
    """Only overridden settings are stored per service, so inheritance is the normal case."""
    config = {"MULTISITE": "yes", "SERVER_NAME": "a.example.com", **ACME}

    assert Templator.has_service_with(config, ACME) is True


def test_a_service_override_beats_the_inherited_global_value():
    config = {"MULTISITE": "yes", "SERVER_NAME": "a.example.com", **ACME, "a.example.com_LETS_ENCRYPT_PASSTHROUGH": "yes"}

    assert Templator.has_service_with(config, ACME) is False


@pytest.mark.parametrize("server_name", ["", "   "])
def test_a_multisite_fleet_with_no_service_never_matches(server_name):
    """Documented divergence from `has_variable`: the global values do not stand in for a service.

    A fleet with no service yet has nothing to issue a certificate for, so the fleet-wide location
    must not render on the strength of the defaults alone.
    """
    config = {"MULTISITE": "yes", "SERVER_NAME": server_name, **ACME}

    assert Templator.has_service_with(config, ACME) is False
    # ...whereas has_variable answers True here, which is what makes the distinction load-bearing.
    assert Templator.has_variable(config, "AUTO_LETS_ENCRYPT", "yes") is True


def test_the_default_server_pseudo_service_is_counted_like_any_other():
    """`default_server.py` puts `default-server` in SERVER_NAME, and `letsencrypt` is in its
    curated plugin subset, so its own settings must be able to satisfy the gate."""
    config = {
        "MULTISITE": "yes",
        "SERVER_NAME": "default-server",
        "default-server_AUTO_LETS_ENCRYPT": "yes",
        "default-server_LETS_ENCRYPT_CHALLENGE": "http",
        "default-server_LETS_ENCRYPT_PASSTHROUGH": "no",
    }

    assert Templator.has_service_with(config, ACME) is True
