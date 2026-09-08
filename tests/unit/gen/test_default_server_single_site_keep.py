"""A single-site deployment whose own service is called ``default-server`` still gets a server block.

The reserved pseudo-service is a MULTISITE-only feature, so under ``MULTISITE=no`` the id is not
reserved *in the database*: ``config_read``'s roster strip is method-aware on purpose
(``db_methods/config_read.py``, ``row.method == DEFAULT_SERVER_METHOD``) and keeps a row that is not
the seeded reserved one. ``Templator.__init__``'s single-site strip used to be method-BLIND, so it
emptied ``SERVER_NAME`` behind that guard and rendered zero server blocks: the whole deployment
served nothing, with one log line as the only signal.

This is the path no other test drives. Everything in ``test_default_server_multisite_only.py`` that
reaches the database goes through the SEEDED row, whose method is the reserved ``wizard`` -- exactly
the row ``config_read`` does strip -- and the two tests that reach the Templator strip at all go
through ``Configurator`` from raw variables. ``render_db_tree`` renders the way the SCHEDULER does
(``push-configs.py`` calls ``gen/main.py`` with no ``--variables``, so ``config`` is
``db.get_non_default_settings()`` and ``full_config``/``default_config`` come from
``db.get_config(methods=True)`` -- ``conftest.py:88-95``), and its ``MULTISITE=yes`` is the LEFT
operand of a ``|`` merge, so ``globals_`` turns it off like any other setting.

The row's method here is the fixture's ``scheduler``, which is what a `SERVER_NAME=default-server`
environment produces, and it is as non-reserved as the ``ui`` a UI/API create would write: the guard
under test keys on ``method == "wizard"``, nothing narrower. Asserted rather than assumed below.
"""

import logging

import pytest

from default_server import DEFAULT_SERVER_ID, DEFAULT_SERVER_METHOD  # type: ignore

pytestmark = pytest.mark.slow

SERVICE = "app1.example.com"


class TestASingleSiteServiceNamedLikeTheReservedId:
    def test_its_server_block_is_still_rendered(self, db, render_db_tree, caplog):
        """The outage this lane exists to close: `config_read` keeps a non-`wizard` row, so a strip
        that drops the id here leaves `SERVER_NAME` EMPTY and the deployment answers nothing."""
        with caplog.at_level(logging.WARNING):
            tree = render_db_tree({"MULTISITE": "no", "SERVER_NAME": DEFAULT_SERVER_ID}, {})

        # The premise: the row exists, it is NOT the reserved one, and the roster kept it. Asserted
        # rather than assumed -- if a future guard erased the row instead, the render below would be
        # "correct" for the wrong reason and this test would go on passing.
        rows = {service["id"]: service["method"] for service in db.get_services(with_drafts=True)}
        assert list(rows) == [DEFAULT_SERVER_ID] and rows[DEFAULT_SERVER_ID] != DEFAULT_SERVER_METHOD
        assert db.get_config()["SERVER_NAME"] == DEFAULT_SERVER_ID

        server_conf = next(content for path, content in tree.items() if path.endswith("server.conf"))
        assert f"server_name {DEFAULT_SERVER_ID};" in server_conf
        # The other half of the outage, and the shape the reproduction printed: an emptied
        # SERVER_NAME reached `variables.env` as `SERVER_NAME=` too, so the Lua side agreed with the
        # missing block instead of contradicting it.
        assert f"SERVER_NAME={DEFAULT_SERVER_ID}\n" in tree["variables.env"]

    def test_the_keep_is_warned_with_the_recovery(self, render_db_tree, caplog):
        """Keeping the name is the safe half; the operator still has to be told the id is reserved,
        or the collision only shows up the day they turn MULTISITE on."""
        with caplog.at_level(logging.WARNING):
            render_db_tree({"MULTISITE": "no", "SERVER_NAME": DEFAULT_SERVER_ID}, {})

        kept = [record.getMessage() for record in caplog.records if DEFAULT_SERVER_ID in record.getMessage() and "is KEPT" in record.getMessage()]
        assert kept, [record.getMessage() for record in caplog.records]
        assert "rename" in kept[0].lower()

    def test_no_stream_default_server_listener_is_opened(self, render_db_tree):
        """`_service_configs()` keys on SERVER_NAME, so now that the name is KEPT the reserved id is
        a real key again and a GLOBAL `DEFAULT_SERVER_STREAM_PORTS` would be read as if it were the
        reserved service's own. The election is gated on MULTISITE for that reason."""
        tree = render_db_tree({"MULTISITE": "no", "SERVER_NAME": DEFAULT_SERVER_ID, "DEFAULT_SERVER_STREAM_PORTS": "9001"}, {})
        assert "9001" not in tree["stream.conf"]

    def test_multisite_still_elects_it_on_the_database_path(self, render_db_tree):
        """The control for the gate above, and it has to be on the DATABASE path: the gate reads
        `MULTISITE` out of `db.get_non_default_settings()`, and if a multisite deployment did not
        carry it there the gate would silently take the stream default server away from every
        multisite install. The other stream tests all go through `Configurator`, which is handed
        `MULTISITE` verbatim and so cannot see that difference."""
        tree = render_db_tree({"MULTISITE": "yes"}, {SERVICE: {}, DEFAULT_SERVER_ID: {"DEFAULT_SERVER_STREAM_PORTS": "9001"}})
        assert "9001" in tree["stream.conf"] and "default_server" in tree["stream.conf"]


class TestTheSeededReservedRowIsTheOnlySingleSiteName:
    """The other half of the same rule, and the one the CI red came from (DS-B6).

    The class above covers the row an OPERATOR owns (method ``scheduler``/``ui``), which
    ``config_read`` keeps. This one covers the SEEDED row -- method ``wizard`` -- which
    ``config_read`` strips, and which a single-site deployment can perfectly well be left holding:
    the API's lifespan seeds it on a fresh install *before* ``MULTISITE`` is knowable
    (``test_default_server_multisite_gate.py::test_a_fresh_install_seeds_before_multisite_is_knowable``),
    so every fresh install has it, whatever it turns out to be.

    On such a deployment ``SERVER_NAME=default-server`` leaves the reserved row as the ONLY roster
    entry, and the strip emptied it: ``get_non_default_settings()["SERVER_NAME"] == ""``, which the
    scheduler feeds straight to ``gen/main.py``. Zero server blocks, ``SERVER_NAME=`` in
    ``variables.env``, and the instance answering nothing -- with ``customcert:init()`` raising
    ``attempt to concatenate a nil value`` on the way past.
    """

    def test_the_roster_keeps_the_reserved_row_when_it_is_alone(self, db, render_db_tree):
        assert db.seed_default_server_service() == ""
        tree = render_db_tree({"MULTISITE": "no", "SERVER_NAME": DEFAULT_SERVER_ID}, {})

        # The premise: this time the row IS the reserved one -- the row the strip exists for.
        rows = {service["id"]: service["method"] for service in db.get_services(with_drafts=True)}
        assert rows == {DEFAULT_SERVER_ID: DEFAULT_SERVER_METHOD}
        # Both readers: `gen/main.py` takes `config` from the first and `full_config` from the second.
        assert db.get_non_default_settings()["SERVER_NAME"] == DEFAULT_SERVER_ID
        assert db.get_config()["SERVER_NAME"] == DEFAULT_SERVER_ID

        server_conf = next(content for path, content in tree.items() if path.endswith("server.conf"))
        assert f"server_name {DEFAULT_SERVER_ID};" in server_conf
        assert f"SERVER_NAME={DEFAULT_SERVER_ID}\n" in tree["variables.env"]

    def test_the_strip_still_fires_when_a_real_service_remains(self, db, render_db_tree):
        """The control: keeping the id when it is alone must not turn the strip off. This is the
        shape the sibling integration case drives (`SERVER_NAME: "default-server www.example.com"`),
        reproduced with the rows that make it single-site AND multi-row -- a deployment that was
        multisite once, which is the only way a single-site roster holds two rows at all."""
        render_db_tree({"MULTISITE": "yes"}, {SERVICE: {}})
        assert db.get_services(with_drafts=True)  # the multisite pass seeded the reserved row

        tree = render_db_tree({"MULTISITE": "no", "SERVER_NAME": f"{DEFAULT_SERVER_ID} {SERVICE}"}, {SERVICE: {}})
        rows = {service["id"]: service["method"] for service in db.get_services(with_drafts=True)}
        assert rows == {DEFAULT_SERVER_ID: DEFAULT_SERVER_METHOD, SERVICE: "scheduler"}

        assert db.get_non_default_settings()["SERVER_NAME"] == SERVICE
        server_conf = next(content for path, content in tree.items() if path.endswith("server.conf"))
        assert f"server_name {SERVICE};" in server_conf
        assert f"SERVER_NAME={SERVICE}\n" in tree["variables.env"]

    def test_a_multisite_roster_of_one_still_drops_it(self, db, render_db_tree):
        """The keep is single-site only. In multisite the reserved row renders into the default
        server block and never gets a `server{}` of its own, so a roster that holds nothing else
        legitimately renders no service block -- keeping it there would render one."""
        tree = render_db_tree({"MULTISITE": "yes"}, {})
        rows = {service["id"]: service["method"] for service in db.get_services(with_drafts=True)}
        assert rows == {DEFAULT_SERVER_ID: DEFAULT_SERVER_METHOD}
        assert not [path for path in tree if path.endswith("server.conf")]
