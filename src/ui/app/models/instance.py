#!/usr/bin/env python3
from contextlib import suppress
from datetime import datetime, timedelta
from heapq import heappush, heapreplace
from json import loads
from operator import itemgetter
from os import getenv
from traceback import format_exc
from typing import Any, List, Literal, Optional, Tuple, Union

from urllib.parse import quote

from API import API  # type: ignore
from ApiCaller import ApiCaller  # type: ignore

from app.utils import LOGGER, RESERVED_SERVICE_NAMES


class Instance:
    hostname: str
    name: str
    method: Literal["ui", "scheduler", "autoconf", "manual"]
    status: Literal["loading", "up", "down"]
    type: Literal["static", "container", "pod"]
    creation_date: datetime
    last_seen: datetime
    apiCaller: ApiCaller

    def __init__(
        self,
        hostname: str,
        name: str,
        method: Literal["ui", "scheduler", "autoconf", "manual"],
        status: Literal["loading", "up", "down"],
        type: Literal["static", "container", "pod"],
        creation_date: datetime,
        last_seen: datetime,
        apiCaller: ApiCaller,
    ) -> None:
        self.hostname = hostname
        self.name = name
        self.method = method
        self.status = status
        self.type = type
        self.creation_date = creation_date
        self.last_seen = last_seen
        self.apiCaller = apiCaller or ApiCaller()

    @staticmethod
    def from_hostname(hostname: str, db) -> Optional["Instance"]:
        instance = db.get_instance(hostname)
        if not instance:
            return None

        return Instance(
            instance["hostname"],
            instance["server_name"],
            instance["method"],
            instance["status"],
            instance["type"],
            instance["creation_date"],
            instance["last_seen"],
            ApiCaller([API.from_instance(instance)]),
        )

    @property
    def id(self) -> str:
        return self.hostname

    def reload(self) -> str:
        try:
            result = self.apiCaller.send_to_apis("POST", f"/reload?test={'no' if getenv('DISABLE_CONFIGURATION_TESTING', 'no').lower() == 'yes' else 'yes'}")[0]
        except BaseException as e:
            return f"Can't reload instance {self.hostname}: {e}"

        if result:
            return f"Instance {self.hostname} has been reloaded."
        return f"Can't reload instance {self.hostname}"

    def start(self) -> str:
        raise NotImplementedError("Method not implemented yet")
        try:
            result = self.apiCaller.send_to_apis("POST", "/start")[0]
        except BaseException as e:
            return f"Can't start instance {self.hostname}: {e}"

        if result:
            return f"Instance {self.hostname} has been started."
        return f"Can't start instance {self.hostname}"

    def stop(self) -> str:
        try:
            result = self.apiCaller.send_to_apis("POST", "/stop")[0]
        except BaseException as e:
            return f"Can't stop instance {self.hostname}: {e}"

        if result:
            return f"Instance {self.hostname} has been stopped."
        return f"Can't stop instance {self.hostname}"

    def restart(self) -> str:
        try:
            result = self.apiCaller.send_to_apis("POST", "/restart")[0]
        except BaseException as e:
            return f"Can't restart instance {self.hostname}: {e}"

        if result:
            return f"Instance {self.hostname} has been restarted."
        return f"Can't restart instance {self.hostname}"

    def ban(self, ip: str, exp: float, reason: str, service: str, ban_scope: str = "global") -> str:
        try:
            # Ensure ban_scope is either 'global' or 'service'
            if ban_scope not in ("global", "service"):
                ban_scope = "global"

            # If ban_scope is service but no valid service provided, default to global
            if ban_scope == "service" and (not service or service in RESERVED_SERVICE_NAMES):
                ban_scope = "global"

            result = self.apiCaller.send_to_apis("POST", "/ban", data={"ip": ip, "exp": exp, "reason": reason, "service": service, "ban_scope": ban_scope})[0]
        except BaseException as e:
            return f"Can't ban {ip} on instance {self.hostname}: {e}"

        if result:
            scope_text = "globally" if ban_scope == "global" else f"for service {service}"
            return f"IP {ip} has been banned {scope_text} on instance {self.hostname} for {exp} seconds{f' with reason: {reason}' if reason else ''}."
        return f"Can't ban {ip} on instance {self.hostname}"

    def unban(self, ip: str, service: Optional[str] = None, ban_scope: str = "global") -> str:
        try:
            # Prepare request data
            data = {"ip": ip, "ban_scope": ban_scope}
            if service and service not in RESERVED_SERVICE_NAMES:
                data["service"] = service
            result = self.apiCaller.send_to_apis("POST", "/unban", data=data)[0]
        except BaseException as e:
            service_text = f" for service {service}" if service else ""
            return f"Can't unban {ip}{service_text} on instance {self.hostname}: {e}"

        if result:
            service_text = f" for service {service}" if service else ""
            return f"IP {ip} has been unbanned{service_text} on instance {self.hostname}."
        return f"Can't unban {ip} on instance {self.hostname}"

    def bans(self) -> Tuple[str, dict[str, Any]]:
        try:
            result = self.apiCaller.send_to_apis("GET", "/bans", response=True)
        except BaseException as e:
            return f"Can't get bans from instance {self.hostname}: {e}", {}

        if result[0]:
            return "", result[1]
        return f"Can't get bans from instance {self.hostname}", result[1]

    def reports(self) -> Tuple[bool, dict[str, Any]]:
        return self.apiCaller.send_to_apis("GET", "/metrics/requests", response=True)

    def reports_query(
        self,
        start: int = 0,
        length: int = 10,
        search: str = "",
        order_column: str = "date",
        order_dir: str = "desc",
        search_panes: str = "",
        count_only: bool = False,
    ) -> Tuple[bool, dict[str, Any]]:
        """Query reports with pagination and filtering support"""
        params = {
            "start": start,
            "length": length,
            "search": quote(search),
            "order_column": order_column,
            "order_dir": order_dir,
            "search_panes": quote(search_panes),
            "count_only": "true" if count_only else "false",
        }
        query_string = "&".join(f"{k}={v}" for k, v in params.items())
        return self.apiCaller.send_to_apis("GET", f"/metrics/requests/query?{query_string}", response=True)

    def metrics(self, plugin_id) -> Tuple[bool, dict[str, Any]]:
        return self.apiCaller.send_to_apis("GET", f"/metrics/{plugin_id}", response=True)

    def metrics_redis(self) -> Tuple[bool, dict[str, Any]]:
        return self.apiCaller.send_to_apis("GET", "/redis/stats", response=True)

    def ping(self, plugin_id: Optional[str] = None) -> Tuple[Union[bool, str], dict[str, Any]]:
        if not plugin_id:
            try:
                result = self.apiCaller.send_to_apis("GET", "/ping")
            except BaseException as e:
                return f"Can't ping instance {self.hostname}: {e}", {}

            if result[0]:
                return f"Instance {self.hostname} is up", result[1]
            return f"Can't ping instance {self.hostname}", result[1]
        return self.apiCaller.send_to_apis("POST", f"/{plugin_id}/ping", response=True)

    def data(self, plugin_endpoint) -> Tuple[bool, dict[str, Any]]:
        return self.apiCaller.send_to_apis("GET", f"/{plugin_endpoint}", response=True)


class InstancesUtils:
    _REPORT_PANE_FIELDS = ["ip", "country", "method", "url", "status", "reason", "server_name", "security_mode"]
    _REPORT_PANE_MAX_VALUES = 200

    def __init__(self, db):
        self.__db = db

    def _get_max_blocked_requests_redis(self) -> int:
        default_max = 100000
        try:
            config = self.__db.get_config(global_only=True, methods=False)
            value = int(config.get("METRICS_MAX_BLOCKED_REQUESTS_REDIS", default_max))
            return max(0, value)
        except Exception:
            return default_max

    def _get_redis_scan_start_index(self, redis_client, max_requests: int) -> int:
        if max_requests <= 0:
            return 0
        try:
            total_requests = redis_client.llen("requests")
            total_requests = int(total_requests or 0)
            return max(0, total_requests - max_requests)
        except Exception:
            return 0

    @staticmethod
    def _decode_redis_text(value: Any) -> str:
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return str(value)

    def _get_redis_top_ip_counts_from_facets(self, redis_client, *, limit: int = 10) -> tuple[list[tuple[str, int]], int]:
        """Read top blocked IPs and unique IP count from Redis request facets.

        Uses HSCAN + heap top-k to keep memory bounded even with large facet maps.
        """
        if limit < 0:
            limit = 0

        top_heap: list[tuple[int, str]] = []
        unique_ips = 0

        try:
            cursor = 0
            while True:
                cursor, raw_pairs = redis_client.hscan("requests:facet:ip", cursor=cursor, count=1000)

                for raw_ip, raw_count in raw_pairs.items():
                    ip = self._decode_redis_text(raw_ip).strip() or "unknown"
                    try:
                        count = int(self._decode_redis_text(raw_count))
                    except Exception:
                        continue
                    if count <= 0:
                        continue

                    unique_ips += 1

                    if limit == 0:
                        continue

                    item = (count, ip)
                    if len(top_heap) < limit:
                        heappush(top_heap, item)
                    elif item > top_heap[0]:
                        heapreplace(top_heap, item)

                if cursor == 0:
                    break
        except Exception:
            return [], 0

        top_items = sorted(((ip, count) for count, ip in top_heap), key=lambda item: (-item[1], item[0]))
        return top_items, unique_ips

    def _get_redis_pane_counts_from_facets(self, redis_client, pane_fields: List[str]) -> Optional[dict[str, dict[str, dict[str, int]]]]:
        pane_counts: dict[str, dict[str, dict[str, int]]] = {field: {} for field in pane_fields}
        has_values = False

        for field in pane_fields:
            max_values = max(0, self._REPORT_PANE_MAX_VALUES)
            top_heap: list[tuple[int, str]] = []

            try:
                cursor = 0
                while True:
                    cursor, raw_pairs = redis_client.hscan(f"requests:facet:{field}", cursor=cursor, count=1000)
                    if not raw_pairs and cursor == 0:
                        break

                    for raw_value, raw_count in raw_pairs.items():
                        value = self._decode_redis_text(raw_value) or "N/A"
                        try:
                            count = int(self._decode_redis_text(raw_count))
                        except Exception:
                            continue
                        if count <= 0:
                            continue

                        has_values = True
                        if max_values == 0:
                            continue

                        item = (count, value)
                        if len(top_heap) < max_values:
                            heappush(top_heap, item)
                        elif item > top_heap[0]:
                            heapreplace(top_heap, item)

                    if cursor == 0:
                        break
            except Exception:
                continue

            if max_values > 0:
                pane_counts[field] = {value: {"total": count, "count": count} for count, value in sorted(top_heap, key=lambda item: (-item[0], item[1]))}

        return pane_counts if has_values else None

    def _get_redis_pane_counts_streaming_fallback(
        self,
        redis_client,
        *,
        max_requests: int,
        pane_fields: List[str],
    ) -> dict[str, dict[str, dict[str, int]]]:
        pane_counts: dict[str, dict[str, dict[str, int]]] = {field: {} for field in pane_fields}
        seen_ids: set = set()
        scan_start_idx = self._get_redis_scan_start_index(redis_client, max_requests)

        for report in self._iter_redis_requests(redis_client, chunk_size=2000, start_index=scan_start_idx):
            report_id = report.get("id")
            if report_id is not None:
                if report_id in seen_ids:
                    continue
                seen_ids.add(report_id)

            status = report.get("status", 0)
            if not isinstance(status, int):
                try:
                    status = int(status)
                except Exception:
                    status = 0

            security_mode = report.get("security_mode")
            if not (400 <= status < 500 or security_mode == "detect"):
                continue

            for field in pane_fields:
                value = str(report.get(field, "N/A"))
                if value not in pane_counts[field]:
                    pane_counts[field][value] = {"total": 0, "count": 0}
                pane_counts[field][value]["total"] += 1
                pane_counts[field][value]["count"] += 1

        return pane_counts

    def _get_redis_requests_fast_page(
        self,
        redis_client,
        *,
        max_requests: int,
        start: int,
        length: int,
        order_dir: str,
    ) -> tuple[int, list[dict[str, Any]]]:
        """Fast pagination path for default date-ordered Redis requests queries.

        This path avoids scanning the whole Redis list and only reads the requested page.
        """
        if length <= 0:
            return 0, []

        try:
            total_requests = int(redis_client.llen("requests") or 0)
        except Exception:
            return 0, []

        if total_requests <= 0:
            return 0, []

        scan_start_idx = self._get_redis_scan_start_index(redis_client, max_requests)
        capped_total = max(0, total_requests - scan_start_idx)
        if capped_total <= 0 or start >= capped_total:
            return capped_total, []

        fetch_count = min(length, capped_total - start)
        if fetch_count <= 0:
            return capped_total, []

        raw_chunk = []
        if order_dir == "asc":
            start_idx = scan_start_idx + start
            end_idx = start_idx + fetch_count - 1
            raw_chunk = redis_client.lrange("requests", start_idx, end_idx)
        else:
            # Descending order: newest first from the capped window.
            end_idx = total_requests - 1 - start
            start_idx = max(scan_start_idx, end_idx - fetch_count + 1)
            raw_chunk = redis_client.lrange("requests", start_idx, end_idx)
            raw_chunk.reverse()

        reports: list[dict[str, Any]] = []
        seen_ids: set = set()
        for report_raw in raw_chunk:
            try:
                report = loads(report_raw)
            except Exception:
                continue
            if not isinstance(report, dict):
                continue

            report_id = report.get("id")
            if report_id is not None:
                if report_id in seen_ids:
                    continue
                seen_ids.add(report_id)

            reports.append(report)

        return capped_total, reports

    def get_instances(self, status: Optional[Literal["loading", "up", "down"]] = None) -> List[Instance]:
        return [
            Instance(
                instance["hostname"],
                instance["name"],
                instance["method"],
                instance["status"],
                instance["type"],
                instance["creation_date"],
                instance["last_seen"],
                ApiCaller([API.from_instance(instance)]),
            )
            for instance in self.__db.get_instances()
            if not status or instance["status"] == status
        ]

    def reload_instances(self, *, instances: Optional[List[Instance]] = None) -> Union[list[str], str]:
        return [
            instance.name for instance in instances or self.get_instances() if instance.status == "down" or instance.reload().startswith("Can't reload")
        ] or "Successfully reloaded instances"

    def ban(
        self, ip: str, exp: float, reason: str, service: str, ban_scope: str = "global", *, instances: Optional[List[Instance]] = None
    ) -> Union[list[str], str]:
        return [
            instance.name
            for instance in instances or self.get_instances(status="up")
            if instance.ban(ip, exp, reason, service, ban_scope).startswith("Can't ban")
        ] or ""

    def unban(self, ip: str, service: Optional[str] = None, ban_scope: str = "global", *, instances: Optional[List[Instance]] = None) -> Union[list[str], str]:
        return [
            instance.name for instance in instances or self.get_instances(status="up") if instance.unban(ip, service, ban_scope).startswith("Can't unban")
        ] or ""

    def get_bans(self, hostname: Optional[str] = None, *, instances: Optional[List[Instance]] = None) -> List[dict[str, Any]]:
        """Get unique bans from all instances or a specific instance and sort them by expiration date"""

        def get_instance_bans(instance: Instance) -> List[dict[str, Any]]:
            resp, instance_bans = instance.bans()
            if resp:
                return []
            return instance_bans[instance.hostname].get("data", [])

        bans: List[dict[str, Any]] = []
        if hostname:
            instance = Instance.from_hostname(hostname, self.__db)
            if not instance:
                return []
            bans = get_instance_bans(instance)
        else:
            for instance in instances or self.get_instances(status="up"):
                bans.extend(get_instance_bans(instance))

        # Improved deduplication that considers IP, scope, and service combination
        # A unique ban is defined by the combination of IP address, ban scope, and service
        unique_bans = {}
        for item in sorted(bans, key=itemgetter("exp")):
            # Normalize ban scope if not present
            if "ban_scope" not in item:
                if item.get("service", "_") == "_":
                    item["ban_scope"] = "global"
                else:
                    item["ban_scope"] = "service"

            # Create a unique key that combines IP, ban scope, and service
            ban_key = (item["ip"], item["ban_scope"], item.get("service", "_"))
            if ban_key not in unique_bans:
                unique_bans[ban_key] = item

        return list(unique_bans.values())

    def get_reports(self, hostname: Optional[str] = None, *, instances: Optional[List[Instance]] = None) -> List[dict[str, Any]]:
        """Get reports from all instances or a specific instance and sort them by date"""

        def get_instance_reports(instance: Instance) -> List[dict[str, Any]]:
            resp, instance_reports = instance.reports()
            if not resp:
                return []
            return (instance_reports[instance.hostname].get("msg") or {"requests": []}).get("requests", [])

        reports: List[dict[str, Any]] = []
        if hostname:
            instance = Instance.from_hostname(hostname, self.__db)
            if not instance:
                return []
            reports = get_instance_reports(instance)
        else:
            for instance in instances or self.get_instances(status="up"):
                reports.extend(get_instance_reports(instance))

        return sorted(reports, key=itemgetter("date"), reverse=True)

    def get_report_data(
        self,
        report_id: str,
        hostname: Optional[str] = None,
        *,
        instances: Optional[List[Instance]] = None,
    ) -> Optional[Any]:
        """Get the `data` field for a specific report ID."""
        from app.routes.utils import get_redis_client

        if not report_id:
            return None

        redis_client = get_redis_client()

        if redis_client and not hostname:
            try:
                max_redis_requests = self._get_max_blocked_requests_redis()
                if max_redis_requests == 0:
                    return {}
                scan_start_idx = self._get_redis_scan_start_index(redis_client, max_redis_requests)
                matched_report = None
                matched_date = float("-inf")
                for report in self._iter_redis_requests(redis_client, chunk_size=2000, start_index=scan_start_idx):
                    if str(report.get("id", "")) != report_id:
                        continue
                    report_date = float(report.get("date", 0) or 0)
                    if report_date >= matched_date:
                        matched_date = report_date
                        matched_report = report
                if matched_report is not None:
                    return matched_report.get("data", {})
            except Exception as e:
                LOGGER.warning(f"Failed to fetch report data from Redis: {e}")

        # Fallback to instance APIs (or when hostname is specified)
        best_match = None
        best_date = float("-inf")
        target_instances = []
        if hostname:
            instance = Instance.from_hostname(hostname, self.__db)
            if instance:
                target_instances = [instance]
            else:
                # A non-instance hostname can be sent by the UI (e.g. service/server_name).
                # Fall back to searching across instances instead of returning no data.
                target_instances = instances or self.get_instances(status="up")
        else:
            target_instances = instances or self.get_instances(status="up")

        for instance in target_instances:
            try:
                resp, instance_reports = instance.reports()
            except Exception:
                continue
            if not resp:
                continue
            reports = (instance_reports.get(instance.hostname, {}).get("msg") or {"requests": []}).get("requests", [])
            if not isinstance(reports, list):
                continue
            for report in reports:
                if str(report.get("id", "")) != report_id:
                    continue
                report_date = float(report.get("date", 0) or 0)
                if report_date >= best_date:
                    best_date = report_date
                    best_match = report

        if best_match is None:
            return None
        return best_match.get("data", {})

    def get_reports_pane_counts(
        self,
        hostname: Optional[str] = None,
        *,
        instances: Optional[List[Instance]] = None,
    ) -> dict[str, dict[str, dict[str, int]]]:
        """Get SearchPanes counts without loading report pages in memory."""
        from app.routes.utils import get_redis_client

        pane_fields = self._REPORT_PANE_FIELDS
        redis_client = get_redis_client()

        if redis_client and not hostname:
            try:
                max_redis_requests = self._get_max_blocked_requests_redis()
                if max_redis_requests == 0:
                    return {field: {} for field in pane_fields}

                facet_counts = self._get_redis_pane_counts_from_facets(redis_client, pane_fields)
                if facet_counts is not None:
                    return facet_counts

                return self._get_redis_pane_counts_streaming_fallback(
                    redis_client,
                    max_requests=max_redis_requests,
                    pane_fields=pane_fields,
                )
            except Exception as e:
                LOGGER.warning(f"Failed to compute pane counts from Redis: {e}")

        # Fallback to instances when Redis is unavailable or scoped by hostname.
        reports = self.get_reports(hostname=hostname, instances=instances)
        return self._calculate_pane_counts(reports, reports)

    def get_reports_query(
        self,
        start: int = 0,
        length: int = 10,
        search: str = "",
        order_column: str = "date",
        order_dir: str = "desc",
        search_panes: str = "",
        count_only: bool = False,
        include_pane_counts: bool = True,
        hostname: Optional[str] = None,
        *,
        instances: Optional[List[Instance]] = None,
    ) -> dict[str, Any]:
        """Get paginated and filtered reports using optimized query endpoint.

        This method uses memory-efficient streaming to process large Redis datasets.
        Pane counts are computed incrementally during the streaming pass.
        """
        from app.routes.utils import get_redis_client

        redis_client = get_redis_client()

        def parse_search_panes(search_panes_value: str) -> dict[str, list[str]]:
            pane_filters: dict[str, list[str]] = {}
            if not search_panes_value:
                return pane_filters
            for field_filter in search_panes_value.split(";"):
                if ":" in field_filter:
                    field, values = field_filter.split(":", 1)
                    pane_filters[field] = values.split(",")
            return pane_filters

        def matches_filters(report: dict[str, Any], search_value: str, pane_filters: dict[str, list[str]]) -> bool:
            if search_value:
                search_lower = search_value.lower()
                if not any(
                    search_lower in str(report.get(field, "")).lower()
                    for field in ("ip", "country", "method", "url", "status", "user_agent", "reason", "server_name")
                ):
                    return False

            for field, allowed_values in pane_filters.items():
                if str(report.get(field, "N/A")) not in allowed_values:
                    return False

            return True

        # If Redis is available, use it for optimized queries
        if redis_client and not hostname:
            try:
                max_redis_requests = self._get_max_blocked_requests_redis()
                if max_redis_requests == 0:
                    if count_only:
                        return {"total": 0, "filtered": 0, "data": [], "pane_counts": {}}
                    return {"total": 0, "filtered": 0, "data": [], "pane_counts": {}}

                pane_filters = parse_search_panes(search_panes)
                pane_fields = self._REPORT_PANE_FIELDS
                selected_pane_values = {field: set(values) for field, values in pane_filters.items()}
                max_pane_values = max(0, self._REPORT_PANE_MAX_VALUES)
                pane_counts_enabled = include_pane_counts
                can_use_precomputed_pane_counts = pane_counts_enabled and search == "" and not pane_filters
                precomputed_pane_counts = self._get_redis_pane_counts_from_facets(redis_client, pane_fields) if can_use_precomputed_pane_counts else None
                use_precomputed_pane_counts = precomputed_pane_counts is not None
                pane_counts = precomputed_pane_counts if use_precomputed_pane_counts else ({field: {} for field in pane_fields} if pane_counts_enabled else {})

                is_default_fast_path = (
                    search == ""
                    and not pane_filters
                    and order_column == "date"
                    and order_dir in ("asc", "desc")
                    and length != -1
                    and (not pane_counts_enabled or use_precomputed_pane_counts)
                )
                if is_default_fast_path:
                    total_count, fast_reports = self._get_redis_requests_fast_page(
                        redis_client,
                        max_requests=max_redis_requests,
                        start=start,
                        length=length,
                        order_dir=order_dir,
                    )
                    return {"total": total_count, "filtered": total_count, "data": fast_reports, "pane_counts": pane_counts}

                if count_only and use_precomputed_pane_counts:
                    try:
                        total_requests = int(redis_client.llen("requests") or 0)
                    except Exception:
                        total_requests = 0
                    scan_start_idx = self._get_redis_scan_start_index(redis_client, max_redis_requests)
                    capped_total = max(0, total_requests - scan_start_idx)
                    return {"total": capped_total, "filtered": capped_total, "data": [], "pane_counts": pane_counts}

                seen_ids: set = set()
                valid_total = 0
                filtered_count = 0
                filtered_requests: List[dict[str, Any]] = []

                use_heap_pagination = not count_only and length != -1 and order_column == "date" and (start + length) > 0
                top_k = start + length if use_heap_pagination else 0
                top_reports: List[tuple[float, int, dict[str, Any]]] = []
                heap_seq = 0
                is_desc = order_dir == "desc"

                scan_start_idx = self._get_redis_scan_start_index(redis_client, max_redis_requests)
                for report in self._iter_redis_requests(redis_client, chunk_size=2000, start_index=scan_start_idx):
                    report_id = report.get("id")
                    if report_id is not None:
                        if report_id in seen_ids:
                            continue
                        seen_ids.add(report_id)

                    status = report.get("status", 0)
                    if not isinstance(status, int):
                        try:
                            status = int(status)
                        except Exception:
                            status = 0
                    security_mode = report.get("security_mode")
                    if not (400 <= status < 500 or security_mode == "detect"):
                        continue

                    valid_total += 1
                    matches = matches_filters(report, search, pane_filters)

                    if pane_counts_enabled and not use_precomputed_pane_counts:
                        # Update pane counts incrementally to avoid a second pass.
                        for field in pane_fields:
                            value = str(report.get(field, "N/A"))
                            if value not in pane_counts[field]:
                                # Keep pane maps bounded for high-cardinality fields
                                # while always retaining currently selected values.
                                if max_pane_values and len(pane_counts[field]) >= max_pane_values and value not in selected_pane_values.get(field, set()):
                                    continue
                                pane_counts[field][value] = {"total": 0, "count": 0}
                            pane_counts[field][value]["total"] += 1
                            if matches:
                                pane_counts[field][value]["count"] += 1

                    if matches:
                        filtered_count += 1
                        if not count_only:
                            if use_heap_pagination:
                                date_value = float(report.get("date", 0) or 0)
                                heap_key = date_value if is_desc else -date_value
                                item = (heap_key, heap_seq, report)
                                heap_seq += 1
                                if len(top_reports) < top_k:
                                    heappush(top_reports, item)
                                elif heap_key > top_reports[0][0]:
                                    heapreplace(top_reports, item)
                            else:
                                filtered_requests.append(report)

                if count_only:
                    return {"total": valid_total, "filtered": filtered_count, "data": [], "pane_counts": pane_counts if pane_counts_enabled else {}}

                if use_heap_pagination:
                    selected_reports = [item[2] for item in top_reports]
                    selected_reports = self._sort_reports(selected_reports, order_column, order_dir)
                    paginated = selected_reports[start:] if length == -1 else selected_reports[start : start + length]  # noqa: E203
                else:
                    # Sort and paginate
                    filtered_requests = self._sort_reports(filtered_requests, order_column, order_dir)
                    if length == -1:
                        paginated = filtered_requests
                    else:
                        paginated = filtered_requests[start : start + length]  # noqa: E203
                    # Clear the large list after pagination to help GC
                    del filtered_requests

                return {"total": valid_total, "filtered": filtered_count, "data": paginated, "pane_counts": pane_counts}
            except Exception as e:
                LOGGER.error(f"Error querying Redis for reports: {e}")
                LOGGER.debug(format_exc())
                # Fall through to instance queries

        # Query instances directly
        result = {"total": 0, "filtered": 0, "data": [], "pane_counts": {}}

        if hostname:
            instance = Instance.from_hostname(hostname, self.__db)
            if instance:
                api_result = instance.reports_query(start, length, search, order_column, order_dir, search_panes, count_only)
                if api_result[0] and isinstance(api_result[1], dict):
                    instance_response = api_result[1].get(instance.hostname, {}).get("msg", {})
                    if isinstance(instance_response, dict):
                        result = instance_response
        else:
            # Aggregate from all instances
            all_data = []
            total_count = 0

            for instance in instances or self.get_instances(status="up"):
                api_result = instance.reports_query(0, -1, search, order_column, "desc", search_panes, False)
                if api_result[0] and isinstance(api_result[1], dict):
                    instance_response = api_result[1].get(instance.hostname, {}).get("msg", {})
                    if isinstance(instance_response, dict) and "data" in instance_response:
                        all_data.extend(instance_response["data"])
                        total_count = max(total_count, instance_response.get("total", 0))

            # Deduplicate by ID
            seen_ids = set()
            unique_data = []
            for report in all_data:
                if report.get("id") not in seen_ids:
                    seen_ids.add(report.get("id"))
                    unique_data.append(report)

            if count_only:
                pane_counts = self._calculate_pane_counts(unique_data, unique_data) if include_pane_counts else {}
                result = {"total": total_count, "filtered": len(unique_data), "data": [], "pane_counts": pane_counts}
            else:
                # Sort and paginate
                sorted_data = self._sort_reports(unique_data, order_column, order_dir)
                if length == -1:
                    paginated = sorted_data
                else:
                    paginated = sorted_data[start : start + length]  # noqa: E203

                pane_counts = self._calculate_pane_counts(unique_data, unique_data)

                result = {"total": total_count, "filtered": len(unique_data), "data": paginated, "pane_counts": pane_counts}

        return result

    def _apply_report_filters(self, reports: List[dict], search: str, search_panes: str) -> List[dict]:
        """Apply search and search panes filters to reports"""
        filtered = reports

        # Global search
        if search:
            search_lower = search.lower()
            filtered = [
                r
                for r in filtered
                if any(
                    search_lower in str(r.get(field, "")).lower()
                    for field in ("ip", "country", "method", "url", "status", "user_agent", "reason", "server_name")
                )
            ]

        # Search panes filters (format: field1:value1,value2;field2:value3)
        if search_panes:
            pane_filters = {}
            for field_filter in search_panes.split(";"):
                if ":" in field_filter:
                    field, values = field_filter.split(":", 1)
                    pane_filters[field] = values.split(",")

            for field, allowed_values in pane_filters.items():
                filtered = [r for r in filtered if str(r.get(field, "N/A")) in allowed_values]

        return filtered

    def _sort_reports(self, reports: List[dict], order_column: str, order_dir: str) -> List[dict]:
        """Sort reports by specified column and direction"""
        reverse = order_dir == "desc"

        if order_column == "date":
            return sorted(reports, key=lambda x: float(x.get("date", 0)), reverse=reverse)
        return sorted(reports, key=lambda x: x.get(order_column, ""), reverse=reverse)

    def _iter_redis_requests(self, redis_client, chunk_size: int = 2000, start_index: int = 0):
        start = max(0, start_index)
        while True:
            end = start + chunk_size - 1
            chunk = redis_client.lrange("requests", start, end)
            if not chunk:
                break
            for report_raw in chunk:
                try:
                    report = loads(report_raw)
                except Exception:
                    continue
                if isinstance(report, dict):
                    yield report
            if len(chunk) < chunk_size:
                break
            start += chunk_size

    def get_home_aggregates(self, hours: int = 24 * 7, top_ips_limit: int = 10) -> dict[str, Any]:
        """
        Compute home page aggregates (country counts, IP counts, time buckets)
        using streaming/chunked processing to minimize memory usage.

        This method processes requests in chunks and computes aggregates incrementally,
        only keeping the aggregated counts in memory instead of all request data.

        Args:
            hours: Number of hours to look back for requests (default: 24)

        Returns:
            Dictionary containing:
            - request_countries: Dict of country -> {blocked: count}
            - top_blocked_ips: Dict of IP -> {blocked: count}
            - blocked_unique_ips: Number of unique blocked IP addresses
            - time_buckets: Dict of ISO timestamp -> blocked count
            - request_statuses: Dict of status code -> count
        """
        from app.routes.utils import get_redis_client

        redis_client = get_redis_client()

        # Initialize aggregates
        request_countries: dict[str, dict[str, int]] = {}
        blocked_ip_counts: dict[str, int] = {}
        request_statuses: dict[int, int] = {}
        top_ips_from_facets, blocked_unique_ips = self._get_redis_top_ip_counts_from_facets(redis_client, limit=top_ips_limit)
        use_facet_ip_counts = blocked_unique_ips > 0

        current_date = datetime.now().astimezone()
        cutoff_timestamp = (current_date - timedelta(hours=hours)).timestamp()

        # Initialize time buckets for the last N hours
        time_buckets: dict[datetime, int] = {(current_date - timedelta(hours=i)).replace(minute=0, second=0, microsecond=0): 0 for i in range(hours)}

        if not redis_client:
            # Fallback: return empty aggregates if no Redis
            return {
                "request_countries": {},
                "top_blocked_ips": {},
                "blocked_unique_ips": 0,
                "time_buckets": {key.isoformat(): value for key, value in time_buckets.items()},
                "request_statuses": {},
            }

        max_redis_requests = self._get_max_blocked_requests_redis()
        if max_redis_requests == 0:
            return {
                "request_countries": {},
                "top_blocked_ips": {},
                "blocked_unique_ips": 0,
                "time_buckets": {key.isoformat(): value for key, value in time_buckets.items()},
                "request_statuses": {},
            }

        # Process requests in chunks using the iterator
        # This avoids loading all requests into memory at once
        scan_start_idx = self._get_redis_scan_start_index(redis_client, max_redis_requests)
        for request in self._iter_redis_requests(redis_client, chunk_size=2000, start_index=scan_start_idx):
            request_date = request.get("date", 0)

            # Skip requests older than cutoff
            if request_date < cutoff_timestamp:
                continue

            country = request.get("country", "unknown")
            status = request.get("status", 0)
            if not isinstance(status, int):
                with suppress(ValueError, TypeError):
                    status = int(status)
            if not isinstance(status, int):
                status = 0

            # Track status distribution in the selected window.
            request_statuses[status] = request_statuses.get(status, 0) + 1

            # Check if blocked (403, 429, 444)
            if status in (403, 429, 444):
                if country not in request_countries:
                    request_countries[country] = {"blocked": 0}
                request_countries[country]["blocked"] += 1

                if not use_facet_ip_counts:
                    ip = request.get("ip")
                    if ip is None or ip == "":
                        ip = "unknown"
                    ip_str = str(ip)
                    blocked_ip_counts[ip_str] = blocked_ip_counts.get(ip_str, 0) + 1

                # Add to time bucket
                with suppress(ValueError, OSError):
                    timestamp = datetime.fromtimestamp(request_date).astimezone()
                    bucket = timestamp.replace(minute=0, second=0, microsecond=0)
                    if bucket in time_buckets:
                        time_buckets[bucket] += 1

        if use_facet_ip_counts:
            top_blocked_ips = {ip: {"blocked": count} for ip, count in top_ips_from_facets}
        else:
            sorted_ips = sorted(blocked_ip_counts.items(), key=lambda item: (-item[1], item[0]))
            if top_ips_limit > 0:
                sorted_ips = sorted_ips[:top_ips_limit]
            top_blocked_ips = {ip: {"blocked": count} for ip, count in sorted_ips}
            blocked_unique_ips = len(blocked_ip_counts)
        blocked_total = sum(time_buckets.values())

        # Defensive fallback: if timeline has blocked data but statuses are empty,
        # keep status cards/charts usable.
        if blocked_total > 0 and not request_statuses:
            request_statuses[403] = blocked_total

        return {
            "request_countries": request_countries,
            "top_blocked_ips": top_blocked_ips,
            "blocked_unique_ips": blocked_unique_ips,
            "time_buckets": {key.isoformat(): value for key, value in time_buckets.items()},
            "request_statuses": request_statuses,
        }

    def _calculate_pane_counts(self, all_reports: List[dict], filtered_reports: List[dict]) -> dict:
        """Calculate search panes counts"""
        pane_counts = {}
        filtered_ids = {r.get("id") for r in filtered_reports}

        pane_fields = ["ip", "country", "method", "url", "status", "reason", "server_name", "security_mode"]

        for field in pane_fields:
            pane_counts[field] = {}

        for report in all_reports:
            for field in pane_fields:
                value = str(report.get(field, "N/A"))
                if value not in pane_counts[field]:
                    pane_counts[field][value] = {"total": 0, "count": 0}
                pane_counts[field][value]["total"] += 1
                if report.get("id") in filtered_ids:
                    pane_counts[field][value]["count"] += 1

        return pane_counts

    def get_metrics(self, plugin_id: str, hostname: Optional[str] = None, *, instances: Optional[List[Instance]] = None):
        """Get metrics from all instances or a specific instance, with Redis integration"""
        from app.routes.utils import get_redis_client

        redis_client = get_redis_client()

        def aggregate_metrics(base_metrics: dict, new_metrics: dict) -> dict[str, Any]:
            """Aggregate metrics from different sources"""
            for key, value in new_metrics.items():
                if key not in base_metrics:
                    base_metrics[key] = value
                    continue

                # Some values are the same for all instances, don't aggregate them
                if key == "redis_nb_keys":
                    continue

                # Aggregate based on value type
                if isinstance(value, (int, float)):
                    base_metrics[key] += value
                elif isinstance(value, str):
                    base_metrics[key] = value
                elif isinstance(value, list):
                    if isinstance(base_metrics[key], list):
                        base_metrics[key].extend(value)
                    else:
                        base_metrics[key] = value
                elif isinstance(value, dict):
                    if not isinstance(base_metrics[key], dict):
                        base_metrics[key] = {}
                    for k, v in value.items():
                        if k not in base_metrics[key]:
                            base_metrics[key][k] = v
                        elif isinstance(v, (int, float)):
                            base_metrics[key][k] += v
                        elif isinstance(v, list):
                            if isinstance(base_metrics[key][k], list):
                                base_metrics[key][k].extend(v)
                            else:
                                base_metrics[key][k] = v
                        else:
                            base_metrics[key][k] = v
            return base_metrics

        def get_redis_metrics() -> dict[str, Any]:
            """Get aggregated metrics from Redis"""
            if not redis_client:
                return {}

            try:
                if plugin_id == "requests":
                    # WARNING: Loading all requests into memory can consume significant memory
                    # for large Redis datasets. Consider using get_home_aggregates() for the
                    # home page or get_reports_query() for paginated report access instead.
                    max_redis_requests = self._get_max_blocked_requests_redis()
                    if max_redis_requests == 0:
                        return {"requests": []}

                    requests_list = []
                    seen_ids: set = set()
                    scan_start_idx = self._get_redis_scan_start_index(redis_client, max_redis_requests)
                    for request in self._iter_redis_requests(redis_client, chunk_size=2000, start_index=scan_start_idx):
                        req_id = request.get("id")
                        if req_id is not None:
                            if req_id in seen_ids:
                                continue
                            seen_ids.add(req_id)
                        requests_list.append(request)
                    return {"requests": requests_list}

                # Check if METRICS_SAVE_TO_REDIS is enabled for errors
                config = self.__db.get_config(global_only=True, methods=False)
                if config.get("METRICS_SAVE_TO_REDIS", "yes").lower() != "yes":
                    return {}

                if plugin_id == "errors":
                    # For errors, get all counter_* keys and aggregate them
                    pattern = "metrics:errors_counter_*"
                    keys = redis_client.keys(pattern)
                    error_counters = {}
                    for key in keys:
                        try:
                            key_str = key.decode("utf-8") if isinstance(key, bytes) else key
                            # Extract the error code from the key
                            error_code = key_str.split("counter_")[1].split(":")[0]
                            value = redis_client.get(key)
                            if value is not None:
                                count = int(value.decode("utf-8"))
                                counter_key = f"counter_{error_code}"
                                if counter_key in error_counters:
                                    error_counters[counter_key] += count
                                else:
                                    error_counters[counter_key] = count
                        except Exception:
                            continue
                    return error_counters

                redis_metrics = {}
                # Get all metric keys for this plugin from all workers
                pattern = f"metrics:{plugin_id}_*"
                keys = redis_client.keys(pattern)

                for key in keys:
                    try:
                        key_str = key.decode("utf-8") if isinstance(key, bytes) else key
                        # Extract metric name from key (remove prefix and worker suffix)
                        metric_name = key_str.replace(f"metrics:{plugin_id}_", "").split(":")[0]

                        # Determine Redis data type and get value accordingly
                        key_type = redis_client.type(key)
                        if isinstance(key_type, bytes):
                            key_type = key_type.decode("utf-8")

                        decoded_value = None

                        if key_type == "string":
                            # Handle string values (counters and simple metrics)
                            value = redis_client.get(key)
                            if value is None:
                                continue

                            # Decode value based on its content
                            try:
                                decoded_value = loads(value.decode("utf-8"))
                            except (ValueError, UnicodeDecodeError):
                                # Try as number
                                try:
                                    decoded_value = float(value.decode("utf-8"))
                                    if decoded_value.is_integer():
                                        decoded_value = int(decoded_value)
                                except ValueError:
                                    # Fall back to string
                                    decoded_value = value.decode("utf-8")

                        elif key_type == "list":
                            # Handle list values (table metrics)
                            list_values = redis_client.lrange(key, 0, -1)
                            decoded_value = []
                            for item in list_values:
                                try:
                                    decoded_item = loads(item.decode("utf-8"))
                                    decoded_value.append(decoded_item)
                                except (ValueError, UnicodeDecodeError):
                                    # Fall back to string
                                    decoded_value.append(item.decode("utf-8"))

                        elif key_type == "none":
                            # Key doesn't exist
                            continue
                        else:
                            # Unsupported Redis data type, skip
                            self.__db.logger.warning(f"Unsupported Redis data type {key_type} for key {key_str}")
                            continue

                        if decoded_value is None:
                            continue

                        # Aggregate values for the same metric name across workers
                        if metric_name in redis_metrics:
                            if isinstance(redis_metrics[metric_name], (int, float)) and isinstance(decoded_value, (int, float)):
                                redis_metrics[metric_name] += decoded_value
                            elif isinstance(redis_metrics[metric_name], list) and isinstance(decoded_value, list):
                                redis_metrics[metric_name].extend(decoded_value)
                            # For other types, just use the latest value
                        else:
                            redis_metrics[metric_name] = decoded_value

                    except Exception as e:
                        self.__db.logger.warning(f"Failed to process Redis metric key {key}: {e}")
                        continue

                return redis_metrics
            except Exception as e:
                self.__db.logger.warning(f"Failed to get metrics from Redis: {e}")
                return {}

        def get_instance_metrics(instance: Instance) -> dict[str, Any]:
            """Get metrics from a single instance"""
            try:
                if plugin_id == "redis":
                    resp, instance_metrics = instance.metrics_redis()
                else:
                    resp, instance_metrics = instance.metrics(plugin_id)
            except Exception as e:
                self.__db.logger.warning(f"Can't get metrics from {instance.hostname}: {e}")
                return {}

            if not resp:
                self.__db.logger.warning(f"Can't get metrics from {instance.hostname}")
                return {}

            instance_data = instance_metrics.get(instance.hostname, {})
            status = instance_data.get("status")

            if status != "success":
                self.__db.logger.warning(f"Can't get metrics from {instance.hostname}: {instance_data.get('msg')} - {status}")
                return {}

            # Handle both nested data structure and direct data response
            if "data" in instance_data and isinstance(instance_data["data"], dict):
                return instance_data["data"]
            elif isinstance(instance_data.get("msg"), dict):
                return instance_data["msg"]
            # For direct response format (like redis metrics)
            return {k: v for k, v in instance_data.items() if k not in ("status", "msg")}

        # Initialize metrics
        metrics = {}

        # If redis_client is available and we're not targeting a specific hostname,
        # prioritize Redis metrics as they're aggregated across all workers
        if redis_client and not hostname:
            redis_metrics = get_redis_metrics()
            if redis_metrics:
                # For requests (always in Redis) and errors (when METRICS_SAVE_TO_REDIS is enabled),
                # if we have Redis data, don't fetch from instances to avoid duplicates
                if (plugin_id == "requests" or (plugin_id == "errors" and redis_metrics)) and redis_metrics:
                    return redis_metrics
                metrics = aggregate_metrics(metrics, redis_metrics)

        # Get instance metrics (either as fallback or for specific hostname)
        if hostname:
            instance = Instance.from_hostname(hostname, self.__db)
            if instance:
                instance_metrics = get_instance_metrics(instance)
                metrics = aggregate_metrics(metrics, instance_metrics)
        else:
            # Only fetch from instances if we don't have Redis data for requests
            # or if errors metrics are not saved to Redis
            should_fetch_from_instances = True
            if redis_client and plugin_id == "requests" and metrics:
                should_fetch_from_instances = False
            elif redis_client and plugin_id == "errors" and metrics:
                should_fetch_from_instances = False

            if should_fetch_from_instances:
                for instance in instances or self.get_instances(status="up"):
                    instance_metrics = get_instance_metrics(instance)
                    metrics = aggregate_metrics(metrics, instance_metrics)

        return metrics

    def get_ping(self, plugin_id: str, *, instances: Optional[List[Instance]] = None):
        """Get ping from all instances and return the first success"""
        ping = {"status": "error"}
        for instance in instances or self.get_instances(status="up"):
            try:
                resp, ping_data = instance.ping(plugin_id)
            except:
                continue

            if not resp:
                continue

            ping["status"] = ping_data[instance.hostname].get("status", "error")

            if ping["status"] == "success":
                return ping
        return ping

    def get_data(self, plugin_endpoint: str, *, instances: Optional[List[Instance]] = None):
        """Get data from all instances and return the first success"""
        data = []
        for instance in instances or self.get_instances(status="up"):
            try:
                resp, instance_data = instance.data(plugin_endpoint)
            except:
                data.append({instance.hostname: {"status": "error"}})
                continue

            if not resp:
                data.append({instance.hostname: {"status": "error"}})
                continue

            if instance_data[instance.hostname].get("status", "error") == "error":
                data.append({instance.hostname: {"status": "error"}})
                continue

            data.append({instance.hostname: instance_data[instance.hostname].get("msg", {})})
        return data
