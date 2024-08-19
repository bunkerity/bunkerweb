from traceback import format_exc


def pre_render(**kwargs):
    try:
        data = kwargs["bw_instances_utils"].get_metrics("dnsbl")
        return {
            "counter_failed_dnsbl": {
                "value": data.get("counter_failed_dnsbl", 0),
                "title": "DNSBL",
                "subtitle": "request blocked",
                "subtitle_color": "error",
                "svg_color": "red",
            }
        }
    except BaseException:
        print(format_exc(), flush=True)
        return {
            "counter_failed_dnsbl": {"value": "unknown", "title": "DNSBL", "subtitle": "request blocked", "subtitle_color": "error", "svg_color": "red"},
            "error": format_exc(),
        }


def dnsbl(**kwargs):
    pass
