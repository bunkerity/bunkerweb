#!/usr/bin/env python3
"""Install service templates from ``EXTERNAL_TEMPLATE_URLS``, the template twin of ``EXTERNAL_PLUGIN_URLS``.

Each URL is one template: a ``bunkerweb-template/1`` package (one JSON file) or a ``.zip`` /
``.tar.gz`` holding ``<id>/template.json`` and ``<id>/configs/...`` (the ``bunkerweb-templates``
repository layout). ``https://`` and ``file:///`` only, at most 1 MiB, and checked against an optional
``#sha256=<hex>`` pin (``url_download``). Templates are parsed by ``template_package``, the parser the
UI and API imports use, and written with ``create_template`` / ``update_template``, which refuse a
template whole on the first unknown setting or bad value.

Ownership: what this job installs is ``method="scheduler"`` with no plugin, which is how it recognises
its own templates -- nothing else writes that combination (plugin-owned templates carry their
``plugin_id``). It never changes or deletes a template the web UI, the API or a plugin owns. A
template whose URL left the setting is deleted, unless a service or the global settings still use it
(kept with a warning, and retried on the next run). A run in which any URL failed deletes nothing:
the job cannot tell which templates that URL would still have delivered.

Exit code: 0 or 2, never 1. Exit 1 ships the job cache to the instances and reloads them, but a
template is database state that only a configuration generation renders. ``update_template`` and
``delete_template`` raise every plugin's ``config_changed`` flag, and a creation raises the
``templates`` plugin's, which is what makes the scheduler dispatch push-configs. Those flags also
re-dispatch the once-jobs of the flagged plugins, this one included, so an unchanged URL must write
nothing: the digest of each installed package is kept in the job cache and compared first.
"""

from hashlib import sha256
from json import JSONDecodeError, dumps, loads
from os import getenv, sep
from os.path import join
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from Database import Database  # type: ignore
from jobs import Job  # type: ignore
from logger import getLogger  # type: ignore
from template_package import PACKAGE_MAX, parse_package, template_from_archive  # type: ignore
from url_download import DownloadError, download  # type: ignore

LOGGER = getLogger("DOWNLOAD-TEMPLATES")
STATE_FILE = "installed.json"
IN_USE_MARKER = "currently used"


def _load_state(job) -> dict:
    """``{template_id: digest of the package installed}`` from the previous run."""
    raw = job.get_cache(STATE_FILE)
    try:
        state = loads(raw) if raw else {}
    except (JSONDecodeError, UnicodeDecodeError, TypeError):
        state = {}
    return state if isinstance(state, dict) else {}


def _fetch_template(url: str):
    """``(template, error)``: the ``create_template`` fields plus ``id``, or why the URL was refused."""
    try:
        blob = download(url, max_bytes=PACKAGE_MAX)
    except DownloadError as e:
        return None, str(e)
    return parse_package(blob) if blob.lstrip()[:1] == b"{" else template_from_archive(blob)


def _is_ours(template: dict) -> bool:
    return not template["plugin_id"] and template["method"] == "scheduler"


def main() -> int:
    urls = getenv("EXTERNAL_TEMPLATE_URLS", "").split()
    db = Database(LOGGER, sqlalchemy_string=getenv("DATABASE_URI"))
    job = Job(LOGGER, __file__, db)
    previous = _load_state(job)
    installed = db.get_templates()
    delivered = {}
    status = 0
    created = False

    for url in urls:
        template, error = _fetch_template(url)
        if error or not template:
            LOGGER.error(f"Skipping template URL {url}: {error or 'no template found'}")
            status = 2
            continue

        template_id = template.pop("id")
        digest = sha256(dumps(template, sort_keys=True).encode("utf-8")).hexdigest()
        current = installed.get(template_id)

        if template_id in delivered:
            LOGGER.error(f"Skipping template URL {url}: template {template_id} was already installed from another URL of the list")
            status = 2
            continue
        if current and not _is_ours(current):
            owner = f"plugin {current['plugin_id']}" if current["plugin_id"] else current["method"]
            LOGGER.error(f"Skipping template URL {url}: template {template_id} already exists and is managed by {owner}")
            status = 2
            continue

        if current and previous.get(template_id) == digest:
            delivered[template_id] = digest
            continue

        if current:
            error = db.update_template(template_id, method="scheduler", **template)
        else:
            error = db.create_template(template_id, method="scheduler", **template)
        if error:
            LOGGER.error(f"Could not install template {template_id} from {url}: {error}")
            status = 2
            continue

        delivered[template_id] = digest
        created = created or not current
        LOGGER.info(f"✅ Template {template_id} {'updated' if current else 'installed'} from {url}")

    state = previous | delivered
    if status == 0:
        state = delivered.copy()
        for template_id, template in installed.items():
            if template_id in delivered or not _is_ours(template):
                continue
            error = db.delete_template(template_id)
            if not error:
                LOGGER.info(f"Template {template_id} removed, its URL is no longer in EXTERNAL_TEMPLATE_URLS")
            elif IN_USE_MARKER in error:
                LOGGER.warning(f"Template {template_id} is no longer in EXTERNAL_TEMPLATE_URLS but is kept: {error}. It will be removed once unused.")
                state[template_id] = previous.get(template_id, "")
            else:
                LOGGER.error(f"Could not remove template {template_id}: {error}")
                state[template_id] = previous.get(template_id, "")
                status = 2
    elif any(_is_ours(template) and template_id not in delivered for template_id, template in installed.items()):
        LOGGER.warning("A template URL failed, so no template is removed during this run")

    if created:
        # A service may already name the new id in USE_TEMPLATE; a generation is what applies it.
        if error := db.checked_changes(["config"], plugins_changes=["templates"], value=True):
            LOGGER.error(f"Could not flag the configuration for regeneration: {error}")
            status = 2

    if state != previous:
        ok, error = job.cache_file(STATE_FILE, dumps(state, sort_keys=True).encode("utf-8"))
        if not ok:
            LOGGER.error(f"Could not save the installed templates state: {error}")
            status = 2

    if not urls and not previous:
        LOGGER.info("No external templates to download")
    return status


try:
    status = main()
except BaseException as e:
    status = 2
    LOGGER.debug(format_exc())
    LOGGER.error(f"Exception while running download-templates.py :\n{e}")

sys_exit(status)
