#!/usr/bin/python3

import sys
sys.path.append("/opt/bunkerweb/deps/python")
sys.path.append("/opt/bunkerweb/utils")

from requests import get
from zipfile import ZipFile
from io import BytesIO
from os import getenv, makedirs, chmod, stat
from os.path import isfile, dirname
from stat import S_IEXEC
from uuid import uuid4
from glob import glob
from json import loads
from shutil import copytree, rmtree
from traceback import format_exc

from logger import log

status = 0

def install_plugin(plugin_dir) :
    # Load plugin.json
    metadata = {}
    with open(plugin_dir + "plugin.json", "r") as f :
        metadata = loads(f.read())
    # Don't go further if plugin is already installed
    if isfile("/data/plugins/" + metadata["id"] + "/plugin.json") :
        log("JOBS", "ℹ️", "Skipping installation of plugin " + metadata["id"] + " (already installed)")
        return
    # Copy the plugin
    copytree(plugin_dir, "/data/plugins/" + metadata["id"])
    # Add u+x permissions to jobs files
    for job_file in glob(plugin_dir + "jobs/*") :
        st = stat(job_file)
        chmod(job_file, st.st_mode | S_IEXEC)

try :

    # Check if we have plugins to download
    plugin_urls = getenv("EXTERNAL_PLUGIN_URLS", "")
    if plugin_urls == "" :
        log("JOBS", "ℹ️", "No external plugins to download")

    # Loop on URLs
    for plugin_url in plugin_urls.split(" ") :

        # Download ZIP file
        try :
            req = get(plugin_url)
        except :
            log("JOBS", "❌", "Exception while downloading plugin(s) from " + plugin_url + " :")
            print(format_exc())
            status = 2
            continue

        # Extract it to tmp folder
        temp_dir = "/opt/bunkerweb/tmp/plugins-" + str(uuid4()) + "/"
        try :
            makedirs(temp_dir, exist_ok=True)
            with ZipFile(BytesIO(req.content)) as zf :
                zf.extractall(path=temp_dir)
        except :
            log("JOBS", "❌", "Exception while decompressing plugin(s) from " + plugin_url + " :")
            print(format_exc())
            status = 2
            continue

        # Install plugins
        try :
            for plugin_dir in glob(temp_dir + "**/plugin.json", recursive=True) :
                install_plugin(dirname(plugin_dir) + "/")
        except :
            log("JOBS", "❌", "Exception while installing plugin(s) from " + plugin_url + " :")
            print(format_exc())
            status = 2
            continue

except :
    status = 2
    log("JOBS", "❌", "Exception while running download-plugins.py :")
    print(format_exc())

for plugin_tmp in glob("/opt/bunkerweb/tmp/plugins-*/") :
    rmtree(plugin_tmp)

sys.exit(status)
