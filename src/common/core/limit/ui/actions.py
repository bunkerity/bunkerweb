def limit(**kwargs):
    try:
        # Here we will have a list { 'limit_uri_url1': X, 'limit_uri_url2': Y ... }
        data = kwargs["app"].config["INSTANCES"].get_metrics("limit")
        format_data = []
        # Format to fit [{url: "url1", count: X}, {url: "url2", count: Y} ...]
        for key, value in data.items():
            format_data[key] = {"url": key.replace("limit_uri_", ""), "count": value}

        return {"items": format_data}

    except:
        return {"items": []}
