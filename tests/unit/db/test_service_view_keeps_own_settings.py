"""``get_config(service=...)`` must answer with the SERVICE's own rows, not the template's.

Port of dev ``b8f59c5a7`` (#3866). The service view stripped the ``{service}_`` prefix from inside
the loop that walked a snapshot of the dict it was mutating: every key was popped, and a prefixed
key was re-inserted under its stripped name. When the stripped name appeared LATER in the same
snapshot -- which a globally declared template makes routine, because the template overlay inserts
suffixed members (``REVERSE_PROXY_URL_1``) that the base ``Settings`` query never seeds, i.e. AFTER
``get_non_default_settings`` has already inserted ``{service}_REVERSE_PROXY_URL_1`` -- the second
visit popped the value that had just been renamed onto it and dropped it on the ``continue``. The
group re-materialisation block below then refilled the hole with the TEMPLATE default, so the
operator was told the opposite of what the generator renders.
"""

from fixtures.seed import add_global_value, add_service_setting, seed_multisite


def _declare_global_template(db, *, value="http://template-backend"):
    assert (
        db.create_template(
            "low",
            name="Low",
            settings={"REVERSE_PROXY_URL_1": value},
            steps=[{"title": "S", "settings": ["REVERSE_PROXY_URL_1"]}],
        )
        == ""
    )
    add_global_value(db, setting_id="USE_TEMPLATE", value="low")


class TestServiceViewUnderAGlobalTemplate:
    def test_the_services_own_value_survives_a_template_that_declares_the_same_key(self, db):
        seed_multisite(db)  # app1 carries REVERSE_PROXY_URL_1 = http://backend1 as its own row
        _declare_global_template(db)

        cfg = db.get_config(methods=True, service="app1.example.com")

        assert cfg["REVERSE_PROXY_URL_1"]["value"] == "http://backend1"
        # Provenance too: reporting the right value under `method: default` would still tell the UI
        # the row is the template's and let a template change drop it.
        assert cfg["REVERSE_PROXY_URL_1"]["method"] == "manual"
        assert cfg["REVERSE_PROXY_URL_1"]["template"] is None

    def test_a_service_with_no_row_of_its_own_still_gets_the_template_value(self, db):
        seed_multisite(db)  # app2 has no REVERSE_PROXY_URL_1 row
        _declare_global_template(db)

        cfg = db.get_config(methods=True, service="app2.example.com")

        assert cfg["REVERSE_PROXY_URL_1"]["value"] == "http://template-backend"
        assert cfg["REVERSE_PROXY_URL_1"]["template"] == "low"

    def test_the_values_only_view_agrees_with_the_metadata_view(self, db):
        seed_multisite(db)
        _declare_global_template(db)

        assert db.get_config(methods=False, service="app1.example.com")["REVERSE_PROXY_URL_1"] == "http://backend1"


class TestServiceViewShape:
    def test_no_key_of_another_service_leaks_into_the_view(self, db):
        seed_multisite(db)
        add_service_setting(db, service_id="app2.example.com", setting_id="USE_REVERSE_PROXY", value="yes")

        cfg = db.get_config(methods=False, service="app1.example.com")

        assert not [key for key in cfg if key.startswith(("app1.example.com_", "app2.example.com_"))]
        assert cfg["USE_REVERSE_PROXY"] == "yes"  # app1's own override, prefix stripped
