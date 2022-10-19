#!/usr/bin/python3

from io import BytesIO
from os import getenv, makedirs, chmod, stat, _exit
from os.path import isfile, dirname
from stat import S_IEXEC
from sys import exit as sys_exit, path as sys_path
from uuid import uuid4
from glob import glob
from json import loads
from shutil import copytree, rmtree
from traceback import format_exc
from zipfile import ZipFile

sys_path.append("/opt/bunkerweb/deps/python")
sys_path.append("/opt/bunkerweb/utils")

from requests import get
from logger import setup_logger


logger = setup_logger("Jobs", getenv("LOG_LEVEL", "INFO"))
status = 0


def install_plugin(plugin_dir):
    # Load plugin.json
    metadata = {}
    with open(f"{plugin_dir}plugin.json", "r") as f:
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
    if plugin_urls == "":
        logger.info("No external plugins to download")
        _exit(0)

    # Loop on URLs
    for plugin_url in plugin_urls.split(" "):

        # Download ZIP file
        try:
            req = get(plugin_url)
        except:
            logger.error(
                f"Exception while downloading plugin(s) from {plugin_url} :",
            )
            print(format_exc())
            status = 2
            continue

        # Extract it to tmp folder
        temp_dir = "/opt/bunkerweb/tmp/plugins-" + str(uuid4()) + "/"
        try:
            makedirs(temp_dir, exist_ok=True)
            with ZipFile(BytesIO(req.content)) as zf:
                zf.extractall(path=temp_dir)
        except:
            logger.error(
                f"Exception while decompressing plugin(s) from {plugin_url} :",
            )
            print(format_exc())
            status = 2
            continue

        # Install plugins
        try:
            for plugin_dir in glob(temp_dir + "**/plugin.json", recursive=True):
                install_plugin(dirname(plugin_dir) + "/")
        except:
            logger.error(
                f"Exception while installing plugin(s) from {plugin_url} :",
            )
            print(format_exc())
            status = 2
            continue

except:
    status = 2
    logger.error(f"Exception while running download-plugins.py :\n{format_exc()}")

for plugin_tmp in glob("/opt/bunkerweb/tmp/plugins-*/"):
    rmtree(plugin_tmp)

sys_exit(status)
