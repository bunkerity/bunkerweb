"""``get_services`` must report the template and security mode the GENERATOR will apply.

Second half of dev ``b8f59c5a7`` (#3866), applied under the coordinator grant of 2026-09-07 00:45.
A service with no ``USE_TEMPLATE`` / ``SECURITY_MODE`` row of its own inherits the global value —
``get_config`` materialises ``{service}_USE_TEMPLATE`` for every service, so that template really is
in force at render time. Reporting the missing row as ``""`` / ``"block"`` told the operator the
opposite of what gets rendered: a fleet running ``SECURITY_MODE=detect`` was listed as blocking, and
a globally templated service was listed as carrying no template at all.

A row of the service's own still wins — that is the half that was already right.
"""

from fixtures.seed import add_global_value, add_service_setting, seed_multisite


class TestInheritedTemplate:
    def test_a_service_with_no_row_reports_the_global_template(self, db):
        seed_multisite(db)
        add_global_value(db, setting_id="USE_TEMPLATE", value="low")

        services = {svc["id"]: svc for svc in db.get_services(with_drafts=True)}

        assert services["app1.example.com"]["template"] == "low"

    def test_the_services_own_template_still_wins(self, db):
        seed_multisite(db)
        add_global_value(db, setting_id="USE_TEMPLATE", value="low")
        add_service_setting(db, service_id="app1.example.com", setting_id="USE_TEMPLATE", value="high")

        services = {svc["id"]: svc for svc in db.get_services(with_drafts=True)}

        assert services["app1.example.com"]["template"] == "high"
        assert services["app2.example.com"]["template"] == "low"

    def test_no_global_row_still_reports_no_template(self, db):
        seed_multisite(db)

        services = {svc["id"]: svc for svc in db.get_services(with_drafts=True)}

        assert services["app1.example.com"]["template"] == ""


class TestInheritedSecurityMode:
    """`seed_multisite` already models the real shape: a global SECURITY_MODE of "detect" with
    app1 carrying its own "block" row and app2 carrying none."""

    def test_a_service_with_no_row_reports_the_global_security_mode(self, db):
        """A fleet on `detect` listed app2 as blocking — the opposite of what it enforces."""
        seed_multisite(db)

        services = {svc["id"]: svc for svc in db.get_services(with_drafts=True)}

        assert services["app2.example.com"]["security_mode"] == "detect"

    def test_the_services_own_security_mode_still_wins(self, db):
        seed_multisite(db)

        services = {svc["id"]: svc for svc in db.get_services(with_drafts=True)}

        assert services["app1.example.com"]["security_mode"] == "block"

    def test_no_global_row_falls_back_to_block(self, db):
        """`seed_minimal` seeds the settings but no SECURITY_MODE global row."""
        from fixtures.seed import seed_minimal

        seed_minimal(db)

        services = {svc["id"]: svc for svc in db.get_services(with_drafts=True)}

        assert services["app1.example.com"]["security_mode"] == "block"
