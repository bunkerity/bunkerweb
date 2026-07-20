from base_api_client import ApiClientError, ApiUnavailableError, BaseApiClient  # type: ignore  # noqa: F401

# Re-export for backwards compatibility — other UI modules import these from here
__all__ = ["ApiClient", "ApiClientError", "ApiUnavailableError"]


class ApiClient(BaseApiClient):
    def __init__(self, base_url: str, api_token: str, timeout=(3, 10)):
        super().__init__(base_url, api_token, timeout=timeout, logger_name="UI")

    def checked_changes(self, changes, plugins_changes=None, value=False):
        """Mark changes as checked/pending."""
        payload = {"changes": changes, "value": value}
        if plugins_changes is not None:
            payload["plugins_changes"] = plugins_changes
        return self._post("/system/checked-changes", json=payload)

    # ── Global Settings ─────────────────────────────────────────────────

    def get_global_settings(self, full=False, methods=False, with_drafts=False, filtered_settings=None, global_only=True):
        params = {}
        if full:
            params["full"] = "true"
        if methods:
            params["methods"] = "true"
        if with_drafts:
            params["with_drafts"] = "true"
        if filtered_settings:
            params["filtered_settings"] = list(filtered_settings)
        if not global_only:
            params["global_only"] = "false"
        return self._get("/global_settings", params=params).get("settings", {})

    def update_global_settings(self, settings: dict):
        return self._patch("/global_settings", json=settings)

    # ── Metrics / Reports ───────────────────────────────────────────────

    def get_metrics_requests(
        self,
        *,
        start=0,
        length=10,
        search="",
        order_column="date",
        order_dir="desc",
        search_panes="",
        count_only=False,
        include_pane_counts=True,
    ):
        """Query persisted blocked-request reports (DB-backed) from the central API."""
        params = {
            "start": start,
            "length": length,
            "search": search,
            "order_column": order_column,
            "order_dir": order_dir,
            "search_panes": search_panes,
            "count_only": "true" if count_only else "false",
            "include_pane_counts": "true" if include_pane_counts else "false",
        }
        return self._get("/metrics/requests", params=params)

    def get_metrics_timeseries(self, *, start: int, end: int, bucket: str = "hour", search_panes: str = ""):
        return self._get("/metrics/requests/timeseries", params={"start": start, "end": end, "bucket": bucket, "search_panes": search_panes})

    def get_metrics_top_offenders(self, *, start: int, end: int, limit: int = 10, search_panes: str = ""):
        return self._get("/metrics/requests/top-offenders", params={"start": start, "end": end, "limit": limit, "search_panes": search_panes})

    def get_metrics_top_rules(self, *, start: int, end: int, limit: int = 10):
        return self._get("/metrics/requests/top-rules", params={"start": start, "end": end, "limit": limit})

    # ── Instances ───────────────────────────────────────────────────────

    def get_instances(self):
        return self._get("/instances").get("instances", [])

    def get_instance(self, hostname):
        data = self._get(f"/instances/{hostname}")
        return data.get("instance", data)

    def create_instance(self, **kwargs):
        return self._post("/instances", json=kwargs)

    def update_instance(self, hostname, **kwargs):
        return self._patch(f"/instances/{hostname}", json=kwargs)

    def delete_instance(self, hostname):
        return self._delete(f"/instances/{hostname}")

    def delete_instances(self, hostnames):
        return self._delete("/instances", json={"instances": list(hostnames)})

    def ping_instances(self):
        return self._get("/instances/ping")

    def reload_instances(self):
        return self._post("/instances/reload")

    def stop_instances(self):
        return self._post("/instances/stop")

    # ── Bans ────────────────────────────────────────────────────────────

    def get_bans(self):
        data = self._get("/bans")
        return data

    def ban(self, bans: list):
        return self._post("/bans/ban", json=bans)

    def unban(self, unbans: list):
        return self._post("/bans/unban", json=unbans)

    # ── Cache ───────────────────────────────────────────────────────────

    def get_cache_files(self, service=None, plugin=None, job_name=None, with_data=False):
        params = {}
        if service:
            params["service"] = service
        if plugin:
            params["plugin"] = plugin
        if job_name:
            params["job_name"] = job_name
        if with_data:
            params["with_data"] = "true"
        return self._get("/cache", params=params).get("cache", [])

    def get_cache_file(self, service, plugin, job, filename, download=False):
        params = {"download": "true"} if download else {}
        path = f"/cache/{service or 'global'}/{plugin}/{job}/{filename}"
        if download:
            return self._raw_request("GET", path, params=params)
        return self._get(path, params=params)

    def delete_cache_files(self, cache_files: list):
        return self._delete("/cache", json={"cache_files": cache_files})

    def delete_cache_file(self, service, plugin, job, filename):
        path = f"/cache/{service or 'global'}/{plugin}/{job}/{filename}"
        return self._delete(path)

    # ── Web cache (proxy_cache) ─────────────────────────────────────────

    def get_web_cache_status(self):
        return self._get("/web-cache/status")

    def get_web_cache_metrics(self):
        return self._get("/web-cache/metrics")

    def purge_web_cache(self, scope="all", urls=None):
        payload = {"scope": scope}
        if urls:
            payload["urls"] = urls
        return self._post("/web-cache/purge", json=payload)

    # ── Jobs ────────────────────────────────────────────────────────────

    def get_jobs(self):
        return self._get("/jobs").get("jobs", [])

    def run_jobs(self, jobs: list):
        return self._post("/jobs/run", json={"jobs": jobs})

    # ── Services ────────────────────────────────────────────────────────

    def get_services(self, with_drafts=True):
        params = {}
        if with_drafts:
            params["with_drafts"] = "true"
        return self._get("/services", params=params).get("services", [])

    def get_service(self, service_id, full=False, methods=True, with_drafts=True):
        params = {}
        if full:
            params["full"] = "true"
        if not methods:
            params["methods"] = "false"
        if with_drafts:
            params["with_drafts"] = "true"
        data = self._get(f"/services/{service_id}", params=params)
        return data.get("config", data)

    def create_service(self, server_name, variables=None, is_draft=None):
        payload = {"server_name": server_name}
        if variables is not None:
            payload["variables"] = variables
        if is_draft is not None:
            payload["is_draft"] = is_draft
        return self._post("/services", json=payload)

    def update_service(self, service_id, **kwargs):
        return self._patch(f"/services/{service_id}", json=kwargs)

    def delete_service(self, service_id):
        return self._delete(f"/services/{service_id}")

    def convert_service(self, service_id, convert_to):
        return self._post(f"/services/{service_id}/convert", params={"convert_to": convert_to})

    # ── Configs ─────────────────────────────────────────────────────────

    def get_configs(self, service=None, type=None, with_drafts=True, with_data=False):
        params = {}
        if service:
            params["service"] = service
        if type:
            params["type"] = type
        if with_drafts:
            params["with_drafts"] = "true"
        if with_data:
            params["with_data"] = "true"
        return self._get("/configs", params=params).get("configs", [])

    def get_config_item(self, service, type, name, with_data=True):
        params = {"with_data": "true"} if with_data else {}
        data = self._get(f"/configs/{service or 'global'}/{type}/{name}", params=params)
        return data.get("config", data)

    def create_config(self, **kwargs):
        return self._post("/configs", json=kwargs)

    def update_config(self, service, type, name, body=None, **kwargs):
        return self._patch(f"/configs/{service or 'global'}/{type}/{name}", json=body if body is not None else kwargs)

    def delete_configs(self, configs: list):
        return self._delete("/configs", json={"configs": configs})

    def delete_config(self, service, type, name):
        return self._delete(f"/configs/{service or 'global'}/{type}/{name}")

    def bulk_save_configs(self, custom_configs, method, changed=True):
        return self._put("/configs/bulk", json={"custom_configs": list(custom_configs), "method": method, "changed": changed})

    # ── Plugins ─────────────────────────────────────────────────────────

    def get_plugins(self, type="all", with_data=False):
        params = {"type": type}
        if with_data:
            params["with_data"] = "true"
        plugins = self._get("/plugins", params=params).get("plugins", [])
        if with_data:
            from base64 import b64decode

            for plugin in plugins:
                if isinstance(plugin.get("data"), str):
                    plugin["data"] = b64decode(plugin["data"])
        return plugins

    def delete_plugin(self, plugin_id):
        return self._delete(f"/plugins/{plugin_id}")

    def upload_plugins(self, files, method="ui"):
        # files should be a list of (filename, file_obj) tuples
        # Remove Content-Type header for multipart upload
        resp = self._request("POST", "/plugins/upload", files=files, data={"method": method}, headers={"Content-Type": None})
        return resp

    def get_plugin_page(self, plugin_id):
        resp = self._raw_request("GET", f"/plugins/{plugin_id}/page")
        return resp.content

    # ── Users ───────────────────────────────────────────────────────────

    def create_user(self, username, password, **kwargs):
        return self._post("/users", json={"username": username, "password": password} | kwargs)

    def get_user(self, username):
        data = self._get(f"/users/{username}")
        return data.get("user", data)

    def update_user(self, username, **kwargs):
        return self._patch(f"/users/{username}", json=kwargs)

    def get_user_sessions(self, username, current_session_id=None):
        params = {}
        if current_session_id:
            params["current_session_id"] = current_session_id
        return self._get(f"/users/{username}/sessions", params=params).get("sessions", [])

    def delete_user_sessions(self, username):
        return self._delete(f"/users/{username}/sessions")

    def mark_user_login(self, username, ip, user_agent):
        return self._post(f"/users/{username}/login", json={"ip": ip, "user_agent": user_agent}).get("session_id")

    def refresh_recovery_codes(self, username, codes):
        return self._post(f"/users/{username}/recovery-codes/refresh", json={"codes": codes})

    def use_recovery_code(self, username, hashed_code):
        return self._post(f"/users/{username}/recovery-codes/use", json={"hashed_code": hashed_code})

    # ── User Preferences ────────────────────────────────────────────────

    def get_user_preferences(self, username, table_name):
        return self._get(f"/users/{username}/preferences/{table_name}").get("preferences", {})

    def update_user_preferences(self, username, table_name, columns):
        return self._patch(f"/users/{username}/preferences/{table_name}", json={"columns": columns})

    def mark_user_access(self, username, session_id):
        return self._post(f"/users/{username}/access", json={"session_id": session_id})

    def get_user_permissions(self, username):
        return self._get(f"/users/{username}/permissions").get("permissions", [])

    def get_user_for_auth(self, username):
        """Get user with auth data (password hash) for Flask-Login."""
        return self._get(f"/users/{username}", params={"auth": "true"}).get("user")

    def get_admin_user(self, auth=False):
        """Get the admin user. Returns None if no admin exists."""
        try:
            params = {"auth": "true"} if auth else {}
            data = self._get("/users", params=params)
            return data.get("user")
        except ApiClientError as e:
            if e.status_code == 404:
                return None
            raise

    def save_config(self, config, method, changed=False):
        """Save a complete config dict via PUT /global_settings/config."""
        return self._put("/global_settings/config", json={"config": config, "method": method, "changed": changed})

    # ── Templates ───────────────────────────────────────────────────────

    def get_templates(self):
        return self._get("/templates").get("templates", {})

    def get_template(self, template_id):
        data = self._get(f"/templates/{template_id}")
        return data.get("template", data)

    def create_template(self, template_id, name, **kwargs):
        return self._post("/templates", json={"id": template_id, "name": name} | kwargs)

    def update_template(self, template_id, **kwargs):
        return self._patch(f"/templates/{template_id}", json=kwargs)

    def delete_template(self, template_id):
        return self._delete(f"/templates/{template_id}")

    # ── Metadata ────────────────────────────────────────────────────────

    def get_metadata(self):
        return self._get("/metadata").get("metadata", {})

    def update_metadata(self, data: dict):
        return self._patch("/metadata", json={"data": data})
