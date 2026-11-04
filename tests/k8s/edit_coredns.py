from logging import getLogger
from os.path import abspath, dirname
from pathlib import Path
from sys import path as sys_path
from yaml import safe_dump, safe_load

sys_path.append(dirname(dirname(abspath(__file__))))

import utils.logger  # noqa: F401

LOGGER = getLogger("EDIT.CoreDNS")

# Load CoreDNS configmap
configmap_file = Path("/tmp/coredns-configmap.yaml")
configmap = safe_load(configmap_file.read_text())

LOGGER.debug(f"Base ConfigMap:\n{configmap}")

hosts_file = Path("tests/misc/conf/dnsmasq.hosts")
if not hosts_file.exists():
    raise FileNotFoundError(f"Hosts file not found: {hosts_file}")

hosts = hosts_file.read_text().strip().split("\n")

# Load configmap data
configmap_conf_file = Path("tests/misc/conf/coredns.conf")
configmap_conf = configmap_conf_file.read_text()

configmap["data"]["Corefile"] = configmap_conf.replace("%HOSTS%", "\n    ".join(hosts))

LOGGER.debug("Edited Corefile:\n%s", configmap["data"]["Corefile"])

# Write back to file
configmap_file.write_text(safe_dump(configmap, indent=2))
