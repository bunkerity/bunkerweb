from operator import itemgetter


def limit(**kwargs):
    try:
        # Here we will have a list { 'limit_uri_url1': X, 'limit_uri_url2': Y ... }
        data = kwargs["app"].config["INSTANCES"].get_metrics("limit")
        format_data = []
        # Format to fit [{url: "url1", count: X}, {url: "url2", count: Y} ...]
        for key, value in data.items():
            key = key.split("/", 1)
            if len(key) > 1:
                key = key[1]
            else:
                key = ""
            format_data.append({"url": f"/{key}", "count": int(value)})
        format_data.sort(key=itemgetter("count"), reverse=True)
        return {"items": format_data}
    except:
        return {"items": []}
