"""``POST``/``PATCH /services``: a service always has a name, and no two services share one.

Dev ``cea19bc67`` (an empty ``SERVER_NAME`` is refused for a service) and ``431269286`` (the API
half of the shared-name check: the Web UI refused it already, ``POST``/``PATCH`` saved a name another
service owns, and the next Web UI edit of either then deleted the other).

Same loader and ``Mock`` db as ``test_services_validation.py``.
"""

from unittest.mock import Mock

import pytest

from test_services_validation import ROUTER, SERVICE, schemas  # noqa: F401  (the module loader is the fixture)

OTHER = "other.example.com"


@pytest.fixture
def db(monkeypatch):
    fake_db = Mock()
    fake_db.get_non_default_settings.return_value = {
        "SERVER_NAME": f"{SERVICE} {OTHER}",
        f"{SERVICE}_SERVER_NAME": SERVICE,
        f"{OTHER}_SERVER_NAME": f"{OTHER} alias.example.com",
    }
    fake_db.save_config.return_value = set()
    fake_db.is_valid_setting.return_value = (True, "")
    fake_db.unknown_template_layers.return_value = []
    fake_db.get_config.return_value = {"HTTP_PORT": "8080"}
    fake_db.get_services.return_value = [{"id": SERVICE, "method": "api"}, {"id": OTHER, "method": "api"}]
    monkeypatch.setattr(ROUTER, "get_db", lambda: fake_db)
    return fake_db


class TestEmptyServerName:
    @pytest.mark.parametrize("blank", ["", "   "], ids=["empty", "blank"])
    def test_create_refuses_an_empty_server_name_variable(self, db, blank):
        response = ROUTER.create_service(schemas.ServiceCreateRequest(server_name="new.example.com", variables={"SERVER_NAME": blank}))

        assert response.status_code == 422
        assert "SERVER_NAME" in response.content["message"]
        db.save_config.assert_not_called()

    def test_create_without_a_server_name_variable_names_the_service_by_its_id(self, db):
        response = ROUTER.create_service(schemas.ServiceCreateRequest(server_name="new.example.com", variables={}))

        assert response.status_code == 200
        assert db.save_config.call_args.args[0]["new.example.com_SERVER_NAME"] == "new.example.com"


class TestSharedServerName:
    def test_create_refuses_a_name_another_service_owns_as_its_id(self, db):
        response = ROUTER.create_service(schemas.ServiceCreateRequest(server_name="new.example.com", variables={"SERVER_NAME": f"new.example.com {OTHER}"}))

        assert response.status_code == 400
        assert OTHER in response.content["message"]
        db.save_config.assert_not_called()

    def test_create_refuses_a_name_another_service_owns_as_an_alias(self, db):
        response = ROUTER.create_service(
            schemas.ServiceCreateRequest(server_name="new.example.com", variables={"SERVER_NAME": "new.example.com alias.example.com"})
        )

        assert response.status_code == 400
        assert OTHER in response.content["message"]
        db.save_config.assert_not_called()

    def test_create_accepts_names_nobody_owns(self, db):
        response = ROUTER.create_service(
            schemas.ServiceCreateRequest(server_name="new.example.com", variables={"SERVER_NAME": "new.example.com fresh.example.com"})
        )

        assert response.status_code == 200
        db.save_config.assert_called_once()

    def test_rename_onto_an_alias_of_another_service_is_refused(self, db):
        response = ROUTER.update_service(SERVICE, schemas.ServiceUpdateRequest(server_name="alias.example.com"))

        assert response.status_code == 400
        assert OTHER in response.content["message"]
        db.save_config.assert_not_called()

    def test_rename_to_a_free_name_is_accepted(self, db):
        response = ROUTER.update_service(SERVICE, schemas.ServiceUpdateRequest(server_name="renamed.example.com"))

        assert response.status_code == 200
        db.save_config.assert_called_once()

    def test_an_edit_that_renames_nothing_is_not_blocked_by_a_legacy_shared_name(self, db):
        """A pre-existing clash between two siblings must not block an unrelated edit."""
        db.get_non_default_settings.return_value = {
            "SERVER_NAME": f"{SERVICE} {OTHER}",
            f"{SERVICE}_SERVER_NAME": f"{SERVICE} shared.example.com",
            f"{OTHER}_SERVER_NAME": f"{OTHER} shared.example.com",
        }

        response = ROUTER.update_service(SERVICE, schemas.ServiceUpdateRequest(variables={"USE_ANTIBOT": "captcha"}))

        assert response.status_code == 200
