from operator import itemgetter
from traceback import format_exc

def pre_render(**kwargs):
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
        return {"top_limit": format_data}
    except BaseException:
        print(format_exc(), flush=True)        
        return {"top_limit": [], "error": format_exc()}


def limit(**kwargs):
    pass
