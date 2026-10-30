from __future__ import annotations

import sys
from datetime import datetime, timezone
from inspect import signature
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import IsolatedAsyncioTestCase

from biscuit_auth import BiscuitBuilder, Fact, KeyPair
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [
    str(ROOT / "src/api"),
    str(ROOT / "src/common/utils"),
    str(ROOT / "src/api/utils"),
    str(ROOT / "src/common/db"),
    str(ROOT / "src/common"),
    str(ROOT / "src/deps/python"),
]

from app import utils as app_utils  # noqa: E402

KEY_DIR = TemporaryDirectory()
KEY_PAIR = KeyPair()
PUBLIC_KEY_FILE = Path(KEY_DIR.name) / "public.key"
PUBLIC_KEY_FILE.write_text(str(KEY_PAIR.public_key))
app_utils.BISCUIT_PUBLIC_KEY_FILE = PUBLIC_KEY_FILE

from app.config import api_config  # noqa: E402
from app.auth import biscuit as biscuit_auth  # noqa: E402
from app.routers import configs  # noqa: E402

VERSION = "1.6.15"
biscuit_auth.get_version = lambda: VERSION


class FakeDatabase:
    def __init__(self) -> None:
        self.config = {
            "service_id": "svc-a",
            "type": "http",
            "name": "snippet",
            "data": "old",
            "method": "api",
            "is_draft": False,
        }

    def get_config(self, **_kwargs):
        return {"SERVER_NAME": "svc-a svc-b"}

    def get_custom_config(self, config_type, name, *, service_id, with_data):
        if config_type != self.config["type"] or name != self.config["name"]:
            return None
        if service_id != self.config["service_id"]:
            return None
        return dict(self.config)

    def upsert_custom_config(self, _config_type, _name, values, *, service_id, new=False):
        if service_id != self.config["service_id"]:
            return "Source config changed during test"
        self.config = dict(values)
        return ""


class FakeUploadFile:
    filename = "snippet.conf"

    async def read(self) -> bytes:
        return b"new"


def biscuit_token(*resource_ids: str, admin: bool = False) -> str:
    builder = BiscuitBuilder(
        """
        user({user});
        time({time});
        client_ip({client_ip});
        domain({domain});
        version({version});
        """,
        {
            "user": "editor",
            "time": datetime.now(timezone.utc),
            "client_ip": "127.0.0.1",
            "domain": "testserver",
            "version": VERSION,
        },
    )
    builder.add_code('role({role}, ["read", "write"]);', {"role": "api_user"})
    if admin:
        builder.add_code("admin(true);")
    else:
        for resource_id in resource_ids:
            builder.add_fact(
                Fact(
                    "api_perm({rtype}, {rid}, {permission})",
                    {"rtype": "configs", "rid": resource_id, "permission": "config_update"},
                )
            )
    return builder.build(KEY_PAIR.private_key).to_base64()


class ConfigMoveAuthorizationTests(IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.database = FakeDatabase()
        self.original_get_db = configs.get_db
        self.original_api_token = api_config.API_TOKEN
        configs.get_db = lambda: self.database
        api_config.API_TOKEN = None

        self.app = FastAPI()
        self.app.include_router(configs.router)

    async def asyncTearDown(self) -> None:
        configs.get_db = self.original_get_db
        api_config.API_TOKEN = self.original_api_token

    def headers(self, *resource_ids: str, admin: bool = False) -> dict[str, str]:
        return {"Authorization": f"Bearer {biscuit_token(*resource_ids, admin=admin)}"}

    def request(self, path: str, headers: dict[str, str]) -> Request:
        return Request(
            {
                "type": "http",
                "method": "PATCH",
                "path": path,
                "raw_path": path.encode(),
                "query_string": b"",
                "headers": [(name.lower().encode(), value.encode()) for name, value in headers.items()],
                "client": ("127.0.0.1", 123),
                "server": ("testserver", 80),
                "scheme": "http",
                "root_path": "",
                "app": self.app,
                "state": {},
            }
        )

    async def authorize(self, request: Request) -> None:
        await configs.guard(request, None)

    def update_json(self, request: Request, body: dict[str, str]):
        update = configs.ConfigUpdateRequest.model_validate(body)
        args = ("svc-a", "http", "snippet", update)
        try:
            if "request" in signature(configs.update_config).parameters:
                return configs.update_config(*args, request=request)
            return configs.update_config(*args)
        except HTTPException as exc:
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    async def update_upload(self, request: Request, new_service: str):
        kwargs = {
            "service": "svc-a",
            "config_type": "http",
            "name": "snippet",
            "file": FakeUploadFile(),
            "new_service": new_service,
        }
        if "request" in signature(configs.update_config_upload).parameters:
            kwargs["request"] = request
        try:
            return await configs.update_config_upload(**kwargs)
        except HTTPException as exc:
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    async def test_json_move_requires_destination_grant(self) -> None:
        headers = self.headers("svc-a")
        request = self.request("/configs/svc-a/http/snippet", headers)
        await self.authorize(request)
        response = self.update_json(request, {"service": "svc-b", "data": "new"})

        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.database.config["service_id"], "svc-a")

    async def test_upload_move_requires_destination_grant(self) -> None:
        headers = self.headers("svc-a")
        request = self.request("/configs/svc-a/http/snippet/upload", headers)
        await self.authorize(request)
        response = await self.update_upload(request, "svc-b")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.database.config["service_id"], "svc-a")

    async def test_json_omitted_service_keeps_current_service(self) -> None:
        headers = self.headers("svc-a")
        request = self.request("/configs/svc-a/http/snippet", headers)
        await self.authorize(request)
        response = self.update_json(request, {"data": "new"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.database.config["service_id"], "svc-a")
        self.assertEqual(self.database.config["data"], "new")

    async def test_move_succeeds_with_both_service_grants(self) -> None:
        headers = self.headers("svc-a", "svc-b")
        request = self.request("/configs/svc-a/http/snippet", headers)
        await self.authorize(request)
        response = self.update_json(request, {"service": "svc-b", "data": "new"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.database.config["service_id"], "svc-b")

    async def test_admin_move_succeeds(self) -> None:
        api_config.API_TOKEN = "admin-token"
        headers = {"Authorization": "Bearer admin-token"}
        request = self.request("/configs/svc-a/http/snippet", headers)
        await self.authorize(request)
        response = self.update_json(request, {"service": "svc-b", "data": "new"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.database.config["service_id"], "svc-b")

    async def test_global_move_requires_global_grant(self) -> None:
        headers = self.headers("svc-a")
        request = self.request("/configs/svc-a/http/snippet", headers)
        await self.authorize(request)
        denied = self.update_json(request, {"service": "global", "data": "new"})
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(self.database.config["service_id"], "svc-a")

        headers = self.headers("svc-a", "global")
        request = self.request("/configs/svc-a/http/snippet", headers)
        await self.authorize(request)
        allowed = self.update_json(request, {"service": "global", "data": "new"})
        self.assertEqual(allowed.status_code, 200)
        self.assertIsNone(self.database.config["service_id"])
