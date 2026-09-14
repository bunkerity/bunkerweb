"""`bwcli custom-configs import <dir>` / `list`: the explicit, portable version of the
scheduler's own adoption of manually-placed configs (`check_configs_changes` in
src/scheduler/main.py), talking to the control-plane API instead of a shared
/etc/bunkerweb/configs volume.

Three properties matter more than the rest, because getting them wrong is a data-loss or a
false-success bug rather than a cosmetic one:

1. `--method manual` sends a FULL REPLACE (`PUT /configs/bulk`, method="manual") -- so the
   payload must include every valid config found under `<dir>`, unchanged ones included, or an
   unrelated file the operator did not touch would be deleted as "no longer present".
2. A config whose `service_id` does not exist is refused LOCALLY, before the bulk call: the bulk
   write is one transaction, and a dangling foreign key would abort the whole batch, not just the
   one bad entry.
3. `--dry-run` never calls the API's write endpoints.
"""

import os
import runpy
import sys
import types
from pathlib import Path as RealPath
from unittest.mock import Mock

import pytest

_ROOT = RealPath(__file__).resolve().parents[3]
for _p in (_ROOT / "src" / "common" / "cli", _ROOT / "src" / "common" / "api", _ROOT / "src" / "common" / "utils", _ROOT / "src" / "common" / "db"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import CLI as CLI_MODULE  # noqa: E402
from CLI import CLI, ApiClientError, ApiUnavailableError  # noqa: E402


def _cli():
    """A CLI without __init__ -- __init__ opens a database, Redis and a terminal."""
    cli = object.__new__(CLI)
    cli._CLI__variables = {}
    cli._CLI__logger = Mock()
    cli._CLI__terminal_width = 80
    return cli


def _fake_client(*, configs=None, services=None, bulk_message=""):
    client = Mock()
    client.list_configs.return_value = list(configs or [])
    client.list_services.return_value = list(services or [])
    client.bulk_save.return_value = bulk_message
    return client


def _patch_client(monkeypatch, client):
    monkeypatch.setattr(CLI_MODULE, "CustomConfigsApiClient", lambda token: client)


def _write(root: RealPath, rel: str, content: str = "some_directive on;\n") -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class TestLayoutValidation:
    def test_a_file_too_deep_is_refused_without_touching_the_api(self, tmp_path, monkeypatch):
        _write(tmp_path, "http/one/two/name.conf")
        client = _fake_client()
        _patch_client(monkeypatch, client)

        ok, message = _cli().custom_configs_import(str(tmp_path), method="manual")

        assert ok is False
        assert "refused http/one/two/name.conf: http/one/two/name.conf is not in the correct path" in message
        client.bulk_save.assert_not_called()

    def test_an_unknown_type_folder_is_refused(self, tmp_path, monkeypatch):
        _write(tmp_path, "bogus/name.conf")
        client = _fake_client()
        _patch_client(monkeypatch, client)

        ok, message = _cli().custom_configs_import(str(tmp_path), method="manual")

        assert ok is False
        assert "refused bogus/name.conf: Invalid type: must be one of" in message

    def test_an_invalid_name_is_refused_with_the_apis_own_wording(self, tmp_path, monkeypatch):
        _write(tmp_path, "http/bad name!.conf")
        client = _fake_client()
        _patch_client(monkeypatch, client)

        ok, message = _cli().custom_configs_import(str(tmp_path), method="manual")

        assert ok is False
        assert r"refused http/bad name!.conf: Invalid name: must match ^[\w_-]{1,255}\Z" in message

    def test_a_missing_directory_fails_before_any_api_call(self, tmp_path, monkeypatch):
        client = _fake_client()
        _patch_client(monkeypatch, client)

        ok, message = _cli().custom_configs_import(str(tmp_path / "nope"))

        assert ok is False
        assert "is not a directory" in message
        client.list_configs.assert_not_called()

    def test_an_empty_directory_succeeds_as_a_no_op(self, tmp_path, monkeypatch):
        client = _fake_client()
        _patch_client(monkeypatch, client)

        ok, message = _cli().custom_configs_import(str(tmp_path), method="manual")

        assert ok is True
        assert "No .conf files found" in message
        client.list_configs.assert_not_called()


class TestManualReplaceSemantics:
    def test_unchanged_configs_are_still_sent_so_the_full_replace_does_not_delete_them(self, tmp_path, monkeypatch):
        _write(tmp_path, "http/global.conf", "same_content;\n")
        _write(tmp_path, "http/changed.conf", "new_content;\n")
        client = _fake_client(
            configs=[
                {
                    "service": None,
                    "type": "http",
                    "name": "global",
                    "checksum": CLI_MODULE.bytes_hash("same_content;\n", algorithm="sha256"),
                    "is_draft": False,
                    "method": "manual",
                },
                {"service": None, "type": "http", "name": "changed", "checksum": "stale-checksum", "is_draft": False, "method": "manual"},
            ]
        )
        _patch_client(monkeypatch, client)

        ok, message = _cli().custom_configs_import(str(tmp_path), method="manual")

        assert ok is True
        payload = client.bulk_save.call_args[0][0]
        exploded_names = {item["exploded"][2] for item in payload}
        assert exploded_names == {"global", "changed"}, "the full-replace payload must carry unchanged configs too"
        assert client.bulk_save.call_args[0][1] == "manual"
        assert "unchanged http/global.conf" in message
        assert "updated http/changed.conf" in message

    def test_a_brand_new_directory_reports_everything_as_created(self, tmp_path, monkeypatch):
        _write(tmp_path, "http/global.conf")
        _write(tmp_path, "server-http/svc1/vhost.conf")
        client = _fake_client(configs=[], services=["svc1"])
        _patch_client(monkeypatch, client)

        ok, message = _cli().custom_configs_import(str(tmp_path), method="manual")

        assert ok is True
        assert "created http/global.conf" in message
        assert "created server-http/svc1/vhost.conf" in message
        payload = client.bulk_save.call_args[0][0]
        assert {item["exploded"] for item in payload} == {(None, "http", "global"), ("svc1", "server_http", "vhost")}

    def test_the_draft_flag_is_carried_into_the_payload(self, tmp_path, monkeypatch):
        _write(tmp_path, "http/global.conf")
        client = _fake_client()
        _patch_client(monkeypatch, client)

        _cli().custom_configs_import(str(tmp_path), draft=True, method="manual")

        payload = client.bulk_save.call_args[0][0]
        assert payload[0]["is_draft"] is True

    def test_a_bulk_save_advisory_message_is_surfaced_and_counts_as_a_problem(self, tmp_path, monkeypatch):
        _write(tmp_path, "http/global.conf")
        client = _fake_client(bulk_message="Service ghost not found, please check your config")
        _patch_client(monkeypatch, client)

        ok, message = _cli().custom_configs_import(str(tmp_path), method="manual")

        assert ok is False
        assert "note: Service ghost not found, please check your config" in message

    def test_a_refused_bulk_save_call_is_reported_as_a_failure(self, tmp_path, monkeypatch):
        _write(tmp_path, "http/global.conf")
        client = _fake_client()
        client.bulk_save.side_effect = ApiClientError("The database is read-only")
        _patch_client(monkeypatch, client)

        ok, message = _cli().custom_configs_import(str(tmp_path), method="manual")

        assert ok is False
        assert "Import failed" in message
        assert "read-only" in message


class TestManualDeleteVisibility:
    """`manual` is a full replace: any existing method="manual" row not re-submitted by this run
    is deleted server-side (and later unlinked from disk by the scheduler's own regeneration).
    That must never happen silently -- the operator needs to see it before it happens (dry-run)
    and be told it happened (a real run)."""

    def test_a_manual_config_outside_the_directory_is_reported_as_deleted(self, tmp_path, monkeypatch):
        _write(tmp_path, "http/global.conf")
        client = _fake_client(
            configs=[
                {"service": None, "type": "http", "name": "global", "checksum": "x", "is_draft": False, "method": "manual"},
                {"service": "svc1", "type": "server_http", "name": "stale", "checksum": "y", "is_draft": False, "method": "manual"},
            ]
        )
        _patch_client(monkeypatch, client)

        ok, message = _cli().custom_configs_import(str(tmp_path), method="manual")

        assert "deleted svc1/server_http/stale" in message
        assert "Summary: " in message and "1 deleted" in message

    def test_a_non_manual_config_absent_from_the_directory_is_never_reported_as_deleted(self, tmp_path, monkeypatch):
        """The full replace only ever touches method="manual" rows -- an api/ui/autoconf/scheduler
        config that simply is not under `<dir>` is untouched server-side and must not be reported
        as if it were about to be deleted."""
        _write(tmp_path, "http/global.conf")
        client = _fake_client(configs=[{"service": None, "type": "http", "name": "other", "checksum": "z", "is_draft": False, "method": "api"}])
        _patch_client(monkeypatch, client)

        ok, message = _cli().custom_configs_import(str(tmp_path), method="manual")

        assert not any(line.startswith("deleted ") for line in message.splitlines())
        assert "0 deleted" in message

    def test_dry_run_reports_the_deletion_without_writing_anything(self, tmp_path, monkeypatch):
        _write(tmp_path, "http/global.conf")
        client = _fake_client(configs=[{"service": None, "type": "http", "name": "stale", "checksum": "y", "is_draft": False, "method": "manual"}])
        _patch_client(monkeypatch, client)

        ok, message = _cli().custom_configs_import(str(tmp_path), method="manual", dry_run=True)

        assert "deleted global/http/stale (dry-run)" in message
        client.bulk_save.assert_not_called()

    def test_dry_run_never_previews_a_deletion_that_a_refusal_would_block(self, tmp_path, monkeypatch):
        """A refusal aborts the real `manual` write entirely (TestDanglingServiceReference above)
        -- the dry-run preview of the SAME input must agree, not promise a deletion that a real
        run of that input would then refuse to perform. Criticos round 2: the dry-run branch used
        to return before the abort check ran, so the preview showed `deleted ... (dry-run)` for a
        run that, for real, aborts and deletes nothing."""
        _write(tmp_path, "bogus/name.conf")  # refused: unknown type
        _write(tmp_path, "http/global.conf")  # would survive, if the batch were sent
        client = _fake_client(configs=[{"service": None, "type": "http", "name": "stale", "checksum": "y", "is_draft": False, "method": "manual"}])
        _patch_client(monkeypatch, client)

        dry_ok, dry_message = _cli().custom_configs_import(str(tmp_path), method="manual", dry_run=True)
        real_ok, real_message = _cli().custom_configs_import(str(tmp_path), method="manual")

        for ok, message in ((dry_ok, dry_message), (real_ok, real_message)):
            assert ok is False
            assert "import aborted" in message
            assert not any(line.startswith("deleted ") for line in message.splitlines())
        client.bulk_save.assert_not_called()

    def test_method_api_never_reports_a_deletion(self, tmp_path, monkeypatch):
        """`--method api` never deletes: an untouched row simply stays untouched."""
        _write(tmp_path, "http/global.conf")
        client = _fake_client(configs=[{"service": None, "type": "http", "name": "stale", "checksum": "y", "is_draft": False, "method": "manual"}])
        _patch_client(monkeypatch, client)

        ok, message = _cli().custom_configs_import(str(tmp_path), method="api")

        assert not any(line.startswith("deleted ") for line in message.splitlines())
        assert "0 deleted" in message


class TestDanglingServiceReference:
    def test_an_unknown_service_is_refused_locally_and_excluded_from_the_batch(self, tmp_path, monkeypatch):
        _write(tmp_path, "http/ghost/name.conf")
        _write(tmp_path, "http/global.conf")
        client = _fake_client(services=["real-service"])
        _patch_client(monkeypatch, client)

        ok, message = _cli().custom_configs_import(str(tmp_path), method="manual")

        assert ok is False
        assert "refused http/ghost/name.conf: Service ghost not found, please check your config" in message
        # `manual` is a full replace: a refusal means `valid` does not carry every config that
        # should survive this run, so sending it as-is would DELETE the good file's existing row
        # (if any) rather than merely skip the bad one. The write must not happen at all.
        assert "import aborted" in message
        client.bulk_save.assert_not_called()

    def test_a_known_service_is_accepted(self, tmp_path, monkeypatch):
        _write(tmp_path, "http/real-service/name.conf")
        client = _fake_client(services=["real-service"])
        _patch_client(monkeypatch, client)

        ok, message = _cli().custom_configs_import(str(tmp_path), method="manual")

        assert ok is True
        assert "created http/real-service/name.conf" in message

    def test_a_foreign_owned_config_is_refused_before_the_bulk_save(self, tmp_path, monkeypatch):
        _write(tmp_path, "http/global.conf")
        client = _fake_client(configs=[{"service": None, "type": "http", "name": "global", "checksum": "stale", "is_draft": False, "method": "scheduler"}])
        _patch_client(monkeypatch, client)

        ok, message = _cli().custom_configs_import(str(tmp_path), method="manual")

        assert ok is False
        assert "refused http/global.conf: existing config is owned by scheduler; import it through the API or change it at its source" in message
        client.bulk_save.assert_not_called()

    def test_a_foreign_owned_config_keeps_the_apis_403_on_the_api_path(self, tmp_path, monkeypatch):
        _write(tmp_path, "http/global.conf")
        client = _fake_client(configs=[{"service": None, "type": "http", "name": "global", "checksum": "stale", "is_draft": False, "method": "scheduler"}])
        client.update_config.side_effect = ApiClientError("Config is not UI/API-managed and cannot be edited")
        _patch_client(monkeypatch, client)

        ok, message = _cli().custom_configs_import(str(tmp_path), method="api")

        assert ok is False
        assert "refused http/global.conf: Config is not UI/API-managed and cannot be edited" in message


class TestMainDefaults:
    def test_import_without_method_dispatches_to_the_api_path(self, tmp_path, monkeypatch):
        calls = []

        class FakeCLI:
            def custom_configs_import(self, directory, *, draft, method, dry_run):
                calls.append((directory, draft, method, dry_run))
                return True, ""

        fake_cli_module = types.ModuleType("CLI")
        fake_cli_module.CLI = FakeCLI
        fake_cli_module.backup_preflight = lambda directory: (True, "")
        fake_cli_module.render_capabilities = lambda: ""
        monkeypatch.setitem(sys.modules, "CLI", fake_cli_module)
        monkeypatch.setattr(sys, "argv", ["main.py", "custom-configs", "import", str(tmp_path)])
        monkeypatch.setattr(os, "_exit", lambda code: (_ for _ in ()).throw(SystemExit(code)))

        with pytest.raises(SystemExit) as exc_info:
            runpy.run_path(str(_ROOT / "src/common/cli/main.py"), run_name="__main__")

        assert exc_info.value.code == 0
        assert calls == [(str(tmp_path), False, "api", False)]


class TestDryRun:
    def test_dry_run_never_calls_a_write_endpoint(self, tmp_path, monkeypatch):
        _write(tmp_path, "http/global.conf")
        client = _fake_client()
        _patch_client(monkeypatch, client)

        ok, message = _cli().custom_configs_import(str(tmp_path), dry_run=True)

        assert ok is True
        assert "created http/global.conf (dry-run)" in message
        client.bulk_save.assert_not_called()
        client.create_config.assert_not_called()
        client.update_config.assert_not_called()

    def test_dry_run_still_reports_refusals_and_exits_non_zero(self, tmp_path, monkeypatch):
        _write(tmp_path, "bogus/name.conf")
        client = _fake_client()
        _patch_client(monkeypatch, client)

        ok, message = _cli().custom_configs_import(str(tmp_path), dry_run=True)

        assert ok is False
        assert "refused bogus/name.conf" in message


class TestMethodApi:
    def test_the_default_method_uses_per_config_api_upserts(self, tmp_path, monkeypatch):
        _write(tmp_path, "http/global.conf", "content;\n")
        client = _fake_client(configs=[])
        _patch_client(monkeypatch, client)

        ok, _ = _cli().custom_configs_import(str(tmp_path))

        assert ok is True
        client.bulk_save.assert_not_called()
        client.create_config.assert_called_once_with(service=None, config_type="http", name="global", data="content;\n", is_draft=False)

    def test_a_new_config_is_created_individually(self, tmp_path, monkeypatch):
        _write(tmp_path, "http/global.conf", "content;\n")
        client = _fake_client(configs=[])
        _patch_client(monkeypatch, client)

        ok, message = _cli().custom_configs_import(str(tmp_path), method="api")

        assert ok is True
        client.create_config.assert_called_once_with(service=None, config_type="http", name="global", data="content;\n", is_draft=False)
        client.update_config.assert_not_called()
        client.bulk_save.assert_not_called()
        assert "created http/global.conf" in message

    def test_an_existing_config_with_new_content_is_patched_not_recreated(self, tmp_path, monkeypatch):
        _write(tmp_path, "http/global.conf", "new;\n")
        client = _fake_client(configs=[{"service": None, "type": "http", "name": "global", "checksum": "stale", "is_draft": False, "method": "api"}])
        _patch_client(monkeypatch, client)

        ok, message = _cli().custom_configs_import(str(tmp_path), method="api")

        assert ok is True
        client.update_config.assert_called_once_with(service=None, config_type="http", name="global", data="new;\n", is_draft=False)
        client.create_config.assert_not_called()
        assert "updated http/global.conf" in message

    def test_an_unchanged_config_is_skipped_with_no_api_call(self, tmp_path, monkeypatch):
        checksum = CLI_MODULE.bytes_hash("same;\n", algorithm="sha256")
        _write(tmp_path, "http/global.conf", "same;\n")
        client = _fake_client(configs=[{"service": None, "type": "http", "name": "global", "checksum": checksum, "is_draft": False, "method": "api"}])
        _patch_client(monkeypatch, client)

        ok, message = _cli().custom_configs_import(str(tmp_path), method="api")

        assert ok is True
        client.create_config.assert_not_called()
        client.update_config.assert_not_called()
        assert "unchanged http/global.conf" in message

    def test_a_bad_reference_does_not_block_the_rest_of_the_batch(self, tmp_path, monkeypatch):
        """Unlike `manual` (one full-replace transaction, see TestDanglingServiceReference above),
        `--method api` writes one config at a time, so a dangling service_id can be excluded
        without endangering anything else in the run."""
        _write(tmp_path, "http/ghost/name.conf")
        _write(tmp_path, "http/global.conf")
        client = _fake_client(services=["real-service"])
        _patch_client(monkeypatch, client)

        ok, message = _cli().custom_configs_import(str(tmp_path), method="api")

        assert ok is False
        assert "refused http/ghost/name.conf: Service ghost not found, please check your config" in message
        assert "created http/global.conf" in message
        client.create_config.assert_called_once_with(service=None, config_type="http", name="global", data="some_directive on;\n", is_draft=False)

    def test_the_apis_own_refusal_message_is_surfaced_verbatim(self, tmp_path, monkeypatch):
        _write(tmp_path, "http/global.conf", "new;\n")
        client = _fake_client(configs=[{"service": None, "type": "http", "name": "global", "checksum": "stale", "is_draft": False, "method": "manual"}])
        client.update_config.side_effect = ApiClientError("Config is not UI/API-managed and cannot be edited")
        _patch_client(monkeypatch, client)

        ok, message = _cli().custom_configs_import(str(tmp_path), method="api")

        assert ok is False
        assert "refused http/global.conf: Config is not UI/API-managed and cannot be edited" in message


class TestCustomConfigsApiClientWireFormat:
    """Every test above mocks `CustomConfigsApiClient` itself, so the actual JSON bodies its
    methods build (`bulk_save`, `update_config`) are otherwise never exercised -- exactly where
    two real bugs lived: an omitted `changed` flag that made every `--method manual` import a
    silent no-op (`db_methods/custom_configs.py` only flips `metadata.custom_configs_changed`,
    which gates the scheduler's regeneration/reload, `when changed`), and an omitted `service`
    that re-scoped every `--method api` update to global (`api/app/routers/configs.py`'s PATCH
    reads the new scope from the body unconditionally -- same defect already found and fixed once
    in `src/ui/app/api_client.py:487-493`)."""

    def _client(self):
        return CLI_MODULE.CustomConfigsApiClient("token")

    def test_bulk_save_signals_the_scheduler_to_regenerate_and_reload(self, monkeypatch):
        client = self._client()
        put = Mock(return_value={})
        monkeypatch.setattr(client, "_put", put)

        client.bulk_save([{"value": "x;\n", "exploded": (None, "http", "global"), "is_draft": False}], "manual")

        assert put.call_args[0][0] == "/configs/bulk"
        assert put.call_args[1]["json"] == {
            "custom_configs": [{"value": "x;\n", "exploded": (None, "http", "global"), "is_draft": False}],
            "method": "manual",
            "changed": True,
        }

    def test_create_config_sends_the_complete_post_body(self, monkeypatch):
        client = self._client()
        post = Mock(return_value={})
        monkeypatch.setattr(client, "_post", post)

        client.create_config(service="svc1", config_type="http", name="vhost", data="x;\n", is_draft=True)

        assert post.call_args[0][0] == "/configs"
        assert post.call_args[1]["json"] == {"service": "svc1", "type": "http", "name": "vhost", "data": "x;\n", "is_draft": True}

    def test_update_config_restates_the_current_service_so_it_is_not_dropped_to_global(self, monkeypatch):
        client = self._client()
        patch = Mock(return_value={})
        monkeypatch.setattr(client, "_patch", patch)

        client.update_config(service="svc1", config_type="http", name="vhost", data="x;\n", is_draft=False)

        assert patch.call_args[0][0] == "/configs/svc1/http/vhost"
        assert patch.call_args[1]["json"]["service"] == "svc1"

    def test_update_config_for_a_global_config_sends_a_null_service(self, monkeypatch):
        client = self._client()
        patch = Mock(return_value={})
        monkeypatch.setattr(client, "_patch", patch)

        client.update_config(service=None, config_type="http", name="global", data="x;\n", is_draft=False)

        assert "service" in patch.call_args[1]["json"]
        assert patch.call_args[1]["json"]["service"] is None


class TestUnreachableApi:
    def test_the_import_fails_cleanly_when_the_api_is_unreachable(self, tmp_path, monkeypatch):
        _write(tmp_path, "http/global.conf")
        client = Mock()
        client.list_configs.side_effect = ApiUnavailableError("API unavailable")
        _patch_client(monkeypatch, client)

        ok, message = _cli().custom_configs_import(str(tmp_path))

        assert ok is False
        assert "Failed to reach the API" in message

    def test_an_unknown_method_is_rejected_before_any_filesystem_walk(self, tmp_path):
        ok, message = _cli().custom_configs_import(str(tmp_path), method="bogus")

        assert ok is False
        assert "Unknown --method" in message


class TestList:
    def test_the_table_has_one_row_per_config_with_a_truncated_checksum(self, monkeypatch):
        client = _fake_client(
            configs=[
                {"service": None, "type": "http", "name": "global", "method": "manual", "is_draft": False, "checksum": "a" * 64},
                {"service": "svc1", "type": "server_http", "name": "vhost", "method": "api", "is_draft": True, "checksum": "b" * 64},
            ]
        )
        _patch_client(monkeypatch, client)

        ok, message = _cli().custom_configs_list()

        assert ok is True
        assert "global" in message and "a" * 12 in message and "a" * 13 not in message
        assert "svc1" in message and "yes" in message

    def test_filters_are_forwarded_to_the_api(self, monkeypatch):
        client = _fake_client(configs=[])
        _patch_client(monkeypatch, client)

        _cli().custom_configs_list(service="svc1", config_type="http")

        client.list_configs.assert_called_once_with(service="svc1", config_type="http")

    def test_an_empty_result_is_reported_without_failing(self, monkeypatch):
        client = _fake_client(configs=[])
        _patch_client(monkeypatch, client)

        ok, message = _cli().custom_configs_list()

        assert ok is True
        assert "No custom configs found" in message

    def test_an_api_error_is_reported_as_a_failure(self, monkeypatch):
        client = Mock()
        client.list_configs.side_effect = ApiClientError("boom")
        _patch_client(monkeypatch, client)

        ok, message = _cli().custom_configs_list()

        assert ok is False
        assert "Failed to list custom configs" in message


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
