"""DatabaseServicesMixin — multisite service listing and cascading deletion."""

from fixtures.seed import (
    add_custom_config_row,
    add_jobs_cache_row,
    add_service,
    add_service_setting,
    seed_minimal,
)


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

        assert db.delete_services(["app1.example.com"]) == ""
        # service + its related rows are gone, and the change flag is set.
        assert db.get_services(with_drafts=True) == []
        assert db.get_custom_config("server_http", "snip", service_id="app1.example.com") == {}
        assert db.get_job_cache_file("testjob", "cache.txt", service_id="app1.example.com") is None
        assert db.get_metadata()["custom_configs_changed"] is True
