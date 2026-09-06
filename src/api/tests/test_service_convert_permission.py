"""Real Biscuit authorization for the service conversion router's URL shape."""

from ast import Call, Constant, FunctionDef, parse, walk
from datetime import datetime, timezone
from pathlib import Path
from unittest import TestCase, main

from test_biscuit_run_limit import VERSION, _KEYPAIR, guard, make_request
from biscuit_auth import BiscuitBuilder
from fastapi import HTTPException
from app.auth.biscuit import _extract_resource_id, _resolve_resource_and_perm
from model import API_PERMISSION_ENUM, API_RESOURCE_ENUM


class TestServiceConvertPermission(TestCase):
    def token(self, permission, resource_id="*"):
        return (
            BiscuitBuilder(
                'version({version}); time({now}); client_ip("127.0.0.1"); api_perm("services", {resource_id}, {permission});',
                {"version": VERSION, "now": datetime.now(timezone.utc), "resource_id": resource_id, "permission": permission},
            )
            .build(_KEYPAIR.private_key)
            .to_base64()
        )

    def test_uses_actual_router_path_and_grantable_permission(self):
        source = Path(__file__).resolve().parents[1] / "app/routers/services.py"
        route = next(node for node in walk(parse(source.read_text())) if isinstance(node, FunctionDef) and node.name == "convert_service")
        decorator = next(node for node in route.decorator_list if isinstance(node, Call) and node.args and isinstance(node.args[0], Constant))
        path = "/services" + decorator.args[0].value.replace("{service}", "example.com")
        self.assertEqual(_resolve_resource_and_perm(path, "POST"), ("services", "service_convert"))
        self.assertIn("services", API_RESOURCE_ENUM.enums)
        self.assertIn("service_convert", API_PERMISSION_ENUM.enums)
        self.assertIsNone(guard(make_request(self.token("service_convert"), path, "POST")))
        with self.assertRaises(HTTPException) as error:
            guard(make_request(self.token("service_create"), path, "POST"))
        self.assertEqual(error.exception.status_code, 403)

    def test_scoped_grant_is_bound_to_the_service(self):
        for service in ("example.com", "convert", "export"):
            with self.subTest(service=service):
                path = f"/services/{service}/convert"
                self.assertEqual(_extract_resource_id(path, "services"), service)
                self.assertIsNone(guard(make_request(self.token("service_convert", service), path, "POST")))
                with self.assertRaises(HTTPException) as error:
                    guard(make_request(self.token("service_convert", "other.example"), path, "POST"))
                self.assertEqual(error.exception.status_code, 403)

    def test_route_normalization_and_crud_remain_unchanged(self):
        self.assertEqual(_resolve_resource_and_perm("/services/example.com/convert/", "post"), ("services", "service_convert"))
        for path, method, permission in (
            ("/services", "POST", "service_create"),
            ("/services/example.com", "GET", "service_read"),
            ("/services/example.com", "PUT", "service_update"),
            ("/services/example.com", "PATCH", "service_update"),
            ("/services/example.com", "DELETE", "service_delete"),
        ):
            with self.subTest(path=path, method=method):
                self.assertEqual(_resolve_resource_and_perm(path, method), ("services", permission))


if __name__ == "__main__":
    main()
