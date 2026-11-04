"""Small stand-ins for the scheduler's collaborators (database, job scheduler, API clients)."""

from types import SimpleNamespace


class FakeDb:
    """The slice of ``Database`` that ``src/scheduler/main.py`` calls. Every call is recorded."""

    def __init__(self, instances=None):
        self.readonly = False
        self.database_uri = "sqlite:////tmp/unit.db"
        self.instances = list(instances or [])
        self.configs = []
        self.plugins = []
        self.cache_rows = []
        self.cache_data = {}
        self.config = {"SERVER_NAME": "www.example.com"}
        self.metadata = {
            "is_initialized": True,
            "scheduler_first_start": False,
            "pro_plugins_changed": False,
            "external_plugins_changed": False,
            "custom_configs_changed": False,
            "plugins_config_changed": [],
            "instances_changed": False,
            "last_pro_plugins_change": None,
            "last_external_plugins_change": None,
            "last_custom_configs_change": None,
            "last_instances_change": None,
        }
        self.calls = []
        self.metadata_script = []
        self.metadata_error = None
        self.save_error = ""
        self.save_raises = None
        self.update_instance_result = ""
        self.checked_changes_result = ""
        self.set_metadata_result = ""
        self.update_external_plugins_result = ""
        self.compatibility_error = ""

    def get_instances(self):
        return [dict(i) for i in self.instances]

    def update_instance(self, hostname, status):
        self.calls.append(("update_instance", hostname, status))
        return self.update_instance_result

    def update_instances(self, instances, method=None):
        self.calls.append(("update_instances", instances, method))
        return ""

    def get_custom_configs(self):
        return list(self.configs)

    def get_custom_config_compatibility_error(self, config_type, service_id=None, with_drafts=False):
        return self.compatibility_error

    def save_custom_configs(self, configs, method):
        self.calls.append(("save_custom_configs", configs, method))
        if self.save_raises:
            raise self.save_raises
        return self.save_error

    def get_plugins(self, _type="external", with_data=False):
        self.calls.append(("get_plugins", _type, with_data))
        return list(self.plugins)

    def update_external_plugins(self, plugins, _type="external", delete_missing=True, preserve_ids=None):
        self.calls.append(("update_external_plugins", plugins, _type, preserve_ids))
        return self.update_external_plugins_result

    def get_jobs_cache_files(self, with_data=True, plugin_id=None, job_name=None):
        rows = self.cache_rows
        if plugin_id:
            rows = [r for r in rows if r["plugin_id"] == plugin_id]
        if job_name:
            rows = [r for r in rows if r["job_name"] == job_name]
        return list(rows)

    def get_job_cache_file(self, job_name, file_name, service_id=""):
        return self.cache_data.get((job_name, file_name, service_id or ""))

    def checked_changes(self, changes=None, plugins_changes=None):
        self.calls.append(
            (
                "checked_changes",
                list(changes) if isinstance(changes, list) else changes,
                list(plugins_changes) if isinstance(plugins_changes, list) else plugins_changes,
            )
        )
        return self.checked_changes_result

    def get_config(self):
        return dict(self.config)

    def get_metadata(self):
        if self.metadata_script:
            return self.metadata_script.pop(0)
        if self.metadata_error:
            return self.metadata_error
        return dict(self.metadata)

    def set_metadata(self, data):
        self.calls.append(("set_metadata", data))
        return self.set_metadata_result

    def close(self):
        self.calls.append(("close",))


class FakeApi:
    def __init__(self, endpoint="http://bw:5000/", answer=(True, "", 200, {"status": "success", "msg": "ok"})):
        self.endpoint = endpoint
        self.answer = answer
        self.requests = []

    def request(self, method, url, **kwargs):
        self.requests.append((method, url))
        if isinstance(self.answer, BaseException):
            raise self.answer
        return self.answer


class FakeScheduler:
    """Stands in for ``JobScheduler`` inside ``main.py``; records the pushes and reloads it is asked for."""

    def __init__(self, db=None, apis=None):
        self.db = db or FakeDb()
        self.apis = list(apis or [])
        self.env = {"SERVER_NAME": "www.example.com"}
        self.cleared = False
        self.sent = []
        self.send_ok = True
        self.responses = {}
        self.reloads = []
        self.reload_answer = (True, {})
        self.send_to_apis_calls = []
        self.updated_jobs = 0
        self.reload_calls = []
        self.reload_result = True
        self.failed_jobs = []
        self.pending = (False, False)
        self.run_once_calls = []
        self.run_once_result = True
        self.run_pending_calls = 0
        self.generation_pending = False
        self.readonly_probes = []

    def clear(self):
        self.cleared = True

    def send_files(self, path, endpoint, timeout=None, response=False):
        self.sent.append((path, endpoint))
        if response:
            return self.send_ok, dict(self.responses)
        return self.send_ok

    def send_to_apis(self, method, url, **kwargs):
        self.send_to_apis_calls.append((method, url, kwargs))
        return self.reload_answer

    def update_jobs(self):
        self.updated_jobs += 1

    def reload(self, env, apis=None, *, changed_plugins=None, ignore_plugins=None):
        self.reload_calls.append((env, list(changed_plugins or []), ignore_plugins))
        return self.reload_result

    def run_once(self, plugins=None, ignore_plugins=None):
        self.run_once_calls.append(plugins)
        return self.run_once_result

    def consume_pending_publication(self):
        return self.pending

    def run_pending(self):
        self.run_pending_calls += 1
        return True

    def try_database_readonly(self, force=False):
        self.readonly_probes.append(force)
        return self.db.readonly


def instance(hostname="bw1", port=5000, **extra):
    return {
        "hostname": hostname,
        "port": port,
        "https_port": 5443,
        "listen_https": False,
        "status": "up",
        "name": hostname,
        "type": "static",
        "method": "manual",
        "last_seen": None,
        **extra,
    }


def namespace(**kwargs):
    return SimpleNamespace(**kwargs)
