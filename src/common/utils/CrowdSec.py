"""CrowdSec control through configured BunkerWeb instances, shared by UI and API."""

from hashlib import sha256
from ipaddress import ip_address
from re import fullmatch
from time import time
from urllib.parse import urlencode

from API import API  # type: ignore


class CrowdSecError(Exception):
    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.status = status


def encode_connection(hostname: str, local_id: str) -> str:
    # Keep IDs within the existing 256-character API grant column, even for long hostnames.
    return sha256(hostname.encode()).hexdigest() + "_" + local_id


def decode_connection(connection_id: str) -> tuple[str, str]:
    match = fullmatch(r"([a-f0-9]{64})_([a-f0-9]{64})", connection_id) if isinstance(connection_id, str) else None
    if not match:
        raise CrowdSecError("Invalid CrowdSec connection", 400)
    return match.group(1), match.group(2)


class CrowdSecClient:
    def __init__(self, db):
        self.db = db

    def _instances(self) -> list[dict]:
        try:
            return self.db.get_instances()
        except Exception:
            raise CrowdSecError("Unable to read configured BunkerWeb instances") from None

    @staticmethod
    def _request(instance: dict, method: str, path: str, data: dict | None = None):
        try:
            ok, _message, status, payload = API.from_instance(instance).request(method, path, data=data, timeout=(5, 30))
        except Exception:
            raise CrowdSecError("BunkerWeb instance is unavailable") from None
        if not ok or not isinstance(payload, dict):
            raise CrowdSecError("BunkerWeb instance is unavailable")
        if status != 200 or payload.get("status") != "success":
            message = payload.get("msg")
            # Only this plugin's controlled messages are surfaced; transport errors can contain secrets.
            if not path.startswith("/crowdsec/") or not isinstance(message, str):
                message = "BunkerWeb instance could not complete the request"
            raise CrowdSecError(message[:1024], status if status in (400, 403, 404, 409) else 502)
        result = payload.get("data", payload.get("msg"))
        if path == "/bans" and result == "":
            return []
        if not isinstance(result, (dict, list)):
            raise CrowdSecError("BunkerWeb instance returned an unsupported response")
        return result

    def _resolve(self, connection_id: str) -> tuple[dict, str]:
        instance_key, local_id = decode_connection(connection_id)
        for instance in self._instances():
            hostname = instance.get("hostname")
            if isinstance(hostname, str) and sha256(hostname.encode()).hexdigest() == instance_key:
                return instance, local_id
        raise CrowdSecError("CrowdSec instance is no longer configured", 404)

    def connections(self) -> dict:
        connections, errors = [], {}
        for instance in self._instances():
            hostname = instance.get("hostname", "")
            try:
                result = self._request(instance, "POST", "/crowdsec/connections", {})
                if not isinstance(result, dict) or not isinstance(result.get("connections"), list):
                    raise CrowdSecError("BunkerWeb instance returned invalid CrowdSec connections")
                for item in result["connections"]:
                    if not isinstance(item, dict):
                        continue
                    connection = dict(item)
                    local_id = connection.get("id")
                    connection["local_id"] = local_id
                    connection["id"] = encode_connection(hostname, local_id) if isinstance(local_id, str) and fullmatch(r"[a-f0-9]{64}", local_id) else None
                    connection["instance"] = hostname
                    connections.append(connection)
            except CrowdSecError as exc:
                errors[hostname] = str(exc)
        return {"connections": connections, "errors": errors, "observed_at": time()}

    def query(self, connection_id: str, action: str, params: dict | None = None) -> dict:
        if action not in {"decisions", "alerts", "unban", "allowlists", "allowlistcheck"}:
            raise CrowdSecError("Invalid CrowdSec operation", 400)
        instance, local_id = self._resolve(connection_id)
        result = self._request(instance, "POST", f"/crowdsec/{action}", {**(params or {}), "connection": local_id})
        if not isinstance(result, dict):
            raise CrowdSecError("BunkerWeb instance returned an invalid CrowdSec response")
        return result

    def investigate(self, connection_id: str, ip: str) -> dict:
        try:
            ip = str(ip_address(ip))
        except ValueError:
            raise CrowdSecError("Invalid IP address", 400) from None
        instance, local_id = self._resolve(connection_id)
        mapping = self._request(instance, "POST", "/crowdsec/connections", {"connection": local_id})
        available = mapping.get("connections", []) if isinstance(mapping, dict) else []
        if not isinstance(available, list):
            raise CrowdSecError("BunkerWeb instance returned an invalid connection scope")
        selected = next((item for item in available if isinstance(item, dict) and item.get("id") == local_id), None)
        services = selected.get("services") if selected else None
        if (
            not isinstance(services, list)
            or not services
            or not all(isinstance(service, str) and service and ";" not in service and "," not in service for service in services)
        ):
            raise CrowdSecError("Unable to establish the selected CrowdSec service scope", 404)
        global_scope = services == ["global"]
        result = {"ip": ip, "connection": connection_id, "observed_at": time(), "errors": {}, "limits": {"decisions": 200, "alerts": 50, "reports": 50}}
        for action in ("decisions", "alerts"):
            try:
                data = self.query(connection_id, action, {"ip": ip, "limit": 200})
                result[action] = data.get(action, [])
                if action == "decisions":
                    result["decisions_total"] = data.get("total", len(result[action]))
            except CrowdSecError as exc:
                result[action] = []
                result["errors"][action] = str(exc)
        try:
            panes = f"ip:{ip}" + ("" if global_scope else ";server_name:" + ",".join(services))
            params = urlencode({"start": 0, "length": 50, "order_column": "date", "order_dir": "desc", "search_panes": panes})
            reports = self._request(instance, "GET", "/metrics/requests/query?" + params)
            if isinstance(reports, dict) and reports.get("data") == {}:
                reports["data"] = []
            if not isinstance(reports, dict) or not isinstance(reports.get("data"), list):
                raise CrowdSecError("BunkerWeb instance returned invalid report data")
            result["reports"] = [
                report
                for report in reports["data"]
                if isinstance(report, dict) and report.get("ip") == ip and (global_scope or report.get("server_name") in services)
            ][:50]
            result["reports_total"] = reports.get("filtered", len(result["reports"]))
        except CrowdSecError as exc:
            result["reports"] = []
            result["errors"]["reports"] = str(exc)
        try:
            bans = self._request(instance, "GET", "/bans")
            if isinstance(bans, dict):
                bans = bans.get("bans", [])
            if not isinstance(bans, list):
                raise CrowdSecError("BunkerWeb instance returned invalid bans")
            result["bans"] = []
            for ban in bans:
                try:
                    if isinstance(ban, dict) and ip_address(ban.get("ip", "")) == ip_address(ip):
                        applies_globally = ban.get("ban_scope") == "global" or (
                            ban.get("ban_scope") is None and ban.get("service") in (None, "", "_", "unknown", "Web UI", "bwcli", "default server")
                        )
                        if global_scope or applies_globally or ban.get("service") in services:
                            result["bans"].append(ban)
                except ValueError:
                    continue
        except CrowdSecError as exc:
            result["bans"] = []
            result["errors"]["bans"] = str(exc)
        try:
            result["allowlist"] = self.query(connection_id, "allowlistcheck", {"ip": ip})
        except CrowdSecError as exc:
            result["allowlist"] = None
            result["errors"]["allowlist"] = str(exc)
        return result
