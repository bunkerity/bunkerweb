from typing import Any, Dict
from uvicorn.workers import UvicornWorker


class ApiUvicornWorker(UvicornWorker):
    CONFIG_KWARGS: Dict[str, Any] = {
        "loop": "auto",
        "http": "auto",
        "proxy_headers": True,
        "server_header": False,
        "date_header": False,
    }
