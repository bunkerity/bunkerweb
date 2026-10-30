"""A global set on the Scheduler must reach a service Autoconf discovered.

PO decision (2026-08-14): globals apply everywhere. A per-service label still wins, and removing
that label falls back to the global -- never to the plugin default.

The observed symptom is one integration spec: `tests/core/misc.yml`'s large_body_size returns 200
on Docker and 400 (ModSecurity 200002) on Autoconf, i.e. the Scheduler's global did not reach the
discovered service. These tests pin the two DB-layer mechanisms that could produce that, so the
search can move on to the Autoconf controller and the generator instead of coming back here:

1. an Autoconf save materializing a per-service ROW for a setting the labels never mentioned,
   which would shadow the global from then on (and Autoconf would not rewrite it, since its own
   label set never changed);
2. an Autoconf save deleting the Scheduler's global rows because they carry another method.
"""

from fixtures.seed import seed_multisite


class TestSchedulerGlobalsReachAutoconfServices:
    def test_an_autoconf_save_does_not_materialize_per_service_rows(self, db):
        """Autoconf posts SERVER_NAME + the labels it saw. Nothing else may become a row.

        A row written here would be indistinguishable later from a deliberate per-service
        override, and would keep answering with the value the setting had the day the service was
        discovered.
        """
        seed_multisite(db)

        db.save_config(
            {
                "SERVER_NAME": "app1.example.com app2.example.com",
                "MULTISITE": "yes",
                "app1.example.com_USE_REVERSE_PROXY": "yes",
            },
            "autoconf",
        )

        config = db.get_config(methods=True)
        autoconf_rows = {
            key for key, entry in config.items() if isinstance(entry, dict) and entry.get("method") == "autoconf" and not entry.get("global", True)
        }
        assert autoconf_rows == {"app1.example.com_USE_REVERSE_PROXY"}

    def test_a_scheduler_global_still_reaches_a_discovered_service(self, db):
        seed_multisite(db)
        db.save_config(
            {
                "SERVER_NAME": "app1.example.com app2.example.com",
                "MULTISITE": "yes",
                "app1.example.com_USE_REVERSE_PROXY": "yes",
            },
            "autoconf",
        )

        # The Scheduler's own environment, saved after Autoconf has already declared the services.
        db.save_config({"SERVER_NAME": "", "MULTISITE": "yes", "SECURITY_MODE": "detect"}, "scheduler")

        config = db.get_config(methods=False)
        assert config["app2.example.com_SECURITY_MODE"] == "detect"
        # app1 carries a real per-service override from the fixture: that one still wins.
        assert config["app1.example.com_SECURITY_MODE"] == "block"

    def test_an_autoconf_save_does_not_wipe_the_scheduler_globals(self, db):
        seed_multisite(db)
        db.save_config({"SERVER_NAME": "", "MULTISITE": "yes", "SECURITY_MODE": "detect"}, "scheduler")

        db.save_config(
            {
                "SERVER_NAME": "app1.example.com app2.example.com",
                "MULTISITE": "yes",
                "app1.example.com_USE_REVERSE_PROXY": "yes",
            },
            "autoconf",
        )

        config = db.get_config(methods=True)
        assert config["SECURITY_MODE"]["value"] == "detect"
        assert config["SECURITY_MODE"]["method"] == "scheduler"
        assert config["app2.example.com_SECURITY_MODE"]["value"] == "detect"
