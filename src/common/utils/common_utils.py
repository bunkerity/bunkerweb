from hashlib import sha512
from io import BytesIO
from os import getenv, sep
from pathlib import Path
from platform import machine
from typing import Dict, Union


def get_version() -> str:
    return Path(sep, "usr", "share", "bunkerweb", "VERSION").read_text(encoding="utf-8").strip()


def get_integration() -> str:
    try:
        integration_path = Path(sep, "usr", "share", "bunkerweb", "INTEGRATION")
        os_release_path = Path(sep, "etc", "os-release")
        if getenv("KUBERNETES_MODE", "no").lower() == "yes":
            return "Kubernetes"
        elif getenv("SWARM_MODE", "no").lower() == "yes":
            return "Swarm"
        elif getenv("AUTOCONF_MODE", "no").lower() == "yes":
            return "Autoconf"
        elif integration_path.is_file():
            return integration_path.read_text(encoding="utf-8").strip().lower()
        elif os_release_path.is_file() and "Alpine" in os_release_path.read_text(encoding="utf-8"):
            return "Docker"

        return "Linux"
    except:
        return "Unknown"


def get_os_info() -> Dict[str, str]:
    os_data = {
        "name": "Linux",
        "version": "Unknown",
        "version_id": "Unknown",
        "version_codename": "Unknown",
        "id": "Unknown",
        "arch": machine(),
    }

    os_release = Path("/etc/os-release")
    if os_release.exists():
        for line in os_release.read_text().splitlines():
            if "=" not in line or line.split("=")[0].strip().lower() not in os_data:
                continue
            os_data[line.split("=")[0].lower()] = line.split("=")[1].strip('"')

    return os_data


def file_hash(file: Union[str, Path]) -> str:
    _sha512 = sha512()
    if not isinstance(file, Path):
        file = Path(file)

    with file.open("rb") as f:
        while True:
            data = f.read(1024)
            if not data:
                break
            _sha512.update(data)
    return _sha512.hexdigest()


def bytes_hash(bio: Union[bytes, BytesIO]) -> str:
    if isinstance(bio, bytes):
        bio = BytesIO(bio)

    assert isinstance(bio, BytesIO)

    _sha512 = sha512()
    while True:
        data = bio.read(1024)
        if not data:
            break
        _sha512.update(data)
    bio.seek(0)
    return _sha512.hexdigest()
