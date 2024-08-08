from traceback import format_exc


def pre_render(**kwargs):
    try:
        data = kwargs["app"].bw_instances_utils.get_metrics("whitelist")
        return {
            "counter_passed_whitelist": {
                "value": data.get("counter_passed_whitelist", 0),
                "title": "WHITELIST",
                "subtitle": "request passed",
                "subtitle_color": "success",
                "svg_color": "green",
            }
        }

    except BaseException:
        print(format_exc(), flush=True)
        return {
            "counter_passed_whitelist": {
                "value": "unknown",
                "title": "WHITELIST",
                "subtitle": "request passed",
                "subtitle_color": "success",
                "svg_color": "green",
            },
            "error": format_exc(),
        }


def whitelist(**kwargs):
    pass
