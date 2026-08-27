from os import getenv
from typing import Any, Optional

celery_app: Optional[Any] = None


def get_celery_app() -> Optional[Any]:
    """Build the Celery producer, or return None when there is nothing to build it from.

    Celery is imported lazily and its absence is not fatal: it is not in the API's own
    requirements — it is installed into the Docker image from the worker's — and on
    FreeBSD it is not installed at all, where a module-level import made the whole API
    unimportable, so the API package could not start and the scheduler then blocked
    forever on "API not ready".
    """
    global celery_app

    if celery_app is not None:
        return celery_app

    broker_url = getenv("CELERY_BROKER_URL", "").strip()
    if not broker_url:
        return None

    try:
        from celery import Celery
    except ImportError:
        return None

    celery_app = Celery("bunkerweb")
    celery_app.conf.update(
        broker_url=broker_url,
        broker_transport_options={
            # Keep an API request worker out of the kernel's long SYN retry path when a
            # stale broker endpoint black-holes connections rather than refusing them.
            "socket_timeout": 5,
            "socket_connect_timeout": 5,
        },
        result_backend=None,
        task_serializer="json",
        result_serializer="json",
        event_serializer="json",
        accept_content=["json"],
        result_accept_content=["json"],
    )
    return celery_app
