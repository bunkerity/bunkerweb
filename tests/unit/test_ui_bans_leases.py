"""Web UI bans back end: CrowdSec leases are listed next to explicit bans and unbanned through the shared flow."""

import sys
import unittest
from json import dumps
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch

REPO = Path(__file__).resolve().parents[2]
for path in ("src/ui", "src/common/utils", "src/common/db", "src/common/api"):
    sys.path.insert(0, str(REPO / path))

from flask import Flask  # noqa: E402

# app.dependencies builds the database at import time: replace it for the import only
deps = ModuleType("app.dependencies")
for name in ("BW_CONFIG", "BW_INSTANCES_UTILS", "DB", "DATA", "CONFIG_TASKS_EXECUTOR"):
    setattr(deps, name, MagicMock())
with patch.dict(sys.modules, {"app.dependencies": deps}):
    import app.models.instance as instance_module  # noqa: E402
    import app.routes.bans as bans_module  # noqa: E402

# the module is imported under patch.dict, so take the class the routes catch
CrowdSecError = bans_module.CrowdSecError

LEASE_DATA = {"reason": "crowdsec", "date": 1000, "country": "FR", "kind": "crowdsec_lease", "reason_data": {"instance": "bw-1", "connection": "main"}}


def lease(ip="1.2.3.4", ban_scope="global", service=None, exp=30):
    return {
        "ip": ip,
        "ban_scope": ban_scope,
        "service": service or "unknown",
        "exp": exp,
        "date": 1000,
        "reason": "crowdsec",
        "kind": "crowdsec_lease",
        "reason_data": {"instance": "bw-1", "connection": "main"},
    }


def explicit(ip="1.2.3.4", ban_scope="global", service="_", exp=3600, **extra):
    return {"ip": ip, "ban_scope": ban_scope, "service": service, "exp": exp, "date": 1000, "reason": "manual", **extra}


class HelpersTest(unittest.TestCase):
    def test_identity_includes_kind_and_defaults_to_ban(self):
        self.assertEqual(bans_module._ban_identity(explicit()), ("1.2.3.4", "global", "_", "ban"))
        self.assertEqual(bans_module._ban_identity(lease(service="svc", ban_scope="service")), ("1.2.3.4", "service", "svc", "crowdsec_lease"))
        self.assertNotEqual(bans_module._ban_identity(explicit(service="unknown")), bans_module._ban_identity(lease()))

    def test_ban_id_separates_a_lease_from_an_explicit_ban(self):
        self.assertNotEqual(bans_module._ban_id(explicit()), bans_module._ban_id(lease()))
        self.assertEqual(bans_module._ban_id(explicit(service="whatever")), bans_module._ban_id(explicit(service="_")))

    def test_collect_keeps_a_lease_and_an_explicit_ban_for_the_same_ip(self):
        merged = bans_module._merge_instance_bans([], [explicit(service="unknown"), lease(), lease()])
        self.assertEqual(sorted(row.get("kind", "ban") for row in merged), ["ban", "crowdsec_lease"])

    def test_collect_prefers_the_redis_row_over_the_instance_copy_of_the_same_identity(self):
        redis_row = explicit(service="unknown", reason="from-redis")
        merged = bans_module._merge_instance_bans([redis_row], [explicit(service="unknown", reason="from-instance"), lease()])
        self.assertEqual([row["reason"] for row in merged if row.get("kind", "ban") == "ban"], ["from-redis"])
        self.assertEqual(len(merged), 2)

    def test_collect_derives_a_missing_scope(self):
        merged = bans_module._merge_instance_bans([], [{"ip": "1.1.1.1", "service": "_"}, {"ip": "1.1.1.1", "service": "svc"}])
        self.assertEqual(sorted(row["ban_scope"] for row in merged), ["global", "service"])

    def test_format_ban_exposes_kind_and_the_crowdsec_source(self):
        row = bans_module.format_ban(lease())
        self.assertEqual((row["kind"], row["cs_node"], row["cs_connection"]), ("crowdsec_lease", "bw-1", "main"))
        plain = bans_module.format_ban(explicit())
        self.assertEqual((plain["kind"], plain["cs_node"], plain["cs_connection"]), ("ban", "", ""))

    def test_format_ban_escapes_the_crowdsec_source(self):
        row = lease()
        row["reason_data"] = {"instance": "<b>x</b>", "connection": '"q"'}
        formatted = bans_module.format_ban(row)
        self.assertNotIn("<", formatted["cs_node"])
        self.assertNotIn('"', formatted["cs_connection"])

    def test_format_ban_ignores_reason_data_that_is_not_a_lease_source(self):
        row = explicit(reason_data={"instance": "bw-1", "connection": "main"})
        formatted = bans_module.format_ban(row)
        self.assertEqual((formatted["cs_node"], formatted["cs_connection"]), ("", ""))
        row = lease()
        row["reason_data"] = "not a dict"
        self.assertEqual(bans_module.format_ban(row)["cs_node"], "")

    def test_redis_lease_rows_parse_both_key_shapes(self):
        scan = [
            (b"bans_cs_ip_1.2.3.4", dumps(LEASE_DATA).encode(), 25),
            (b"bans_cs_service_www.example.com_ip_5.6.7.8", dumps(LEASE_DATA).encode(), 20),
        ]
        rows = {(row["ip"], row["ban_scope"], row["service"]): row for row in bans_module._redis_lease_rows(scan)}
        self.assertEqual(set(rows), {("1.2.3.4", "global", "unknown"), ("5.6.7.8", "service", "www.example.com")})
        for row in rows.values():
            self.assertEqual(row["kind"], "crowdsec_lease")
            self.assertFalse(row["permanent"])
        self.assertEqual(rows[("5.6.7.8", "service", "www.example.com")]["exp"], 20)

    def test_redis_lease_rows_split_at_the_last_ip_marker_and_strip_cluster_tags(self):
        scan = [
            ("bans_cs_service_a_ip_b.example.com_ip_{1.2.3.4}", dumps(LEASE_DATA), 10),
            ("bans_cs_ip_{2001:db8::1}", dumps(LEASE_DATA), 10),
            ("bans_cs_service_%7Bweird%7D.example_ip_{9.9.9.9}", dumps(LEASE_DATA), 10),
        ]
        rows = bans_module._redis_lease_rows(scan)
        self.assertEqual(
            [(r["ip"], r["ban_scope"], r["service"]) for r in rows],
            [
                ("1.2.3.4", "service", "a_ip_b.example.com"),
                ("2001:db8::1", "global", "unknown"),
                ("9.9.9.9", "service", "{weird}.example"),
            ],
        )

    def test_redis_lease_rows_skip_empty_unreadable_and_foreign_keys(self):
        scan = [
            (b"bans_cs_ip_1.1.1.1", None, 5),
            (b"bans_cs_ip_2.2.2.2", b"not json", 5),
            (b"bans_cs_ip_3.3.3.3", b'"a string"', 5),
            (b"bans_ip_4.4.4.4", dumps(LEASE_DATA).encode(), 5),
        ]
        self.assertEqual(bans_module._redis_lease_rows(scan), [])

    def test_instances_get_bans_keeps_a_lease_and_an_explicit_ban_apart(self):
        rows = [explicit(service="unknown", exp=100), lease(exp=30), lease(exp=50), explicit(service="unknown", exp=200)]
        fake = SimpleNamespace(_gather_from_instances=lambda instances, collect: rows, get_instances=lambda status: [])
        result = instance_module.InstancesUtils.get_bans(fake, instances=[object()])
        self.assertEqual(sorted((row.get("kind", "ban"), row["exp"]) for row in result), [("ban", 100), ("crowdsec_lease", 30)])


def make_app():
    app = Flask("bans-test", template_folder=str(REPO / "src" / "ui" / "app" / "templates"))
    app.secret_key = "test"
    app.config["LOGIN_DISABLED"] = True
    app.add_url_rule("/loading", "loading", lambda: "")
    app.register_blueprint(bans_module.bans)
    return app


ADMIN = SimpleNamespace(admin=True, list_permissions=["write"], get_id=lambda: "admin")
READER = SimpleNamespace(admin=False, list_permissions=["read"], get_id=lambda: "reader")
ADMIN_READ_ONLY = SimpleNamespace(admin=True, list_permissions=["read"], get_id=lambda: "ro")

PREVIEW = {"lease": {}, "source": {}, "connections": ["c1"], "unavailable": [], "decisions": [{"key": "c1:7"}], "warnings": {}, "management_missing": []}


class RouteCase(unittest.TestCase):
    user = ADMIN

    def setUp(self):
        self.app = make_app()
        self.client = self.app.test_client()
        self.flashes = []
        self.instances = MagicMock()
        self.instances.unban.return_value = None
        self.instances.ban.return_value = None
        self.instances.get_bans.return_value = []
        db = MagicMock(readonly=False)
        record = lambda message, category="success", **kw: self.flashes.append((category, message))  # noqa: E731
        patches = [
            patch.object(bans_module, "current_user", self.user),
            patch.object(bans_module, "flash", record),
            # handle_error flashes through its own module
            patch.dict(bans_module.handle_error.__globals__, {"flash": record}),
            patch.object(bans_module, "BW_INSTANCES_UTILS", self.instances),
            patch.object(bans_module, "DB", db),
            patch.object(bans_module, "CrowdSecClient", MagicMock()),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.db = db

    def flashed(self, category):
        return [message for cat, message in self.flashes if cat == category]


class PreviewRouteTest(RouteCase):
    def post(self, body):
        return self.client.post("/bans/crowdsec_preview", json=body)

    def test_denies_non_admin_and_missing_write_permission(self):
        for user in (READER, ADMIN_READ_ONLY):
            with patch.object(bans_module, "current_user", user), patch.object(bans_module, "crowdsec_preview_data") as fake:
                self.assertEqual(self.post({"ip": "1.2.3.4", "ban_scope": "global"}).status_code, 403)
                fake.assert_not_called()

    def test_refuses_a_read_only_database(self):
        self.db.readonly = True
        with patch.object(bans_module, "crowdsec_preview_data") as fake:
            self.assertEqual(self.post({"ip": "1.2.3.4", "ban_scope": "global"}).status_code, 423)
            fake.assert_not_called()

    def test_returns_the_preview_json(self):
        with patch.object(bans_module, "crowdsec_preview_data", return_value=PREVIEW) as fake:
            response = self.post({"ip": "1.2.3.4", "ban_scope": "service", "service": "www.example.com"})
        self.assertEqual((response.status_code, response.get_json()), (200, PREVIEW))
        self.assertEqual(fake.call_args.args[1:], ("1.2.3.4", "service", "www.example.com"))

    def test_a_reserved_service_name_becomes_the_global_scope(self):
        with patch.object(bans_module, "crowdsec_preview_data", return_value=PREVIEW) as fake:
            self.post({"ip": "1.2.3.4", "ban_scope": "service", "service": "unknown"})
        self.assertEqual(fake.call_args.args[1:], ("1.2.3.4", "global", None))

    def test_crowdsec_errors_keep_their_status(self):
        for status in (404, 409, 502):
            with patch.object(bans_module, "crowdsec_preview_data", side_effect=CrowdSecError("nope", status)):
                response = self.post({"ip": "1.2.3.4", "ban_scope": "global"})
            self.assertEqual((response.status_code, response.get_json()), (status, {"error": "nope"}))

    def test_rejects_a_bad_body_without_calling_crowdsec(self):
        with patch.object(bans_module, "crowdsec_preview_data") as fake:
            for body in ({"ip": "nope", "ban_scope": "global"}, {"ban_scope": "global"}, {"ip": "1.2.3.4", "ban_scope": "service"}, ["x"]):
                self.assertEqual(self.post(body).status_code, 400, body)
            fake.assert_not_called()


def unban_form(unbans, **extra):
    return {"ips": dumps(unbans), **extra}


class UnbanRouteTest(RouteCase):
    def setUp(self):
        super().setUp()
        self.calls = []
        self.results = {}

        def revalidate(client, ip, ban_scope, service, keys, allowed=None):
            self.calls.append(("revalidate", ip, ban_scope, service, list(keys), allowed))
            return self.results.get(("revalidate", ip), {"status": "ready", "preview": {"ip": ip}})

        def apply(client, ip, ban_scope, service, current):
            self.calls.append(("apply", ip, ban_scope, service))
            return self.results.get(("apply", ip), {"status": "success", "failed": [], "lease_failed": [], "unavailable": [], "down": []})

        for p in (patch.object(bans_module, "crowdsec_revalidate", revalidate), patch.object(bans_module, "crowdsec_apply", apply)):
            p.start()
            self.addCleanup(p.stop)

    def post(self, unbans, **extra):
        return self.client.post("/bans/unban", data=unban_form(unbans, **extra))

    def test_explicit_items_keep_the_old_path(self):
        response = self.post([{"ip": "1.2.3.4", "ban_scope": "global"}, {"ip": "5.6.7.8", "ban_scope": "service", "service": "svc", "kind": "ban"}])
        self.assertEqual(response.status_code, 302)
        self.assertEqual([c.args for c in self.instances.unban.call_args_list], [("1.2.3.4", None, "global"), ("5.6.7.8", "svc", "service")])
        self.assertEqual(self.calls, [])

    def test_a_lease_item_without_confirmation_changes_nothing(self):
        self.post([{"ip": "1.2.3.4", "ban_scope": "global", "kind": "crowdsec_lease"}, {"ip": "9.9.9.9", "ban_scope": "global"}])
        self.assertEqual(self.calls, [])
        self.instances.unban.assert_not_called()
        self.assertTrue(self.flashed("error"))

    def test_a_non_admin_cannot_unban_a_lease(self):
        for user in (READER, ADMIN_READ_ONLY):
            self.calls.clear()
            self.flashes.clear()
            with patch.object(bans_module, "current_user", user):
                self.post([{"ip": "1.2.3.4", "ban_scope": "global", "kind": "crowdsec_lease"}], crowdsec_confirmed="yes")
            self.assertEqual(self.calls, [])
            self.instances.unban.assert_not_called()
            self.assertTrue(self.flashed("error"))

    def test_every_item_is_revalidated_before_the_first_mutation(self):
        selection = {"1.1.1.1|global|_": ["c1:7"], "2.2.2.2|service|svc": []}
        self.post(
            [
                {"ip": "1.1.1.1", "ban_scope": "global", "kind": "crowdsec_lease"},
                {"ip": "2.2.2.2", "ban_scope": "service", "service": "svc", "kind": "crowdsec_lease"},
                {"ip": "3.3.3.3", "ban_scope": "global"},
            ],
            crowdsec_confirmed="yes",
            crowdsec_selection=dumps(selection),
        )
        self.assertEqual(
            self.calls,
            [
                ("revalidate", "1.1.1.1", "global", None, ["c1:7"], None),
                ("revalidate", "2.2.2.2", "service", "svc", [], None),
                ("apply", "1.1.1.1", "global", None),
                ("apply", "2.2.2.2", "service", "svc"),
            ],
        )
        self.instances.unban.assert_called_once()
        self.assertEqual(len(self.flashed("success")), 3)

    def test_the_selection_key_ignores_a_displayed_reserved_service_name(self):
        self.post(
            [{"ip": "1.1.1.1", "ban_scope": "global", "service": "unknown", "kind": "crowdsec_lease"}],
            crowdsec_confirmed="yes",
            crowdsec_selection=dumps({"1.1.1.1|global|unknown": ["c1:7"]}),
        )
        self.assertEqual(self.calls[0], ("revalidate", "1.1.1.1", "global", None, ["c1:7"], None))

    def test_a_changed_item_blocks_every_mutation(self):
        self.results[("revalidate", "2.2.2.2")] = {"status": "changed", "preview": {}}
        self.post(
            [
                {"ip": "1.1.1.1", "ban_scope": "global", "kind": "crowdsec_lease"},
                {"ip": "2.2.2.2", "ban_scope": "global", "kind": "crowdsec_lease"},
                {"ip": "3.3.3.3", "ban_scope": "global"},
            ],
            crowdsec_confirmed="yes",
        )
        self.assertEqual([c[0] for c in self.calls], ["revalidate", "revalidate"])
        self.instances.unban.assert_not_called()
        self.assertEqual(self.flashed("error"), ["The CrowdSec decisions changed, review the Unban again"])

    def test_a_crowdsec_error_during_revalidation_blocks_every_mutation(self):
        def boom(*args, **kwargs):
            raise CrowdSecError("No CrowdSec ban found for this IP", 404)

        with patch.object(bans_module, "crowdsec_revalidate", boom):
            self.post([{"ip": "1.1.1.1", "ban_scope": "global", "kind": "crowdsec_lease"}, {"ip": "3.3.3.3", "ban_scope": "global"}], crowdsec_confirmed="yes")
        self.instances.unban.assert_not_called()
        self.assertEqual(self.calls, [])
        self.assertTrue(any("No CrowdSec ban found" in message for message in self.flashed("error")))

    def test_a_partial_result_lists_the_failures_and_says_the_ban_stays(self):
        self.results[("apply", "1.1.1.1")] = {
            "status": "partial",
            "failed": [{"key": "c1:7", "error": "boom"}],
            "lease_failed": [{"instance": "bw-2", "error": "502"}],
            "unavailable": ["c9"],
            "down": ["bw-3"],
        }
        self.post([{"ip": "1.1.1.1", "ban_scope": "global", "kind": "crowdsec_lease"}], crowdsec_confirmed="yes")
        errors = self.flashed("error")
        self.assertEqual(len(errors), 1)
        for needle in ("1.1.1.1", "c1:7", "boom", "bw-2", "c9", "bw-3", "ban stays"):
            self.assertIn(needle, errors[0])
        self.assertEqual(self.flashed("success"), [])

    def test_a_filtered_selection_skips_leases_with_one_warning(self):
        with patch.object(bans_module, "_get_filtered_bans", return_value=[lease("1.1.1.1"), lease("2.2.2.2"), explicit("3.3.3.3")]):
            self.client.post("/bans/unban", data={"selection_mode": "filtered", "source": "bans"})
        self.assertEqual(self.calls, [])
        self.assertEqual([c.args[0] for c in self.instances.unban.call_args_list], ["3.3.3.3"])
        self.assertEqual(len(self.flashed("warning")), 1)

    def test_the_ips_field_is_still_read(self):
        self.assertEqual(self.client.post("/bans/unban", data={}).status_code, 302)
        self.instances.unban.assert_not_called()


class DurationRouteTest(RouteCase):
    def post(self, updates):
        return self.client.post("/bans/update_duration", data={"updates": dumps(updates)})

    def test_refuses_a_lease_and_mutates_nothing(self):
        self.post(
            [{"ip": "9.9.9.9", "duration": "1h", "ban_scope": "global"}, {"ip": "1.2.3.4", "duration": "1h", "ban_scope": "global", "kind": "crowdsec_lease"}]
        )
        self.instances.ban.assert_not_called()
        self.assertEqual(self.flashed("error"), ["CrowdSec bans follow their CrowdSec decision and cannot be edited"])

    def test_keeps_the_original_reason_of_the_explicit_ban_next_to_a_lease(self):
        self.instances.get_bans.return_value = [lease(), explicit(reason="manual")]
        self.post([{"ip": "1.2.3.4", "duration": "1h", "ban_scope": "global"}])
        self.assertEqual(self.instances.ban.call_args.args[:3], ("1.2.3.4", 3600, "manual"))

    def test_a_filtered_selection_skips_leases(self):
        with patch.object(bans_module, "_get_filtered_bans", return_value=[lease("1.1.1.1"), explicit("3.3.3.3", reason="r")]):
            self.client.post("/bans/update_duration", data={"selection_mode": "filtered", "source": "bans", "duration": "1h"})
        self.assertEqual([c.args[0] for c in self.instances.ban.call_args_list], ["3.3.3.3"])
        self.assertEqual(len(self.flashed("warning")), 1)


if __name__ == "__main__":
    unittest.main()
