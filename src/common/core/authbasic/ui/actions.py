from collections import Counter
from datetime import datetime
from json import loads as json_loads
from logging import getLogger
from operator import itemgetter
from traceback import format_exc


def _normalize_service_name(value):
    if value is None:
        return ""
    normalized = str(value).strip()
    if not normalized:
        return ""
    lowered = normalized.lower()
    if lowered in {"all", "any"}:
        return ""
    if lowered in {"default", "default_server"}:
        return "_"
    return normalized.lower()


def _format_date(raw_value):
    if isinstance(raw_value, (int, float)):
        try:
            return datetime.fromtimestamp(raw_value).isoformat()
        except (OSError, ValueError):
            return datetime.fromtimestamp(0).isoformat()
    try:
        return datetime.fromtimestamp(float(raw_value)).isoformat()
    except (TypeError, ValueError, OSError):
        return str(raw_value or "")


def _flatten_table_data(raw_data):
    if raw_data is None:
        return []
    if isinstance(raw_data, str):
        try:
            raw_data = json_loads(raw_data)
        except ValueError:
            return []
    if isinstance(raw_data, list):
        return raw_data
    if isinstance(raw_data, dict):
        flattened = []
        for value in raw_data.values():
            if isinstance(value, list):
                flattened.extend(value)
            elif value:
                flattened.append(value)
        return flattened
    return []


def _build_counter_data(entries, field_name, label):
    counter = Counter()
    for entry in entries:
        value = entry.get(field_name)
        if value in (None, ""):
            value = "N/A"
        counter[str(value)] += 1

    formatted = {label: [], "count": []}
    for value, count in counter.most_common():
        formatted[label].append(value)
        formatted["count"].append(count)
    return formatted


def pre_render(**kwargs):
    logger = getLogger("UI")
    ret = {
        "counter_passed_authbasic": {
            "value": 0,
            "title": "AUTH BASIC",
            "subtitle": "Successful",
            "subtitle_color": "success",
            "svg_color": "success",
        },
        "counter_failed_authbasic": {
            "value": 0,
            "title": "AUTH BASIC",
            "subtitle": "Failed",
            "subtitle_color": "danger",
            "svg_color": "danger",
        },
        "top_authbasic_users": {
            "col-size": "col-12 col-md-6",
            "data": {},
            "order": {
                "column": 1,
                "dir": "desc",
            },
            "svg_color": "primary",
        },
        "top_authbasic_failed_ips": {
            "col-size": "col-12 col-md-6",
            "data": {},
            "order": {
                "column": 1,
                "dir": "desc",
            },
            "svg_color": "warning",
        },
        "list_authbasic_authentications": {
            "col-size": "col-12",
            "data": {},
            "order": {
                "column": 0,
                "dir": "desc",
            },
            "svg_color": "primary",
        },
        "list_authbasic_configured_users": {
            "col-size": "col-12",
            "data": {},
            "order": {
                "column": 0,
                "dir": "asc",
            },
            "svg_color": "info",
        },
    }
    try:
        metrics = kwargs["bw_instances_utils"].get_metrics("authbasic")
        args = kwargs.get("args") or {}
        data_payload = kwargs.get("data") or {}
        service_filter = _normalize_service_name(
            args.get("service") or args.get("server_name") or data_payload.get("service") or data_payload.get("server_name")
        )
        apply_service_filter = bool(service_filter)

        # Get counters
        ret["counter_passed_authbasic"]["value"] = metrics.get("counter_passed_authbasic", 0)
        ret["counter_failed_authbasic"]["value"] = metrics.get("counter_failed_authbasic", 0)

        # Process authentication events from table data
        filtered_events = []
        list_fields = ["date", "ip", "server_name", "uri", "username", "success", "reason"]
        list_data = {field: [] for field in list_fields}

        table_sources = []
        if "table_authentications" in metrics:
            table_sources.append(metrics["table_authentications"])
        for key, value in metrics.items():
            if key.startswith("table_authentications_"):
                table_sources.append(value)

        if table_sources:
            seen_entries = set()
            for source in table_sources:
                for entry in _flatten_table_data(source):
                    entry_service = _normalize_service_name(entry.get("server_name"))
                    if apply_service_filter and entry_service != service_filter:
                        continue

                    # Create a unique key for deduplication
                    entry_key = (
                        entry.get("date", 0),
                        entry.get("ip", ""),
                        entry.get("username", ""),
                        entry.get("uri", ""),
                    )
                    if entry_key in seen_entries:
                        continue
                    seen_entries.add(entry_key)

                    filtered_events.append(entry)
                    list_data["date"].append(_format_date(entry.get("date", 0)))
                    list_data["ip"].append(entry.get("ip", ""))
                    list_data["server_name"].append(entry.get("server_name", ""))
                    list_data["uri"].append(entry.get("uri", ""))
                    list_data["username"].append(entry.get("username", ""))
                    list_data["success"].append("✓" if entry.get("success") else "✗")
                    list_data["reason"].append(entry.get("reason", "") if not entry.get("success") else "")

        ret["list_authbasic_authentications"]["data"] = list_data

        # Build top users (successful authentications)
        if filtered_events or apply_service_filter:
            successful_events = [e for e in filtered_events if e.get("success")]
            ret["top_authbasic_users"]["data"] = _build_counter_data(successful_events, "username", "user")

            failed_events = [e for e in filtered_events if not e.get("success")]
            ret["top_authbasic_failed_ips"]["data"] = _build_counter_data(failed_events, "ip", "ip")
        else:
            # Build from counter metrics
            format_data = [
                {"user": key.replace("counter_passed_user_", ""), "count": int(value)}
                for key, value in metrics.items()
                if key.startswith("counter_passed_user_")
            ]
            format_data.sort(key=itemgetter("count"), reverse=True)
            data = {"user": [], "count": []}
            for item in format_data:
                data["user"].append(item["user"])
                data["count"].append(item["count"])
            ret["top_authbasic_users"]["data"] = data

            format_data = [
                {"ip": key.replace("counter_failed_ip_", ""), "count": int(value)} for key, value in metrics.items() if key.startswith("counter_failed_ip_")
            ]
            format_data.sort(key=itemgetter("count"), reverse=True)
            data = {"ip": [], "count": []}
            for item in format_data:
                data["ip"].append(item["ip"])
                data["count"].append(item["count"])
            ret["top_authbasic_failed_ips"]["data"] = data

        # Build configured users table from successful authentication usernames
        # This provides visibility into which users are actively authenticating
        configured_users_data = {"scope": [], "username": [], "auth_count": []}

        # Build from counter metrics for passed users
        user_auth_counts = {}
        for key, value in metrics.items():
            if key.startswith("counter_passed_user_"):
                username = key.replace("counter_passed_user_", "")
                if username not in user_auth_counts:
                    user_auth_counts[username] = 0
                user_auth_counts[username] += int(value)

        # Sort by auth count descending
        sorted_users = sorted(user_auth_counts.items(), key=itemgetter(1), reverse=True)
        for username, count in sorted_users:
            configured_users_data["scope"].append("global")
            configured_users_data["username"].append(username)
            configured_users_data["auth_count"].append(count)

        ret["list_authbasic_configured_users"]["data"] = configured_users_data

    except BaseException as e:
        logger.debug(format_exc())
        logger.error(f"Failed to get authbasic metrics: {e}")
        ret["error"] = str(e)

    return ret


def authbasic(**kwargs):
    pass
