"""Every shipped stack that deploys a scheduler must also deploy the worker and its broker.

Since 1.7 the scheduler only *dispatches* jobs; they run in a Celery worker behind a broker. A
manifest that ships a scheduler without those two boots clean, reports healthy, and runs zero
background jobs -- no certificate renewal, no blocklist or GeoIP refresh -- while saying nothing
about it. That is exactly how ``misc/integrations/docker.yml``, the SQLite quickstart and the
first stack most people copy, shipped jobless.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
MANIFESTS = sorted((ROOT / "misc" / "integrations").glob("*.yml"))

# Stacks built on the all-in-one image run the worker and broker inside the single container
# (supervisor.d/worker.ini + an embedded Redis), so they carry no scheduler image and are not
# expected to declare either as a service.
CONTROL_PLANE = [path for path in MANIFESTS if "bunkerweb-scheduler" in path.read_text(encoding="utf-8")]

# The Kubernetes manifests answer the same questions in a different vocabulary -- env as
# `- name: DATABASE_URI`, storage as PersistentVolumeClaims -- so only the "which components are
# deployed" check below is meaningful for them; the compose-volume one is not.
COMPOSE = [path for path in CONTROL_PLANE if not path.name.startswith("k8s.")]

DOCKERFILE_UID = re.compile(r"useradd -u (\d+) -g \w+ ")

# The mapping key, never the word: docker.yml mentions DATABASE_URI in a comment telling the
# reader to set one, and a substring match there quietly turned the check below into a no-op.
DATABASE_URI_KEY = re.compile(r"^\s*DATABASE_URI:", re.MULTILINE)


def _uid(component):
    dockerfile = (ROOT / "src" / component / "Dockerfile").read_text(encoding="utf-8")
    match = DOCKERFILE_UID.search(dockerfile)
    assert match, f"src/{component}/Dockerfile no longer creates its runtime user with useradd -u"
    return int(match.group(1))


def test_there_are_manifests_to_check():
    """A glob that silently matches nothing would make every assertion below vacuously true."""
    assert len(CONTROL_PLANE) >= 20


@pytest.mark.parametrize("manifest", CONTROL_PLANE, ids=lambda path: path.name)
def test_a_stack_with_a_scheduler_can_actually_run_jobs(manifest):
    text = manifest.read_text(encoding="utf-8")

    missing = [
        piece
        for piece, marker in (
            ("the API", "bunkerweb-api"),
            ("a worker", "bunkerweb-worker"),
            ("a broker (CELERY_BROKER_URL)", "CELERY_BROKER_URL"),
        )
        if marker not in text
    ]
    assert not missing, f"{manifest.name} ships a scheduler but no {', '.join(missing)}"


@pytest.mark.parametrize("component", ["api", "worker"])
def test_the_control_plane_images_share_one_uid(component):
    """A SQLite stack hands the scheduler, the API and the worker the same /data volume, because
    the database is a file inside it. That only works while the three images run as the same user
    -- the ids the shared helpers/data.sh preflight names in every error it prints."""
    assert _uid(component) == _uid("scheduler") == 101


@pytest.mark.parametrize("manifest", COMPOSE, ids=lambda path: path.name)
def test_a_file_backed_stack_shares_the_volume_holding_that_file(manifest):
    """No DATABASE_URI means every component falls back to SQLite under /data. Give the worker a
    volume of its own there and it silently talks to a *different, empty* database."""
    text = manifest.read_text(encoding="utf-8")
    if DATABASE_URI_KEY.search(text):
        return
    assert "bw-worker-storage" not in text, f"{manifest.name} has no DATABASE_URI, so the worker cannot have its own /data"
    assert text.count("- bw-storage:/data") == 3, f"{manifest.name} must mount bw-storage:/data in the scheduler, the API and the worker"
