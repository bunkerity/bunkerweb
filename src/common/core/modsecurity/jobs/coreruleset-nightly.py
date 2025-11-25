#!/usr/bin/env python3

from io import BytesIO
from os import getenv, sep
from os.path import join
from pathlib import Path
from re import MULTILINE, search
from shutil import rmtree
from subprocess import CalledProcessError, run
from sys import exit as sys_exit, path as sys_path
from tarfile import open as tar_open
from time import sleep
from traceback import format_exc

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from requests import RequestException, get
from requests.exceptions import ConnectionError

from logger import getLogger  # type: ignore
from jobs import Job  # type: ignore

LOGGER = getLogger("MODSECURITY.CORERULESET.NIGHTLY")
status = 0

CRS_NIGHTLY_PATH = Path(sep, "var", "cache", "bunkerweb", "modsecurity", "crs", "nightly")
PATCH_SCRIPT = Path(sep, "usr", "share", "bunkerweb", "core", "modsecurity", "misc", "patch.sh")

try:
    if not PATCH_SCRIPT.is_file():
        LOGGER.error(f"Patch script not found: {PATCH_SCRIPT}")
        sys_exit(1)

    # * Check if we're using the nightly version of the Core Rule Set (CRS)
    use_nightly_crs = False

    if getenv("MULTISITE", "no") == "yes":
        for first_server in getenv("SERVER_NAME", "www.example.com").split(" "):
            if first_server and getenv(f"{first_server}_MODSECURITY_CRS_VERSION", "4") == "nightly":
                use_nightly_crs = True
                break
    elif getenv("MODSECURITY_CRS_VERSION", "4") == "nightly":
        use_nightly_crs = True

    if not use_nightly_crs:
        LOGGER.info("Core Rule Set (CRS) nightly is not being used, skipping download...")
        sys_exit(0)

    JOB = Job(LOGGER, __file__)

    LOGGER.info("Checking if Core Rule Set (CRS) nightly needs to be downloaded...")

    commit_hash = JOB.get_cache("commit_hash")

    max_retries = 3
    retry_count = 0
    while retry_count < max_retries:
        try:
            resp = get("https://github.com/coreruleset/coreruleset/releases/tag/nightly", timeout=7)
            break
        except ConnectionError as e:
            retry_count += 1
            if retry_count == max_retries:
                raise e
            LOGGER.warning(f"Connection refused, retrying in 3 seconds... ({retry_count}/{max_retries})")
            sleep(3)
    resp.raise_for_status()

    content = resp.text

    page_commit_hash = search(r"/coreruleset/coreruleset/commit/(?P<hash>[0-9a-f]{40})", content, MULTILINE)

    if page_commit_hash is None:
        LOGGER.error("Failed to find commit hash on Core Rule Set (CRS) nightly page.")
        sys_exit(2)

    page_commit_hash = page_commit_hash.group("hash")

    LOGGER.debug(f"Page commit hash: {page_commit_hash}")

    if commit_hash:
        LOGGER.debug(f"Current commit hash: {commit_hash.decode()}")

        if commit_hash.decode() == page_commit_hash:
            LOGGER.info("Core Rule Set (CRS) nightly is up to date.")
            sys_exit(0)

        LOGGER.info("Core Rule Set (CRS) nightly is outdated.")

    cached, err = JOB.cache_file("commit_hash", page_commit_hash.encode())
    if not cached:
        LOGGER.error(f"Failed to cache the Core Rule Set (CRS) nightly commit hash: {err}")
        status = 2

    LOGGER.info("Downloading Core Rule Set (CRS) nightly tarball...")

    file_content = BytesIO()
    try:
        max_retries = 3
        retry_count = 0
        while retry_count < max_retries:
            try:
                with get("https://github.com/coreruleset/coreruleset/archive/refs/tags/nightly.tar.gz", stream=True, timeout=5) as resp:
                    resp.raise_for_status()
                    for chunk in resp.iter_content(chunk_size=4 * 1024):
                        if chunk:
                            file_content.write(chunk)
                break
            except ConnectionError as e:
                retry_count += 1
                if retry_count == max_retries:
                    raise e
                LOGGER.warning(f"Connection refused, retrying in 3 seconds... ({retry_count}/{max_retries})")
                sleep(3)
    except RequestException as e:
        LOGGER.debug(format_exc())
        LOGGER.error(f"Failed to download Core Rule Set (CRS) nightly tarball: \n{e}")
        sys_exit(2)

    file_content.seek(0)

    rmtree(CRS_NIGHTLY_PATH, ignore_errors=True)
    CRS_NIGHTLY_PATH.mkdir(parents=True, exist_ok=True)

    LOGGER.info("Extracting Core Rule Set (CRS) nightly tarball...")

    with tar_open(fileobj=file_content, mode="r:gz") as tar_file:
        try:
            tar_file.extractall(CRS_NIGHTLY_PATH, filter="data")
        except TypeError:
            tar_file.extractall(CRS_NIGHTLY_PATH)

    # * Rename the extracted folder to "crs-nightly"
    extracted_folder = next(CRS_NIGHTLY_PATH.iterdir())
    extracted_folder.rename(CRS_NIGHTLY_PATH.joinpath("crs-nightly"))

    # * Move and rename the example configuration file to "crs-setup-nightly.conf"
    example_conf = CRS_NIGHTLY_PATH.joinpath("crs-nightly", "crs-setup.conf.example")
    example_conf.rename(CRS_NIGHTLY_PATH.joinpath("crs-setup-nightly.conf"))

    # * Patch the rules so we can extract the rule IDs when matching
    try:
        LOGGER.info("Patching Core Rule Set (CRS) nightly rules...")
        result = run(
            [PATCH_SCRIPT.as_posix(), CRS_NIGHTLY_PATH.as_posix()],
            check=True,
            env={"PATH": getenv("PATH", ""), "PYTHONPATH": getenv("PYTHONPATH", "")},
        )
    except CalledProcessError as e:
        LOGGER.debug(format_exc())
        LOGGER.error(f"Failed to patch Core Rule Set (CRS) nightly rules: \n{e}")
        sys_exit(1)

    LOGGER.info("Successfully patched Core Rule Set (CRS) nightly rules.")

    cached, err = JOB.cache_dir(CRS_NIGHTLY_PATH)
    if not cached:
        LOGGER.error(f"Error while saving Core Rule Set (CRS) nightly data to db cache: {err}")
    else:
        LOGGER.info("Successfully saved Core Rule Set (CRS) nightly data to db cache.")

    if status == 0:
        status = 1
except SystemExit as e:
    status = e.code
except BaseException as e:
    status = 2
    LOGGER.debug(format_exc())
    LOGGER.error(f"Exception while running coreruleset-nightly.py :\n{e}")

sys_exit(status)
