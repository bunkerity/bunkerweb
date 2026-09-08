"""The reserved ``default-server`` row is MULTISITE-ONLY, and it is seeded from two places.

PO ruling of 2026-09-06. Everything that gives the reserved row meaning is gated on
``MULTISITE=yes``: ``config_read`` materialises ``<service>_<SETTING>`` keys only there, and
``helpers.lua`` builds the per-site ``variables`` tables only there. A row on a single-site
deployment would therefore be a page whose every setting silently resolves to the globals -- and it
would put the reserved id in that deployment's ``SERVER_NAME``, which non-multisite renders verbatim
into one ``server_name`` directive.

The gate cannot be "MULTISITE != yes -> skip" alone, and that is what most of this file is about.
``config_save`` never stores a global value equal to its default and MULTISITE defaults to ``no``,
so an ABSENT value means either "single-site" or "the configuration has never been written" -- and
the second is the normal state when the API's lifespan runs on a fresh install (the scheduler's
entrypoint pre-initialises the database and exits before writing any global value, and
``is_initialized`` is the only thing the API's pre-fork hook waits for). Reading that as
"single-site" would skip the seeding on every fresh multisite install, permanently, because the
lifespan runs once per API boot.
"""

import pytest

from default_server import DEFAULT_SERVER_ID, DEFAULT_SERVER_METHOD, strip_default_server_unless_alone  # type: ignore
from fixtures.seed import make_core_plugin, make_general_settings

pytestmark = pytest.mark.slow


class _Recorder:
    """Stand-in for ``Database.logger``: the INFO skip line and the ERROR collision line are the
    only thing the operator ever sees of either decision, so they are asserted, not assumed."""

    def __init__(self):
        self.records = []

    def _record(self, level):
        def _log(message, *args, **kwargs):
            self.records.append((level, str(message)))

        return _log

    def __getattr__(self, name):
        return self._record(name)


@pytest.fixture
def fresh(db):
    """A database that has been initialised and has NEVER saved a configuration.

    `metadata.first_config_saved` is False here -- the state the API lifespan finds on a fresh
    install, whatever MULTISITE will turn out to be.
    """
    # IS_DRAFT has to exist in `bw_settings` for a save to carry `<service>_IS_DRAFT`, which is how
    # the drafting half of the recovery is exercised below.
    schema = make_general_settings() | {
        "IS_DRAFT": {"id": "is-draft", "context": "multisite", "default": "no", "help": "h", "label": "D", "regex": "^(yes|no)$", "type": "check"}
    }
    db.init_tables([schema, make_core_plugin("alpha")])
    db.initialize_db("1.7.0", "Docker")
    return db


def _ids(database):
    return {service["id"] for service in database.get_services(with_drafts=True)}


def _methods(database):
    return {service["id"]: service["method"] for service in database.get_services(with_drafts=True)}


class TestTheGateIsThreeValued:
    def test_a_fresh_install_seeds_before_multisite_is_knowable(self, fresh):
        """MULTISITE is unreadable at this point and the row is created anyway.

        The alternative -- reading "absent" as "single-site" -- skips the seeding on every fresh
        MULTISITE=yes install, and the lifespan never runs again.
        """
        assert fresh.get_metadata()["first_config_saved"] is False
        assert fresh.seed_default_server_service() == ""
        assert DEFAULT_SERVER_ID in _ids(fresh)

    def test_a_fresh_single_site_install_seeds_a_row_that_is_invisible(self, fresh):
        """The cost of the branch above, and the reason it is acceptable: on a deployment that
        turns out to be single-site the row exists and reaches nothing.

        The roster is the load-bearing half -- `SERVER_NAME` is what every template, the Lua
        per-site tables and `Templator.render` build from.
        """
        fresh.seed_default_server_service()
        fresh.save_config({"MULTISITE": "no", "SERVER_NAME": "app1.example.com", "app1.example.com_SERVER_NAME": "app1.example.com"}, "scheduler")

        assert DEFAULT_SERVER_ID in _ids(fresh)
        assert fresh.get_config()["SERVER_NAME"].split() == ["app1.example.com"]

    def test_an_upgraded_single_site_database_is_skipped_with_one_info_line(self, fresh):
        """The state the ruling is actually about: a real single-site deployment, upgrading."""
        fresh.save_config({"MULTISITE": "no", "SERVER_NAME": "app1.example.com", "app1.example.com_SERVER_NAME": "app1.example.com"}, "scheduler")
        assert fresh.get_metadata()["first_config_saved"] is True
        assert DEFAULT_SERVER_ID not in _ids(fresh)

        recorder = _Recorder()
        fresh.logger = recorder
        assert fresh.seed_default_server_service() == ""

        assert DEFAULT_SERVER_ID not in _ids(fresh)
        assert [message for level, message in recorder.records if level == "info" and "MULTISITE is not enabled" in message]

    def test_an_upgraded_multisite_database_is_seeded(self, fresh):
        fresh.save_config({"MULTISITE": "yes", "SERVER_NAME": "app1.example.com", "app1.example.com_SERVER_NAME": "app1.example.com"}, "scheduler")
        # The save itself is the second trigger, so the row is already there -- and a second call
        # changes nothing.
        assert DEFAULT_SERVER_ID in _ids(fresh)
        assert fresh.seed_default_server_service() == ""
        assert len([sid for sid in _ids(fresh) if sid == DEFAULT_SERVER_ID]) == 1


class TestTheRosterStripIsNotBranchShaped:
    """The regression the in-lane Criticos pass caught, and the reason this class exists at all.

    The strip was first written in the `else:` of `if not global_only and is_multisite:`
    (`db_methods/config_read.py`) on the assumption that the `else` IS the non-multisite branch. It
    is not: a `global_only=True` read lands there in EVERY mode -- and that is exactly the shape the
    web UI's service-exists check uses (`ui/app/routes/services.py` ->
    `models/config.py::get_services` -> `GET /global_settings?global_only=true`), so on a MULTISITE
    deployment `/services/default-server` redirected straight back to the services list and the whole
    Default server page was dead.

    The second trap is that `is_multisite` cannot be re-read from `config` there either:
    `config_read` tops `filtered_settings` up with MULTISITE only when `global_only` is False, so on
    the very call above it is False whatever the deployment.
    """

    @pytest.fixture
    def multisite(self, fresh):
        fresh.save_config({"MULTISITE": "yes", "SERVER_NAME": "app1.example.com", "app1.example.com_SERVER_NAME": "app1.example.com"}, "scheduler")
        assert DEFAULT_SERVER_ID in _ids(fresh)
        return fresh

    @pytest.mark.parametrize("filtered", (None, ("SERVER_NAME",)))
    def test_a_global_only_read_keeps_the_id_in_multisite(self, multisite, filtered):
        for reader in (multisite.get_config, multisite.get_non_default_settings):
            roster = reader(global_only=True, methods=False, filtered_settings=filtered)["SERVER_NAME"].split()
            assert DEFAULT_SERVER_ID in roster, (reader.__name__, filtered)

    @pytest.mark.parametrize("filtered", (None, ("SERVER_NAME",)))
    def test_a_global_only_read_drops_the_id_in_single_site(self, multisite, filtered):
        multisite.save_config({"MULTISITE": "no", "SERVER_NAME": "app1.example.com", "app1.example.com_SERVER_NAME": "app1.example.com"}, "scheduler")
        for reader in (multisite.get_config, multisite.get_non_default_settings):
            roster = reader(global_only=True, methods=False, filtered_settings=filtered)["SERVER_NAME"].split()
            assert DEFAULT_SERVER_ID not in roster, (reader.__name__, filtered)
            assert roster == ["app1.example.com"]

    def test_a_foreign_row_survives_a_global_only_single_site_read(self, fresh):
        """An operator's own service named `default-server` is a real service: stripping it from a
        single-site roster would erase the only row a `SERVER_NAME=default-server` deployment has."""
        fresh.save_config({"MULTISITE": "no", "SERVER_NAME": DEFAULT_SERVER_ID, f"{DEFAULT_SERVER_ID}_SERVER_NAME": DEFAULT_SERVER_ID}, "ui")
        assert _methods(fresh)[DEFAULT_SERVER_ID] == "ui"

        assert fresh.get_config(global_only=True, methods=False, filtered_settings=("SERVER_NAME",))["SERVER_NAME"] == DEFAULT_SERVER_ID


class TestTheSecondTrigger:
    def test_turning_multisite_on_seeds_without_restarting_the_api(self, fresh):
        """The hole the lifespan alone leaves open: an operator flips MULTISITE from the global
        settings page years after the install, and nothing restarts the API."""
        fresh.save_config({"MULTISITE": "no", "SERVER_NAME": "app1.example.com", "app1.example.com_SERVER_NAME": "app1.example.com"}, "scheduler")
        assert fresh.seed_default_server_service() == ""
        assert DEFAULT_SERVER_ID not in _ids(fresh)

        fresh.save_config({"MULTISITE": "yes", "SERVER_NAME": "app1.example.com", "app1.example.com_SERVER_NAME": "app1.example.com"}, "scheduler")

        assert DEFAULT_SERVER_ID in _ids(fresh)
        assert _methods(fresh)[DEFAULT_SERVER_ID] == DEFAULT_SERVER_METHOD

    def test_the_flip_back_does_not_delete_the_row(self, fresh):
        """Deliberate: the seeding is the only thing gated, never a deletion. An operator who turns
        multisite off and on again keeps every setting they put on the default server page."""
        fresh.save_config({"MULTISITE": "yes", "SERVER_NAME": "app1.example.com", "app1.example.com_SERVER_NAME": "app1.example.com"}, "scheduler")
        assert DEFAULT_SERVER_ID in _ids(fresh)

        fresh.save_config({"MULTISITE": "no", "SERVER_NAME": "app1.example.com", "app1.example.com_SERVER_NAME": "app1.example.com"}, "scheduler")

        assert DEFAULT_SERVER_ID in _ids(fresh)
        # ... and it is out of the roster while multisite is off, which is what keeps it inert.
        assert DEFAULT_SERVER_ID not in fresh.get_config()["SERVER_NAME"].split()


class TestAForeignRowIsNotAdopted:
    """Finding A of the independent Criticos pass on DS-B: a service an operator created under the
    reserved name, before 1.7 reserved it. Adopting it would hand their service to the default
    server; refusing it silently would leave them with a site that renders no `server{}` block
    (`http.conf` drops the id by name, whatever the method) and no supported way out."""

    @pytest.fixture
    def foreign(self, fresh):
        fresh.save_config(
            {
                "MULTISITE": "yes",
                "SERVER_NAME": f"app1.example.com {DEFAULT_SERVER_ID}",
                "app1.example.com_SERVER_NAME": "app1.example.com",
                f"{DEFAULT_SERVER_ID}_SERVER_NAME": DEFAULT_SERVER_ID,
            },
            "ui",
        )
        assert _methods(fresh)[DEFAULT_SERVER_ID] == "ui"
        return fresh

    def test_the_seeding_leaves_the_method_alone_and_says_so(self, foreign):
        recorder = _Recorder()
        foreign.logger = recorder

        assert foreign.seed_default_server_service() == ""

        assert _methods(foreign)[DEFAULT_SERVER_ID] == "ui"
        errors = [message for level, message in recorder.records if level == "error"]
        assert errors, recorder.records
        assert DEFAULT_SERVER_ID in errors[0]
        assert "'ui'" in errors[0]
        # The recovery, not just the complaint.
        assert "Rename it" in errors[0]

    def test_a_foreign_row_stays_deletable(self, foreign):
        assert foreign.delete_services([DEFAULT_SERVER_ID]) == ""
        assert DEFAULT_SERVER_ID not in _ids(foreign)


class TestDeleteServicesRefusesTheReservedRow:
    """Finding B. Both production callers refuse it before they get here, but this is the method
    that bypasses every method check, so the invariant is stated where it cannot be walked into."""

    def test_the_reserved_row_is_refused(self, fresh):
        fresh.save_config({"MULTISITE": "yes", "SERVER_NAME": "app1.example.com", "app1.example.com_SERVER_NAME": "app1.example.com"}, "scheduler")
        assert DEFAULT_SERVER_ID in _ids(fresh)

        error = fresh.delete_services([DEFAULT_SERVER_ID])

        assert "reserved default server" in error
        assert DEFAULT_SERVER_ID in _ids(fresh)

    def test_a_bulk_delete_carrying_it_takes_nothing_with_it(self, fresh):
        fresh.save_config({"MULTISITE": "yes", "SERVER_NAME": "app1.example.com", "app1.example.com_SERVER_NAME": "app1.example.com"}, "scheduler")

        error = fresh.delete_services(["app1.example.com", DEFAULT_SERVER_ID])

        assert error
        assert _ids(fresh) == {"app1.example.com", DEFAULT_SERVER_ID}

    def test_an_ordinary_service_is_still_deleted(self, fresh):
        fresh.save_config({"MULTISITE": "yes", "SERVER_NAME": "app1.example.com", "app1.example.com_SERVER_NAME": "app1.example.com"}, "scheduler")

        assert fresh.delete_services(["app1.example.com"]) == ""

        assert _ids(fresh) == {DEFAULT_SERVER_ID}


class TestTheRecoveryReachesTheDatabase:
    """PO ruling 4's lift has to survive the layer that actually writes.

    The API and the UI both stop refusing a rename/delete/draft on a row whose method is not
    `wizard` -- and then both save through `save_config`, which excluded the reserved id from
    `missing_ids`, from `method_services`/`foreign_services` and from `drafts` **by name**. The
    result was a 200 with nothing changed: the operator was told the recovery worked and the row was
    still there. These assert the ROW, not a status code, which is exactly what the mock-based API
    tests structurally cannot do.
    """

    def _roster(self, database, *names, method="ui", drafts=()):
        config = {"MULTISITE": "yes", "SERVER_NAME": " ".join(names)}
        for name in names:
            config[f"{name}_SERVER_NAME"] = name
            config[f"{name}_IS_DRAFT"] = "yes" if name in drafts else "no"
        assert not isinstance(database.save_config(config, method), str)

    @pytest.fixture
    def foreign(self, fresh):
        self._roster(fresh, "app1.example.com", DEFAULT_SERVER_ID)
        assert _methods(fresh)[DEFAULT_SERVER_ID] == "ui"
        return fresh

    @pytest.fixture
    def reserved(self, fresh):
        self._roster(fresh, "app1.example.com")
        assert _methods(fresh)[DEFAULT_SERVER_ID] == DEFAULT_SERVER_METHOD
        return fresh

    def test_a_save_that_omits_a_foreign_row_really_deletes_it(self, foreign):
        """And the seeding immediately puts the REAL reserved service in its place, which is the
        whole point of the recovery: the operator's row goes, the default server arrives. The method
        is the evidence -- the id alone cannot tell the two apart, which is the defect this closes."""
        self._roster(foreign, "app1.example.com")

        assert _methods(foreign)[DEFAULT_SERVER_ID] == DEFAULT_SERVER_METHOD

    def test_a_foreign_row_is_gone_even_when_nothing_reseeds_it(self, foreign):
        """Same deletion, single-site, where the seeding stands down -- so the row is simply gone."""
        assert not isinstance(
            foreign.save_config({"MULTISITE": "no", "SERVER_NAME": "app1.example.com", "app1.example.com_SERVER_NAME": "app1.example.com"}, "ui"),
            str,
        )

        assert DEFAULT_SERVER_ID not in _ids(foreign)

    def test_a_save_that_omits_the_reserved_row_keeps_it(self, reserved):
        """The invariant the exclusion exists for, and it must survive the lift."""
        self._roster(reserved, "app1.example.com")

        assert DEFAULT_SERVER_ID in _ids(reserved)

    def test_a_foreign_row_can_be_drafted(self, foreign):
        self._roster(foreign, "app1.example.com", DEFAULT_SERVER_ID, drafts=(DEFAULT_SERVER_ID,))

        drafted = {service["id"] for service in foreign.get_services(with_drafts=True) if service["is_draft"]}
        assert DEFAULT_SERVER_ID in drafted

    def test_the_reserved_row_can_never_be_drafted(self, reserved):
        """A drafted reserved row drops out of SERVER_NAME and the default server falls back to the
        global-only rendering with no error anywhere -- deletion by another name."""
        self._roster(reserved, "app1.example.com", DEFAULT_SERVER_ID, drafts=(DEFAULT_SERVER_ID,))

        drafted = {service["id"] for service in reserved.get_services(with_drafts=True) if service["is_draft"]}
        assert DEFAULT_SERVER_ID not in drafted

    def test_an_autoconf_teardown_still_spares_the_reserved_row(self, reserved):
        """`foreign_services` is the other list: an autoconf save with an empty SERVER_NAME must not
        abandon the whole save because a permanent wizard row exists."""
        assert not isinstance(reserved.save_config({"MULTISITE": "yes", "SERVER_NAME": ""}, "autoconf"), str)

        assert DEFAULT_SERVER_ID in _ids(reserved)

    def test_an_autoconf_teardown_does_NOT_delete_an_operators_own_row(self, foreign):
        """The other direction of the same list, and the reason it had to become method-aware: a
        `ui` service named `default-server` is a foreign service, so autoconf's teardown must stop
        rather than delete it on the strength of its name."""
        foreign.save_config({"MULTISITE": "yes", "SERVER_NAME": ""}, "autoconf")

        assert DEFAULT_SERVER_ID in _ids(foreign)
        assert "app1.example.com" in _ids(foreign)


class TestTheStripNeverEmptiesTheRoster:
    """DS-B6: the strip above must not be the thing that empties ``SERVER_NAME``.

    ``TestTheGateIsThreeValued`` establishes why every FRESH install carries the seeded row
    whatever it turns out to be -- the lifespan runs once, before MULTISITE is knowable, and
    reading "absent" as single-site would skip the seeding on every fresh multisite install
    permanently. The cost stated there ("a row that reaches nothing") holds only while the
    deployment has a service of its own. It does not when the operator's single-site
    ``SERVER_NAME`` IS ``default-server``: the roster then holds exactly one row, it is the seeded
    one, and the strip left ``SERVER_NAME`` empty.

    That empty string is not cosmetic. ``push-configs.py`` calls ``gen/main.py`` with no
    ``--variables``, so ``get_non_default_settings()`` IS the config the scheduler renders from:
    ``Templator.render`` iterated an empty roster and rendered no ``server{}`` block at all,
    ``_write_config`` wrote ``SERVER_NAME=`` into ``variables.env``, and the instance answered
    nothing -- with ``certificates:init()`` logging "no server name configured yet" and
    ``customcert:init()`` aborting on "attempt to concatenate a nil value" behind it. Seen in CI on
    the Linux arm of ``customcert / single_site_only_name_is_still_served_its_certificate``.

    The rule is ``strip_default_server_unless_alone``: keep the reserved id when nothing else
    remains, exactly as ``Templator.__init__`` and ``jobs/custom-cert.py`` already do -- both of
    which document THIS reader as the one that keeps the name.
    """

    @pytest.fixture
    def alone(self, fresh):
        """A fresh install seeded by the lifespan, then configured single-site under the reserved
        name -- the deployment the CI case drives, with no other row anywhere."""
        assert fresh.seed_default_server_service() == ""
        fresh.save_config({"MULTISITE": "no", "SERVER_NAME": DEFAULT_SERVER_ID}, "scheduler")
        assert _ids(fresh) == {DEFAULT_SERVER_ID}
        assert _methods(fresh)[DEFAULT_SERVER_ID] == DEFAULT_SERVER_METHOD
        return fresh

    @pytest.mark.parametrize("global_only", (False, True))
    @pytest.mark.parametrize("filtered", (None, ("SERVER_NAME",)))
    def test_the_only_row_is_kept_by_every_reader(self, alone, global_only, filtered):
        """`get_non_default_settings` is what the scheduler renders from and `get_config` is what
        it takes `full_config` from, so a rule that holds on one of them holds for half a render."""
        for reader in (alone.get_config, alone.get_non_default_settings):
            roster = reader(global_only=global_only, methods=False, filtered_settings=filtered)["SERVER_NAME"]
            assert roster == DEFAULT_SERVER_ID, (reader.__name__, global_only, filtered)

    def test_the_strip_still_fires_as_soon_as_anything_else_remains(self, alone):
        """The control, and the half the CI sibling case drives
        (`SERVER_NAME: "default-server www.example.com"`): the keep is "nothing else remains", not
        "single-site", so one real service is enough to put the reserved id back out of the roster."""
        alone.save_config({"MULTISITE": "yes", "SERVER_NAME": "app1.example.com", "app1.example.com_SERVER_NAME": "app1.example.com"}, "scheduler")
        alone.save_config({"MULTISITE": "no", "SERVER_NAME": f"{DEFAULT_SERVER_ID} app1.example.com"}, "scheduler")
        assert _ids(alone) == {DEFAULT_SERVER_ID, "app1.example.com"}

        assert alone.get_config()["SERVER_NAME"] == "app1.example.com"
        assert alone.get_non_default_settings()["SERVER_NAME"] == "app1.example.com"

    def test_the_rule_survives_a_one_shot_iterable(self):
        """`strip_default_server_unless_alone` is typed `Iterable`, exported in `__all__`, and the
        1.8 unification note proposes three more callers for it. Walking `names` twice would let the
        strip exhaust a generator and the fallback answer `[]` -- this exact outage, silently, on the
        only input that needs the keep at all."""
        assert strip_default_server_unless_alone(iter([DEFAULT_SERVER_ID])) == [DEFAULT_SERVER_ID]
        assert strip_default_server_unless_alone(name for name in (DEFAULT_SERVER_ID, "app1.example.com")) == ["app1.example.com"]
        assert strip_default_server_unless_alone(None) == []
        assert strip_default_server_unless_alone(()) == []

    def test_two_real_rows_beside_the_reserved_one_both_survive(self, fresh):
        """The keep removes nothing from the strip: with anything else in the roster the reserved id
        goes, and every real name stays. `Templator.render` renders ONE block from the whole string
        in single-site, so a name lost here is a `Host` the deployment stops answering."""
        fresh.save_config(
            {
                "MULTISITE": "yes",
                "SERVER_NAME": f"app1.example.com {DEFAULT_SERVER_ID} app2.example.com",
                "app1.example.com_SERVER_NAME": "app1.example.com",
                "app2.example.com_SERVER_NAME": "app2.example.com",
            },
            "scheduler",
        )
        assert _ids(fresh) == {DEFAULT_SERVER_ID, "app1.example.com", "app2.example.com"}

        fresh.save_config({"MULTISITE": "no", "SERVER_NAME": "app1.example.com app2.example.com"}, "scheduler")

        assert _ids(fresh) == {DEFAULT_SERVER_ID, "app1.example.com", "app2.example.com"}
        assert set(fresh.get_config()["SERVER_NAME"].split()) == {"app1.example.com", "app2.example.com"}
