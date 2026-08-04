"""The shipped stacks in ``misc/integrations/`` must be able to come up as written.

These files are what the documentation tells people to copy, so a component missing from one, or
a placeholder its own image refuses, is not a cosmetic problem -- it is the product not starting.
Two ways that has happened, both of them silent until something is actually booted:

* a stack with no worker and no broker. Since 1.7 the scheduler only *dispatches*; without those
  two it boots clean, reports healthy and runs zero background jobs -- no certificate renewal, no
  blocklist or GeoIP refresh -- and says nothing.
* a placeholder credential the API and UI reject at startup with ``exit(1)``, which leaves the
  scheduler waiting on an API that is never coming.
"""

import re
from pathlib import Path

import pytest

from password_utils import USER_PASSWORD_RX

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

# API_PASSWORD / ADMIN_PASSWORD as compose mapping (`KEY: "v"`) and as a Kubernetes env entry
# (`- name: KEY` / `value: "v"`). Only these two are checked against USER_PASSWORD_RX -- the
# database passwords beside them answer to their own engine, not to this rule.
CREDENTIALS = (
    re.compile(r'(API_PASSWORD|ADMIN_PASSWORD):\s*"([^"]*)"'),
    re.compile(r'name:\s*(API_PASSWORD|ADMIN_PASSWORD)\s*\n\s*value:\s*"([^"]*)"'),
)

# The mapping's value, never the bare word: docker.yml also names DATABASE_URI in a comment, and
# a substring match on that quietly turned the check below into a no-op.
DATABASE_URI_VALUE = re.compile(r'^\s*DATABASE_URI:\s*"([^"]*)"', re.MULTILINE)


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


@pytest.mark.parametrize("manifest", MANIFESTS, ids=lambda path: path.name)
def test_the_placeholder_credentials_are_ones_the_images_accept(manifest):
    """gunicorn.conf.py exit(1)s on a password that fails USER_PASSWORD_RX, in both the API and
    the UI. Ship one in a manifest and the container dies on boot -- and the scheduler then waits
    forever on an API that is never coming. Every stack here shipped "changeme"."""
    text = manifest.read_text(encoding="utf-8")
    found = [pair for pattern in CREDENTIALS for pair in pattern.findall(text)]

    rejected = [f"{key}={value!r}" for key, value in found if not USER_PASSWORD_RX.match(value)]
    assert not rejected, f"{manifest.name} ships credentials its own image refuses: {', '.join(rejected)}"


def test_the_placeholder_credential_is_one_value_everywhere():
    """Someone copying two of these files must not end up with two different passwords."""
    values = {value for path in MANIFESTS for pattern in CREDENTIALS for _, value in pattern.findall(path.read_text(encoding="utf-8"))}

    assert len(values) == 1, f"shipped manifests disagree on the placeholder credential: {sorted(values)}"


@pytest.mark.parametrize("manifest", [path for path in MANIFESTS if not path.name.startswith("k8s.")], ids=lambda path: path.name)
def test_every_service_comes_back_after_it_dies(manifest):
    """Compose does not restart a container unless told to, and the scheduler does exit on
    purpose -- it gives up once its error budget is spent. Without a policy that exit is
    permanent: no config change is applied and no job is dispatched again, silently, until
    somebody notices. install-bunkerweb.sh has always set one; these did not."""
    text = manifest.read_text(encoding="utf-8")
    services = text.count("\n    image:")

    assert (
        services and text.count('\n    restart: "unless-stopped"') == services
    ), f"{manifest.name} leaves some of its {services} services with no restart policy"


@pytest.mark.parametrize("manifest", COMPOSE, ids=lambda path: path.name)
def test_every_stack_states_its_database_rather_than_relying_on_the_default(manifest):
    """The worker is the one component that reads an unset DATABASE_URI as "no database"
    (worker/app.py::init_worker_db) instead of falling back to the SQLite path. Leave it out and
    its jobs record no run and read compiled defaults instead of the stored configuration -- while
    still reporting success."""
    assert DATABASE_URI_VALUE.search(manifest.read_text(encoding="utf-8")), f"{manifest.name} ships a worker but never sets DATABASE_URI"


@pytest.mark.parametrize("manifest", COMPOSE, ids=lambda path: path.name)
def test_a_file_backed_stack_shares_the_volume_holding_that_file(manifest):
    """A sqlite:// DSN means the database is a file inside /data. Give the worker a volume of its
    own there and it silently talks to a *different, empty* one."""
    text = manifest.read_text(encoding="utf-8")
    dsn = DATABASE_URI_VALUE.search(text)
    if not dsn or not dsn.group(1).startswith("sqlite"):
        return
    assert "bw-worker-storage" not in text, f"{manifest.name} is SQLite-backed, so the worker cannot have a /data of its own"
    assert text.count("- bw-storage:/data") == 3, f"{manifest.name} must mount bw-storage:/data in the scheduler, the API and the worker"
