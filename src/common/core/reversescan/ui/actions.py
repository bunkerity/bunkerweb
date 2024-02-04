def reversescan(**kwargs):
    try:
        # Here we will have a list { 'counter_403': X, 'counter_401': Y ... }
        data = kwargs["app"].config["INSTANCES"].get_metrics("reversescan")
        format_data = []
        # Format to fit [{code: 403, count: X}, {code: 401, count: Y} ...]
        for key, value in data.items():
            format_data[key] = {"port": int(key.split("_")[1]), "count": value}

        return {"items": format_data}

    except:
        return {"items": []}
