from base64 import b64decode
from typing import Tuple, Union

from base_api_client import BaseApiClient, ApiClientError, ApiUnavailableError  # type: ignore  # noqa: F401


class SchedulerApiClient(BaseApiClient):
    """API client for the Scheduler. All data access goes through the API."""

    def __init__(self, base_url: str, api_token: str, timeout: int = 30):
        super().__init__(base_url, api_token, timeout=timeout, logger_name="SCHEDULER")

    # ── Config ──────────────────────────────────────────────────────────

    def get_config(self) -> dict:
        """Get all global settings (full=true to include defaults)."""
        return self._get("/global_settings", params={"full": "true"}).get("settings", {})

    def save_config(self, config: dict, method: str, changed: bool = False) -> Union[str, list]:
        """Save full config dict. Returns error string on failure, or list of changed plugin IDs on success."""
        try:
            data = self._put("/global_settings/config", json={"config": config, "method": method, "changed": changed})
            return data.get("changed_plugins", [])
        except ApiClientError as e:
            return e.message
        except ApiUnavailableError:
            raise

    # ── Instances ───────────────────────────────────────────────────────

    def get_instances(self) -> list:
        """Get registered instances."""
        return self._get("/instances").get("instances", [])

    def update_instance(self, hostname: str, status: str) -> str:
        """Update instance status (up/down/failover). Returns empty string on success."""
        try:
            self._patch(f"/instances/{hostname}/status", json={"status": status})
            return ""
        except (ApiClientError, ApiUnavailableError) as e:
            return e.message

    def update_instances(self, instances: list, method: str, changed: bool = False) -> str:
        """Bulk replace instances for the given method. Returns empty string on success."""
        try:
            self._put("/instances/bulk", json={"instances": instances, "method": method, "changed": changed})
            return ""
        except (ApiClientError, ApiUnavailableError) as e:
            return e.message

    def ping_instance(self, hostname: str) -> bool:
        """Ping a specific instance. Returns True if reachable."""
        try:
            self._get(f"/instances/{hostname}/ping")
            return True
        except (ApiClientError, ApiUnavailableError):
            return False

    def reload_instances(self, test: bool = True) -> bool:
        """Reload all instances. Returns True on success."""
        try:
            self._post("/instances/reload", params={"test": str(test).lower()})
            return True
        except (ApiClientError, ApiUnavailableError):
            return False

    # ── Metadata / Changes ──────────────────────────────────────────────

    def get_metadata(self) -> Union[str, dict]:
        """Get all metadata. Returns dict on success, error string on failure."""
        try:
            data = self._get("/metadata")
            return data.get("metadata", {})
        except (ApiClientError, ApiUnavailableError) as e:
            return e.message

    def set_metadata(self, metadata: dict) -> str:
        """Update metadata. Returns empty string on success."""
        try:
            self._patch("/metadata", json={"data": metadata})
            return ""
        except (ApiClientError, ApiUnavailableError) as e:
            return e.message

    def checked_changes(self, changes: list, plugins_changes=None, value: bool = True) -> str:
        """Signal changes to checked. value=True marks flags as changed (UI/autoconf
        legacy contract); value=False clears them (scheduler after processing).
        Callers MUST pass value= explicitly to avoid drift between roles."""
        payload = {"changes": changes, "value": value}
        if plugins_changes is not None:
            payload["plugins_changes"] = sorted(plugins_changes) if isinstance(plugins_changes, (list, set)) else plugins_changes
        try:
            self._post("/system/checked-changes", json=payload)
            return ""
        except (ApiClientError, ApiUnavailableError) as e:
            return e.message

    # ── Custom Configs ──────────────────────────────────────────────────

    def get_custom_configs(self) -> list:
        """Get all custom configs (with payload). API renames `service_id` → `service`
        and omits `data` unless with_data=true is requested — re-normalize back to the
        scheduler-expected shape (`service_id`, `data`)."""
        configs = self._get("/configs", params={"with_data": "true"}).get("configs", [])
        for c in configs:
            if "service" in c and "service_id" not in c:
                c["service_id"] = c.pop("service")
                if c["service_id"] == "global":
                    c["service_id"] = None
            d = c.get("data", "")
            if isinstance(d, str):
                c["data"] = d.encode("utf-8")
        return configs

    def save_custom_configs(self, configs: list, method: str, changed: bool = False) -> str:
        """Bulk save custom configs. Returns empty string on success."""
        try:
            self._put("/configs/bulk", json={"custom_configs": configs, "method": method, "changed": changed})
            return ""
        except (ApiClientError, ApiUnavailableError) as e:
            return e.message

    # ── Plugins ─────────────────────────────────────────────────────────

    def get_plugins(self, _type: str = "all", with_data: bool = False, only_enabled: bool = False) -> list:
        """Get plugins of the specified type. When with_data=True, API returns base64-encoded
        bytes — decode them so callers can pass directly to BytesIO/tar_open.
        ``only_enabled`` excludes disabled external/ui/pro plugins (materialization skip)."""
        params = {"type": _type, "with_data": str(with_data).lower()}
        if only_enabled:
            params["only_enabled"] = "true"
        plugins = self._get("/plugins", params=params).get("plugins", [])
        if with_data:
            for p in plugins:
                d = p.get("data")
                if isinstance(d, str):
                    try:
                        p["data"] = b64decode(d)
                    except Exception:
                        p["data"] = d.encode("utf-8")
        return plugins

    def update_external_plugins(self, plugins: list, _type: str = "external", delete_missing: bool = True) -> str:
        """Bulk update external/pro plugins. Returns empty string on success."""
        try:
            self._put("/plugins/external", json={"plugins": plugins, "_type": _type, "delete_missing": delete_missing})
            return ""
        except (ApiClientError, ApiUnavailableError) as e:
            return e.message

    # ── Cache ───────────────────────────────────────────────────────────

    def get_jobs_cache_files(self) -> list:
        """Get all job cache files."""
        return self._get("/cache").get("cache", [])

    # ── Job Dispatch ────────────────────────────────────────────────────

    def dispatch_jobs(self, jobs: list) -> Tuple[bool, list]:
        """Dispatch jobs to API for Celery worker execution."""
        try:
            data = self._post("/jobs/dispatch", json={"jobs": jobs})
            return True, data.get("runs", [])
        except (ApiClientError, ApiUnavailableError) as e:
            self._logger.error(f"Failed to dispatch jobs: {e.message}")
            return False, []
