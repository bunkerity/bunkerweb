from collections import Counter
from json import loads as json_loads
from logging import getLogger
from operator import itemgetter
from traceback import format_exc
from datetime import datetime


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


def _format_increment_date(raw_value):
    if isinstance(raw_value, (int, float)):
        try:
            return datetime.fromtimestamp(raw_value).isoformat()
        except (OSError, ValueError):
            return datetime.fromtimestamp(0).isoformat()
    try:
        return datetime.fromtimestamp(float(raw_value)).isoformat()
    except (TypeError, ValueError, OSError):
        return str(raw_value or "")


def _flatten_table_increments(raw_increments):
    if raw_increments is None:
        return []
    if isinstance(raw_increments, str):
        try:
            raw_increments = json_loads(raw_increments)
        except ValueError:
            return []
    if isinstance(raw_increments, list):
        return raw_increments
    if isinstance(raw_increments, dict):
        flattened = []
        for value in raw_increments.values():
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
        "top_bad_behavior_status": {
            "col-size": "col-12 col-md-4",
            "data": {},
            "order": {
                "column": 1,
                "dir": "desc",
            },
            "svg_color": "primary",
        },
        "top_bad_behavior_ips": {
            "col-size": "col-12 col-md-4",
            "data": {},
            "order": {
                "column": 2,
                "dir": "desc",
            },
            "svg_color": "primary",
        },
        "top_bad_behavior_urls": {
            "col-size": "col-12 col-md-4",
            "data": {},
            "order": {
                "column": 3,
                "dir": "desc",
            },
            "svg_color": "primary",
        },
        "list_bad_behavior_history": {
            "col-size": "col-12",
            "data": {},
            "order": {
                "column": 4,
                "dir": "desc",
            },
            "svg_color": "warning",
        },
    }
    try:
        metrics = kwargs["bw_instances_utils"].get_metrics("badbehavior")
        args = kwargs.get("args") or {}
        data_payload = kwargs.get("data") or {}
        service_filter = _normalize_service_name(
            args.get("service") or args.get("server_name") or data_payload.get("service") or data_payload.get("server_name")
        )
        apply_service_filter = bool(service_filter)

        filtered_events = []
        list_fields = [
            "date",
            "id",
            "ip",
            "country",
            "server_name",
            "method",
            "url",
            "status",
            "security_mode",
            "ban_scope",
            "ban_time",
            "threshold",
            "count_time",
        ]
        list_data = {field: [] for field in list_fields}
        table_sources = []
        if "table_increments" in metrics:
            table_sources.append(metrics["table_increments"])
        for key, value in metrics.items():
            if key.startswith("table_increments_"):
                table_sources.append(value)

        if table_sources:
            seen_ids = set()
            for source in table_sources:
                for increment in _flatten_table_increments(source):
                    entry_service = _normalize_service_name(increment.get("server_name"))
                    if apply_service_filter and entry_service != service_filter:
                        continue

                    increment_id = increment.get("id")
                    if increment_id and increment_id in seen_ids:
                        continue

                    if increment_id:
                        seen_ids.add(increment_id)

                    filtered_events.append(increment)
                    list_data["date"].append(_format_increment_date(increment.get("date", 0)))
                    list_data["id"].append(increment_id or "")
                    list_data["ip"].append(increment.get("ip", ""))
                    list_data["country"].append(increment.get("country", ""))
                    list_data["server_name"].append(increment.get("server_name", ""))
                    list_data["method"].append(increment.get("method", ""))
                    list_data["url"].append(increment.get("url", ""))
                    list_data["status"].append(increment.get("status", ""))
                    list_data["security_mode"].append(increment.get("security_mode", ""))
                    list_data["ban_scope"].append(increment.get("ban_scope", ""))
                    list_data["ban_time"].append(str(increment.get("ban_time", "")))
                    list_data["threshold"].append(str(increment.get("threshold", "")))
                    list_data["count_time"].append(str(increment.get("count_time", "")))
        ret["list_bad_behavior_history"]["data"] = list_data

        if filtered_events or apply_service_filter:
            ret["top_bad_behavior_status"]["data"] = _build_counter_data(filtered_events, "status", "code")
            ret["top_bad_behavior_ips"]["data"] = _build_counter_data(filtered_events, "ip", "ip")
            ret["top_bad_behavior_urls"]["data"] = _build_counter_data(filtered_events, "url", "url")
        else:
            format_data = [
                {
                    "code": int(key.split("_")[2]),
                    "count": int(value),
                }
                for key, value in metrics.items()
                if key.startswith("counter_status_")
            ]
            format_data.sort(key=itemgetter("count"), reverse=True)
            data = {"code": [], "count": []}
            for item in format_data:
                data["code"].append(item["code"])
                data["count"].append(item["count"])
            ret["top_bad_behavior_status"]["data"] = data

            format_data = [
                {
                    "ip": key.split("_")[2],
                    "count": int(value),
                }
                for key, value in metrics.items()
                if key.startswith("counter_ip_")
            ]
            format_data.sort(key=itemgetter("count"), reverse=True)
            data = {"ip": [], "count": []}
            for item in format_data:
                data["ip"].append(item["ip"])
                data["count"].append(item["count"])
            ret["top_bad_behavior_ips"]["data"] = data

            format_data = [
                {
                    "url": key.split("_", 2)[2],
                    "count": int(value),
                }
                for key, value in metrics.items()
                if key.startswith("counter_url_")
            ]
            format_data.sort(key=itemgetter("count"), reverse=True)
            data = {"url": [], "count": []}
            for item in format_data:
                data["url"].append(item["url"])
                data["count"].append(item["count"])
            ret["top_bad_behavior_urls"]["data"] = data

    except BaseException as e:
        logger.debug(format_exc())
        logger.error(f"Failed to get badbehavior metrics: {e}")
        ret["error"] = str(e)

    return ret


def badbehavior(**kwargs):
    pass
