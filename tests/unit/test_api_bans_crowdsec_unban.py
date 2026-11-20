from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

from biscuit_auth import BiscuitBuilder, Fact, KeyPair
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [
    str(ROOT / "src/api"),
    str(ROOT / "src/common/utils"),
    str(ROOT / "src/api/utils"),
    str(ROOT / "src/common/api"),
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
from app.routers import bans  # noqa: E402
from app.schemas import UnbanRequest  # noqa: E402
from CrowdSec import CrowdSecError  # noqa: E402
import crowdsec_unban  # noqa: E402

VERSION = "1.6.15"
biscuit_auth.get_version = lambda: VERSION

SOURCE = "src-conn"
OTHER = "other-conn"
KEYS = [f"{SOURCE}:11", f"{OTHER}:12"]


def make_preview(connections=(SOURCE, OTHER), keys=KEYS):
    return {
        "lease": {"ip": "1.2.3.4", "ban_scope": "global", "service": None, "exp": 30},
        "source": {"connection_id": SOURCE, "instance": "bw1"},
        "connections": list(connections),
        "unavailable": [],
        "decisions": [{"key": key, "connection_id": key.split(":")[0], "id": int(key.split(":")[1])} for key in keys],
        "warnings": {"list_origin": False, "range": False},
        "management_missing": [],
    }


def biscuit_token(grants: dict[str, list[str]]) -> str:
    builder = BiscuitBuilder(
        """
        user({user});
        time({time});
        client_ip({client_ip});
        domain({domain});
        version({version});
        """,
        {
            "user": "operator",
            "time": datetime.now(timezone.utc),
            "client_ip": "127.0.0.1",
            "domain": "testserver",
            "version": VERSION,
        },
    )
    builder.add_code('role({role}, ["read", "write"]);', {"role": "api_user"})
    for resource_id, permissions in grants.items():
        for permission in permissions:
            builder.add_fact(Fact("api_perm({rtype}, {rid}, {permission})", {"rtype": "bans", "rid": resource_id, "permission": permission}))
    return builder.build(KEY_PAIR.private_key).to_base64()


class FakeCaller:
    def __init__(self, bans_rows=None, bans_ok=True):
        self.calls = []
        self.bans_rows = bans_rows or []
        self.bans_ok = bans_ok

    def send_to_apis(self, method, url, data=None, response=False, **_kwargs):
        self.calls.append((method, url, data))
        if method == "GET" and url == "/bans":
            return self.bans_ok, {"bw1": {"status": "success", "data": self.bans_rows}}
        return True, None

    @property
    def writes(self):
        return [call for call in self.calls if call[0] != "GET"]


class BansCrowdSecUnbanTests(IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.original_api_token = api_config.API_TOKEN
        api_config.API_TOKEN = None
        self.previews = []
        self.applied = []
        self.revalidated = []
        self.apply_result = {"status": "success", "deleted": KEYS, "failed": [], "down": [], "unavailable": []}

        def fake_preview(_client, ip, ban_scope, service):
            if isinstance(self.preview_value, Exception):
                raise self.preview_value
            self.previews.append((ip, ban_scope, service))
            return self.preview_value

        self.preview_value = make_preview()
        self.lease = {"reason_data": {"instance": "bw1"}}
        self.lease_error = None

        def fake_find_lease(_client, _ip, _ban_scope, _service):
            if self.lease_error:
                raise self.lease_error
            return self.lease

        def fake_apply(_client, ip, ban_scope, service, current):
            self.applied.append((ip, ban_scope, service, current))
            return dict(self.apply_result)

        def real_revalidate(client, ip, ban_scope, service, keys, allowed_connections=None):
            self.revalidated.append((ip, ban_scope, service, list(keys), allowed_connections))
            return crowdsec_unban.revalidate(client, ip, ban_scope, service, keys, allowed_connections)

        self.patches = [
            patch.object(bans, "get_db", lambda **_kw: object()),
            patch.object(bans, "CrowdSecClient", lambda _db: object()),
            patch.object(bans, "preview", fake_preview),
            patch.object(crowdsec_unban, "preview", fake_preview),
            patch.object(bans, "find_lease", fake_find_lease),
            patch.object(bans, "apply", fake_apply),
            patch.object(bans, "revalidate", real_revalidate),
        ]
        for item in self.patches:
            item.start()

    async def asyncTearDown(self) -> None:
        for item in self.patches:
            item.stop()
        api_config.API_TOKEN = self.original_api_token

    async def make_request(self, grants=None, admin=False) -> Request:
        headers = [] if admin else [(b"authorization", f"Bearer {biscuit_token(grants or {})}".encode())]
        request = Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/bans/unban",
                "raw_path": b"/bans/unban",
                "query_string": b"",
                "headers": headers,
                "client": ("127.0.0.1", 123),
                "server": ("testserver", 80),
                "scheme": "http",
                "root_path": "",
                "state": {},
            }
        )
        if admin:
            request.state.auth_admin = True
        else:
            await bans.guard(request, None)
        return request

    def call(self, items, request, caller=None):
        caller = caller or FakeCaller()
        self.caller = caller
        try:
            response = bans.unban([UnbanRequest(**item) for item in items], request, caller)
        except HTTPException as exc:
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
        return response

    @staticmethod
    def body(response) -> dict:
        import json

        return json.loads(response.body)

    def lease_item(self, **extra):
        return {"ip": "1.2.3.4", "kind": "crowdsec_lease", **extra}

    def confirmed_item(self, **extra):
        return self.lease_item(remove_crowdsec_decisions=True, confirmed=True, decision_keys=list(KEYS), **extra)

    async def test_lease_without_flags_gets_a_conflict_with_the_preview(self) -> None:
        request = await self.make_request({"*": ["ban_delete", "crowdsec_delete"]})
        response = self.call([self.lease_item()], request)

        self.assertEqual(response.status_code, 409)
        body = self.body(response)
        self.assertEqual(body["status"], "error")
        self.assertEqual(body["preview"]["decisions"][0]["key"], KEYS[0])
        self.assertIn("confirmed", body["message"])
        self.assertEqual(self.applied, [])
        self.assertEqual(self.caller.writes, [])

    async def test_lease_with_flags_but_no_keys_gets_a_conflict(self) -> None:
        request = await self.make_request(admin=True)
        response = self.call([self.lease_item(remove_crowdsec_decisions=True, confirmed=True)], request)

        self.assertEqual(response.status_code, 409)
        self.assertIn("preview", self.body(response))
        self.assertEqual(self.applied, [])

    async def test_unauthorized_token_gets_403_without_preview_and_no_write(self) -> None:
        request = await self.make_request({"*": ["ban_delete"]})
        response = self.call([self.confirmed_item()], request)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.body(response), {"detail": "Forbidden"})
        self.assertEqual(self.applied, [])
        self.assertEqual(self.revalidated, [])
        self.assertEqual(self.caller.writes, [])

    async def test_unauthorized_token_gets_403_even_without_flags(self) -> None:
        request = await self.make_request({"*": ["ban_delete"]})
        response = self.call([self.lease_item()], request)

        self.assertEqual(response.status_code, 403)
        self.assertNotIn("preview", self.body(response))

    async def test_one_unauthorized_connection_denies_the_whole_request(self) -> None:
        request = await self.make_request({"*": ["ban_delete"], SOURCE: ["crowdsec_delete"]})
        response = self.call([self.confirmed_item()], request)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.applied, [])

    async def test_unavailable_connection_without_identity_needs_wildcard_before_any_disclosure(self) -> None:
        self.preview_value = make_preview() | {"unavailable": ["instance:bw9"]}
        request = await self.make_request({"*": ["ban_delete"], SOURCE: ["crowdsec_delete"], OTHER: ["crowdsec_delete"]})
        response = self.call([self.lease_item()], request)

        self.assertEqual(response.status_code, 403)
        self.assertNotIn("preview", self.body(response))
        self.assertEqual(self.applied, [])

    async def test_unavailable_connection_with_identity_must_be_authorized(self) -> None:
        self.preview_value = make_preview() | {"unavailable": ["down-conn"], "unavailable_ids": ["down-conn"]}
        request = await self.make_request({"*": ["ban_delete"], SOURCE: ["crowdsec_delete"], OTHER: ["crowdsec_delete"]})
        response = self.call([self.lease_item()], request)
        self.assertEqual(response.status_code, 403)
        self.assertNotIn("preview", self.body(response))

        granted = await self.make_request({"*": ["ban_delete"], SOURCE: ["crowdsec_delete"], OTHER: ["crowdsec_delete"], "down-conn": ["crowdsec_delete"]})
        response = self.call([self.lease_item()], granted)
        self.assertEqual(response.status_code, 409)
        self.assertIn("preview", self.body(response))

    async def test_unavailable_connection_appearing_between_preview_and_execute_is_a_conflict(self) -> None:
        request = await self.make_request({"*": ["ban_delete"], SOURCE: ["crowdsec_delete"], OTHER: ["crowdsec_delete"]})
        calls = []

        def drifting_preview(_client, _ip, _ban_scope, _service):
            calls.append(1)
            return make_preview() if len(calls) == 1 else make_preview() | {"unavailable": ["instance:bw9"]}

        with patch.object(bans, "preview", drifting_preview), patch.object(crowdsec_unban, "preview", drifting_preview):
            response = self.call([self.confirmed_item()], request)

        self.assertEqual(response.status_code, 409)
        self.assertNotIn("preview", self.body(response))
        self.assertEqual(self.applied, [])
        self.assertEqual(self.caller.writes, [])

    async def test_connection_appearing_between_preview_and_execute_is_a_conflict(self) -> None:
        request = await self.make_request({"*": ["ban_delete"], SOURCE: ["crowdsec_delete"], OTHER: ["crowdsec_delete"]})
        calls = []

        def drifting_preview(_client, _ip, _ban_scope, _service):
            calls.append(1)
            return make_preview() if len(calls) == 1 else make_preview(connections=(SOURCE, OTHER, "new-conn"))

        with patch.object(bans, "preview", drifting_preview), patch.object(crowdsec_unban, "preview", drifting_preview):
            response = self.call([self.confirmed_item()], request)

        self.assertEqual(response.status_code, 409)
        body = self.body(response)
        self.assertEqual(body["status"], "error")
        self.assertNotIn("preview", body)
        self.assertEqual(self.applied, [])
        self.assertEqual(self.caller.writes, [])

    async def test_changed_selection_is_a_conflict_with_the_new_preview(self) -> None:
        request = await self.make_request(admin=True)
        response = self.call([self.lease_item(remove_crowdsec_decisions=True, confirmed=True, decision_keys=[KEYS[0]])], request)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(sorted(d["key"] for d in self.body(response)["preview"]["decisions"]), sorted(KEYS))
        self.assertEqual(self.applied, [])

    async def test_granted_token_with_matching_keys_succeeds(self) -> None:
        request = await self.make_request({"*": ["ban_delete", "crowdsec_delete"]})
        response = self.call([self.confirmed_item()], request)

        self.assertEqual(response.status_code, 200)
        body = self.body(response)
        self.assertEqual(body["status"], "success")
        self.assertEqual(body["results"][0]["status"], "success")
        self.assertEqual(body["results"][0]["ip"], "1.2.3.4")
        self.assertEqual(len(self.applied), 1)
        self.assertEqual(self.revalidated[0][4], {SOURCE, OTHER})

    async def test_admin_revalidates_without_a_connection_filter(self) -> None:
        request = await self.make_request(admin=True)
        response = self.call([self.confirmed_item()], request)

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(self.revalidated[0][4])

    async def test_partial_apply_is_a_502(self) -> None:
        self.apply_result = {"status": "partial", "deleted": [], "failed": [{"key": KEYS[0], "error": "boom"}], "down": [], "unavailable": []}
        request = await self.make_request(admin=True)
        response = self.call([self.confirmed_item()], request)

        self.assertEqual(response.status_code, 502)
        body = self.body(response)
        self.assertEqual(body["status"], "error")
        self.assertEqual(body["results"][0]["status"], "partial")

    async def test_prepare_barrier_applies_nothing_when_a_later_item_changed(self) -> None:
        request = await self.make_request(admin=True)
        second = self.confirmed_item()
        second["ip"] = "5.6.7.8"
        second["decision_keys"] = [KEYS[0]]  # stale selection
        response = self.call([self.confirmed_item(), second], request)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.applied, [])
        self.assertEqual(self.caller.writes, [])

    async def test_preview_failure_reaches_an_authorized_caller_and_hides_from_others(self) -> None:
        self.preview_value = CrowdSecError("No CrowdSec ban found for this IP", 404)
        granted = await self.make_request({"*": ["ban_delete", "crowdsec_delete"]})
        response = self.call([self.confirmed_item()], granted)
        self.assertEqual(response.status_code, 404)
        self.assertIn("No CrowdSec ban", self.body(response)["message"])

        denied = await self.make_request({"*": ["ban_delete"]})
        response = self.call([self.confirmed_item()], denied)
        self.assertEqual(response.status_code, 403)

    async def test_explicit_ban_keeps_the_old_path_and_body(self) -> None:
        self.lease = None
        request = await self.make_request({"*": ["ban_delete"]})
        response = self.call([{"ip": "1.2.3.4", "service": "www.example.com"}], request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.body(response), {"status": "success"})
        self.assertEqual(self.caller.writes, [("POST", "/unban", {"ip": "1.2.3.4", "service": "www.example.com", "ban_scope": "service"})])

    async def test_explicit_ban_never_sends_lease_flags_to_the_instances(self) -> None:
        self.lease = None
        request = await self.make_request({"*": ["ban_delete"]})
        self.call([{"ip": "1.2.3.4", "confirmed": True, "decision_keys": ["a"]}], request)

        sent = self.caller.writes[0][2]
        self.assertEqual(sorted(sent), ["ban_scope", "ip"])

    async def test_kind_ban_on_a_lease_without_an_explicit_ban_asks_for_the_flags(self) -> None:
        caller = FakeCaller(bans_rows=[{"kind": "crowdsec_lease", "ip": "1.2.3.4", "ban_scope": "global"}])
        request = await self.make_request({"*": ["ban_delete", "crowdsec_delete"]})
        response = self.call([{"ip": "1.2.3.4"}], request, caller)

        self.assertEqual(response.status_code, 409)
        self.assertIn("preview", self.body(response))
        self.assertEqual(caller.writes, [])

    async def test_kind_ban_on_a_lease_is_denied_before_any_disclosure(self) -> None:
        caller = FakeCaller(bans_rows=[{"kind": "crowdsec_lease", "ip": "1.2.3.4", "ban_scope": "global"}])
        request = await self.make_request({"*": ["ban_delete"]})
        response = self.call([{"ip": "1.2.3.4"}], request, caller)

        self.assertEqual(response.status_code, 403)
        self.assertNotIn("preview", self.body(response))
        self.assertEqual(caller.writes, [])

    async def test_explicit_ban_wins_and_the_lease_remains(self) -> None:
        rows = [{"kind": "ban", "ip": "1.2.3.4", "ban_scope": "global"}, {"kind": "crowdsec_lease", "ip": "1.2.3.4", "ban_scope": "global"}]
        caller = FakeCaller(bans_rows=rows)
        request = await self.make_request({"*": ["ban_delete"]})
        response = self.call([{"ip": "1.2.3.4"}], request, caller)

        self.assertEqual(response.status_code, 200)
        body = self.body(response)
        self.assertTrue(body["results"][0]["lease_remains"])
        self.assertEqual(len(caller.writes), 1)

    async def test_incomplete_lease_lookup_still_unbans_and_never_reports_success(self) -> None:
        self.lease_error = CrowdSecError("Could not check every instance for a CrowdSec ban: bw2: down", 502)
        request = await self.make_request({"*": ["ban_delete"]})
        response = self.call([{"ip": "1.2.3.4"}], request)

        self.assertEqual(response.status_code, 502)
        body = self.body(response)
        self.assertEqual(body["status"], "error")
        self.assertEqual(body["results"][0]["lease_check"], "incomplete")
        self.assertEqual(len(self.caller.writes), 1)

    async def test_unreadable_ban_listing_counts_as_an_incomplete_check(self) -> None:
        caller = FakeCaller(bans_ok=False)
        request = await self.make_request({"*": ["ban_delete"]})
        response = self.call([{"ip": "1.2.3.4"}], request, caller)

        self.assertEqual(response.status_code, 502)
        self.assertEqual(self.body(response)["results"][0]["lease_check"], "incomplete")
        self.assertEqual(len(caller.writes), 1)

    async def test_schema_defaults(self) -> None:
        item = UnbanRequest(ip="1.2.3.4")
        self.assertEqual((item.kind, item.remove_crowdsec_decisions, item.confirmed, item.decision_keys), ("ban", False, False, None))
        with self.assertRaises(ValueError):
            UnbanRequest(ip="1.2.3.4", kind="other")
