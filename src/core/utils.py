from glob import glob
from hashlib import sha512
from io import BufferedReader, BytesIO
from json import loads
from logging import Logger
from os import chmod
from os.path import basename, dirname, join, normpath, sep
from pathlib import Path
from shutil import copytree, rmtree
from stat import S_IEXEC
from tarfile import open as tar_open
from threading import Semaphore
from traceback import format_exc
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4
from zipfile import ZipFile

from magic import Magic
from requests import get


def dict_to_frozenset(d):
    if isinstance(d, dict):
        return frozenset((k, dict_to_frozenset(v)) for k, v in d.items())
    return d


def bytes_hash(bio: BufferedReader) -> str:
    _sha512 = sha512()
    while True:
        data = bio.read(1024)
        if not data:
            break
        _sha512.update(data)
    bio.seek(0)
    return _sha512.hexdigest()


def install_plugin(
    plugin_url: str, logger: Logger, *, semaphore: Optional[Semaphore] = None
):
    if semaphore:
        semaphore.acquire(timeout=30)

    # Download Plugin file
    try:
        if plugin_url.startswith("file://"):
            content = Path(normpath(plugin_url[7:])).read_bytes()
        else:
            content = b""
            resp = get(plugin_url, stream=True, timeout=10)

            if resp.status_code != 200:
                logger.warning(f"Got status code {resp.status_code}, skipping...")
                return

            # Iterate over the response content in chunks
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    content += chunk
    except:
        logger.error(
            f"Exception while downloading plugin(s) from {plugin_url} :\n{format_exc()}",
        )
        return

    # Extract it to tmp folder
    temp_dir = join(sep, "var", "tmp", "bunkerweb", "plugins", str(uuid4()))
    try:
        Path(temp_dir).mkdir(parents=True, exist_ok=True)
        file_type = Magic(mime=True).from_buffer(content)

        if file_type == "application/zip":
            with ZipFile(BytesIO(content)) as zf:
                zf.extractall(path=temp_dir)
        elif file_type == "application/gzip":
            with tar_open(fileobj=BytesIO(content), mode="r:gz") as tar:
                tar.extractall(path=temp_dir)
        elif file_type == "application/x-tar":
            with tar_open(fileobj=BytesIO(content), mode="r") as tar:
                tar.extractall(path=temp_dir)
        else:
            logger.error(
                f"Unknown file type for {plugin_url}, either zip or tar are supported, skipping..."
            )
            return
    except:
        logger.error(
            f"Exception while decompressing plugin(s) from {plugin_url} :\n{format_exc()}",
        )
        return

    # Install plugins
    try:
        for plugin_dir in glob(join(temp_dir, "**", "plugin.json"), recursive=True):
            try:
                plugin_dir = dirname(plugin_dir)
                # Load plugin.json
                metadata = loads(
                    Path(plugin_dir, "plugin.json").read_text(encoding="utf-8")
                )
                # Don't go further if plugin is already installed
                if Path(
                    "etc", "bunkerweb", "plugins", metadata["id"], "plugin.json"
                ).is_file():
                    logger.warning(
                        f"Skipping installation of plugin {metadata['id']} (already installed)",
                    )
                    return
                # Copy the plugin
                copytree(
                    plugin_dir, join(sep, "etc", "bunkerweb", "plugins", metadata["id"])
                )
                # Add u+x permissions to jobs files
                for job_file in glob(join(plugin_dir, "jobs", "*")):
                    st = Path(job_file).stat()
                    chmod(job_file, st.st_mode | S_IEXEC)
                logger.info(f"Plugin {metadata['id']} installed")
            except FileExistsError:
                logger.warning(
                    f"Skipping installation of plugin {basename(dirname(plugin_dir))} (already installed)",
                )
    except:
        logger.error(
            f"Exception while installing plugin(s) from {plugin_url} :\n{format_exc()}",
        )

    if semaphore:
        semaphore.release()


def generate_external_plugins(
    plugins: List[Dict[str, Any]],
    logger: Logger,
    *,
    original_path: Union[Path, str] = join(sep, "etc", "bunkerweb", "plugins"),
):
    if not isinstance(original_path, Path):
        original_path = Path(original_path)

    # Remove old external plugins files
    logger.info("Removing old external plugins files ...")
    for file in glob(str(original_path.joinpath("*"))):
        file = Path(file)
        if file.is_symlink() or file.is_file():
            file.unlink()
        elif file.is_dir():
            rmtree(str(file), ignore_errors=True)

    if plugins:
        logger.info("Generating new external plugins ...")
        original_path.mkdir(parents=True, exist_ok=True)
        for plugin in plugins:
            tmp_path = original_path.joinpath(plugin["id"], f"{plugin['name']}.tar.gz")
            tmp_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path.write_bytes(plugin["data"])
            with tar_open(str(tmp_path), "r:gz") as tar:
                tar.extractall(original_path)
            tmp_path.unlink()

            for job_file in glob(join(str(tmp_path.parent), "jobs", "*")):
                st = Path(job_file).stat()
                chmod(job_file, st.st_mode | S_IEXEC)
