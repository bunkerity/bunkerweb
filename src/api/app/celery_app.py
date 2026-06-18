from os import getenv
from typing import Optional

from celery import Celery

celery_app: Optional[Celery] = None


def get_celery_app() -> Optional[Celery]:
    global celery_app

    if celery_app is not None:
        return celery_app

    broker_url = getenv("CELERY_BROKER_URL", "").strip()
    if not broker_url:
        return None

    celery_app = Celery("bunkerweb")
    celery_app.conf.update(
        broker_url=broker_url,
        result_backend=None,
        task_serializer="json",
        result_serializer="json",
        event_serializer="json",
        accept_content=["json"],
        result_accept_content=["json"],
    )
    return celery_app
