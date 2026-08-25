"""The second lock on the per-service listen ports: the write path.

Two places refuse a prefixed write for a ``global`` setting, and they read the SAME
``bw_settings.context`` column:

* generation -- ``Configurator.py:390-391``, "context of X isn't multisite"; covered by the render
  tests in ``tests/unit/gen/test_per_service_ports.py``;
* every write -- ``is_valid_setting`` -> ``config_read.py:58-59``, "not multisite", reached from
  ``api/app/routers/services.py:97`` (``multisite=True``), ``IngressController.py:120``,
  ``config_save.py:366`` and ``templates.py:436``.

So one context flip opens both, and there is no hidden second chantier on the API/UI/autoconf side.
This file pins the second half, with the declaration read from ``settings.json`` rather than
invented, so flipping the context back turns it red.
"""

import json
import sys
from pathlib import Path

from fixtures.seed import add_global_value, add_service, add_service_setting, add_setting, seed_minimal

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "src" / "common" / "utils"))


def _declaration(setting_id):
    return json.loads((_REPO_ROOT / "src" / "common" / "settings.json").read_text())[setting_id]


def _seed_port_setting(db, setting_id):
    """Seed the real declaration of a port setting: its context, regex and ``multiple`` group."""
    declared = _declaration(setting_id)
    add_setting(
        db,
        setting_id,
        context=declared["context"],
        type=declared["type"],
        regex=declared["regex"],
        multiple=declared["multiple"],
        default=declared["default"],
    )
    return declared


class TestPrefixedPortWrites:
    def test_a_service_prefixed_port_is_accepted(self, db):
        seed_minimal(db)
        _seed_port_setting(db, "HTTP_PORT")
        assert db.is_valid_setting("app1.example.com_HTTP_PORT", value="9080", multisite=True) == (True, "")

    def test_a_service_prefixed_repetition_is_accepted(self, db):
        """``_N`` resolution and the service prefix have to compose: ``config_read.py:36-38``
        strips the suffix, the prefix is resolved against the known services."""
        seed_minimal(db)
        _seed_port_setting(db, "HTTPS_PORT")
        assert db.is_valid_setting("app1.example.com_HTTPS_PORT_1", value="9444", multisite=True) == (True, "")

    def test_an_out_of_range_port_is_still_refused(self, db):
        """The flip must not become a way in for a value the regex exists to stop. 99999 used to
        pass: the declaration said ``^\\d*$``."""
        seed_minimal(db)
        _seed_port_setting(db, "HTTP_PORT")
        ok, message = db.is_valid_setting("app1.example.com_HTTP_PORT", value="99999", multisite=True)
        assert ok is False
        assert "not matching regex" in message

    def test_an_empty_port_is_accepted_because_it_disables_listening(self, db):
        """``settings.json:23`` documents the empty value; the write path must keep allowing it or
        the documented way to disable HTTP listening becomes unreachable through the API."""
        seed_minimal(db)
        _seed_port_setting(db, "HTTP_PORT")
        assert db.is_valid_setting("app1.example.com_HTTP_PORT", value="", multisite=True) == (True, "")

    def test_a_global_write_still_works_and_stays_the_fleet_default(self, db):
        """A multisite setting accepts a global value, which becomes every service's default
        (``Configurator.py:344-360``) -- that is what makes the flip a no-op for existing installs."""
        seed_minimal(db)
        _seed_port_setting(db, "HTTP_PORT")
        assert db.is_valid_setting("HTTP_PORT", value="8080") == (True, "")

    def test_the_stream_ports_were_already_multisite(self, db):
        """Stated as the prior art the flip copies: this is exactly what HTTP/HTTPS now do."""
        seed_minimal(db)
        _seed_port_setting(db, "LISTEN_STREAM_PORT")
        assert db.is_valid_setting("app1.example.com_LISTEN_STREAM_PORT", value="2337", multisite=True) == (True, "")


class TestTheNonDefaultViewOnlyReportsRealDeclarations:
    """``get_non_default_settings`` is the ONLY thing that can say "this service declared a port".

    A service REPLACES the global port list rather than extending it, and the renderer decides that
    by asking whether the key is present in the NON-default view
    (``Templator._get_server_config`` -> ``ports.drop_inherited_ports``). ``config_read.py``
    materialises an inherited copy of every multisite setting under every service name, which is
    what the per-service editor needs -- and which, applied to the port lists, made every service
    look like it had declared the whole global list.
    """

    def _multisite_fleet(self, db, global_ports):
        seed_minimal(db)
        _seed_port_setting(db, "HTTP_PORT")
        add_service(db, "app2.example.com")
        add_global_value(db, setting_id="MULTISITE", value="yes")
        for suffix, value in enumerate(global_ports):
            add_global_value(db, setting_id="HTTP_PORT", value=value, suffix=suffix)

    def test_a_service_that_declared_nothing_gets_no_port_key_at_all(self, db):
        self._multisite_fleet(db, ["8080", "8081"])
        config = db.get_non_default_settings(methods=True, with_drafts=True)
        assert "app1.example.com_HTTP_PORT" not in config
        assert "app1.example.com_HTTP_PORT_1" not in config

    def test_a_service_that_declared_one_member_gets_that_member_alone(self, db):
        """The exact shape the render bug needed: the declared ``HTTP_PORT`` row is reported, the
        global ``HTTP_PORT_1`` is NOT copied under the service, so the replacement rule sees one
        declared member and drops the inherited repetition instead of keeping 8081 alive."""
        self._multisite_fleet(db, ["8080", "8081"])
        add_service_setting(db, service_id="app1.example.com", setting_id="HTTP_PORT", value="9000")
        config = db.get_non_default_settings(methods=True, with_drafts=True)
        assert config["app1.example.com_HTTP_PORT"]["value"] == "9000"
        assert "app1.example.com_HTTP_PORT_1" not in config
        # ...and the sibling that declared nothing still has neither.
        assert not [key for key in config if key.startswith("app2.example.com_HTTP_PORT")]

    def test_every_other_multisite_setting_still_gets_its_inherited_copy(self, db):
        """The skip is port-specific. Removing the materialisation wholesale would change what
        every consumer of this view reads for every other multisite setting."""
        self._multisite_fleet(db, ["8080"])
        add_global_value(db, setting_id="USE_REVERSE_PROXY", value="yes")
        config = db.get_non_default_settings(methods=True, with_drafts=True)
        assert config["app1.example.com_USE_REVERSE_PROXY"]["value"] == "yes"

    def test_the_full_view_keeps_the_inherited_copies(self, db):
        """``get_config`` strips the ``<service>_`` prefix on the way out, so the per-service editor
        would lose the port settings entirely if the copies went with them. Its consumers merge the
        globals themselves, so the inherited view is the right one there."""
        self._multisite_fleet(db, ["8080", "8081"])
        config = db.get_config(methods=True, with_drafts=True)
        assert config["app1.example.com_HTTP_PORT"]["value"] == "8080"
        assert config["app1.example.com_HTTP_PORT_1"]["value"] == "8081"


class TestThePortListComesBackInSuffixOrder:
    """``Settings.order`` carries the same value for every repetition of one ``multiple`` setting,
    so it cannot decide between ``HTTP_PORT`` and ``HTTP_PORT_1``: without a ``suffix`` tiebreak the
    relative position of the two in the returned dict is whatever the engine gives back.

    That order is not cosmetic. ``ports.collect_ports`` / ``list_moved`` compare ORDERED sequences,
    and the per-service templates render their ``listen`` lines straight from the dict — so the same
    database could answer differently on PostgreSQL than on SQLite, and a service could be judged
    "moved" for having its keys read back in another order.
    """

    def _fleet(self, db, rows):
        seed_minimal(db)
        _seed_port_setting(db, "HTTP_PORT")
        add_global_value(db, setting_id="MULTISITE", value="yes")
        for suffix, value in rows:
            add_global_value(db, setting_id="HTTP_PORT", value=value, suffix=suffix)

    def _ports(self, config):
        return [value["value"] for key, value in config.items() if key.startswith("HTTP_PORT")]

    def test_the_base_comes_first_even_when_the_repetition_was_inserted_first(self, db):
        # Rows written repetition-first, which is what an operator adding a second port to an
        # already-default fleet produces.
        self._fleet(db, [(1, "8081"), (0, "8080")])
        assert self._ports(db.get_non_default_settings(methods=True, with_drafts=True)) == ["8080", "8081"]

    def test_the_same_holds_for_the_per_service_rows(self, db):
        self._fleet(db, [(0, "8080")])
        add_service_setting(db, service_id="app1.example.com", setting_id="HTTP_PORT", value="9081", suffix=1)
        add_service_setting(db, service_id="app1.example.com", setting_id="HTTP_PORT", value="9080", suffix=0)
        config = db.get_non_default_settings(methods=True, with_drafts=True)
        service_ports = [value["value"] for key, value in config.items() if key.startswith("app1.example.com_HTTP_PORT")]
        assert service_ports == ["9080", "9081"]
