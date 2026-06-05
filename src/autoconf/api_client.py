from typing import Any, Dict, List, Optional, Tuple, Union

from base_api_client import BaseApiClient, ApiClientError, ApiUnavailableError  # type: ignore  # noqa: F401


class AutoconfApiClient(BaseApiClient):
    def __init__(self, base_url: str, api_token: str, timeout: int = 30):
        super().__init__(base_url, api_token, timeout=timeout, logger_name="AUTOCONF")

    # ── Plugins / Settings ──────────────────────────────────────────────

    def get_plugins(self) -> list:
        """Fetch all plugins with their settings schemas."""
        data = self._get("/plugins")
        return data.get("plugins", [])

    def validate_setting(
        self,
        setting: str,
        *,
        value: Optional[str] = None,
        multisite: bool = False,
        extra_services: Optional[List[str]] = None,
    ) -> Tuple[bool, str]:
        """Validate a setting name/value. Returns (valid, error_message)."""
        payload: Dict[str, Any] = {"setting": setting, "multisite": multisite}
        if value is not None:
            payload["value"] = value
        if extra_services is not None:
            payload["extra_services"] = extra_services
        data = self._post("/global_settings/validate", json=payload)
        return data.get("valid", False), data.get("error", "")

    # ── Services ────────────────────────────────────────────────────────

    def get_services(self) -> list:
        """Get all services (without drafts)."""
        data = self._get("/services", params={"with_drafts": "false"})
        return data.get("services", [])

    # ── Instances ───────────────────────────────────────────────────────

    def get_instances(self, autoconf: bool = False) -> list:
        """Get registered instances, optionally with autoconf fields (health, env)."""
        params = {}
        if autoconf:
            params["autoconf"] = "true"
        data = self._get("/instances", params=params)
        return data.get("instances", [])

    def update_instances(self, instances: list, method: str, changed: bool = False) -> str:
        """Bulk replace instances for the given method. Returns empty string on success, error otherwise."""
        try:
            self._put("/instances/bulk", json={"instances": instances, "method": method, "changed": changed})
            return ""
        except ApiClientError as e:
            return e.message
        except ApiUnavailableError:
            raise

    # ── Config ──────────────────────────────────────────────────────────

    def save_config(self, config: dict, method: str, changed: bool = False, disable_cleanup: bool = False) -> Union[str, List[str]]:
        """Save full config dict. Returns error string on failure, or list of changed plugin IDs on success."""
        try:
            data = self._put("/global_settings/config", json={"config": config, "method": method, "changed": changed, "disable_cleanup": disable_cleanup})
            return data.get("changed_plugins", [])
        except ApiClientError as e:
            return e.message
        except ApiUnavailableError:
            raise

    def save_custom_configs(self, custom_configs: list, method: str, changed: bool = False, disable_cleanup: bool = False) -> str:
        """Bulk save custom configs. Returns empty string on success, error otherwise."""
        try:
            self._put("/configs/bulk", json={"custom_configs": custom_configs, "method": method, "changed": changed, "disable_cleanup": disable_cleanup})
            return ""
        except ApiClientError as e:
            return e.message
        except ApiUnavailableError:
            raise

    # ── Metadata / Changes ──────────────────────────────────────────────

    def get_metadata(self) -> Union[str, dict]:
        """Get all metadata. Returns dict on success, error string on failure."""
        try:
            data = self._get("/metadata")
            return data.get("metadata", {})
        except (ApiClientError, ApiUnavailableError) as e:
            return e.message

    def set_metadata(self, data: dict) -> str:
        """Update metadata. Returns empty string on success, error otherwise."""
        try:
            self._patch("/metadata", json={"data": data})
            return ""
        except ApiClientError as e:
            return e.message
        except ApiUnavailableError as e:
            return e.message

    def checked_changes(self, changes: list, plugins_changes=None, value: bool = True) -> str:
        """Signal changes to the scheduler. Returns empty string on success, error otherwise."""
        payload: Dict[str, Any] = {"changes": changes, "value": value}
        if plugins_changes is not None:
            payload["plugins_changes"] = sorted(plugins_changes) if isinstance(plugins_changes, set) else plugins_changes
        try:
            self._post("/system/checked-changes", json=payload)
            return ""
        except (ApiClientError, ApiUnavailableError) as e:
            return e.message
