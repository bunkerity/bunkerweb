#!/usr/bin/env python3

"""Materialize the certificate attached to each service so NGINX can serve it.

The inventory is the source of truth; this job is the only thing that turns an attachment
into files on an instance. It writes ``cert.pem``/``key.pem`` under this plugin's cache
directory, which the ordinary Jobs_cache -> push-configs -> instance ``/cache`` path ships
untouched, and ``certificates.lua`` reads at init. Exiting with 1 tells the worker material
changed, which triggers exactly that push and a reload.
"""

from os import sep
from os.path import join
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from logger import getLogger  # type: ignore
from jobs import Job  # type: ignore

LOGGER = getLogger("CERTIFICATES")
JOB = Job(LOGGER, __file__)

status = 0


def renew_due_self_signed() -> None:
    """Renew self-signed inventory certificates whose renewal date has passed.

    Best-effort per certificate: ``renew_self_signed_certificate`` already records its own
    failure on the row, so one bad certificate must not stop the others from renewing or
    stop the deployment below from running.
    """
    for resource_id in JOB.db.get_self_signed_certificates_due_for_renewal():
        error = JOB.db.renew_self_signed_certificate(resource_id)
        if error:
            LOGGER.error(f"Could not renew self-signed certificate {resource_id} : {error}")
        else:
            LOGGER.info(f"Renewed self-signed certificate {resource_id}")


def deployed_services() -> set:
    """Services that currently have deployed material on disk."""
    if not JOB.job_path.is_dir():
        return set()
    return {directory.name for directory in JOB.job_path.iterdir() if directory.is_dir()}


try:
    renew_due_self_signed()

    deployable = JOB.db.get_deployable_certificates()
    changed = False

    for service_id, certificate in deployable.items():
        # The fingerprint is the identity of the material: comparing it to what is already
        # on disk keeps an unchanged certificate from re-triggering a push and a reload on
        # every run of this job.
        previous = JOB.get_cache("fingerprint", service_id=service_id)
        if previous is not None and previous.decode(errors="replace").strip() == certificate["fingerprint"]:
            LOGGER.info(f"Certificate {certificate['name']} already deployed for service {service_id}")
            continue

        failed = False
        for name, content in (
            ("cert.pem", certificate["certificate_pem"]),
            ("key.pem", certificate["private_key_pem"]),
            ("fingerprint", certificate["fingerprint"].encode()),
        ):
            cached, err = JOB.cache_file(name, content, service_id=service_id)
            if not cached:
                LOGGER.error(f"Error while caching {name} for service {service_id} : {err}")
                failed = True
                break

        if failed:
            status = 2
            continue

        LOGGER.info(f"Deployed certificate {certificate['name']} ({certificate['source']}) for service {service_id}")
        changed = True

    # A detached, deleted or revoked certificate must stop being served: dropping its files
    # lets the settings-driven providers take the service back over on the next reload.
    for service_id in deployed_services() - set(deployable):
        LOGGER.info(f"No certificate attached to service {service_id} anymore, removing its deployed material")
        for name in ("cert.pem", "key.pem", "fingerprint"):
            deleted, err = JOB.del_cache(name, service_id=service_id)
            if not deleted:
                LOGGER.error(f"Error while removing {name} for service {service_id} : {err}")
        changed = True

    if changed and status == 0:
        status = 1
    elif not deployable and not changed:
        LOGGER.info("No certificate attached to any service, nothing to deploy")
except SystemExit as e:
    status = e.code
except BaseException as e:
    status = 2
    LOGGER.debug(format_exc())
    LOGGER.error(f"Exception while running deploy-certificates.py :\n{e}")

sys_exit(status)
