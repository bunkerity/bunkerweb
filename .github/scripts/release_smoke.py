"""Start all six final images on one release platform and require their healthchecks."""

from json import loads
from os import environ
from pathlib import Path
from subprocess import run
from sys import argv
from tempfile import TemporaryDirectory
from time import sleep

from release_artifacts import IMAGES, PLATFORMS, command, load_manifest, require, write_json


def compose_config(manifest, platform):
    require(platform in PLATFORMS, "unknown release platform")
    common = {
        "DATABASE_URI": "sqlite:////data/db.sqlite3",
        "USE_BUNKERNET": "no",
        "USE_BLACKLIST": "no",
        "USE_WHITELIST": "no",
        "SEND_ANONYMOUS_REPORT": "no",
        "API_WHITELIST_IP": "127.0.0.0/8 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16",
    }
    services = {
        name: {"image": manifest["images"][name]["ref"], "platform": platform, "environment": dict(common), "volumes": ["shared:/data"], "restart": "no"}
        for name in IMAGES
    }
    services["bunkerweb"]["labels"] = {"bunkerweb.INSTANCE": "yes"}
    for name in ("scheduler", "autoconf"):
        services[name]["environment"].update(AUTOCONF_MODE="yes", MULTISITE="yes", SERVER_NAME="", BUNKERWEB_INSTANCES="")
    services["autoconf"]["volumes"].append("/var/run/docker.sock:/var/run/docker.sock:ro")
    services["autoconf"]["environment"]["DOCKER_HOST"] = "unix:///var/run/docker.sock"
    services["autoconf"]["user"] = "0:0"
    for name in ("ui", "api"):
        services[name]["depends_on"] = {"scheduler": {"condition": "service_healthy"}}
    services["all-in-one"]["volumes"] = ["aio:/data"]
    services["all-in-one"]["environment"].update(SERVER_NAME="smoke.example.com", SERVICE_API="yes", SERVICE_UI="yes", SERVICE_SCHEDULER="yes")
    return {"services": services, "volumes": {"shared": {}, "aio": {}}}


def main():
    platform = argv[1]
    manifest = load_manifest("release-manifest.json", environ["MANIFEST_SHA256"])
    with TemporaryDirectory(prefix="release-smoke-") as temporary:
        file = Path(temporary) / "compose.json"
        write_json(file, compose_config(manifest, platform))
        compose = ["docker", "compose", "--project-name", "release-smoke", "--file", str(file)]
        try:
            run([*compose, "up", "--detach", "--wait", "--wait-timeout", "600", "--no-build"], check=True)
            # Two healthy observations catch an immediately exiting entrypoint.
            sleep(10)
            containers = command([*compose, "ps", "--all", "--quiet"]).decode().split()
            require(len(containers) == len(IMAGES), "not all candidate services started")
            for container in containers:
                state = loads(command(["docker", "inspect", container]))[0]
                require(state["State"]["Running"] and state["State"]["Health"]["Status"] == "healthy", "candidate service unhealthy")
                require(state["RestartCount"] == 0, "candidate service restarted")
                name = state["Config"]["Labels"]["com.docker.compose.service"]
                require(state["Config"]["Image"] == manifest["images"][name]["ref"], "unexpected running image")
                version = command(["docker", "exec", container, "cat", "/usr/share/bunkerweb/VERSION"]).decode().strip()
                require(version == manifest["version"], "running image version differs from manifest")
                image = loads(command(["docker", "image", "inspect", state["Image"]]))[0]
                require(image["Architecture"] == platform.split("/")[1], "running image architecture differs from matrix")
        finally:
            run([*compose, "logs", "--no-color"], check=False)
            run([*compose, "down", "--volumes", "--remove-orphans"], check=True)


if __name__ == "__main__":
    main()
