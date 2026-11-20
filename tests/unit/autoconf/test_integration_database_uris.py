"""Kubernetes examples must connect every BunkerWeb component to the same database."""

from pathlib import Path
from urllib.parse import urlsplit

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
MANIFESTS = sorted((ROOT / "misc/integrations").glob("k8s.*.yml"))


@pytest.mark.parametrize("manifest", MANIFESTS, ids=lambda path: path.name)
def test_kubernetes_component_uris_match_database(manifest):
    containers = {}
    for document in yaml.safe_load_all(manifest.read_text()):
        if document and document.get("kind") in ("Deployment", "DaemonSet"):
            for container in document["spec"]["template"]["spec"]["containers"]:
                containers[container["name"]] = {entry["name"]: entry.get("value") for entry in container.get("env", [])}

    uris = {name: env["DATABASE_URI"] for name, env in containers.items() if "DATABASE_URI" in env}
    assert {"bunkerweb-controller", "bunkerweb-scheduler"} <= uris.keys()
    if ".ui." in manifest.name:
        assert "bunkerweb-ui" in uris
    assert len(set(uris.values())) == 1, uris

    uri = urlsplit(uris["bunkerweb-scheduler"])
    database = containers["bunkerweb-db"]
    if "POSTGRES_PASSWORD" in database:
        assert uri.scheme == "postgresql"
        assert uri.port == 5432
        assert (uri.username, uri.password, uri.path.lstrip("/")) == (database["POSTGRES_USER"], database["POSTGRES_PASSWORD"], database["POSTGRES_DB"])
    elif "MYSQL_PASSWORD" in database:
        assert uri.scheme in ("mysql+pymysql", "mariadb+pymysql")
        assert uri.port == 3306
        assert (uri.username, uri.password, uri.path.lstrip("/")) == (database["MYSQL_USER"], database["MYSQL_PASSWORD"], database["MYSQL_DATABASE"])
