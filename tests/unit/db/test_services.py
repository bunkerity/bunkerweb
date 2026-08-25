"""DatabaseServicesMixin — multisite service listing and cascading deletion."""

from datetime import datetime, timezone

from fixtures.seed import (
    add_custom_config_row,
    add_global_value,
    add_setting,
    add_jobs_cache_row,
    add_service,
    add_service_setting,
    seed_minimal,
    session,
)
from model import ResourceAttachments, Resources, Upstreams


class TestGetServices:
    def test_empty(self, db):
        assert db.get_services() == []

    def test_returns_seeded_with_label_defaults(self, db):
        seed_minimal(db)
        svcs = db.get_services()
        assert [s["id"] for s in svcs] == ["app1.example.com"]
        s0 = svcs[0]
        assert s0["method"] == "manual"
        assert s0["is_draft"] is False
        # No USE_TEMPLATE / SECURITY_MODE service-setting rows -> outerjoin NULL -> defaults.
        assert s0["template"] == ""
        assert s0["security_mode"] == "block"

    def test_template_and_security_mode_labels(self, db):
        seed_minimal(db)
        add_service_setting(db, service_id="app1.example.com", setting_id="USE_TEMPLATE", value="low")
        add_service_setting(db, service_id="app1.example.com", setting_id="SECURITY_MODE", value="detect")
        s0 = db.get_services()[0]
        assert s0["template"] == "low"
        assert s0["security_mode"] == "detect"

    def test_drafts_filtered_unless_requested(self, db):
        seed_minimal(db)  # app1 is non-draft
        add_service(db, "draft.example.com", is_draft=True)
        assert {s["id"] for s in db.get_services()} == {"app1.example.com"}
        assert {s["id"] for s in db.get_services(with_drafts=True)} == {"app1.example.com", "draft.example.com"}


class TestDeleteServices:
    def test_empty_list_is_noop(self, db):
        assert db.delete_services([]) == ""

    def test_cascade_and_metadata_flag(self, db):
        seed_minimal(db)
        add_service_setting(db, service_id="app1.example.com", setting_id="USE_REVERSE_PROXY", value="yes")
        add_custom_config_row(db, service_id="app1.example.com", type="server_http", name="snip", data=b"# x")
        add_jobs_cache_row(db, job_name="testjob", service_id="app1.example.com")
        with session(db) as db_session:
            now = datetime.now(timezone.utc)
            db_session.add(Resources(id="pool", type="upstream", name="pool", creation_date=now, last_update=now))
            db_session.add(Upstreams(resource_id="pool", protocol="http", method="round_robin"))
            db_session.add(ResourceAttachments(resource_id="pool", service_id="app1.example.com", creation_date=now))

        assert db.delete_services(["app1.example.com"]) == ""
        # service + its related rows are gone, and the change flag is set.
        assert db.get_services(with_drafts=True) == []
        assert db.get_custom_config("server_http", "snip", service_id="app1.example.com") == {}
        assert db.get_job_cache_file("testjob", "cache.txt", service_id="app1.example.com") is None
        assert db.get_metadata()["custom_configs_changed"] is True
        with session(db) as db_session:
            assert db_session.query(ResourceAttachments).count() == 0


class TestLinkPort:
    """``link_port`` is what an absolute link to a service must carry, and "" means "carry none".

    Empty is the answer for every service that listens where the fleet does, which is every service
    on a deployment that uses no per-service ports: the images publish ``443:8443``
    (``misc/integrations/docker.yml:16-18``), so the RENDERED port is not the reachable one and
    putting it in a link would send the operator to a socket nothing listens on from outside.
    A service moved off that list is the opposite case -- its rendered port is the only one that
    reaches it, so the link has to carry it.
    """

    def _settings(self, db):
        add_setting(db, "HTTPS_PORT", context="multisite", multiple="listen-https-ports", default="8443")

    def test_a_service_that_declares_nothing_gets_no_port(self, db):
        seed_minimal(db)
        self._settings(db)
        assert db.get_services()[0]["link_port"] == ""

    def test_a_service_on_its_own_port_gets_that_port(self, db):
        seed_minimal(db)
        self._settings(db)
        add_service_setting(db, service_id="app1.example.com", setting_id="HTTPS_PORT", value="9443")
        assert db.get_services()[0]["link_port"] == "9443"

    def test_a_service_declaring_the_global_value_gets_no_port(self, db):
        """Same list as the global one is not a move, whether it is inherited or restated."""
        seed_minimal(db)
        self._settings(db)
        add_global_value(db, setting_id="HTTPS_PORT", value="9443")
        add_service_setting(db, service_id="app1.example.com", setting_id="HTTPS_PORT", value="9443")
        assert db.get_services()[0]["link_port"] == ""

    def test_the_declared_default_is_used_when_no_global_row_exists(self, db):
        """A setting left at its default has no ``Global_values`` row at all, so without the
        fallback every service that restated the default would look moved."""
        seed_minimal(db)
        self._settings(db)
        add_service_setting(db, service_id="app1.example.com", setting_id="HTTPS_PORT", value="8443")
        assert db.get_services()[0]["link_port"] == ""

    def test_the_first_port_is_the_one_linked(self, db):
        seed_minimal(db)
        self._settings(db)
        add_service_setting(db, service_id="app1.example.com", setting_id="HTTPS_PORT", value="9443", suffix=0)
        add_service_setting(db, service_id="app1.example.com", setting_id="HTTPS_PORT", value="9444", suffix=1)
        assert db.get_services()[0]["link_port"] == "9443"

    def test_one_service_moving_does_not_move_its_neighbour(self, db):
        seed_minimal(db)
        self._settings(db)
        add_service(db, "app2.example.com")
        add_service_setting(db, service_id="app2.example.com", setting_id="HTTPS_PORT", value="9443")
        assert {service["id"]: service["link_port"] for service in db.get_services()} == {
            "app1.example.com": "",
            "app2.example.com": "9443",
        }
