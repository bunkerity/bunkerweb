import sys
from pathlib import Path
from unittest import TestCase, main
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parents[2]
for source_dir in (REPO_ROOT / "src/common/cli", REPO_ROOT / "src/common/api", REPO_ROOT / "src/common/utils"):
    sys.path.insert(0, str(source_dir))

import CLI as cli_module  # noqa: E402
from CLI import CLI  # noqa: E402
from CrowdSec import CrowdSecError  # noqa: E402

IP = "1.2.3.4"
LEASE = {"kind": "crowdsec_lease", "ip": IP, "reason_data": {"instance": "n", "connection": "c"}}


def reply(found, row=None, status=200):
    data = {"found": found, "redis_checked": True}
    if row is not None:
        data["row"] = row
    return True, "ok", status, {"status": "success", "msg": "success", "data": data}


def api(*replies, name="bw1"):
    fake = MagicMock(name=name)
    fake.endpoint = f"http://{name}:5000/"
    fake.request.side_effect = list(replies)
    return fake


def decision(key="c1:7"):
    return {"key": key, "id": 7, "connection_id": "c1", "scope": "Ip", "value": IP, "type": "ban", "origin": "crowdsec", "scenario": "s"}


PREVIEW = {
    "lease": {"ip": IP, "ban_scope": "global", "service": None, "exp": 30},
    "source": {"connection_id": "c1", "instance": "bw1"},
    "connections": ["c1"],
    "unavailable": [],
    "decisions": [decision()],
    "warnings": {"list_origin": False, "range": False},
    "management_missing": [],
}


def make_cli(apis, db=object(), token="tok"):
    cli = CLI.__new__(CLI)
    cli.apis = apis
    cli._CLI__db = db
    cli._CLI__api_token = token
    cli._CLI__logger = MagicMock()
    cli._CLI__terminal_width = 80
    cli.send_to_apis = MagicMock(return_value=(True, None))
    return cli


class CliCrowdSecUnbanTests(TestCase):
    def test_explicit_ban_keeps_the_old_path_when_no_instance_has_a_lease(self):
        cli = make_cli([api(reply(False)), api(reply(False), name="bw2")], db=None)
        with patch.object(cli_module, "preview") as preview_mock, patch.object(cli_module, "execute") as execute_mock:
            ok, message = cli.unban(IP)
        self.assertTrue(ok)
        self.assertIn("has been unbanned", message)
        cli.send_to_apis.assert_called_once_with("POST", "/unban", data={"ip": IP, "ban_scope": "global"})
        preview_mock.assert_not_called()
        execute_mock.assert_not_called()

    def test_lookup_payload_carries_scope_and_service(self):
        one = api(reply(False))
        cli = make_cli([one])
        cli.unban(IP, "app.example.com")
        method, path = one.request.call_args.args[:2]
        self.assertEqual((method, path), ("POST", "/lease_lookup"))
        self.assertEqual(one.request.call_args.kwargs["data"], {"ip": IP, "ban_scope": "service", "service": "app.example.com"})

    def test_lease_without_confirm_prints_the_preview_and_executes_nothing(self):
        cli = make_cli([api(reply(True, LEASE))])
        with patch.object(cli_module, "CrowdSecClient") as client_cls, patch.object(cli_module, "preview", return_value=PREVIEW) as preview_mock, patch.object(
            cli_module, "execute"
        ) as execute_mock:
            ok, message = cli.unban(IP)
        self.assertFalse(ok)
        self.assertIn("-confirm", message)
        self.assertIn(IP, message)
        self.assertIn("explicit unban succeeded", message)
        client_cls.assert_called_once_with(cli._CLI__db, token="tok")
        preview_mock.assert_called_once_with(client_cls.return_value, IP, "global", None)
        execute_mock.assert_not_called()
        cli.send_to_apis.assert_called_once_with("POST", "/unban", data={"ip": IP, "ban_scope": "global"})

    def test_preview_shows_warnings_and_unavailable_connections(self):
        current = {**PREVIEW, "unavailable": ["c2"], "warnings": {"list_origin": True, "range": True}}
        cli = make_cli([api(reply(True, LEASE))])
        with patch.object(cli_module, "CrowdSecClient"), patch.object(cli_module, "preview", return_value=current):
            ok, message = cli.unban(IP)
        self.assertFalse(ok)
        self.assertIn("c2", message)
        self.assertIn("allowlist", message)
        self.assertIn("range", message)

    def test_confirm_executes_with_the_keys_of_the_preview(self):
        cli = make_cli([api(reply(True, LEASE))])
        result = {"status": "success", "deleted": ["c1:7"], "already_absent": [], "unavailable": [], "down": [], "lease_failed": [], "failed": []}
        with patch.object(cli_module, "CrowdSecClient") as client_cls, patch.object(cli_module, "preview", return_value=PREVIEW), patch.object(
            cli_module, "execute", return_value=result
        ) as execute_mock:
            ok, message = cli.unban(IP, None, confirm=True)
        self.assertTrue(ok)
        execute_mock.assert_called_once_with(client_cls.return_value, IP, "global", None, ["c1:7"])
        cli.send_to_apis.assert_called_once_with("POST", "/unban", data={"ip": IP, "ban_scope": "global"})
        self.assertIn("explicit unban succeeded", message)
        self.assertIn("CrowdSec decisions deleted", message)

    def test_changed_selection_is_an_error(self):
        cli = make_cli([api(reply(True, LEASE))])
        with patch.object(cli_module, "CrowdSecClient"), patch.object(cli_module, "preview", return_value=PREVIEW), patch.object(
            cli_module, "execute", return_value={"status": "changed", "preview": PREVIEW}
        ):
            ok, message = cli.unban(IP, None, confirm=True)
        self.assertFalse(ok)
        self.assertIn("changed", message)

    def test_partial_result_is_an_error_naming_the_failures(self):
        cli = make_cli([api(reply(True, LEASE))])
        result = {
            "status": "partial",
            "deleted": [],
            "failed": [{"key": "c1:7", "error": "boom"}],
            "unavailable": [],
            "down": ["bw9"],
            "lease_failed": [{"instance": "bw2", "error": "nope"}],
        }
        with patch.object(cli_module, "CrowdSecClient"), patch.object(cli_module, "preview", return_value=PREVIEW), patch.object(
            cli_module, "execute", return_value=result
        ):
            ok, message = cli.unban(IP, None, confirm=True)
        self.assertFalse(ok)
        for text in ("boom", "bw9", "bw2"):
            self.assertIn(text, message)

    def test_crowdsec_error_is_reported(self):
        cli = make_cli([api(reply(True, LEASE))])
        with patch.object(cli_module, "CrowdSecClient"), patch.object(cli_module, "preview", side_effect=CrowdSecError("source unavailable", 409)):
            ok, message = cli.unban(IP, None, confirm=True)
        self.assertFalse(ok)
        self.assertIn("source unavailable", message)

    def test_lease_without_database_points_to_the_web_ui_or_api(self):
        cli = make_cli([api(reply(True, LEASE))], db=None)
        with patch.object(cli_module, "CrowdSecClient") as client_cls:
            ok, message = cli.unban(IP, None, confirm=True)
        self.assertFalse(ok)
        self.assertIn("Web UI", message)
        self.assertIn("API", message)
        client_cls.assert_not_called()
        cli.send_to_apis.assert_called_once_with("POST", "/unban", data={"ip": IP, "ban_scope": "global"})
        self.assertIn("explicit unban succeeded", message)

    def test_a_lease_on_one_instance_only_is_found(self):
        cli = make_cli([api(reply(False)), api(reply(True, LEASE), name="bw2")])
        with patch.object(cli_module, "CrowdSecClient"), patch.object(cli_module, "preview", return_value=PREVIEW):
            ok, _ = cli.unban(IP)
        self.assertFalse(ok)
        cli.send_to_apis.assert_called_once_with("POST", "/unban", data={"ip": IP, "ban_scope": "global"})

    def test_lease_and_explicit_ban_confirmed_removes_both(self):
        cli = make_cli([api(reply(True, LEASE))])
        result = {"status": "success", "deleted": ["c1:7"], "already_absent": [], "unavailable": [], "down": [], "lease_failed": [], "failed": []}
        with patch.object(cli_module, "CrowdSecClient"), patch.object(cli_module, "preview", return_value=PREVIEW), patch.object(
            cli_module, "execute", return_value=result
        ) as execute_mock:
            ok, message = cli.unban(IP, None, confirm=True)
        self.assertTrue(ok)
        cli.send_to_apis.assert_called_once_with("POST", "/unban", data={"ip": IP, "ban_scope": "global"})
        execute_mock.assert_called_once()
        self.assertIn("explicit unban succeeded", message)
        self.assertIn("CrowdSec decisions deleted: 1", message)

    def test_lease_and_explicit_ban_without_confirm_removes_explicit_and_previews_lease(self):
        cli = make_cli([api(reply(True, LEASE))])
        with patch.object(cli_module, "CrowdSecClient"), patch.object(cli_module, "preview", return_value=PREVIEW), patch.object(
            cli_module, "execute"
        ) as execute_mock:
            ok, message = cli.unban(IP)
        self.assertFalse(ok)
        cli.send_to_apis.assert_called_once_with("POST", "/unban", data={"ip": IP, "ban_scope": "global"})
        execute_mock.assert_not_called()
        self.assertIn("explicit unban succeeded", message)
        self.assertIn("-confirm", message)

    def test_lease_failure_after_explicit_success_is_an_error_naming_both(self):
        cli = make_cli([api(reply(True, LEASE))])
        with patch.object(cli_module, "CrowdSecClient"), patch.object(cli_module, "preview", return_value=PREVIEW), patch.object(
            cli_module, "execute", return_value={"status": "changed", "preview": PREVIEW}
        ):
            ok, message = cli.unban(IP, None, confirm=True)
        self.assertFalse(ok)
        cli.send_to_apis.assert_called_once_with("POST", "/unban", data={"ip": IP, "ban_scope": "global"})
        self.assertIn("explicit unban succeeded", message)
        self.assertIn("changed", message)

    def test_explicit_failure_does_not_skip_the_lease_flow(self):
        cli = make_cli([api(reply(True, LEASE))])
        cli.send_to_apis.return_value = (False, None)
        result = {"status": "success", "deleted": ["c1:7"], "already_absent": [], "unavailable": [], "down": [], "lease_failed": [], "failed": []}
        with patch.object(cli_module, "CrowdSecClient"), patch.object(cli_module, "preview", return_value=PREVIEW), patch.object(
            cli_module, "execute", return_value=result
        ) as execute_mock:
            ok, message = cli.unban(IP, None, confirm=True)
        self.assertFalse(ok)
        execute_mock.assert_called_once()
        self.assertIn("explicit unban failed", message)
        self.assertIn("CrowdSec decisions deleted", message)

    def test_incomplete_check_still_unbans_explicitly_then_fails(self):
        for bad in (
            (False, "Connection error", None, None),
            (True, "ok", 500, {"status": "error", "msg": "x"}),
            (True, "ok", 200, {"status": "success", "data": {"found": "no"}}),
            (True, "ok", 200, None),
            (True, "ok", 200, {"status": "success", "data": {"found": True, "row": {"kind": "crowdsec_lease"}}}),
        ):
            with self.subTest(bad=bad):
                cli = make_cli([api(reply(False)), api(bad, name="bw2")])
                ok, message = cli.unban(IP)
                self.assertFalse(ok)
                self.assertIn("bw2", message)
                cli.send_to_apis.assert_called_once_with("POST", "/unban", data={"ip": IP, "ban_scope": "global"})

    def test_incomplete_check_reports_a_failed_explicit_unban_too(self):
        cli = make_cli([api((False, "down", None, None))])
        cli.send_to_apis.return_value = (False, None)
        ok, message = cli.unban(IP)
        self.assertFalse(ok)
        self.assertIn("explicit unban failed", message)

    def test_no_instance_is_an_error(self):
        ok, message = make_cli([]).unban(IP)
        self.assertFalse(ok)
        self.assertIn("no BunkerWeb instance", message)


class CliBansListingTests(TestCase):
    def test_bans_shows_the_kind_and_scans_the_lease_patterns(self):
        cli = make_cli([MagicMock()])
        cli.send_to_apis.return_value = (
            True,
            {
                "bw1": {
                    "data": [
                        {"ip": IP, "ban_scope": "global", "date": 1, "exp": 5, "reason": "crowdsec", "kind": "crowdsec_lease"},
                        {"ip": IP, "ban_scope": "global", "date": 2, "exp": 5, "reason": "manual", "kind": "ban"},
                    ]
                }
            },
        )
        cli._CLI__redis = MagicMock()
        with patch.object(cli, "_CLI__collect_redis_bans", return_value=[]) as collect:
            ok, output = cli.bans()
        self.assertTrue(ok)
        self.assertIn("CrowdSec lease", output)
        patterns = [call.args[0] for call in collect.call_args_list]
        for pattern in ("bans_ip_*", "bans_service_*_ip_*", "bans_cs_ip_*", "bans_cs_service_*_ip_*"):
            self.assertIn(pattern, patterns)

    def test_redis_collect_tags_the_kind_and_splits_lease_keys(self):
        cli = make_cli([])
        redis = MagicMock()
        redis.scan_iter.return_value = ["bans_cs_service_a_ip_b.example.com_ip_1.2.3.4"]
        redis.pipeline.return_value.execute.return_value = [b'{"reason":"crowdsec","ban_scope":"service"}', 42]
        cli._CLI__redis = redis
        rows = cli._CLI__collect_redis_bans("bans_cs_service_*_ip_*", "service", "crowdsec_lease")
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]["service"], rows[0]["ip"], rows[0]["kind"], rows[0]["exp"]), ("a_ip_b.example.com", IP, "crowdsec_lease", 42))
        self.assertEqual(rows[0]["date"], 0)

    def test_redis_collect_keeps_explicit_rows_as_bans(self):
        cli = make_cli([])
        redis = MagicMock()
        redis.scan_iter.return_value = ["bans_ip_1.2.3.4"]
        redis.pipeline.return_value.execute.return_value = [b'{"reason":"manual","date":3}', -1]
        cli._CLI__redis = redis
        rows = cli._CLI__collect_redis_bans("bans_ip_*", "global")
        self.assertEqual((rows[0]["ip"], rows[0]["kind"]), (IP, "ban"))


if __name__ == "__main__":
    main()
