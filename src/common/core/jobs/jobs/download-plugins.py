#!/usr/bin/python3

from io import BytesIO
from os import getenv, listdir, makedirs, chmod, stat, _exit
from os.path import isfile, dirname
from stat import S_IEXEC
from sys import exit as sys_exit, path as sys_path
from uuid import uuid4
from glob import glob
from json import load, loads
from shutil import copytree, rmtree
from traceback import format_exc
from zipfile import ZipFile

sys_path.extend(
    (
        "/usr/share/bunkerweb/deps/python",
        "/usr/share/bunkerweb/utils",
        "/usr/share/bunkerweb/db",
    )
)

from requests import get

from Database import Database
from logger import setup_logger


logger = setup_logger("Jobs", getenv("LOG_LEVEL", "INFO"))
db = Database(
    logger,
    sqlalchemy_string=getenv("DATABASE_URI", None),
)
status = 0


def install_plugin(plugin_dir):
    # Load plugin.json
    with open(f"{plugin_dir}plugin.json", "rb") as f:
        metadata = loads(f.read())
    # Don't go further if plugin is already installed
    if isfile(f"/data/plugins/{metadata['id']}/plugin.json"):
        logger.info(
            f"Skipping installation of plugin {metadata['id']} (already installed)",
        )
        return
    # Copy the plugin
    copytree(plugin_dir, f"/data/plugins/{metadata['id']}")
    # Add u+x permissions to jobs files
    for job_file in glob(f"{plugin_dir}jobs/*"):
        st = stat(job_file)
        chmod(job_file, st.st_mode | S_IEXEC)


try:

    # Check if we have plugins to download
    plugin_urls = getenv("EXTERNAL_PLUGIN_URLS", "")
    if not plugin_urls:
        logger.info("No external plugins to download")
        _exit(0)

    # Loop on URLs
    for plugin_url in plugin_urls.split(" "):
        # Download ZIP file
        try:
            req = get(plugin_url)
        except:
            logger.error(
                f"Exception while downloading plugin(s) from {plugin_url} :\n{format_exc()}",
            )
            status = 2
            continue

        # Extract it to tmp folder
        temp_dir = f"/var/tmp/bunkerweb/plugins-{uuid4()}/"
        try:
            makedirs(temp_dir, exist_ok=True)
            with ZipFile(BytesIO(req.content)) as zf:
                zf.extractall(path=temp_dir)
        except:
            logger.error(
                f"Exception while decompressing plugin(s) from {plugin_url} :\n{format_exc()}",
            )
            status = 2
            continue

        # Install plugins
        try:
            for plugin_dir in glob(f"{temp_dir}**/plugin.json", recursive=True):
                install_plugin(f"{dirname(plugin_dir)}/")
        except:
            logger.error(
                f"Exception while installing plugin(s) from {plugin_url} :\n{format_exc()}",
            )
            status = 2
            continue

    external_plugins = []
    for plugin in listdir("/etc/bunkerweb/plugins"):
        with open(
            f"/etc/bunkerweb/plugins/{plugin}/plugin.json",
            "r",
        ) as f:
            plugin_file = load(f)

        external_plugins.append(plugin_file)

    if external_plugins:
        err = db.update_external_plugins(external_plugins)
        if err:
            logger.error(
                f"Couldn't update external plugins to database: {err}",
            )

except:
    status = 2
    logger.error(f"Exception while running download-plugins.py :\n{format_exc()}")

for plugin_tmp in glob("/var/tmp/bunkerweb/plugins-*/"):
    rmtree(plugin_tmp)

sys_exit(status)
