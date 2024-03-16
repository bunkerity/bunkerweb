def pre_render(**kwargs):
    try:
        data = kwargs["app"].config["INSTANCES"].get_metrics("dnsbl")
        return {
            "counter_failed_dnsbl": {
                "value": data.get("counter_failed_dnsbl", 0),
                "title": "DNSBL",
                "subtitle": "request blocked",
                "subtitle_color": "error",
                "svg_color": "red",
            }
        }
    except:
        return {"counter_failed_dnsbl": {"value": "unknown", "title": "DNSBL", "subtitle": "request blocked", "subtitle_color": "error", "svg_color": "red"}}


def dnsbl(**kwargs):
    pass
