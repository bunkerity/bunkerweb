"""The reserved ``default-server`` pseudo-service: seeding and the reconciliation guards.

The default server is the NGINX block answering every request that matches no configured service.
Conception option (b) gives it one permanent row in ``bw_services`` so its certificate, TLS,
headers and error pages can be stored and edited like a service's. "Permanent" is the whole
contract, and it is not free: the row is seeded with method ``wizard`` (the only existing
``methods_enum`` value that is both editable and already undeletable), which puts it in the path of
three lists in ``config_save.py`` that would otherwise delete it, or abort an unrelated save
because of it.
"""

import pytest

from default_server import DEFAULT_SERVER_ID, DEFAULT_SERVER_METHOD, DEFAULT_SERVER_SEEDED_SETTINGS  # type: ignore
from fixtures.seed import make_core_plugin, make_general_settings

pytestmark = pytest.mark.slow


# The three settings the reserved row is seeded with have to EXIST in `bw_settings` before a row in
# `bw_services_settings` can reference them (the FK), so a fixture that wants to see the seeding has
# to declare them. Their real global defaults are used deliberately: `AUTO_REDIRECT_HTTP_TO_HTTPS`
# and `USE_WHITELIST` ship as `yes`, which is what makes "the seeded value is `no`" a statement
# about the seeding rather than about the default.
_SEEDED_DEFAULTS = {"AUTO_REDIRECT_HTTP_TO_HTTPS": "yes", "REDIRECT_HTTP_TO_HTTPS": "no", "USE_WHITELIST": "yes"}


def _seeded_settings_schema() -> dict:
    return {
        key: {
            "id": key.lower().replace("_", "-"),
            "context": "multisite",
            "default": default,
            "help": "h",
            "label": key,
            "regex": "^(yes|no)$",
            "type": "check",
        }
        for key, default in _SEEDED_DEFAULTS.items()
    }


@pytest.fixture
def seeded(db):
    db.init_tables([make_general_settings(), make_core_plugin("alpha")])
    db.initialize_db("1.7.0", "Docker")
    return db


@pytest.fixture
def seeded_full(db):
    """`seeded`, plus the three settings the seeding writes. Separate rather than folded in, so the
    tests above keep proving the row is created even when `bw_settings` has never heard of them --
    the first-boot race with the scheduler's `init_tables`.

    MULTISITE is turned on here because `get_config` materialises no per-service key without it, and
    reading the seeded rows back is the whole point of this fixture."""
    db.init_tables([make_general_settings() | _seeded_settings_schema(), make_core_plugin("alpha")])
    db.initialize_db("1.7.0", "Docker")
    db.save_config({"MULTISITE": "yes", "SERVER_NAME": "app1.example.com"}, "scheduler")
    return db


def _own_settings(database, service=DEFAULT_SERVER_ID):
    """What the SERVICE stores, not what it inherits. `get_config(methods=True)` marks an inherited
    value `default`, so keying off the method is the only way to tell a seeded `no` from a global
    `no` -- and REDIRECT_HTTP_TO_HTTPS is exactly that case."""
    config = database.get_config(methods=True, with_drafts=True)
    return {
        key[len(service) + 1 :]: value["value"]  # noqa: E203
        for key, value in config.items()
        if key.startswith(f"{service}_") and isinstance(value, dict) and value.get("method") == DEFAULT_SERVER_METHOD
    }


def _ids(database):
    return {service["id"] for service in database.get_services(with_drafts=True)}


class TestSeeding:
    def test_a_fresh_database_gains_the_row(self, seeded):
        assert seeded.seed_default_server_service() == ""
        assert DEFAULT_SERVER_ID in _ids(seeded)
        row = next(s for s in seeded.get_services(with_drafts=True) if s["id"] == DEFAULT_SERVER_ID)
        assert row["method"] == DEFAULT_SERVER_METHOD
        assert row["is_draft"] is False

    def test_seeding_is_idempotent(self, seeded):
        assert seeded.seed_default_server_service() == ""
        created = next(s for s in seeded.get_services(with_drafts=True) if s["id"] == DEFAULT_SERVER_ID)["creation_date"]
        assert seeded.seed_default_server_service() == ""
        again = next(s for s in seeded.get_services(with_drafts=True) if s["id"] == DEFAULT_SERVER_ID)
        # Same row, not a replacement: a second boot must not reset anything the operator changed.
        assert again["creation_date"] == created
        assert len([s for s in seeded.get_services(with_drafts=True) if s["id"] == DEFAULT_SERVER_ID]) == 1

    def test_an_upgraded_database_gains_the_row_on_first_boot(self, seeded):
        """An "upgraded" database here is one that already carries services and no reserved row --
        exactly the state a 1.6 database is in when the 1.7 API starts against it.

        DS-B4 re-pin: the configuration save is now a seeding trigger of its own (PO ruling of
        2026-09-06 -- the API lifespan decides once per boot, on a MULTISITE value that is not yet
        written on a fresh install and that an operator can flip years later), so the row is there
        before the lifespan runs. What the lifespan call has to prove here is that it is a no-op on
        top, and that neither trigger touches the operator's own service.
        """
        seeded.save_config({"MULTISITE": "yes", "SERVER_NAME": "app1.example.com", "app1.example.com_ALPHA_MS": "v1"}, "scheduler")
        assert _ids(seeded) == {"app1.example.com", DEFAULT_SERVER_ID}
        created = next(s for s in seeded.get_services(with_drafts=True) if s["id"] == DEFAULT_SERVER_ID)["creation_date"]

        assert seeded.seed_default_server_service() == ""

        assert _ids(seeded) == {"app1.example.com", DEFAULT_SERVER_ID}
        assert next(s for s in seeded.get_services(with_drafts=True) if s["id"] == DEFAULT_SERVER_ID)["creation_date"] == created
        # And the operator's service is untouched by the seeding.
        assert seeded.get_config()["app1.example.com_ALPHA_MS"] == "v1"

    def test_the_row_lands_in_server_name(self, seeded):
        """`SERVER_NAME` is rebuilt from `bw_services` (config_read.py), and that is what makes
        `variables["default-server"]` exist in the Lua runtime -- the per-site table the runners
        bind to.

        DS-B4 re-pin: in MULTISITE mode. The non-multisite branch of the same rebuild strips the
        reserved id deliberately (`tests/unit/db/test_default_server_multisite_gate.py`), because
        single-site renders ONE block from the whole string and the id would become an alias that
        block answers to.
        """
        seeded.save_config({"MULTISITE": "yes", "SERVER_NAME": "app1.example.com", "app1.example.com_SERVER_NAME": "app1.example.com"}, "scheduler")
        seeded.seed_default_server_service()
        assert DEFAULT_SERVER_ID in seeded.get_config()["SERVER_NAME"].split()

    def test_a_created_row_carries_the_conservative_values(self, seeded_full):
        """PO ruling of 2026-09-03. The three phase runners are unconditional, so without these an
        upgrade changes what the catch-all block answers: `ssl:access` starts 301-ing plain HTTP to
        https, and the whitelist chain -- skipped on the default server until now -- starts running.
        Both are pinned back to the pre-1.7 behaviour ON CREATION, and shown on the page."""
        assert seeded_full.seed_default_server_service() == ""
        # Spelled out rather than compared against the constant: asserting a module constant equals
        # itself proves nothing, and these three values ARE the ruling.
        assert _own_settings(seeded_full) == {"AUTO_REDIRECT_HTTP_TO_HTTPS": "no", "REDIRECT_HTTP_TO_HTTPS": "no", "USE_WHITELIST": "no"}
        assert DEFAULT_SERVER_SEEDED_SETTINGS == _own_settings(seeded_full), "the constant is the single source of truth for the page and the docs"

    def test_a_later_boot_never_writes_the_seeded_values_again(self, seeded_full):
        """The half that matters more than the values: an operator who turns the redirect back on
        must not find it off after the next restart.

        A value equal to its setting default is not STORED (`config_save`), so setting all three
        back leaves the row with no settings of its own -- which is why the guard is "the row
        exists", not "the row has settings". This test is what pins that: with a
        top-up-when-empty rule it goes red."""
        seeded_full.seed_default_server_service()
        # Two saves, because a row is only dropped when the value CHANGES to its default: the first
        # turns all three on, the second puts REDIRECT_HTTP_TO_HTTPS back. What the operator meant
        # is "the shipped behaviour"; what the database holds afterwards is nothing at all.
        for redirect in ("yes", "no"):
            seeded_full.save_config(
                {
                    "MULTISITE": "yes",
                    "SERVER_NAME": f"app1.example.com {DEFAULT_SERVER_ID}",
                    f"{DEFAULT_SERVER_ID}_AUTO_REDIRECT_HTTP_TO_HTTPS": "yes",
                    f"{DEFAULT_SERVER_ID}_REDIRECT_HTTP_TO_HTTPS": redirect,
                    f"{DEFAULT_SERVER_ID}_USE_WHITELIST": "yes",
                },
                "wizard",
            )
        assert _own_settings(seeded_full) == {}, "the premise: values equal to their defaults store no rows"

        assert seeded_full.seed_default_server_service() == ""

        after = seeded_full.get_config()
        assert after[f"{DEFAULT_SERVER_ID}_AUTO_REDIRECT_HTTP_TO_HTTPS"] == "yes"
        assert after[f"{DEFAULT_SERVER_ID}_USE_WHITELIST"] == "yes"

    def test_a_row_created_before_the_settings_existed_carries_none(self, db):
        """The first-boot race, stated rather than worked around: the API's lifespan can run before
        the scheduler's `init_tables`, and the FK on `bw_services_settings.setting_id` means the
        seeds cannot be written yet. The row is still created and simply carries none -- a FRESH
        install has no previous behaviour to preserve, and topping it up later would collide with
        the guarantee proven just above."""
        db.init_tables([make_general_settings(), make_core_plugin("alpha")])
        db.initialize_db("1.7.0", "Docker")
        db.save_config({"MULTISITE": "yes", "SERVER_NAME": "app1.example.com"}, "scheduler")

        assert db.seed_default_server_service() == ""

        assert DEFAULT_SERVER_ID in _ids(db)
        assert _own_settings(db) == {}

    def test_seeding_is_refused_on_a_readonly_database(self, seeded):
        seeded.readonly = True
        try:
            assert "read-only" in seeded.seed_default_server_service()
        finally:
            seeded.readonly = False
        assert DEFAULT_SERVER_ID not in _ids(seeded)


class TestReconciliationGuards:
    def test_a_ui_save_that_omits_it_does_not_delete_it(self, seeded):
        seeded.seed_default_server_service()
        seeded.save_config({"MULTISITE": "yes", "SERVER_NAME": "app1.example.com", "app1.example.com_ALPHA_MS": "v1"}, "ui")

        seeded.save_config({"MULTISITE": "yes", "SERVER_NAME": "app1.example.com", "app1.example.com_ALPHA_MS": "v2"}, "ui")

        assert DEFAULT_SERVER_ID in _ids(seeded)

    def test_a_wizard_save_that_omits_it_does_not_delete_it(self, seeded):
        """The sharp case: the reserved row is seeded `wizard`, so a save BY the wizard matches its
        method and `missing_ids` would collect it without the explicit exclusion."""
        seeded.seed_default_server_service()
        seeded.save_config({"MULTISITE": "yes", "SERVER_NAME": "app1.example.com", "app1.example.com_ALPHA_MS": "v1"}, "wizard")

        seeded.save_config({"MULTISITE": "yes", "SERVER_NAME": "app1.example.com", "app1.example.com_ALPHA_MS": "v2"}, "wizard")

        assert DEFAULT_SERVER_ID in _ids(seeded)

    def test_a_globals_only_wizard_save_is_not_abandoned_because_the_reserved_row_exists(self, seeded):
        """`method_services` is the third guard, and the one whose damage is silent.

        The branch it feeds abandons the ENTIRE save -- "skipping entire config save to prevent
        data loss" -- when a config with no `SERVER_NAME` key arrives while the database still holds
        services owned by the saving method. The reserved row is seeded `wizard`, so without the
        exclusion it makes that list permanently non-empty for the wizard: a deployment with no
        services of its own could never persist a global setting again, and the API would still
        answer 200.
        """
        seeded.seed_default_server_service()

        seeded.save_config({"MULTISITE": "yes", "ALPHA_GLOBAL": "persisted"}, "wizard")

        assert seeded.get_config()["ALPHA_GLOBAL"] == "persisted"
        assert DEFAULT_SERVER_ID in _ids(seeded)

    def test_an_autoconf_teardown_with_an_empty_server_name_still_removes_its_own_services(self, seeded):
        """`foreign_services` is the guard that matters most. It holds every row that is not
        autoconf/scheduler and, when it is non-empty, autoconf's "last ingress removed" save is
        ABANDONED whole ("skipping entire config save to prevent data loss"). A permanent wizard row
        makes it non-empty forever, so without the exclusion this breaks in every autoconf
        deployment -- not on an edge case, on the normal teardown path."""
        seeded.seed_default_server_service()
        seeded.save_config({"MULTISITE": "yes", "SERVER_NAME": "ingress.example.com", "ingress.example.com_ALPHA_MS": "v1"}, "autoconf")
        assert _ids(seeded) == {"ingress.example.com", DEFAULT_SERVER_ID}

        seeded.save_config({"MULTISITE": "yes", "SERVER_NAME": ""}, "autoconf")

        assert _ids(seeded) == {DEFAULT_SERVER_ID}

    def test_an_autoconf_teardown_is_still_refused_when_a_real_foreign_service_exists(self, seeded):
        """The other direction, so the exclusion above cannot be read as "empty the guard": a real
        UI-owned service must STILL abort an autoconf teardown."""
        seeded.seed_default_server_service()
        seeded.save_config({"MULTISITE": "yes", "SERVER_NAME": "ui.example.com", "ui.example.com_ALPHA_MS": "v1"}, "ui")
        seeded.save_config({"MULTISITE": "yes", "SERVER_NAME": "ui.example.com ingress.example.com", "ingress.example.com_ALPHA_MS": "v1"}, "autoconf")

        seeded.save_config({"MULTISITE": "yes", "SERVER_NAME": ""}, "autoconf")

        assert _ids(seeded) == {"ui.example.com", "ingress.example.com", DEFAULT_SERVER_ID}

    def test_its_own_settings_survive_a_save_by_another_method(self, seeded):
        """The realistic hazard: an operator edits the default server in the UI, then a Docker
        deployment's scheduler saves the environment -- a config that has never heard of the
        reserved service. Method-scoped cleanup is what protects it, exactly as it protects a
        UI-created service from an environment save.

        NOT asserted, because the product does not promise it for ANY service: that a *ui/api* save
        which omits the keys keeps them. A ui save declaring complete desired state drops the
        ui-owned settings it does not carry, for the reserved row like for every other; the UI's own
        service page never posts that shape (`restore_unowned_settings`), and the API's handlers
        build their payload from a full snapshot.
        """
        seeded.seed_default_server_service()
        seeded.save_config(
            {"MULTISITE": "yes", "SERVER_NAME": f"app1.example.com {DEFAULT_SERVER_ID}", f"{DEFAULT_SERVER_ID}_ALPHA_MS": "kept"},
            "ui",
        )
        assert seeded.get_config()[f"{DEFAULT_SERVER_ID}_ALPHA_MS"] == "kept"

        seeded.save_config({"MULTISITE": "yes", "SERVER_NAME": "app1.example.com", "app1.example.com_ALPHA_MS": "v1"}, "scheduler")

        assert DEFAULT_SERVER_ID in _ids(seeded)
        assert seeded.get_config()[f"{DEFAULT_SERVER_ID}_ALPHA_MS"] == "kept"

    def test_a_save_that_drafts_it_leaves_it_online(self, seeded):
        """Drafting the reserved row is deleting it by another name: a draft drops out of
        SERVER_NAME, so the default server silently falls back to the global-only rendering and
        every setting on its page stops applying with no error anywhere.

        The API and the UI both refuse the request, but `save_config` is reached by more than those
        two -- the CLI, the scheduler, an autoconf run -- and the row is seeded `wizard`, which is
        in EDITABLE_METHODS, so the draft branch would flip it. Guarded by id rather than by the
        method it happens to carry, for the reason `can_delete_service` states.

        HONESTY NOTE: this test pins the CONTRACT, not the guard. Deleting the `is_default_server`
        skip in `config_save.py`'s draft loop leaves it GREEN, because `<service>_IS_DRAFT` in a
        `save_config` payload does not reach that loop here -- an ordinary service given the same
        key in the same save does not draft either. The guard is therefore belt-and-braces against
        the mechanism the API's own `PATCH /services/{service}` uses
        (`conf[f"{target}_IS_DRAFT"] = "yes"` -> `_persist_config`), and it is declared as
        unproven in `report-DS-B.md` rather than counted among the mutation-proved guards.
        """
        seeded.seed_default_server_service()
        seeded.save_config({"MULTISITE": "yes", "SERVER_NAME": "app1.example.com", "app1.example.com_ALPHA_MS": "v1"}, "wizard")

        seeded.save_config(
            {
                "MULTISITE": "yes",
                "SERVER_NAME": f"app1.example.com {DEFAULT_SERVER_ID}",
                f"{DEFAULT_SERVER_ID}_IS_DRAFT": "yes",
                "app1.example.com_IS_DRAFT": "yes",
            },
            "wizard",
        )

        rows = {service["id"]: service for service in seeded.get_services(with_drafts=True)}
        assert rows[DEFAULT_SERVER_ID]["is_draft"] is False
