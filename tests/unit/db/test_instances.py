"""DatabaseInstancesMixin — BunkerWeb instance registry CRUD.

Runs against every selected engine via the ``db`` fixture. ``db_init`` seeds the
singleton Metadata row so the ``changed`` -> ``instances_changed`` paths are exercised.
"""

import pytest


@pytest.fixture
def db_init(db):
    db.initialize_db("1.7.0", "Docker")
    return db


class TestAddInstance:
    def test_add_and_get(self, db_init):
        assert db_init.add_instance("bw-1", 5000, "bwapi", "manual") == ""
        inst = db_init.get_instance("bw-1")
        assert inst["hostname"] == "bw-1"
        assert inst["port"] == 5000
        assert inst["server_name"] == "bwapi"
        assert inst["method"] == "manual"
        assert inst["listen_https"] is False

    def test_duplicate_rejected(self, db_init):
        db_init.add_instance("bw-1", 5000, "bwapi", "manual")
        msg = db_init.add_instance("bw-1", 5000, "bwapi", "manual")
        assert "already exists" in msg

    def test_changed_flag_flips_metadata(self, db_init):
        assert db_init.get_metadata()["instances_changed"] is False
        db_init.add_instance("bw-1", 5000, "bwapi", "manual", changed=True)
        assert db_init.get_metadata()["instances_changed"] is True

    def test_listen_https_roundtrip(self, db_init):
        db_init.add_instance("bw-tls", 5000, "bwapi", "manual", listen_https=True, https_port=8443)
        inst = db_init.get_instance("bw-tls")
        assert inst["listen_https"] is True
        assert inst["https_port"] == 8443


class TestGetInstances:
    def test_method_filter_and_autoconf_shape(self, db_init):
        db_init.add_instance("bw-a", 5000, "bwapi", "manual")
        db_init.add_instance("bw-b", 5000, "bwapi", "autoconf")
        assert {i["hostname"] for i in db_init.get_instances()} == {"bw-a", "bw-b"}
        manual = db_init.get_instances(method="manual")
        assert [i["hostname"] for i in manual] == ["bw-a"]
        auto = db_init.get_instances(method="autoconf", autoconf=True)
        assert len(auto) == 1
        # autoconf=True augments each row with health + env; don't assume a default status.
        assert "health" in auto[0]
        assert auto[0]["env"] == {}

    def test_missing_returns_empty_dict(self, db_init):
        assert db_init.get_instance("nope") == {}


class TestDeleteInstance:
    def test_delete(self, db_init):
        db_init.add_instance("bw-1", 5000, "bwapi", "manual")
        assert db_init.delete_instance("bw-1") == ""
        assert db_init.get_instance("bw-1") == {}

    def test_delete_absent(self, db_init):
        assert "does not exist" in db_init.delete_instance("ghost")

    def test_delete_instances_none_found(self, db_init):
        assert db_init.delete_instances(["ghost"]) == "No instances found to delete."


class TestUpdateInstances:
    def test_empty_autoconf_list_is_noop_data_loss_guard(self, db_init):
        db_init.add_instance("bw-auto", 5000, "bwapi", "autoconf")
        # An empty list for method 'autoconf' must NOT wipe existing autoconf instances.
        assert db_init.update_instances([], "autoconf") == ""
        assert db_init.get_instance("bw-auto")["hostname"] == "bw-auto"

    def test_update_replaces_method_scope(self, db_init):
        db_init.add_instance("old", 5000, "bwapi", "autoconf")
        new = [{"hostname": "new", "env": {"API_HTTP_PORT": 5000, "API_SERVER_NAME": "bwapi"}}]
        assert db_init.update_instances(new, "autoconf") == ""
        # 'old' (autoconf) is cleared and replaced by 'new'.
        assert {i["hostname"] for i in db_init.get_instances()} == {"new"}


class TestUpdateInstance:
    def test_update_status(self, db_init):
        db_init.add_instance("bw-1", 5000, "bwapi", "manual")
        assert db_init.update_instance("bw-1", "up") == ""
        assert db_init.get_instance("bw-1")["status"] == "up"

    def test_update_status_missing(self, db_init):
        assert "does not exist" in db_init.update_instance("ghost", "up")

    def test_update_fields(self, db_init):
        db_init.add_instance("bw-1", 5000, "bwapi", "manual")
        assert db_init.update_instance_fields("bw-1", name="renamed", port=6000) == ""
        inst = db_init.get_instance("bw-1")
        assert inst["name"] == "renamed"
        assert inst["port"] == 6000

    def test_update_fields_missing(self, db_init):
        assert "does not exist" in db_init.update_instance_fields("ghost", name="x")
