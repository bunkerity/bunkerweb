"""Start all six staging images at once and require their healthchecks."""

from json import loads
from pathlib import Path
from subprocess import run
from tempfile import TemporaryDirectory
from time import sleep

from release_artifacts import IMAGES, command, require, write_json

TAG = "testing"


def compose_config():
    common = {
        "DATABASE_URI": "sqlite:////data/db.sqlite3",
        "USE_BUNKERNET": "no",
        "USE_BLACKLIST": "no",
        "USE_WHITELIST": "no",
        "SEND_ANONYMOUS_REPORT": "no",
        "API_WHITELIST_IP": "127.0.0.0/8 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16",
        # The API service and the all-in-one API exit(1) when no auth path is configured.
        "API_TOKEN": "smoke",
    }
    services = {
        name: {"image": f"ghcr.io/bunkerity/{name}-tests:{TAG}", "environment": dict(common), "volumes": ["shared:/data"], "restart": "no"} for name in IMAGES
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
    with TemporaryDirectory(prefix="staging-smoke-") as temporary:
        file = Path(temporary) / "compose.json"
        write_json(file, compose_config())
        compose = ["docker", "compose", "--project-name", "staging-smoke", "--file", str(file)]
        try:
            run([*compose, "up", "--detach", "--wait", "--wait-timeout", "600", "--no-build"], check=True)
            # Two healthy observations catch an immediately exiting entrypoint.
            sleep(10)
            containers = command([*compose, "ps", "--all", "--quiet"]).decode().split()
            require(len(containers) == len(IMAGES), "not all staging services started")
            for container in containers:
                state = loads(command(["docker", "inspect", container]))[0]
                require(state["State"]["Running"] and state["State"]["Health"]["Status"] == "healthy", "staging service unhealthy")
                require(state["RestartCount"] == 0, "staging service restarted")
                name = state["Config"]["Labels"]["com.docker.compose.service"]
                require(state["Config"]["Image"] == f"ghcr.io/bunkerity/{name}-tests:{TAG}", "unexpected running image")
        finally:
            run([*compose, "logs", "--no-color"], check=False)
            run([*compose, "down", "--volumes", "--remove-orphans"], check=True)


if __name__ == "__main__":
    main()
