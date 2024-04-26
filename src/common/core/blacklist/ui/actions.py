from traceback import format_exc


def pre_render(**kwargs):
    metrics = {
        "counter_blacklist_url": {"value": "unknown", "title": "URL", "subtitle": "denied", "subtitle_color": "error", "svg_color": "red"},
        "counter_blacklist_ip": {"value": "unknown", "title": "IP", "subtitle": "denied", "subtitle_color": "error", "svg_color": "orange"},
        "counter_blacklist_rdns": {"value": "unknown", "title": "RDNS", "subtitle": "denied", "subtitle_color": "error", "svg_color": "amber"},
        "counter_blacklist_asn": {"value": "unknown", "title": "ASN", "subtitle": "denied", "subtitle_color": "error", "svg_color": "emerald"},
        "counter_blacklist_ua": {"value": "unknown", "title": "UA", "subtitle": "denied", "subtitle_color": "error", "svg_color": "pink"},
    }

    try:
        data = kwargs["app"].config["INSTANCES"].get_metrics("blacklist")
        for key in metrics:
            metrics[key]["value"] = data.get(key, 0)
        return metrics
    except BaseException:
        print(format_exc(), flush=True)
        metrics["error"] = format_exc()
        return metrics


def blacklist(**kwargs):
    pass
